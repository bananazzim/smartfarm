"""Signed links bind a displayed combination to its current data snapshot."""
import hashlib
import json
from urllib.parse import urlencode
from django.core import signing
from django.core.serializers.json import DjangoJSONEncoder
from django.urls import reverse
from measurements.models import Measurement

SALT = 'gso.optimization.simulator.v1'


def fingerprint(house, mode):
    data = {'house': [house.pk, str(house.length_m), str(house.width_m), str(house.height_m), house.shape], 'mode': mode}
    if mode == 'real':
        data['sensors'] = list(house.sensors.order_by('pk').values('external_id', 'x', 'y', 'z', 'status'))
        data['rows'] = list(Measurement.objects.filter(greenhouse=house).exclude(source='demo').order_by('pk').values('sensor_id', 'timestamp', 'temperature', 'humidity', 'x', 'y', 'z', 'source'))
    return hashlib.sha256(json.dumps(data, cls=DjangoJSONEncoder, sort_keys=True).encode()).hexdigest()


def attach_links(house, evaluation):
    if not house or not evaluation['results']:
        return
    mode = 'demo' if evaluation['is_demo'] else 'real'
    common = {'house': house.pk, 'mode': mode, 'selection': evaluation['selected_sensor_ids'], 'fingerprint': fingerprint(house, mode)}
    for row in evaluation['results']:
        token = signing.dumps({**common, 'rank': row['rank'], 'ids': row['sensors']}, salt=SALT, compress=True)
        row['simulator_url'] = reverse('simulator') + '?' + urlencode({'greenhouse': house.pk, 'mode': mode, 'combination': token})
