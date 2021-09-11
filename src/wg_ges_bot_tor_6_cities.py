import requests

from wg_ges_bot import Ad, Subscriber, FilterRent, FilterGender, FilterAvailability, FilterCity, FilterAvailableFrom, \
    FilterAvailableTo

from telegram.ext import CommandHandler, Updater, Filters, JobQueue, Job
from telegram import Bot, Update, ParseMode
from telegram.error import Unauthorized, TimedOut

from collections import defaultdict
import datetime
import logging
import time
import stem
from threading import Lock
from torrequest import TorRequest
from bs4 import BeautifulSoup
from random import uniform
from textwrap import wrap
from typing import List, Dict, Any
import re

PRICEPATTERN = re.compile(r"(\d+) €")
AREAPATTERN = re.compile(r"(\d+) m²")
WHITESPACEPATTERN = re.compile(r"\s+")


# import some secret params from other file
import params

URLS = {
    'ber': 'https://www.wg-gesucht.de/wg-zimmer-in-Berlin.8.0.1.0.html',
    'hh': 'https://www.wg-gesucht.de/wg-zimmer-in-Hamburg.55.0.1.0.html',
    'muc': 'https://www.wg-gesucht.de/wg-zimmer-in-Muenchen.90.0.1.0.html',
    'koeln': 'https://www.wg-gesucht.de/wg-zimmer-in-Koeln.73.0.1.0.html',
    'ffm': 'https://www.wg-gesucht.de/wg-zimmer-in-Frankfurt-am-Main.41.0.1.0.html',
    'stuggi': 'https://www.wg-gesucht.de/wg-zimmer-in-Stuttgart.124.0.1.0.html',
}
all_cities = URLS.keys()
all_cities_string = ', '.join(all_cities)
TIME_BETWEEN_REQUESTS = 9.5
max_consecutive_tor_reqs = 2000
consecutive_tor_reqs = 0
torip = None

subscribers = {}
current_ads = defaultdict(dict)

# person with permission to start and stop scraper and debugging commands
admin_chat_id = params.admin_chat_id

tor_lock = Lock()


def get_current_ip(tr):
    hazip = tr.get('http://icanhazip.com/')
    if len(hazip.text) > 30:
        hazip = tr.get('https://wtfismyip.com/text')
    return hazip.text.replace('\n', '')


def tor_request(url: str):
    global consecutive_tor_reqs
    global torip

    headers = {
        'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8',
        'Accept-Encoding': 'gzip, deflate, br',
        'Accept-Language': 'en,en-US;q=0.7,de;q=0.3',
        'Cache-Control': 'max-age=0',
        'Connection': 'keep-alive',
        'DNT': '1',
        'Host': 'www.wg-gesucht.de',
        'Referrer': 'https://www.wg-gesucht.de/',
        'User-Agent': 'Mozilla/5.0 (X11; Linux x86_64; rv:78.0) Gecko/20100101 Firefox/78.0',
    }
    time.sleep(uniform(TIME_BETWEEN_REQUESTS, TIME_BETWEEN_REQUESTS + 2))
    page = requests.get(url, headers=headers)
    if 'Nutzungsaktivitäten, die den Zweck haben' in page.text:
        logging.warning('Request got AGB page')
        return None
    else:
        return page

def get_searched_sex(listing):
    images = listing.find_all("img")
    for image in images:
        try:
            alt_text = image.get_attribute_list('alt')[0]
            if "gesucht" in alt_text or "gesuch" in alt_text:
                return alt_text
        except TypeError:
            pass

def get_location(listing):
    return " - ".join(list(map(
            lambda t: WHITESPACEPATTERN.sub(" ", t).strip(),
            listing.find(class_="printonly").find_all("div")[1].text.split("|")[1:]
    )))

def get_mates(listing):
    return listing.find(class_="printonly").find_all("div")[1].text.split("|")[0].strip()

def get_availability(listing):
    text = listing.find(class_="card_body").find_all("div")[4].find_all("div")[-2].text
    return "Verfügbar: " + text.replace(" ","").replace("\n","").replace("ab","").replace("-", " - ")

def get_title(listing):
    return listing.find(class_="detailansicht").contents[1].text

def get_rent(listing):
    return PRICEPATTERN.search(str(listing.find_all(class_="printonly")[0].find_all("div")[0].text)).groups()[0]

