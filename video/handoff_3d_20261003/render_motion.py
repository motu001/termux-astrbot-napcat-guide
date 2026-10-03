"""Offscreen GPU motion design. Keeps narration unchanged; never accesses the phone.
ModernGL implicit 3D surfaces, studio lighting, emissive data paths, bloom and animated typography.
"""
from __future__ import annotations
from pathlib import Path
import argparse,hashlib,json,math,time,subprocess,sys,wave
import moderngl
import numpy as np
from PIL import Image,ImageDraw,ImageFont
ROOT=Path(__file__).resolve().parent
SOURCES=[ROOT.parent/'人机分工短版_20261003',ROOT.parent/'handoff_short_20261003',ROOT]
SOURCE=next((p for p in SOURCES if (p/'timeline.json').exists()),None)
# Public clones use a locally produced short course as audio input; explicit --source is supported.
W,H,FPS=1080,1920,30
OUT=ROOT.parent.parent/'06_成片'/'人机分工_3D动画版_20261003'
VERT='''#version 330
in vec2 in_pos;
void main(){gl_Position=vec4(in_pos,0.,1.);}
'''
def ease(x):x=float(np.clip(x,0,1));return x*x*(3-2*x)
def f(n,b=False):return ImageFont.truetype('C:/Windows/Fonts/msyhbd.ttc' if b else 'C:/Windows/Fonts/msyh.ttc',n)
def run(cmd,log=None):
 r=subprocess.run([str(x) for x in cmd],capture_output=True,cwd=ROOT)
 if log:Path(log).write_bytes(r.stderr)
 if r.returncode:raise RuntimeError(r.stderr.decode('utf-8',errors='replace')[-1800:])
 return r

def phone_texture(i):
 im=Image.new('RGB',(768,1408),'#0a1d2c');d=ImageDraw.Draw(im)
 for y in range(1408):
  k=y/1408;d.line((0,y,768,y),fill=(int(10+6*k),int(27+20*k),int(42+17*k)))
 d.rounded_rectangle((52,72,715,1295),radius=40,outline='#244b59',width=3)
 d.text((88,154),'PHONE / AGENT',font=f(29,True),fill='#86c4c8')
 titles=['你的手机','一次准备','安全连接','任务交接','部署执行','本人授权','分层核验','结果交付']
 d.text((83,244),titles[i],font=f(70,True),fill='#e7f5ed')
 d.text((90,362),'工作流示意',font=f(30),fill='#739aa9')
 cx,cy=386,649
 d.ellipse((cx-149,cy-149,cx+149,cy+149),outline='#366a72',width=4)
 d.ellipse((cx-122,cy-122,cx+122,cy+122),fill='#123e46',outline='#68ddbc',width=5)
 if i in [0,1,4]:
  d.line((323,606,373,647,323,689),fill='#b7f3df',width=17);d.line((399,692,466,692),fill='#b7f3df',width=13)
 elif i==5:
  d.ellipse((345,584,429,668),fill='#f4c994');d.rounded_rectangle((319,681,455,745),radius=30,fill='#f4c994')
 else:
  d.rounded_rectangle((320,592,453,719),radius=19,outline='#b7f3df',width=10)
  for n in range(3):d.line((343,622+n*31,427,622+n*31),fill='#b7f3df',width=6)
 labels=[['TERMUX','SSH ACCESS','HANDOFF'],['软件 / 权限','网络 / 空间','准备交接'],['可信设备','私有认证','SSH 通路'],['部署目标','授权范围','执行文档'],['预检 / 安装','配置 / 连接','启动 / 恢复'],['首次扫码','安全确认','完成后继续'],['服务 / 登录','连接 / 模型','消息 / 恢复'],['验收回执','待处理事项','使用与恢复']][i]
 for n,txt in enumerate(labels):
  y=923+n*98;d.rounded_rectangle((91,y,677,y+70),radius=17,fill='#173945',outline='#275461',width=2)
  d.ellipse((111,y+26,128,y+43),fill='#e0b87f' if i in [1,5] else '#6de3c2')
  d.text((158,y+13),txt,font=f(32,True),fill='#d2e8e5')
 return im

