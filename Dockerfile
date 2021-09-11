FROM python:3-slim-buster

RUN apt -y update
RUN apt -y upgrade
RUN apt -y install tor obfs4proxy

COPY torrc /etc/tor/torrc

WORKDIR /app

ADD . ./

EXPOSE 9101
EXPOSE 9102
EXPOSE 9051

RUN pip install -r requirements.txt

CMD [ "python3", "wg_ges_bot_tor_6_cities.py" ]