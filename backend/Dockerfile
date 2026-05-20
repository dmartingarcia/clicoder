FROM elixir:1.15-alpine AS build

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

EXPOSE 4000

CMD ["mix", "phx.server"]