def document_texture(report=False):
 out=Image.new('RGB',(1152,512),'#eef3e8')
 for i,label in enumerate(['验收回执','待处理项','恢复说明'] if report else ['部署目标','授权范围','执行文档']):
  im=Image.new('RGB',(384,512),'#edf3e8');d=ImageDraw.Draw(im)
  d.rounded_rectangle((24,22,359,488),radius=20,outline='#b9cfc8',width=2)
  d.rounded_rectangle((49,58,115,113),radius=12,fill='#286965');d.text((60,68),f'{i+1:02}',font=f(28,True),fill='#ffffff')
  d.text((47,155),label,font=f(45,True),fill='#153b40')
  d.text((49,224),'按证据填写' if report else '交给 Agent',font=f(27),fill='#577b7b')
  for j,l in enumerate([250,205,245,151]):d.rounded_rectangle((50,303+j*27,50+l,312+j*27),radius=4,fill='#abc8bd' if j==0 else '#cbd9cf')
  out.paste(im,(i*384,0))
 return out

def module_texture(human=False):
 out=Image.new('RGB',(1536,384),'#163c42')
 for i,label in enumerate(['Termux','网络','权限','空间'] if human else ['AstrBot','NapCat','OneBot','模型']):
  im=Image.new('RGB',(384,384),'#174049' if i else '#543822');d=ImageDraw.Draw(im);color='#7de7c6' if i else '#f7c893'
  d.rounded_rectangle((19,19,365,365),radius=40,outline=color,width=4)
  d.ellipse((125,61,259,195),outline=color,width=5)
  if i==2:
   d.line((151,117,231,117),fill=color,width=5);d.line((151,148,231,148),fill=color,width=5)
   d.line((216,105,231,117,216,129),fill=color,width=5);d.line((166,136,151,148,166,160),fill=color,width=5)
  else:d.text((157,90),['>_','N','','AI'][i],font=f(41,True),fill=color)
  font=f(44,True);tw=d.textlength(label,font=font);d.text(((384-tw)/2,239),label,font=font,fill='#f4f4e9')
  out.paste(im,(384*i,0))
 return out

