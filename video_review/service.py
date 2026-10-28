"""Versioned video intake HTTP boundary. B's synthetic service is left intact."""
import copy
import json
import os
import re
import time
from urllib.parse import urlsplit,parse_qs
from contracts.model import digest
from decision_analysis.agents import run,configuration
from decision_analysis.counterfactual import simulate
from decision_analysis.metrics import analysis_document
from .storage import ROOT,asset_path,read_asset,read_revision,upload,write_json,LOCK
from .project import confirm,VideoRepository,fact_bundle,integer
from .audit import human_metrics
from .proposals import import_proposal


def upload_enabled():
    public=bool(os.environ.get('NEXTPLAY_PUBLIC_ORIGIN') or os.environ.get('ITG_ALLOWED_HOSTS'))
    return not public or os.environ.get('NEXTPLAY_VIDEO_UPLOADS')=='1'


def handle_upload(handler):
    if urlsplit(handler.path).path!='/api/video-review/upload':return False
    if not handler.trusted() or not upload_enabled():handler.reply(403,{'error':'Video upload is disabled on this public demo; use the local review workspace.'});return True
    try:
        size=int(handler.headers.get('Content-Length','0'))
        source=handler.headers.get('X-NextPlay-Source','uploaded_video')
        timeout=handler.connection.gettimeout();handler.connection.settimeout(30)
        try:value=upload(handler.rfile,size,handler.headers.get('Content-Type',''),source)
        finally:handler.connection.settimeout(timeout)
        handler.reply(201,value)
    except (ValueError,TypeError):handler.reply(400,{'error':'Invalid upload: use a playable MP4/WebM under 64 MiB and a 2-minute clip. Storage limits also apply.'})
    except TimeoutError:handler.reply(408,{'error':'Video upload timed out.'})
    return True


def media(handler,asset_id):
    asset=read_asset(asset_id);path=asset_path(asset_id)/'media';size=asset['bytes'];start=0;end=size-1
    header=handler.headers.get('Range')
    if header:
        match=re.fullmatch(r'bytes=(\d*)-(\d*)',header)
        if not match or not any(match.groups()):raise ValueError('Invalid media range')
        left,right=match.groups()
        if left:
            start=int(left);end=min(size-1,int(right)) if right else size-1
        else:
            length=int(right);start=max(0,size-length)
        if start>end or start>=size:
            handler.send_response(416);handler.send_header('Content-Range','bytes */'+str(size));handler.end_headers();return
    handler.send_response(206 if header else 200)
    handler.send_header('Content-Type',asset['media_type']);handler.send_header('Content-Length',str(end-start+1))
    handler.send_header('Accept-Ranges','bytes');handler.send_header('Cache-Control','private, no-store')
    handler.send_header('X-Content-Type-Options','nosniff')
    if header:handler.send_header('Content-Range',f'bytes {start}-{end}/{size}')
    handler.end_headers()
    with path.open('rb') as stream:
        stream.seek(start);remaining=end-start+1
        while remaining:
            block=stream.read(min(65536,remaining))
            if not block:break
            handler.wfile.write(block);remaining-=len(block)


def handle_get(handler):
    route=urlsplit(handler.path)
    if not route.path.startswith('/api/video-review/'):return False
    if not handler.trusted():handler.reply(403,{'error':'Same-origin requests only'});return True
    if not upload_enabled():handler.reply(403,{'error':'Private video review is disabled on this public demo.'});return True
    try:
        if route.path.startswith('/api/video-review/media/'):media(handler,route.path.rsplit('/',1)[1])
        elif route.path=='/api/video-review/revision':
            q=parse_qs(route.query);record=read_revision(q['video_id'][0],q['revision_id'][0]);handler.reply(200,record)
        else:handler.reply(404,{'error':'Unknown video-review endpoint'})
    except FileNotFoundError:handler.reply(404,{'error':'Private video or revision not found'})
    except (KeyError,ValueError,TypeError):handler.reply(400,{'error':'Invalid video identity or media range'})
    return True


