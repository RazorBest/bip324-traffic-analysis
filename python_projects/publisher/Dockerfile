FROM python:3.12-slim

COPY . /work
WORKDIR /work
RUN chmod u+x main.py
RUN pip install .
RUN apt-get update && apt-get install -y git openssh-client && rm -rf /var/lib/apt/lists/*
