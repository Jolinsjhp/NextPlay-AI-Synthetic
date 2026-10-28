import copy
import io
import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch
from video_review.geometry import calibrate, project
from video_review.storage import upload,read_asset,read_revision
from video_review.project import confirm,VideoRepository,fact_bundle
from video_review.audit import audit_note,human_metrics
from video_review import service
from decision_analysis.agents import run

FIX=Path(__file__).parent/'fixtures/contracts'
class Base:
    matches={'fixture-source':{}}
    def model_for(self,match):return dict(model_id='fixture-video-transfer',source_commit='source-only',xt=[.02]*96,fitting_matches=[],temperature=.05)

def draft(asset):
    snapshot=json.loads((FIX/'case-a/snapshot.json').read_text());metadata=json.loads((FIX/'match.json').read_text())['metadata']
    active={p[0] for p in snapshot['frame']['players']}
    roster=[dict(player_id=p['player_id'],team_id=p['team_id'],jersey_number=p['jersey_number'],name=p['name'],position='GK' if p['position']=='GK' else 'OUTFIELD') for p in metadata['players'] if p['player_id'] in active]
    frame=dict(video_ms=1000,period=1,period_ms=30000,score=[0,0],home_attacks='positive_x',actor_id=snapshot['frame']['ball_owner_id'],
        ball=[snapshot['frame']['ball'][0]/105,snapshot['frame']['ball'][1]/68],
        players=[dict(player_id=p[0],image=[p[1]/105,p[2]/68]) for p in snapshot['frame']['players']],
        landmarks=[dict(image=p,pitch=q) for p,q in [([0,0],[0,0]),([1,0],[105,0]),([1,1],[105,68]),([0,1],[0,68])]],
        confirmed={k:True for k in ('calibration_reviewed','identities_reviewed','positions_reviewed','coverage_complete','ball_on_ground','in_play')})
    return dict(video_id=asset['video_id'],video_duration_ms=5000,roster=roster,frames=[frame],rights_confirmed=True)

