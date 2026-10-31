import numpy as np
import pandas as pd
from django.utils import timezone


def dashboard_series():
    times = pd.date_range(end=timezone.now().replace(minute=0, second=0, microsecond=0), periods=24, freq="h")
    hour = np.arange(24)
    temperature = 23.1 + 2.1 * np.sin((hour - 7) * np.pi / 12) + 0.32 * np.sin(hour * 0.8)
    humidity = 66.0 - 7.4 * np.sin((hour - 7) * np.pi / 12) + 1.1 * np.cos(hour * 0.55)
    sensor_values = [
        {"name": "센서 A", "temperature": round(float(temperature[-1] - 0.3), 1), "humidity": round(float(humidity[-1] + 1.6), 1)},
        {"name": "센서 B", "temperature": round(float(temperature[-1] + 0.1), 1), "humidity": round(float(humidity[-1] - 0.5), 1)},
        {"name": "센서 C", "temperature": round(float(temperature[-1] + 0.4), 1), "humidity": round(float(humidity[-1] - 1.2), 1)},
    ]
    return {
        "labels": [stamp.strftime("%H:%M") for stamp in times],
        "timestamps": [stamp.to_pydatetime() for stamp in times],
        "temperature": np.round(temperature, 1).tolist(),
        "humidity": np.round(humidity, 1).tolist(),
        "sensor_values": sensor_values,
    }


def sample_measurement_frame(sensors=None, periods=48):
    rng = np.random.default_rng(24680)
    timestamps = pd.date_range(end=timezone.now().replace(minute=0, second=0, microsecond=0), periods=periods, freq="h")
    sensor_rows = list(sensors or [])
    points = [
        (sensor.external_id, sensor.name, index)
        for index, sensor in enumerate(sensor_rows)
    ] or [(f"DEMO-{letter}", f"센서 {letter}", index) for index, letter in enumerate(("A", "B", "C"))]
    rows = []
    for sensor_id, name, index in points:
        temp_offset = (-0.3, 0.1, 0.4)[index % 3]
        humidity_offset = (1.6, -0.5, -1.2)[index % 3]
        noise_t = rng.normal(0, 0.1, periods)
        noise_h = rng.normal(0, 0.4, periods)
        for hour, timestamp in enumerate(timestamps):
            daily = np.sin((hour - 7) * np.pi / 12)
            rows.append({
                "timestamp": timestamp,
                "sensor__name": name,
                "sensor_id": sensor_id,
                "temperature": 23.2 + 2.0 * daily + temp_offset + noise_t[hour],
                "humidity": 66.0 - 7.0 * daily + humidity_offset + noise_h[hour],
                "source": "demo",
            })
    return pd.DataFrame(rows)


def sample_optimization_frame(seed=7319, periods=96):
    rng = np.random.default_rng(seed)
    timestamps = pd.date_range(end=timezone.now().replace(minute=0, second=0, microsecond=0), periods=periods, freq="h")
    elapsed = np.arange(periods)
    daily = np.sin((elapsed - 7) * np.pi / 12)
    points = [
        ("P1", 0.15, 0.20, 1.5, -0.9, 4.0),
        ("P2", 0.15, 0.80, 1.5, 0.1, -1.5),
        ("P3", 0.38, 0.50, 1.5, -0.2, 0.5),
        ("P4", 0.62, 0.20, 1.5, 0.2, -0.5),
        ("P5", 0.62, 0.80, 1.5, 0.6, -2.0),
        ("P6", 0.85, 0.50, 1.5, 1.0, -3.5),
    ]
    rows = []
    for sensor_id, x_ratio, y_ratio, z, temp_offset, humidity_offset in points:
        noise_t = rng.normal(0, 0.12, periods)
        noise_h = rng.normal(0, 0.45, periods)
        for index, timestamp in enumerate(timestamps):
            rows.append(
                {
                    "timestamp": timestamp,
                    "sensor_id": sensor_id,
                    "x_ratio": x_ratio,
                    "y_ratio": y_ratio,
                    "z": z,
                    "temperature": 23.2 + 2.0 * daily[index] + temp_offset + noise_t[index],
                    "humidity": 66.0 - 7.0 * daily[index] + humidity_offset + noise_h[index],
                }
            )
    return pd.DataFrame(rows)
