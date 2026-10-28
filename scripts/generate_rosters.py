#!/usr/bin/env python3
"""Reproduce the fictional roster without reading any player source file."""
import argparse
import json
import random
import sys
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT))
from generate import CLUBS

def encoded():
    rng=random.Random(20261028)
    for _ in range(20):rng.randrange(0x1000000)
    for _ in range(80):rng.uniform(.92,1.08)
    teams=[]
    for club in CLUBS:
        players=[]
        for n in range(1,19):
            pos='GK' if n in (1,18) else 'DEF' if n<=7 else 'MID' if n<=12 else 'FWD'
            players.append(dict(player_id=f'{club["club_id"]}-P{n:02d}',name=f'{club["short_name"]} Player {n:02d}',shirt_number=n,position=pos,position_detail=pos,kind='simulated',simulated_profile=dict(kind='simulated',status='complete',attribute_kind='goalkeeper' if pos=='GK' else 'outfield',attributes={k:rng.randint(35,85) for k in ('ATT','TEC','TAC','DEF','CRE','BAL','ANT')},source_conflicts={})))
        teams.append(dict(club_id=club['club_id'],kind='simulated',players=players))
    return (json.dumps(dict(kind='simulated',seed=20261028,teams=teams),indent=2)+'\n').encode()

if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('--check',action='store_true');args=p.parse_args()
    path=ROOT/'data/league/squads.json'
    if args.check:
        if path.read_bytes()!=encoded():raise SystemExit('Roster reproducibility FAILED')
        print('Roster reproducibility PASS: 360 fictional players')
    else:
        path.parent.mkdir(parents=True,exist_ok=True);path.write_bytes(encoded())