class MotionRenderer:
 def __init__(self,source=SOURCE,width=W,height=H,with_overlay=True):
  if source is None:raise RuntimeError('Need the generated short course directory with timeline, subtitles and narration')
  self.source=Path(source);self.timeline=json.loads((self.source/'timeline.json').read_text(encoding='utf-8'));self.events=json.loads((self.source/'subtitle_events.json').read_text(encoding='utf-8'))
  self.w,self.h=width,height;self.rw,self.rh=width*3//2,height*3//2;self.ctx=moderngl.create_standalone_context(require=330);self.ctx.enable(moderngl.PROGRAM_POINT_SIZE)
  self.scene=self.ctx.program(vertex_shader=VERT,fragment_shader=(ROOT/'scene.frag').read_text(encoding='utf-8-sig'))
  self.post=self.ctx.program(vertex_shader=VERT,fragment_shader=(ROOT/'composite.frag').read_text(encoding='utf-8-sig'))
  self.vbo=self.ctx.buffer(np.array([-1,-1,1,-1,-1,1,1,1],dtype='f4').tobytes())
  self.vao=self.ctx.simple_vertex_array(self.scene,self.vbo,'in_pos');self.pvao=self.ctx.simple_vertex_array(self.post,self.vbo,'in_pos')
  self.hdr=self.ctx.texture((self.rw,self.rh),4,dtype='f2');self.hdr.filter=(moderngl.LINEAR,moderngl.LINEAR);self.hdr.repeat_x=False;self.hdr.repeat_y=False
  self.fbo=self.ctx.framebuffer(color_attachments=[self.hdr]);self.final=self.ctx.simple_framebuffer((width,height),components=4)
  self.overlay_tex=self.ctx.texture((width,height),4);self.overlay_tex.filter=(moderngl.LINEAR,moderngl.LINEAR)
  self.overlay_tex.write(bytes(width*height*4))
  self.screens=[self.tex(phone_texture(i)) for i in range(8)];self.documents=[self.tex(document_texture(False)),self.tex(document_texture(True))];self.modules=[self.tex(module_texture(True)),self.tex(module_texture(False))]
  self.overlay=None
  if with_overlay:
   from overlay import OverlayPainter
   self.overlay=OverlayPainter(self.timeline,self.events,width=width,height=height)
  self.scene['u_res'].value=(self.rw,self.rh);self.post['u_res'].value=(width,height)
  self.scene['u_prev_screen'].value=3;self.scene['u_screen'].value=0;self.scene['u_doc'].value=1;self.scene['u_modules'].value=2
  self.post['u_hdr'].value=0;self.post['u_overlay'].value=1
 def tex(self,im):
  im=im.convert('RGB').transpose(Image.Transpose.FLIP_TOP_BOTTOM);t=self.ctx.texture(im.size,3,im.tobytes());t.build_mipmaps();t.filter=(moderngl.LINEAR_MIPMAP_LINEAR,moderngl.LINEAR);t.repeat_x=False;t.repeat_y=False;return t
 def pose(self,i,l,duration):
  # Shared hero objects survive cuts. Entry, relation changes and settling carry meaning.
  q=float(np.clip(l/duration,0,1));base={
   'phone':np.array([-.34,-.09,.0]),'rot':np.array([-.075,-.23,-.055]),'ps':.88,
   'agent':np.array([1.23,.46,.18]),'as':.88,'human':np.array([-1.51,-.48,.42]),'hs':.70,
   'docs':np.array([[0.,0.,0.]]*3),'ds':np.zeros(3),'boxes':np.array([[0.,0.,0.]]*4),'bs':np.zeros(4)}
  if i==0:
   base['phone'][1]+=-2.8*(1-ease(l/1.35));base['rot'][1]+=.85*(1-ease(l/2.2))
   base['as']*=ease((l-6.0)/1.1);base['hs']*=ease((l-5.2)/1.1)
  elif i==1:
   base['phone']=np.array([.16,-.11,.12]);base['rot']=np.array([-.1,.28,.035]);base['ps']=.91;base['as']=0.;base['human']=np.array([-1.43,-.89,.8]);base['hs']=.85
   for j in range(4):
    a=j*1.65+l*.045;base['boxes'][j]=[math.cos(a)*1.2,.4+math.sin(a)*.95,-.2]
    base['bs'][j]=.43*ease((l-1-j*1.5)/.8)
  elif i==2:
   base['phone']=np.array([-.66,-.12,0.]);base['ps']=.82;base['rot']=np.array([-.08,-.30,-.03]);base['as']=1.13;base['hs']=0.
   base['agent']=np.array([1.10,.45,.35])
  elif i==3:
   base['phone']=np.array([-1.0,-.16,-.23]);base['ps']=.73;base['agent']=np.array([1.08,.26,.34]);base['as']=1.10;base['hs']=0.
   for j in range(3):
    k=ease((l-1.2-j*1.1)/11.0);a=np.array([-.62,.6-j*.25,.45+j*.14]);b=base['agent']+np.array([-.15,-.15,0])
    base['docs'][j]=a*(1-k)+b*k+np.array([0,.55*math.sin(k*math.pi),.30*math.sin(k*math.pi)])
    base['ds'][j]=(.72-.5*ease((k-.68)/.32))*ease((l-.3-j*.55)/.55)
  elif i==4:
   base['phone']=np.array([-.7,-.64,-.60]);base['ps']=.66;base['rot']=np.array([-.05,-.15,.03]);base['hs']=0.
   base['agent']=np.array([.95,.48,.2]);base['as']=1.12
   targets=[[-1.30,.66,.6],[-.24,.72,.7],[-1.35,-.47,.6],[-.2,-.42,.65]]
   for j in range(4):
    a=l*.23+j*math.pi/2;orbit=np.array([math.cos(a)*1.3,.15+math.sin(a)*.8,.12+math.sin(a)*.3]);k=ease((l-5.5-j*.8)/5.)
    base['boxes'][j]=orbit*(1-k)+np.array(targets[j])*k;base['bs'][j]=.72*ease((l-.4-j*.45)/.85)
  elif i==5:
   base['phone']=np.array([-.43,-.12,-.08]);base['ps']=.82;base['human']=np.array([-1.13,-.72,.98]);base['hs']=1.03;base['as']=.77;base['agent']=np.array([1.2,.55,.22])
  elif i==6:
   base['phone']=np.array([-.34,-.07,.10]);base['rot']=np.array([-.07,.20,-.025]);base['ps']=.93;base['hs']=0.;base['agent']=np.array([1.3,-.80,.26]);base['as']=.70
   for j in range(3):base['docs'][j]=[-1.33,.64-j*.6,.40];base['ds'][j]=.39*ease((l-1-j*2.2)/.65)
  else:
   base['phone']=np.array([-.81,-.27,-.5]);base['ps']=.70;base['rot']=np.array([-.08,-.26,-.1]);base['human']=np.array([-1.28,-1.19,.35]);base['hs']=.57;base['agent']=np.array([1.16,.38,-.05]);base['as']=.9
   base['docs'][0]=[.04,-.05,.84];base['ds'][0]=1.34*ease(l/1.0)
   for j in [1,2]:base['docs'][j]=[.1+j*.065,-.02+j*.045,.72-j*.08];base['ds'][j]=1.26*ease((l-.2)/1.0)
  base['agent'][0]-=.16;base['as']*=.82
  base['phone'][1]+=.045*math.sin(l*.85);base['rot'][1]+=.055*math.sin(l*.36);base['agent'][1]+=.07*math.sin(l*.78)
  return base
 def state(self,t):
  scenes=self.timeline['scenes'];i=max(j for j,s in enumerate(scenes) if s['start']<=t+1e-6);s=scenes[i];l=t-s['start'];p=self.pose(i,l,s['duration']);sweep=0.
  if i>0 and l<.85:
   prev=scenes[i-1];a=self.pose(i-1,prev['duration'],prev['duration']);k=ease(l/.85)
   p={key:a[key]*(1-k)+p[key]*k for key in p};sweep=l/.85
  return i,l,p,sweep
 def frame(self,t,overlay=True):
  i,l,p,sweep=self.state(t);self.fbo.use();self.ctx.viewport=(0,0,self.rw,self.rh)
  for key,u in [('phone','u_phone'),('rot','u_phone_rot'),('agent','u_agent'),('human','u_human')]:self.scene[u].value=tuple(p[key])
  for key,u in [('ps','u_ps'),('as','u_as'),('hs','u_hs')]:self.scene[u].value=float(p[key])
  for key,u in [('docs','u_docs'),('ds','u_ds'),('boxes','u_boxes'),('bs','u_bs')]:self.scene[u].write(np.asarray(p[key],dtype='f4').tobytes())
  self.scene['u_time'].value=t;self.scene['u_scene'].value=i;self.scene['u_scan'].value=-1.3+2.6*((l*.10)%1)
  self.scene['u_camera'].value=(.12*math.sin(t*.10),.60+.06*math.cos(t*.18),7.4-.12*math.sin(t*.25))
  self.screens[max(i-1,0)].use(3);self.scene['u_ui_mix'].value=ease(l/.85);self.screens[i].use(0);self.documents[int(i==7)].use(1);self.modules[int(i!=1)].use(2)
  self.vao.render(moderngl.TRIANGLE_STRIP)
  self.final.use();self.ctx.viewport=(0,0,self.w,self.h);self.hdr.use(0)
  if self.overlay is not None and overlay:
   im=self.overlay.frame(t).convert('RGBA').transpose(Image.Transpose.FLIP_TOP_BOTTOM);self.overlay_tex.write(im.tobytes())
  self.overlay_tex.use(1);self.post['u_sweep'].value=sweep;self.pvao.render(moderngl.TRIANGLE_STRIP)
  return self.final.read(components=3,alignment=1)
 def save(self,t,path):
  im=Image.frombytes('RGB',(self.w,self.h),self.frame(t)).transpose(Image.Transpose.FLIP_TOP_BOTTOM);Path(path).parent.mkdir(parents=True,exist_ok=True);im.save(path)
 def close(self):self.ctx.release()