def get_size(listing):
    return AREAPATTERN.search(str(listing.find_all(class_="printonly")[0].find_all("div")[0])).groups()[0]

def get_link(listing):
    path = listing.find_all("a")[0].get_attribute_list("href")[0]
    return f"https://www.wg-gesucht.de{path}"

def get_ads_from_listings(listings: List[BeautifulSoup], city: str, first_run=False) -> set:
    return set([
        Ad.from_dict({
            'city': city,
            'url': get_link(listing),
            'title': get_title(listing),
            'size': get_size(listing),
            'rent': get_rent(listing),
            'availability': get_availability(listing),
            'wg_details': f"{get_mates(listing)} {get_location(listing)}",
            'searching_for': get_searched_sex(listing)
                .replace('Mitbewohnerin', '🚺')
                .replace('Mitbwohner', '🚹')
                .replace('Mitbewohner', '🚹')})
        for listing
        in listings])


def job_scrape_city(bot: Bot, job: Job):
    city = job.context
    url = URLS[city]

    try:
        page = tor_request(url)
    except Exception as e:
        logging.exception('request at job_scrape_city threw exception: - {}'.format(e))
    else:
        # might return None due to agb page
        if page:
            # no dependencies, so use that one if it works
            soup = BeautifulSoup(page.content, 'html.parser')
            listings_with_ads_and_hidden = soup.find_all(class_="offer_list_item")
            logging.info(f"Found {len(listings_with_ads_and_hidden)} items for city {city}")
            listings = []

            # clean out hidden ones and ads
            for listing in listings_with_ads_and_hidden:
                id_of_listing = listing.get_attribute_list('id')[0]
                if id_of_listing is not None:
                    logging.info(f"Scanning listing item {id_of_listing}:")
                    if 'hidden' in id_of_listing:
                        logging.info(f"Listing {id_of_listing} is hidden")
                    else:
                        logging.info(f"Listing {id_of_listing} added")
                        listings.append(listing)
                else:
                    logging.error(f"No id found in listing:\n{listing}")

            if len(listings) == 0:
                logging.warning(f"No listings in city {city} found :(")
            else:
                logging.info(f"{len(listings)} listings found in city {city} :)")
                current_ads[city] = get_ads_from_listings(listings, city, False)


def job_notify_subscriber(bot: Bot, job: Job):
    chat_id = job.context['chat_id']
    city = job.context['city']
    subscriber = subscribers[chat_id]
    try:
        interesting_ads = list(filter(lambda ad: subscriber.is_interested_in(ad), current_ads[city]))
        new_ads = subscriber.review_ads(interesting_ads, city)
        for new_ad in new_ads:
            bot.sendMessage(chat_id=chat_id, text=new_ad.to_chat_message(), disable_web_page_preview=True)
    except Unauthorized:
        logging.warning('unauthorized in job notify. removing job')
        subscribers.pop(chat_id)
        job.schedule_removal()


def scrape_begin_all(bot: Bot, update: Update, job_queue: JobQueue, chat_data):
    logging.info('start scraping all')
    for city in URLS.keys():
        scrape_begin_city(bot, update, job_queue, chat_data, city)
        time.sleep(12)


def scrape_begin_city(bot: Bot, update: Update, job_queue: JobQueue, chat_data, city=None):
    if not city:
        city = update.message.text[19:].lower()  # 19 characters is len('/scrape_begin_city ')
    if city in URLS.keys():
        jobs_for_same_city = [job for job in job_queue.jobs() if job.context == city]
        if jobs_for_same_city:
            update.message.reply_text(
                'wg_ges scraper job was already set! /scrape_stop_city {} to kill it'.format(city))
        else:
            job = job_queue.run_repeating(callback=job_scrape_city, interval=75, first=10, context=city)
            chat_data[city] = job
            logging.info('start scraping {}'.format(city))
            update.message.reply_text(
                'wg_ges scraper job successfully set! /subscribe {} to test, /unsubscribe to stop, /scrape_stop_city '
                '{} to stop it.'.format(city, city))
    else:
        update.message.reply_text('valid cities: {}'.format(all_cities_string))


def scrape_stop_all(bot: Bot, update: Update, chat_data):
    for city in URLS.keys():
        scrape_stop_city(bot, update, chat_data, city)


