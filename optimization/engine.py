from itertools import combinations

import numpy as np
import pandas as pd

from measurements.demo import sample_optimization_frame


def _metrics(predicted, reference):
    residual = np.asarray(predicted, dtype=float) - np.asarray(reference, dtype=float)
    return {
        "mae": float(np.mean(np.abs(residual))),
        "rmse": float(np.sqrt(np.mean(np.square(residual)))),
    }


def evaluate_combinations(frame=None, sensor_count=3, train_fraction=0.75):
    """Rank sample point combinations on a chronological train split; report holdout errors separately."""
    frame = sample_optimization_frame() if frame is None else frame.copy()
    if not 0 < train_fraction < 1:
        raise ValueError("train_fraction은 0과 1 사이여야 합니다.")
    sensors = sorted(frame["sensor_id"].unique())
    if sensor_count < 1 or sensor_count > len(sensors):
        raise ValueError("조합 크기는 측정 지점 수 이하여야 합니다.")
    timestamps = sorted(frame["timestamp"].unique())
    split_at = max(1, min(len(timestamps) - 1, int(len(timestamps) * train_fraction)))
    train_times, test_times = set(timestamps[:split_at]), set(timestamps[split_at:])
    # These subsets and reference means are identical for every combination.
    subsets = []
    for subset_name, times in (("train", train_times), ("test", test_times)):
        subset = frame[frame["timestamp"].isin(times)]
        reference = subset.groupby("timestamp")[["temperature", "humidity"]].mean()
        subsets.append((subset_name, subset, reference))
    results = []
    for combo in combinations(sensors, sensor_count):
        score = {}
        for subset_name, subset, reference in subsets:
            selected = subset[subset["sensor_id"].isin(combo)].groupby("timestamp")[["temperature", "humidity"]].mean()
            aligned = reference.join(selected, lsuffix="_ref", rsuffix="_pred", how="inner")
            score[subset_name] = {
                "temperature": _metrics(aligned["temperature_pred"], aligned["temperature_ref"]),
                "humidity": _metrics(aligned["humidity_pred"], aligned["humidity_ref"]),
            }
        results.append({"sensors": list(combo), **score})
    results.sort(key=lambda result: (result["train"]["temperature"]["mae"] + result["train"]["humidity"]["mae"], result["sensors"]))
    for rank, result in enumerate(results, start=1):
        result["rank"] = rank
    return {
        "results": results,
        "recommended": results[0],
        "train_start": pd.Timestamp(min(train_times)).isoformat(),
        "train_end": pd.Timestamp(max(train_times)).isoformat(),
        "validation_start": pd.Timestamp(min(test_times)).isoformat(),
        "validation_end": pd.Timestamp(max(test_times)).isoformat(),
        "candidate_count": len(sensors),
        "combination_count": len(results),
    }