class VideoTests(unittest.TestCase):
    def setUp(self):
        self.temp=tempfile.TemporaryDirectory();self.root=Path(self.temp.name)
        self.asset=upload(io.BytesIO(b'\x1aE\xdf\xa3'+b'0'*100),104,'video/webm',root=self.root)
        self.draft=draft(self.asset)
    def tearDown(self):self.temp.cleanup()
    def record(self,d=None):return confirm(self.asset['video_id'],d or self.draft,self.root)
    def repo(self):return VideoRepository(self.record(),0,Base())
    def test_homography_and_degenerate_layout(self):
        fit=calibrate(self.draft['frames'][0]['landmarks']);self.assertAlmostEqual(project(fit['matrix'],[.5,.5])[0],52.5)
        self.assertIsNone(fit['measured_accuracy_m'])
        for p in self.draft['frames'][0]['landmarks']:p['image'][1]=0
        with self.assertRaises(ValueError):calibrate(self.draft['frames'][0]['landmarks'])
    def test_upload_limits_signature_truncation_and_path_traversal(self):
        for data,size,kind in [(b'bad'*40,120,'video/webm'),(b'\x1aE\xdf\xa3',104,'video/webm'),(b'x'*100,100,'application/json')]:
            with self.assertRaises(ValueError):upload(io.BytesIO(data),size,kind,root=self.root)
        with self.assertRaises(ValueError):read_asset('../../private',self.root)
    def test_immutable_revision_binds_video_annotation_and_real_provenance(self):
        a=self.record();b=self.record();self.assertEqual(a,b)
        self.assertEqual(read_revision(self.asset['video_id'],a['revision_id'],self.root),a)
        self.draft['frames'][0]['score']=[0,1];c=self.record();self.assertNotEqual(a['revision_id'],c['revision_id'])
        repo=VideoRepository(a,0,Base());self.assertFalse(repo.metadata['synthetic']);self.assertIsNone(repo.metadata['seed'])
        self.assertTrue(a['frames'][0]['quality']['ready'])
    def test_missing_player_ball_confirmation_and_camera_calibration_block_scoring(self):
        for mutator in [lambda f:f['players'].pop(),lambda f:f.update(ball=None),lambda f:f['confirmed'].update(coverage_complete=False),lambda f:f.update(landmarks=[])]:
            d=copy.deepcopy(self.draft);mutator(d['frames'][0]);r=self.record(d)
            self.assertFalse(r['frames'][0]['quality']['ready'])
            with self.assertRaises(ValueError):VideoRepository(r,0,Base())
    def test_causal_velocity_never_uses_a_future_keyframe(self):
        f=self.draft['frames'][0];future=copy.deepcopy(f);future.update(video_ms=1500,period_ms=30500)
        for p in future['players']:p['image'][0]+=.001
        self.draft['frames'].append(future);r=self.record()
        self.assertTrue(all(p['velocity'] is None for p in r['frames'][0]['players']))
        self.assertTrue(all(p['velocity'] is not None for p in r['frames'][1]['players']))
        facts=fact_bundle(r,0);self.assertTrue(all(x['source']['video_ms']==1000 for x in facts['facts']))
    def test_identity_clock_score_and_nan_errors(self):
        for mutator in [lambda d:d['frames'][0]['ball'].__setitem__(0,float('nan')),lambda d:d['roster'][1].update(jersey_number=d['roster'][0]['jersey_number']),lambda d:d.update(rights_confirmed=False)]:
            d=copy.deepcopy(self.draft);mutator(d)
            with self.assertRaises(ValueError):self.record(d)
        d=copy.deepcopy(self.draft);f=copy.deepcopy(d['frames'][0]);f.update(video_ms=1500,period_ms=40000);d['frames'].append(f)
        with self.assertRaises(ValueError):self.record(d)
    def test_candidate_set_changes_with_annotation_and_recomputes_deterministically(self):
        repo=self.repo();a=repo.compare(repo.request)[0];b=repo.compare(repo.request)[0];self.assertEqual(a,b)
        d=copy.deepcopy(self.draft);d['frames'][0]['score']=[1,0];other=VideoRepository(self.record(d),0,Base());c=other.compare(other.request)[0]
        self.assertNotEqual(a['candidate_set_id'],c['candidate_set_id'])
        self.assertTrue(any(e['evidence_id']=='video-clock' for e in a['evidence']))
    def note(self,repo,approved=False):
        claim=dict(text='Compare the computed choices; these remain model estimates.',evidence_ids=['model-context'],fact_ids=[],player_ids=[],action_id=None,certainty='estimate',quantities=[])
        return dict(text=claim['text'],cited_evidence_ids=['model-context'],approved=approved,claims=[claim])
    def test_structured_claim_rejection_of_numbers_entities_future_and_false_observation(self):
        repo=self.repo();public,private=repo.compare(repo.request);context=repo.claim_context(public,private)
        note=self.note(repo);self.assertTrue(audit_note(note,public,context,[],1000)['ok'])
        changes=[{'text':'There is a 75% chance.'},{'text':'Defender arrives in 7 seconds.'},{'action_id':'pass:missing'}, {'player_ids':['H99']}, {'certainty':'observation','fact_ids':['position-H01']}]
        for update in changes:
            n=copy.deepcopy(note);n['claims'][0].update(update);n['text']=n['claims'][0]['text']
            with self.assertRaises(ValueError):audit_note(n,public,context,[],1000)
        n=copy.deepcopy(note);n['claims'][0].update(certainty='observation',fact_ids=['video-clock']);c=copy.deepcopy(context)
        next(f for f in c['facts'] if f['fact_id']=='video-clock')['source']['video_ms']=2000
        with self.assertRaises(ValueError):audit_note(n,public,c,[],1000)
    def test_real_model_loop_uses_structured_claim_context_and_reviewer(self):
        repo=self.repo();public,_=repo.compare(repo.request);seen=[]
        def fake(payload,timeout):
            seen.append(payload);note=self.note(repo,'Role: reviewer.' in payload['instructions'])
            return dict(output=[dict(type='message',content=[dict(type='output_text',text=json.dumps(note))])])
        result=run(repo.request,public['candidate_set_id'],dict(api_key='fake',model='fake',base_url='https://example.com/v1'),repo,call=fake)
        self.assertEqual(result['status'],'ready');self.assertEqual(len(seen),4);self.assertEqual(len(repo.claim_audits),4)
        for payload in seen:
            context=json.loads(payload['input'][0]['content'])['context'];self.assertIn('claim_context',context)
            self.assertNotIn('frames',context);self.assertNotIn('actual_action',json.dumps(context))
        self.assertEqual(result['candidates'],public['candidates'])
    def test_human_metrics_unknown_until_labelled(self):
        self.assertIsNone(human_metrics([])['unsupported_or_incorrect_rate'])
        self.assertEqual(human_metrics([dict(verdict='supported'),dict(verdict='unsupported')])['unsupported_or_incorrect_rate'],.5)

if __name__=='__main__':unittest.main()
