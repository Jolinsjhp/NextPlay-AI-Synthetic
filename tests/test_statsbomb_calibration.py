"""Invented fixtures only; no external dataset is accessed."""
import hashlib
import json
import tempfile
import unittest
from pathlib import Path
from research.statsbomb_calibration import run
ROOT=Path(__file__).resolve().parents[1]
def events(offset):
    base=dict(period=1,play_pattern={'name':'Regular Play'},location=[50+offset,40])
    return [dict(base,type={'name':'Pass'},**{'pass':dict(body_part={'name':'Right Foot'},height={'name':'Ground Pass'},end_location=[70,40])}),dict(base,type={'name':'Carry'}),dict(base,type={'name':'Shot'},shot=dict(body_part={'name':'Right Foot'},outcome={'name':'Saved'}))]
class CalibrationTests(unittest.TestCase):
    def setUp(self):
        (ROOT/'.local').mkdir(exist_ok=True)
        self.temp=tempfile.TemporaryDirectory(dir=ROOT/'.local');self.addCleanup(self.temp.cleanup);self.folder=Path(self.temp.name);self.sources=[]
        for i,split in enumerate(('train','test')):
            p=self.folder/(split+'.json');raw=json.dumps(events(i)).encode();p.write_bytes(raw)
            self.sources.append(dict(path=p.name,sha256=hashlib.sha256(raw).hexdigest(),split=split))
        self.manifest=dict(authorization=dict(reviewed=True,reference='TEST FIXTURES ONLY',uses=['research','hackathon','public_derived_statistics','public_demo']),sources=self.sources)
    def execute(self):
        p=self.folder/'manifest.json';p.write_text(json.dumps(self.manifest));return run(p,self.folder/'output')
    def test_missing_authorization_is_blocked(self):
        self.manifest['authorization']['reviewed']=False
        with self.assertRaisesRegex(ValueError,'permission'):self.execute()
        self.assertFalse((self.folder/'output').exists())
    def test_split_leakage_is_blocked(self):
        self.sources[1].update(path=self.sources[0]['path'],sha256=self.sources[0]['sha256'])
        with self.assertRaisesRegex(ValueError,'leakage'):self.execute()
    def test_hash_mismatch_is_blocked(self):
        self.sources[0]['sha256']='0'*64
        with self.assertRaisesRegex(ValueError,'hash mismatch'):self.execute()
    def test_aggregate_only_and_release_unchanged(self):
        release=ROOT/'realism/profile.json';before=release.read_bytes();report=self.execute();profile=json.loads((self.folder/'output/profile.json').read_text())
        self.assertEqual(sum(v['n'] for v in profile['pass_success'].values()),1)
        self.assertEqual(report['split_source_counts'],{'train':1,'test':1});self.assertEqual(release.read_bytes(),before)
        self.assertNotIn('location',profile)
        self.assertEqual(profile['provenance']['release_activation'],'not activated; synthetic release data unchanged')
if __name__=='__main__':unittest.main()
