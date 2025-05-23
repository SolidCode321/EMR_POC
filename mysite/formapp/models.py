from django.db import models

class AudioFile(models.Model):
    file = models.FileField(upload_to='audio/')
    uploaded_at = models.DateTimeField(auto_now_add=True)


class MedicalForm(models.Model):
    title = models.CharField(max_length=255)
    pdf = models.FileField(upload_to='forms/')
    uploaded_at = models.DateTimeField(auto_now_add=True)
