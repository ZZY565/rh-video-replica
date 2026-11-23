"""Deterministic media evidence and rendering; Python 3.10+, Pillow, imageio-ffmpeg."""
import hashlib, json, math, os, re, shutil, subprocess
from pathlib import Path
from PIL import Image, ImageOps, ImageDraw, ImageFont

def ffmpeg():
    if os.getenv('FFMPEG_BINARY'): return os.environ['FFMPEG_BINARY']
    if shutil.which('ffmpeg'): return shutil.which('ffmpeg')
    import imageio_ffmpeg
    return imageio_ffmpeg.get_ffmpeg_exe()

def run(args, check=True):
    r=subprocess.run([ffmpeg(),'-hide_banner','-nostdin',*map(str,args)],capture_output=True)
    if check and r.returncode: raise RuntimeError(r.stderr.decode(errors='replace')[-4000:])
    return r

def save(path,obj):
    p=Path(path);p.parent.mkdir(parents=True,exist_ok=True)
    tmp=p.with_suffix(p.suffix+'.tmp');tmp.write_text(json.dumps(obj,ensure_ascii=False,indent=2));tmp.replace(p)

def probe(path):
    p=Path(path)
    r=run(['-i',p],False).stderr.decode(errors='replace')
    t=re.search(r'Duration: (\d+):(\d+):([\d.]+)',r)
    if not t: raise ValueError('Cannot probe media duration: '+str(p))
    duration=int(t[1])*3600+int(t[2])*60+float(t[3])
    v=next((x for x in r.splitlines() if 'Video:' in x),'')
    dim=re.search(r'\b(\d{2,5})x(\d{2,5})\b',v)
    fps=re.search(r'([\d.]+) fps',v)
    digest=hashlib.sha256()
    with p.open('rb') as stream:
        for chunk in iter(lambda: stream.read(1024*1024),b''): digest.update(chunk)
    return dict(file=p.name,bytes=p.stat().st_size,sha256=digest.hexdigest(),duration=duration,width=int(dim[1]) if dim else None,height=int(dim[2]) if dim else None,fps=float(fps[1]) if fps else None,audio=any('Audio:' in x for x in r.splitlines()),video_stream=v.strip())

def frame(path,t,out):
    run(['-y','-ss',f'{t:.4f}','-i',path,'-frames:v','1','-update','1',out])

def font(size):
    candidates=[os.getenv('VIDEO_FONT',''),'/System/Library/Fonts/PingFang.ttc','/System/Library/Fonts/Supplemental/Arial Unicode.ttf','/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf']
    for f in candidates:
        if f and Path(f).is_file(): return ImageFont.truetype(f,size)
    return ImageFont.load_default()

def prepare(source,out,interval=.5):
    out=Path(out);out.mkdir(parents=True,exist_ok=True); m=probe(source)
    if interval<=0 or not math.isfinite(interval): raise ValueError('interval must be positive')
    if m['duration']>60: raise ValueError('prepare accepts references up to 60 seconds; split long videos first')
    interval=max(interval,m['duration']/120)
    times=[round(i*interval,4) for i in range(max(1,math.ceil(m['duration']/interval)))]
    shots=run(['-i',source,'-vf',"select='gt(scene,0.32)',showinfo",'-an','-f','null','-']).stderr.decode(errors='replace')
    cuts=[float(x) for x in re.findall(r'pts_time:([\d.]+)',shots)]
    evidence=[]; cols=5; tw=240; th=round(tw*m['height']/m['width'])+38
    sheet=Image.new('RGB',(cols*tw,math.ceil(len(times)/cols)*th),'#121b1b');d=ImageDraw.Draw(sheet)
    for i,t in enumerate(times):
        fn=f'frame-{i:03d}.jpg';frame(source,t,out/fn)
        im=Image.open(out/fn).convert('RGB');im.thumbnail((tw-12,th-38))
        x=(i%cols)*tw+(tw-im.width)//2;y=(i//cols)*th
        sheet.paste(im,(x,y));d.text(((i%cols)*tw+10,y+th-30),f'{i:02d} / {t:.2f}s',font=font(16),fill='#ecd2a0')
        evidence.append(dict(frame=fn,time=t))
    sheet.save(out/'contact-sheet.jpg',quality=92)
    result=dict(media=m,sampling_interval=interval,frames=evidence,cut_candidates=cuts,audio_status='audio present; not transcribed' if m['audio'] else 'no audio stream',analysis_method='FFmpeg scene change candidates + sampled image evidence; semantic interpretation belongs to agent review',motion_limit='Sub-frame actions cannot be established from sampled frames alone')
    save(out/'evidence.json',result);return result

