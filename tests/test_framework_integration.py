"""Actual Microsoft Agent Framework execution on invented, decision-time fixtures."""
import copy
import importlib.util
import json
import unittest
from pathlib import Path
from unittest.mock import patch
from decision_analysis.comparison import compare_actions
from decision_analysis.framework import kernel_inputs,workflow_diagnostic
from decision_analysis.kernel import tendency
READY=importlib.util.find_spec('agent_framework') is not None and importlib.util.find_spec('numpy') is not None
@unittest.skipUnless(READY,'Install the agent extra to run actual framework integration')
class FrameworkTests(unittest.TestCase):
    def setUp(self):
        r=Path(__file__).parent/'fixtures/contracts';self.s=json.loads((r/'case-a/snapshot.json').read_text());self.m=json.loads((r/'match.json').read_text())['metadata'];req=json.loads((r/'case-a/request.json').read_text())
        self.p,self.q=compare_actions(req,self.s,self.m,dict(model_id='test',source_commit='test',xt=[.02]*96,fitting_matches=[],temperature=.05))
    def test_real_framework_matches_direct(self):
        a=workflow_diagnostic(self.s,self.m,self.p,self.q);b=workflow_diagnostic(self.s,self.m,self.p,self.q,backend='direct')
        self.assertEqual(a['status'],'computed');self.assertEqual(a['output']['decision'],b['output']['decision']);self.assertEqual(a['output']['completion'],b['output']['completion'])
        self.assertEqual([t['tool'] for t in a['output']['tools']],['read-frame','decide','score-completion','narrate'])
        self.assertFalse(a['output']['narration']['sent']);self.assertFalse(a['model_called'])
        self.assertIsNotNone(a['output']['decision']['primary_pass'])
        self.assertEqual(a['output']['decision']['probabilities'],tendency(self.s,self.m)['distribution'])
    def test_candidate_ranks_and_snapshot_are_unchanged(self):
        before=copy.deepcopy((self.s,self.p,self.q));workflow_diagnostic(self.s,self.m,self.p,self.q);self.assertEqual((self.s,self.p,self.q),before)
    def test_scoring_failure_is_recorded(self):
        with patch('inside_the_game.system1.agent_workflow.score_paths',side_effect=RuntimeError('test scoring failure')):
            a=workflow_diagnostic(self.s,self.m,self.p,self.q)
        self.assertEqual(a['status'],'computed');self.assertTrue(a['output']['degraded']);self.assertIsNotNone(a['output']['decision'])
    def test_narrator_failure_is_not_success(self):
        from inside_the_game.system1.agent_workflow import run_decision_workflow
        from inside_the_game.system1.policy import SoftmaxActionPolicy
        m,e=kernel_inputs(self.s,self.m,self.p,self.q)
        def fail(_):raise RuntimeError('test narrator failure')
        a=run_decision_workflow(m,e,SoftmaxActionPolicy.stub(),fail)
        self.assertTrue(a['degraded']);self.assertFalse(a['narration']['sent'])
    def test_future_frame_refused(self):
        from inside_the_game.system1.agent_workflow import run_decision_workflow
        m,e=kernel_inputs(self.s,self.m,self.p,self.q);m.frames_by_id[self.s['t_ms']]['t_ms']+=1
        with self.assertRaises(Exception):run_decision_workflow(m,e)
if __name__=='__main__':unittest.main()
