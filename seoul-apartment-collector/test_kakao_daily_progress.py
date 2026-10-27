"""Offline regression tests for daily report truthfulness and delivery deduplication."""
import contextlib
import copy
from datetime import datetime, timedelta
import io
import json
import os
import unittest
from unittest.mock import patch

import kakao_daily_progress as daily


NOW = datetime(2026,10,23,9,0,tzinfo=daily.KST)


def entry():
    return {'sha256':'a'*64,'bytes':100,'storage':'r2','checked_at_utc':'2026-10-23T00:00:00+00:00'}


def manifest():
    files = {key:entry() for region in ('seoul','gyeonggi') for kind in ('sale','rent')
             for key in daily.scope_keys(region,kind,'202609','202609')}
    return {'files':files,'updated_at_utc':'2026-10-23T00:00:00+00:00'}


def report(now=NOW):
    return daily.build_report(manifest(),{'as_of_kst':'2026-10-23','last_run_requests':9,'last_run_failures':3},now)


class Missing(Exception):
    response = {'Error':{'Code':'NoSuchKey'}}


class MemoryStorage:
    def __init__(self):self.objects={}
    def get_object(self,Bucket,Key):
        if Key not in self.objects:raise Missing()
        return {'Body':io.BytesIO(self.objects[Key])}
    def put_object(self,Bucket,Key,Body,**kwargs):
        self.objects[Key]=Body


class DailyReportTests(unittest.TestCase):
    def test_targets_match_seoul_periods_and_actual_district_history(self):
        data = report()
        self.assertEqual(11000,data['coverage']['seoul']['total']['target'])
        self.assertEqual(20680,data['coverage']['gyeonggi']['total']['target'])
        self.assertEqual(25,data['coverage']['seoul']['sale']['stored'])
        self.assertEqual(47,data['coverage']['gyeonggi']['rent']['stored'])
        self.assertEqual('202609',data['comparison']['contract_month'])
        self.assertTrue(data['comparison']['ready'])
        self.assertEqual('2026-10-23',data['comparison']['common_observation_day_kst'])
        for kind in ('sale','rent'):
            left=data['coverage']['seoul'][kind];right=data['coverage']['gyeonggi'][kind]
            self.assertEqual(left['first_contract_month'],right['first_contract_month'])
            self.assertEqual(left['last_contract_month'],right['last_contract_month'])
        # Invalid metadata cannot count towards coverage.
        data_manifest=manifest();key=next(iter(data_manifest['files']))
        data_manifest['files'][key]['sha256']='bad'
        invalid=daily.build_report(data_manifest,{},NOW)
        self.assertFalse(invalid['comparison']['ready'])
        self.assertEqual('missing_scopes',invalid['comparison']['reason'])

    def test_same_period_is_not_enough_when_observation_dates_are_missing_or_differ(self):
        for variant,reason in [('missing','observation_date_missing'),('different','observation_days_differ'),
                               ('future','observation_date_missing')]:
            with self.subTest(variant=variant):
                data=manifest();meta=next(iter(data['files'].values()))
                if variant=='missing':meta.pop('checked_at_utc')
                elif variant=='different':meta['checked_at_utc']='2026-10-21T00:00:00Z'
                else:meta['checked_at_utc']='2026-10-24T00:00:00Z'
                check=daily.build_report(data,{},NOW)['comparison']
                self.assertFalse(check['ready']);self.assertEqual(reason,check['reason'])

    def test_text_fits_kakao_and_exposes_errors_with_real_progress_delta(self):
        data=report();data['coverage']['gyeonggi']['sale'].update(stored=11750,percent=100)
        data['coverage']['gyeonggi']['rent'].update(stored=8930,percent=100)
        data['coverage']['gyeonggi']['total'].update(stored=20680,percent=100)
        previous={'report':{'coverage':{'gyeonggi':{'total':{'stored':1,'target':20680}}}}}
        text=daily.render_message(data,previous)
        self.assertLessEqual(len(text),200)
        self.assertIn('+20,679구간',text)
        self.assertIn('오류 3건',text)
        self.assertIn('동일 확인일',text)

    def test_changed_scope_target_is_not_reported_as_new_collection(self):
        data=report()
        previous={'report':{'coverage':{'gyeonggi':{'total':{'stored':19062,'target':19062}}}}}
        self.assertIsNone(daily.comparable_previous_total(data,previous))
        self.assertIn('집계기준 변경',daily.render_message(data,previous))

    def test_once_per_kst_day_and_next_day_delta(self):
        storage=MemoryStorage();sent=[]
        with patch.dict(os.environ,{'R2_BUCKET_NAME':'test'}), \
             patch.object(daily,'access_token',return_value='dummy'), \
             contextlib.redirect_stdout(io.StringIO()):
            self.assertEqual('sent',daily.notify(report(),NOW,storage,lambda token,text:sent.append(text)))
            self.assertEqual('already_sent',daily.notify(report(),NOW+timedelta(hours=2),storage,lambda *args:sent.append('duplicate')))
            tomorrow=NOW+timedelta(days=1);next_report=report(tomorrow)
            self.assertEqual('sent',daily.notify(next_report,tomorrow,storage,lambda token,text:sent.append(text)))
        self.assertEqual(2,len(sent));self.assertIn('전일대비 +0구간',sent[-1])
        receipt=json.loads(storage.objects[daily.ledger_key(NOW.date())])
        self.assertEqual('sent',receipt['status']);self.assertEqual(0,receipt['api_result_code'])

    def test_ambiguous_send_cannot_be_blindly_retried(self):
        storage=MemoryStorage();sent=[]
        def ambiguous(token,text):
            sent.append(text);raise daily.kakao.NotificationError('Service network error')
        with patch.dict(os.environ,{'R2_BUCKET_NAME':'test'}),patch.object(daily,'access_token',return_value='dummy'):
            with self.assertRaises(daily.kakao.NotificationError):daily.notify(report(),NOW,storage,ambiguous)
            with self.assertRaises(daily.kakao.NotificationError):daily.notify(report(),NOW,storage,ambiguous)
        self.assertEqual(1,len(sent))
        self.assertEqual('sending',json.loads(storage.objects[daily.ledger_key(NOW.date())])['status'])

    def test_before_nine_is_preview_and_previous_day_report_is_rejected(self):
        storage=MemoryStorage();before=NOW-timedelta(minutes=1)
        with contextlib.redirect_stdout(io.StringIO()):
            self.assertEqual('not_due',daily.notify(report(before),before,storage))
        self.assertEqual({},storage.objects)
        with self.assertRaises(ValueError):daily.notify(report(),NOW+timedelta(days=1),storage)

    def test_refresh_rotation_reuses_existing_encrypted_token_store(self):
        storage=MemoryStorage()
        with patch.object(daily.kakao,'token_cipher_secret',return_value='cipher'), \
             patch.object(daily.kakao,'get_refresh_token',return_value='old'), \
             patch.object(daily.kakao,'renew_access_token',return_value=('access','rotated')), \
             patch.object(daily.kakao,'save_refresh_token') as save:
            self.assertEqual('access',daily.access_token(storage))
            save.assert_called_once_with(storage,'cipher','rotated')


if __name__=='__main__':unittest.main(verbosity=2)

