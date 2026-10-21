"""Official-vintage preserving incremental storage."""
import csv,datetime
from pathlib import Path
FIELDS=['period','value','source_id']
def read(path):
    if not Path(path).exists():return {}
    with open(path,encoding='utf-8-sig',newline='') as f:rows=list(csv.DictReader(f))
    result={}
    for row in rows:
        p=row['period']
        if p in result or any(not row.get(k) for k in FIELDS):raise ValueError('duplicate or incomplete '+p)
        result[p]={k:row[k] for k in FIELDS}
    return result
def update(source,master,log):
    old=read(master);new=read(source)
    if not new:raise ValueError('empty download')
    events=[]
    for p,row in sorted(new.items()):
        was=old.get(p)
        if was!=row:
            events.append({'timestamp_utc':datetime.datetime.now(datetime.timezone.utc).isoformat(),'period':p,'change':'NEW' if was is None else 'REVISED','old_value':was['value'] if was else '', 'new_value':row['value']})
            old[p]=row
    Path(master).parent.mkdir(parents=True,exist_ok=True)
    tmp=Path(str(master)+'.tmp')
    with tmp.open('w',newline='',encoding='utf-8') as f:
        w=csv.DictWriter(f,fieldnames=FIELDS);w.writeheader();w.writerows(old[p] for p in sorted(old))
    tmp.replace(master)
    if events:
        lp=Path(log);exists=lp.exists()
        with lp.open('a',newline='',encoding='utf-8') as f:
            w=csv.DictWriter(f,fieldnames=list(events[0]))
            if not exists:w.writeheader()
            w.writerows(events)
    return {'new':sum(x['change']=='NEW' for x in events),'revised':sum(x['change']=='REVISED' for x in events)}
