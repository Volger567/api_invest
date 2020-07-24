FROM python:3.8-alpine
ENV PYTHONBUFFERED 1
RUN apk update && apk add postgresql-dev gcc python3-dev musl-dev bash curl
RUN mkdir -p /logs
RUN mkdir -p /code/backend
COPY requirements.txt /code/backend
WORKDIR /code/backend
RUN pip install -r requirements.txt
COPY . /code/backend