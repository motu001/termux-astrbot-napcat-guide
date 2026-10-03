"""Resumable local tutorial production. Never stores or logs TTS credentials.
Run sample -> audio -> graphics -> render -> assemble -> verify.
Requires Python, Pillow, numpy, FFmpeg and the already configured MiMo TTS skill.
"""
from __future__ import annotations
import argparse, concurrent.futures as cf, hashlib, json, math, os, re, shutil
import subprocess, sys, threading, time, wave
from pathlib import Path
import numpy as np
from PIL import ImageFont

if hasattr(sys.stdout, 'reconfigure'):
    sys.stdout.reconfigure(encoding='utf-8')

WORK = Path(__file__).resolve().parent
ROOT = WORK.parent.parent
OUT = ROOT / '06_成片' / '完整教程_20261003'
TTS = Path(os.environ.get('MIMO_TTS_SCRIPT', str(Path.home() / '.codex' / 'skills' / 'mimo-tts' / 'scripts' / 'tts.py')))
FPS, RATE, LEAD = 24, 24000, 0.20
VOICE = '冰糖'
STYLE = '清晰温和的中文教学讲解，耐心地对第一次操作手机的新手说话。中等偏慢的自然语速，步骤之间稍作停顿，专业英文读得清楚，不夸张，不朗诵，不添加文字之外的话。'
MODEL = 'mimo-v2.5-tts'
STEM = '手机部署机器人_完整详细教程_竖屏_20261003'
LOCK = threading.Lock()

def save_json(path, obj):
    path = Path(path); path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_name(path.name + '.tmp')
    tmp.write_text(json.dumps(obj, ensure_ascii=False, indent=2), encoding='utf-8')
    os.replace(tmp, path)

def load_json(path, default=None):
    return json.loads(Path(path).read_text(encoding='utf-8-sig')) if Path(path).exists() else default

def run(args, cwd=None, timeout=300, log=None):
    if cwd is None: cwd = WORK
    p = subprocess.run([str(x) for x in args], cwd=cwd, capture_output=True, timeout=timeout)
    if log: Path(log).write_bytes(p.stderr)
    if p.returncode:
        raise RuntimeError(f'Local command failed ({Path(str(args[0])).name}, exit={p.returncode}); see local diagnostic file if provided')
    return p

def probe(path):
    return json.loads(run(['ffprobe','-v','error','-show_format','-show_streams','-of','json',path]).stdout)

def digest_scene(scene):
    return hashlib.sha256(json.dumps([MODEL,VOICE,STYLE,scene['speech']], ensure_ascii=False).encode()).hexdigest()

def scenes():
    data = load_json(WORK/'scenes.json')
    if not data or not data.get('scenes'): raise RuntimeError('scenes.json is not ready')
    expected = [c['id'] for c in data['chapters']]
    transitions = []
    for item in data['scenes']:
        if not transitions or transitions[-1] != item['chapter']:
            transitions.append(item['chapter'])
    if transitions != expected:
        raise RuntimeError('Chapter order must be contiguous and match the declared unique chapter index')
    ids = [s['id'] for s in data['scenes']]
    if len(ids) != len(set(ids)): raise RuntimeError('Duplicate scene IDs')
    for s in data['scenes']:
        if not re.fullmatch(r'\d{3}',s['id']): raise RuntimeError('Unsafe scene ID')
        if not s['speech'].strip(): raise RuntimeError(f"Empty speech: {s['id']}")
        if len(s.get('bullets',[])) > 3: raise RuntimeError(f"Too many bullets: {s['id']}")
    return data

def inspect_wav(path):
    with wave.open(str(path),'rb') as w:
        channels, width, rate, frames = w.getnchannels(), w.getsampwidth(), w.getframerate(), w.getnframes()
        if (channels,width,rate)!=(1,2,RATE): raise RuntimeError(f'Unexpected WAV format: {Path(path).name}')
        pcm = np.frombuffer(w.readframes(frames),dtype='<i2').astype(np.float64)
    if frames < RATE or not pcm.size or np.max(np.abs(pcm)) < 200:
        raise RuntimeError(f'Short or silent WAV: {Path(path).name}')
    return {'duration': frames/rate, 'sample_rate':rate, 'channels':channels,
            'peak_dbfs':float(20*np.log10(max(1,np.max(np.abs(pcm)))/32768)),
            'rms_dbfs':float(20*np.log10(max(1,np.sqrt(np.mean(pcm**2)))/32768))}

