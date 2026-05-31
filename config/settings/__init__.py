import os


ENVIRONMENT = os.getenv('ENVIRONMENT', 'local')


if ENVIRONMENT == 'production':
    from .local import *
else:
    from .production import *
