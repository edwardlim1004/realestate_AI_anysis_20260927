"""Get official Korean quarterly RHP/PIR/PTR; reject schema mismatches."""
import argparse,csv,datetime,io,json,time,urllib.request,urllib.error
from pathlib import Path
from .incremental import update
BASES=(
    'https://sdmx.oecd.org/public/rest/data/OECD.ECO.MPD,DSD_AN_HOUSE_PRICES@DF_HOUSE_PRICES,1.0/',
    'https://sdmx.oecd.org/public/rest/v1/data/OECD.ECO.MPD,DSD_AN_HOUSE_PRICES@DF_HOUSE_PRICES,1.0/',
)
UNIT={'RHP':'IX','HPI_YDH_AVG':'PT_AVG_L_TERM','HPI_RPI_AVG':'PT_AVG_L_TERM'}
MEASURES={'RHP':'real_hpi','HPI_YDH_AVG':'pir','HPI_RPI_AVG':'ptr'}
def fetch(measure,root):
    # Complete SDMX key REF_AREA.FREQ.MEASURE.UNIT_MEASURE. An empty
    # final dimension and a bare 'Accept: csvfile' caused HTTP 500 on runner.
    urls=[f'{base}KOR.Q.{measure}.{UNIT[measure]}?startPeriod=1980-Q1&dimensionAtObservation=AllDimensions&format=csvfile'
          for base in BASES]
    error=None;url=None;blob=None
    for endpoint in urls:
        url=endpoint
        for attempt in range(3):
            try:
                req=urllib.request.Request(url,headers={'User-Agent':'GSADF-Research/1.1'})
                with urllib.request.urlopen(req,timeout=90) as response:
                    blob=response.read(15000000)
                    if len(blob)>=15000000:raise ValueError('response too large')
                break
            except (urllib.error.URLError,TimeoutError) as exc:
                error=exc
                if isinstance(exc,urllib.error.HTTPError) and exc.code in (400,404):
                    break
                time.sleep(2**attempt)
        if blob is not None: break
    if blob is None:
        raise RuntimeError(f'Official OECD API failed for {measure} on both documented endpoints: {type(error).__name__} HTTP {getattr(error,"code","N/A")}') from error
    raw=root/'raw';raw.mkdir(parents=True,exist_ok=True)
    stamp=datetime.datetime.now(datetime.timezone.utc).strftime('%Y%m%dT%H%M%SZ')
    (raw/f'{MEASURES[measure]}_{stamp}.csv').write_bytes(blob)
    reader=csv.DictReader(io.StringIO(blob.decode('utf-8-sig')))
    required={'TIME_PERIOD','OBS_VALUE','REF_AREA','FREQ','MEASURE','UNIT_MEASURE'}
    if not reader.fieldnames or not required.issubset(reader.fieldnames):raise ValueError(f'Unexpected OECD schema: {reader.fieldnames}')
    records={}
    for row in reader:
        if any(row[k]!=expected for k,expected in [('REF_AREA','KOR'),('FREQ','Q'),('MEASURE',measure),('UNIT_MEASURE',UNIT[measure])]):continue
        p=row['TIME_PERIOD'];v=row['OBS_VALUE']
        if not v or len(p)!=7 or p[4:6]!='-Q' or p[-1] not in '1234':continue
        val=float(v)
        if not 0<val<100000:raise ValueError('bad observation '+p)
        if p in records and records[p]!=v:raise ValueError('multiple inconsistent series '+p)
        records[p]=v
    if len(records)<48:raise ValueError(f'Incomplete historical records {measure}: {len(records)}')
    staged=root/f'{MEASURES[measure]}_incoming.csv'
    with staged.open('w',newline='',encoding='utf-8') as f:
        w=csv.DictWriter(f,fieldnames=['period','value','source_id']);w.writeheader()
        w.writerows({'period':p,'value':records[p],'source_id':f'OECD|KOR|Q|{measure}'} for p in sorted(records))
    outcome=update(staged,root/f'korea_{MEASURES[measure]}_quarterly.csv',root/f'{MEASURES[measure]}_revisions.csv')
    staged.unlink()
    return {'measure':measure,'earliest':min(records),'latest':max(records),'observations':len(records),'updates':outcome,'url':url}
def main():
    ap=argparse.ArgumentParser();ap.add_argument('--data-dir',default='gsadf/data')
    root=Path(ap.parse_args().data_dir);root.mkdir(parents=True,exist_ok=True)
    results=[fetch(m,root) for m in MEASURES]
    (root/'source_manifest.json').write_text(json.dumps(results,indent=2),encoding='utf-8')
    print(json.dumps(results,indent=2))
if __name__=='__main__':main()
