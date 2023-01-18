FROM python:3.8-slim-buster

WORKDIR /app

COPY main.py main.py

CMD [ "python3", "-u", "/app/main.py" ]
