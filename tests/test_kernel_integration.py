import copy
import json
import unittest
from pathlib import Path
from decision_analysis.kernel import tendency
from decision_analysis.comparison import compare_actions
from decision_analysis.metrics import analysis_document
ROOT=Path(__file__).parent/'fixtures/contracts'
class KernelTests(unittest.TestCase):
    def setUp(self):
        self.s=json.loads((ROOT/'case-a/snapshot.json').read_text());self.m=json.loads((ROOT/'match.json').read_text())['metadata'];self.r=json.loads((ROOT/'case-a/request.json').read_text())
    def test_distribution_and_provenance(self):
        t=tendency(self.s,self.m);self.assertEqual(set(t['distribution']),{'pass','shoot','dribble','hold'})
        self.assertAlmostEqual(sum(t['distribution'].values()),1);self.assertEqual(t['weight_source'],'hand_set_stub');self.assertFalse(t['affects_candidate_ranks'])
        self.assertEqual(t['snapshot_id'],self.s['snapshot_id'])
    def test_rotate_everything_preserves_distribution(self):
        rotated=copy.deepcopy(self.s);f=rotated['frame'];f['ball'][0]=105-f['ball'][0];f['ball'][1]=68-f['ball'][1]
        for p in f['players']:p[1],p[2]=105-p[1],68-p[2]
        rotated['attacking_direction']={k:('negative_x' if v=='positive_x' else 'positive_x') for k,v in rotated['attacking_direction'].items()}
        for k,v in tendency(self.s,self.m)['distribution'].items():self.assertAlmostEqual(v,tendency(rotated,self.m)['distribution'][k])
    def test_nonlive_snapshot_cannot_generate_tendency(self):
        self.s['frame']['in_play']=False;self.assertEqual(tendency(self.s,self.m)['status'],'unavailable')
    def test_diagnostics_do_not_mutate_candidates(self):
        model=dict(model_id='test-only',source_commit='test-only',xt=[.02]*96,fitting_matches=[],temperature=.05)
        public,private=compare_actions(self.r,self.s,self.m,model);before=copy.deepcopy(public)
        doc=analysis_document(self.r,public,private,self.s,self.m,{},'test')
        self.assertEqual(public,before);self.assertEqual(doc['public'],before)
        self.assertEqual(doc['action_tendency']['snapshot_id'],doc['snapshot_id'])
if __name__=='__main__':unittest.main()
