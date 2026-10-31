from datetime import datetime, timedelta
from unittest.mock import patch

from django.test import TestCase
from django.utils import timezone

from greenhouses.models import Greenhouse
from measurements.models import Measurement
from sensors.models import Sensor
from .data import evaluation_context


class AnalysisSelectionTests(TestCase):
    def setUp(self):
        self.house = Greenhouse.objects.create(name="혼합 기록 온실", length_m=30, width_m=8, height_m=4)
        self.ids = [f"S{i:02}" for i in range(1,9)]
        stamp = timezone.make_aware(datetime(2026,10,26,9))
        for index, sid in enumerate(self.ids):
            sensor = Sensor.objects.create(greenhouse=self.house, external_id=sid, name=sid, x=index+1, y=2, z=1.5)
            Measurement.objects.bulk_create([Measurement(greenhouse=self.house,sensor=sensor,timestamp=stamp+timedelta(minutes=i),temperature=20+index*.1+i*.01,humidity=60+index*.2,x=index+1,y=2,z=1.5,source="csv") for i in range(8)])
        self.legacy = Sensor.objects.create(greenhouse=self.house, external_id="OLD-API",name="이전 기록",x=1,y=1,z=1)
        Measurement.objects.create(greenhouse=self.house,sensor=self.legacy,timestamp=stamp-timedelta(days=12),temperature=20,humidity=60,x=1,y=1,z=1,source="api")

    def test_latest_cohort_excludes_old_unrelated_api_and_preserves_records(self):
        before=Measurement.objects.count()
        context=evaluation_context(self.house,"real")
        self.assertEqual(context["selected_sensor_ids"],self.ids)
        self.assertEqual(context["common_count"],8)
        self.assertEqual(context["combination_count"],56)
        self.assertEqual(Measurement.objects.count(),before)
        self.assertEqual(len(context["position_sensors"]),8)

    def test_all_sensors_report_exact_common_time_and_can_be_corrected(self):
        context=evaluation_context(self.house,"real",self.ids+["OLD-API"])
        self.assertEqual(context["common_count"],0)
        self.assertIn("선택 센서 9개",context["analysis_error"])
        self.assertIn("공통 시각 0개",context["analysis_error"])
        response=self.client.get('/optimization/',{"greenhouse":self.house.pk,"mode":"real","selection":"1","sensor":self.ids})
        self.assertEqual(response.status_code,200)
        self.assertEqual(response.context["combination_count"],56)
        self.assertContains(response,'name="sensor"')
        again=self.client.get('/optimization/',{"greenhouse":self.house.pk,"mode":"real"})
        self.assertEqual(again.context["selected_sensor_ids"],self.ids)

    def test_empty_selection_is_not_silently_replaced_and_other_house_rejected(self):
        response=self.client.get('/optimization/',{"greenhouse":self.house.pk,"mode":"real","selection":"1"})
        self.assertEqual(response.context["selected_sensor_ids"],[])
        self.assertEqual(response.context["results"],[])
        other=Greenhouse.objects.create(name="다른 온실",length_m=10,width_m=4,height_m=3)
        Sensor.objects.create(greenhouse=other,external_id="OTHER",name="OTHER")
        response=self.client.get('/optimization/',{"greenhouse":self.house.pk,"mode":"real","selection":"1","sensor":"OTHER"})
        self.assertEqual(response.status_code,400)

    def test_selected_sensor_without_measurements_does_not_disappear(self):
        Sensor.objects.create(greenhouse=self.house,external_id="EMPTY",name="EMPTY")
        context=evaluation_context(self.house,"real",self.ids+["EMPTY"])
        self.assertEqual(context["common_count"],0)
        self.assertIn("선택 센서 9개",context["analysis_error"])

    def test_simulator_reuses_same_analysis_selection(self):
        self.house.sensors.filter(external_id__in=self.ids).update(status='active')
        expected=evaluation_context(self.house,'real',self.ids[:3])['recommended']['sensors']
        response=self.client.get('/simulator/',{"greenhouse":self.house.pk,"mode":"real","selection":"1","sensor":self.ids[:3],"highlight":"FAKE"})
        self.assertEqual(response.status_code,200)
        self.assertContains(response,'id="gso-fps"')
        self.assertFalse(response.context['is_demo'])
        payload=response.context['simulator_data']
        self.assertEqual(payload['optimization']['recommendedIds'],expected)
        self.assertEqual({r.get('id',r.get('sensor_id')) for r in payload['sensors']+payload['records'] if r['isRecommended']},set(expected))
        self.assertTrue(all(r['positionType']=='measured' for r in payload['sensors']+payload['records']))
        self.assertEqual(self.client.get(payload['dataUrl']).json()['optimization']['recommendedIds'],expected)
        self.client.get('/optimization/',{'greenhouse':self.house.pk,'mode':'real','selection':'1','sensor':self.ids[:2]})
        empty=self.client.get('/simulator/data/',{'greenhouse':self.house.pk,'mode':'real'}).json()
        self.assertEqual(empty['optimization']['recommendedIds'],[])
        self.assertFalse(any(r['isRecommended'] for r in empty['sensors']+empty['records']))
        # A fresh data range must be evaluated again, rather than retaining IDs
        # from an earlier CSV or another greenhouse.
        Measurement.objects.filter(greenhouse=self.house).delete()
        cleared=self.client.get(payload['dataUrl']).json()
        self.assertEqual(cleared['optimization']['recommendedIds'],[])
        other=Greenhouse.objects.create(name='Separate',length_m=30,width_m=8,height_m=4)
        Sensor.objects.create(greenhouse=other,external_id='S01',name='S01',status='active',x=1,y=2,z=1.5)
        isolated=self.client.get('/simulator/data/',{'greenhouse':other.pk,'mode':'real'}).json()
        self.assertEqual(isolated['optimization']['recommendedIds'],[])
        self.assertFalse(any(r['isRecommended'] for r in isolated['sensors']))

    def test_signed_combination_links_and_data_isolation(self):
        from urllib.parse import urlsplit, parse_qs, urlencode
        self.house.sensors.filter(external_id__in=self.ids).update(status='active')
        page=self.client.get('/optimization/',{'greenhouse':self.house.pk,'mode':'real'})
        for row in page.context['results'][:2]:
            response=self.client.get(row['simulator_url'])
            payload=response.context['simulator_data']
            self.assertTrue(payload['autoEnter'])
            self.assertEqual(payload['optimization']['selectedRank'],row['rank'])
            self.assertEqual(payload['optimization']['recommendedIds'],row['sensors'])
            self.assertEqual({r.get('id',r.get('sensor_id')) for r in payload['records']+payload['sensors'] if r['isRecommended']},set(row['sensors']))
            self.assertEqual(self.client.get(payload['dataUrl']).json()['optimization']['recommendedIds'],row['sensors'])
        second=page.context['results'][1]['simulator_url']
        self.assertIn('1위 추천이 아님',self.client.get(second).context['simulator_data']['optimization']['selectionLabel'])
        query={k:v[0] for k,v in parse_qs(urlsplit(second).query).items()}
        for changed in ({**query,'combination':query['combination']+'bad'}, {**query,'mode':'demo'}):
            bad=self.client.get('/simulator/',changed).context['simulator_data']
            self.assertEqual(bad['optimization']['recommendedIds'],[])
            self.assertTrue(bad['optimization']['error'])
        other=Greenhouse.objects.create(name='Other',length_m=30,width_m=8,height_m=4)
        bad=self.client.get('/simulator/',{**query,'greenhouse':other.pk}).context['simulator_data']
        self.assertEqual(bad['optimization']['recommendedIds'],[])
        self.assertFalse(self.client.get('/simulator/',{'greenhouse':self.house.pk,'mode':'real'}).context['simulator_data']['autoEnter'])
        Measurement.objects.filter(greenhouse=self.house).update(temperature=33)
        stale=self.client.get(second).context['simulator_data']
        self.assertEqual(stale['optimization']['recommendedIds'],[])
        self.assertTrue(stale['optimization']['error'])

    def test_signed_demo_combination_uses_existing_demo_candidates(self):
        page=self.client.get('/optimization/',{'greenhouse':self.house.pk,'mode':'demo'})
        row=page.context['results'][1]
        payload=self.client.get(row['simulator_url']).context['simulator_data']
        self.assertEqual({s['id'] for s in payload['sensors']},{f'P{i}' for i in range(1,7)})
        self.assertEqual(payload['optimization']['recommendedIds'],row['sensors'])
        self.assertTrue(payload['demo'])

    def test_real_and_demo_share_the_demo_scene_layout(self):
        for mode, count in (('real',56),('demo',20)):
            response=self.client.get('/optimization/',{'greenhouse':self.house.pk,'mode':mode})
            self.assertEqual(response.status_code,200)
            self.assertContains(response,'simulator-layout optimization-scene')
            self.assertContains(response,'id="location-scenario"')
            self.assertContains(response,'id="location-detail"')
            self.assertContains(response,'class="card placement-card"')
            self.assertEqual(response.context['combination_count'],count)
            self.assertEqual(len(response.context['scene_data']['recommended']),3)
