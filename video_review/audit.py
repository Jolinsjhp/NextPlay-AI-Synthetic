"""Hard provenance checks plus explicit, human-labelled evaluation. Not a truth oracle."""
import math
import re
from contracts.model import digest
from decision_analysis.claim_safety import check_language, check_estimate_scope

CLAIM_SCHEMA = dict(type='object',properties={
    'text':dict(type='string'), 'cited_evidence_ids':dict(type='array',items=dict(type='string')), 'approved':dict(type='boolean'),
    'claims':dict(type='array',items=dict(type='object',properties={
        'text':dict(type='string'), 'evidence_ids':dict(type='array',items=dict(type='string')),
        'fact_ids':dict(type='array',items=dict(type='string')), 'player_ids':dict(type='array',items=dict(type='string')),
        'action_id':dict(anyOf=[dict(type='string'),dict(type='null')]),
        'certainty':dict(type='string',enum=['observation','estimate','hypothesis']),
        'quantities':dict(type='array',items=dict(type='object',properties={
            'fact_id':dict(type='string'),'value':dict(type='number'),'unit':dict(type='string')},
            required=['fact_id','value','unit'],additionalProperties=False))},
        required=['text','evidence_ids','fact_ids','player_ids','action_id','certainty','quantities'],additionalProperties=False))},
    required=['text','cited_evidence_ids','approved','claims'],additionalProperties=False)

POLICY = '''This input is manually annotated video (or an explicitly synthetic walkthrough), not automatic tracking.
The evidence preparer has built claim_context. Use only these facts and B's comparison. Never infer unseen players or body orientation.
Return the required claims array; text MUST equal the claim texts joined with one space.
Every claim needs evidence_ids. Every numeric value in prose needs a quantities entry with an exact fact_id/value/unit.
Never emit percentages or success probabilities. Q2 ranks and xT are transferred, unvalidated model estimates.
Only use listed player IDs, action IDs, and observed time/score. Unknown remains unknown.
certainty=observation is permitted only for observed facts; calibrated coordinates are estimates and future scenarios are hypotheses.
Do not infer a pass's actual result. A reviewer approves only if draft claims are supported and do not exaggerate.'''
POLICY += '''
Every estimate/hypothesis claim must explicitly say it is from a model, simulation or assumption AND state uncertainty (may/could/unvalidated).
Never say likely/probably/high risk/low risk/guaranteed/optimal or their Chinese equivalents: no calibrated likelihood or risk thresholds exist.
Use a specific action_id and its route evidence for action conclusions. A generic model-context citation does not support an action-specific claim.
Include player_ids for every player-linked fact. Never substitute a fact about another player or action.
Do not assert footedness, body orientation, intent or actual outcomes. Omit unsupported conclusions rather than filling gaps.'''
POLICY += '\nObservation claims must quote exactly one server-supplied observation_statement and cite its fact_id. Do not paraphrase observations.'
POLICY += '\nA hypothesis claim requires simulate_action for that action and the returned hypothesis_fact.fact_id; do not claim a simulation was performed without that tool result.'


def observation_statements(facts):
    """A small fixed vocabulary, so observation prose cannot invent extra facts."""
    statements=[]
    for f in facts:
        if f['kind']!='observed' or f.get('verification')!='human_confirmed':continue
        key,value=f['fact_id'],f['value'];pid=f.get('player_id')
        texts=[]
        if key in ('score-home','score-away'):
            side='home' if key=='score-home' else 'away';zh='主队' if side=='home' else '客队'
            texts=[f'The human-confirmed {side} score is {value}.',f'人工确认的{zh}比分为 {value}。']
        elif key=='actor' and value:
            texts=[f'The human-confirmed ball owner is {value}.',f'人工确认的持球者为 {value}。']
        elif key=='video-clock':
            texts=[f'The confirmed video timestamp is {value} ms.',f'确认的视频时间戳为 {value} ms。']
        elif key.startswith('image-') and pid:
            texts=[f'{pid} was manually marked in this frame.',f'{pid} 的位置已在该帧人工标注。']
        for text in texts:statements.append(dict(fact_id=key,text=text))
    return statements


