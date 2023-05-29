FROM python:3.11-slim as python
ENV PYTHONUNBUFFERED=true
WORKDIR /app
RUN apt-get update
RUN apt-get install -y locales
RUN sed -i -e 's/# da_DK.UTF-8 UTF-8/da_DK.UTF-8 UTF-8/' /etc/locale.gen && \
    locale-gen

FROM python as poetry
ENV POETRY_HOME=/opt/poetry
ENV POETRY_VIRTUALENVS_IN_PROJECT=true
ENV PATH="$POETRY_HOME/bin:$PATH"
RUN python -c 'from urllib.request import urlopen; print(urlopen("https://install.python-poetry.org").read().decode())' | python -
COPY . ./
RUN poetry install --no-interaction --no-ansi -vvv --only main

FROM python as runtime
ENV PATH="/app/.venv/bin:$PATH"
ENV LC_ALL="da_DK.UTF-8"
ENV LANG="da_DK.UTF-8"
ENV LANGUAGE="da_DK.UTF-8"

COPY --from=poetry /app /app
COPY --from=python /usr/lib/locale/locale-archive /usr/lib/locale/locale-archive

RUN adduser --system --no-create-home -u 999 chores

RUN mkdir /data && \
   chown 999 /data

VOLUME ["/data"]

USER 999

CMD ["flask", "--app", "app", "run", "--host", "0.0.0.0"]
