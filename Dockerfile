FROM python:3-slim-buster

RUN apt -y update
RUN apt -y upgrade
RUN apt -y install tor obfs4proxy

COPY /res/torrc /etc/tor/torrc

WORKDIR /app

ADD src/. ./

RUN pip install -r requirements.txt

EXPOSE 9101
EXPOSE 9102
EXPOSE 9051


CMD [ "python3", "wg_ges_bot_tor_6_cities.py" ]