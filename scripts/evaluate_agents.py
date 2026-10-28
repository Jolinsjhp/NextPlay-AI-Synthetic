#!/usr/bin/env python3
"""Explicitly opt in to paid calls. No invented offline model evaluation results."""
import argparse
import json
import sys
import time
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from decision_analysis.service import repository
from decision_analysis.agents import run, configuration

parser=argparse.ArgumentParser(description='Compare one-agent and four-agent explanations on three registered snapshots.')
parser.add_argument('--live',action='store_true',help='Actually invoke the configured provider (may incur charges).')
args=parser.parse_args()
repo=repository();config=configuration();rows=[]
for match_id in list(repo.matches)[:3]:
    row=next(r for r in repo.index(match_id)['records'] if r['analyzable'])
    snapshot=repo.records(match_id)[row['snapshot_id']]['snapshot'];request=repo.request_for(snapshot)
    request['mode']='fan';request['question']='Why prefer the highest-ranked option, and what could go wrong?'
    public,_=repo.compare(request)
    for strategy in ('single','multi'):
        start=time.monotonic()
        result=run(request,public['candidate_set_id'],config,repo,strategy=strategy) if args.live else None
        rows.append(dict(match_id=match_id,snapshot_id=request['snapshot_id'],candidate_set_id=public['candidate_set_id'],
            strategy=strategy,execution='live' if args.live else 'not_run',
            status=result['status'] if result else 'not_run',
            elapsed_s=round(time.monotonic()-start,3) if args.live else None,
            explanation=result['explanation'] if result else None,
            trace=result['agent_trace'] if result else [],
            limitation='A valid evidence ID does not prove a claim is correct. Human quality review is still required.'))
print(json.dumps(rows,ensure_ascii=False,indent=2))
