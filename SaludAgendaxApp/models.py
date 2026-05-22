from django.db import models

# Create your models here.
#


class User(models.Model):
    roles = [
        "Patient",
        "Doctor",
        "Admin",
        "SuperAdmin"
    ]
    name = models.CharField(max_length=30)
    last_name = models.CharField(max_length=30)
    email = models.EmailField(unique=True)
    role = models.CharField(max_length=20, choices=roles)
    active = models.BooleanField(default=False)
    created_at = models.DateTimeField()
    updated_at = models.DateTimeField()


class Patient(models.Model):
    document_types = [
        "CC",
        "TI",
        "RC",
        "PPT",
        "PEP"
    ]
    user_id = models.ForeignKey(User, on_delete=models.CASCADE)
    identity_document = models.CharField(unique=True)
    document_type = models.CharField(choices=document_types)
    date_birth = models.DateField()
    phone_number = models.CharField(max_length=10)
    address = models.TextField()


class EPS(models.Model):
    name = models.CharField(max_length=255)
    code = models.CharField(max_length=255)
    active = models.BooleanField()


class Doctor(models.Model):
    user_id = models.ForeignKey(User, on_delete=models.CASCADE)
    eps_id = models.ForeingKey(EPS, on_delete=models.SET_NULL)
    identity_document = models.CharField()
    register_number = models.CharField()  # medic register number
    phone_number = models.CharField()
    active = models.BooleanField()


class Headquarters(models.Model):
    pass


class Admin(models.Model):
    user_id = models.ForeignKey(User, on_delete=models.CASCADE)
    headquarters_id = models.ForeignKey(Headquarters, on_delete=models.CASCADE)
    # TODO: roles?


class Specialties(models.Model):
    name = models.CharField(max_length=100)
    description = models.TextField()
    active = models.BooleanField()
