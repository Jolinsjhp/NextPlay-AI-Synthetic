"""Turn an untrusted detection into an explicitly unconfirmed annotation draft."""
import copy
import re
from contracts.model import digest
from .geometry import point
from .project import CONFIRMATIONS, PLAYER, integer
from .storage import read_asset, asset_path, write_json


def import_proposal(data):
    if set(data) != {'video_id', 'proposal', 'mapping'}:
        raise ValueError('Expected video_id, proposal and human track mapping')
    asset = read_asset(data['video_id'])
    p, mapping = data['proposal'], data['mapping']
    if not isinstance(p, dict) or p.get('schema_version') != 'cv-proposal-1' or p.get('verification') != 'unconfirmed':
        raise ValueError('Expected an unconfirmed CV proposal')
    if p.get('source_sha256') != asset['sha256']:
        raise ValueError('Proposal must match the exact uploaded source video')
    if p.get('coordinate_space') != 'normalized_image':
        raise ValueError('Image-plane stand-ins cannot be used as pitch coordinates')
    hashes=p.get('model_hashes')
    if not isinstance(hashes,dict) or set(hashes)!={'player','ball','pitch'} or any(not isinstance(h,str) or not re.fullmatch('[a-f0-9]{64}',h) for h in hashes.values()):
        raise ValueError('Expected actual detector weight hashes')
    if not isinstance(mapping, dict) or len(mapping)>22 or any(not isinstance(v,str) or not PLAYER.fullmatch(v) for v in mapping.values()) or len(set(mapping.values()))!=len(mapping):
        raise ValueError('Map each selected track to a unique H01–H11 / A01–A11 identity')
    tracks=p.get('tracks')
    if not isinstance(tracks,list) or len(tracks)>40 or len({t['track_id'] for t in tracks})!=len(tracks):
        raise ValueError('Invalid detector tracks')
    by_id={t['track_id']:t for t in tracks}
    if not set(mapping)<=set(by_id):raise ValueError('Mapped track not in this frame')
    marks=[dict(player_id=pid,image=point(by_id[tid]['image'])) for tid,pid in mapping.items()]
    landmarks=[]
    if p.get('plane_mode')=='current':
        raw=p.get('landmarks',[])
        if not isinstance(raw,list) or len(raw)>40:raise ValueError('Invalid pitch landmarks')
        # The manual contract supports at most 16 landmarks. Keep a spread
        # through the original keypoint order; retain all raw points in storage.
        if len(raw)>16:raw=[raw[round(i*(len(raw)-1)/15)] for i in range(16)]
        landmarks=[dict(image=point(l['image']),pitch=point(l['pitch'],105,68)) for l in raw]
    ball=None if p.get('ball') is None else point(p['ball']['image'])
    frame=dict(video_ms=integer(p.get('video_ms'),0,119999),period=1,period_ms=0,score=[0,0],
               home_attacks='positive_x',actor_id=None,players=marks,ball=ball,landmarks=landmarks,
               confirmed={k:False for k in CONFIRMATIONS})
    pid=digest(dict(proposal=p,mapping=mapping))
    write_json(asset_path(data['video_id'])/('proposal-'+pid+'.json'),dict(proposal=copy.deepcopy(p),mapping=mapping))
    return dict(proposal_id=pid,frame=frame,verification='unconfirmed',
                warnings=['Review clock, score, direction, identity and ground-ball status; defaults are placeholders.',
                          'No player identity, possession or complete coverage was inferred. Confirmations remain unchecked.'])
