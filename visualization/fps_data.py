"""Position snapshots for the walk-through page; no optimization/model changes."""
from collections import defaultdict
from django.utils import timezone
from measurements.models import Measurement
from sensors.models import Sensor
from measurements.services import parse_timestamp


def compact_records(records):
    """Keep position run boundaries and simultaneous conflicts, never averages."""
    groups = defaultdict(list)
    for record in records:
        groups[record['sensor_id']].append(record)
    result = []
    for group in groups.values():
        first = previous = None
        for record in group:
            position = tuple(record[a] for a in 'xyz')
            if previous is None or position != tuple(previous[a] for a in 'xyz'):
                if previous is not None and previous is not first:
                    result.append(previous)
                result.append(record)
                first = record
            previous = record
        if previous is not None and previous is not first:
            result.append(previous)
    return result


def simulator_payload(greenhouse, mode=None, at=None):
    demo = mode == 'demo' or greenhouse is None and mode != 'real'
    config = {'name': greenhouse.name if greenhouse else 'DEMO · 예시 온실',
              'length': float(greenhouse.length_m) if greenhouse else 30,
              'width': float(greenhouse.width_m) if greenhouse else 7,
              'height': float(greenhouse.height_m) if greenhouse else 4}
    payload = {'config': config, 'demo': demo, 'sensors': [], 'records': [], 'at': '', 'issues': [], 'state': 'demo' if demo else 'empty'}
    if demo:
        payload['sensors'] = [
            {'id': 'DEMO-A', 'x': config['length']*.2, 'y': config['width']*.3, 'z': min(1.5,config['height']*.4), 'positionType': 'measured'},
            {'id': 'DEMO-B', 'x': config['length']*.5, 'y': config['width']*.5, 'z': min(1.5,config['height']*.4), 'positionType': 'measured'},
            {'id': 'DEMO-C', 'x': config['length']*.8, 'y': config['width']*.7, 'z': min(1.8,config['height']*.45), 'positionType': 'measured'},
        ]
        return payload
    if greenhouse is None:
        payload['state'] = 'no_greenhouse'
        return payload
    # Seed/demo sensors are never substituted for customer installation data.
    sensors = list(greenhouse.sensors.exclude(status=Sensor.Status.DEMO))
    qs = Measurement.objects.filter(greenhouse=greenhouse, sensor__in=sensors).exclude(source=Measurement.Source.DEMO).order_by('sensor_id', 'timestamp', 'pk')
    history, recorded = [], set()
    latest = None
    for record in qs.values('sensor__external_id', 'timestamp', 'x', 'y', 'z'):
        sid = record.pop('sensor__external_id')
        stamp = record['timestamp']
        latest = stamp if latest is None or stamp > latest else latest
        history.append({'sensor_id': sid, 'positionType': 'measured', **record, 'timestamp': timezone.localtime(stamp).isoformat()})
        recorded.add(sid)
    payload['records'] = compact_records(history)
    payload['sensors'] = [{'id': s.external_id, **{a: float(getattr(s,a)) if getattr(s,a) is not None else None for a in 'xyz'}, 'positionType': 'measured'} for s in sensors if s.external_id not in recorded]
    payload['state'] = 'real' if sensors else 'empty'
    if at:
        try:
            payload['at'] = parse_timestamp(at).isoformat()
        except (ValueError, TypeError, OverflowError):
            payload['at'] = str(at)
            payload['issues'].append({'code': 'INVALID_TIMESTAMP', 'message': '선택 시각을 해석할 수 없습니다.'})
    elif latest is not None:
        payload['at'] = timezone.localtime(latest).isoformat()
    return payload
