"""Shared data selection for results and the simulator; never mix demo and real rows."""
import math
from time import perf_counter
from urllib.parse import urlencode
import pandas as pd
from django.core.exceptions import BadRequest
from django.db.models import Count, Min, Max
from django.utils import timezone

from measurements.models import Measurement
from sensors.geometry import validate_position
from .engine import evaluate_combinations


def request_sensor_ids(request, greenhouse):
    if not greenhouse:
        return None
    key = str(greenhouse.pk)
    saved = request.session.get("optimization_selection", {})
    explicit = "selection" in request.GET or "sensor" in request.GET
    ids = list(dict.fromkeys(request.GET.getlist("sensor"))) if explicit else saved.get(key)
    if ids is not None:
        registered = set(greenhouse.sensors.values_list("external_id", flat=True))
        if set(ids) - registered:
            if explicit:
                raise BadRequest("분석 대상 센서는 선택한 온실에 등록되어 있어야 합니다.")
            return None
    if explicit and request.GET.get("mode") != "demo":
        request.session["optimization_selection"] = {**saved, key: ids}
    return ids


def evaluation_context(greenhouse, mode=None, sensor_ids=None, *, analyze=True):
    started = perf_counter()
    timings = {}
    qs = Measurement.objects.filter(greenhouse=greenhouse).exclude(source=Measurement.Source.DEMO) if greenhouse else Measurement.objects.none()
    is_demo = mode == "demo" or (mode != "real" and not qs.exists())
    context = {"is_demo": is_demo, "analysis_error": "", "analysis_warning": "", "results": [], "candidate_count": 0, "combination_count": 0, "common_count": 0, "sensor_choices": [], "selected_sensor_ids": []}
    if is_demo:
        if analyze:
            context.update(evaluate_combinations())
        if greenhouse:
            points = {"P1": (.15, .20), "P2": (.15, .80), "P3": (.38, .50), "P4": (.62, .20), "P5": (.62, .80), "P6": (.85, .50)}
            sensors = [{"name": sid, "x": float(greenhouse.length_m)*x, "y": float(greenhouse.width_m)*y, "z": min(1.5, float(greenhouse.height_m)*.6)} for sid, (x,y) in points.items()]
        else:
            sensors = []
    else:
        sensors = [{"name": s.external_id, **{axis: float(getattr(s, axis)) if getattr(s, axis) is not None else None for axis in "xyz"}} for s in greenhouse.sensors.all()] if greenhouse else []
        summaries = {r["sensor__external_id"]: r for r in qs.order_by().values("sensor__external_id").annotate(records=Count("pk"), first=Min("timestamp"), last=Max("timestamp"))}
        if sensor_ids is None:
            latest = max((r["last"] for r in summaries.values()), default=None)
            sensor_ids = [s["name"] for s in sensors if latest is not None and summaries.get(s["name"], {}).get("last") == latest]
        sensor_ids = list(dict.fromkeys(sensor_ids))
        if set(sensor_ids) - {s["name"] for s in sensors}:
            raise BadRequest("분석 대상 센서는 선택한 온실에 등록되어 있어야 합니다.")
        context["selected_sensor_ids"] = sensor_ids
        context["sensor_query"] = urlencode([("selection", "1")] + [("sensor", sid) for sid in sensor_ids])
        context["sensor_choices"] = [{"id": s["name"], "selected": s["name"] in sensor_ids, **summaries.get(s["name"], {"records": 0})} for s in sensors]
        qs = qs.filter(sensor__external_id__in=sensor_ids)
        timings["selection_ms"] = (perf_counter()-started)*1000
        queried = perf_counter()
        rows = list(qs.order_by("timestamp").values("timestamp", "sensor__external_id", "temperature", "humidity")) if analyze else []
        timings["query_ms"] = (perf_counter()-queried)*1000
        if rows:
            prepared = perf_counter()
            frame = pd.DataFrame(rows).rename(columns={"sensor__external_id": "sensor_id"})
            count = len(sensor_ids)
            context["candidate_count"] = count
            common = frame.groupby("timestamp").sensor_id.nunique()
            common = common[common == count].index
            frame = frame[frame.timestamp.isin(common)]
            context["common_count"] = len(common)
            timings["prepare_ms"] = (perf_counter()-prepared)*1000
            if count < 3:
                context["analysis_error"] = f"선택 센서 {count}개 · 공통 시각 {len(common)}개. 측정 센서가 3개 미만이어서 3개 조합 분석을 수행할 수 없습니다. 아래에서 센서를 선택해 주세요."
            elif len(common) < 4:
                context["analysis_error"] = f"선택 센서 {count}개 · 공통 시각 {len(common)}개. 선택 센서 모두의 공통 시각이 4개 이상 필요합니다. 기록 기간을 확인하고 같은 시기에 측정한 센서만 선택해 주세요. 누락 시각을 생성하거나 보간하지 않습니다."
            elif math.comb(count, 3) > 5000:
                context["analysis_error"] = "조합 수가 5,000개를 초과합니다. 분석 대상 센서 수를 줄여 주세요."
            else:
                evaluated = perf_counter()
                context.update(evaluate_combinations(frame))
                timings["evaluate_ms"] = (perf_counter()-evaluated)*1000
                context["common_count"] = len(common)
                dropped = len(rows) - len(frame)
                context["analysis_warning"] = f"선택 센서 {count}개 · 공통 측정 시각 {len(common)}개 사용 · 불완전 시각의 측정 행 {dropped}개 제외. "
                if count == 3:
                    context["analysis_warning"] += "센서가 3개이므로 조합은 1개이며 비교 가능한 다른 조합이 없습니다. "
                if len(common) < 24 or (max(common)-min(common)).total_seconds() < 86400:
                    context["analysis_warning"] += "측정 기간 또는 공통 시각 수가 적어 결과를 일반화하기 어렵습니다."
                current = {s["name"]: tuple(s[a] for a in "xyz") for s in sensors}
                history = qs.order_by().values_list("sensor__external_id", "x", "y", "z").distinct()
                if any(tuple(position[1:]) != current.get(position[0]) for position in history):
                    context["analysis_warning"] += " 설치 위치 변경 이력이 있습니다. 측정별 과거 좌표는 보존되며, 3D는 현재 등록 위치를 표시합니다. 위치별 분석이 필요하면 기간을 분리한 데이터로 검토해 주세요."
                for key in ("train_start", "train_end", "validation_start", "validation_end"):
                    context[key] = timezone.localtime(pd.Timestamp(context[key]).to_pydatetime()).isoformat()
        elif analyze:
            context["analysis_error"] = f"선택 센서 {len(sensor_ids)}개 · 공통 시각 0개. 분석할 실제 측정 데이터가 없습니다. 아래에서 센서를 선택하거나 CSV를 업로드해 주세요."
        context["recommended_query"] = urlencode([("selection", "1")] + [("sensor", sid) for sid in sensor_ids] + [("highlight", sid) for sid in context.get("recommended", {}).get("sensors", [])])
        # Position candidates follow the explicit analysis set; unrelated legacy
        # and demo-only sensors remain registered but do not crowd this scene.
        sensors = [sensor for sensor in sensors if sensor["name"] in sensor_ids]
    for sensor in sensors:
        try:
            validate_position(greenhouse, [sensor[a] for a in "xyz"])
            sensor["position_valid"] = True
            sensor["relative"] = [round(sensor[a]/float(bound)*100, 1) for a, bound in zip("xyz", (greenhouse.length_m, greenhouse.width_m, greenhouse.height_m))]
        except ValueError as exc:
            sensor["position_valid"] = False
            sensor["position_error"] = str(exc)
    context["position_sensors"] = sensors
    context["scene_data"] = {
        "length": float(greenhouse.length_m) if greenhouse else 0,
        "width": float(greenhouse.width_m) if greenhouse else 0,
        "height": float(greenhouse.height_m) if greenhouse else 0,
        "shape": greenhouse.shape if greenhouse else "single",
        "sensors": sensors,
        "selected": context.get("recommended", {}).get("sensors", context["selected_sensor_ids"] if not analyze else []),
        "combinations": {str(row["rank"]): row["sensors"] for row in context["results"]},
    }
    context["analysis_timings"] = {**timings, "total_ms": (perf_counter()-started)*1000}
    return context
