"""RunningHub workflow adapter. No keys in files; no automatic resubmission."""
import hashlib,json,mimetypes,os,time,urllib.request,urllib.error,uuid
from pathlib import Path
from media import save

class RunningHubError(RuntimeError): pass

class Client:
    def __init__(self,base=None,key=None):
        self.base=(base or os.getenv('RUNNINGHUB_BASE_URL','https://www.runninghub.cn')).rstrip('/')
        if self.base not in ['https://www.runninghub.cn','https://www.runninghub.ai']:raise ValueError('Use an official RunningHub HTTPS endpoint')
        self.key=key or os.getenv('RUNNINGHUB_API_KEY')
        if not self.key:raise RunningHubError('Set RUNNINGHUB_API_KEY locally. Do not paste it into reports or prompts.')
    def request(self,path,payload=None,body=None,content_type='application/json'):
        data=body if body is not None else json.dumps(payload).encode()
        req=urllib.request.Request(self.base+path,data=data,headers={'Content-Type':content_type,'Authorization':'Bearer '+self.key},method='POST')
        # Never retry a submission: a lost response can still mean a paid task exists.
        try:
            with urllib.request.urlopen(req,timeout=90) as r:return json.load(r)
        except (urllib.error.URLError,TimeoutError,ValueError) as e:
            # Do not echo server response bodies that may include credential-bearing websocket URLs.
            raise RunningHubError('HTTP request failed; reconcile remote task history before resubmitting. '+type(e).__name__) from None
    def upload(self,path):
        p=Path(path)
        if not p.is_file() or not 0<p.stat().st_size<=30*1024*1024:raise ValueError('Input must be a nonempty file <=30MiB')
        boundary='----rh'+uuid.uuid4().hex
        safe=p.name.replace('"','_').replace('\r','_').replace('\n','_')
        pieces=[]
        for name,value in [('apiKey',self.key),('fileType','input')]:
            pieces.append(f'--{boundary}\r\nContent-Disposition: form-data; name="{name}"\r\n\r\n{value}\r\n'.encode())
        pieces.append(f'--{boundary}\r\nContent-Disposition: form-data; name="file"; filename="{safe}"\r\nContent-Type: {mimetypes.guess_type(safe)[0] or "application/octet-stream"}\r\n\r\n'.encode()+p.read_bytes()+f'\r\n--{boundary}--\r\n'.encode())
        result=self.request('/task/openapi/upload',body=b''.join(pieces),content_type='multipart/form-data; boundary='+boundary)
        if result.get('code')!=0 or not isinstance(result.get('data'),dict) or not result['data'].get('fileName'):raise RunningHubError('Upload rejected; inspect account and API availability (legacy upload is deprecated)')
        return result['data']['fileName']
    def query(self,task):
        result=self.request('/openapi/v2/query',{'taskId':str(task)})
        if result.get('code') not in (None,0):raise RunningHubError('Query rejected; no new task was submitted')
        return result

def validate_request(request,graph):
    workflow=str(request.get('workflowId',''))
    if not workflow.isdigit():raise ValueError('Numeric workflowId required')
    seen=set()
    for v in request.get('nodeInfoList',[]):
        n,f=str(v['nodeId']),v['fieldName']
        if (n,f) in seen:raise ValueError('Duplicate node override')
        seen.add((n,f))
        if n not in graph or f not in graph[n].get('inputs',{}):raise ValueError(f'Unknown node input {n}.{f}')
        if isinstance(graph[n]['inputs'][f],list):raise ValueError('Do not overwrite graph links; override the originating value node')
        if isinstance(v['fieldValue'],(dict,list)):raise ValueError('fieldValue must be a scalar')
    return {'workflowId':workflow,'nodeInfoList':request.get('nodeInfoList',[])}

def submit(client,request,graph,journal):
    payload=validate_request(request,graph);p=Path(journal)
    if p.exists():raise RunningHubError('Journal already exists. Resume its task or reconcile its state before a new submission.')
    record={'state':'submitting','request_sha256':hashlib.sha256(json.dumps(payload,sort_keys=True).encode()).hexdigest(),'workflowId':payload['workflowId'],'created_at':time.time(),'taskId':None}
    # Exclusive journal reservation prevents concurrent duplicate submissions.
    p.parent.mkdir(parents=True,exist_ok=True)
    with p.open('x') as f:json.dump(record,f,indent=2)
    try:
        result=client.request('/task/openapi/create',dict(payload,apiKey=client.key))
    except Exception:
        record['state']='submission_unknown';save(p,record);raise
    data=result.get('data') or {}
    task=data.get('taskId') if isinstance(data,dict) else None
    if not task:
        record['state']='rejected' if result.get('code') not in (None,0) else 'submission_unknown'
        record['response_code']=result.get('code');save(p,record);raise RunningHubError('No taskId returned. Check RunningHub history before resubmitting.')
    record.update(state='submitted',taskId=str(task));save(p,record);return record

def poll(client,journal,timeout=900,interval=10):
    p=Path(journal);r=json.loads(p.read_text());task=r.get('taskId')
    if not task:raise RunningHubError('No confirmed taskId; reconcile remote history')
    deadline=time.monotonic()+timeout
    while True:
        result=client.query(task);status=result.get('status') or (result.get('data') or {}).get('status')
        if status in ['SUCCESS','SUCCEEDED','COMPLETED']:
            if not result.get('results'):raise RunningHubError('Task reported success without downloadable results')
            r.update(state='success',results=result['results'],usage=result.get('usage'),completed_at=time.time());save(p,r);return r
        if status in ['FAILED','FAILURE','CANCELED','CANCELLED','ERROR']:
            r.update(state='failed',errorCode=result.get('errorCode'));save(p,r);raise RunningHubError('Task failed: '+str(result.get('errorCode','unknown')))
        if status not in ['RUNNING','QUEUED','PENDING','WAITING']:
            raise RunningHubError('Unknown task status; journal retained, do not resubmit')
        if time.monotonic()>=deadline:
            r.update(state='waiting',last_status=status);save(p,r);raise RunningHubError('Polling timed out; task may continue remotely. Resume the same journal.')
        time.sleep(min(interval,max(0,deadline-time.monotonic())))

