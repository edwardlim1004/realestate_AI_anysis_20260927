"""Offline tests for account scope, concurrent reservations and honest reports."""
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime
import hashlib
import io
import json
import os
import sys
import threading
from types import SimpleNamespace
import unittest
from unittest.mock import patch

import storage_usage as usage
from storage_budget import StorageBudget,StorageBudgetExceeded,KEY,CONTROL_RESERVE
import kakao_daily_progress as daily
from test_kakao_daily_progress import report,NOW


class Missing(Exception):
    def __init__(self,code='NoSuchKey'):self.response={'Error':{'Code':code}}


class S3:
    def __init__(self):
        self.sizes={('main','apartments'):200,('other','gsadf'):300}
        self.blobs={};self.etags={};self.lock=threading.RLock();self.forbid_list=False
        self.ambiguous=False;self.writes=0
    def list_buckets(self):
        if self.forbid_list:raise Missing('AccessDenied')
        return {'Buckets':[{'Name':name} for name in ('main','other')]}
    def get_paginator(self,operation):
        assert operation=='list_objects_v2'
        outer=self
        class Pages:
            def paginate(self,Bucket):
                for (bucket,key),size in list(outer.sizes.items()):
                    if bucket==Bucket:yield {'Contents':[{'Key':key,'Size':size}]}
        return Pages()
    def head_object(self,Bucket,Key):
        with self.lock:
            if (Bucket,Key) not in self.sizes:raise Missing()
            return {'ContentLength':self.sizes[Bucket,Key]}
    def get_object(self,Bucket,Key):
        with self.lock:
            if (Bucket,Key) not in self.blobs:raise Missing()
            return {'Body':io.BytesIO(self.blobs[Bucket,Key]),'ETag':self.etags[Bucket,Key]}
    def put_object(self,Bucket,Key,Body,IfNoneMatch=None,IfMatch=None,**kwargs):
        with self.lock:
            key=(Bucket,Key)
            if IfNoneMatch=='*' and key in self.blobs:raise Missing('PreconditionFailed')
            if IfMatch and self.etags.get(key)!=IfMatch:raise Missing('PreconditionFailed')
            self.blobs[key]=Body;self.sizes[key]=len(Body)
            self.etags[key]=hashlib.sha256(Body).hexdigest();self.writes+=1
            if self.ambiguous:
                self.ambiguous=False;raise Missing('InternalError')


