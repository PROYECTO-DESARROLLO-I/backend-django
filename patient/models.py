from django.db import models

# Create your models here.


class Patient(models.Model):
    document_types = [
        "CC",
        "TI",
        "RC",
        "PPT",
        "PEP",
        "CE",
        "Pasaporte"
    ]
    user_id = models.ForeignKey("user.User", on_delete=models.CASCADE)
    identity_document = models.CharField(unique=True)
    document_type = models.CharField(choices=document_types)
    date_birth = models.DateField()
    phone_number = models.CharField(max_length=10)
    address = models.TextField()