def make_sfx(timeline):
 sr=48000;n=round(timeline['duration']*sr);a=np.zeros(n,dtype=np.float32);rng=np.random.default_rng(37)
 for s in timeline['scenes'][1:]:
  dur=.70;count=round(dur*sr);t=np.arange(count)/sr;env=np.sin(np.pi*t/dur)**2
  noise=rng.standard_normal(count);kernel=np.ones(27)/27;noise=np.convolve(noise,kernel,mode='same')
  whoosh=(noise*.047+np.sin(2*np.pi*(190*t+140*t*t))*0.006)*env
  start=max(0,round((s['start']-.10)*sr));end=min(n,start+count);a[start:end]+=whoosh[:end-start]
 for s in timeline['scenes']:
  for off in [2.0,6.0,10.0]:
   dur=.075;tt=np.arange(round(sr*dur))/sr;click=np.sin(2*np.pi*830*tt)*np.exp(-tt*90)*.007
   start=round((s['start']+off)*sr);end=min(n,start+len(click))
   if end>start:a[start:end]+=click[:end-start]
 p=ROOT/'transition_sfx.wav'
 with wave.open(str(p),'wb') as f:f.setnchannels(1);f.setsampwidth(2);f.setframerate(sr);f.writeframes((np.clip(a,-1,1)*32767).astype('<i2').tobytes())
 return p

