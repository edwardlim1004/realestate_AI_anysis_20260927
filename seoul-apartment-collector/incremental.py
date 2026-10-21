"""Deterministic snapshots and append-only change summaries (no credentials)."""
from collections import Counter
from datetime import datetime, timezone
import hashlib
import json

_SEEN={}


def canonical(record):
    return json.dumps(record,ensure_ascii=False,sort_keys=True,separators=(',',':'))


def counts(records):
    return Counter(canonical(record) for record in records)


def content_hash(records):
    # Order does not matter; identical-looking transactions keep their multiplicity.
    h=hashlib.sha256()
    for item,count in sorted(counts(records).items()):
        h.update((str(count)+'|'+item+'\n').encode('utf-8'))
    return h.hexdigest()


def change_summary(relative, before, after, existed, observed_day=None):
    old, new = counts(before), counts(after)
    old_hash=content_hash(before) if existed else None
    new_hash=content_hash(after)
    event_id=hashlib.sha256((relative+'|'+str(old_hash)+'|'+new_hash+'|'+str(observed_day)).encode()).hexdigest()
    return {'event_id':event_id, 'scope':relative,
            'kind':'updated' if existed else 'new_scope', 'observed_day_kst':observed_day,
            'added_rows':sum((new-old).values()),
            'removed_rows':sum((old-new).values()),
            'rows':len(after), 'before_content_sha256':old_hash,
            'after_content_sha256':new_hash}


def record_change(root, event, now=None):
    now=now or datetime.now(timezone.utc)
    path=root/now.strftime('%Y')/(now.strftime('%m')+'.jsonl')
    path.parent.mkdir(parents=True,exist_ok=True)
    signature=(path.stat().st_mtime_ns,path.stat().st_size) if path.exists() else None
    cached=_SEEN.get(path)
    if cached is None or cached[0]!=signature:
        ids={json.loads(line)['event_id'] for line in path.read_text(encoding='utf-8').splitlines()} if path.exists() else set()
    else:
        ids=cached[1]
    if event['event_id'] in ids:return False
    with path.open('a',encoding='utf-8') as out:
        out.write(canonical({'recorded_at_utc':now.isoformat(),**event})+'\n')
    ids.add(event['event_id'])
    _SEEN[path]=((path.stat().st_mtime_ns,path.stat().st_size),ids)
    return True
