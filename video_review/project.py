"""Immutable manual observations and a private compatibility bridge into B Q2.

The video contract is separate from synthetic contract-1. No fake generation seed.
"""
import copy
import math
import re
from contracts import make_snapshot, candidate_set_id, check_exchange
from contracts.model import digest
from decision_analysis.comparison import compare_actions
from decision_analysis.input_adapter import NEUTRAL_PROFILE
from video_review.geometry import calibrate, project, point, number
from video_review.storage import read_asset, save_revision, read_revision

SCHEMA = 'video-review-1'
PLAYER = re.compile(r'^[HA](?:0[1-9]|10|11)$')
CONFIRMATIONS = ('calibration_reviewed','identities_reviewed','positions_reviewed','coverage_complete','ball_on_ground','in_play')
LIMITATIONS = [
 'Manual video annotations, not automatic tracking or verified ground truth.',
 'Pitch coordinates use a ground-plane homography. Fit residual is not measured accuracy.',
 'Unknown velocity falls back to zero in B; it does not mean the player is stationary.',
 'Q2/xT transfers from the existing synthetic-source model; real-video performance is unvalidated.',
 'Camera must remain fixed within each annotated moment; annotate fresh landmarks after camera changes.',
 'Opponent reactions and counterfactual futures are hypotheses, not observations.']


def integer(value, low, high):
    if type(value) is not int or not low <= value <= high:raise ValueError('Invalid integer field')
    return value


def normalize(asset, draft):
    if not isinstance(draft,dict) or set(draft)!={'video_id','video_duration_ms','roster','frames','rights_confirmed'}:
        raise ValueError('Expected the versioned video annotation fields')
    if draft['video_id']!=asset['video_id'] or draft['rights_confirmed'] is not True:
        raise ValueError('Confirm authorization to use this video')
    duration=integer(draft['video_duration_ms'],100,120000)
    roster=draft['roster']
    if not isinstance(roster,list) or not 4<=len(roster)<=22:raise ValueError('Confirm 4–22 active players, including two goalkeepers')
    ids=set();players=[]
    for p in roster:
        if not isinstance(p,dict) or set(p)!={'player_id','team_id','jersey_number','name','position'}:
            raise ValueError('Invalid roster fields')
        pid=p['player_id'];team=p['team_id']
        if (not isinstance(pid,str) or not PLAYER.fullmatch(pid) or pid in ids
            or team not in ('HOME','AWAY') or pid[0]!=team[0] or p['position'] not in ('GK','OUTFIELD')
            or not isinstance(p['name'],str) or not 1<=len(p['name'].strip())<=64):raise ValueError('Invalid player identity')
        integer(p['jersey_number'],1,99);ids.add(pid);players.append(copy.deepcopy(p))
    for team in ('HOME','AWAY'):
        group=[p for p in players if p['team_id']==team]
        if not 2<=len(group)<=11 or sum(p['position']=='GK' for p in group)!=1:
            raise ValueError('Each team needs one confirmed goalkeeper and at least one outfield player')
        if len({p['jersey_number'] for p in group})!=len(group):raise ValueError('Duplicate jersey numbers within a team')
    frames=draft['frames']
    if not isinstance(frames,list) or not 1<=len(frames)<=60:raise ValueError('Annotate 1–60 keyframes')
    clean=[];times=set()
    for frame in frames:
        required={'video_ms','period','period_ms','score','home_attacks','actor_id','ball','players','landmarks','confirmed'}
        if not isinstance(frame,dict) or set(frame)!=required:raise ValueError('Invalid keyframe fields')
        video_ms=integer(frame['video_ms'],0,duration-1)
        if video_ms in times:raise ValueError('Duplicate video timestamp')
        times.add(video_ms);integer(frame['period'],1,2);integer(frame['period_ms'],0,3599999)
        if not isinstance(frame['score'],list) or len(frame['score'])!=2:raise ValueError('Invalid score')
        for v in frame['score']:integer(v,0,50)
        if frame['home_attacks'] not in ('positive_x','negative_x'):raise ValueError('Confirm attacking direction')
        if frame['actor_id'] is not None and frame['actor_id'] not in ids:raise ValueError('Unknown ball owner')
        if frame['ball'] is not None:point(frame['ball'])
        confirmed=frame['confirmed']
        if not isinstance(confirmed,dict) or set(confirmed)!=set(CONFIRMATIONS) or any(type(v) is not bool for v in confirmed.values()):
            raise ValueError('Explicit human confirmations required')
        observations=frame['players']
        if not isinstance(observations,list) or len(observations)>22:raise ValueError('Invalid observations')
        seen=set()
        for p in observations:
            if not isinstance(p,dict) or set(p)!={'player_id','image'} or p['player_id'] not in ids or p['player_id'] in seen:
                raise ValueError('Unknown or duplicate player annotation')
            seen.add(p['player_id']);point(p['image'])
        landmarks=frame['landmarks']
        if not isinstance(landmarks,list) or len(landmarks)>16:raise ValueError('Invalid calibration')
        # Store incomplete drafts too, but refuse malformed/out-of-bounds landmarks.
        for p in landmarks:
            if not isinstance(p,dict) or set(p)!={'image','pitch'}:raise ValueError('Invalid landmark')
            point(p['image']);point(p['pitch'],105,68)
        clean.append(copy.deepcopy(frame))
    clean.sort(key=lambda f:f['video_ms'])
    for old,new in zip(clean,clean[1:]):
        if new['period']<old['period'] or new['period']==old['period'] and new['period_ms']<=old['period_ms']:
            raise ValueError('Video and match clocks must advance together; split replays/camera cuts into separate reviews')
        if new['period']==old['period'] and abs((new['period_ms']-old['period_ms'])-(new['video_ms']-old['video_ms']))>500:
            raise ValueError('Clock alignment differs by over 500 ms; split edited or slow-motion footage')
        if any(b<a for a,b in zip(old['score'],new['score'])):raise ValueError('Scores cannot decrease within a continuous clip')
        if new['period']==old['period'] and new['home_attacks']!=old['home_attacks']:raise ValueError('Attacking direction changed within a period')
    return dict(video_id=asset['video_id'],video_duration_ms=duration,roster=sorted(players,key=lambda p:p['player_id']),
                frames=clean,rights_confirmed=True)