def render_video(source,duration=None,preview=False):
 source=Path(source)
 audio=source.parent.parent/'06_成片'/'人机分工短版_20261003'/'配音_小米MiMo冰糖_20261003.m4a'
 if not audio.exists():raise RuntimeError('Original Xiaomi narration missing; prepare the short-course audio before rendering video')
 timeline=json.loads((source/'timeline.json').read_text(encoding='utf-8'));dur=timeline['duration'] if duration is None else min(duration,timeline['duration']);frames=round(dur*FPS);dur=frames/FPS
 OUT.mkdir(parents=True,exist_ok=True);name='动态样片_27秒' if preview else '手机部署机器人_人机分工_3D动画版_20261003';silent=ROOT/(name+'_silent.mp4');final=OUT/(name+'.mp4')
 r=MotionRenderer(source);print('GPU:',r.ctx.info['GL_RENDERER'],'frames:',frames,flush=True)
 cmd=['ffmpeg','-hide_banner','-loglevel','error','-y','-f','rawvideo','-pix_fmt','rgb24','-s',f'{W}x{H}','-r',str(FPS),'-i','-','-vf','vflip','-c:v','h264_nvenc','-preset','p5','-tune','hq','-rc','vbr','-cq','20','-b:v','0','-pix_fmt','yuv420p','-g','60','-an','-movflags','+faststart',str(silent)]
 log=(ROOT/(name+'_encode.log')).open('wb');proc=subprocess.Popen(cmd,stdin=subprocess.PIPE,stdout=subprocess.DEVNULL,stderr=log,cwd=ROOT,bufsize=8*1024*1024);start=time.perf_counter()
 try:
  for j in range(frames):
   proc.stdin.write(r.frame(j/FPS))
   if j%150==0:print(f'FRAME {j}/{frames} elapsed={time.perf_counter()-start:.1f}s',flush=True)
  proc.stdin.close();code=proc.wait();assert code==0,code
 finally:r.close();log.close()
 audio=source.parent.parent/'06_成片'/'人机分工短版_20261003'/'配音_小米MiMo冰糖_20261003.m4a'
 if not audio.exists():raise RuntimeError('Original normalized Xiaomi narration is missing')
 sfx=make_sfx(timeline)
 run(['ffmpeg','-hide_banner','-loglevel','warning','-y','-i',silent,'-i',audio,'-i',sfx,'-filter_complex','[1:a][2:a]amix=inputs=2:duration=first:normalize=0[a]','-map','0:v','-map','[a]','-c:v','copy','-c:a','aac','-b:a','160k','-t',str(dur),'-movflags','+faststart',final],ROOT/(name+'_mux.log'))
 print('DONE',final,'seconds',dur,'elapsed',round(time.perf_counter()-start,1),flush=True)
 return final

if __name__=='__main__':
 ap=argparse.ArgumentParser();ap.add_argument('mode',choices=['frames','preview','full']);ap.add_argument('--source',type=Path,default=SOURCE);ap.add_argument('--no-overlay',action='store_true');args=ap.parse_args()
 if args.mode=='frames':
  r=MotionRenderer(args.source,with_overlay=not args.no_overlay)
  for t in [4.,12.,23.,43.,62.,85.,101.,120.,143.]:
   start=time.perf_counter();p=ROOT/'lookdev'/f'frame_{int(t):03}.jpg';r.save(t,p);print(p.name,'seconds',round(time.perf_counter()-start,3),flush=True)
  r.close()
 elif args.mode=='preview':render_video(args.source,27,True)
 else:render_video(args.source)
