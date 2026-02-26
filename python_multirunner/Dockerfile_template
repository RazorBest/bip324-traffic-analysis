FROM python:3.12-slim

COPY . /work
WORKDIR /work

SHELL ["/bin/bash", "-c"]

RUN for project in $(ls -d */); do \
        cd $project && \
        pip install . && \
        if [ -f ./install_dependecies ]; then ./install_dependecies; fi && \
        cd .. \
    ;done
