from django.apps import AppConfig


class CoreConfig(AppConfig):
    name = 'core'

    def ready(self):
        # Makes sure all signal handlers are connected
        from core import handler
