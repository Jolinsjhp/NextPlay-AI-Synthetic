"""Run the teammate's analytic route kernel on a single bound decision snapshot."""
import copy
import importlib.util
import os
from pathlib import Path


def kernel_inputs(snapshot, metadata, public, private):
    from inside_the_game.features.from_tracking import SynthMatch
    f=snapshot['frame'];t=int(snapshot['t_ms']);frame_id=t
    frame=copy.deepcopy(f)
    frame.update(frame_id=frame_id,t_ms=t,attack_dir=1 if snapshot['attacking_direction']['HOME']=='positive_x' else -1)
    frame['ball']=[f['ball'][0]-52.5,f['ball'][1]-34,*f['ball'][2:]]
    frame['players']=[[p[0],p[1]-52.5,p[2]-34,*p[3:]] for p in f['players']]
    teams={p['player_id']:p['team_id'] for p in metadata['players']}
    event=dict(type='decision_point',event_id=snapshot['snapshot_id'],match_id=snapshot['match_id'],
               available_at_ms=t,player_id=f['ball_owner_id'],team_id=teams[f['ball_owner_id']],options=[])
    options={o['key']:o for o in private['options']}
    for c in public['candidates']:
        if not c['eligible'] or c['type'] not in ('pass','carry'):continue
        target=options[c['action_id']].get('target')
        if target is None:continue
        # The public target is a point in metres; only already-computed candidates enter.
        target_id=c['action_id'].split(':',1)[1] if c['type']=='pass' else None
        event['options'].append(dict(option_id=c['action_id'],type=c['type'],target_player_id=target_id,
            end_location=[target[0]-52.5,target[1]-34],offside=False))
    meta=dict(match_id=snapshot['match_id'],frame_hz=1000,players=copy.deepcopy(metadata['players']))
    return SynthMatch(Path('.'),meta,{frame_id:frame},(event,)),event


def workflow_diagnostic(snapshot, metadata, public, private, backend=None):
    backend=backend or os.getenv('NEXTPLAY_KERNEL_BACKEND','framework')
    result=dict(backend=backend,snapshot_id=snapshot['snapshot_id'],candidate_set_id=public['candidate_set_id'],
        affects_candidate_ranks=False,model_called=False,
        note='Analytic kernel diagnostics only. Q2 owns candidate ranks. Narration request is built but not sent; the evidence-reviewed four-role team remains separate.')
    if backend not in ('framework','direct'):raise ValueError('Invalid kernel backend')
    if importlib.util.find_spec('numpy') is None or (backend=='framework' and importlib.util.find_spec('agent_framework') is None):
        return dict(result,status='unavailable',reason='Install the agent extra with Python 3.12: python -m pip install -e ".[agent]"')
    try:
        from inside_the_game.system1.policy import SoftmaxActionPolicy
        match,event=kernel_inputs(snapshot,metadata,public,private)
        if not snapshot['frame'].get('in_play') or not event['player_id']:return dict(result,status='unavailable',reason='Active play and confirmed carrier required')
        if backend=='framework':
            from inside_the_game.system1.agent_workflow import run_decision_workflow
            output=run_decision_workflow(match,event,policy=SoftmaxActionPolicy.stub())
        else:
            from inside_the_game.system1.orchestrator import run_decision_tools
            output=run_decision_tools(match,event,policy=SoftmaxActionPolicy.stub())
        return dict(result,status='computed',weight_source='hand_set_stub',output=output)
    except Exception as exc:
        return dict(result,status='unavailable',reason=type(exc).__name__+': '+str(exc)[:300])
