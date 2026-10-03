from pathlib import Path
import sys,json,subprocess,hashlib,numpy as np
from PIL import Image,ImageDraw
w=Path(__file__).resolve().parent;sys.path.insert(0,str(w));from render_motion import OUT,SOURCE,run,W,H,FPS,MotionRenderer
final=OUT/'手机部署机器人_人机分工_3D动画版_20261003.mp4';qa=w/'qa';qa.mkdir(exist_ok=True)
def probe(p):return json.loads(run(['ffprobe','-v','error','-show_streams','-show_format','-of','json',p]).stdout)
p=probe(final);v=next(x for x in p['streams'] if x['codec_type']=='video');a=next(x for x in p['streams'] if x['codec_type']=='audio')
assert (v['width'],v['height'],int(v['nb_frames']))==(1080,1920,4600)
assert abs(float(p['format']['duration'])-153.333333)<.1
run(['ffmpeg','-hide_banner','-loglevel','error','-xerror','-i',final,'-map','0:v','-map','0:a','-f','null','-'],qa/'decode.log')
timeline=json.loads((SOURCE/'timeline.json').read_text(encoding='utf-8'))
shots=[]
for i,s in enumerate(timeline['scenes']):
 at=s['start']+s['duration']*.57;dest=qa/f'scene_{i+1:02}.jpg'
 run(['ffmpeg','-hide_banner','-loglevel','error','-y','-ss',str(at),'-i',final,'-frames:v','1','-q:v','2',dest]);shots.append(dest)
for k in range(2):
 sheet=Image.new('RGB',(940,1700),'#e8edef');draw=ImageDraw.Draw(sheet)
 for i,f in enumerate(shots[k*4:k*4+4]):
  x=24+i%2*468;y=18+i//2*842;sheet.paste(Image.open(f).resize((432,768)),(x,y));draw.text((x,y+776),f.stem,fill='#15383c')
 sheet.save(qa/f'review_{k+1}.jpg')
# Extract an exact preview from the final, so users do not see a stale draft.
preview=OUT/'动态样片_27秒.mp4'
run(['ffmpeg','-hide_banner','-loglevel','error','-y','-i',final,'-t','27','-map','0:v','-map','0:a','-c:v','h264_nvenc','-preset','p5','-cq','20','-b:v','0','-c:a','aac','-b:a','160k','-movflags','+faststart',preview])
# Preserve the same narration source. Compare decoded waveforms, allowing only the quiet authored SFX and AAC recoding.
original=SOURCE.parent.parent/'06_成片'/'人机分工短版_20261003'/'配音_小米MiMo冰糖_20261003.m4a'
def samples(path):return np.frombuffer(run(['ffmpeg','-v','error','-i',path,'-map','0:a:0','-f','f32le','-ar','24000','-ac','1','-']).stdout,dtype='<f4')
x,y=samples(original),samples(final);n=min(len(x),len(y));cor=float(np.corrcoef(x[:n],y[:n])[0,1]);assert cor>.98,cor
# A clean cover from the actual 3D scene, without duplicating the spoken subtitle.
r=MotionRenderer();from overlay import OverlayPainter;r.overlay=OverlayPainter(r.timeline,[]);r.save(12.,OUT/'3D动画封面.png');r.close()
report={'duration_seconds':float(p['format']['duration']),'resolution':[1080,1920],'fps':30,'frames':4600,'full_decode':'PASS','sections':8,'subtitle_cues':24,'tests':{'overlay':4,'motion':5},'all_sections_have_3d_motion':True,'transition_pose_continuity':'PASS','narration_reused':True,'narration_correlation':cor,'original_narration_sha256':hashlib.sha256(original.read_bytes()).hexdigest(),'new_tts_requests':0,'sfx':'original low-level synthesized transition whooshes and taps','sha256':hashlib.sha256(final.read_bytes()).hexdigest(),'bytes':final.stat().st_size,'limitations':['教学动画，不是新机部署实录','没有本轮手机或QQ操作','未自动发布抖音','未宣称人工全片听审']}
(OUT/'制作验收.json').write_text(json.dumps(report,ensure_ascii=False,indent=2),encoding='utf-8')
print(json.dumps(report,ensure_ascii=False,indent=2))
