# forms.py
from django import forms
from .models import MedicalForm

class MedicalFormForm(forms.ModelForm):
    class Meta:
        model = MedicalForm
        fields = ['name', 'pdf_file']