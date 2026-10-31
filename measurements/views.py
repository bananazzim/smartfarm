import json
import logging
import secrets
from io import BytesIO
from datetime import timedelta

import pandas as pd
import plotly.graph_objects as go
from django.conf import settings
from django.contrib import messages
from django.db import DatabaseError, IntegrityError, transaction
from django.http import JsonResponse
from django.shortcuts import redirect, render
from django.utils import timezone
from django.views.decorators.csrf import csrf_exempt
from django.views.decorators.http import require_POST

from greenhouses.models import Greenhouse
from sensors.models import Sensor

from .demo import sample_measurement_frame
from .models import Measurement
from .services import parse_timestamp, validate_csv_frame, validate_measurement_values

logger = logging.getLogger(__name__)


def analysis(request):
    greenhouses = Greenhouse.objects.all()
    greenhouse_id = request.GET.get("greenhouse")
    greenhouse = greenhouses.filter(pk=greenhouse_id).first() if greenhouse_id and greenhouse_id.isdigit() else greenhouses.first()
    sensors = greenhouse.sensors.all() if greenhouse else Sensor.objects.none()
    selected_ids = request.GET.getlist("sensor")
    selected_sensors = sensors.filter(external_id__in=selected_ids) if selected_ids else sensors
    qs = Measurement.objects.filter(greenhouse=greenhouse, sensor__in=selected_sensors).select_related("sensor") if greenhouse else Measurement.objects.none()
    period = request.GET.get("period", "24h")
    if period not in {"24h", "7d", "30d", "all"}:
        period = "24h"
    if period != "all":
        delta = {"24h": timedelta(hours=24), "7d": timedelta(days=7), "30d": timedelta(days=30)}[period]
        qs = qs.filter(timestamp__gte=timezone.now() - delta)
    data = list(qs.order_by("timestamp").values("timestamp", "sensor__name", "temperature", "humidity", "source"))
    if not data:
        data = sample_measurement_frame(selected_sensors, periods=48).to_dict(orient="records")
    frame = pd.DataFrame(data)
    if period != "all":
        frame = frame[frame["timestamp"] >= timezone.now() - delta]
    temperature = go.Figure()
    humidity = go.Figure()
    sensor_palette = ("#c83e59", "#f26b75", "#56748a", "#b07a37")
    for index, (name, subset) in enumerate(frame.groupby("sensor__name")):
        color = sensor_palette[index % len(sensor_palette)]
        temperature.add_trace(go.Scatter(x=subset["timestamp"], y=subset["temperature"], name=name, mode="lines", line={"color": color, "width": 2}))
        humidity.add_trace(go.Scatter(x=subset["timestamp"], y=subset["humidity"], name=name, mode="lines", line={"color": color, "width": 2, "dash": "dot"}))
    charts = []
    for figure, unit in [(temperature, "온도 (°C)"), (humidity, "상대습도 (%)")]:
        figure.update_layout(
            height=380,
            margin={"l": 8, "r": 8, "t": 12, "b": 8},
            paper_bgcolor="rgba(0,0,0,0)",
            plot_bgcolor="rgba(0,0,0,0)",
            font={"family": "Pretendard, sans-serif", "color": "#666474", "size": 12},
            yaxis={"title": unit, "gridcolor": "#eeeaf0"},
            xaxis={"showgrid": False},
            legend={"orientation": "h", "y": 1.15},
        )
        charts.append(figure.to_html(full_html=False, include_plotlyjs="cdn" if not charts else False, config={"displayModeBar": False, "responsive": True}))
    is_demo = not any(item["source"] != "demo" for item in data)
    source_text = "SAMPLE DATA · 고정 시드 데모" if is_demo else "업로드/API/저장 데이터"
    stats = {key: {"mean": round(float(frame[key].mean()), 2), "min": round(float(frame[key].min()), 2), "max": round(float(frame[key].max()), 2)} for key in ("temperature", "humidity")}
    context = {
        "greenhouses": greenhouses, "greenhouse": greenhouse, "sensors": sensors,
        "selected_ids": selected_ids, "period": period, "charts": charts, "stats": stats,
        "source_text": source_text, "is_demo": is_demo,
    }
    return render(request, "measurements/analysis.html", context)


