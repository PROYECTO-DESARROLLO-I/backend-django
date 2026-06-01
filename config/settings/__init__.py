import os

ENVIRONMENT = os.getenv("ENVIRONMENT", "local")

if ENVIRONMENT == "production":
    from .production import *
elif ENVIRONMENT == "test":
    from .test import *
else:
    from .local import *