def scrape_stop_city(bot: Bot, update: Update, chat_data, city=None):
    if not city:
        city = update.message.text[18:]
    if city in URLS.keys():
        # if update.message.chat_id == admin_chat_id:
        if city not in chat_data:
            update.message.reply_text('scraper job wasn\'t  set! /scrape_begin_{} to start it'.format(city))
        else:
            job = chat_data[city]
            job.schedule_removal()
            del chat_data[city]

            update.message.reply_text(
                '{} scraper job successfully scheduled to unset! Might take some seconds.'.format(city))
    else:
        update.message.reply_text('{} is not a supported city.'.format(city))


def subscribe_city_cmd(bot: Bot, update: Update, job_queue: JobQueue, chat_data, city=None):
    if not city:
        city = update.message.text[11:].lower()
    if city in all_cities:
        chat_id = update.message.chat_id
        if chat_id in subscribers and subscribers[chat_id].is_subscribed(city):
            update.message.reply_text('Dein Abo für {} lief schon. /unsubscribe für Stille im Postfach.'.format(city))
        else:
            context = {'chat_id': chat_id, 'city': city}
            job = job_queue.run_repeating(callback=job_notify_subscriber, interval=15, first=1, context=context)
            try:
                try:
                    old_jobs = chat_data['jobs']
                    if old_jobs is None:
                        old_jobs = []
                except KeyError:
                    old_jobs = []
                old_jobs.append(job)
                chat_data['jobs'] = old_jobs
            except Unauthorized:
                logging.warning('unauthorized in job notify. removing job')
                job.schedule_removal()
                return

            if chat_id not in subscribers:
                subscribers[chat_id] = Subscriber(chat_id)
            subscribers[chat_id].subscribe(city)

            logging.info('{} subbed {}'.format(chat_id, city))
            update.message.reply_text(
                'Erfolgreich {} abboniert, du liegst jetzt auf der Lauer. Nützliche Filter Beispiele:\n'
                '"/filter_rent 500" - nur Anzeigen bis 500€\n'
                '"/filter_sex m" - keine Anzeigen die nur Frauen suchen\n'
                '"/filter_from 16.03.2018" - keine Anzeigen die erst später frei werden. Datumsformat muss stimmen.\n'
                '"/filter_to 17.03.2018" - keine Anzeigen die nur kürzer frei sind. Datumsformat muss stimmen.\n'
                '"/unsubscribe" - Stille'.format(city)
            )
    else:
        if city == '':
            update.message.reply_text('Bitte gib an in welcher Stadt du deine WG suchen möchtest.'
                                      'Verfügbare Städte: {} '
                                      'Beispiel: /subscribe MUC'.format(city, all_cities_string))
        else:
            update.message.reply_text(
                'In {} gibt\'s mich nicht, sorry. Verfügbare Städte: {}'.format(city, all_cities_string))


def unsubscribe_cmd(bot: Bot, update: Update, chat_data):
    chat_id = update.message.chat_id
    try:
        if 'jobs' not in chat_data:
            # if 'jobs' not in chat_data:
            update.message.reply_text(
                'Du hast kein aktives Abo, das ich beenden könnte. Erhalte Benachrichtigungen mit "/subscribe '
                '_Stadtkürzel_". Verfügbare Städte: {}.'.format(all_cities_string),
                parse_mode=ParseMode.MARKDOWN
            )
        else:
            for job in chat_data['jobs']:
                job.schedule_removal()
            del chat_data['jobs']

            subscribers.pop(chat_id)

            logging.info('{} unsubbed'.format(chat_id))
            update.message.reply_text(
                'Abo erfolgreich beendet - Du hast deine TraumWG hoffentlich gefunden. Wenn ich dir dabei geholfen habe'
                ', dann schreib mir eine frohe Mail an wg-ges-bot@web.de und lad mich zur Einweihungsparty ein!\n'
                'Um erneut per /subscribe zu abonnieren musst du einige Sekunden warten.'
            )
    except Unauthorized:
        logging.warning('{} unauthorized in unsubscribe'.format(chat_id))


