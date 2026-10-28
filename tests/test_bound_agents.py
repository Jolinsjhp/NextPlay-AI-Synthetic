import copy
import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch
from decision_analysis.agents import run, configuration, consume_quota, transport, match_context
from decision_analysis.comparison import compare_actions
from contracts.model import check_exchange

FIX = Path(__file__).parent / 'fixtures/contracts'

class FixtureRepo:
    def __init__(self):
        self.metadata = json.loads((FIX/'match.json').read_text())['metadata']
        self.snapshot = json.loads((FIX/'case-a/snapshot.json').read_text())
        self.request = json.loads((FIX/'case-a/request.json').read_text())
    def compare(self, request):
        return compare_actions(request, self.snapshot, self.metadata,
            dict(model_id='test-only', source_commit='test-only', xt=[.02]*96, fitting_matches=[], temperature=.05))
    def resolve(self, request):return self.snapshot, self.metadata, {}
    def bundle(self, request):return {'source_profile': {'preferred_foot': None}}

class AgentTests(unittest.TestCase):
    def setUp(self):
        self.repo=FixtureRepo(); self.request=self.repo.request
        self.public=self.repo.compare(self.request)[0]; self.cid=self.public['candidate_set_id']
        self.eid=self.public['evidence'][0]['evidence_id']
        self.config=dict(base_url='https://example.openai.azure.com/openai/v1',model='deployment',api_key='test-only')
        self.calls=[]
    def response(self, approved=False, citation=None, text='A model hypothesis; compare the supported options.'):
        note=dict(text=text,cited_evidence_ids=[citation or self.eid],approved=approved)
        return {'status':'completed','output':[{'type':'message','content':[{'type':'output_text','text':json.dumps(note)}]}]}
    def fake(self,payload,timeout):
        self.calls.append(payload)
        return self.response(approved='Role: reviewer.' in payload['instructions'])
    def run_team(self,call=None):return run(self.request,self.cid,self.config,self.repo,call=call or self.fake)
    def test_four_roles_same_evidence_and_no_rescoring_or_future(self):
        result=self.run_team();self.assertEqual(result['status'],'ready');self.assertIsNotNone(result['explanation'])
        self.assertEqual(result['candidates'],self.public['candidates']);self.assertEqual(result['candidate_set_id'],self.cid)
        self.assertEqual(len(self.calls),4)
        for call in self.calls:
            context=json.loads(call['input'][0]['content'])['context']
            self.assertEqual(context['comparison'],self.public)
            self.assertNotIn('retrospective',context);self.assertTrue(all(not c['is_actual'] for c in context['comparison']['candidates']))
        check_exchange(self.request,result,self.repo.snapshot,self.repo.metadata)
    def test_stale_candidate_rejected_before_model_call(self):
        with self.assertRaises(ValueError):run(self.request,'outcome-3.0:0000000000000000',self.config,self.repo,call=self.fake)
        self.assertEqual(self.calls,[])
    def test_missing_configuration_never_fakes_agent_calls(self):
        result=run(self.request,self.cid,{},self.repo,call=self.fake)
        self.assertEqual(result['status'],'model_unavailable');self.assertEqual(result['agent_trace'],[]);self.assertEqual(self.calls,[])
    def test_invalid_citation_and_uncalibrated_percentage_are_blocked(self):
        for kwargs in ({'citation':'invented'},{'text':'70% probability of a goal'}):
            result=self.run_team(lambda p,t:self.response(**kwargs))
            self.assertIsNone(result['explanation']);self.assertEqual(result['status'],'model_unavailable')
            self.assertFalse(result['agent_trace'][-1]['ok'])
    def test_reviewer_rejects_then_coordinator_rewrites_once(self):
        roles=[]
        def fake(p,t):
            role=p['instructions'].split('Role: ')[1].split('.')[0];roles.append(role)
            return self.response(approved=role=='reviewer' and roles.count('reviewer')==2)
        result=self.run_team(fake)
        self.assertEqual(roles,['attack','defense','coordinator','reviewer','coordinator','reviewer'])
        self.assertIsNotNone(result['explanation'])
    def test_two_rejections_fall_back_to_computed_evidence(self):
        result=self.run_team(lambda p,t:self.response())
        self.assertEqual(result['status'],'partial');self.assertIsNone(result['explanation'])
        self.assertEqual(result['candidates'],self.public['candidates'])
    def test_tool_roundtrip_uses_bound_evidence(self):
        first=[True]
        def fake(p,t):
            if first[0]:
                first[0]=False
                return {'output':[{'type':'function_call','call_id':'1','name':'compare_actions','arguments':'{}'}]}
            if p['input'][-1].get('type')=='function_call_output':
                self.assertEqual(json.loads(p['input'][-1]['output']),self.public)
            return self.fake(p,t)
        result=self.run_team(fake)
        self.assertIsNotNone(result['explanation']);self.assertTrue(any(x['tool']=='compare_actions' for x in result['agent_trace']))
    def test_unknown_tool_never_executes(self):
        result=self.run_team(lambda p,t:{'output':[{'type':'function_call','call_id':'1','name':'shell','arguments':'{}'}]})
        self.assertIsNone(result['explanation']);self.assertFalse(result['agent_trace'][-1]['ok'])
    def test_timeout_keeps_canonical_comparison(self):
        def fail(p,t):raise TimeoutError('secret-provider-message')
        result=self.run_team(fail)
        self.assertEqual(result['candidates'],self.public['candidates']);self.assertNotIn('secret-provider-message',json.dumps(result))
    def test_persistent_daily_cap_and_disabled_budget(self):
        with tempfile.TemporaryDirectory() as folder:
            path=Path(folder)/'quota.db';consume_quota(path,1)
            with self.assertRaises(RuntimeError):consume_quota(path,1)
            with self.assertRaises(RuntimeError):consume_quota(Path(folder)/'zero.db',0)
    def test_azure_auth_and_no_secret_in_output(self):
        import io
        class Response(io.BytesIO):pass
        def opener(req, timeout):
            self.assertEqual(req.full_url,self.config['base_url']+'/responses')
            self.assertEqual(req.get_header('Api-key'),'test-only');self.assertIsNone(req.get_header('Authorization'))
            return Response(json.dumps(self.response()).encode())
        with patch('decision_analysis.agents.urlopen',opener),patch('decision_analysis.agents.consume_quota'):
            transport(self.config,{'model':'deployment'},2)
    def test_environment_configuration(self):
        with patch.dict('os.environ',{'NEXTPLAY_MODEL':'env-model','NEXTPLAY_MODEL_API_KEY':'env-key'}):
            config=configuration(self.config);self.assertEqual(config['model'],'env-model');self.assertEqual(config['api_key'],'env-key')
    def test_single_baseline_really_uses_one_model_call(self):
        result=run(self.request,self.cid,self.config,self.repo,call=self.fake,strategy='single')
        self.assertEqual(len(self.calls),1);self.assertIsNotNone(result['explanation'])
        self.assertTrue(any('no separate model reviewer' in x for x in result['limitations']))
    def test_situation_uses_observed_score_and_keeps_competition_rules_unknown(self):
        snap=copy.deepcopy(self.repo.snapshot)
        team=next(p['team_id'] for p in self.repo.metadata['players'] if p['player_id']==self.request['actor_id'])
        snap['frame'].update(score=[0,1] if team=='HOME' else [1,0],period=2,period_ms=44*60*1000)
        context=match_context(self.request,snap,self.repo.metadata)
        self.assertEqual(context['score_state'],'trailing');self.assertEqual(context['goal_margin'],-1)
        self.assertEqual(context['nominal_regulation_remaining_s'],60)
        self.assertIsNone(context['competition_rules']);self.assertIsNone(context['qualification_objective'])
        self.assertFalse(context['ranking_accounts_for_match_objective'])

if __name__=='__main__':unittest.main()
