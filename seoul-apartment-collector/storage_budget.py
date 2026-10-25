"""Shared conservative R2 data budget; atomic reservations across writers.

All-account listing is mandatory. Failed/ambiguous uploads retain reservations.
Positive growth is charged; shrink/deletion is not reclaimed automatically.
This deliberately favors early Drive failover over undercounting storage.
"""
import json
import time
from datetime import datetime, timezone
from storage_usage import r2_usage, R2_SAFE_BYTES

KEY = 'internal/storage-budget-v1.json'
CONTROL_RESERVE = 1_000_000


class StorageBudgetExceeded(RuntimeError):pass


def error_code(error):
    return str(getattr(error,'response',{}).get('Error',{}).get('Code',''))


class StorageBudget:
    def __init__(self,s3,bucket):
        self.s3=s3;self.bucket=bucket;self.snapshot=None

    def reserve(self,key,size):
        if self.snapshot is None:self.snapshot=r2_usage(self.s3,self.bucket)
        if self.snapshot.get('status')!='ok' or self.snapshot.get('scope')!='account':
            raise StorageBudgetExceeded('R2 account usage is unknown; use verified Google Drive')
        try:
            try:
                old=self.s3.head_object(Bucket=self.bucket,Key=key)
                previous=int(old['ContentLength'])
            except Exception as error:
                if error_code(error) not in ('NoSuchKey','NotFound','404'):raise
                previous=0
            growth=max(0,int(size)-previous)
            if size < 0:raise ValueError()
            for attempt in range(8):
                try:
                    try:
                        response=self.s3.get_object(Bucket=self.bucket,Key=KEY)
                    except Exception as error:
                        if error_code(error) not in ('NoSuchKey','NotFound','404'):raise
                        response=None
                    if response:
                        body=response['Body']
                        try:raw=body.read(8193)
                        finally:body.close()
                        if len(raw)>8192:raise ValueError()
                        ledger=json.loads(raw)
                        used=int(ledger['reserved_usage_bytes'])
                        if used<0 or ledger.get('schema')!=1:raise ValueError()
                        condition={'IfMatch':response['ETag']}
                    else:
                        used=0;condition={'IfNoneMatch':'*'}
                    projected=max(used,self.snapshot['used_bytes'])+growth
                    if projected+CONTROL_RESERVE > R2_SAFE_BYTES:
                        raise StorageBudgetExceeded('R2 8 GB safety threshold reached; use verified Google Drive')
                    payload={'schema':1,'reserved_usage_bytes':projected,
                             'checked_at_utc':datetime.now(timezone.utc).isoformat(),
                             'safety_bytes':R2_SAFE_BYTES}
                    self.s3.put_object(Bucket=self.bucket,Key=KEY,
                        Body=json.dumps(payload).encode(),ContentType='application/json',**condition)
                    return
                except StorageBudgetExceeded:raise
                except Exception as error:
                    if error_code(error) not in ('PreconditionFailed','412','SlowDown','TooManyRequests','429'):
                        raise
                    if attempt==7:raise
                    time.sleep(1.1)
        except StorageBudgetExceeded:raise
        except Exception:
            raise StorageBudgetExceeded('R2 shared budget could not be reserved; use verified Google Drive') from None
