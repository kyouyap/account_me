FROM python:3.9.6

WORKDIR /app

RUN apt update -y && \
    apt install -y curl

ENV POETRY_HOME /etc/poetry
RUN curl -sSL https://install.python-poetry.org | POETRY_HOME=$POETRY_HOME python3 -
ENV PATH="$POETRY_HOME/bin:$PATH"
ENV PYTHONPATH /app

COPY ./app /app

RUN poetry config virtualenvs.create false && \
    poetry install
WORKDIR /app/src