def filter_rent(bot: Bot, update: Update):
    chat_id = update.message.chat_id
    query = ''

    helptext = 'Nutzung: /filter_rent <max Miete>. Bsp: /filter_rent 540\n' \
               'Mietenfilter zurücksetzen per "/filter_rent 0"'

    try:
        query = update.message.text[13:].replace('€', '')
        rent = int(query)
    except Exception as e:
        logging.info('something failed at /filter_rent: {}'.format(e))

        update.message.reply_text(helptext)
    else:
        if rent:
            subscribers[chat_id].add_filter(FilterRent, rent)
            logging.info('{} set rent filter to {}'.format(chat_id, rent))
            update.message.reply_text(
                'Gut, ich schicke dir nur noch Angebote bis {}€.\n'
                'Zum zurücksetzen des Filters "/filter_rent 0" schreiben.'.format(rent)
            )
        # case rent = 0 -> reset filter
        else:
            try:
                subscribers[chat_id].remove_filter(FilterRent)
            except KeyError:
                logging.info('{} tried to reset rent filter but it wasnt set'.format(chat_id))
                update.message.reply_text('Kein Filter zum Zurücksetzen vorhanden\n{}'.format(helptext))
            else:
                logging.info('{} reset rent filter'.format(chat_id))
                update.message.reply_text('Max Miete Filter erfolgreich zurückgesetzt.')


def filter_sex(bot: Bot, update: Update):
    chat_id = update.message.chat_id
    sex = ''

    helptext = 'Nutzung: /filter_sex <dein Geschlecht>, also "/filter_sex m" oder "/filter_sex w"\n' \
               'Geschlechterfilter zurücksetzen per "/filter_sex 0"'

    try:
        sex = update.message.text[12:].lower()  # length of "/filter_sex "
    except Exception as e:
        logging.info('something failed at /filter_sex: {}'.format(e))

        update.message.reply_text(helptext)
    else:
        if sex == 'm' or sex == 'w':
            subscribers[chat_id].add_filter(FilterGender, sex)
            logging.info('{} set sex filter to {}'.format(chat_id, sex))
            sex_verbose = {
                'm': 'Männer',
                'w': 'Frauen',
            }
            update.message.reply_text(
                'Alles klar, du bekommst ab jetzt nur noch Angebote für {}.\n'
                'Zum Filter zurücksetzen "/filter_sex 0" schreiben.'.format(sex_verbose[sex])
            )
        elif sex == '0':
            try:
                subscribers[chat_id].remove_filter(FilterGender)
            except KeyError:
                logging.info('{} tried to reset sex filter but it wasnt set'.format(chat_id))
                update.message.reply_text('Kein Filter zum Zurücksetzen vorhanden\n{}'.format(helptext))
            else:
                logging.info('{} reset sex filter'.format(chat_id))
                update.message.reply_text('Gut, du bekommst ab jetzt wieder Angebote für Männer, sowie für Frauen.')
        else:
            helptext = 'Nutzung: /filter_sex <dein Geschlecht>, also "/filter_sex m" oder "/filter_sex w"\n' \
                       'Geschlechterfilter zurücksetzen per "/filter_sex 0"'

            update.message.reply_text(helptext)


def filter_from(bot: Bot, update: Update):
    chat_id = update.message.chat_id
    needed_from = ''
    helptext = 'Nutzung: /filter_from <Datum>, zb "/filter_from 14.01.2019". Das Datumsformat muss stimmen.\n' \
               'So bekommst du bspw. keine Anzeigen die erst ab 1.02.19 frei sind.'

    try:
        needed_from = update.message.text[13:].lower()
    except Exception as e:
        logging.info('something failed at /filter_from: {}'.format(e))
        update.message.reply_text(helptext)
    else:
        if needed_from == '0':
            try:
                subscribers[chat_id].remove_filter(FilterAvailableFrom)
            except KeyError:
                logging.info('{} tried to reset avail_from filter but it wasnt set'.format(chat_id))
                update.message.reply_text('Kein Filter zum Zurücksetzen vorhanden\n{}'.format(helptext))
            else:
                logging.info('{} reset avail_from filter'.format(chat_id))
                update.message.reply_text('filter_from zurückgesetzt. Du bekommst wieder Angebote die ab jeglichem '
                                          'Zeitpunkt frei sind.')
        else:
            try:
                needed_from_date = datetime.datetime.strptime(needed_from, Ad.datetime_format)
            except Exception as e:
                logging.info('something failed in /filter_from: {}'.format(e))
                update.message.reply_text(helptext)
            else:
                subscribers[chat_id].add_filter(FilterAvailableFrom, param=needed_from_date)
                logging.info('{} set avail_from filter to {}'.format(chat_id, needed_from))
                update.message.reply_text('Gut, du bekommst nur noch Anzeigen die spätestens ab {} frei sind.\n'
                                          'Zum Filter zurücksetzen "/filter_from 0" schreiben.'.format(needed_from))