def synth_one(s, manifest, stopped):
    sid=s['id']; target=WORK/'audio'/f'{sid}.wav'; target.parent.mkdir(exist_ok=True)
    fp=digest_scene(s)
    if target.exists() and manifest.get(sid,{}).get('fingerprint')==fp:
        info=inspect_wav(target); return sid, info, True
    if stopped.is_set(): return sid, None, False
    temp=target.with_name(sid+'.pending.wav')
    print(f"TTS {sid}: {s['title']}",flush=True)
    # Capture provider diagnostics; do not print or persist response bodies or keys.
    try:
        result=subprocess.run([sys.executable,str(TTS),s['speech'],'--voice',VOICE,
                               '--style',STYLE,'--format','wav','--out',str(temp)],
                              capture_output=True,timeout=150)
        if result.returncode:
            stopped.set()
            status=re.search(rb'HTTP (\d{3})', result.stderr)
            label=('HTTP '+status.group(1).decode()) if status else 'provider or transport error'
            raise RuntimeError(f'TTS scene {sid} failed: {label}; no automatic retry')
        info=inspect_wav(temp); os.replace(temp,target)
    except Exception:
        stopped.set(); raise
    with LOCK:
        manifest[sid]={'fingerprint':fp, **info, 'file':str(target.relative_to(WORK))}
        save_json(WORK/'audio_manifest.json',manifest)
    return sid, info, False

def do_audio(limit=None, workers=2):
    data=scenes(); selected=data['scenes'][:limit] if limit else data['scenes']
    if not TTS.exists(): raise RuntimeError('Configured MiMo TTS skill is missing')
    manifest=load_json(WORK/'audio_manifest.json',{})
    stopped=threading.Event()
    with cf.ThreadPoolExecutor(max_workers=workers) as pool:
        futures=[pool.submit(synth_one,s,manifest,stopped) for s in selected]
        done=0
        for future in cf.as_completed(futures):
            sid,info,cached=future.result()
            if info:
                done+=1; print(f"AUDIO {done}/{len(selected)} id={sid} seconds={info['duration']:.2f} cached={cached}",flush=True)
    if not limit: make_timeline(data)

def sample():
    if not TTS.exists(): raise RuntimeError('MiMo TTS skill is missing')
    scene={'id':'000','title':'讲解小样','speech':'一部安卓手机，也可以搭建自己的测试机器人。这期我们不跳步骤，从安装环境开始，一直讲到账号登录、模型连接和开机恢复。每一步都先确认在哪个窗口操作，再看真实的成功信号。画面是教学示意，不是实机成功录像。'}
    manifest=load_json(WORK/'audio_manifest.json',{})
    result=synth_one(scene,manifest,threading.Event())
    save_json(WORK/'sample_check.json',{'voice':VOICE,'model':MODEL,'audio':result[1],
              'note':'结构/非静音检查完成；不是人工听审或ASR校验。'})
    print(json.dumps(result[1],ensure_ascii=False),flush=True)

def make_timeline(data=None):
    data=data or scenes(); manifest=load_json(WORK/'audio_manifest.json',{})
    cursor=0; items=[]; chapters=[]
    for s in data['scenes']:
        info=manifest.get(s['id'])
        if not info or info.get('fingerprint')!=digest_scene(s): raise RuntimeError('Audio missing/stale: '+s['id'])
        nframes=math.ceil((info['duration']+LEAD+.45)*FPS)
        duration=nframes/FPS
        if not chapters or chapters[-1]['id']!=s['chapter']:
            chapters.append({'id':s['chapter'],'title':s['chapter_title'],'start_frame':cursor,'start':cursor/FPS})
        items.append({'id':s['id'],'chapter':s['chapter'],'title':s['title'],'start':cursor/FPS,
                      'start_frame':cursor,'duration':duration,'frames':nframes,'voice_duration':info['duration']})
        cursor+=nframes
    for i,c in enumerate(chapters): c['end']=chapters[i+1]['start'] if i+1<len(chapters) else cursor/FPS
    timeline={'fps':FPS,'duration':cursor/FPS,'frames':cursor,'scenes':items,'chapters':chapters}
    save_json(WORK/'timeline.json',timeline); return timeline