def reconstruct(draft):
    output=[];roster={p['player_id']:p for p in draft['roster']}
    for index, f in enumerate(draft['frames']):
        errors=[];calibration=None;positions=[];ball=None
        try:calibration=calibrate(f['landmarks'])
        except ValueError as e:errors.append(str(e))
        if calibration:
            try:
                positions=[dict(player_id=p['player_id'],image=p['image'],pitch=project(calibration['matrix'],p['image']),velocity=None) for p in f['players']]
                ball=project(calibration['matrix'],f['ball']) if f['ball'] is not None else None
            except ValueError as e:errors.append(str(e))
        if any(sum(p['team_id']==team for p in roster.values())!=11 for team in ('HOME','AWAY')):
            errors.append('This first scoring adapter requires a fully observed 11-versus-11 scene; other formats remain annotation-only')
        missing=sorted(set(roster)-{p['player_id'] for p in f['players']})
        if missing:errors.append('Unobserved active players: '+', '.join(missing))
        for key,value in f['confirmed'].items():
            if not value:errors.append('Human confirmation required: '+key)
        if f['actor_id'] is None:errors.append('Ball owner is unknown')
        if ball is None:errors.append('Ground-ball position is unknown')
        if ball and f['actor_id']:
            actor=next((p for p in positions if p['player_id']==f['actor_id']),None)
            if actor and math.dist(actor['pitch'],ball)>2:errors.append('Ball is over 2 m from the confirmed owner; correct the moment or owner')
        if output and output[-1]['quality']['ready'] and 0< f['video_ms']-output[-1]['video_ms']<=2000 and f['period']==output[-1]['period']:
            previous={p['player_id']:p for p in output[-1]['players']}
            dt=(f['video_ms']-output[-1]['video_ms'])/1000
            for p in positions:
                old=previous.get(p['player_id'])
                if old:
                    velocity=[(p['pitch'][j]-old['pitch'][j])/dt for j in (0,1)]
                    if math.hypot(*velocity)>12:errors.append('Implausible causal velocity: '+p['player_id'])
                    else:p['velocity']=[round(v,4) for v in velocity]
        output.append(dict(frame_index=index,video_ms=f['video_ms'],period=f['period'],period_ms=f['period_ms'],score=f['score'],
            home_attacks=f['home_attacks'],actor_id=f['actor_id'],ball=ball,players=positions,calibration=calibration,
            confirmations=f['confirmed'],quality=dict(ready=not errors,blocking_reasons=errors,missing_player_ids=missing)))
    return output