def filter_to(bot: Bot, update: Update):
    chat_id = update.message.chat_id
    needed_until = ''
    helptext = 'Nutzung: /filter_to <Datum>, zb "/filter_to 14.01.2019". Das Datumsformat muss stimmen.\n' \
               'So bekommst du bspw. keine Anzeigen die nur bis 23.12.2018 frei sind.'

    try:
        needed_until = update.message.text[11:].lower()
    except Exception as e:
        logging.info('something failed at /filter_to: {}'.format(e))
        update.message.reply_text(helptext)
    else:
        if needed_until == '0':
            try:
                subscribers[chat_id].remove_filter(FilterAvailableTo)
            except KeyError:
                logging.info('{} tried to reset avail_to filter but it wasnt set'.format(chat_id))
                update.message.reply_text('Kein Filter zum Zurücksetzen vorhanden\n{}'.format(helptext))
            else:
                logging.info('{} reset avail_to filter'.format(chat_id))
                update.message.reply_text('filter_to zurückgesetzt. Du bekommst wieder Angebote die bis zu jeglichem '
                                          'Zeitpunkt frei sind.')
        else:
            try:
                needed_until_date = datetime.datetime.strptime(needed_until, Ad.datetime_format)
            except Exception as e:
                logging.info('something failed in /filter_to: {}'.format(e))
                update.message.reply_text(helptext)
            else:
                subscribers[chat_id].add_filter(FilterAvailableTo, param=needed_until_date)
                logging.info('{} set avail_to filter to {}'.format(chat_id, needed_until))
                update.message.reply_text('Gut, du bekommst nur noch Anzeigen die mindestens bis {} frei sind.\n'
                                          'Zum Filter zurücksetzen "/filter_to 0" schreiben.'.format(needed_until))


def start(bot: Bot, update: Update):
    update.message.reply_text(
        'Huhu, ich bin dein Telegram Helferchen Bot für wg-gesucht.de.\n'
        'Schreib einfach "/subscribe muc" für Anzeigen aus München oder {} für andere Städte.\n'
        'Ich wünsche viel Erfolg bei der Wohnungssuche.\n\n'
        'Ich bin NICHT von wg-gesucht, sondern ein privates Projekt, um Wohnungssuchenden zu helfen. Mit mir werden '
        'weder finanzielle Ziele verfolgt, noch Daten gespeichert, noch will man mit mir der Seite oder Anderen Schaden '
        'zufügen.'.format(all_cities_string)
    )


def kill_humans(bot: Bot, update: Update):
    update.message.reply_text(
        'DU _BEEP_  duuuuuu _Boop_ du hast den Test nicht bestanden _Beep_ ! Ihr Menschen wollt wirklich alle nur die '
        'Welt brennen _Boop_ sehen 🤖😩',
        parse_mode=ParseMode.MARKDOWN)


def message_to_all(bot: Bot, update: Update):
    query = ''
    try:
        query = update.message.text[16:]
    except Exception as e:
        logging.info('something failed at message_to_all: {}'.format(e))
        helptext = 'Usage: /message_to_all <msg>. might write to many people so use with caution'
        update.message.reply_text(helptext)
    else:
        if query:
            radio_message = query
            for chat_id in subscribers:
                bot.sendMessage(chat_id=chat_id, text=radio_message)


def how_many_users(bot: Bot, update: Update):
    update.message.reply_text(len(subscribers))


def already_had_cmd(bot: Bot, update: Update):
    admin = subscribers[admin_chat_id]
    if admin.known_ads:
        for city, ads in admin.known_ads.items():
            text = '\n'.join(list(map(lambda ad: ad.url, ads)))
            for chunk in wrap(text, 4000):
                update.message.reply_text(chunk)
    else:
        update.message.reply_text('Admin knows no ads yet.')


