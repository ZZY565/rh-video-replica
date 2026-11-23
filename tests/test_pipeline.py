import sys,json,tempfile,unittest,copy
from pathlib import Path
from unittest.mock import patch
ROOT=Path(__file__).resolve().parents[1];sys.path.insert(0,str(ROOT/'scripts'))
from rh_api import Client,RunningHubError,validate_request,submit,poll,model_run
from media import validate_plan
class Fake:
 key='test-not-a-real-key'
 def __init__(self,results=None):self.calls=[];self.results=list(results or [])
 def request(self,path,payload=None,**kw):
  self.calls.append((path,payload))
  result=self.results.pop(0)
  if isinstance(result,Exception):raise result
  return result
 def query(self,task):return self.request('query',{'taskId':task})
class Tests(unittest.TestCase):
 def setUp(self):
  self.tmp=tempfile.TemporaryDirectory();self.addCleanup(self.tmp.cleanup);self.j=Path(self.tmp.name)/'task.json';self.graph={'1':{'inputs':{'image':'x'}},'2':{'inputs':{'image':['1',0]}}};self.req={'workflowId':'123','nodeInfoList':[{'nodeId':'1','fieldName':'image','fieldValue':'api/new.png'}]}
 def test_accept_known_scalar(self):self.assertEqual(validate_request(self.req,self.graph)['workflowId'],'123')
 def test_reject_links(self):
  self.req['nodeInfoList'][0]['nodeId']='2'
  with self.assertRaises(ValueError):validate_request(self.req,self.graph)
 def test_reject_duplicates(self):
  self.req['nodeInfoList']*=2
  with self.assertRaises(ValueError):validate_request(self.req,self.graph)
 def test_reject_unknown_node(self):
  self.req['nodeInfoList'][0]['nodeId']='9'
  with self.assertRaises(ValueError):validate_request(self.req,self.graph)
 def test_one_submit_only(self):
  c=Fake([{'code':0,'data':{'taskId':'456'}}]);r=submit(c,self.req,self.graph,self.j)
  self.assertEqual(r['taskId'],'456')
  with self.assertRaises(RunningHubError):submit(c,self.req,self.graph,self.j)
  self.assertEqual(len(c.calls),1);self.assertNotIn(c.key,self.j.read_text())
 def test_lost_response_does_not_retry(self):
  c=Fake([TimeoutError()])
  with self.assertRaises(TimeoutError):submit(c,self.req,self.graph,self.j)
  self.assertEqual(json.loads(self.j.read_text())['state'],'submission_unknown');self.assertEqual(len(c.calls),1)
 def test_no_id_is_not_success(self):
  with self.assertRaises(RunningHubError):submit(Fake([{'code':0,'data':{}}]),self.req,self.graph,self.j)
  self.assertEqual(json.loads(self.j.read_text())['state'],'submission_unknown')
 def seed_task(self):self.j.write_text(json.dumps({'state':'submitted','taskId':'456'}))
 def test_poll_success_has_usage(self):
  self.seed_task();r=poll(Fake([{'status':'SUCCESS','results':[{'url':'https://example.com/a.mp4'}],'usage':{'consumeMoney':'12.6'}}]),self.j)
  self.assertEqual(r['usage']['consumeMoney'],'12.6')
 def test_poll_failed_is_not_success(self):
  self.seed_task()
  with self.assertRaises(RunningHubError):poll(Fake([{'status':'FAILED','errorCode':'BAD'}]),self.j)
  self.assertEqual(json.loads(self.j.read_text())['state'],'failed')
 def test_timeout_preserves_id(self):
  self.seed_task()
  with self.assertRaises(RunningHubError):poll(Fake([{'status':'RUNNING'}]),self.j,timeout=0)
  self.assertEqual(json.loads(self.j.read_text())['taskId'],'456')
 def test_empty_results_are_not_success(self):
  self.seed_task()
  with self.assertRaises(RunningHubError):poll(Fake([{'status':'SUCCESS','results':[]}]),self.j)
 def test_model_reservation_and_payload(self):
  c=Fake([{'code':0,'data':{'download_url':'https://example.com/ref.mp4'}},{'code':0,'data':{'download_url':'https://example.com/img.png'}},{'taskId':'789'}]);asset=Path(self.tmp.name)/'x.png';asset.write_bytes(b'data')
  job={'endpoint':'alibaba/wan-3.0/reference-to-video','prompt':'coffee','settings':{'duration':15,'resolution':'720P'},'video_paths':[str(asset)],'image_paths':[str(asset)]}
  with patch('media.probe',return_value={'duration':15}):r=model_run(c,job,self.j)
  self.assertEqual(r['taskId'],'789');self.assertEqual(len(c.calls),3);self.assertNotIn('download_url',self.j.read_text())
 def test_storyboard_only_uses_product_image(self):
  asset=Path(self.tmp.name)/'x.png';asset.write_bytes(b'data')
  c=Fake([{'code':0,'data':{'download_url':'https://example.com/img.png'}},{'taskId':'990'}]);job={'endpoint':'alibaba/wan-3.0/reference-to-video','conditioning':'storyboard_and_product','prompt':'new coffee scenes','settings':{'duration':15,'resolution':'720P'},'video_paths':[],'image_paths':[str(asset)]}
  r=model_run(c,job,self.j)
  self.assertEqual(r['taskId'],'990');self.assertEqual(len(c.calls),2);self.assertEqual(c.calls[1][1]['videoUrls'],[])
 def test_missing_reference_is_not_silently_accepted(self):
  c=Fake();job={'endpoint':'alibaba/wan-3.0/reference-to-video','prompt':'x','settings':{'duration':15,'resolution':'720P'},'video_paths':[],'image_paths':['product.png']}
  with self.assertRaises(ValueError):model_run(c,job,self.j)
  self.assertEqual(c.calls,[]);self.assertFalse(self.j.exists())
 def test_model_limits_before_upload(self):
  c=Fake();job={'endpoint':'alibaba/wan-3.0/reference-to-video','prompt':'x','settings':{'duration':20,'resolution':'720P'},'video_paths':['x'],'image_paths':['y']}
  with patch('media.probe',return_value={'duration':15}):
   with self.assertRaises(ValueError):model_run(c,job,self.j)
  self.assertEqual(c.calls,[]);self.assertFalse(self.j.exists())
 def test_render_nan_and_missing_source(self):
  plan={'width':720,'height':1280,'fps':30,'shots':[{'kind':'image','source':'missing','duration':float('nan')}]}
  with self.assertRaises(ValueError):validate_plan(plan)
 def test_video_out_of_range(self):
  asset=Path(self.tmp.name)/'x.mp4';asset.touch();plan={'width':720,'height':1280,'fps':30,'shots':[{'kind':'video','source':str(asset),'start':4,'duration':3}]}
  with patch('media.probe',return_value={'duration':5}):
   with self.assertRaises(ValueError):validate_plan(plan)
if __name__=='__main__':unittest.main(verbosity=2)
