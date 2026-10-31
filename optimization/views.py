from django.shortcuts import render, get_object_or_404

from greenhouses.models import Greenhouse
from .data import evaluation_context, request_sensor_ids
from .simulator_links import attach_links


def optimization_results(request):
    greenhouses = Greenhouse.objects.all()
    selected_id = request.GET.get("greenhouse")
    greenhouse = get_object_or_404(greenhouses, pk=selected_id) if selected_id and selected_id.isdigit() else greenhouses.first()
    if selected_id and not selected_id.isdigit():
        from django.http import Http404
        raise Http404("온실을 찾을 수 없습니다.")
    evaluation = evaluation_context(greenhouse, request.GET.get("mode"), request_sensor_ids(request, greenhouse))
    attach_links(greenhouse, evaluation)
    evaluation["scene_data"]["recommended"] = evaluation.get("recommended", {}).get("sensors", [])
    basic_placements = []
    if greenhouse:
        for name, ratio in (("A", 0.2), ("B", 0.5), ("C", 0.8)):
            basic_placements.append({
                "name": name,
                "ratio": int(ratio * 100),
                "x": round(float(greenhouse.length_m) * ratio, 2),
            })
    return render(request, "optimization/results.html", {"greenhouse": greenhouse, "greenhouses": greenhouses, "basic_placements": basic_placements, **evaluation})