def download(journal,out):
    r=json.loads(Path(journal).read_text())
    if r.get('state')!='success':raise RunningHubError('Download requires confirmed success')
    out=Path(out);out.mkdir(parents=True,exist_ok=True);items=[]
    for i,item in enumerate(r['results']):
        url=item.get('url') or item.get('fileUrl')
        if not url or not url.startswith('https://'):raise RunningHubError('Result must be an HTTPS URL')
        ext=str(item.get('outputType','bin')).lower().lstrip('.')
        if ext not in ['mp4','mov','webm','png','jpg','jpeg','wav','mp3','webp']:ext='bin'
        dest=out/f'result-{i:02d}.{ext}';tmp=dest.with_suffix(dest.suffix+'.part')
        # No API Authorization on storage downloads.
        with urllib.request.urlopen(url,timeout=90) as stream,tmp.open('wb') as f:
            while True:
                chunk=stream.read(1024*1024)
                if not chunk:break
                f.write(chunk)
        tmp.replace(dest);items.append({'file':dest.name,'bytes':dest.stat().st_size,'sha256':hashlib.sha256(dest.read_bytes()).hexdigest()})
    save(out/'download-manifest.json',items);return items

def model_run(client,job,journal):
    """One model task from local assets; resume uses rh-poll, never this function."""
    p=Path(journal)
    if p.exists():raise RunningHubError('Existing model journal: resume with rh-poll; never create another task automatically')
    endpoint=job.get('endpoint','')
    if endpoint!='alibaba/wan-3.0/reference-to-video':raise ValueError('This profile supports only alibaba/wan-3.0/reference-to-video')
    settings=dict(job['settings']);duration=int(settings['duration']);settings['duration']=str(duration)
    refs=job.get('video_paths',[]);imgs=job.get('image_paths',[])
    conditioning=job.get('conditioning','reference_video_and_product')
    if conditioning not in ['reference_video_and_product','storyboard_and_product']:raise ValueError('Unknown conditioning mode')
    if not imgs or len(refs)>5 or len(imgs)>10:raise ValueError('Require 1–10 product images and at most 5 reference videos')
    if conditioning=='reference_video_and_product' and not refs:raise ValueError('Video conditioning requires reference video; choose storyboard_and_product explicitly for agent-only reference analysis')
    if conditioning=='storyboard_and_product' and refs:raise ValueError('Storyboard conditioning must not send the original reference video')
    from media import probe
    ref_durations=[probe(v)['duration'] for v in refs]
    if any(not 1<=d<=15.05 for d in ref_durations) or sum(ref_durations)>15.05:raise ValueError('Reference videos must each be 1–15s, total <=15s')
    if sum(ref_durations)+duration>30.05:raise ValueError('Reference video duration + output duration exceeds 30s')
    if not 2<=duration<=30 or settings.get('resolution') not in ['480P','720P','1080P']:raise ValueError('Unsupported model settings')
    if not job.get('prompt','').strip():raise ValueError('Prompt required')
    p.parent.mkdir(parents=True,exist_ok=True)
    record={'state':'uploading','endpoint':endpoint,'created_at':time.time(),'taskId':None,'conditioning':conditioning,'input_counts':{'videos':len(refs),'images':len(imgs)},'reference_seen_by_model':bool(refs)}
    with p.open('x') as f:json.dump(record,f,indent=2)
    try:
        def upload_v2(path):
            asset=Path(path)
            if not asset.is_file() or asset.stat().st_size>100*1024*1024:raise ValueError('Model upload input must be a file <=100MiB')
            boundary='----rh'+uuid.uuid4().hex
            name=asset.name.replace('"','_').replace('\n','_').replace('\r','_')
            body=f'--{boundary}\r\nContent-Disposition: form-data; name="file"; filename="{name}"\r\nContent-Type: {mimetypes.guess_type(name)[0] or "application/octet-stream"}\r\n\r\n'.encode()+asset.read_bytes()+f'\r\n--{boundary}--\r\n'.encode()
            result=client.request('/openapi/v2/media/upload/binary',body=body,content_type='multipart/form-data; boundary='+boundary)
            if result.get('code')!=0 or not result.get('data',{}).get('download_url'):raise RunningHubError('V2 upload did not return download_url')
            return result['data']['download_url']
        payload=dict(settings,prompt=job['prompt'],videoUrls=[upload_v2(v) for v in refs],imageUrls=[upload_v2(v) for v in imgs])
        record.update(state='submitting',request_sha256=hashlib.sha256(json.dumps(payload,sort_keys=True).encode()).hexdigest());save(p,record)
        result=client.request('/openapi/v2/'+endpoint,payload)
        task=result.get('taskId') or (result.get('data') or {}).get('taskId')
        if not task:
            record['state']='rejected' if result.get('errorCode') or result.get('code') not in [None,0] else 'submission_unknown';save(p,record)
            raise RunningHubError('Model returned no taskId; reconcile remote history before any retry')
        record.update(state='submitted',taskId=str(task));save(p,record);return record
    except Exception:
        if record['state']=='submitting':record['state']='submission_unknown'
        elif record['state']=='uploading':record['state']='upload_failed'
        save(p,record);raise
