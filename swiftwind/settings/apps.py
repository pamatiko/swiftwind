from django.apps import AppConfig
from django.conf import settings as django_settings
from django.db.utils import DatabaseError


class SettingsConfig(AppConfig):
    name = 'swiftwind.settings'

    def ready(self):
        from swiftwind.settings.models import Settings

        try:
            db_settings = Settings.objects.get()
        except DatabaseError:
            # Maybe we are running migrations on the settings table
            return

        # TODO: Move all settings into here, stop accessing settings model directly
        if db_settings.smtp_host:
            django_settings.DEFAULT_FROM_EMAIL = db_settings.from_email
            django_settings.EMAIL_HOST = db_settings.smtp_host
            django_settings.EMAIL_HOST_PASSWORD = db_settings.smtp_password
            django_settings.EMAIL_HOST_USER = db_settings.smtp_user
            django_settings.EMAIL_PORT = db_settings.smtp_port
            django_settings.EMAIL_SUBJECT_PREFIX = db_settings.smtp_subject_prefix
            django_settings.EMAIL_USE_TLS = db_settings.smtp_use_tls
            django_settings.EMAIL_USE_SSL = db_settings.smtp_use_ssl
            django_settings.EMAIL_TIMEOUT = 10
