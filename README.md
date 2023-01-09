# Pleio account

This is the Pleio microservice used for handling user registration, login and SAML2 SSO. It is based on [Django project](https://www.djangoproject.com/) and handles login througout the Pleio ecosystem using OAuth2.

## Setup development (through Docker)
For windows: make sure you configure git to not do CRLF before you pull (git config --global core.autocrlf false)

Make sure [Docker](https://www.docker.com/) and [Docker Compose](https://docs.docker.com/compose/install/) is installed. Then run the following commands within the repository:

    docker-compose -f docker-compose.dev.yml up

Then create a superuser account using:
    docker-compose exec web python manage.py createsuperuser

Now login with your new (superuser) account on http://localhost:8000

The docker-compose.dev.yml is meant to be used in non HTTPS settings like a development environment

## Setup development (manually)

To setup the development environment, make sure Python3 and yarn is installed on your development machine. Then run the following commands:

    mkvirtualenv pleio_account --python=/usr/bin/python3
    pip install -r requirements.txt
    yarn install

Send up and configure a mail server (ex: sendmail)

Make sure postgres is installed and configured and a database is created for your app.

Create your configuration file

    sudo cp pleio_account/config.example.py pleio_account/config.py

In your new config file set secret key, allowed hosts, and debug variables. 
Set your database config like:

    DATABASES = {
        'default': {
            'ENGINE': 'django.db.backends.postgresql',
            'NAME': 'your_database_name',
            'USER': 'Your_database_user',
            'PASSWORD': 'Your_database_password',
            'HOST': '127.0.0.1',
            'PORT': '',
        }
    }

Create a database using

    python manage.py migrate

Now create a superuser account using:

    python manage.py createsuperuser

Start a yarn and Django server using:

    python manage.py runserver localhost:8000
    yarn run watch

Now login with your new (superuser) account on http://localhost:8000

## Deploy to Kubernetes
  kubectl create namespace gctoolsv2
  kubectl create -f https://raw.githubusercontent.com/gctools-outilsgc/pleio_account/master/kubernetes/deployment.yaml

## Deploy using Docker
Make sure [Docker](https://www.docker.com/) and [Docker Compose](https://docs.docker.com/compose/install/) is installed. Then run the following commands within the repository:

    docker-compose -f docker-compose.yml up --build -d

Then create a superuser account using:
    docker-compose exec web python manage.py createsuperuser

Now login with your new (superuser) account on https://DOMAIN_NAME:8000

The docker-compose.yml is meant to be use behind a Nginx Proxy that handles the HTTPS connection

## Generate new translations

We use the standard [i18n toolset of Django](https://docs.djangoproject.com/en/1.10/topics/i18n/). To add new translations to the source files use:

    python manage.py makemessages

To compile the translations use:

    python manage.py compilemessages

On OSX first make sure gettext (> 0.14) is installed and linked using:

    brew install gettext
    brew link --force gettext

## Run tests

To run the accompanied test suite use:

    python manage.py test