def wrap_caption(text, width=785):
    font=ImageFont.truetype('C:/Windows/Fonts/msyh.ttc',44)
    # Keep complete Latin technical names and addresses on one line when possible.
    pattern=r'[A-Za-z0-9]+(?:[._/+:-][A-Za-z0-9]+)*|.'
    tokens=re.findall(pattern,text,flags=re.S)
    lines=[]; line=''
    for token in tokens:
        pieces=[token] if font.getlength(token)<=width else list(token)
        for piece in pieces:
            if font.getlength(line+piece)>width and line:
                if piece in '，。！？；：、,.!?;:' and len(line)>1:
                    tail=line[-1];lines.append(line[:-1]);line=tail+piece
                else:
                    lines.append(line);line=piece
            else:line+=piece
    if line:lines.append(line)
    if len(lines)==2 and font.getlength(lines[1])<width*.40:
        joined=''.join(lines);candidates=[]
        positions=[m.end() for m in re.finditer(pattern,joined,flags=re.S)]
        for i in positions[:-1]:
            left,right=joined[:i],joined[i:]
            lw,rw=font.getlength(left),font.getlength(right)
            if max(lw,rw)>width or right[0] in '，。！？；：、,.!?;:':continue
            penalty=0 if left[-1] in '，。！？；：、,.!?;:' else 50
            candidates.append((abs(lw-rw)+penalty,left,right))
        if candidates:
            _,left,right=min(candidates);lines=[left,right]
    return lines

def caption_chunks(text):
    # Preserve sentence boundaries; split a long sentence at its natural phrases.
    sentences=re.findall(r'[^。！？；!?;]+[。！？；!?;]?',text)
    out=[]
    for sentence in sentences:
        phrases=re.findall(r'[^，：,:]+[，：,:]?',sentence)
        pending=''
        for phrase in phrases:
            if len(wrap_caption(pending+phrase))<=2:
                pending+=phrase
            else:
                if pending:out.append(pending)
                lines=wrap_caption(phrase)
                while len(lines)>2:
                    out.append(''.join(lines[:2]));lines=lines[2:]
                pending=''.join(lines)
        if pending:out.append(pending)
    return out or [text]

def spoken_weight(text):
    tokens=re.findall(r'[A-Za-z][A-Za-z0-9_.+-]*|\d|[\u3400-\u9fff]|[，。！？；：,.!?;:]',text)
    return sum(max(1,len(t)*.42) if t.isascii() and t[0].isalnum() else (.42 if t in '，。！？；：,.!?;:' else 1) for t in tokens) or 1

