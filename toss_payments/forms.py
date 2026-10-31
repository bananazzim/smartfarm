from datetime import datetime

from django import forms
from django.utils import timezone


class SurveyForm(forms.Form):
    DISCOVERY_SOURCE_CHOICES = (
        ("youtube", "유튜브"),
        ("naver_blog", "네이버 블로그"),
        ("instagram", "인스타그램"),
        ("google", "웹 검색"),
        ("referral", "지인 소개"),
        ("other", "기타"),
    )
    CONSULTING_INTEREST_CHOICES = (
        ("greenhouse_consulting", "온실 환경 상담"),
        ("sensor_education", "센서 위치 최적화 교육"),
        ("other", "기타"),
    )
    INVESTMENT_BUDGET_CHOICES = (
        ("under_100k", "10만 원 미만"),
        ("100k_300k", "10만~30만 원"),
        ("300k_1m", "30만~100만 원"),
        ("1m_3m", "100만~300만 원"),
        ("3m_10m", "300만~1,000만 원"),
        ("over_10m", "1,000만 원 이상"),
        ("undecided", "아직 정하지 않았습니다."),
    )
    REVENUE_CHOICES = (
        ("not_operating", "운영 전"),
        ("under_10m", "1,000만 원 미만"),
        ("10m_30m", "1,000만~3,000만 원"),
        ("30m_100m", "3,000만~1억 원"),
        ("100m_300m", "1억~3억 원"),
        ("300m_1b", "3억~10억 원"),
        ("over_1b", "10억 원 이상"),
        ("prefer_not", "응답하지 않음"),
    )
    PROFIT_CHOICES = (
        ("not_operating", "운영 전"),
        ("loss", "적자"),
        ("under_10m", "1,000만 원 미만"),
        ("10m_30m", "1,000만~3,000만 원"),
        ("30m_100m", "3,000만~1억 원"),
        ("100m_300m", "1억~3억 원"),
        ("over_300m", "3억 원 이상"),
        ("prefer_not", "응답하지 않음"),
    )

    discovery_source = forms.ChoiceField(choices=DISCOVERY_SOURCE_CHOICES)
    consulting_interest = forms.ChoiceField(choices=CONSULTING_INTEREST_CHOICES)
    investment_budget = forms.ChoiceField(choices=INVESTMENT_BUDGET_CHOICES)
    annual_revenue = forms.ChoiceField(
        choices=(("", "선택하지 않음"),) + REVENUE_CHOICES,
        required=False,
    )
    annual_profit = forms.ChoiceField(
        choices=(("", "선택하지 않음"),) + PROFIT_CHOICES,
        required=False,
    )


class ReservationForm(forms.Form):
    customer_name = forms.CharField(max_length=50)
    customer_phone = forms.RegexField(
        regex=r"01[016789]-?[0-9]{3,4}-?[0-9]{4}\Z",
        max_length=13,
    )
    consulting_date = forms.DateField()
    consulting_time = forms.TimeField()
    greenhouse_location = forms.CharField(max_length=200, required=False)
    consulting_request = forms.CharField(max_length=2000, required=False)
    privacy_consent = forms.BooleanField(required=True)

    def clean(self):
        cleaned_data = super().clean()
        consultation_date = cleaned_data.get("consulting_date")
        consultation_time = cleaned_data.get("consulting_time")
        if consultation_date and consultation_time:
            requested_at = timezone.make_aware(
                datetime.combine(consultation_date, consultation_time),
                timezone.get_current_timezone(),
            )
            if requested_at <= timezone.now():
                raise forms.ValidationError("현재 시각보다 이후의 상담 일시를 선택해 주세요.")
        return cleaned_data
