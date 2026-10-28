#!/usr/bin/env python3
"""Build a standalone clean source/data ZIP without Git, uploads or credentials."""
import argparse
import hashlib
import json
import zipfile
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]
EXCLUDED={'.git','.local','node_modules','__pycache__','.training','.models','.pytest_cache','.venv'}

def build(output):
    output=Path(output).resolve()
    selected=[]
    for p in ROOT.rglob('*'):
        if not p.is_file():continue
        rel=p.relative_to(ROOT)
        if set(rel.parts)&EXCLUDED or p==output or p.suffix in ('.pyc','.zip','.mp4','.webm','.joblib'):continue
        if p.name.startswith('.env') and p.name!='.env.example':continue
        if p.name=='.DS_Store':continue
        selected.append(p)
    with zipfile.ZipFile(output,'w',zipfile.ZIP_DEFLATED,compresslevel=5) as z:
        for p in sorted(selected):z.write(p,p.relative_to(ROOT).as_posix())
    report=dict(files=len(selected),bytes=output.stat().st_size,sha256=hashlib.sha256(output.read_bytes()).hexdigest(),excludes=sorted(EXCLUDED|{'credentials','uploaded videos','legacy data','old Git history'}))
    output.with_suffix('.manifest.json').write_text(json.dumps(report,indent=2)+'\n')
    print(json.dumps(report,indent=2))

if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('output',type=Path);build(p.parse_args().output)
