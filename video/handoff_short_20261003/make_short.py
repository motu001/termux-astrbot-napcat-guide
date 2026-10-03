"""Produce the short human/Agent handoff film, reusing the tested local engine.
Only stage=audio calls the configured Xiaomi TTS service. Credentials are never copied.
"""
from pathlib import Path
import importlib.util,json,sys,argparse
BASE=Path(__file__).resolve().parent
candidates=[BASE.parent/'完整教程_20261003',BASE.parent/'tutorial_20261003']
LIB=next((p for p in candidates if (p/'build_video.py').exists()),None)
if LIB is None:raise SystemExit('Missing shared production engine; keep the detailed-course source folder beside this one.')
sys.path.insert(0,str(LIB))
spec=importlib.util.spec_from_file_location('handoff_engine',LIB/'build_video.py')
b=importlib.util.module_from_spec(spec);spec.loader.exec_module(b)
b.WORK=BASE;b.ROOT=BASE.parent.parent;b.OUT=b.ROOT/'06_成片'/'人机分工短版_20261003'
b.STEM='手机部署机器人_人做准备_Agent部署验收_短版_20261003'

def preflight():
    import render_cards as r
    d=b.scenes();assert [c['id'] for c in d['chapters']]==['01','02'];assert len(d['scenes'])==8
    char_count=sum(len(s['speech']) for s in d['scenes']);assert char_count<=800
    report=[]
    for i,s in enumerate(d['scenes']):
        for phase in range(3):report.append(r.render_scene(s,BASE/'layout_preflight'/f"{s['id']}_p{phase}.png",phase,i,len(d['scenes'])))
        chunks=b.caption_chunks(s['speech']);assert ''.join(chunks)==s['speech']
        for c in chunks:assert len(b.wrap_caption(c))<=2
    b.save_json(BASE/'content_and_layout_check.json',{'chapters':2,'scenes':8,'characters':char_count,'frames_checked':len(report),'passed':all(x['ok'] for x in report)})
    print('Preflight passed: 2 parts, 8 scenes, 24 layout states.',flush=True)

def duration_guard():
    timeline=b.make_timeline();assert len(timeline['chapters'])==2
    if timeline['duration']>180:raise RuntimeError(f"Duration {timeline['duration']:.2f}s exceeds 3 minutes; shorten narration before rendering")
    print(f"Short-film duration: {timeline['duration']:.3f} seconds",flush=True)
    return timeline

def cover():
    from PIL import Image,ImageDraw,ImageFont
    im=Image.new('RGB',(1080,1920),'#0B1F2B');d=ImageDraw.Draw(im)
    def f(n,bold=False):return ImageFont.truetype('C:/Windows/Fonts/msyhbd.ttc' if bold else 'C:/Windows/Fonts/msyh.ttc',n)
    white='#F6F1E8';teal='#69DFBF';orange='#FFC181';muted='#A7BEC7'
    d.text((78,143),'手机部署机器人',font=f(51,True),fill=teal)
    d.text((70,298),'人做准备',font=f(119,True),fill=white)
    d.text((70,458),'Agent 来部署',font=f(101,True),fill=white)
    d.rounded_rectangle((76,661,922,744),radius=22,fill='#214553')
    d.text((103,680),'不学整套命令 · 把任务交给 Agent',font=f(38,True),fill=teal)
    for y,title,items,color in [(860,'人做一次',['安装软件与手机授权','接通SSH，交接执行文档'],orange),(1180,'Agent 负责',['部署 · 配置 · 排错','自主验收，交付检查回执'],teal)]:
        d.rounded_rectangle((76,y,922,y+249),radius=28,fill='#143540')
        d.text((105,y+24),title,font=f(51,True),fill=color)
        for j,t in enumerate(items):d.text((108,y+107+58*j),t,font=f(35),fill=white)
    d.text((83,1538),'本人扫码 / 安全确认 → 必要时回交',font=f(32),fill=muted)
    d.text((83,1710),'教学示意 · 小米 MiMo 合成配音',font=f(30),fill=orange)
    b.OUT.mkdir(parents=True,exist_ok=True);im.save(b.OUT/'短版封面.png')

if __name__=='__main__':
    ap=argparse.ArgumentParser();ap.add_argument('stage',choices=['preflight','audio','video','verify']);args=ap.parse_args()
    if args.stage=='preflight':preflight()
    elif args.stage=='audio':preflight();b.do_audio(workers=2);duration_guard()
    elif args.stage=='video':
        duration_guard();b.do_graphics();b.do_render(workers=2);b.do_assemble(export_chapters=False);cover();b.verify()
    else:duration_guard();b.verify()
