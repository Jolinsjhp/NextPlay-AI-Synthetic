"""Offline StatsBomb-format aggregate fitting; never changes the release dataset.

Use only on locally supplied data whose intended use has been authorized.
No downloader, player attributes, real sequences or match IDs are exported.
"""
import argparse
import hashlib
import json
import math
from collections import defaultdict
from pathlib import Path
from realism.model import bucket, shot_bucket

def records(events):
    for e in events:
        if e.get('period', 0) > 2 or e.get('play_pattern', {}).get('name') != 'Regular Play':
            continue
        kind = e.get('type', {}).get('name', '').lower()
        if kind not in ('pass', 'carry', 'shot') or 'location' not in e:
            continue
        x, y = e['location'][:2]
        x, y = x*105/120, y*68/80
        r = {'kind': kind, 'x': x, 'y': y}
        if kind == 'pass':
            p = e['pass']
            if p.get('body_part', {}).get('name') not in ('Left Foot', 'Right Foot') or p.get('height', {}).get('name') != 'Ground Pass':
                continue
            end = p.get('end_location')
            if not end:
                continue
            ex, ey = end[0]*105/120, end[1]*68/80
            r.update(distance=math.hypot(ex-x, ey-y), backward=ex < x-1,
                     big_back=x>88 and ex<x-30, pressured=bool(e.get('under_pressure')),
                     success='outcome' not in p)
        elif kind == 'shot':
            if e['shot'].get('body_part', {}).get('name') not in ('Left Foot', 'Right Foot'):
                continue
            r.update(distance=math.hypot(105-x, y-34), success=e['shot']['outcome']['name']=='Goal')
        yield r