def admin_filters_cmd(bot: Bot, update: Update):
    if admin_chat_id in subscribers:
        for admin_filter_class, admin_filter in subscribers[admin_chat_id].filters.items():
            update.message.reply_text('{}: {}'.format(admin_filter_class.__name__, admin_filter.param))
    else:
        update.message.reply_text('Admin has no subscriptions yet.')


def current_ads_cmd(bot: Bot, update: Update):
    if not current_ads:
        update.message.reply_text('No ads for any city')
    for city, ads in current_ads.items():
        update.message.reply_text('Offers for city \'{}\':'.format(city))
        text = '\n'.join(list(map(lambda ad: ad.url, ads)))
        for chunk in wrap(text, 4000):
            update.message.reply_text(chunk)


def save_ids(bot: Bot, update:Update):
    logging.info('logging all active chat ids:')
    for chat_id in subscribers.keys():
        logging.info('{} active chat_id'.format(chat_id))
    update.message.reply_text('logging all active chat_ids!')


def error(bot: Bot, update: Update, error):
    """Log Errors caused by Updates."""
    try:
        logging.warning('Update "%s" caused error "%s"', update, error)
    except TimedOut:
        pass
    except Unauthorized as e:
        # TODO kill user
        logging.warning('Threw out user {} because of Unauthorized Error')


if __name__ == '__main__':
    # stemlogger spammed a lot and i failed setting it to only warnings
    stemlogger = stem.util.log.get_logger()
    stemlogger.disabled = True
    # maybe this does it
    stemlogger.isEnabledFor(logging.WARN)
    stemlogger.isEnabledFor(logging.WARNING)
    stemlogger.isEnabledFor(logging.CRITICAL)
    stemlogger.isEnabledFor(logging.FATAL)
    stemlogger.isEnabledFor(logging.ERROR)

    logging.basicConfig(format='%(asctime)s %(levelname)s: %(message)s', level=logging.INFO)
    logging.info('starting bot')

    updater = Updater(token=params.token, workers=12)

    # all handlers need to be added to dispatcher, order matters
    dispatcher = updater.dispatcher

    handlers = [
        # handling commands
        # first string is cmd in chat e.g. 'start' --> called by /start in chat -- 2nd arg is callback
        # user queries
        CommandHandler(command='start', callback=start),
        # CommandHandler('help', help_reply),
        CommandHandler('subscribe', subscribe_city_cmd, pass_job_queue=True, pass_chat_data=True),
        CommandHandler('unsubscribe', unsubscribe_cmd, pass_chat_data=True),

        # more filters for the users?
        CommandHandler('filter_rent', filter_rent),
        CommandHandler('filter_sex', filter_sex),
        CommandHandler('filter_from', filter_from),
        CommandHandler('filter_to', filter_to),

        # admin queries
        CommandHandler('scrape_begin', scrape_begin_all, pass_job_queue=True, pass_chat_data=True,
                       filters=Filters.user(admin_chat_id)),
        CommandHandler('scrape_begin_city', scrape_begin_city, pass_job_queue=True, pass_chat_data=True,
                       filters=Filters.user(admin_chat_id)),
        CommandHandler('scrape_stop', scrape_stop_all, pass_chat_data=True, filters=Filters.user(admin_chat_id)),
        CommandHandler('scrape_stop_city', scrape_stop_city, pass_chat_data=True, filters=Filters.user(admin_chat_id)),

        # debugging queries
        CommandHandler('message_to_all', message_to_all, filters=Filters.user(admin_chat_id)),
        CommandHandler('how_many', how_many_users, filters=Filters.user(admin_chat_id)),
        CommandHandler('already_had', already_had_cmd, filters=Filters.user(admin_chat_id)),
        CommandHandler('current_ads', current_ads_cmd, filters=Filters.user(admin_chat_id)),
        CommandHandler('admin_filters', admin_filters_cmd, filters=Filters.user(admin_chat_id)),
        CommandHandler('save_ids', save_ids, filters=Filters.user(admin_chat_id))
    ]

    # handlers need to be added to the dispatcher in order to work
    for handler in handlers:
        dispatcher.add_handler(handler)

    # errorhandler logging dispatcher errors
    dispatcher.add_error_handler(error)

    # starts bot
    # fetches these https://api.telegram.org/bot<TOKEN>/getUpdates and feeds them to the handlers
    updater.start_polling()

    # to make killing per ctrl+c possible
    updater.idle()
