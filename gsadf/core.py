"""Right-tailed recursive ADF exploratory implementation; lag 0 intercept."""
import numpy as np
def adf_t(y,start,end):
    w=np.asarray(y[start:end],dtype=float)
    if len(w)<12 or not np.isfinite(w).all():return np.nan
    x=np.column_stack([np.ones(len(w)-1),w[:-1]])
    dy=np.diff(w)
    try:
        beta=np.linalg.lstsq(x,dy,rcond=None)[0]
        residual=dy-x@beta
        inv=np.linalg.inv(x.T@x)
        se=np.sqrt(max(0.,residual@residual/(len(dy)-2)*inv[1,1]))
        return float(beta[1]/se) if se>1e-12 else np.nan
    except np.linalg.LinAlgError:return np.nan
def minimum_window(n):
    return max(12,int(np.ceil((.01+1.8/np.sqrt(n))*n)))
def recursive_statistics(y,min_window=None):
    y=np.asarray(y,dtype=float);n=len(y);w=min_window or minimum_window(n)
    if n<w+5 or not np.isfinite(y).all():raise ValueError('insufficient observations')
    bsadf=np.full(n,np.nan)
    for end in range(w,n+1):
        z=[adf_t(y,start,end) for start in range(end-w+1)]
        good=[v for v in z if np.isfinite(v)]
        bsadf[end-1]=max(good) if good else np.nan
    return {'bsadf':bsadf,'gsadf':float(np.nanmax(bsadf)),'minimum_window':w}
def simulate_critical_values(n,reps=2000,seed=20261022,min_window=None):
    if reps<1:raise ValueError('reps must be positive')
    rng=np.random.default_rng(seed);w=min_window or minimum_window(n)
    samples=np.empty((reps,n));top=np.empty(reps)
    for i in range(reps):
        v=np.r_[0.,np.cumsum(rng.standard_normal(n-1))]
        x=recursive_statistics(v,w);samples[i]=x['bsadf'];top[i]=x['gsadf']
    with np.errstate(all='ignore'):
        import warnings
        with warnings.catch_warnings():
            warnings.simplefilter('ignore',RuntimeWarning)
            threshold=np.nanquantile(samples,.95,axis=0)
    return {'gsadf_95':float(np.quantile(top,.95)),'bsadf_95':threshold}
def date_episodes(periods,signal,min_duration):
    events=[];start=None
    for i,on in enumerate(list(signal)+[False]):
        if on and start is None:start=i
        if not on and start is not None:
            if i-start>=min_duration:events.append({'start':periods[start],'end':periods[i-1],'observations':i-start})
            start=None
    return events
