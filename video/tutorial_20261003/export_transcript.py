"""Create the readable manuscript from the single canonical JSON content source."""
from pathlib import Path
import json,re
BASE=Path(__file__).resolve().parent

def export():
    d=json.loads((BASE/'scenes.json').read_text(encoding='utf-8-sig'))
    n=len(d['scenes']);chars=sum(len(s['speech']) for s in d['scenes'])
    lines=['# 用手机部署机器人｜完整视频口播与分镜','',
      f"内容版本：{d['version']}。共 {len(d['chapters'])} 章、{n} 个场景、{chars} 个口播字符（含英文与标点）。时长以实际音频为准。",'',
      '## 制作与事实边界','',
      '- 1080×1920竖屏；小米MiMo TTS「冰糖」；画面始终标注教学示意，不冒充实机录屏。',
      '- 2026-10-03技术核对见配套《上游参考》。旧QQ链接404，官网新包在核对网络403；未取得包字节和新机运行证据，不能宣传已修复。',
      '- 视频说明安装动作、通过条件和失败出口。长配置/完整脚本应从《从零安装与连接》对应小节复制，不能从字幕或短命令卡补猜代码。',
      '- 2026-10-02只验证过原机NapCat/QQ服务重启免点击登录；整次测试136秒。新机零镜像、整机无人值守和AI来源仍须单独验收。',
      '- Termux:Boot新装范例只请求恢复服务，不等于已经安装原机的登录查询与12轮重试功能。',
      '- 不含真实账号、二维码、凭据、聊天、原始日志和私有镜像；不自动发布到抖音。',
      '- 分镜以JSON为唯一内容源，本文件自动导出。', '', '## 章节索引','']
    for c in d['chapters']:
        count=sum(s['chapter']==c['id'] for s in d['scenes'])
        lines.append(f"- {c['id']}｜{c['title']}（{count}段）")
    current=None
    for s in d['scenes']:
        if s['chapter']!=current:
            current=s['chapter'];lines+=['',f"## {current}｜{s['chapter_title']}",'']
        lines+=[f"### {s['id']}｜{s['title']}",'',f"**操作位置：**{s['env']}　**画面类型：**{s['kind']}",'','**画面要点**']
        lines += [f'- {x}' for x in s['bullets']]
        if s['code']:lines+=['','**画面命令或字段（按上下文辨别；完整操作以配套教程为准）**','','```text',*s['code'],'```']
        lines+=['',f"**提示：**{s['note']}",'','**口播**','',s['speech'],'']
    target=BASE/'口播与分镜.md';target.write_text('\n'.join(lines).rstrip()+'\n',encoding='utf-8')
    return {'scenes':n,'chapters':len(d['chapters']),'narration_characters':chars,'output':target.name}

if __name__=='__main__':print(json.dumps(export(),ensure_ascii=False))