def confirm(asset_id, draft, root=None):
    asset=read_asset(asset_id,root);clean=normalize(asset,draft)
    revision_id=digest(dict(schema_version=SCHEMA,asset_sha256=asset['sha256'],annotation=clean))
    record=dict(schema_version=SCHEMA,video_id=asset_id,revision_id=revision_id,asset_sha256=asset['sha256'],
        source_kind=asset['source_kind'],annotation=clean,frames=reconstruct(clean),limitations=LIMITATIONS)
    return save_revision(asset_id,revision_id,record,root)


def fact_bundle(record,index):
    f=record['frames'][index];facts=[]
    source=dict(video_id=record['video_id'],asset_sha256=record['asset_sha256'],video_ms=f['video_ms'],revision_id=record['revision_id'])
    def add(key,kind,value,unit=None,player_id=None):
        facts.append(dict(fact_id=key,kind=kind,value=value,unit=unit,player_id=player_id,source=copy.deepcopy(source),
                          verification=('human_confirmed' if f['quality']['ready'] else 'unconfirmed') if kind=='observed' else 'derived_unvalidated'))
    add('video-clock','observed',f['video_ms'],'ms');add('period-clock','observed',f['period_ms'],'ms')
    add('score-home','observed',f['score'][0],'goals');add('score-away','observed',f['score'][1],'goals')
    add('actor','observed',f['actor_id']);add('direction','observed',f['home_attacks'])
    roster={p['player_id']:p for p in record['annotation']['roster']}
    for p in f['players']:
        add('jersey-'+p['player_id'],'observed',roster[p['player_id']]['jersey_number'],'shirt_number',p['player_id'])
        add('image-'+p['player_id'],'observed',p['image'],'normalized_image',p['player_id'])
        if f['calibration']:
            add('position-'+p['player_id'],'derived',p['pitch'],'m',p['player_id'])
            add('velocity-'+p['player_id'],'derived' if p['velocity'] is not None else 'assumed',p['velocity'],'m/s',p['player_id'])
    if f['ball'] is not None:add('ball-position','derived',f['ball'],'m')
    add('calibration','derived',f['calibration']);add('quality-gate','derived',f['quality'])
    return dict(schema_version='video-facts-1',video_id=record['video_id'],revision_id=record['revision_id'],frame_index=index,
        video_ms=f['video_ms'],facts=facts,quality=f['quality'],limitations=LIMITATIONS)