def fit(rows):
    groups = {'pass_success': defaultdict(list), 'shot_goal': defaultdict(list)}
    actions = defaultdict(lambda: defaultdict(int))
    for r in rows:
        actions[str(min(3, int(r['x']//26.25)))][r['kind']] += 1
        if r['kind']=='pass':
            groups['pass_success'][f"{bucket(r['distance'])}:{int(r['pressured'])}"].append(r['success'])
        if r['kind']=='shot':
            groups['shot_goal'][str(shot_bucket(r['x'], r['y']))].append(r['success'])
    result = {}
    for name, cells in groups.items():
        all_values = [v for cell in cells.values() for v in cell]
        prior = sum(all_values)/len(all_values) if all_values else 0.0
        result[name] = {key: {'n': len(values), 'probability': (sum(values)+20*prior)/(len(values)+20)}
                        for key, values in cells.items()}
    result['pass_geometry'] = {}
    for zone in range(4):
        group = [r for r in rows if r['kind']=='pass' and min(3,int(r['x']//26.25))==zone]
        result['pass_geometry'][str(zone)] = {'backward': (sum(r['backward'] for r in group)+1)/(len(group)+2),
            'lengths': [(sum(bucket(r['distance'])==b for r in group)+1)/(len(group)+5) for b in range(5)]}
    result['actions'] = {key: {kind: (counts[kind]+1)/(sum(counts.values())+3)
                              for kind in ('pass','carry','shot')} for key, counts in actions.items()}
    return result

def summary(rows):
    passes = [r for r in rows if r['kind']=='pass']
    shots = [r for r in rows if r['kind']=='shot']
    return {'actions': len(rows), 'passes': len(passes), 'shots': len(shots),
            'pass_distance_m': sum(r['distance'] for r in passes)/max(1,len(passes)),
            'pass_completion': sum(r['success'] for r in passes)/max(1,len(passes)),
            'backward_pass_share': sum(r['backward'] for r in passes)/max(1,len(passes)),
            'shot_distance_m': sum(r['distance'] for r in shots)/max(1,len(shots)),
            'shot_conversion': sum(r['success'] for r in shots)/max(1,len(shots))}

def run(manifest_path, output):
    manifest_path = Path(manifest_path).resolve()
    manifest = json.loads(manifest_path.read_text())
    permission = manifest.get('authorization', {})
    required = {'research', 'hackathon', 'public_derived_statistics', 'public_demo'}
    if permission.get('reviewed') is not True or not required <= set(permission.get('uses', [])):
        raise ValueError('Document permission for research, hackathon, public derived statistics and public demo first')
    if not isinstance(permission.get('reference'), str) or not permission['reference'].strip():
        raise ValueError('An authorization reference is required; do not include private correspondence or secrets')
    sources = manifest.get('sources', [])
    if not isinstance(sources, list) or not sources:
        raise ValueError('Provide local source files and predeclared train/test splits')
    splits = {'train': [], 'test': []}
    hashes = {'train': [], 'test': []}
    seen = set()
    for source in sources:
        split = source.get('split')
        if split not in splits:
            raise ValueError('Each source must have split train or test')
        path = (manifest_path.parent / source['path']).resolve()
        raw = path.read_bytes()
        sha = hashlib.sha256(raw).hexdigest()
        if sha != source.get('sha256'):
            raise ValueError('Source hash mismatch')
        if sha in seen:
            raise ValueError('Duplicate source or leakage between splits')
        seen.add(sha)
        events = json.loads(raw)
        if not isinstance(events, list):
            raise ValueError('Expected an event list')
        splits[split].extend(records(events))
        hashes[split].append(sha)
    for split, rows in splits.items():
        if not hashes[split] or any(not any(r['kind']==k for r in rows) for k in ('pass', 'carry', 'shot')):
            raise ValueError('Both disjoint splits need passes, carries and shots')
    profile = fit(splits['train'])
    profile['kind'] = 'external_aggregate_research'
    profile['provenance'] = {
        'provider': 'StatsBomb', 'source_sha256': hashes,
        'scope': 'Regular Play, periods 1–2; footed ground passes, footed shots and carries',
        'coordinates': '120x80 scaled to 105x68 metres',
        'authorization_reference': permission['reference'],
        'attribution_required': 'StatsBomb credit and brand logo; follow the applicable agreement',
        'release_activation': 'not activated; synthetic release data unchanged'}
    metrics = {}
    for kind, table in (('pass', 'pass_success'), ('shot', 'shot_goal')):
        train = [r for r in splits['train'] if r['kind']==kind]
        test = [r for r in splits['test'] if r['kind']==kind]
        prior = sum(r['success'] for r in train)/len(train)
        def predict(row):
            key = f"{bucket(row['distance'])}:{int(row['pressured'])}" if kind=='pass' else str(shot_bucket(row['x'], row['y']))
            return profile[table].get(key, {'probability': prior})['probability']
        predictions = [predict(r) for r in test]
        metrics[kind] = dict(n=len(test), brier=sum((p-r['success'])**2 for p,r in zip(predictions,test))/len(test),
            constant_train_prior_brier=sum((prior-r['success'])**2 for r in test)/len(test),
            observed_rate=sum(r['success'] for r in test)/len(test), mean_prediction=sum(predictions)/len(test))
    report = dict(train=summary(splits['train']), held_out=summary(splits['test']), predictive_metrics=metrics,
        split_source_counts={k:len(v) for k,v in hashes.items()},
        limitations=['Selected event frequencies are not decision-opportunity frequencies.',
            'No tracking or counterfactual validation; no Premier League transfer claim.',
            'These checks do not certify licensing or competition eligibility.',
            'Existing bundled matches and fitted Q2 models have not been recalibrated.'])
    output = Path(output).resolve()
    private_root = Path(__file__).resolve().parents[1]/'.local'
    if private_root.resolve() not in output.parents:
        raise ValueError('Write research outputs inside .local, outside the public release')
    output.mkdir(parents=True, exist_ok=True)
    (output/'profile.json').write_text(json.dumps(profile, indent=2)+'\n')
    (output/'validation.json').write_text(json.dumps(report, indent=2)+'\n')
    return report

if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--manifest', type=Path, required=True)
    parser.add_argument('--output', type=Path, default=Path(__file__).resolve().parents[1]/'.local/statsbomb-calibration')
    args = parser.parse_args()
    print(json.dumps(run(args.manifest, args.output), indent=2))
