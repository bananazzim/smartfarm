"""Validated, session-staged CSV import. No database writes before confirmation."""
from io import StringIO
import math

import pandas as pd
from django import forms
from django.db import transaction

from sensors.geometry import validate_position
from sensors.models import Sensor
from .models import Measurement
from .services import CSV_ALIASES, CSV_COLUMNS, is_csv_null, parse_timestamp


def read_upload(upload):
    if upload.size > 5 * 1024 * 1024:
        raise ValueError("CSV 파일은 5MB 이하로 업로드해 주세요.")
    content = upload.read()
    try:
        text = content.decode("utf-8-sig")
    except UnicodeDecodeError:
        text = content.decode("cp949")
    frame = pd.read_csv(StringIO(text), dtype=str, nrows=10001)
    frame.columns = [CSV_ALIASES.get(c.strip().lstrip("\ufeff"), c.strip().lstrip("\ufeff")) for c in frame.columns]
    if frame.columns.duplicated().any() or CSV_COLUMNS - set(frame.columns):
        raise ValueError("필수 컬럼 누락 또는 중복 컬럼이 있습니다: " + ", ".join(sorted(CSV_COLUMNS)))
    if frame.empty or len(frame) > 10000:
        raise ValueError("CSV는 1~10,000행이어야 합니다.")
    return frame.where(pd.notna(frame), None).to_dict("records")


def inspect_rows(rows, greenhouse):
    existing = {s.external_id: s for s in greenhouse.sensors.all()}
    plans, normalized, seen = {}, [], {}
    for line, row in enumerate(rows, 2):
        try:
            sid = str(row["sensor_id"]).strip()
            if is_csv_null(row["sensor_id"]) or len(sid) > 80:
                raise ValueError("sensor_id: 1~80자의 센서 ID가 필요합니다.")
            gid = row["greenhouse_id"]
            if not is_csv_null(gid) and float(gid) != greenhouse.pk:
                raise ValueError("온실 ID가 선택된 온실과 일치하지 않습니다.")
            stamp = parse_timestamp(row["timestamp"])
            values = {}
            for key in ("temperature", "humidity", "x", "y", "z"):
                if is_csv_null(row[key]):
                    if key in ("temperature", "humidity"):
                        raise ValueError(f"{key}: 필수 측정값이 없습니다.")
                    values[key] = None
                else:
                    values[key] = float(row[key])
                    if not math.isfinite(values[key]):
                        raise ValueError(f"{key}: 유한한 숫자가 필요합니다.")
            if not -50 <= values["temperature"] <= 80 or not 0 <= values["humidity"] <= 100:
                raise ValueError("temperature(-50~80°C) 또는 humidity(0~100%) 범위 오류")
            sensor = existing.get(sid)
            coordinates = [values[a] if values[a] is not None else (float(getattr(sensor, a)) if sensor and getattr(sensor, a) is not None else None) for a in "xyz"]
            # Validate supplied axes even while other axes await user input.
            for axis, coordinate, bound in zip("xyz", coordinates, (greenhouse.length_m, greenhouse.width_m, greenhouse.height_m)):
                if values[axis] is not None and not 0 <= coordinate <= float(bound):
                    raise ValueError(f"{axis}: 온실 크기 범위를 벗어났습니다.")
            position_error = ""
            if all(c is not None for c in coordinates):
                try:
                    validate_position(greenhouse, coordinates)
                except ValueError as exc:
                    if all(values[a] is not None for a in "xyz"):
                        raise
                    position_error = str(exc)
            if sid not in plans:
                old = [float(getattr(sensor, a)) if sensor and getattr(sensor, a) is not None else None for a in "xyz"]
                plans[sid] = {"sid": sid, "coordinates": coordinates, "old": old, "existing": bool(sensor), "changed": bool(sensor) and old != coordinates, "position_error": position_error}
            elif plans[sid]["coordinates"] != coordinates:
                raise ValueError(f"{sid}: 한 파일에 여러 설치 위치가 있습니다. 위치별로 파일을 분리해 주세요.")
            entry = {"sid": sid, "timestamp": stamp.isoformat(), **values}
            key = (sid, stamp)
            if key in seen:
                if seen[key] != entry:
                    raise ValueError("중복 데이터의 측정값 또는 좌표가 충돌합니다.")
                continue
            seen[key] = entry
            normalized.append(entry)
        except (ValueError, TypeError, OverflowError, KeyError) as exc:
            raise ValueError(f"{line}행: {exc}") from exc
    return list(plans.values()), normalized


class ImportConfirmationForm(forms.Form):
    def __init__(self, plans, greenhouse, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.sensor_fields = []
        for index, plan in enumerate(plans):
            fields = []
            for axis, value, bound in zip("xyz", plan["coordinates"], (greenhouse.length_m, greenhouse.width_m, greenhouse.height_m)):
                key = f"sensor_{index}_{axis}"
                self.fields[key] = forms.DecimalField(label=f"{plan['sid']} · {axis.upper()} (m)", initial=value, min_value=0, max_value=bound, max_digits=8, decimal_places=3, widget=forms.NumberInput(attrs={"step": ".001"}))
                fields.append(self[key])
            self.sensor_fields.append({"plan": plan, "fields": fields})
        self.fields["confirm"] = forms.BooleanField(label="센서 위치와 측정 데이터 저장을 확인합니다. 기존 위치 변경 시 과거 측정 좌표는 유지됩니다.")


@transaction.atomic
def commit_import(rows, greenhouse, form):
    # Lock the target greenhouse to serialize uploads and recheck current DB state.
    type(greenhouse).objects.select_for_update().get(pk=greenhouse.pk)
    plans, normalized = inspect_rows(rows, greenhouse)
    sensors = {}
    for index, plan in enumerate(plans):
        coordinates = [form.cleaned_data[f"sensor_{index}_{a}"] for a in "xyz"]
        validate_position(greenhouse, coordinates)
        sensor, _ = Sensor.objects.get_or_create(greenhouse=greenhouse, external_id=plan["sid"], defaults={"name": plan["sid"], "status": Sensor.Status.ACTIVE})
        # The visible confirmation fields explicitly approve any location change.
        for axis, value in zip("xyz", coordinates):
            setattr(sensor, axis, value)
        sensor.full_clean()
        sensor.save()
        sensors[plan["sid"]] = sensor
    created, duplicates = 0, len(rows) - len(normalized)
    for row in normalized:
        sensor = sensors[row["sid"]]
        coordinates = {a: float(getattr(sensor, a)) for a in "xyz"}
        validate_position(greenhouse, coordinates.values())
        values = {"greenhouse": greenhouse, "temperature": row["temperature"], "humidity": row["humidity"], "source": Measurement.Source.CSV, **coordinates}
        record, new = Measurement.objects.get_or_create(sensor=sensor, timestamp=parse_timestamp(row["timestamp"]), defaults=values)
        if not new:
            if any(getattr(record, k) != values[k] for k in ("temperature", "humidity", "x", "y", "z")):
                raise ValueError(f"{row['sid']} / {row['timestamp']}: 기존 측정값 또는 좌표와 충돌합니다.")
            duplicates += 1
        created += int(new)
    greenhouse.sensor_count = greenhouse.sensors.count()
    greenhouse.save(update_fields=["sensor_count"])
    return created, duplicates
