"""Train finite-horizon, event-only possession value from real observed outcomes.
Inspired by xT; this is a small, own implementation, not a pretrained xT model.
"""
import hashlib
import json
from pathlib import Path
from collections import defaultdict

ROOT=Path(__file__).resolve().parents[1]
NX,NY,HORIZON=8,5,10

def cell(point):
    return min(NX-1,max(0,int(point[0]/105*NX)))+NX*min(NY-1,max(0,int(point[1]/68*NY)))

def actions(events):
    for e in events:
        if e.get('period') not in (1,2) or e.get('play_pattern',{}).get('name')!='Regular Play': continue
        kind=e.get('type',{}).get('name')
        if kind not in ('Pass','Carry','Shot') or 'location' not in e: continue
        point=[e['location'][0]*105/120,e['location'][1]*68/80]
        r={'event_id':e['id'],'team_id':e['team']['id'],'possession':e.get('possession'),
           'kind':kind.lower(),'start':point,'cell':cell(point),'success':True}
        if kind=='Shot':
            if e['shot'].get('body_part',{}).get('name') not in ('Left Foot','Right Foot'):continue
            r['goal']=e['shot']['outcome']['name']=='Goal'
        else:
            if kind=='Pass':
                p=e['pass']
                if p.get('body_part',{}).get('name') not in ('Left Foot','Right Foot') or p.get('height',{}).get('name')!='Ground Pass':continue
                end=p.get('end_location');r['success']='outcome' not in p
            else:end=e['carry'].get('end_location')
            if not end:continue
            r['end']=[end[0]*105/120,end[1]*68/80];r['end_cell']=cell(r['end'])
        yield r

def fit(rows):
    n=NX*NY;counts=[0]*n;goals=[0]*n;trans=[defaultdict(int) for _ in range(n)]
    # Failed moves end this simplified possession. Saved shots have no modeled rebound.
    for r in rows:
        a=r['cell'];counts[a]+=1
        if r['kind']=='shot':goals[a]+=r['goal']
        elif r['success']:trans[a][r['end_cell']]+=1
    # A 5-observation global goal-rate prior avoids fabricated monotonic spatial rules.
    prior=sum(goals)/max(1,len(rows));values=[[0.]*n]
    for _ in range(HORIZON):
        previous=values[-1]
        values.append([(goals[i]+5*prior+sum(count*previous[j] for j,count in trans[i].items()))/(counts[i]+5) for i in range(n)])
    return {'nx':NX,'ny':NY,'horizon_actions':HORIZON,'values_by_horizon':values,'cell_counts':counts,
            'prior_strength':5,'global_goal_per_action_prior':prior,
            'target':'goal within at most 10 eligible on-ball actions in the same simplified possession',
            'limitations':['Only ground foot passes, carries and foot shots in Regular Play.',
                'Failed moves and non-goal shots terminate the model; rebounds and set plays are not modeled.',
                'Carry events are recorded movements, not failed-dribble labels.',
                'Location-only possession value; no learned player ability, defender response or optimal policy.']}
