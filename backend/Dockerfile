FROM elixir:1.19.5-alpine AS build

RUN apk add --no-cache build-base git nodejs npm postgresql-client bash

WORKDIR /app

RUN mix local.hex --force && \
    mix local.rebar --force

ENV MIX_ENV=dev

COPY mix.exs mix.lock ./
RUN mix deps.get --only dev
RUN mix deps.compile

COPY config config
COPY lib lib
COPY priv priv
COPY .formatter.exs .

RUN mix compile

COPY entrypoint.sh /entrypoint.sh
RUN chmod +x /entrypoint.sh

EXPOSE 4000

CMD ["/entrypoint.sh"]
