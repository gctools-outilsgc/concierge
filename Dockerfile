FROM python:3.6-alpine

RUN apk --no-cache add \
    nodejs \
    npm \
    gcc \
    jpeg-dev \
    musl-dev \
    pcre-dev \
    linux-headers \
    postgresql-dev \
    zlib-dev \
    mailcap \
    gettext

COPY . /app

WORKDIR /app

## Update NPM
RUN npm install -g npm

## Install and update NPM packages
RUN npm install --legacy-peer-deps && \
    npm run build

RUN mv /app/docker/start.sh /start.sh
RUN chmod +x /start.sh

RUN pip3 install virtualenv && \
    virtualenv /app/env && \
    /app/env/bin/pip install -r requirements.txt

ENV PATH="/app/env/bin:${PATH}"
EXPOSE 8000
CMD ["/start.sh"]