def validate_plan(plan):
    w,h=plan['width'],plan['height'];fps=plan['fps']
    if not all(isinstance(n,int) and n>0 for n in [w,h,fps]) or w%2 or h%2: raise ValueError('Even positive dimensions and positive integer fps required')
    if not 1<=fps<=60 or max(w,h)>3840: raise ValueError('Renderer supports up to 3840 pixels and 60fps')
    if not plan.get('shots'): raise ValueError('Empty timeline')
    total=0
    for s in plan['shots']:
        dur=s['duration'];start=s.get('start',0)
        if not isinstance(dur,(int,float)) or not math.isfinite(dur) or not 0<dur<=60: raise ValueError('Invalid shot duration')
        if not isinstance(start,(int,float)) or not math.isfinite(start) or start<0: raise ValueError('Invalid start time')
        if abs(dur*fps-round(dur*fps))>1e-5: raise ValueError('Shot duration must align to the frame grid')
        if not Path(s['source']).is_file(): raise ValueError('Missing source: '+s['source'])
        if s['kind'] not in ['image','video']: raise ValueError('Unsupported shot type')
        if s['kind']=='image':
            for key,default in [('zoom_start',1.03),('zoom_end',1.09)]:
                z=s.get(key,default)
                if not isinstance(z,(int,float)) or not math.isfinite(z) or not 1<=z<=2:raise ValueError('Image zoom must be finite and between 1 and 2')
        if s['kind']=='video' and start+dur>probe(s['source'])['duration']+.025: raise ValueError('Video trim exceeds source duration')
        total+=dur
    if total>120: raise ValueError('Renderer supports up to 120s')
    if plan.get('music') and not Path(plan['music']).is_file(): raise ValueError('Missing music file')
    return total

def title_overlay(plan,s,out):
    w,h=plan['width'],plan['height'];im=Image.new('RGBA',(w,h));d=ImageDraw.Draw(im)
    if s.get('overlay',True) is False:
        im.save(out); return
    if s.get('layout')=='editorial':
        x=round(w*.065); y=round(h*.16)
        # Landscape product card: leave the product on the right unobscured.
        for xx in range(round(w*.56)):
            a=round(160*max(0,1-xx/(w*.56)))
            d.line((xx,0,xx,h),fill=(12,9,7,a))
        d.text((x,y),plan.get('brand',''),font=font(round(h*.037)),fill='#d8b680')
        y+=round(h*.105)
        for line in s.get('headline','').split('\n'):
            f=font(round(h*.072))
            if d.textbbox((0,0),line,font=f)[2]>w*.48: raise ValueError('Editorial headline exceeds left safe area')
            d.text((x,y),line,font=f,fill='#fff5e3'); y+=round(h*.105)
        if s.get('subline'): d.text((x,y+round(h*.025)),s['subline'],font=font(round(h*.027)),fill='#dfd0bd')
        d.text((x,round(h*.89)),plan.get('footer',''),font=font(round(h*.020)),fill='#baa991')
        im.save(out); return
    # Deliberate safe areas: 8% side, 12% top, 18% bottom for platform controls.
    x=round(w*.083);ink='#fff5e3';gold='#d8b680'
    if s.get('layout','top')=='bottom':
        for y in range(h):
            a=int(210*max(0,(y/h-.40)/.60));d.line((0,y,w,y),fill=(15,22,21,a))
        y=int(h*.60)
    else:
        for yy in range(int(h*.53)):
            a=int(200*max(0,1-yy/(h*.53)));d.line((0,yy,w,yy),fill=(15,22,21,a))
        y=int(h*.16)
    d.text((x,int(h*.085)),plan.get('brand',''),font=font(round(w*.029)),fill=gold,stroke_width=0)
    d.line((x,y-22,x+46,y-22),fill=gold,width=3)
    for line in s.get('headline','').split('\n'):
        f=font(round(w*.073));
        if d.textbbox((0,0),line,font=f)[2]>w-2*x: raise ValueError('Headline exceeds safe width; wrap text')
        d.text((x,y),line,font=f,fill=ink);y+=round(w*.10)
    if s.get('subline'):d.text((x,y+18),s['subline'],font=font(round(w*.028)),fill=ink)
    if s.get('cta'):
        yy=round(h*.77);cw=round(w*.42);d.rounded_rectangle((x,yy,x+cw,yy+round(h*.043)),radius=4,fill=gold)
        d.text((x+18,yy+8),s['cta'],font=font(round(w*.027)),fill='#152724')
    d.text((x,round(h*.875)),plan.get('footer',''),font=font(round(w*.019)),fill='#d9cbb7')
    im.save(out)

