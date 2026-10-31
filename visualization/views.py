from django.http import Http404, JsonResponse
from django.shortcuts import get_object_or_404, render
from django.urls import reverse
from urllib.parse import urlencode

from greenhouses.models import Greenhouse
from .fps_data import simulator_payload
from optimization.data import evaluation_context, request_sensor_ids
from django.core import signing
from optimization.simulator_links import SALT, fingerprint


def selected_greenhouse(request):
    greenhouses = Greenhouse.objects.all()
    selected = request.GET.get("greenhouse")
    if selected:
        if not selected.isdigit():
            raise Http404("온실을 찾을 수 없습니다.")
        return get_object_or_404(greenhouses, pk=selected), greenhouses
    return greenhouses.first(), greenhouses


def build_payload(request, greenhouse):
    payload = simulator_payload(greenhouse, request.GET.get("mode"), request.GET.get("at"))
    # Reuse the optimizer's data selection and calculations, never infer a subset
    # from installation type or trust client-provided highlight IDs.
    token = request.GET.get('combination')
    linked = 'combination' in request.GET
    chosen = None
    invalid = False
    if linked:
        try:
            chosen = signing.loads(token, salt=SALT, max_age=86400)
            if not greenhouse or chosen['house'] != greenhouse.pk or chosen['mode'] != ('demo' if payload['demo'] else 'real') or chosen['fingerprint'] != fingerprint(greenhouse, chosen['mode']):
                raise ValueError('Stale or mismatched combination')
        except (signing.BadSignature, ValueError, KeyError, TypeError):
            chosen = None
            invalid = True
    selection = chosen['selection'] if chosen else (None if linked else request_sensor_ids(request, greenhouse))
    evaluation = evaluation_context(greenhouse, "demo" if payload["demo"] else "real", selection)
    selected_row = None
    if chosen:
        selected_row = next((r for r in evaluation['results'] if r['rank'] == chosen['rank'] and r['sensors'] == chosen['ids']), None)
        invalid = selected_row is None
    # DEMO candidates are the optimizer's existing P1~P6, never customer data.
    if selected_row and payload['demo']:
        payload['sensors'] = [{'id': s['name'], **{a: s[a] for a in 'xyz'}, 'positionType': 'measured'} for s in evaluation['position_sensors']]
    installed = {str(s.get('id', s.get('sensor_id'))) for s in payload['sensors'] + payload['records']}
    result_ids = selected_row['sensors'] if selected_row else evaluation.get('recommended', {}).get('sensors', [])
    if selected_row and not set(result_ids).issubset(installed):
        invalid = True
    recommended = [] if invalid else [str(sid) for sid in result_ids if str(sid) in installed]
    payload['autoEnter'] = linked
    payload['optimization'] = {
        'sensorIds': evaluation.get('selected_sensor_ids', []),
        'recommendedIds': recommended,
        'commonCount': evaluation.get('common_count', 0),
        'error': evaluation.get('analysis_error', ''),
        'validationStart': evaluation.get('validation_start'),
        'validationEnd': evaluation.get('validation_end'),
        'selectedRank': selected_row['rank'] if selected_row and not invalid else None,
        'selectionLabel': ('1위 추천 조합' if selected_row['rank'] == 1 else f"{selected_row['rank']}위 비교 조합 · 1위 추천이 아님") if selected_row and not invalid else '',
    }
    if invalid:
        payload['optimization']['error'] = '조합 링크가 만료되었거나 온실·데이터가 변경되었습니다. 최적 배치 페이지에서 다시 선택해 주세요.'
    for sensor in payload['sensors'] + payload['records']:
        sensor['isRecommended'] = str(sensor.get('id', sensor.get('sensor_id'))) in recommended
    query = {"mode": "demo" if payload["demo"] else "real"}
    if greenhouse:
        query["greenhouse"] = greenhouse.pk
    if request.GET.get("at"):
        query["at"] = request.GET["at"]
    pairs = list(query.items())
    if selection is not None and not payload['demo']:
        pairs += [('selection', '1')] + [('sensor', sid) for sid in selection]
    if linked:
        pairs += [('combination', token)]
    payload["dataUrl"] = reverse("simulator-data") + "?" + urlencode(pairs)
    return payload


def simulator(request):
    greenhouse, greenhouses = selected_greenhouse(request)
    payload = build_payload(request, greenhouse)
    sensor_types = {('recommended' if item.get('positionType', item.get('position_type')) == 'recommended' else 'measured', str(item.get('id', item.get('sensor_id')))) for item in payload['sensors'] + payload['records']}
    return render(request, "visualization/simulator.html", {
        "greenhouse": greenhouse, "greenhouses": greenhouses,
        "simulator_data": payload, "is_demo": payload["demo"],
        "measured_count": sum(kind == 'measured' for kind, _ in sensor_types),
        "recommended_count": sum(kind == 'recommended' for kind, _ in sensor_types),
    })


def simulator_data(request):
    greenhouse, _ = selected_greenhouse(request)
    response = JsonResponse(build_payload(request, greenhouse))
    response["Cache-Control"] = "no-store"
    return response
