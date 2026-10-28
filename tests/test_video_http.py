import json
import tempfile
import threading
import unittest
import urllib.request
import urllib.error
from pathlib import Path
from unittest.mock import patch
import server
from test_video_review import draft

class VideoHTTPTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.temp=tempfile.TemporaryDirectory();cls.patch=patch('video_review.storage.ROOT',Path(cls.temp.name));cls.patch.start()
        cls.http=server.ThreadingHTTPServer(('127.0.0.1',0),server.Handler);cls.thread=threading.Thread(target=cls.http.serve_forever,daemon=True);cls.thread.start()
        cls.url='http://127.0.0.1:'+str(cls.http.server_port)
    @classmethod
    def tearDownClass(cls):cls.http.shutdown();cls.http.server_close();cls.thread.join();cls.patch.stop();cls.temp.cleanup()
    def req(self,path,data=None,headers=None):
        raw=data if isinstance(data,bytes) else json.dumps(data).encode() if data is not None else None
        h={'Content-Type':'application/json',**(headers or {})}
        try:
            with urllib.request.urlopen(urllib.request.Request(self.url+path,data=raw,headers=h),timeout=20) as r:
                content=r.read();return r.status,json.loads(content) if r.headers.get('Content-Type','').startswith('application/json') else content,r.headers
        except urllib.error.HTTPError as e:return e.code,e.read(),e.headers
    def asset(self):
        code,a,_=self.req('/api/video-review/upload',b'\x1aE\xdf\xa3'+b'x'*100,{'Content-Type':'video/webm'});self.assertEqual(code,201);return a
    def test_real_upload_confirmation_compare_counterfactual_missing_model_and_range(self):
        asset=self.asset();annotation=draft(asset)
        code,record,_=self.req('/api/video-review/confirm',{'annotation':annotation});self.assertEqual(code,200)
        selection=dict(video_id=asset['video_id'],revision_id=record['revision_id'],frame_index=0,question='Compare the options',mode='fan',language='en',candidate_set_id=None)
        code,result,_=self.req('/api/video-review/analyze',selection);self.assertEqual(code,200);self.assertEqual(result['status'],'computed')
        self.assertFalse(result['metadata']['synthetic']);self.assertIn('facts',result)
        selection['candidate_set_id']=result['analysis']['candidate_set_id']
        action=next(c['action_id'] for c in result['analysis']['public']['candidates'] if c['eligible'])
        code,hypothesis,_=self.req('/api/video-review/counterfactual',{'selection':selection,'action_id':action})
        self.assertEqual(code,200);self.assertTrue(hypothesis['not_observed_future']);self.assertEqual(hypothesis['candidate_set_id'],selection['candidate_set_id'])
        with patch('server.configuration',return_value={}):
            code,result,_=self.req('/api/video-review/agents',selection)
        self.assertEqual(code,200);self.assertEqual(result['response']['status'],'model_unavailable');self.assertEqual(result['claims'],[])
        selection['candidate_set_id']='old';self.assertEqual(self.req('/api/video-review/agents',selection)[0],400)
        code,part,headers=self.req(asset['media_url'],headers={'Range':'bytes=0-3'});self.assertEqual(code,206);self.assertEqual(part,b'\x1aE\xdf\xa3');self.assertIn('bytes 0-3/',headers['Content-Range'])
        self.assertEqual(self.req(asset['media_url'],headers={'Range':'bytes=1000-'})[0],416)
    def test_partial_annotations_are_saved_but_not_scored(self):
        asset=self.asset();annotation=draft(asset);annotation['frames'][0]['players'].pop()
        code,r,_=self.req('/api/video-review/confirm',{'annotation':annotation});self.assertEqual(code,200)
        s=dict(video_id=asset['video_id'],revision_id=r['revision_id'],frame_index=0,question='Compare',mode='fan',language='en',candidate_set_id=None)
        code,r,_=self.req('/api/video-review/analyze',s);self.assertEqual(code,200);self.assertEqual(r['status'],'needs_confirmation');self.assertIsNone(r['analysis'])
    def test_public_demo_and_cross_origin_cannot_upload_or_read_private_video(self):
        asset=self.asset()
        self.assertEqual(self.req('/api/video-review/upload',b'x'*100,{'Content-Type':'video/webm','Origin':'https://other.example'})[0],403)
        with patch.dict('os.environ',{'NEXTPLAY_PUBLIC_ORIGIN':'https://demo.example'}):
            h={'Host':'demo.example','Origin':'https://demo.example','Content-Type':'video/webm'}
            self.assertEqual(self.req('/api/video-review/upload',b'\x1aE\xdf\xa3'+b'x'*100,h)[0],403)
            self.assertEqual(self.req(asset['media_url'],headers=h)[0],403)
    def test_signatures_json_size_and_unknown_asset(self):
        self.assertEqual(self.req('/api/video-review/upload',b'x'*100,{'Content-Type':'video/mp4'})[0],400)
        self.assertEqual(self.req('/api/video-review/analyze',{'video_id':'..'})[0],400)
        self.assertEqual(self.req('/api/video-review/media/'+'0'*32)[0],404)
    def test_structured_explanation_feedback_is_persisted_against_immutable_revision(self):
        asset=self.asset();_,record,_=self.req('/api/video-review/confirm',{'annotation':draft(asset)})
        selection=dict(video_id=asset['video_id'],revision_id=record['revision_id'],frame_index=0,question='Compare',mode='fan',language='en',candidate_set_id=None)
        _,analysis,_=self.req('/api/video-review/analyze',selection);selection['candidate_set_id']=analysis['analysis']['candidate_set_id']
        def fake(payload,timeout):
            note=dict(text='These options are unvalidated model estimates.',cited_evidence_ids=['model-context'],approved='Role: reviewer.' in payload['instructions'],claims=[dict(text='These options are unvalidated model estimates.',evidence_ids=['model-context'],fact_ids=[],player_ids=[],action_id=None,certainty='estimate',quantities=[])])
            return dict(status='completed',output=[dict(type='message',content=[dict(type='output_text',text=json.dumps(note))])])
        with patch('decision_analysis.agents.transport',side_effect=lambda config,payload,timeout:fake(payload,timeout)),patch('server.configuration',return_value=dict(api_key='fake',model='fake',base_url='https://example.test/v1')):
            code,a,_=self.req('/api/video-review/agents',selection)
        self.assertEqual(code,200);self.assertTrue(a['audit']['ok']);self.assertEqual(a['audit']['citation_coverage'],1)
        label=dict(video_id=asset['video_id'],revision_id=record['revision_id'],explanation_id=a['audit']['explanation_id'],claim_index=0,verdict='unsupported',notes='Test-only human label')
        code,value,_=self.req('/api/video-review/feedback',label)
        self.assertEqual(code,200);self.assertEqual(value['metrics']['unsupported_or_incorrect_rate'],1)
        label['revision_id']='0'*16;self.assertEqual(self.req('/api/video-review/feedback',label)[0],400)

if __name__=='__main__':unittest.main()
