import math


def validate_position(greenhouse, coordinates):
    """Data axes: X inward from entrance, Y rightward, Z upward.

    Single-span rendering uses straight walls to 68% height and an elliptical roof.
    """
    bounds = (float(greenhouse.length_m), float(greenhouse.width_m), float(greenhouse.height_m))
    values = []
    for axis, value, bound in zip("xyz", coordinates, bounds):
        if value is None:
            raise ValueError(f"{axis}: 설치 위치 미등록")
        value = float(value)
        if not math.isfinite(value) or not 0 <= value <= bound:
            raise ValueError(f"{axis}: 온실 크기 범위를 벗어났습니다 (0~{bound:g}m).")
        values.append(value)
    if greenhouse.shape == "single":
        cross = (values[1] - bounds[1] / 2) / (bounds[1] / 2)
        roof = bounds[2] * (.68 + .32 * math.sqrt(max(0, 1 - cross * cross)))
        if values[2] > roof + 1e-6:
            raise ValueError("z: 아치형 지붕 외부의 좌표입니다.")
    return values
