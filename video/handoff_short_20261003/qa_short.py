"""Short-film checks, full decode and actual encoded-frame review sheets."""
from pathlib import Path
import json,re,hashlib
from PIL import Image,ImageDraw
import make_short as m
b=m.b;w=m.BASE;out=b.OUT
m.duration_guard();d=b.scenes();t=b.make_timeline();qa=w/'qa';qa.mkdir(exist_ok=True)
assert len(d['scenes'])==8 and len(t['chapters'])==2
for s in d['scenes']:
 ass=(w/'captions'/f"{s['id']}.ass").read_text(encoding='utf-8')
 lines=[ln.split(',',9)[-1] for ln in ass.splitlines() if ln.startswith('Dialogue:')]
 spoken=re.sub(r'\{[^}]*\}','', ''.join(lines)).replace(r'\N','')
 assert re.sub(r'\s','',spoken)==re.sub(r'\s','',s['speech']),s['id']
 b.inspect_wav(w/'audio'/f"{s['id']}.wav")
shots=[]
for s,item in zip(d['scenes'],t['scenes']):
 p=qa/f"review_{s['id']}.jpg";at=item['start']+item['duration']*.72
 b.run(['ffmpeg','-hide_banner','-loglevel','error','-y','-ss',str(at),'-i',out/(b.STEM+'.mp4'),'-frames:v','1','-q:v','2',p]);shots.append(p)
for k in range(2):
 im=Image.new('RGB',(940,1720),'#e7edf0');draw=ImageDraw.Draw(im)
 for j,p in enumerate(shots[k*4:k*4+4]):
  x=22+(j%2)*468;y=18+(j//2)*850;im.paste(Image.open(p).resize((432,768)),(x,y));draw.text((x,y+775),p.stem,fill='#17333c')
 im.save(qa/f'review_sheet_{k+1}.jpg')
b.run(['ffmpeg','-hide_banner','-loglevel','error','-xerror','-i',out/(b.STEM+'.mp4'),'-map','0:v:0','-map','0:a:0','-f','null','-'],timeout=120,log=qa/'full_decode.log')
report=b.load_json(out/'制作验收.json');report.update({'full_decode':'PASS','duration_limit_seconds':180,'duration_gate':'PASS','active_audio_files_checked':8,'subtitle_source_matches_all_scenes':True,'engine_regression_tests':11,'burned_subtitle_workdir_fix':'Applied and re-rendered; inspect fresh review sheets','file_bytes':(out/(b.STEM+'.mp4')).stat().st_size,'sha256':hashlib.sha256((out/(b.STEM+'.mp4')).read_bytes()).hexdigest()});b.save_json(out/'制作验收.json',report)
print(json.dumps({'seconds':report['duration_seconds'],'full_decode':report['full_decode'],'subtitle_sources':'8/8 match','bytes':report['file_bytes']},ensure_ascii=False))
