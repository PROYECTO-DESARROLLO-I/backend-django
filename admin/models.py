"""Compatibility module for the old local admin app.

The domain model for administrative staff now lives in the `administrative` app
so it does not collide conceptually with `django.contrib.admin`.
"""

from administrative.models import Administrative as Admin

__all__ = ["Admin"]