def selection(data,base_repo):
    expected={'video_id','revision_id','frame_index','question','mode','language','candidate_set_id'}
    if not isinstance(data,dict) or set(data)!=expected:raise ValueError('Expected versioned video selection')
    record=read_revision(data['video_id'],data['revision_id']);idx=integer(data['frame_index'],0,len(record['frames'])-1)
    return record,idx


def analyze(data,base_repo):
    record,index=selection(data,base_repo);facts=fact_bundle(record,index)
    trace=[dict(agent='evidence',execution='deterministic_tool',tool='prepare_facts',ok=True,video_ms=facts['video_ms'])]
    if not facts['quality']['ready']:
        return dict(schema_version='video-analysis-1',status='needs_confirmation',video_id=record['video_id'],revision_id=record['revision_id'],
            frame_index=index,facts=facts,analysis=None,pipeline_trace=trace,audit=dict(model_called=False,blocking_reasons=facts['quality']['blocking_reasons']))
    repo=VideoRepository(record,index,base_repo);request={**repo.request,'question':data['question'],'mode':data['mode'],'language':data['language']}
    if data['mode'] not in ('fan','analyst') or data['language'] not in ('en','zh') or not isinstance(data['question'],str) or not 0<len(data['question'])<=1200:
        raise ValueError('Invalid audience or question')
    public,private=repo.compare(request)
    source=dict(dataset=record['source_kind'],root='private_video',source_commit=repo.model['source_commit'],dataset_version=public['data_version'],
        model_id=repo.model['model_id'],snapshot_source='human_confirmed_video',match_excluded_from_fitting=True)
    document=analysis_document(request,public,private,repo.snapshot,repo.metadata,source,'video-frame-'+str(index))
    document['action_conditions']['provenance']='human_confirmed_video; calibrated coordinates; unknown velocities use neutral zeros'
    actor=next(p for p in repo.frame['players'] if p['player_id']==repo.frame['actor_id'])
    if actor['velocity'] is None:
        document['action_conditions'].update(speed_mps=None,speed_kmh=None,movement_heading_deg=None,movement_label='Unknown; model uses neutral zero velocity')
    for candidate in document['candidates']:
        if candidate.get('features'):candidate['features']['state_quality']=0
    document['model']['evaluation_mode']='unvalidated_video_transfer_Q2'
    document['assessment']['agent_available']=True
    # This bridge is not exported as a contract-1 synthetic match. Its seed is null.
    return dict(schema_version='video-analysis-1',status='computed',video_id=record['video_id'],revision_id=record['revision_id'],frame_index=index,
        facts=facts,analysis=document,metadata=repo.metadata,pipeline_trace=trace,
        audit=dict(model_called=False,structural_checks_passed=True,human_factual_accuracy=None,probability_claims_allowed=False,
                   note='Human-confirmed input, not independently verified ground truth.'))


def bound_repo(data,base_repo):
    record,index=selection(data,base_repo);repo=VideoRepository(record,index,base_repo)
    request={**repo.request,'question':data['question'],'mode':data['mode'],'language':data['language']}
    public,private=repo.compare(request)
    if data['candidate_set_id']!=public['candidate_set_id']:raise ValueError('Stale candidate set; recompute video analysis')
    return repo,request,public,private


def agents(data,base_repo,config,call=None):
    repo,request,public,private=bound_repo(data,base_repo)
    response=run(request,public['candidate_set_id'],config,repo,call=call)
    matching=next((a for a in reversed(repo.claim_audits) if response['explanation'] and a['text']==response['explanation']['text']),None)
    audit=matching['audit'] if matching else dict(ok=False,claims=0,cited_claims=0,citation_coverage=None,human_factual_accuracy=None)
    audit['rejection_reasons']=getattr(repo,'claim_rejections',[])[:6]
    claims=[] if not matching else matching['claims']
    explanation_id=audit.get('explanation_id')
    if explanation_id:
        record=dict(video_id=repo.record['video_id'],revision_id=repo.record['revision_id'],frame_index=repo.index,candidate_set_id=public['candidate_set_id'],
            explanation_id=explanation_id,claims=claims,text=response['explanation']['text'])
        write_json(asset_path(repo.record['video_id'])/('explanation-'+explanation_id+'.json'),record)
    return dict(schema_version='video-agents-1',video_id=repo.record['video_id'],revision_id=repo.record['revision_id'],frame_index=repo.index,
        candidate_set_id=public['candidate_set_id'],response=response,claims=claims,audit=audit,
        pipeline_trace=[dict(agent='evidence',execution='deterministic_tool',tool='prepare_facts',ok=True),
                        dict(agent='reviewer',execution='deterministic_rules',tool='claim_provenance_gate',ok=bool(matching))])