class StorageTests(unittest.TestCase):
    def test_optional_usage_key_is_read_only_and_keeps_write_key_intact(self):
        reader=object();calls=[]
        def client(*args,**kwargs):calls.append(kwargs);return reader
        with patch.dict(os.environ,{'R2_ACCOUNT_ID':'dummy','R2_SECRET_ACCESS_KEY':'original-write-key',
                'R2_USAGE_ACCESS_KEY_ID':'reader-id','R2_USAGE_SECRET_ACCESS_KEY':'reader-secret'}), \
             patch.dict(sys.modules,{'boto3':SimpleNamespace(client=client),
                                    'botocore.config':SimpleNamespace(Config=lambda **kwargs:kwargs)}):
            self.assertIs(reader,usage.account_reader(object()))
            self.assertEqual('reader-id',calls[0]['aws_access_key_id'])
            self.assertEqual('original-write-key',os.environ['R2_SECRET_ACCESS_KEY'])

    def test_all_buckets_included_and_partial_is_not_free_space(self):
        s3=S3();data=usage.r2_usage(s3,'main')
        self.assertEqual(500,data['used_bytes']);self.assertEqual('account',data['scope'])
        self.assertEqual(2,data['bucket_count'])
        s3.forbid_list=True;data=usage.r2_usage(s3,'main')
        self.assertEqual(200,data['known_used_bytes']);self.assertNotIn('remaining_bytes',data)
        self.assertEqual('AccessDenied',data['error_code'])
        with self.assertRaises(StorageBudgetExceeded):StorageBudget(s3,'main').reserve('new',20)
        self.assertEqual(0,s3.writes)

    def test_concurrent_writers_cannot_spend_same_remaining_bytes(self):
        s3=S3();baseline=usage.R2_SAFE_BYTES-CONTROL_RESERVE-1000
        guards=[StorageBudget(s3,'main'),StorageBudget(s3,'main')]
        for guard in guards:guard.snapshot={'status':'ok','scope':'account','used_bytes':baseline}
        def reserve(pair):
            index,guard=pair
            try:guard.reserve('raw/'+str(index),800);return True
            except StorageBudgetExceeded:return False
        with ThreadPoolExecutor(max_workers=2) as pool:results=list(pool.map(reserve,enumerate(guards)))
        self.assertEqual(1,sum(results))
        ledger=json.loads(s3.blobs['main',KEY])
        self.assertLessEqual(ledger['reserved_usage_bytes']+CONTROL_RESERVE,usage.R2_SAFE_BYTES)

    def test_ambiguous_reservation_is_retained_and_shrink_never_frees_budget(self):
        s3=S3();guard=StorageBudget(s3,'main')
        baseline=usage.R2_SAFE_BYTES-CONTROL_RESERVE-1000
        guard.snapshot={'status':'ok','scope':'account','used_bytes':baseline}
        s3.ambiguous=True
        with self.assertRaises(StorageBudgetExceeded):guard.reserve('new',800)
        with self.assertRaises(StorageBudgetExceeded):guard.reserve('new',800)
        self.assertEqual(baseline+800,json.loads(s3.blobs['main',KEY])['reserved_usage_bytes'])
        # Replacing an existing object with a smaller one gets no negative credit.
        guard.reserve('apartments',100)
        self.assertEqual(baseline+800,json.loads(s3.blobs['main',KEY])['reserved_usage_bytes'])

    def test_google_uses_account_total_and_capacity_failure_stops(self):
        class Request:
            def execute(self,**kwargs):return {'storageQuota':{'usage':'700','limit':'1000','usageInDrive':'300'}}
        class Drive:
            def about(self):return self
            def get(self,**kwargs):return Request()
        import google_drive_backup as backup
        with patch.object(backup,'authorized_drive',return_value=Drive()), \
             patch.object(backup,'execute',side_effect=lambda request:request.execute()):
            data=usage.google_usage(S3())
            self.assertEqual(70,data['percent']);self.assertEqual(300,data['drive_bytes'])
            usage.check_google_capacity(Drive(),300)
            with self.assertRaises(RuntimeError):usage.check_google_capacity(Drive(),301)

    def test_github_code_artifact_and_cache_are_separate(self):
        def request(path):
            if '/actions/artifacts?' in path:return {'artifacts':[
                {'id':1,'size_in_bytes':200,'expired':False},
                {'id':1,'size_in_bytes':200,'expired':False},
                {'id':2,'size_in_bytes':900,'expired':True}]}
            if path.endswith('/actions/cache/usage'):return {'active_caches_size_in_bytes':77}
            return {'size':1024}
        data=usage.github_usage(request)
        self.assertEqual(1048576,data['code']['used_bytes'])
        self.assertEqual(200,data['artifacts']['used_bytes']);self.assertEqual(77,data['cache']['used_bytes'])

    def test_combined_kakao_limits_and_unknowns_do_not_look_healthy(self):
        data=report();data['coverage']['gyeonggi']['sale'].update(stored=5261,percent=48.484)
        data['coverage']['gyeonggi']['rent'].update(stored=5239,percent=63.8)
        data['coverage']['gyeonggi']['total'].update(stored=10500,percent=55.083)
        data['storage']={'github':{'code':{'status':'ok',**usage.measured(18643968,usage.GIT_MANAGEMENT_BYTES)}},
            'r2':{'status':'ok','scope':'account',**usage.measured(449601145,usage.R2_FREE_BYTES)},
            'google':{'status':'ok',**usage.measured(500_000_000_000,5_000_000_000_000)},
            'guard':{'status':'armed'}}
        previous={'report':{'coverage':{'gyeonggi':{'total':{'stored':5703}}}}}
        text=daily.render_message(data,previous)
        self.assertLessEqual(len(text),200);self.assertIn('9.55',text);self.assertIn('4.50TB',text)
        self.assertIn('48.5%',text);self.assertIn('55.1%',text);self.assertIn('+4,797',text)
        data['storage']['r2']={'status':'partial','known_used_bytes':449601145}
        data['storage']['guard']={'status':'r2_data_paused'}
        data['storage']['google']={'status':'unknown'}
        text=daily.render_message(data,previous)
        self.assertIn('계정합계미확인',text);self.assertIn('🔴저장보류',text)
        self.assertNotIn('여유9.55',text)


if __name__=='__main__':unittest.main(verbosity=2)