def render(plan,out):
    total=validate_plan(plan);out=Path(out);out.mkdir(parents=True,exist_ok=True)
    w,h,fps=plan['width'],plan['height'],plan['fps'];segments=[]
    for i,s in enumerate(plan['shots']):
        overlay=out/f'overlay-{i:02d}.png';title_overlay(plan,s,overlay);dur=s['duration'];n=round(dur*fps)
        if s['kind']=='image':
            inp=['-loop','1','-i',s['source']]
            zs=s.get('zoom_start',1.03);ze=s.get('zoom_end',1.09)
            vf=f"scale={w*2}:{h*2}:force_original_aspect_ratio=increase,crop={w*2}:{h*2},zoompan=z='{zs}+({ze}-{zs})*on/{max(n-1,1)}':x='iw/2-iw/zoom/2':y='ih/2-ih/zoom/2':d=1:s={w}x{h}:fps={fps}"
        else:
            inp=['-ss',s.get('start',0),'-i',s['source']]
            vf=f'scale={w}:{h}:force_original_aspect_ratio=increase,crop={w}:{h},fps={fps}'
        target=out/f'shot-{i:02d}.mp4';segments.append(target.resolve())
        run(['-y',*inp,'-loop','1','-i',overlay,'-filter_complex',f'[0:v]{vf},setsar=1[b];[b][1:v]overlay=0:0:shortest=1,format=yuv420p[v]','-map','[v]','-an','-t',dur,'-frames:v',n,'-c:v','libx264','-preset','fast','-crf','18',target])
    listing=out/'concat.txt'
    # FFmpeg concat syntax: reject ambiguous names rather than interpreting them.
    if any("'" in str(s) or '\n' in str(s) for s in segments):raise ValueError('Output path cannot contain quotes/newlines')
    listing.write_text(''.join("file '"+str(s)+"'\n" for s in segments))
    video=out/'picture.mp4';run(['-y','-f','concat','-safe','0','-i',listing,'-c','copy',video])
    final=out/'final.mp4'
    if plan.get('music'):
        run(['-y','-i',video,'-i',plan['music'],'-map','0:v:0','-map','1:a:0','-c:v','copy','-af',f'loudnorm=I=-18:TP=-1.5:LRA=9,afade=t=in:d=0.3,afade=t=out:st={max(0,total-.8)}:d=0.8','-c:a','aac','-b:a','192k','-ar','48000','-t',total,'-movflags','+faststart',final])
    else:run(['-y','-i',video,'-c','copy','-movflags','+faststart',final])
    qc=quality(final,total);save(out/'qc.json',qc)
    if not qc['passed']: raise RuntimeError('Rendered video failed technical QC')
    return qc

def quality(path,expected=None):
    m=probe(path);r=run(['-v','error','-i',path,'-map','0:v:0','-map','0:a?','-f','null','-'],False)
    log=run(['-i',path,'-af','volumedetect','-vn','-f','null','-'],False).stderr.decode(errors='replace') if m['audio'] else ''
    black=run(['-i',path,'-vf','blackdetect=d=0.1:pix_th=0.1','-an','-f','null','-']).stderr.decode(errors='replace')
    blacks=[dict(start=float(a),end=float(b),duration=float(c)) for a,b,c in re.findall(r'black_start:([\d.]+) black_end:([\d.]+) black_duration:([\d.]+)',black)]
    duration_ok=expected is None or abs(m['duration']-expected)<=.08
    return dict(media=m,full_decode_exit_code=r.returncode,decode_errors=r.stderr.decode(errors='replace'),expected_duration=expected,duration_ok=duration_ok,black_intervals=blacks,volume=[x.strip() for x in log.splitlines() if 'mean_volume:' in x or 'max_volume:' in x],passed=r.returncode==0 and duration_ok and not blacks,semantic_review='requires human or agent viewing; technical pass alone is not visual approval')
