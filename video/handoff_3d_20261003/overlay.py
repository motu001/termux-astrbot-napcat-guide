"""153.333s film typography. Seconds in; straight-alpha RGBA out (never premultiplied).

Construct once with decoded timeline/subtitle JSON; frame(n / 30) ignores legacy fps.
Only Pillow is required. All typography/layout/gradients are cached at construction.
"""
from bisect import bisect_right
from functools import lru_cache
import math
from pathlib import Path
import re

from PIL import Image, ImageDraw, ImageFont

IVORY, HUMAN, AGENT = (246, 242, 228), (237, 187, 136), (111, 224, 204)
FONT_DIR = Path("C:/Windows/Fonts")
TOKENS = re.compile(r"[A-Za-z0-9]+(?:[._:/+\-][A-Za-z0-9]+)*|不需要|授权范围|模型调用|真实收发|"
                    r"没验证|私有配置|执行任务书|准备好|新增授权|交付|通过|验证|授权|[^\S\n]+|[^\s]")
COPY = (
    ("人做好准备\nAgent 接手部署", "人 × Agent", AGENT,
     ("人准备设备与授权", "Agent 负责部署与检查", "详细步骤留在执行文档")),
    ("装好 Termux\n准备好手机", "人 / 准备", HUMAN,
     ("官方来源安装 Termux", "网络 · 空间 · 自用测试账号", "必要权限，由本人确认")),
    ("连接手机\n再交给 Agent", "人 / 连接", HUMAN,
     ("按文档开启 SSH", "私下完成连接与授权", "有终端能力，才有执行能力")),
    ("交出执行文档\n说清授权边界", "人 / 交接", HUMAN,
     ("交接文档与执行任务书", "说明目标、现状与授权范围", "密码与密钥只进私有配置")),
    ("Agent 接棒\n自动部署配置", "Agent / 执行", AGENT,
     ("先预检，保护已有数据", "安装配置 AstrBot 与 NapCat", "接通 OneBot 与指定模型")),
    ("需要本人时\n再回来确认", "人 / 确认", HUMAN,
     ("首次扫码，由本人完成", "安全验证与新增授权", "确认后，Agent 继续执行")),
    ("不止能打开\n更要真的跑通", "Agent / 验收", AGENT,
     ("核查服务、登录与连接", "验证模型调用与真实收发", "未验证项，明确标注")),
    ("用真实证据\n交付验收回执", "Agent / 交付", AGENT,
     ("回执列明结果与证据", "未通过项写清原因与下一步", "留下启动、恢复与回退方法")),
)


def smooth(x):
    x = min(1.0, max(0.0, x))
    return x * x * (3 - 2 * x)


def envelope(t, start, end, fade=.55):
    return smooth((t - start) / fade) * smooth((end - t) / fade)


@lru_cache(maxsize=24)
def font(size, bold=False):
    return ImageFont.truetype(str(FONT_DIR / ("msyhbd.ttc" if bold else "msyh.ttc")), size)


def wrap(text, face, width=843, phrases_only=False):
    """Balanced two-line layout; Latin names are indivisible, punctuation stays attached."""
    text = text.replace("\n", "").strip()
    if face.getlength(text) <= width:
        return (text,)
    tokens = TOKENS.findall(text)
    choices = []
    for i in range(1, len(tokens)):
        a, b = "".join(tokens[:i]).rstrip(), "".join(tokens[i:]).lstrip()
        if not a or not b or b[0] in "，。！？；：、）】》”’" or a[-1] in "（【《“‘":
            continue
        if phrases_only and a[-1] not in "，。；：！？、":
            continue
        wa, wb = face.getlength(a), face.getlength(b)
        if max(wa, wb) <= width:
            choices.append((abs(wa - wb) + (0 if a[-1] in "，。；：！？、" else 250), a, b))
    if not choices:
        raise ValueError(f"Subtitle cannot fit two lines at {face.size}px: {text}")
    return min(choices)[1:]


@lru_cache(maxsize=192)
def raster(lines, size, color=IVORY, bold=False):
    face = font(size, bold)
    step = round(size * 1.28)
    boxes = [face.getbbox(s, anchor="lt") for s in lines]
    out = Image.new("RGBA", (math.ceil(max(face.getlength(s) for s in lines)) + 8,
                             step * (len(lines) - 1) + max(b[3] for b in boxes) + 8))
    draw = ImageDraw.Draw(out)
    for n, s in enumerate(lines):
        draw.text((4, 4 + n * step), s, font=face, fill=(*color, 255), anchor="lt")
    return out.crop(out.getbbox())


def wash(width, height, strength):
    mask = Image.new("L", (64, 32))
    mask.putdata([round(strength * math.sin(math.pi * x / 63) ** .7 *
                        math.sin(math.pi * y / 31) ** 1.3)
                  for y in range(32) for x in range(64)])
    out = Image.new("RGBA", (width, height), (4, 14, 30, 0))
    out.putalpha(mask.resize(out.size, Image.Resampling.BICUBIC))
    return out


def stamp(canvas, sprite, x, y, alpha=1.0):
    """Fade alpha alone, then Porter-Duff over; never mask-paste RGBA twice."""
    if alpha <= 0:
        return
    if alpha < 1:
        faded = sprite.copy()
        faded.putalpha(sprite.getchannel("A").point([round(v * alpha) for v in range(256)]))
        sprite = faded
    canvas.alpha_composite(sprite, (round(x), round(y)))


