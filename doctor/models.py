from django.db import models

# Create your models here.


class Doctor(models.Model):
    user_id = models.ForeignKey("User.user", on_delete=models.CASCADE)
    eps_id = models.ForeignKey("eps.EPS", on_delete=models.SET_NULL)
    identity_document = models.CharField()
    register_number = models.CharField()  # medic register number
    phone_number = models.CharField()
    active = models.BooleanField()
