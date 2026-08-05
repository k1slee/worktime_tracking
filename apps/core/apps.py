from django.apps import AppConfig
from django.db.backends.signals import connection_created
from django.dispatch import receiver


class CoreConfig(AppConfig):
    default_auto_field = 'django.db.models.BigAutoField'
    name = 'apps.core'
    verbose_name = 'Ядро системы'

    def ready(self):
        @receiver(connection_created)
        def configure_sqlite_connection(sender, connection, **kwargs):
            if connection.vendor == 'sqlite':
                cursor = connection.cursor()
                cursor.execute('PRAGMA journal_mode=WAL;')
                cursor.execute('PRAGMA synchronous=NORMAL;')
                cursor.execute('PRAGMA busy_timeout=30000;')
                cursor.execute('PRAGMA cache_size=-64000;')
                cursor.execute('PRAGMA temp_store=MEMORY;')
                cursor.close()