class VideoRepository:
    """One immutable revision/moment per instance. Not registered as a synthetic league."""
    def __init__(self, record, frame_index, base_repo):
        self.record=record;self.index=integer(frame_index,0,len(record['frames'])-1);self.rollout_facts={}
        self.frame=record['frames'][self.index];self.facts=fact_bundle(record,self.index);self.claim_audits=[]
        if not self.frame['quality']['ready']:raise ValueError('Moment requires human confirmation before scoring')
        # Reuse a frozen source model, explicitly as unvalidated transfer to video.
        self.model=copy.deepcopy(base_repo.model_for(next(iter(base_repo.matches))))
        f=self.frame;period=f['period'];start=(period-1)*3600000;t_ms=start+f['period_ms']
        metadata=dict(schema_version='video-bridge-1',match_id='VID-'+record['video_id'],synthetic=record['source_kind']=='synthetic_demo',seed=None,
            generator='manual-video-adapter-1',video_revision=record['revision_id'],source_kind=record['source_kind'],
            duration_ms=7200000,tracking_hz=1000,pitch=dict(length_m=105,width_m=68),
            periods=[dict(period=1,start_ms=0,duration_ms=3600000,home_attacks=f['home_attacks'] if period==1 else ('negative_x' if f['home_attacks']=='positive_x' else 'positive_x')),
                     dict(period=2,start_ms=3600000,duration_ms=3600000,home_attacks=f['home_attacks'] if period==2 else ('negative_x' if f['home_attacks']=='positive_x' else 'positive_x'))],
            teams=[dict(team_id='HOME',name='Home'),dict(team_id='AWAY',name='Away')],
            players=[dict(p,starter=True,nationality=None,position_detail=p['position']) for p in record['annotation']['roster']],
            limitations=LIMITATIONS+['One-hour internal period offsets are an adapter clock, not observed half durations. tracking_hz=1000 is a millisecond ID grid, not video frame rate.'])
        tracking=dict(frame_id=t_ms,t_ms=t_ms,period=period,period_ms=f['period_ms'],in_play=True,phase='manual_snapshot',
            action_id=None,possession_team_id=next(p['team_id'] for p in metadata['players'] if p['player_id']==f['actor_id']),
            ball_owner_id=f['actor_id'],score=f['score'],players=[[p['player_id'],*p['pitch'],*(p['velocity'] or [0.,0.])] for p in f['players']],
            ball=[*f['ball'],0.,0.,0.,0.])
        self.snapshot=make_snapshot(metadata,tracking);self.metadata=metadata
        self.request=dict(match_id=metadata['match_id'],snapshot_id=self.snapshot['snapshot_id'],t_ms=t_ms,actor_id=f['actor_id'],
            question='Compare the current options and risks',mode='fan',language='en',profile=copy.deepcopy(NEUTRAL_PROFILE))

    def resolve(self,request):
        for key in ('match_id','snapshot_id','t_ms','actor_id'):
            if request.get(key)!=self.request[key]:raise ValueError('Stale video moment')
        return self.snapshot,self.metadata,None

    def bundle(self,request):
        self.resolve(request)
        return dict(source_profile=dict(status='unavailable',observation=None,used_in_probability=False),facts=self.facts)

    def compare(self,request):
        self.resolve(request)
        public,private=compare_actions(request,self.snapshot,self.metadata,self.model)
        # Bind provenance, annotation revision and numeric model diagnostics into CID.
        for fact in self.facts['facts']:
            public['evidence'].append(dict(evidence_id=fact['fact_id'],kind='observed' if fact['kind']=='observed' else 'assumed' if fact['kind']=='assumed' else 'computed',
                source='video:'+self.record['video_id']+'@'+str(self.frame['video_ms'])+'ms revision:'+self.record['revision_id'],
                value=json_text(fact['value'])+'; '+fact['kind']+'; '+fact['verification']))
        public['evidence'].append(dict(evidence_id='video-model-binding',kind='assumed',source='video_review.project',
            value='Transferred synthetic-source Q2/xT model '+self.model['model_id']+' hash '+digest(self.model)+'; unvalidated on this video.'))
        for c in public['candidates']:
            c['evidence_ids'] += ['video-clock','actor','direction','ball-position','quality-gate','video-model-binding']
        public['candidate_set_id']=candidate_set_id(self.snapshot,request['profile'],public['candidate_set_id'].split(':')[0],public['candidates'],public['evidence'])
        private['candidate_set_id']=public['candidate_set_id']
        public['limitations']+=LIMITATIONS
        check_exchange(request,public,self.snapshot,self.metadata)
        return public,private

    def validate_note(self,note,public,private):
        from .audit import audit_note
        try:audit=audit_note(note,public,self.claim_context(public,private),[p['player_id'] for p in self.metadata['players']],self.frame['video_ms'])
        except ValueError as e:
            if not hasattr(self,'claim_rejections'):self.claim_rejections=[]
            self.claim_rejections.append(str(e)[:180])
            raise
        self.claim_audits.append(dict(audit=audit,claims=copy.deepcopy(note['claims']),text=note['text']))
        return note

    def claim_context(self,public,private):
        from .audit import observation_statements
        registry={f['fact_id']:f for f in self.facts['facts']}
        registry.update(self.rollout_facts)
        for c in public['candidates']:
            registry['rank-'+c['action_id']]=dict(fact_id='rank-'+c['action_id'],kind='model',value=c['rank'],unit='rank',action_id=c['action_id'],source=dict(model_id=self.model['model_id']))
        # Canonical evidence text is valid to cite, but NOT a numerical provenance record.
        return dict(facts=list(registry.values()),evidence=public['evidence'],
                    observation_statements=observation_statements(registry.values()),numeric_probability_claims_allowed=False)

    def register_rollout(self,action_id,result):
        key='hypothesis-'+action_id
        fact=dict(fact_id=key,kind='hypothesis',action_id=action_id,
                  value=dict(outcomes=[s['outcome'] for s in result.get('scenarios',[])]),unit=None,
                  verification='hypothetical_unvalidated',source=dict(candidate_set_id=result['candidate_set_id'],video_ms=self.frame['video_ms']))
        self.rollout_facts[key]=fact
        return copy.deepcopy(fact)


def json_text(value):
    import json
    return json.dumps(value,ensure_ascii=False,sort_keys=True,allow_nan=False)
