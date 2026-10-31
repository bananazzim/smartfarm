from django.contrib import messages
from django.shortcuts import redirect, render

from greenhouses.models import Greenhouse

from .forms import AlertSettingForm
from .models import AlertEvent, AlertSetting
from .services import NotificationService


def alert_management(request):
    greenhouse_id = request.POST.get("greenhouse") or request.GET.get("greenhouse")
    greenhouse = Greenhouse.objects.filter(pk=greenhouse_id).first() if greenhouse_id and greenhouse_id.isdigit() else Greenhouse.objects.first()
    setting = AlertSetting.objects.filter(greenhouse=greenhouse).first() if greenhouse else None
    form = AlertSettingForm(
        request.POST if request.method == "POST" else None,
        instance=setting,
        initial={"greenhouse": greenhouse.pk} if greenhouse and not setting else None,
    )
    if request.method == "POST" and form.is_valid():
        setting = form.save()
        if request.POST.get("simulate") == "1":
            message = f"[DEMO 알림] {setting.greenhouse.name} 온실의 가상 환경 경보입니다. 온도/습도 기준을 확인해 주세요."
            result = NotificationService().send(setting.phone, message)
            AlertEvent.objects.create(greenhouse=setting.greenhouse, message=result["message"], status=result["status"])
            messages.success(request, "가상 알림 기록을 생성했습니다. 문자 발송은 이루어지지 않았습니다.")
        else:
            messages.success(request, "알림 기준을 저장했습니다.")
        return redirect("notifications")
    return render(request, "notifications/manage.html", {
        "form": form,
        "greenhouse": greenhouse,
        "events": AlertEvent.objects.select_related("greenhouse")[:10],
    })
