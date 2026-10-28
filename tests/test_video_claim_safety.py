import copy
import io
import json
import tempfile
import unittest
from pathlib import Path
from decision_analysis.claim_safety import check_language
from video_review.audit import audit_note
from video_review.project import confirm,VideoRepository,fact_bundle
from video_review.storage import upload
from test_video_review import Base,draft
CONFIG=dict(model='fake',api_key='fake',base_url='https://example.com/v1')
from decision_analysis.agents import run


class ClaimSafetyTests(unittest.TestCase):
    def setUp(self):
        self.temp=tempfile.TemporaryDirectory();self.root=Path(self.temp.name)
        self.asset=upload(io.BytesIO(b'\x1aE\xdf\xa3'+b'x'*100),104,'video/webm',root=self.root)
        self.annotation=draft(self.asset)
        self.repo=VideoRepository(confirm(self.asset['video_id'],self.annotation,self.root),0,Base())
        self.public,self.private=self.repo.compare(self.repo.request)
        self.context=self.repo.claim_context(self.public,self.private)
    def tearDown(self):self.temp.cleanup()
    def note(self,**updates):
        c=dict(text='These are unvalidated model estimates.',evidence_ids=['model-context'],fact_ids=[],player_ids=[],action_id=None,certainty='estimate',quantities=[])
        c.update(updates)
        return dict(text=c['text'],cited_evidence_ids=c['evidence_ids'],approved=True,claims=[c])
    def audit(self,note):return audit_note(note,self.public,self.context,[p['player_id'] for p in self.repo.metadata['players']],1000)
    def test_overconfident_english_and_chinese_are_rejected(self):
        for text in ['The defender is likely to intercept.','This has a significant practical risk.','He will score.','This is the optimal choice.','这条传球大概率被断。','这是最佳选择。','他的惯用脚是左脚。']:
            with self.subTest(text=text),self.assertRaises(ValueError):check_language(text)
    def test_model_claim_requires_explicit_scope_and_uncertainty(self):
        check_language('This is not a calibrated probability.')
        self.assertTrue(self.audit(self.note())['ok'])
        with self.assertRaisesRegex(ValueError,'missing_model_scope'):self.audit(self.note(text='The option is safe.'))
    def test_observation_cannot_smuggle_in_a_tactical_conclusion(self):
        with self.assertRaisesRegex(ValueError,'observation_must'):
            self.audit(self.note(text='The team controls the match.',certainty='observation',fact_ids=['video-clock']))
    def test_server_authored_observation_with_exact_numeric_source_is_allowed(self):
        text=next(x['text'] for x in self.context['observation_statements'] if x['fact_id']=='video-clock')
        n=self.note(text=text,certainty='observation',fact_ids=['video-clock'],quantities=[dict(fact_id='video-clock',value=1000,unit='ms')])
        self.assertTrue(self.audit(n)['ok'])
    def test_incomplete_scene_never_labels_observations_confirmed(self):
        self.annotation['frames'][0]['confirmed']['in_play']=False
        record=confirm(self.asset['video_id'],self.annotation,self.root)
        facts=fact_bundle(record,0)
        self.assertTrue(all(f['verification']=='unconfirmed' for f in facts['facts'] if f['kind']=='observed'))
    def test_generic_citation_cannot_support_a_specific_action(self):
        action=next(c for c in self.public['candidates'] if c['eligible'])
        with self.assertRaisesRegex(ValueError,'missing_action_specific'):
            self.audit(self.note(action_id=action['action_id']))
    def test_unbound_action_conclusion_is_rejected(self):
        with self.assertRaisesRegex(ValueError,'action_conclusion_needs'):
            self.audit(self.note(text='In this model, the pass may be intercepted.'))
    def test_a_player_fact_cannot_be_attached_to_another_player(self):
        with self.assertRaisesRegex(ValueError,'fact_player_mismatch'):
            self.audit(self.note(fact_ids=['image-H01'],player_ids=['H02']))
    def test_a_rank_fact_cannot_be_attached_to_another_action(self):
        a,b=[c for c in self.public['candidates'] if c['eligible']][:2]
        shared=set.intersection(*(set(c['evidence_ids']) for c in self.public['candidates']))
        refs=list(set(a['evidence_ids'])-shared)
        with self.assertRaisesRegex(ValueError,'fact_action_mismatch'):
            self.audit(self.note(evidence_ids=refs,action_id=a['action_id'],fact_ids=['rank-'+b['action_id']]))
    def test_hypotheses_require_a_real_tool_result_bound_to_the_same_set(self):
        a=next(c for c in self.public['candidates'] if c['eligible'])
        refs=[e for e in a['evidence_ids'] if e.startswith('route-')]
        n=self.note(text='In this model simulation, this option may vary.',evidence_ids=refs,action_id=a['action_id'],certainty='hypothesis')
        with self.assertRaisesRegex(ValueError,'hypothesis_requires'):self.audit(n)
        f=self.repo.register_rollout(a['action_id'],dict(candidate_set_id=self.public['candidate_set_id'],scenarios=[dict(outcome='retained')]))
        self.context=self.repo.claim_context(self.public,self.private);n['claims'][0]['fact_ids']=[f['fact_id']]
        self.assertTrue(self.audit(n)['ok'])
        next(x for x in self.context['facts'] if x['fact_id']==f['fact_id'])['source']['candidate_set_id']='old'
        with self.assertRaisesRegex(ValueError,'stale_hypothesis'):self.audit(n)
    def test_unsafe_model_answer_is_withheld_without_changing_computed_ranks(self):
        for text in ['Under this model, the pass is likely to succeed.','This model gives ninety percent success.']:
            note=self.note(text=text)
            def fake(payload,timeout):
                return dict(output=[dict(type='message',content=[dict(type='output_text',text=json.dumps(note))])])
            result=run(self.repo.request,self.public['candidate_set_id'],CONFIG,self.repo,call=fake)
            self.assertEqual(result['status'],'model_unavailable');self.assertIsNone(result['explanation'])
            self.assertEqual(result['candidates'],self.public['candidates'])
            self.assertNotIn(text,json.dumps(result))
            self.assertIn('uncalibrated_probability',self.repo.claim_rejections)


