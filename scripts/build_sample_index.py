import sys,json,gzip
from pathlib import Path
root=Path(__file__).resolve().parents[1];sys.path.insert(0,str(root))
from decision_analysis.service import Repository
repo=Repository()
for mid in repo.matches:
 p=repo.root/'matches'/mid/'index.json';index=json.loads(p.read_text());records=repo.records(mid);sample=json.loads(gzip.decompress((p.parent/'scored.json.gz').read_bytes()));sample_ids={r['decision_id'] for r in sample};eligible_ids={r['decision_id'] for r in sample if any(c['eligible'] for c in r['response']['candidates'])};teams={p['player_id']:p['team_id'] for p in repo.metadata(mid)['players']}
 for row in index['records']:
  snap=records[row['snapshot_id']]['snapshot'];f=snap['frame'];team=teams.get(row['actor_id'],'HOME');x=f['ball'][0];x=x if snap['attacking_direction'].get(team)=='positive_x' else 105-x
  row.update(period=snap['period'],team_id=team,zone=min(2,int(x/35)),category='sampled comparison' if row['decision_id'] in sample_ids else 'compute on selection',analyzable=row['decision_id'] in eligible_ids if row['decision_id'] in sample_ids else None)
 index.update(source_dataset='league',index_mode='periodic_sample_with_on_demand_scoring',representative_ids=[r['decision_id'] for r in index['records'] if r['decision_id'] in eligible_ids],largest_ids=[],summary=dict(covered=len(index['records']),analyzable=len(eligible_ids),players=len({r['actor_id'] for r in index['records']}),representative_players=len({r['actor_id'] for r in index['records'] if r['decision_id'] in eligible_ids})))
 p.write_text(json.dumps(index,separators=(',',':'))+'\n')
print('Published sampled decision indexes for',len(repo.matches),'matches')
