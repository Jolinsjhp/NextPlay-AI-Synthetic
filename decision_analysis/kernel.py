"""Decision-time category tendencies, independent of Q2 ranking and evidence."""
import math
from inside_the_game.features.extract import FeatureVector
from inside_the_game.features.from_cv import pressure_from_distances
from inside_the_game.system1.policy import SoftmaxActionPolicy


def tendency(snapshot, metadata):
    frame=snapshot['frame'];owner=frame.get('ball_owner_id')
    players={p[0]:p for p in frame['players']}
    teams={p['player_id']:p['team_id'] for p in metadata['players']}
    if not frame.get('in_play') or owner not in players or owner not in teams:
        return dict(status='unavailable',reason='Active play with an identified carrier is required')
    team=teams[owner];direction=snapshot['attacking_direction'].get(team)
    if direction not in ('positive_x','negative_x'):
        return dict(status='unavailable',reason='Attacking direction is unknown')
    x,y=frame['ball'][:2]
    if not (math.isfinite(x) and math.isfinite(y) and 0<=x<=105 and 0<=y<=68):
        return dict(status='unavailable',reason='Calibrated pitch coordinates are required')
    if direction=='negative_x':x,y=105-x,68-y
    actor=players[owner]
    opponents=[math.dist(actor[1:3],p[1:3]) for p in players.values() if teams.get(p[0]) not in (None,team)]
    if not opponents:return dict(status='unavailable',reason='Opponent coverage is unavailable')
    # Continuous proximity proxy; not a measured tackle probability.
    pressure=pressure_from_distances(opponents)
    elapsed=int(snapshot['t_ms'])//60000
    home,away=frame['score'];diff=home-away if team=='HOME' else away-home
    features=FeatureVector(x/105,y/68,1-abs(y/68-.5)*2,pressure,min(1.,max(0.,elapsed/90)),max(-1.,min(1.,diff/5)))
    policy=SoftmaxActionPolicy.stub()
    return dict(status='computed',schema_version='action-tendency-1',snapshot_id=snapshot['snapshot_id'],
        data_version=snapshot['data_version'],actor_id=owner,weight_source='hand_set_stub',
        distribution=policy.predict_features(features).as_dict(),
        features=dict(zip(('ball_x','ball_y','centrality','pressure','minute','goal_diff'),features.as_tuple())),
        affects_candidate_ranks=False,
        meaning='Four-class softmax tendency; not action success, goal probability or candidate value.',
        assumptions=['Hand-set upstream baseline; no inherited fitted weights loaded.',
                     'Pressure is a distance proxy; time and score come only from this snapshot.',
                     'No legality mask: a category share does not establish an eligible specific action.',
                     'Tendencies cannot override Q2 candidates, scores or evidence.'])