def pause_times(path):
    with wave.open(str(path),'rb') as w: arr=np.frombuffer(w.readframes(w.getnframes()),dtype='<i2').astype(np.float64)
    n=480; arr=arr[:len(arr)//n*n].reshape(-1,n); rms=np.sqrt((arr**2).mean(axis=1))
    threshold=max(35,float(np.percentile(rms,80))*.05); quiet=rms<threshold
    out=[]; start=None
    for i,value in enumerate(list(quiet)+[False]):
        if value and start is None:start=i
        if not value and start is not None:
            if i-start>=7: out.append((start+i)*.01)
            start=None
    return out

def caption_events(s, item):
    chunks=caption_chunks(s['speech']); weights=[spoken_weight(x) for x in chunks]
    cumulative=np.cumsum(weights)/sum(weights)*item['voice_duration']
    pauses=pause_times(WORK/'audio'/f"{s['id']}.wav")
    edges=[0.0]
    for expected in cumulative[:-1]:
        candidates=[p for p in pauses if abs(p-expected)<.8 and p>edges[-1]+.65 and p<item['voice_duration']-.65]
        edge=min(candidates,key=lambda p:abs(p-expected)) if candidates else float(expected)
        edges.append(max(edges[-1]+.05,edge))
    edges.append(item['voice_duration'])
    return [{'start':a+LEAD,'end':b+LEAD,'text':'\n'.join(wrap_caption(t))} for a,b,t in zip(edges,edges[1:],chunks)]

def ass_time(t):
    n=round(t*100); return f'{n//360000}:{n//6000%60:02}:{n//100%60:02}.{n%100:02}'

def srt_time(t):
    n=round(t*1000); return f'{n//3600000:02}:{n//60000%60:02}:{n//1000%60:02},{n%1000:03}'

ASS_HEADER='''[Script Info]\nScriptType: v4.00+\nPlayResX: 1080\nPlayResY: 1920\nWrapStyle: 2\nScaledBorderAndShadow: yes\n\n[V4+ Styles]\nFormat: Name, Fontname, Fontsize, PrimaryColour, SecondaryColour, OutlineColour, BackColour, Bold, Italic, Underline, StrikeOut, ScaleX, ScaleY, Spacing, Angle, BorderStyle, Outline, Shadow, Alignment, MarginL, MarginR, MarginV, Encoding\nStyle: Default,Microsoft YaHei,44,&H00F5F8FA,&H00F5F8FA,&H002B1C10,&H80000000,0,0,0,0,100,100,0,0,1,2,0,7,78,175,20,1\n\n[Events]\nFormat: Layer, Start, End, Style, Name, MarginL, MarginR, MarginV, Effect, Text\n'''

def do_graphics():
    import render_cards
    data=scenes(); timeline=make_timeline(data); cards=WORK/'cards'; captions=WORK/'captions'
    cards.mkdir(exist_ok=True); captions.mkdir(exist_ok=True); OUT.mkdir(parents=True,exist_ok=True)
    report=[]; all_events=[]
    for index,(s,item) in enumerate(zip(data['scenes'],timeline['scenes'])):
        for phase in range(3):
            report.append(render_cards.render_scene(s,cards/f"{s['id']}_p{phase}.png",phase,index,len(data['scenes'])))
        events=caption_events(s,item); lines=[]
        for event in events:
            text=event['text'].replace('\\','＼').replace('{','｛').replace('}','｝').replace('\n',r'\N')
            lines.append(f"Dialogue: 0,{ass_time(event['start'])},{ass_time(event['end'])},Default,,0,0,0,,{{\\an7\\pos(78,1494)}}{text}")
            all_events.append({**event,'start':event['start']+item['start'],'end':event['end']+item['start']})
        (captions/f"{s['id']}.ass").write_text(ASS_HEADER+'\n'.join(lines)+'\n',encoding='utf-8')
    save_json(WORK/'layout_report.json',report); save_json(WORK/'subtitle_events.json',all_events)
    srt='\n\n'.join(f"{i+1}\n{srt_time(e['start'])} --> {srt_time(e['end'])}\n{e['text']}" for i,e in enumerate(all_events))+'\n'
    srt='\n'.join(line.rstrip() for line in srt.splitlines()).rstrip()+'\n'
    (OUT/f'{STEM}.srt').write_text(srt,encoding='utf-8')
    if hasattr(render_cards,'render_cover'): render_cards.render_cover(OUT/'封面.png')
    print(f"GRAPHICS: {len(data['scenes'])} scenes, {len(all_events)} phrase captions",flush=True)

def encoder_args(encoder):
    if encoder=='h264_nvenc': return ['-c:v','h264_nvenc','-preset','p4','-tune','hq','-rc','vbr','-cq','23','-b:v','0']
    return ['-c:v','libx264','-preset','veryfast','-crf','22','-threads','4']

def choose_encoder():
    p=subprocess.run(['ffmpeg','-hide_banner','-loglevel','error','-f','lavfi','-i','color=s=1080x1920:r=24:d=0.3',
                      '-c:v','h264_nvenc','-f','null','-'],capture_output=True,timeout=30)
    return 'h264_nvenc' if p.returncode==0 else 'libx264'

def render_one(s,item,encoder):
    folder=WORK/'clips'; folder.mkdir(exist_ok=True); target=folder/f"{s['id']}.mp4"
    inputs=[WORK/'cards'/f"{s['id']}_p{i}.png" for i in range(3)]+[WORK/'captions'/f"{s['id']}.ass"]
    fp=hashlib.sha256(b''.join(p.read_bytes() for p in inputs)+str(item['frames']).encode()+encoder.encode()+b'v3').hexdigest()
    stamp=target.with_suffix('.sha256')
    if target.exists() and stamp.exists() and stamp.read_text()==fp:return s['id'],True
    listing=WORK/'clips'/f"{s['id']}.ffconcat"
    parts=['ffconcat version 1.0']
    frames=[item['frames']//3,item['frames']//3,item['frames']-2*(item['frames']//3)]
    for i,count in enumerate(frames):
        parts += [f"file '../cards/{s['id']}_p{i}.png'",f'duration {count/FPS:.8f}']
    parts.append(f"file '../cards/{s['id']}_p2.png'")
    listing.write_text('\n'.join(parts)+'\n',encoding='utf-8')
    vf=f"fps={FPS},drawbox=x=60:y=1464:w=846:h=216:color=0x071522@0.90:t=fill,ass=captions/{s['id']}.ass,format=yuv420p"
    pending=target.with_name(s['id']+'.pending.mp4')
    run(['ffmpeg','-hide_banner','-loglevel','warning','-y','-f','concat','-safe','0','-i',listing,
         '-vf',vf,'-frames:v',str(item['frames']),*encoder_args(encoder),'-g','48','-pix_fmt','yuv420p',
         '-an','-movflags','+faststart',pending],timeout=1200,log=WORK/'clips'/f"{s['id']}.render.log")
    os.replace(pending,target);stamp.write_text(fp);return s['id'],False

def do_render(limit=None,workers=2):
    data=scenes(); timeline=make_timeline(data); selected=list(zip(data['scenes'],timeline['scenes']))
    if limit:selected=selected[:limit]
    encoder=choose_encoder(); print('ENCODER '+encoder,flush=True)
    save_json(WORK/'render_settings.json',{'encoder':encoder,'fps':FPS,'width':1080,'height':1920,'subtitle_timing':'phrase-weighted, silence-adjusted; not ASR forced alignment'})
    with cf.ThreadPoolExecutor(max_workers=workers) as pool:
        futures=[pool.submit(render_one,s,i,encoder) for s,i in selected]
        for n,future in enumerate(cf.as_completed(futures)):
            sid,cached=future.result();print(f'VIDEO {n+1}/{len(selected)} id={sid} cached={cached}',flush=True)

def master_wav(timeline):
    target=WORK/'narration_master.wav'
    with wave.open(str(target),'wb') as out:
        out.setnchannels(1);out.setsampwidth(2);out.setframerate(RATE)
        for item in timeline['scenes']:
            with wave.open(str(WORK/'audio'/f"{item['id']}.wav"),'rb') as w:
                pcm=w.readframes(w.getnframes())
            total=round(item['duration']*RATE);lead=round(LEAD*RATE);tail=total-lead-len(pcm)//2
            if tail<0:raise RuntimeError('Audio would be truncated')
            out.writeframes(b'\0'*(lead*2)+pcm+b'\0'*(tail*2))
    return target

def chapter_metadata(timeline):
    lines=[';FFMETADATA1','title=用手机部署机器人｜完整详细教程','comment=教学示意，非实机录屏；小米 MiMo TTS 合成讲解']
    for c in timeline['chapters']:
        title=c['title'].replace('=','\\=').replace(';','\\;').replace('#','\\#').replace('\n',' ')
        lines += ['[CHAPTER]','TIMEBASE=1/1000',f"START={round(c['start']*1000)}",f"END={round(c['end']*1000)}",f"title={c['id']} {title}"]
    path=WORK/'chapters.ffmetadata';path.write_text('\n'.join(lines)+'\n',encoding='utf-8');return path

def do_assemble(export_chapters=True):
    OUT.mkdir(parents=True,exist_ok=True);timeline=make_timeline();wav=master_wav(timeline)
    audio=OUT/'配音_小米MiMo冰糖_20261003.m4a'
    run(['ffmpeg','-hide_banner','-loglevel','info','-y','-i',wav,'-af','loudnorm=I=-16:TP=-1.5:LRA=9:print_format=json',
         '-ar','48000','-c:a','aac','-b:a','160k','-movflags','+faststart',audio],timeout=1200,log=WORK/'audio_loudnorm.log')
    listing=WORK/'all_clips.ffconcat'
    listing.write_text('ffconcat version 1.0\n'+''.join(f"file 'clips/{s['id']}.mp4'\n" for s in timeline['scenes']),encoding='utf-8')
    metadata=chapter_metadata(timeline); final=OUT/f'{STEM}.mp4'
    run(['ffmpeg','-hide_banner','-loglevel','warning','-y','-f','concat','-safe','0','-i',listing,'-i',audio,'-i',metadata,
         '-map','0:v:0','-map','1:a:0','-map_metadata','2','-map_chapters','2','-c','copy','-t',f"{timeline['duration']:.8f}",
         '-movflags','+faststart',final],timeout=600,log=WORK/'mux.log')
    marks=['# 视频章节时间表','','本版为全流程教学示意，不是全新手机端到端成功实录。','']
    for c in timeline['chapters']:
        marks.append(f"- **{srt_time(c['start']).replace(',', '.')}**　{c['id']}　{c['title']}")
    (OUT/'章节时间表.md').write_text('\n'.join(marks)+'\n',encoding='utf-8')
    save_json(OUT/'章节时间表.json',timeline['chapters'])
    if export_chapters:
        folder=OUT/'分章视频';folder.mkdir(exist_ok=True)
        for c in timeline['chapters']:
            title=re.sub(r'[<>:"/\\|?*]','_',c['title']);dest=folder/f"{c['id']}_{title}.mp4"
            run(['ffmpeg','-hide_banner','-loglevel','warning','-y','-ss',str(c['start']),'-i',final,
                 '-t',str(c['end']-c['start']),'-map','0:v:0','-map','0:a:0','-c:v','copy','-c:a','aac','-b:a','160k',
                 '-map_chapters','-1','-avoid_negative_ts','make_zero','-movflags','+faststart',dest],timeout=300,
                 log=WORK/f"chapter_{c['id']}.log")
    print(f'ASSEMBLED {final} seconds={timeline["duration"]:.3f}',flush=True)

def verify():
    timeline=load_json(WORK/'timeline.json');final=OUT/f'{STEM}.mp4';info=probe(final)
    video=next(s for s in info['streams'] if s['codec_type']=='video');audio=next(s for s in info['streams'] if s['codec_type']=='audio')
    assert (video['width'],video['height'])==(1080,1920)
    assert video['codec_name']=='h264' and audio['codec_name']=='aac'
    assert abs(float(info['format']['duration'])-timeline['duration'])<.2
    assert int(video['nb_frames'])==timeline['frames']
    qa=WORK/'qa';qa.mkdir(exist_ok=True)
    images=[]
    for c in timeline['chapters']:
        path=qa/f"chapter_{c['id']}.jpg";at=min(c['end']-.5,c['start']+4)
        run(['ffmpeg','-hide_banner','-loglevel','error','-y','-ss',str(at),'-i',final,'-frames:v','1','-q:v','2',path])
        images.append(path)
    from PIL import Image,ImageDraw
    for page in range(math.ceil(len(images)/6)):
        batch=images[page*6:page*6+6];sheet=Image.new('RGB',(1080,1340),'#eef1f5');d=ImageDraw.Draw(sheet)
        for i,path in enumerate(batch):
            thumb=Image.open(path).resize((324,576));x=20+(i%3)*356;y=18+(i//3)*666
            sheet.paste(thumb,(x,y));d.text((x,y+584),path.stem,fill='#102336')
        sheet.save(qa/f'contact_{page+1}.jpg')
    report={'status':'technical_checks_passed','final':str(final),'duration_seconds':float(info['format']['duration']),
            'video':{'codec':video['codec_name'],'width':video['width'],'height':video['height'],'frames':video['nb_frames'],'fps':video['avg_frame_rate']},
            'audio':{'codec':audio['codec_name'],'sample_rate':audio['sample_rate'],'channels':audio['channels']},
            'scene_count':len(timeline['scenes']),'chapter_count':len(timeline['chapters']),
            'subtitle_event_count':len(load_json(WORK/'subtitle_events.json',[])),
            'limitations':['教学示意而非全流程实机录像','短语字幕按实长和停顿估算，非ASR逐字强对齐','本报告不代表人工听审','未在本轮操作手机、登录账号、验证AI回复或整机自启']}
    save_json(OUT/'制作验收.json',report);print(json.dumps(report,ensure_ascii=False,indent=2))

if __name__=='__main__':
    parser=argparse.ArgumentParser();parser.add_argument('stage',choices=['sample','audio','graphics','render','assemble','verify','all'])
    parser.add_argument('--limit',type=int);parser.add_argument('--workers',type=int,default=2);parser.add_argument('--no-chapters',action='store_true')
    args=parser.parse_args()
    if args.workers not in [1,2]:raise SystemExit('Use only 1 or 2 workers')
    if args.stage=='sample':sample()
    if args.stage in ['audio','all']:do_audio(args.limit,args.workers)
    if args.stage in ['graphics','all']:do_graphics()
    if args.stage in ['render','all']:do_render(args.limit,args.workers)
    if args.stage in ['assemble','all']:do_assemble(not args.no_chapters)
    if args.stage in ['verify','all']:verify()
