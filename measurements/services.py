import hashlib
import math

import pandas as pd

from django.utils import dateparse, timezone

from .models import Measurement

CSV_COLUMNS = {"timestamp", "greenhouse_id", "sensor_id", "temperature", "humidity", "x", "y", "z"}
CSV_ALIASES = dict(zip(
    ("측정일시", "온실ID", "센서ID", "온도(°C)", "습도(%)", "X좌표(m)", "Y좌표(m)", "Z좌표(m)"),
    ("timestamp", "greenhouse_id", "sensor_id", "temperature", "humidity", "x", "y", "z"),
))


def is_csv_null(value):
    return pd.isna(value) or str(value).strip().lower() in {"", "null"}


def parse_timestamp(value):
    if not isinstance(value, str) or not value.strip():
        raise ValueError("timestamp는 비어 있지 않은 ISO 8601 문자열이어야 합니다.")
    stamp = dateparse.parse_datetime(value.strip())
    if stamp is None:
        raise ValueError("timestamp는 유효한 ISO 8601 날짜·시간이어야 합니다.")
    if timezone.is_naive(stamp):
        stamp = timezone.make_aware(stamp, timezone.get_current_timezone())
    return stamp.astimezone(timezone.get_current_timezone())


def measurement_key(sensor_id, timestamp):
    return hashlib.sha256(f"{sensor_id}|{timestamp.isoformat()}".encode("utf-8")).hexdigest()


def validate_measurement_values(values, greenhouse, sensor):
    numeric = {}
    for key in ("temperature", "humidity", "x", "y", "z"):
        try:
            number = float(values[key])
        except (KeyError, TypeError, ValueError) as exc:
            raise ValueError(f"{key} 값은 숫자여야 합니다.") from exc
        if not math.isfinite(number):
            raise ValueError(f"{key} 값은 유한한 숫자여야 합니다.")
        numeric[key] = number
    if not -50 <= numeric["temperature"] <= 80:
        raise ValueError("temperature는 -50~80°C 범위여야 합니다.")
    if not 0 <= numeric["humidity"] <= 100:
        raise ValueError("humidity는 0~100% 범위여야 합니다.")
    if not (0 <= numeric["x"] <= float(greenhouse.length_m)):
        raise ValueError("x는 온실 길이 범위를 벗어났습니다.")
    if not (0 <= numeric["y"] <= float(greenhouse.width_m)):
        raise ValueError("y는 온실 폭 범위를 벗어났습니다.")
    if not (0 <= numeric["z"] <= float(greenhouse.height_m)):
        raise ValueError("z는 온실 높이 범위를 벗어났습니다.")
    if sensor.greenhouse_id != greenhouse.pk:
        raise ValueError("sensor_id가 greenhouse_id에 속하지 않습니다.")
    return numeric


def validate_csv_frame(frame, greenhouse):
    frame = frame.copy()
    frame.columns = [CSV_ALIASES.get(str(column).strip().lstrip("\ufeff"), str(column).strip().lstrip("\ufeff")) for column in frame.columns]
    if frame.columns.duplicated().any():
        raise ValueError("같은 의미의 컬럼이 중복되어 있습니다.")
    missing = sorted(CSV_COLUMNS - set(frame.columns))
    if missing:
        raise ValueError(f"필수 컬럼이 없습니다: {', '.join(missing)}")
    if frame.empty:
        raise ValueError("CSV에 측정 행이 없습니다.")
    if len(frame) > 10000:
        raise ValueError("한 번에 업로드할 수 있는 행은 10,000개까지입니다.")
    validated = []
    sensors = {sensor.external_id: sensor for sensor in greenhouse.sensors.all()}
    for row_number, row in enumerate(frame.to_dict(orient="records"), start=2):
        try:
            sensor = sensors.get(str(row["sensor_id"]).strip())
            if not sensor:
                raise ValueError(f"등록되지 않은 센서 ID: {row['sensor_id']}")
            if not is_csv_null(row["greenhouse_id"]):
                try:
                    greenhouse_number = float(row["greenhouse_id"])
                except (ValueError, TypeError) as exc:
                    raise ValueError("온실 ID는 숫자 또는 Null이어야 합니다.") from exc
                if greenhouse_number != greenhouse.pk:
                    raise ValueError("온실 ID가 선택된 온실과 일치하지 않습니다.")
            for coordinate in ("x", "y", "z"):
                if is_csv_null(row[coordinate]):
                    row[coordinate] = getattr(sensor, coordinate)
            numeric = validate_measurement_values(row, greenhouse, sensor)
            validated.append(
                Measurement(
                    timestamp=parse_timestamp(row["timestamp"]),
                    greenhouse=greenhouse,
                    sensor=sensor,
                    source=Measurement.Source.CSV,
                    **numeric,
                )
            )
        except (ValueError, TypeError, KeyError, OverflowError) as exc:
            raise ValueError(f"{row_number}행: {exc}") from exc
    return validated
