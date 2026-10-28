#!/usr/bin/env python3
"""Read-only release gate. Reports file paths/counts, never player field values.

This detects known source fields, not ownership, permission or legal compliance.
Run against a proposed dataset before publishing. Nonzero means manual review.
"""
import argparse
import gzip
import json
from collections import Counter
from pathlib import Path

KEYS={'sofascore','date_of_birth','api_player_id','source_date_of_birth'}
DOMAINS=('premierleague.com','sofascore.com')


def scan(root):
    counts=Counter();findings=[];errors=[]
    for p in sorted(Path(root).rglob('*')):
        if not p.is_file() or not (p.suffix in ('.json','.jsonl') or p.name.endswith('.jsonl.gz')):continue
        per_file=Counter()
        try:
            opener=gzip.open if p.suffix=='.gz' else open
            with opener(p,'rt',encoding='utf-8') as f:
                documents=(json.loads(line) for line in f if line.strip()) if '.jsonl' in p.name else (json.load(f),)
                for doc in documents:
                    stack=[doc]
                    while stack:
                        value=stack.pop()
                        if isinstance(value,dict):
                            for key,child in value.items():
                                if key in KEYS and child is not None:per_file[key]+=1
                                stack.append(child)
                        elif isinstance(value,list):stack.extend(value)
                        elif isinstance(value,str):
                            for domain in DOMAINS:
                                if domain in value.lower():per_file['source_domain:'+domain]+=1
        except (OSError,ValueError,UnicodeError):errors.append(str(p));continue
        if per_file:
            counts.update(per_file);findings.append(dict(path=str(p),counts=dict(per_file)))
    return dict(ready=not findings and not errors,field_occurrences=dict(counts),affected_files=len(findings),
                files=findings,unreadable_files=errors,
                note='Known-field detection only. Clean output is not proof of independent generation, permission, anonymity or eligibility.')


if __name__=='__main__':
    parser=argparse.ArgumentParser();parser.add_argument('root',nargs='?',default='data');args=parser.parse_args()
    report=scan(args.root);print(json.dumps(report,ensure_ascii=False,indent=2));raise SystemExit(0 if report['ready'] else 1)
