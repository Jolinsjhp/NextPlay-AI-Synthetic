#!/usr/bin/env python3
"""Package the integrated app, never local keys, uploaded videos, labels or Git data."""
import argparse
import hashlib
import json
import zipfile
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]

def paths(root=ROOT):
    result=[]
    for p in root.iterdir():
        if p.is_file() and p.suffix in ('.py','.js','.html','.css','.json') and not p.name.startswith('.'):
            result.append(p)
    for name in ('inside_the_game','realism','decision','decision_analysis','video_review','contracts','deploy/azure','data/decision-analysis','data/league','tests/fixtures/contracts'):
        for p in (root/name).rglob('*'):
            if not p.is_file() or any(part.startswith('.') or part=='__pycache__' for part in p.relative_to(root).parts):continue
            # B reads immutable decision snapshots from the derived sidecar. The repository
            # explicitly permits absent raw decisions; all metadata/event hashes stay intact.
            if p.name=='decisions.jsonl':continue
            if p.suffix in ('.pyc','.zip'):continue
            result.append(p)
    return sorted(set(result))

def build(output,root=ROOT):
    selected=paths(root);size=sum(p.stat().st_size for p in selected)
    if size>750*1024*1024:raise ValueError('Package exceeds the conservative F1 trial storage budget')
    output=Path(output);output.parent.mkdir(parents=True,exist_ok=True)
    with zipfile.ZipFile(output,'w',zipfile.ZIP_DEFLATED,compresslevel=3) as archive:
        for p in selected:archive.write(p,p.relative_to(root).as_posix())
    manifest=dict(files=len(selected),uncompressed_bytes=size,zip_bytes=output.stat().st_size,sha256=hashlib.sha256(output.read_bytes()).hexdigest(),
        excludes=['.local','.env','private video uploads','labels','credentials','Git','node_modules','duplicate league-validated','raw decisions.jsonl'],
        source='local integrated branch; not deployed or provider-tested')
    output.with_suffix('.manifest.json').write_text(json.dumps(manifest,indent=2)+'\n')
    return manifest

if __name__=='__main__':
    parser=argparse.ArgumentParser();parser.add_argument('--output',type=Path,default=ROOT/'artifacts/deployment/nextplay-azure.zip');args=parser.parse_args()
    print(json.dumps(build(args.output),indent=2))
