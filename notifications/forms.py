from django import forms

from .models import AlertSetting


class AlertSettingForm(forms.ModelForm):
    class Meta:
        model = AlertSetting
        fields = ["greenhouse", "phone", "temperature_min", "temperature_max", "humidity_min", "humidity_max"]
        widgets = {
            "temperature_min": forms.NumberInput(attrs={"step": "0.1"}),
            "temperature_max": forms.NumberInput(attrs={"step": "0.1"}),
            "humidity_min": forms.NumberInput(attrs={"step": "0.1", "min": "0", "max": "100"}),
            "humidity_max": forms.NumberInput(attrs={"step": "0.1", "min": "0", "max": "100"}),
        }
