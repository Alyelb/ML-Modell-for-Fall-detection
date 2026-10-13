"""Kennwerte je Aktivitaet (|a|max, |w|max, |a|min, Lageaenderung, Ruhe) aus den Pilotdaten.
Aufruf: python tools/kennwerte_pilot.py Pilotdaten/   (Unterordner Waist, Right_Ankle, Left_Ankle)"""
import sys,re,numpy as np,json
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
import fall_lib as fl
from pathlib import Path
FS=50
def feats(x,c):
    a=np.linalg.norm(x[:,:3],axis=1); g=np.linalg.norm(x[:,3:],axis=1)
    lo,hi=max(0,c-FS),min(len(x),c+FS//2)
    pre=x[max(0,c-int(1.5*FS)):max(1,c-int(0.5*FS)),:3].mean(0)
    post_seg=x[c+FS:c+3*FS]
    if len(post_seg)<FS or len(pre)==0 or not np.isfinite(pre).all(): return None
    post=post_seg[:,:3].mean(0)
    ang=np.degrees(np.arccos(np.clip(pre@post/np.linalg.norm(pre)/np.linalg.norm(post),-1,1)))
    return dict(a_max=a[lo:hi].max(), a_min=a[max(0,c-FS):c+1].min(), g_max=g[lo:hi].max(),
                winkel=ang, ruhe_std=np.std(np.linalg.norm(post_seg[:,:3],axis=1)))
rows=[]
for pos in ["Waist","Right_Ankle","Left_Ankle"]:
    for f in sorted(Path(sys.argv[1] if len(sys.argv)>1 else 'Pilotdaten',pos).glob('*.csv')):
        x=fl._read_pilot_csv(f)
        act=re.sub(r"^\d+_[A-Z_]+?_","",f.stem)
        a=np.linalg.norm(x[:,:3],axis=1)
        if act.startswith('fall'):
            cs=fl.pilot_impacts(x)
        else:
            # alle lokalen |a|-Spitzen > 1.3 g, mind. 1 s Abstand; ersten 4 s (Klopfmarken) auslassen
            cs=[];last=-999
            for i in range(4*FS,len(a)-1):
                if a[i]>1.3 and a[i]==a[max(0,i-FS//2):i+FS//2].max() and i-last>FS:
                    cs.append(i);last=i
        for c in cs:
            r=feats(x,c)
            if r: rows.append(dict(pos=pos.upper(),act=act,fall=act.startswith('fall'),**{k:float(v) for k,v in r.items()}))

import collections
for pos in ["WAIST","RIGHT_ANKLE","LEFT_ANKLE"]:
    print("\n==",pos)
    print(f"{'Aktivitaet':14s}{'n':>4}  {'|a|max g (min-max)':>20}  {'|w|max dps':>16}  {'|a|min g':>12}  {'Winkel deg':>12}  {'Ruhe-std g':>12}")
    for act in sorted({r['act'] for r in rows if r['pos']==pos}):
        s=[r for r in rows if r['pos']==pos and r['act']==act]
        f=lambda k:f"{min(r[k] for r in s):.2f}-{max(r[k] for r in s):.2f}"
        print(f"{act:14s}{len(s):>4}  {f('a_max'):>20}  {f('g_max'):>16}  {f('a_min'):>12}  {f('winkel'):>12}  {f('ruhe_std'):>12}")
