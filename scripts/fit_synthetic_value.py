#!/usr/bin/env python3
"""Fit the auxiliary value grid using only newly generated first-week events."""
import hashlib
import json
import sys
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT))
from decision.train_value import fit, cell

def main():
    rows=[];sources={}
    for p in sorted((ROOT/'data/league/matches').glob('SYN26-W01-*/events.jsonl')):
        sources[str(p.relative_to(ROOT))]=hashlib.sha256(p.read_bytes()).hexdigest()
        for line in p.open():
            e=json.loads(line)
            if e['type'] not in ('pass','carry','shot') or e['period'] not in (1,2):continue
            direction=1 if (e['team_id']=='HOME')==(e['period']==1) else -1
            def point(x):return [x[0] if direction==1 else 105-x[0],x[1]]
            r=dict(kind=e['type'],cell=cell(point(e['start_location'])),success=e.get('outcome','complete')=='complete')
            if e['type']=='shot':r['goal']=e.get('outcome')=='goal'
            else:r['end_cell']=cell(point(e['end_location']))
            rows.append(r)
    if not rows:raise ValueError('No newly generated events')
    model=fit(rows)
    model['provenance']=dict(kind='simulated',seed=20261028,source_hashes=sources)
    model['validation']=dict(status='not_real_world_validated',training_actions=len(rows),warning='Synthetic-only auxiliary grid; no real-world calibration or counterfactual validation.')
    (ROOT/'decision/value-model.json').write_text(json.dumps(model,indent=2)+'\n')
    anchors=['generate.py','realism/profile.json','realism/player-action-profile.json','data/league/squads.json']
    (ROOT/'docs/decision-source-lock.json').write_text(json.dumps({n:hashlib.sha256((ROOT/n).read_bytes()).hexdigest() for n in anchors},indent=2)+'\n')
    print(json.dumps(dict(training_actions=len(rows),matches=len(sources))))

if __name__=='__main__':main()
