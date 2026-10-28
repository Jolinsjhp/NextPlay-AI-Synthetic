import json
import unittest
from pathlib import Path

ROOT=Path(__file__).resolve().parents[1]

class SubmissionDataTests(unittest.TestCase):
    def test_roster_is_independently_simulated_without_identity_fields(self):
        roster=json.loads((ROOT/'data/league/squads.json').read_text())
        self.assertEqual(roster['seed'],20261028)
        self.assertEqual(len(roster['teams']),20)
        ids=set()
        for t in roster['teams']:
            self.assertRegex(t['club_id'],r'^S\d{2}$')
            for p in t['players']:
                self.assertEqual(p['kind'],'simulated')
                self.assertNotIn(p['player_id'],ids);ids.add(p['player_id'])
                for key in ('date_of_birth','nationality','api_player_id','sofascore','source_date_of_birth'):
                    self.assertNotIn(key,p)
        self.assertEqual(len(ids),360)

    def test_no_inherited_models_or_importer(self):
        self.assertFalse((ROOT/'import_sofascore.py').exists())
        model=json.loads((ROOT/'decision/value-model.json').read_text())
        self.assertEqual(model['provenance']['kind'],'simulated')
        self.assertTrue(model['provenance']['source_hashes'])

    def test_new_match_ids_and_synthetic_fold_provenance(self):
        league=json.loads((ROOT/'data/league/league.json').read_text())
        self.assertTrue(league['competition']['synthetic'])
        self.assertEqual(league['format']['total_matches'],30)
        for p in (ROOT/'data/league/matches').iterdir():
            self.assertRegex(p.name,r'^SYN26-W\d{2}-S\d{2}-S\d{2}$')
        for p in (ROOT/'data/decision-analysis/models').glob('*.json'):
            model=json.loads(p.read_text())
            if 'fitting_matches' not in model:continue
            fit=set(model['fitting_matches']);cal=set(model['calibration_matches']);test=set(model['test_matches'])
            self.assertFalse(fit&cal or fit&test or cal&test)
