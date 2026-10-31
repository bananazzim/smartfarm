from django import forms

from .models import Greenhouse


class GreenhouseForm(forms.ModelForm):
    class Meta:
        model = Greenhouse
        fields = ["name", "shape", "length_m", "width_m", "height_m", "ventilation", "crop", "sensor_count"]
        widgets = {
            "name": forms.TextInput(attrs={"placeholder": "예: A동 테스트 온실"}),
            "length_m": forms.NumberInput(attrs={"min": "0.1", "max": "500", "step": "0.1"}),
            "width_m": forms.NumberInput(attrs={"min": "0.1", "max": "500", "step": "0.1"}),
            "height_m": forms.NumberInput(attrs={"min": "0.1", "max": "500", "step": "0.1"}),
            "sensor_count": forms.NumberInput(attrs={"min": "1", "max": "99"}),
        }
