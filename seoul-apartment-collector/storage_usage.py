"""Live storage measurements. Unknown scope is never reported as free space."""
from datetime import datetime, timezone
import os

GB = 1_000_000_000
R2_FREE_BYTES = 10*GB
R2_SAFE_BYTES = 8*GB
GIT_MANAGEMENT_BYTES = GB


def account_reader(fallback):
    """Optional independent read-only account key; keep token encryption keys intact."""
    access=os.getenv('R2_USAGE_ACCESS_KEY_ID','')
    secret=os.getenv('R2_USAGE_SECRET_ACCESS_KEY','')
    if not access and not secret:return fallback
    if not access or not secret:raise ValueError('Incomplete R2 usage reader credentials')
    import boto3
    from botocore.config import Config
    return boto3.client('s3',endpoint_url='https://'+os.environ['R2_ACCOUNT_ID']+'.r2.cloudflarestorage.com',
        aws_access_key_id=access,aws_secret_access_key=secret,region_name='auto',
        config=Config(retries={'max_attempts':3,'mode':'standard'},connect_timeout=10,read_timeout=25))


def measured(used, limit=None):
    used = int(used)
    if used < 0:raise ValueError('Negative storage usage')
    limit = int(limit) if limit is not None else None
    if limit is not None and limit <= 0:raise ValueError('Invalid storage limit')
    return {'used_bytes':used,'limit_bytes':limit,
        'percent':round(used*100/limit,3) if limit else None,
        'remaining_bytes':max(0,limit-used) if limit else None}


def bucket_bytes(s3,bucket):
    total = 0; count = 0
    for page in s3.get_paginator('list_objects_v2').paginate(Bucket=bucket):
        for item in page.get('Contents',[]):
            size = int(item['Size'])
            if size < 0:raise ValueError('Invalid R2 object size')
            total += size;count += 1
    return total,count


def r2_usage(s3,bucket):
    try:
        reader=account_reader(s3)
        response = reader.list_buckets()
        buckets = [item['Name'] for item in response['Buckets']]
        if bucket not in buckets:raise ValueError('Configured bucket missing from account list')
        total = 0;count = 0
        for name in buckets:
            size,objects = bucket_bytes(reader,name);total += size;count += objects
        return {'status':'ok','scope':'account','bucket_count':len(buckets),'objects':count,
                **measured(total,R2_FREE_BYTES),'safe_bytes':R2_SAFE_BYTES}
    except Exception as error:
        # Scoped S3 tokens may be unable to enumerate the whole account.
        # The known bucket is useful but is not an account-wide measurement.
        try:
            used,count = bucket_bytes(s3,bucket)
            return {'status':'partial','scope':'configured_bucket','known_used_bytes':used,
                    'objects':count,'error_type':type(error).__name__,
                    'error_code':str(getattr(error,'response',{}).get('Error',{}).get('Code','')),
                    'safe_bytes':R2_SAFE_BYTES}
        except Exception as inner:
            return {'status':'unknown','scope':'unknown','error_type':type(inner).__name__,
                    'safe_bytes':R2_SAFE_BYTES}


def google_usage(s3):
    from google_drive_backup import authorized_drive,execute
    try:
        drive = authorized_drive(s3)
        quota = execute(drive.about().get(fields='storageQuota'))['storageQuota']
        result = measured(quota['usage'],quota.get('limit'))
        return {'status':'ok','scope':'account_or_workspace_pool',**result,
                'drive_bytes':int(quota.get('usageInDrive',0)),
                'trash_bytes':int(quota.get('usageInDriveTrash',0))}
    except Exception as error:
        return {'status':'unknown','error_type':type(error).__name__}


def check_google_capacity(drive,size):
    from google_drive_backup import execute
    try:
        quota = execute(drive.about().get(fields='storageQuota'))['storageQuota']
        used = int(quota['usage'])
        limit = int(quota['limit']) if quota.get('limit') is not None else None
        if used < 0 or size < 0:raise ValueError()
        # Missing limit is Google's documented unlimited/pool response.
        if limit is not None and used+size > limit:
            raise RuntimeError('Google Drive storage capacity insufficient')
    except RuntimeError:raise
    except Exception:
        raise RuntimeError('Google Drive capacity could not be verified') from None


def github_usage(request):
    repo = os.getenv('GITHUB_REPOSITORY','edwardlim1004/realestate_AI_anysis_20260927')
    prefix = '/repos/'+repo
    output = {}
    try:
        data = request(prefix)
        output['code'] = {'status':'ok','basis':'management_target_not_free_quota',
                          **measured(int(data['size'])*1024,GIT_MANAGEMENT_BYTES)}
    except Exception as error:output['code']={'status':'unknown','error_type':type(error).__name__}
    try:
        size = 0;count = 0;seen = set()
        for page in range(1,51):
            data = request(prefix+f'/actions/artifacts?per_page=100&page={page}')
            artifacts = data['artifacts']
            for artifact in artifacts:
                if artifact['id'] not in seen and not artifact.get('expired'):
                    size += int(artifact['size_in_bytes']);count += 1;seen.add(artifact['id'])
            if len(artifacts)<100:break
        else:raise RuntimeError('Artifact pagination bound reached')
        output['artifacts']={'status':'ok','used_bytes':size,'count':count,
                             'scope':'this_repository_not_account_billing'}
    except Exception as error:output['artifacts']={'status':'unknown','error_type':type(error).__name__}
    try:
        data = request(prefix+'/actions/cache/usage')
        output['cache']={'status':'ok','used_bytes':int(data['active_caches_size_in_bytes']),
                         'scope':'this_repository'}
    except Exception as error:output['cache']={'status':'unknown','error_type':type(error).__name__}
    return output


def collect_storage(s3,request):
    bucket = os.environ['R2_BUCKET_NAME']
    return {'checked_at_utc':datetime.now(timezone.utc).isoformat(),
            'github':github_usage(request),'r2':r2_usage(s3,bucket),'google':google_usage(s3)}
