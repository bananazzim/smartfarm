from django.shortcuts import render

from greenhouses.models import Greenhouse
from measurements.demo import sample_optimization_frame
from optimization.engine import evaluate_combinations


def installation_guide(request):
    greenhouse = Greenhouse.objects.first()
    evaluation = evaluate_combinations(sample_optimization_frame())
    sensor_points = []
    if greenhouse:
        ratios = {"P1": (0.15, 0.20), "P2": (0.15, 0.80), "P3": (0.38, 0.50), "P4": (0.62, 0.20), "P5": (0.62, 0.80), "P6": (0.85, 0.50)}
        for sensor_id in evaluation["recommended"]["sensors"]:
            x_ratio, y_ratio = ratios[sensor_id]
            sensor_points.append({"name": sensor_id, "x": round(float(greenhouse.length_m) * x_ratio, 2), "y": round(float(greenhouse.width_m) * y_ratio, 2), "z": min(1.5, float(greenhouse.height_m) * 0.75)})
    return render(request, "reports/guide.html", {"greenhouse": greenhouse, "sensor_points": sensor_points, "evaluation": evaluation})