def csv_upload(request):
    from django.core.exceptions import ValidationError
    from django.shortcuts import get_object_or_404
    from .importing import read_upload, inspect_rows, ImportConfirmationForm, commit_import

    if request.method != "POST":
        return redirect("analysis")
    greenhouse_id = request.POST.get("greenhouse_id", "")
    if not greenhouse_id.isdigit():
        messages.error(request, "대상 온실을 선택해 주세요.", extra_tags="csv-upload")
        return redirect("analysis")
    greenhouse = get_object_or_404(Greenhouse, pk=greenhouse_id)
    form = None
    try:
        if request.POST.get("stage") == "confirm":
            staged = request.session.get("csv_import")
            if not staged or staged["greenhouse"] != greenhouse.pk or staged["token"] != request.POST.get("token"):
                raise ValueError("업로드 확인 정보가 만료되었거나 대상 온실이 다릅니다. 다시 업로드해 주세요.")
            rows = staged["rows"]
        else:
            upload = request.FILES.get("file")
            if not upload:
                raise ValueError("CSV 파일을 선택해 주세요.")
            request.session.pop("csv_import", None)
            rows = read_upload(upload)
            staged = {"greenhouse": greenhouse.pk, "rows": rows, "token": secrets.token_urlsafe(24)}
        plans, normalized = inspect_rows(rows, greenhouse)
        form = ImportConfirmationForm(plans, greenhouse, request.POST if request.POST.get("stage") == "confirm" else None)
        if request.POST.get("stage") == "confirm" and form.is_valid():
            created, duplicates = commit_import(rows, greenhouse, form)
            request.session.pop("csv_import", None)
            from urllib.parse import urlencode
            sensor_ids = [plan["sid"] for plan in plans]
            request.session["optimization_selection"] = {**request.session.get("optimization_selection", {}), str(greenhouse.pk): sensor_ids}
            selection_query = urlencode([("sensor", sid) for sid in sensor_ids])
            messages.success(request, f"CSV {created}건을 저장했습니다. 동일 데이터 {duplicates}건은 중복 저장하지 않았습니다.", extra_tags="csv-upload")
            return redirect(f"/optimization/?greenhouse={greenhouse.pk}&mode=real&selection=1&{selection_query}")
        request.session["csv_import"] = staged
        return render(request, "measurements/import_confirm.html", {"greenhouse": greenhouse, "form": form, "token": staged["token"], "row_count": len(rows), "sensor_count": len(plans)})
    except (ValueError, ValidationError, UnicodeDecodeError, pd.errors.ParserError, pd.errors.EmptyDataError) as exc:
        if form is not None and request.POST.get("stage") == "confirm":
            form.add_error(None, str(exc))
            return render(request, "measurements/import_confirm.html", {"greenhouse": greenhouse, "form": form, "token": staged["token"], "row_count": len(rows), "sensor_count": len(plans)})
        messages.error(request, f"CSV를 저장하지 못했습니다. 이번 파일은 저장되지 않았습니다: {exc}", extra_tags="csv-upload")
    except DatabaseError:
        logger.exception("CSV database write failed")
        messages.error(request, "데이터베이스 오류로 이번 파일은 저장되지 않았습니다.", extra_tags="csv-upload")
    return redirect(f"/analysis/?greenhouse={greenhouse.pk}&period=all#csv-upload")


@csrf_exempt
@require_POST
def ingest_measurements(request):
    expected_token = settings.MEASUREMENT_INGEST_TOKEN
    if not expected_token:
        logger.error("Measurement ingest endpoint used before server token configuration")
        return JsonResponse({"error": "ingest_not_configured", "detail": "서버에 MEASUREMENT_INGEST_TOKEN이 설정되지 않았습니다."}, status=503)
    supplied = request.headers.get("X-API-Key", "")
    if not supplied and request.headers.get("Authorization", "").startswith("Bearer "):
        supplied = request.headers["Authorization"][7:]
    if not secrets.compare_digest(supplied, expected_token):
        logger.warning("Measurement ingest authentication failed")
        return JsonResponse({"error": "unauthorized", "detail": "유효한 API 토큰이 필요합니다."}, status=401)
    try:
        payload = json.loads(request.body)
    except (json.JSONDecodeError, UnicodeDecodeError):
        logger.warning("Measurement ingest rejected malformed JSON")
        return JsonResponse({"error": "invalid_json", "detail": "JSON 요청 본문을 확인해 주세요."}, status=400)
    items = payload if isinstance(payload, list) else [payload]
    if not items or len(items) > 500:
        logger.warning("Measurement ingest rejected batch size %d", len(items))
        return JsonResponse({"error": "invalid_batch_size", "detail": "요청당 1~500건만 전송할 수 있습니다."}, status=400)
    prepared = []
    errors = []
    for index, item in enumerate(items):
        try:
            if not isinstance(item, dict):
                raise ValueError("각 측정 데이터는 JSON 객체여야 합니다.")
            required = {"timestamp", "greenhouse_id", "sensor_id", "temperature", "humidity", "x", "y", "z"}
            missing = required - set(item)
            if missing:
                raise ValueError(f"필수 필드 누락: {', '.join(sorted(missing))}")
            greenhouse = Greenhouse.objects.get(pk=int(item["greenhouse_id"]))
            sensor = Sensor.objects.get(greenhouse=greenhouse, external_id=str(item["sensor_id"]).strip())
            timestamp = parse_timestamp(item["timestamp"])
            values = validate_measurement_values(item, greenhouse, sensor)
            prepared.append(Measurement(timestamp=timestamp, greenhouse=greenhouse, sensor=sensor, source=Measurement.Source.API, **values))
        except (ValueError, TypeError, KeyError, Greenhouse.DoesNotExist, Sensor.DoesNotExist, OverflowError) as exc:
            errors.append({"index": index, "detail": str(exc)})
    if errors:
        logger.warning("Measurement ingest validation rejected %d item(s)", len(errors))
        return JsonResponse({"error": "validation_error", "details": errors}, status=400)
    created = 0
    duplicates = 0
    try:
        with transaction.atomic():
            for record in prepared:
                _, was_created = Measurement.objects.get_or_create(
                    sensor=record.sensor,
                    timestamp=record.timestamp,
                    defaults={
                        "greenhouse": record.greenhouse,
                        "temperature": record.temperature,
                        "humidity": record.humidity,
                        "x": record.x,
                        "y": record.y,
                        "z": record.z,
                        "source": record.source,
                    },
                )
                created += int(was_created)
                duplicates += int(not was_created)
    except IntegrityError:
        logger.exception("Measurement ingest database write failed")
        return JsonResponse({"error": "storage_error", "detail": "측정 데이터를 저장하지 못했습니다."}, status=500)
    return JsonResponse({"created": created, "duplicates": duplicates, "total": len(prepared)}, status=201 if created else 200)
