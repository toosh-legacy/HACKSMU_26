# Ship

Prepare and ship the current RumbleOS changes.

1. **Run smoke tests**
   ```bash
   python -c "from agents.base import BaseAgent, SENTINEL; print('base OK')"
   python -c "
   import numpy as np; from agents.nmf_masking import NMFMaskingAgent
   sr=4000; t=np.linspace(0,10,40000)
   sig=sum(np.sin(2*np.pi*18*n*t)/n for n in range(1,8))
   noisy=sig+np.random.randn(len(t))*0.5
   r=NMFMaskingAgent(0,None,None,name='T').process({'segment':noisy,'sr':sr,'noise_type':'airplane','original':noisy,'call_id':'t'})
   assert 14<=r['detected_f0']<=22; print('NMF OK F0=',r['detected_f0'])
   "
   ```
2. **Review the diff** — confirm no critical parameters were changed accidentally
3. **Commit** with a clear message describing which stage(s) changed and why
4. **Push** to remote branch
5. **Open a PR** if one doesn't exist — title should name the pipeline stage affected

Do not ship if the NMF smoke test fails or if any critical parameter was modified.