class OverlayPainter:
    def __init__(self, timeline, subtitles, width=1080, height=1920):
        self.size = (int(width), int(height))
        if min(self.size) <= 0:
            raise ValueError("Canvas dimensions must be positive")
        self.scenes = [dict(s) for s in timeline["scenes"]]
        self.subtitles = sorted((dict(s) for s in subtitles), key=lambda s: s["start"])
        self.duration = float(timeline["duration"])
        self.starts = [s["start"] for s in self.scenes]
        self.sub_starts = [s["start"] for s in self.subtitles]
        if len(self.scenes) != 8 or self.starts != sorted(self.starts):
            raise ValueError("This authored overlay requires the eight ordered film scenes")
        self.titles, self.roles, self.states, self.counts = [], [], [], []
        self.layout_bounds, self.subtitle_lines, self.subtitle_sizes = [], [], []
        for i, (title, role, color, states) in enumerate(COPY):
            rows = [raster((line,), 96, IVORY if n == 0 else color, True)
                    for n, line in enumerate(title.splitlines())]
            self.titles.append(rows)
            for n, row in enumerate(rows):
                self.layout_bounds.append(("title", (72, 194 + 106*n, 72 + row.width, 216 + 106*n + row.height)))
            self.roles.append(raster((role,), 26, color))
            self.states.append([raster((state,), 32, color) for state in states])
            self.counts.append(raster((f"{i+1:02d} / 08",), 22, (163, 179, 190)))
        self.captions = []
        for event in self.subtitles:
            for phrases_only, size in [(p, s) for p in (True, False) for s in (50, 48, 46, 44)]:
                try:
                    lines = wrap(event["text"], font(size), phrases_only=phrases_only)
                    break
                except ValueError:
                    if not phrases_only and size == 44:
                        raise
            sprite = raster(lines, size)
            if sprite.width > 843 or sprite.height > 128:
                raise ValueError("Subtitle raster escaped its safe area")
            self.subtitle_lines.append(lines)
            self.subtitle_sizes.append(size)
            self.captions.append(sprite)
            self.layout_bounds.append(("subtitle", (72, 1520, 72 + sprite.width, 1530 + sprite.height)))
        self.brand = raster(("ASTRBOT  /  MOBILE AUTOMATION",), 22, (174, 189, 202))
        self.disclaimer = raster(("教学动画 · 非实机录屏",), 24, (177, 190, 204))
        self.top_wash, self.sub_wash = wash(886, 314, 68), wash(886, 194, 174)

    def frame(self, t: float) -> Image.Image:
        t = float(t)
        if not math.isfinite(t):
            raise ValueError("Time must be finite seconds")
        out = Image.new("RGBA", (1080, 1920))
        if not 0 <= t < self.duration:
            return out if self.size == out.size else out.resize(self.size)
        i = max(0, min(7, bisect_right(self.starts, t) - 1))
        scene, color = self.scenes[i], COPY[i][2]
        age, end = t - scene["start"], scene["start"] + scene["duration"]
        progress = min(1.0, age / scene["duration"])
        fade = envelope(t, scene["start"], end)
        stamp(out, self.top_wash, 40, 150, fade)
        stamp(out, self.brand, 72, 88)
        stamp(out, self.roles[i], 914 - self.roles[i].width, 132, fade)
        for n, row in enumerate(self.titles[i]):
            u = min(1.0, max(0.0, (age - n*.055) / .65))
            # A restrained ease-out-back settles the whole line, not individual letters.
            settle = 1 + 2.05*(u-1)**3 + 1.05*(u-1)**2
            stamp(out, row, 72, 196 + 106*n + 20*(1-settle), fade)
        phase = min(2, int(progress * 3))
        phase_start = scene["start"] + phase * scene["duration"] / 3
        phase_end = min(end, phase_start + scene["duration"] / 3)
        state_alpha = fade * envelope(t, phase_start, phase_end, .32)
        stamp(out, self.states[i][phase], 72, 1360 + 6*(1-smooth((t-phase_start)/.4)), state_alpha)
        # Supersampled hairline rail: three conceptual phases, never fabricated checkmarks.
        rail = Image.new("RGBA", (1688, 32))
        rd = ImageDraw.Draw(rail)
        rd.line((0, 16, 1686, 16), fill=(*IVORY, 46), width=2)
        for x in (5, 843, 1682):
            rd.ellipse((x-4, 12, x+4, 20), fill=(*color, 140))
        head = 5 + 1677*progress
        rd.line((5, 16, head, 16), fill=(*color, 155), width=2)
        rd.ellipse((head-5, 11, head+5, 21), fill=(*color, 245))
        stamp(out, rail.resize((844, 16), Image.Resampling.LANCZOS), 72, 1420, fade)
        j = bisect_right(self.sub_starts, t) - 1
        if j >= 0 and t < self.subtitles[j]["end"]:
            sub = self.subtitles[j]
            a = fade * smooth((t-sub["start"])/.20) * smooth((sub["end"]-t)/.14)
            stamp(out, self.sub_wash, 40, 1484, a)
            stamp(out, self.captions[j], 72, 1520 + 10*(1-smooth((t-sub["start"])/.28)), a)
        stamp(out, self.disclaimer, 72, 1680)
        stamp(out, self.counts[i], 914-self.counts[i].width, 1682, fade)
        draw = ImageDraw.Draw(out)
        for k in range(8):
            x = 72 + k*106
            draw.line((x, 1724, x+97, 1724), fill=(*IVORY, 42), width=2)
            fill = 1 if k < i else progress if k == i else 0
            if fill > 0:
                draw.line((x, 1724, x+97*fill, 1724), fill=(*COPY[k][2], 180), width=2)
        return out if self.size == out.size else out.resize(self.size, Image.Resampling.LANCZOS)
