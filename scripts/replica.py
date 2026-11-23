#!/usr/bin/env python3
"""Portable entrypoint for an agent-operated video adaptation workflow."""
import argparse,json,sys
from pathlib import Path
from media import prepare,render,quality,save,ffmpeg
from rh_api import Client,validate_request,submit,poll,download,model_run

def load(path):return json.loads(Path(path).read_text())
def main():
 p=argparse.ArgumentParser(description='镜作 RH Ad Structure Adaptation 2.0');s=p.add_subparsers(dest='cmd',required=True)
 s.add_parser('doctor')
 a=s.add_parser('prepare');a.add_argument('source');a.add_argument('--out',required=True);a.add_argument('--interval',type=float,default=.5)
 a=s.add_parser('render');a.add_argument('plan');a.add_argument('--out',required=True)
 a=s.add_parser('qc');a.add_argument('video');a.add_argument('--expected',type=float);a.add_argument('--out',required=True)
 a=s.add_parser('rh-plan');a.add_argument('request');a.add_argument('--graph',required=True);a.add_argument('--out',required=True)
 a=s.add_parser('rh-model-run');a.add_argument('job');a.add_argument('--journal',required=True)
 a=s.add_parser('rh-upload');a.add_argument('file');a.add_argument('--out',required=True)
 a=s.add_parser('rh-submit');a.add_argument('request');a.add_argument('--graph',required=True);a.add_argument('--journal',required=True)
 a=s.add_parser('rh-poll');a.add_argument('journal');a.add_argument('--timeout',type=float,default=900);a.add_argument('--interval',type=float,default=10)
 a=s.add_parser('rh-download');a.add_argument('journal');a.add_argument('--out',required=True)
 a=p.parse_args()
 try:
  if a.cmd=='doctor':result={'ffmpeg':ffmpeg(),'python':sys.version.split()[0],'api_key_configured':bool(__import__('os').getenv('RUNNINGHUB_API_KEY'))}
  elif a.cmd=='prepare':result=prepare(a.source,a.out,a.interval);result={'duration':result['media']['duration'],'frames':len(result['frames']),'output':a.out}
  elif a.cmd=='render':
   path=Path(a.plan).resolve();plan=load(path)
   for shot in plan['shots']:shot['source']=str((path.parent/shot['source']).resolve())
   if plan.get('music'):plan['music']=str((path.parent/plan['music']).resolve())
   result=render(plan,a.out)
  elif a.cmd=='qc':result=quality(a.video,a.expected);save(a.out,result)
  elif a.cmd=='rh-plan':result=validate_request(load(a.request),load(a.graph));save(a.out,result)
  elif a.cmd=='rh-model-run':
   jobpath=Path(a.job).resolve();job=load(jobpath)
   for k in ['video_paths','image_paths']:job[k]=[str((jobpath.parent/x).resolve()) for x in job.get(k,[])]
   result=model_run(Client(),job,a.journal)
  elif a.cmd=='rh-upload':result={'fileName':Client().upload(a.file)};save(a.out,result)
  elif a.cmd=='rh-submit':result=submit(Client(),load(a.request),load(a.graph),a.journal)
  elif a.cmd=='rh-poll':
   if a.timeout<=0 or not 0<a.interval<=60:raise ValueError('Positive timeout and interval <=60 required')
   result=poll(Client(),a.journal,a.timeout,a.interval)
  elif a.cmd=='rh-download':result=download(a.journal,a.out)
  print(json.dumps(result,ensure_ascii=False,indent=2))
  if a.cmd=='qc' and not result['passed']:return 1
  return 0
 except (ValueError,RuntimeError,OSError,KeyError) as e:
  print(f'ERROR: {e}',file=sys.stderr);return 1
if __name__=='__main__':sys.exit(main())