def audit_note(note, public, claim_context, active_ids, video_ms):
    if not isinstance(note,dict) or set(note)!={'text','cited_evidence_ids','approved','claims'}:raise ValueError('Structured claims required')
    if type(note['approved']) is not bool:raise ValueError('Invalid approval flag')
    claims=note['claims']
    if not isinstance(claims,list) or not 1<=len(claims)<=10:raise ValueError('Expected 1–10 cited claims')
    allowed_evidence={e['evidence_id'] for e in public['evidence']};actions={a['action_id']:a for a in public['candidates']}
    shared=set.intersection(*(set(a['evidence_ids']) for a in actions.values())) if actions else set()
    facts={f['fact_id']:f for f in claim_context['facts']};covered=0
    for claim in claims:
        if not isinstance(claim,dict) or set(claim)!={'text','evidence_ids','fact_ids','player_ids','action_id','certainty','quantities'}:raise ValueError('Invalid claim fields')
        text=claim['text']
        if not isinstance(text,str) or not 1<=len(text)<=1200 or re.search(r'[%％]',text):raise ValueError('Invalid prose or forbidden probability percentage')
        check_language(text)
        for field,allowed in (('evidence_ids',allowed_evidence),('fact_ids',set(facts)),('player_ids',set(active_ids))):
            if not isinstance(claim[field],list) or any(not isinstance(x,str) for x in claim[field]) or not set(claim[field])<=allowed:
                raise ValueError('Unregistered claim reference: '+field)
        if not claim['evidence_ids']:raise ValueError('Every claim needs evidence')
        covered+=1
        if claim['action_id'] is not None and claim['action_id'] not in actions:raise ValueError('Action outside bound candidate set')
        if claim['action_id'] is not None:
            action=actions[claim['action_id']]
            if not action['eligible']:raise ValueError('unsupported_action_conclusion')
            specific=set(action['evidence_ids'])-shared-set(facts)-{'model-context','video-model-binding'}
            if not specific.intersection(claim['evidence_ids']):raise ValueError('missing_action_specific_evidence')
        if claim['certainty'] not in ('observation','estimate','hypothesis'):raise ValueError('Invalid certainty')
        for fid in claim['fact_ids']:
            f=facts[fid]
            if f.get('verification')=='unconfirmed':raise ValueError('unconfirmed_fact')
            if f.get('player_id') and f['player_id'] not in claim['player_ids']:raise ValueError('fact_player_mismatch')
            if f.get('action_id') and f['action_id']!=claim['action_id']:raise ValueError('fact_action_mismatch')
            if f.get('source',{}).get('video_ms',video_ms)>video_ms:raise ValueError('Future observation leakage')
            if claim['certainty']=='observation' and f['kind']!='observed':raise ValueError('Model output or derived coordinates labelled observed')
        if claim['certainty']=='observation' and not claim['fact_ids']:raise ValueError('Observed claims need observed facts')
        if claim['certainty']=='observation':
            permitted={(s['fact_id'],s['text']) for s in observation_statements(facts.values())}
            if len(claim['fact_ids'])!=1 or (claim['fact_ids'][0],text) not in permitted:
                raise ValueError('observation_must_use_verified_statement')
        if claim['certainty']!='observation':check_estimate_scope(text)
        if claim['certainty']=='hypothesis':
            supporting=[facts[fid] for fid in claim['fact_ids'] if facts[fid]['kind']=='hypothesis']
            if not supporting or claim['action_id'] is None:raise ValueError('hypothesis_requires_actual_bound_rollout')
            if any(f['source'].get('candidate_set_id')!=public['candidate_set_id'] for f in supporting):raise ValueError('stale_hypothesis')
        mentioned_actions=set(re.findall(r'\b(?:pass|carry|shot|hold):[A-Za-z0-9_-]+',text))
        if mentioned_actions and mentioned_actions!={claim['action_id']}:raise ValueError('action_in_prose_mismatch')
        if re.search(r'\b(?:pass|carry|shot|intercept|defender|receiver)\b|传球|带球|射门|拦截|防守者|接球者',text,re.I) and claim['certainty']!='observation' and claim['action_id'] is None:
            raise ValueError('action_conclusion_needs_bound_action')
        if re.search(r'\b[HA]\d{2}\b',text) and not set(re.findall(r'\b[HA]\d{2}\b',text))<=set(claim['player_ids']):raise ValueError('Unlisted player in prose')
        if not isinstance(claim['quantities'],list) or len(claim['quantities'])>10:raise ValueError('Invalid quantities')
        numbers=[]
        for quantity in claim['quantities']:
            if not isinstance(quantity,dict) or set(quantity)!={'fact_id','value','unit'}:raise ValueError('Invalid quantity')
            fid=quantity['fact_id'];fact=facts.get(fid);value=quantity['value']
            if (not fact or fid not in claim['fact_ids'] or type(value) not in (int,float) or not math.isfinite(value)
                or type(fact['value']) not in (int,float) or value!=fact['value'] or quantity['unit']!=fact['unit']):
                raise ValueError('Number has no exact model/observation source')
            numbers.append(value)
        # Player IDs are entities, not numerical claims. Free textual jersey numbers must have a fact.
        stripped=re.sub(r'\b[HA]\d{2}\b','',text)
        for token in re.findall(r'(?<![\w])[-+]?\d+(?:\.\d+)?',stripped):
            if float(token) not in numbers:raise ValueError('Unsupported number in prose')
    combined=' '.join(c['text'] for c in claims)
    if note['text']!=combined:raise ValueError('Free prose must not bypass claim-level auditing')
    cited=note['cited_evidence_ids']
    if not isinstance(cited,list) or any(not isinstance(x,str) for x in cited) or set(cited)!={x for c in claims for x in c['evidence_ids']}:
        raise ValueError('Top-level citations must match claim citations')
    return dict(ok=True,claims=len(claims),cited_claims=covered,citation_coverage=covered/len(claims),
                human_factual_accuracy=None,semantic_support='requires model/human review',
                explanation_id=digest(dict(candidate_set_id=public['candidate_set_id'],text=combined,claims=claims)))


def human_metrics(labels):
    reviewed=[x for x in labels if x['verdict'] in ('supported','unsupported','incorrect')]
    return dict(reviewed_claims=len(reviewed),unsupported_or_incorrect_rate=(sum(x['verdict']!='supported' for x in reviewed)/len(reviewed) if reviewed else None),
                note='Human-labelled claims only; citation coverage is not a hallucination-rate estimate.')
