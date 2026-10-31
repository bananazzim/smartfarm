from datetime import datetime, timedelta
from unittest.mock import patch
from django.test import TestCase
from django.utils import timezone
from greenhouses.models import Greenhouse
from sensors.models import Sensor
from measurements.models import Measurement
from .fps_data import simulator_payload, compact_records


class FirstPersonDataTests(TestCase):
    def setUp(self):
        self.house=Greenhouse.objects.create(name='고객 온실',length_m=30,width_m=7,height_m=4)
        self.start=timezone.make_aware(datetime(2026,10,31,9))

    def sensor(self,sid,house=None,**kwargs):
        return Sensor.objects.create(greenhouse=house or self.house,external_id=sid,name=sid,status='active',**kwargs)

    def test_dynamic_zero_one_two_three_six_ten_sensors_and_three_dimensions(self):
        for count in (0,1,2,3,6,10):
            Sensor.objects.all().delete()
            for i in range(count):self.sensor(f'S{i}',x=i+1,y=2,z=1.5)
            payload=simulator_payload(self.house)
            self.assertFalse(payload['demo'])
            self.assertEqual(len(payload['sensors']),count)
            self.assertEqual(payload['records'],[])
        for length,width,height in ((30,7,4),(50,9,4.5),(12,6,3.5)):
            self.house.length_m=length;self.house.width_m=width;self.house.height_m=height
            cfg=simulator_payload(self.house)['config']
            self.assertEqual((cfg['length'],cfg['width'],cfg['height']),(length,width,height))

    def test_history_compaction_preserves_position_changes_and_time_offsets(self):
        sensor=self.sensor('S01',x=8,y=2,z=1.5)
        Measurement.objects.bulk_create([Measurement(greenhouse=self.house,sensor=sensor,timestamp=self.start+timedelta(minutes=i),x=1 if i<50 else 8,y=2,z=1.5,temperature=24,humidity=60,source='csv') for i in range(100)])
        payload=simulator_payload(self.house)
        self.assertEqual(len(payload['records']),4)
        self.assertEqual([r['x'] for r in payload['records']],[1,1,8,8])
        self.assertTrue(all(r['timestamp'].endswith('+09:00') for r in payload['records']))
        self.assertEqual(payload['sensors'],[])
        self.assertEqual(Measurement.objects.count(),100)
        self.assertEqual(simulator_payload(self.house,at='2026-10-31T00:00:00Z')['at'],'2026-10-31T09:00:00+09:00')
        bad=simulator_payload(self.house,at='bad')
        self.assertEqual(bad['issues'][0]['code'],'INVALID_TIMESTAMP')

    def test_simultaneous_conflicting_positions_are_not_lost_by_compression(self):
        rows=[dict(sensor_id='S01',timestamp=self.start,x=x,y=2,z=1.5) for x in (1,8)]
        self.assertEqual(compact_records(rows),rows)

    def test_missing_coordinates_are_never_replaced_with_demo_or_zero(self):
        self.sensor('UNSET')
        payload=simulator_payload(self.house,'real')
        self.assertEqual(payload['sensors'][0]['x'],None)
        self.assertEqual(payload['sensors'][0]['y'],None)
        self.assertEqual(payload['sensors'][0]['z'],None)
        self.assertFalse(payload['demo'])

    def test_selected_greenhouse_isolation_and_demo_exclusion(self):
        self.sensor('S01',x=1,y=2,z=1.5)
        other=Greenhouse.objects.create(name='다른 고객',length_m=50,width_m=9,height_m=4.5)
        self.sensor('S02',other,x=1,y=2,z=1.5)
        Sensor.objects.create(greenhouse=self.house,name='DEMO',external_id='DEMO',x=1,y=2,z=1.5)
        for house,sid in ((self.house,'S01'),(other,'S02')):
            response=self.client.get('/simulator/data/',{'greenhouse':house.pk,'mode':'real'})
            self.assertEqual([s['id'] for s in response.json()['sensors']],[sid])
            self.assertEqual(response['Cache-Control'],'no-store')
        self.assertEqual(self.client.get('/simulator/data/',{'greenhouse':999}).status_code,404)

    def test_html_ids_are_json_escaped_and_optimizer_is_not_invoked(self):
        hostile='<img src=x onerror=alert(1)>'
        self.sensor(hostile,x=1,y=2,z=1.5)
        with patch('optimization.engine.evaluate_combinations',side_effect=AssertionError('No optimization in viewer')):
            response=self.client.get('/simulator/',{'greenhouse':self.house.pk,'mode':'real'})
        self.assertEqual(response.status_code,200)
        self.assertNotContains(response,hostile)
        self.assertContains(response,'\\u003Cimg')
        self.assertNotContains(response,'greenhouse-scene.js')
        self.assertNotContains(response,'three.min.js')
        self.assertContains(response,'simulator-fps.css')

    def test_explicit_real_without_greenhouse_has_no_fallback_markers(self):
        Greenhouse.objects.all().delete()
        response=self.client.get('/simulator/',{'mode':'real'})
        self.assertFalse(response.context['is_demo'])
        self.assertNotContains(response,'id="gso-fps"')
        self.assertEqual(response.context['simulator_data']['sensors'],[])

    def test_overview_is_initial_state_with_dynamic_counts_and_shared_preview(self):
        sensor=self.sensor('S01',x=3,y=2,z=1.5)
        Measurement.objects.bulk_create([Measurement(greenhouse=self.house,sensor=sensor,timestamp=self.start+timedelta(minutes=i),x=3,y=2,z=1.5,temperature=24,humidity=60,source='csv') for i in range(3)])
        response=self.client.get('/simulator/',{'greenhouse':self.house.pk,'mode':'real'})
        self.assertContains(response,'data-view="overview"')
        self.assertContains(response,'id="fps-exploring" hidden')
        self.assertContains(response,'greenhouse-isometric-preview.png')
        self.assertContains(response,'id="enter-preview"')
        self.assertContains(response,'id="enter-simulator"')
        self.assertContains(response,'id="back-overview"')
        self.assertEqual(response.context['measured_count'],1)
        self.assertEqual(response.context['recommended_count'],0)

    def test_overview_counts_types_by_id_without_inventing_recommendations(self):
        supplied={'config':{'name':'QA','length':30,'width':7,'height':4},'demo':False,'sensors':[{'id':'SAME','positionType':'measured'},{'id':'SAME','positionType':'recommended'}],'records':[{'sensor_id':'SAME','timestamp':'2026-10-31T00:00:00Z'}],'issues':[],'at':'','state':'real'}
        with patch('visualization.views.simulator_payload',return_value=supplied):
            response=self.client.get('/simulator/',{'greenhouse':self.house.pk})
        self.assertEqual(response.context['measured_count'],1)
        self.assertEqual(response.context['recommended_count'],1)