def feedback(data):
    required={'video_id','revision_id','explanation_id','claim_index','verdict','notes'}
    if set(data)!=required or data['verdict'] not in ('supported','unsupported','incorrect') or not isinstance(data['notes'],str) or len(data['notes'])>1000:
        raise ValueError('Invalid feedback')
    eid=data['explanation_id']
    if not isinstance(eid,str) or not re.fullmatch('[a-f0-9]{16}',eid):raise ValueError('Invalid explanation')
    folder=asset_path(data['video_id']);record=json.loads((folder/('explanation-'+eid+'.json')).read_text())
    if record['revision_id']!=data['revision_id']:raise ValueError('Feedback revision mismatch')
    integer(data['claim_index'],0,len(record['claims'])-1)
    # One current label per claim; edits replace the label, never the underlying explanation.
    with LOCK:
        file=folder/('feedback-'+eid+'.json');labels=json.loads(file.read_text()) if file.exists() else []
        labels=[x for x in labels if x['claim_index']!=data['claim_index']]+[copy.deepcopy(data)]
        write_json(file,labels)
    return dict(labels=labels,metrics=human_metrics(labels))


def handle_post(handler,route,data,base_repo,config=None):
    if not route.startswith('/api/video-review/'):return False
    try:
        if not upload_enabled():handler.reply(403,{'error':'Private video review is disabled on the public judging demo.'});return True
        if route=='/api/video-review/import-proposal':handler.reply(200,import_proposal(data))
        elif route=='/api/video-review/confirm':
            if set(data) not in ({'annotation'},{'annotation','proposal_id'}):raise ValueError('Invalid confirmation')
            proposal_id=data.get('proposal_id')
            if proposal_id is not None:
                if not isinstance(proposal_id,str) or not re.fullmatch('[a-f0-9]{16}',proposal_id):raise ValueError('Invalid proposal ID')
                folder=asset_path(data['annotation']['video_id'])
                proposal=json.loads((folder/('proposal-'+proposal_id+'.json')).read_text())
                if not any(f['video_ms']==proposal['proposal']['video_ms'] for f in data['annotation']['frames']):raise ValueError('Proposal timestamp absent from annotation')
            record=confirm(data['annotation']['video_id'],data['annotation'])
            if proposal_id is not None:
                write_json(folder/('proposal-confirmation-'+record['revision_id']+'-'+proposal_id+'.json'),dict(proposal_id=proposal_id,revision_id=record['revision_id'],relationship='human reviewed and potentially corrected; raw proposal is not ground truth'))
            handler.reply(200,record)
        elif route=='/api/video-review/analyze':handler.reply(200,analyze(data,base_repo))
        elif route=='/api/video-review/agents':handler.reply(200,agents(data,base_repo,config or {}))
        elif route=='/api/video-review/counterfactual':
            if set(data)!={'selection','action_id'}:raise ValueError('Invalid counterfactual request')
            repo,request,public,private=bound_repo(data['selection'],base_repo)
            handler.reply(200,simulate(request,public,private,repo.snapshot,repo.metadata,data['action_id'],public['candidate_set_id']))
        elif route=='/api/video-review/feedback':handler.reply(200,feedback(data))
        else:handler.reply(404,{'error':'Unknown video-review endpoint'})
    except FileNotFoundError:handler.reply(404,{'error':'Video, immutable annotation revision or explanation not found'})
    except (ValueError,KeyError,TypeError,IndexError) as e:handler.reply(400,{'error':str(e) if isinstance(e,ValueError) else 'Invalid video-review request'})
    return True
