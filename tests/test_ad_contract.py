import copy,json,sys,tempfile,unittest
from pathlib import Path
from PIL import Image
ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/'scripts'))
from ad_audit import validate_contract,timing_metrics
from media import title_overlay,validate_plan
class ContractTests(unittest.TestCase):
 def setUp(self):self.c=json.loads((ROOT/'tests/fixtures/adaptation-contract.json').read_text())
 def test_real_benchmark_contract(self):self.assertEqual(validate_contract(self.c)['planned_shots'],6)
 def test_excerpt_cannot_claim_full_ad(self):
  self.c['full_ad_replica']=True
  with self.assertRaises(ValueError):validate_contract(self.c)
 def test_unsubstantiated_claim_blocked(self):
  self.c['shots'][0]['claims']=['certified organic']
  with self.assertRaises(ValueError):validate_contract(self.c)
 def test_gap_is_not_valid_timeline(self):
  self.c['shots'][2]['output_start']+=.02
  with self.assertRaises(ValueError):validate_contract(self.c)
 def test_nonfinite_shot_time_blocked(self):
  self.c['shots'][0]['output_duration']=float('nan')
  with self.assertRaises(ValueError):validate_contract(self.c)
 def test_motion_imitation_is_different_mode(self):
  self.c['mode']='motion_imitation'
  with self.assertRaises(ValueError):validate_contract(self.c)
 def test_evidence_range_must_be_in_source(self):
  self.c['shots'][0]['reference_start']=0
  with self.assertRaises(ValueError):validate_contract(self.c)
 def test_no_double_credit_for_one_cut(self):
  m=timing_metrics([1,1.1],[1.05],.2)
  self.assertEqual(m['recall'],.5);self.assertEqual(len(m['matched_boundaries']),1)
 def test_extra_cuts_reduce_precision(self):
  m=timing_metrics([1,2],[1,2,3],.1)
  self.assertEqual(m['recall'],1);self.assertAlmostEqual(m['precision'],2/3)
 def test_bad_image_zoom_rejected_before_render(self):
  with tempfile.TemporaryDirectory() as t:
   p=Path(t)/'product.png';Image.new('RGB',(32,32),'white').save(p)
   plan={'width':1280,'height':720,'fps':25,'shots':[{'kind':'image','source':str(p),'duration':3.6,'zoom_end':float('nan')}]}
   with self.assertRaises(ValueError):validate_plan(plan)
   plan['shots'][0]['zoom_end']=.5
   with self.assertRaises(ValueError):validate_plan(plan)
 def test_picture_only_overlay_is_transparent(self):
  with tempfile.TemporaryDirectory() as t:
   p=Path(t)/'overlay.png';title_overlay({'width':1280,'height':720},{'overlay':False},p)
   self.assertIsNone(Image.open(p).getbbox())
if __name__=='__main__':unittest.main(verbosity=2)
