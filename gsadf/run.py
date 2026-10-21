"""Standalone simulation; never changes composite or live dashboard."""
import argparse,csv,hashlib,json,math
from datetime import datetime,timezone
from pathlib import Path
import numpy as np
from .core import recursive_statistics,simulate_critical_values,date_episodes
def run(csv_path,output_path,reps=2000,seed=20261022):
    src=Path(csv_path);raw=src.read_bytes()
    with src.open(encoding='utf-8-sig',newline='') as f:rows=list(csv.DictReader(f))
    if len(rows)<48:raise ValueError('minimum 48 observations')
    periods=[r['period'] for r in rows]
    if periods!=sorted(set(periods)):raise ValueError('duplicates or unordered periods')
    if not all(len(p)==7 and p[4:6]=='-Q' and p[-1] in '1234' and p[:4].isdigit() for p in periods):raise ValueError('quarterly only')
    indexes=[int(p[:4])*4+int(p[-1]) for p in periods]
    if any(b-a!=1 for a,b in zip(indexes,indexes[1:])):raise ValueError('series contains gaps')
    values=np.array([float(r['value']) for r in rows])
    if not np.isfinite(values).all() or np.any(values<=0):raise ValueError('nonpositive value')
    if any(not r.get('source_id') for r in rows):raise ValueError('missing provenance')
    stats=recursive_statistics(np.log(values));cv=simulate_critical_values(len(values),reps,seed,stats['minimum_window'])
    exceed=np.isfinite(stats['bsadf']) & (stats['bsadf']>cv['bsadf_95'])
    episodes=date_episodes(periods,exceed,max(2,math.ceil(math.log(len(periods)))))
    result={'schemaVersion':'gsadf.v1','approval':'PENDING_INDEPENDENT_VALIDATION','eligibleForComposite':False,
        'generatedAtUTC':datetime.now(timezone.utc).isoformat(),
        'source':{'file':src.name,'sha256':hashlib.sha256(raw).hexdigest(),'start':periods[0],'end':periods[-1],'observations':len(periods)},
        'method':{'frequency':'quarterly','transform':'log','ADF_lag':0,'intercept':True,'MC_repetitions':reps,'MC_seed':seed,'criticalQuantile':.95,'null':'Gaussian random walk','minimumWindow':stats['minimum_window']},
        'result':{'gsadf':stats['gsadf'],'critical95':cv['gsadf_95'],'reject95':bool(stats['gsadf']>cv['gsadf_95']),'episodes':episodes},
        'history':[{'period':p,'bsadf':float(v) if np.isfinite(v) else None,'critical95':float(c) if np.isfinite(c) else None} for p,v,c in zip(periods,stats['bsadf'],cv['bsadf_95'])]}
    output=Path(output_path);output.parent.mkdir(parents=True,exist_ok=True)
    output.write_text(json.dumps(result,indent=2,allow_nan=False),encoding='utf-8')
    print(f"{src.name}: GSADF {stats['gsadf']:.3f} / 95% critical {cv['gsadf_95']:.3f}; COMPOSITE LOCKED")
    return result
if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('--input',required=True);p.add_argument('--output',required=True);p.add_argument('--reps',type=int,default=2000);a=p.parse_args()
    run(a.input,a.output,a.reps)
