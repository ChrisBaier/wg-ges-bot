FROM python:3-slim-buster

RUN apt -y update
RUN apt -y upgrade


WORKDIR /app

ADD . ./

RUN pip install -r requirements.txt


CMD [ "python3", "src/wg_ges_bot_tor_6_cities.py" ]
