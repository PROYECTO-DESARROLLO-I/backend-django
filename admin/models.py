from django.db import models

# Create your models here.


class Admin(models.Model):
    user_id = models.ForeignKey("user.User", on_delete=models.CASCADE)
    headquarters_id = models.ForeignKey(Headquarters, on_delete=models.CASCADE)
    # TODO: roles?
