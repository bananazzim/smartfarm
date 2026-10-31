import plotly.graph_objects as go
from django.contrib import messages
from django.shortcuts import get_object_or_404, redirect, render

from measurements.demo import dashboard_series
from measurements.models import Measurement
from notifications.models import AlertEvent

from .forms import GreenhouseForm
from .models import Greenhouse


def _selected_greenhouse(request):
    greenhouses = Greenhouse.objects.all()
    selected_id = request.GET.get("greenhouse")
    if selected_id and selected_id.isdigit():
        greenhouse = greenhouses.filter(pk=selected_id).first()
        if greenhouse:
            return greenhouse, greenhouses
    return greenhouses.first(), greenhouses


def dashboard(request):
    greenhouse, greenhouses = _selected_greenhouse(request)
    series = dashboard_series()
    chart = go.Figure()
    for label, values, color in [
        ("온도", series["temperature"], "#c83e59"),
        ("상대습도", series["humidity"], "#f26b75"),
    ]:
        chart.add_trace(go.Scatter(x=series["labels"], y=values, name=label, mode="lines", line={"color": color, "width": 2.5}))
    chart.update_layout(
        margin={"l": 8, "r": 12, "t": 12, "b": 8},
        paper_bgcolor="rgba(0,0,0,0)",
        plot_bgcolor="rgba(0,0,0,0)",
        font={"family": "Pretendard, sans-serif", "color": "#666474", "size": 12},
        legend={"orientation": "h", "y": 1.16, "x": 0},
        xaxis={"showgrid": False, "tickfont": {"size": 11}},
        yaxis={"gridcolor": "#eeeaf0", "zeroline": False, "title": "온도 (°C)"},
        yaxis2={"overlaying": "y", "side": "right", "showgrid": False, "title": "습도 (%)", "range": [35, 85]},
        height=330,
    )
    chart.data[1].update(yaxis="y2")
    chart_html = chart.to_html(full_html=False, include_plotlyjs="cdn", config={"displayModeBar": False, "responsive": True})
    rows = []
    if greenhouse:
        rows = Measurement.objects.filter(greenhouse=greenhouse).select_related("sensor").order_by("-timestamp")[:5]
    context = {
        "greenhouse": greenhouse,
        "greenhouses": greenhouses,
        "chart_html": chart_html,
        "sample_temp": round(sum(series["temperature"]) / len(series["temperature"]), 1),
        "sample_humidity": round(sum(series["humidity"]) / len(series["humidity"]), 1),
        "snapshot_temperature_series": series["temperature"],
        "snapshot_humidity_series": series["humidity"],
        "connected_sensors": greenhouse.sensor_count if greenhouse else 0,
        "measurements": rows,
        "alerts": AlertEvent.objects.select_related("greenhouse").order_by("-created_at")[:3],
        "demo_sensor_values": series["sensor_values"],
    }
    return render(request, "greenhouses/dashboard.html", context)


def greenhouse_list(request):
    return render(request, "greenhouses/list.html", {"greenhouses": Greenhouse.objects.all()})


def greenhouse_create(request):
    form = GreenhouseForm(request.POST or None)
    if request.method == "POST" and form.is_valid():
        greenhouse = form.save()
        messages.success(request, f"{greenhouse.name} 온실을 등록했습니다.")
        return redirect("greenhouse-detail", pk=greenhouse.pk)
    return render(request, "greenhouses/form.html", {"form": form, "title": "온실 등록"})


def greenhouse_update(request, pk):
    greenhouse = get_object_or_404(Greenhouse, pk=pk)
    form = GreenhouseForm(request.POST or None, instance=greenhouse)
    if request.method == "POST" and form.is_valid():
        form.save()
        messages.success(request, "온실 정보를 저장했습니다.")
        return redirect("greenhouse-detail", pk=greenhouse.pk)
    return render(request, "greenhouses/form.html", {"form": form, "title": "온실 정보 수정", "greenhouse": greenhouse})


def greenhouse_detail(request, pk):
    greenhouse = get_object_or_404(Greenhouse, pk=pk)
    return render(request, "greenhouses/detail.html", {"greenhouse": greenhouse, "measurements": greenhouse.measurements.select_related("sensor").order_by("-timestamp")[:8]})
