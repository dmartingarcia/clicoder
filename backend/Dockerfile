FROM elixir:1.19.5-alpine AS build

RUN apk add --no-cache build-base git nodejs npm postgresql-client bash

ENV MIX_HOME=/opt/mix
RUN mix local.hex --force && \
    mix local.rebar --force

RUN addgroup -g 1000 -S app && adduser -u 1000 -S -G app app

COPY entrypoint.sh /entrypoint.sh
RUN chmod +x /entrypoint.sh

WORKDIR /app

ENV MIX_ENV=dev

RUN chown -R app:app /app /opt/mix

USER app

COPY --chown=app:app mix.exs mix.lock ./
RUN mix deps.get --only dev
RUN mix deps.compile

COPY --chown=app:app config config
COPY --chown=app:app lib lib
COPY --chown=app:app priv priv
COPY --chown=app:app .formatter.exs .

RUN mix compile

EXPOSE 4000

CMD ["/entrypoint.sh"]
