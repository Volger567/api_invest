FROM python:3.8
ENV PYTHONBUFFERED 1
RUN mkdir -p /code/backend
COPY requirements.txt /code/backend
WORKDIR /code/backend
RUN pip install -r requirements.txt
COPY . /code/backend