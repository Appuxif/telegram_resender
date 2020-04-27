from django import forms
from .models import TelegramClient


class TelegramClientForm(forms.ModelForm):
    password = forms.CharField(max_length=255, widget=forms.PasswordInput, required=False)

    class Meta:
        model = TelegramClient
        exclude = ('id', )
