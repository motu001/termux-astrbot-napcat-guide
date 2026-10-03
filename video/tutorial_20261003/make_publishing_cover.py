"""Create a standalone code-native publishing cover; no screenshots or external media."""
from pathlib import Path
from PIL import Image,ImageDraw,ImageFont
BASE=Path(__file__).resolve().parent
OUT=BASE.parent.parent/'06_成片'/'完整教程_20261003'

def make_cover(path):
    im=Image.new('RGB',(1080,1920),'#0A1E28');d=ImageDraw.Draw(im)
    def font(n,b=False):return ImageFont.truetype('C:/Windows/Fonts/msyhbd.ttc' if b else 'C:/Windows/Fonts/msyh.ttc',n)
    cream='#F5F0E6';teal='#65DDC3';muted='#A2B7BE';orange='#FFC17F'
    d.rounded_rectangle((70,130,326,191),radius=20,fill=teal)
    d.text((92,140),'从准备讲到维护',font=font(29,True),fill='#102D32')
    d.text((72,236),'旧手机',font=font(132,True),fill=cream)
    d.text((72,401),'搭建机器人',font=font(112,True),fill=cream)
    d.rounded_rectangle((76,568,889,659),radius=22,fill='#193E45')
    d.text((100,589),'Termux  ×  AstrBot  ×  NapCat',font=font(40,True),fill=teal)
    d.text((76,700),'18章详细讲解 · 小米中文配音',font=font(36),fill=muted)
    # A deliberately abstract instructional phone, not a copied app screen.
    d.rounded_rectangle((241,812,809,1404),radius=56,fill='#06151D')
    d.rounded_rectangle((226,794,794,1384),radius=56,fill='#F1ECDD')
    d.rounded_rectangle((241,809,779,1369),radius=42,fill='#102D38')
    d.rounded_rectangle((448,828,573,841),radius=7,fill='#54717A')
    d.text((280,897),'手机机器人工作流',font=font(37,True),fill=cream)
    for i,label in enumerate(['01  环境与安装','02  登录与连接','03  模型与验收','04  自启与维护']):
        y=978+i*82
        d.rounded_rectangle((277,y,744,y+61),radius=15,fill='#244851' if i!=2 else '#DDEFE4')
        d.text((296,y+10),label,font=font(29,True),fill=cream if i!=2 else '#133138')
    d.rounded_rectangle((73,1466,899,1618),radius=28,fill='#173A40')
    d.text((99,1486),'每一步都讲清',font=font(40,True),fill=teal)
    d.text((101,1550),'在哪操作  /  怎么检查  /  失败怎么停',font=font(30),fill=cream)
    d.text((77,1682),'教学示意 · 非实机成功录像',font=font(31,True),fill=orange)
    d.text((77,1738),'仅用自己的测试账号；安装须逐关验证',font=font(25),fill=muted)
    path=Path(path);path.parent.mkdir(parents=True,exist_ok=True);im.save(path)
    return str(path)

if __name__=='__main__':print(make_cover(OUT/'抖音发布封面.png'))
