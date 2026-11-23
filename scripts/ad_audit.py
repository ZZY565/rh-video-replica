#!/usr/bin/env python3
"""Evidence extraction, adaptation-contract validation and timing evaluation."""
import argparse,json,math,re
from pathlib import Path
from PIL import Image,ImageDraw
from media import probe,run,frame,font,save

def detect_cuts(path,threshold=.24,min_gap=.20):
    m=probe(path)
    log=run(['-i',path,'-vf',f"select='gt(scene,{threshold})',showinfo",'-an','-f','null','-']).stderr.decode(errors='replace')
    cuts=[]
    for x in re.findall(r'pts_time:([\d.]+)',log):
        t=float(x)
        if t>.15 and t<m['duration']-.15 and (not cuts or t-cuts[-1]>=min_gap):cuts.append(t)
    return m,cuts

def inspect(path,out,threshold=.24):
    out=Path(out);out.mkdir(parents=True,exist_ok=True);m,cuts=detect_cuts(path,threshold)
    if m['duration']>180:raise ValueError('Split references over 180s into explicit analysis ranges')
    bounds=[0,*cuts,m['duration']];shots=[];tiles=[]
    for i,(a,b) in enumerate(zip(bounds,bounds[1:])):
        evid=[]
        for k,fraction in enumerate([.15,.5,.85]):
            t=a+(b-a)*fraction;name=f'shot-{i+1:02d}-{k}.jpg';frame(path,t,out/name);evid.append({'time':round(t,4),'frame':name})
        shots.append({'id':i+1,'start':a,'end':b,'duration':round(b-a,4),'boundary_status':'candidate_until_agent_review','evidence':evid})
        tiles.append((out/evid[1]['frame'],f'{i+1:02d} | {a:.2f}-{b:.2f}s'))
    cols=3;tw,th=400,265;sheet=Image.new('RGB',(cols*tw,math.ceil(len(tiles)/cols)*th),'#102820');d=ImageDraw.Draw(sheet)
    for i,(p,label) in enumerate(tiles):
        im=Image.open(p).convert('RGB');im.thumbnail((tw-16,220));x=i%cols*tw+(tw-im.width)//2;y=i//cols*th;sheet.paste(im,(x,y));d.text((i%cols*tw+10,y+226),label,font=font(18),fill='#e4c18b')
    sheet.save(out/'shot-contact-sheet.jpg',quality=94)
    result={'media':m,'cut_threshold':threshold,'cut_candidates':cuts,'shots':shots,'audio_status':'present, not transcribed' if m['audio'] else 'no audio in this file','method':'scene-change candidates + 3 evidence frames per interval; not semantic or musical beat detection'}
    save(out/'shot-evidence.json',result);return result

def validate_contract(c):
    if c.get('mode')!='ad_structure_adaptation':raise ValueError('This Skill handles ad_structure_adaptation; motion imitation is a different task')
    ref=c['reference'];product=c['product'];scope=c['scope'];shots=c['shots']
    if ref.get('origin')!='real_commercial' or not str(ref.get('source_url','')).startswith('https://'):raise ValueError('A real-commercial source URL is required for this benchmark')
    a,b=scope['reference_range_seconds'];duration=scope['output_duration_seconds']
    if not all(isinstance(x,(int,float)) and math.isfinite(x) for x in [a,b,duration]) or not 0<=a<b or duration<=0:raise ValueError('Invalid time range')
    if b>ref['full_duration_seconds']+.05:raise ValueError('Reference range exceeds original')
    if not product.get('image') or not product.get('name'):raise ValueError('Target product image/name required')
    if product.get('is_concept') is not True and not product.get('provided_by_user'):raise ValueError('Identify concept or user-supplied product provenance')
    claims=product.get('verified_claims',[])
    used=[];end=0
    for s in shots:
        for key in ['id','output_start','output_duration','reference_start','reference_end','observed','transfer','target_visual','acceptance']:
            if key not in s:raise ValueError('Shot missing '+key)
        if not all(isinstance(s[k],(int,float)) and not isinstance(s[k],bool) and math.isfinite(s[k]) for k in ['output_start','output_duration','reference_start','reference_end']):raise ValueError('Finite numeric shot times required')
        if abs(s['output_start']-end)>.0001 or s['output_duration']<=0:raise ValueError('Output timeline must be continuous and positive')
        if not a-.05<=s['reference_start']<s['reference_end']<=b+.05:raise ValueError('Shot evidence outside selected range')
        if not s['observed'] or not s['target_visual'] or not s['acceptance']:raise ValueError('Observable source and target acceptance required')
        for claim in s.get('claims',[]):
            if claim not in claims:raise ValueError('Unsupported product claim: '+claim)
        used.append(s['id']);end=s['output_start']+s['output_duration']
    if len(set(used))!=len(used) or not shots:raise ValueError('Unique nonempty shot IDs required')
    if abs(end-duration)>.05:raise ValueError('Timeline does not cover requested duration')
    if c.get('full_ad_replica') and (a!=0 or b<ref['full_duration_seconds']-.05):raise ValueError('An excerpt cannot be called a full-ad replica')
    return {'valid':True,'mode':c['mode'],'source_range_seconds':[a,b],'output_duration_seconds':duration,'planned_shots':len(shots),'product':product['name'],'is_concept':product['is_concept'],'full_ad_replica':c.get('full_ad_replica',False)}

def timing_metrics(expected,actual,tolerance=.16):
    if tolerance<=0:raise ValueError('Positive tolerance required')
    expected=sorted(expected);actual=sorted(actual);used=set();pairs=[]
    for e in expected:
        candidates=[(abs(e-a),i,a) for i,a in enumerate(actual) if i not in used and abs(e-a)<=tolerance]
        if candidates:
            diff,i,a=min(candidates);used.add(i);pairs.append({'expected':e,'actual':a,'error_seconds':round(diff,4)})
    precision=len(pairs)/len(actual) if actual else (1 if not expected else 0)
    recall=len(pairs)/len(expected) if expected else (1 if not actual else 0)
    return {'tolerance_seconds':tolerance,'matched_boundaries':pairs,'precision':precision,'recall':recall,'expected_count':len(expected),'actual_count':len(actual),'mean_error_seconds':sum(abs(x['expected']-x['actual']) for x in pairs)/len(pairs) if pairs else None,'semantic_match':'not assessed by timing; inspect content separately'}

def main():
    p=argparse.ArgumentParser();sp=p.add_subparsers(dest='cmd',required=True)
    a=sp.add_parser('inspect');a.add_argument('source');a.add_argument('--out',required=True);a.add_argument('--threshold',type=float,default=.24)
    a=sp.add_parser('validate');a.add_argument('contract');a.add_argument('--out',required=True)
    a=sp.add_parser('compare');a.add_argument('contract');a.add_argument('evidence');a.add_argument('--out',required=True);a.add_argument('--tolerance',type=float,default=.16)
    a=p.parse_args()
    if a.cmd=='inspect':r=inspect(a.source,a.out,a.threshold);print(json.dumps({'shots':len(r['shots']),'cuts':r['cut_candidates']}));return
    c=json.loads(Path(a.contract).read_text());r=validate_contract(c)
    if a.cmd=='compare':
        evidence=json.loads(Path(a.evidence).read_text());r=timing_metrics([s['output_start'] for s in c['shots'][1:]],evidence['cut_candidates'],a.tolerance)
    save(a.out,r);print(json.dumps(r,ensure_ascii=False,indent=2))
if __name__=='__main__':main()
