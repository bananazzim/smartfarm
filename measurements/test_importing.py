import math
import os
from datetime import datetime
from pathlib import Path
from unittest import skipUnless

import pandas as pd
from django.core.files.uploadedfile import SimpleUploadedFile
from django.test import TestCase
from django.utils import timezone

from greenhouses.models import Greenhouse
from sensors.models import Sensor
from optimization.data import evaluation_context
from optimization.engine import evaluate_combinations
from measurements.importing import read_upload, inspect_rows, ImportConfirmationForm, commit_import
from measurements.models import Measurement


HEADER = "측정일시,온실ID,센서ID,온도(°C),습도(%),X좌표(m),Y좌표(m),Z좌표(m)\n"


class CustomerImportTests(TestCase):
    def setUp(self):
        self.house = Greenhouse.objects.create(name="고객 A", length_m=20, width_m=10, height_m=4)

    def rows(self, count=8, periods=8):
        return [dict(timestamp=f"2026-10-26 {9+i//60:02}:{i%60:02}:00", greenhouse_id=None, sensor_id=f"S{sid:02}", temperature=str(20+sid/10+i/100), humidity=str(60+sid/5), x=None, y=None, z=None) for i in range(periods) for sid in range(1,count+1)]

    def confirm(self, rows, house=None, coordinates=None):
        house = house or self.house
        plans, _ = inspect_rows(rows, house)
        data = {"confirm": "on"}
        for index, plan in enumerate(plans):
            for axis, value in zip("xyz", coordinates or [None]*3):
                existing = plan["coordinates"]["xyz".index(axis)]
                data[f"sensor_{index}_{axis}"] = value if value is not None else (existing if existing is not None else {"x": index+1,"y": 3,"z": 1.5}[axis])
        form = ImportConfirmationForm(plans, house, data)
        self.assertTrue(form.is_valid(), form.errors)
        return commit_import(rows, house, form)

    def test_missing_coordinates_stage_then_save_and_reupload(self):
        rows = self.rows()
        plans, normalized = inspect_rows(rows, self.house)
        self.assertEqual(len(plans),8)
        self.assertTrue(all(p["coordinates"] == [None]*3 for p in plans))
        self.assertFalse(Sensor.objects.exists())
        self.assertFalse(Measurement.objects.exists())
        self.assertEqual(self.confirm(rows),(64,0))
        self.assertEqual(self.confirm(rows),(0,64))
        self.assertEqual(Sensor.objects.count(),8)
        self.assertEqual(Measurement.objects.count(),64)
        self.assertEqual(evaluation_context(self.house,"real")["combination_count"],56)

    def test_customer_sensor_ids_are_scoped_and_measurements_do_not_mix(self):
        other=Greenhouse.objects.create(name="고객 B",length_m=30,width_m=8,height_m=5)
        self.confirm(self.rows(3), self.house)
        self.confirm(self.rows(3), other)
        self.assertEqual(Sensor.objects.filter(external_id="S01").count(),2)
        a=evaluation_context(self.house,"real")
        b=evaluation_context(other,"real")
        self.assertEqual(a["combination_count"],1)
        self.assertEqual(b["combination_count"],1)
        self.assertEqual(a["scene_data"]["length"],20)
        self.assertEqual(b["scene_data"]["length"],30)
        self.assertIn("1개",a["analysis_warning"])

    def test_conflicts_rollback_sensor_and_all_measurements(self):
        rows=self.rows(3)
        self.confirm(rows)
        changed=[dict(r) for r in rows]
        changed[0]["temperature"]="30"
        with self.assertRaisesMessage(ValueError,"충돌"):
            self.confirm(changed,coordinates=[2,3,1.5])
        self.assertEqual(Measurement.objects.count(),24)
        self.assertEqual(float(Sensor.objects.get(external_id="S01").x),1)

    def test_duplicate_rows_safe_but_conflicting_duplicate_rejected(self):
        rows=self.rows(3)
        self.assertEqual(self.confirm(rows+[rows[0]]),(24,1))
        with self.assertRaisesMessage(ValueError,"중복 데이터"):
            inspect_rows(rows+[{**rows[0],"humidity":"70"}],self.house)

    def test_invalid_fields_have_row_numbers_and_do_not_save(self):
        for patch in ({"humidity":None},{"temperature":"NaN"},{"timestamp":"2026-99-99"},{"x":"25"},{"greenhouse_id":"999"},{"sensor_id":"Null"}):
            with self.subTest(patch=patch), self.assertRaisesRegex(ValueError,"2행"):
                inspect_rows([{**self.rows(3)[0],**patch}],self.house)
        self.assertEqual(Measurement.objects.count(),0)

    def test_roof_and_missing_coordinates_and_zero(self):
        with self.assertRaisesMessage(ValueError,"아치형"):
            self.confirm(self.rows(3),coordinates=[1,0,4])
        self.assertEqual(self.confirm(self.rows(3),coordinates=[0,0,0]),(24,0))
        sensor=Sensor.objects.get(external_id="S01")
        self.assertEqual(sensor.x,0)
        unset=Sensor.objects.create(greenhouse=self.house,external_id="UNSET",name="미설정")
        self.assertIsNone(unset.x)
        context=evaluation_context(self.house,"real",["S01","S02","S03","UNSET"])
        self.assertFalse(next(s for s in context["position_sensors"] if s["name"]=="UNSET")["position_valid"])

    def test_dimension_change_warns_without_fabricating_positions(self):
        self.confirm(self.rows(3))
        self.assertEqual(evaluation_context(self.house,"real")["position_sensors"][0]["relative"],[5.0,30.0,37.5])
        self.house.length_m=1
        self.house.save()
        context=evaluation_context(self.house,"real")
        self.assertEqual(sum(s["position_valid"] for s in context["position_sensors"]),1)
        self.assertEqual(context["scene_data"]["length"],1)
        plans,_ = inspect_rows(self.rows(3),self.house)
        self.assertTrue(plans[1]["position_error"])

    def test_moving_sensor_preserves_historical_measurement_coordinates(self):
        self.confirm(self.rows(3))
        old=Measurement.objects.get(sensor__external_id="S01",timestamp=timezone.make_aware(datetime(2026,10,26,9)))
        later=[{**row,"timestamp":row["timestamp"].replace('2026-10-26','2026-10-27')} for row in self.rows(3)]
        self.confirm(later,coordinates=[2,3,1.5])
        old.refresh_from_db()
        self.assertEqual(old.x,1)
        self.assertEqual(float(Sensor.objects.get(external_id='S01').x),2)
        self.assertIn('설치 위치 변경 이력',evaluation_context(self.house,'real')['analysis_warning'])

    def test_dynamic_counts_common_times_and_exact_original_metrics(self):
        for count in (3,6,8,12):
            with self.subTest(count=count):
                Measurement.objects.all().delete(); Sensor.objects.all().delete()
                rows=self.rows(count)
                self.confirm(rows)
                context=evaluation_context(self.house,"real")
                self.assertEqual(context["combination_count"],math.comb(count,3))
                frame=pd.DataFrame([{**r,"timestamp":pd.Timestamp(r["timestamp"],tz="Asia/Seoul"),"temperature":float(r["temperature"]),"humidity":float(r["humidity"])} for r in rows])
                expected=evaluate_combinations(frame)
                self.assertEqual(context["results"],expected["results"])
                self.assertLess(context["train_end"],context["validation_start"])
                Measurement.objects.filter(sensor__external_id="S01").earliest("timestamp").delete()
                filtered=evaluation_context(self.house,"real")
                self.assertEqual(filtered["common_count"],7)

    def test_insufficient_data_and_explicit_demo(self):
        context=evaluation_context(self.house,"real")
        self.assertFalse(context["is_demo"])
        self.assertTrue(context["analysis_error"])
        self.confirm(self.rows(2))
        self.assertIn("3개 미만",evaluation_context(self.house,"real")["analysis_error"])
        demo=evaluation_context(self.house,"demo")
        self.assertEqual(demo["combination_count"],20)
        self.assertEqual(demo["results"],evaluate_combinations()["results"])
        self.assertEqual({s["name"] for s in demo["position_sensors"]},{f"P{i}" for i in range(1,7)})
        Measurement.objects.all().delete()
        self.confirm(self.rows(3,3))
        self.assertIn("4개 이상",evaluation_context(self.house,"real")["analysis_error"])

    def test_http_confirmation_and_tampering_and_real_templates(self):
        content=HEADER+"2026-10-26 09:00:39,Null,S01,22.70,77.53,Null,Null,Null"
        response=self.client.post('/analysis/upload/',{"greenhouse_id":self.house.pk,"file":SimpleUploadedFile('sample.csv',content.encode('utf-8-sig'))})
        self.assertEqual(response.status_code,200)
        self.assertEqual(response.context['sensor_count'],1)
        self.assertEqual(Measurement.objects.count(),0)
        self.assertIsNone(response.context['form'].fields['sensor_0_x'].initial)
        data={"greenhouse_id":self.house.pk,"stage":"confirm","token":response.context['token'],"sensor_0_x":2,"sensor_0_y":3,"sensor_0_z":1.5,"confirm":"on"}
        bad=self.client.post('/analysis/upload/',{**data,"sensor_0_x":25})
        self.assertEqual(bad.status_code,200)
        self.assertEqual(Measurement.objects.count(),0)
        response=self.client.post('/analysis/upload/',data,follow=True)
        self.assertEqual(response.status_code,200)
        self.assertEqual(Measurement.objects.count(),1)
        self.assertFalse(response.context['is_demo'])
        self.assertContains(response,'실제 측정 데이터 분석')
        self.assertNotContains(response,'??')
        self.assertNotContains(response,'<span class="soft-tag">DEMO</span>',html=False)
        self.assertEqual(self.client.get(f'/simulator/?greenhouse={self.house.pk}&mode=real').status_code,200)
        replay=self.client.post('/analysis/upload/',data)
        self.assertEqual(replay.status_code,302)
        self.assertEqual(Measurement.objects.count(),1)

    def test_encodings_english_columns_and_limits(self):
        content=HEADER+"2026-10-26 09:00:39,Null,S01,22.70,77.53,Null,Null,Null"
        for encoding in ('utf-8','utf-8-sig','cp949'):
            rows=read_upload(SimpleUploadedFile('sample.csv',content.encode(encoding)))
            self.assertEqual(len(inspect_rows(rows,self.house)[0]),1)
        english='timestamp,greenhouse_id,sensor_id,temperature,humidity,x,y,z\n2026-10-26 09:00:39,,S01,22.7,77.53,,,'
        self.assertEqual(len(read_upload(SimpleUploadedFile('en.csv',english.encode()))),1)
        with self.assertRaisesMessage(ValueError,'5MB'):
            read_upload(SimpleUploadedFile('large.csv',b'x'*(5*1024*1024+1)))
        with self.assertRaisesMessage(ValueError,'10,000'):
            header, row = english.split('\n')
            read_upload(SimpleUploadedFile('rows.csv',(header+'\n'+'\n'.join([row]*10001)).encode()))

    @skipUnless(os.environ.get('GSO_SAMPLE_CSV'), 'Set GSO_SAMPLE_CSV to run the supplied customer CSV integration test')
    def test_supplied_customer_csv_4680_records_8_sensors_56_combinations(self):
        content=Path(os.environ['GSO_SAMPLE_CSV']).read_bytes()
        rows=read_upload(SimpleUploadedFile('customer.csv',content))
        self.assertEqual(len(rows),4680)
        plans,_=inspect_rows(rows,self.house)
        self.assertEqual([p['sid'] for p in plans],[f'S{i:02}' for i in range(1,9)])
        self.assertTrue(all(p['coordinates']==[None,None,None] for p in plans))
        staged=self.client.post('/analysis/upload/',{"greenhouse_id":self.house.pk,"file":SimpleUploadedFile('customer.csv',content)})
        self.assertEqual(staged.status_code,200)
        self.assertEqual(staged.context['row_count'],4680)
        self.assertEqual(staged.context['sensor_count'],8)
        self.assertFalse(Measurement.objects.exists())
        fields={"greenhouse_id":self.house.pk,"stage":"confirm","token":staged.context['token'],"confirm":"on"}
        for index in range(8):
            fields.update({f'sensor_{index}_x':index+1,f'sensor_{index}_y':3,f'sensor_{index}_z':1.5})
        saved=self.client.post('/analysis/upload/',fields,follow=True)
        self.assertEqual(saved.status_code,200)
        self.assertContains(saved,'CSV 4680건을 저장했습니다')
        self.assertEqual(self.confirm(rows),(0,4680))
        self.assertEqual(Measurement.objects.values('timestamp').distinct().count(),585)
        for sensor in self.house.sensors.all(): self.assertEqual(sensor.measurements.count(),585)
        for row in rows:
            record=Measurement.objects.get(sensor__external_id=row['sensor_id'],timestamp=timezone.make_aware(datetime.fromisoformat(row['timestamp'])))
            self.assertEqual(record.temperature,float(row['temperature']))
            self.assertEqual(record.humidity,float(row['humidity']))
        context=evaluation_context(self.house,'real')
        self.assertEqual(context['combination_count'],56)
        self.assertEqual(context['common_count'],585)
        response=self.client.get(f'/optimization/?greenhouse={self.house.pk}&mode=real')
        self.assertEqual(response.status_code,200)
        self.assertEqual(response.content.decode().count('data-combination='),56)
        self.assertEqual(len(response.context['scene_data']['sensors']),8)
        self.assertContains(response,'S08')
        self.assertNotContains(response,'??')
