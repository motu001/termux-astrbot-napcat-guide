"""1080x1920 code-native instructional cards. No network, screenshots or TTS.

API: render_scene(scene, out_path, phase=2, index=0, total=1) -> JSON-safe report
     render_cover(out_path), make_contact_sheet(paths, out_path)
CLI: python -B render_cards.py --demo
     python -B render_cards.py --scenes scenes.json --out-dir frames

All phases use identical text geometry; only emphasis changes. Ink bounds,
reserved zones, lossless source-line fragments and a phase-independent layout
signature are reported. A LayoutError is raised BEFORE saving if material
cannot fit at the font-size floor. Split the scene; never truncate a command.
Input code is DISPLAY DATA, never executed. Soft-wrap markers are in the gutter,
not in the command. Supplied evidence is not interpreted as live measurements.
The credential guard catches obvious mistakes, not every possible private datum.
"""
from __future__ import annotations
import argparse
import hashlib
import json
import math
import os
import re
import sys
import unicodedata
from dataclasses import dataclass
from functools import lru_cache
from pathlib import Path
from typing import Iterable
from PIL import Image, ImageDraw, ImageFont

WIDTH, HEIGHT = 1080, 1920
BG, INK, CREAM = "#0B1C29", "#132B36", "#F5F1E7"
TEAL, ORANGE, MUTED = "#68DFC3", "#FFB16B", "#9BB2BE"
PANEL, LINE = "#142B3A", "#2B4554"
SUBTITLE_BOX = (0, 1460, WIDTH, 1680)
RIGHT_SAFE_BOX = (940, 0, WIDTH, HEIGHT)
TOP_SAFE_BOX = (0, 0, WIDTH, 110)
BOTTOM_SAFE_BOX = (0, 1760, WIDTH, HEIGHT)
SAFE_ZONES = {"subtitles": SUBTITLE_BOX, "platform_buttons": RIGHT_SAFE_BOX,
              "top": TOP_SAFE_BOX, "bottom": BOTTOM_SAFE_BOX}
DISCLAIMER = "教学示意 · 非实机录屏"
KINDS = {"terminal", "checklist", "diagram", "ui", "evidence", "warning"}
FONT_FLOORS = {"title": 48, "bullet": 32, "code": 30, "note": 28, "label": 24}
BODY_BOX = (64, 820, 904, 1310)
TITLE_BOX = (64, 284, 904, 460)
BULLET_BOXES = tuple((64, 484 + i * 106, 904, 580 + i * 106) for i in range(3))
NOTE_BOX = (64, 1330, 904, 1440)
PALETTE = {"background": BG, "cream": CREAM, "teal": TEAL, "orange": ORANGE}

class SceneError(ValueError):
    """Invalid display input; nothing has been saved for this render call."""

class LayoutError(SceneError):
    def __init__(self, message: str, report: dict | None = None):
        super().__init__(message)
        self.report = report or {"ok": False, "errors": [message]}

@dataclass(frozen=True)
class TextPlan:
    text: str
    lines: tuple[str, ...]
    size: int
    style: str
    line_height: int
    height: int

@dataclass(frozen=True)
class CodePlan:
    sources: tuple[str, ...]
    fragments: tuple[tuple[str, ...], ...]
    size: int
    style: str
    line_height: int
    row_gap: int
    height: int

def _inside(a, b, tolerance=0.01):
    return (a[0] >= b[0] - tolerance and a[1] >= b[1] - tolerance
            and a[2] <= b[2] + tolerance and a[3] <= b[3] + tolerance)

def _intersects(a, b):
    return a[0] < b[2] and a[2] > b[0] and a[1] < b[3] and a[3] > b[1]

@lru_cache(maxsize=1)
def _font_paths():
    root = Path(os.environ.get("WINDIR", "C:/Windows")) / "Fonts"
    options = {
        "regular": [root / "msyh.ttc", Path("/usr/share/fonts/opentype/noto/NotoSansCJK-Regular.ttc")],
        "bold": [root / "msyhbd.ttc", Path("/usr/share/fonts/opentype/noto/NotoSansCJK-Bold.ttc")],
        "mono": [root / "consola.ttf", Path("/usr/share/fonts/truetype/dejavu/DejaVuSansMono.ttf")],
    }
    result = {}
    for name, candidates in options.items():
        override = os.environ.get("ASTROBOT_FONT_" + name.upper())
        if override:
            candidates = [Path(override)]
        found = next((p for p in candidates if p.is_file()), None)
        if found is None:
            raise SceneError(f"Missing {name} font; set ASTROBOT_FONT_{name.upper()} to a CJK/monospace font.")
        result[name] = str(found.resolve())
    return result

@lru_cache(maxsize=160)
def _font(style, size):
    return ImageFont.truetype(_font_paths()[style], size=size)

def _runs(text, style):
    """Consolas for Latin code, YaHei for CJK. Measurements use actual glyphs."""
    if style != "mono":
        return [(text.expandtabs(4), style)]
    runs = []
    for char in text.expandtabs(4):
        family = "mono" if ord(char) < 0x250 else "regular"
        if unicodedata.combining(char) and runs:
            family = runs[-1][1]
        if runs and runs[-1][1] == family:
            runs[-1] = (runs[-1][0] + char, family)
        else:
            runs.append((char, family))
    return runs

@lru_cache(maxsize=32768)
def _metrics(text, style, size):
    """Advance and true ink bounds, relative to a shared baseline."""
    cursor, ink = 0.0, None
    for run, family in _runs(text, style):
        font = _font(family, size)
        box = font.getbbox(run, anchor="ls")
        if box[2] > box[0] and box[3] > box[1]:
            current = (cursor + box[0], box[1], cursor + box[2], box[3])
            ink = current if ink is None else (
                min(ink[0], current[0]), min(ink[1], current[1]),
                max(ink[2], current[2]), max(ink[3], current[3]))
        cursor += font.getlength(run)
    return cursor, ink or (0.0, 0.0, 0.0, 0.0)

def _width(text, style, size):
    advance, ink = _metrics(text, style, size)
    return max(advance, ink[2]) - min(0, ink[0])

def _clusters(text):
    """Keep combining marks/variation selectors with their base glyph."""
    result = []
    for char in text:
        if result and (unicodedata.combining(char) or char in "\ufe0e\ufe0f" or result[-1].endswith("\u200d")):
            result[-1] += char
        elif char == "\u200d" and result:
            result[-1] += char
        else:
            result.append(char)
    return result

def wrap_text(text: str, width: int, size: int, style: str = "regular") -> tuple[str, ...]:
    """Lossless measured wrapping; no stripping/ellipsis/inserted backslashes.

    For one logical line, ''.join(wrap_text(line, ...)) equals line exactly.
    """
    result = []
    for paragraph in text.split("\n"):
        units = _clusters(paragraph)
        if not units:
            result.append("")
            continue
        start = 0
        while start < len(units):
            lo, hi, best = start + 1, len(units), start
            while lo <= hi:
                mid = (lo + hi) // 2
                if _width("".join(units[start:mid]), style, size) <= width:
                    best, lo = mid, mid + 1
                else:
                    hi = mid - 1
            if best == start:
                raise LayoutError("A glyph cannot fit in its box at the minimum font size.")
            if best < len(units):
                lower = start + max(1, int((best - start) * 0.62))
                breaks = [j for j in range(lower, best + 1)
                          if units[j - 1].isspace() or units[j - 1] in "/=&?,-_，。；："]
                if breaks:
                    best = breaks[-1]
                if style != "mono" and best > start + 1 and units[best] in "，。！？；：、）】》」』":
                    best -= 1
            result.append("".join(units[start:best]))
            start = best
    return tuple(result)

def _line_height(lines, style, size, leading):
    height = max((_metrics(s, style, size)[1][3] - _metrics(s, style, size)[1][1]
                  for s in lines), default=0)
    return max(math.ceil(size * leading), math.ceil(height) + 4)

def _fit(text, box, *, size, minimum, style="regular", leading=1.22, max_lines=None):
    for candidate in range(size, minimum - 1, -1):
        lines = wrap_text(text, box[2] - box[0], candidate, style)
        lh = _line_height(lines, style, candidate, leading)
        if (max_lines is None or len(lines) <= max_lines) and len(lines) * lh <= box[3] - box[1]:
            return TextPlan(text, lines, candidate, style, lh, len(lines) * lh)
    raise LayoutError(f"Text will not fit at {minimum}px; split the scene or shorten its non-code wording.")

def _code_plan(sources, width, height, *, style="mono", size=36, minimum=30, gap=4):
    for candidate in range(size, minimum - 1, -1):
        fragments = tuple(wrap_text(line, width, candidate, style) for line in sources)
        all_lines = tuple(line for part in fragments for line in part)
        lh = _line_height(all_lines, style, candidate, 1.20)
        used = len(all_lines) * lh + max(0, len(sources) - 1) * gap
        if used <= height:
            return CodePlan(tuple(sources), fragments, candidate, style, lh, gap, used)
    raise LayoutError(f"Code/data needs more space at {minimum}px. Split into another scene; no path was truncated.")

def _stage(i, count):
    return min(2, i * 3 // max(1, count))

def _state(i, count, phase):
    active = min(phase, max((_stage(j, count) for j in range(count)), default=0))
    group = _stage(i, count)
    return "active" if group == active else "done" if group < active else "pending"

def _validate_scene(scene, phase, index, total):
    if not isinstance(scene, dict):
        raise SceneError("scene must be a dictionary")
    if type(phase) is not int or phase not in (0, 1, 2):
        raise SceneError("phase must be 0, 1, or 2")
    if type(index) is not int or type(total) is not int or not 0 <= index < total:
        raise SceneError("index is zero-based and must satisfy 0 <= index < total")
    result = dict(scene)
    result["id"] = str(scene.get("id", "001"))
    if not re.fullmatch(r"[A-Za-z0-9_-]{1,64}", result["id"]):
        raise SceneError("Scene id must be a safe filename: 1-64 ASCII letters, digits, '_' or '-'.")
    result["chapter"] = str(scene.get("chapter", "01"))
    for key, default in (("title", "手机部署机器人"), ("chapter_title", "部署教程"),
                         ("env", "说明"), ("kind", "checklist"), ("note", "")):
        value = scene.get(key, default)
        if not isinstance(value, str):
            raise SceneError(f"{key} must be a string")
        result[key] = value.replace("\r\n", "\n").replace("\r", "\n")
    if result["kind"] not in KINDS:
        raise SceneError("Unknown kind; use terminal/checklist/diagram/ui/evidence/warning")
    for key, limit in (("bullets", 3), ("code", 7)):
        value = scene.get(key, [])
        if not isinstance(value, (tuple, list)) or any(not isinstance(s, str) for s in value):
            raise SceneError(f"{key} must be a list of strings")
        if len(value) > limit:
            raise SceneError(f"Too many {key}: maximum {limit}; split the scene instead of dropping content")
        result[key] = [s.replace("\r\n", "\n").replace("\r", "\n") for s in value]
    display = "\n".join([result[k] for k in ("id", "chapter", "title", "chapter_title", "env", "note")]
                        + result["bullets"] + result["code"])
    if any(unicodedata.category(c) == "Cc" and c not in "\n\t" for c in display):
        raise SceneError("Display text contains unsupported control characters")
    if len(display) > 12000:
        raise SceneError("Scene is too dense; split it into separate steps")
    if re.search(r"\bsk-[A-Za-z0-9_-]{16,}|\bBearer\s+[A-Za-z0-9_.-]{20,}", display):
        raise SceneError("Possible credential in display text; replace it with an explicit placeholder")
    assignment = re.compile(r"(?im)(?:\b(?:access[_-]?token|api[_-]?key|password|passwd|token)|密码|口令)"
                            r"[\"']?\s*[:=]\s*[\"']?([^\s\"',;]+)")
    for match in assignment.finditer(display):
        value = match.group(1)
        placeholder = any(marker in value.lower() for marker in (
            "<", ">", "${", "示例", "自行", "你的", "请", "自设", "替换", "本地", "不可公开", "example", "placeholder", "redacted", "****"))
        if value and not placeholder:
            raise SceneError("Possible credential assignment; use <YOUR_TOKEN> or another explicit placeholder")
    if re.search(r"(?i)(?:autoLoginAccount|NAPCAT_QUICK_ACCOUNT|QQ号|QQ账号)[\"']?\s*[:=：]\s*[\"']?\d{5,12}\b", display):
        raise SceneError("Possible personal QQ account; use an explicit placeholder")
    return result

class _Canvas:
    def __init__(self, scene, phase, index, total):
        self.image = Image.new("RGB", (WIDTH, HEIGHT), BG)
        self.draw = ImageDraw.Draw(self.image)
        self.scene, self.phase = scene, phase
        self.report = {
            "scene_id": scene["id"], "kind": scene["kind"], "phase": phase,
            "index": index, "total": total, "size": [WIDTH, HEIGHT],
            "ok": True, "errors": [], "warnings": [], "truncated": False,
            "safe_zones": {k: list(v) for k, v in SAFE_ZONES.items()},
            "palette": PALETTE, "fonts": dict(_font_paths()),
            "font_floors": dict(FONT_FLOORS), "elements": [], "texts": [],
            "command_rows": [], "disclaimer": DISCLAIMER,
        }

    def _record(self, role, kind, box):
        box = [round(float(v), 3) for v in box]
        self.report["elements"].append({"role": role, "kind": kind, "box": box})
        if not _inside(box, (0, 0, WIDTH, HEIGHT)):
            self.report["errors"].append(f"{role}: outside frame")
        for zone, reserved in SAFE_ZONES.items():
            if _intersects(box, reserved):
                self.report["errors"].append(f"{role}: overlaps {zone}")

    def rect(self, role, box, fill, *, radius=0, outline=None, width=1):
        self._record(role, "shape", box)
        if radius:
            self.draw.rounded_rectangle(box, radius=radius, fill=fill, outline=outline, width=width)
        else:
            self.draw.rectangle(box, fill=fill, outline=outline, width=width)

    def line(self, role, points, fill, width=2):
        half = width / 2
        box = (min(x for x, _ in points) - half, min(y for _, y in points) - half,
               max(x for x, _ in points) + half, max(y for _, y in points) + half)
        self._record(role, "line", box)
        self.draw.line(points, fill=fill, width=width, joint="curve")

    def text(self, role, plan, box, color, *, align="left", valign="top"):
        y = box[1] + (box[3] - box[1] - plan.height) / 2 if valign == "center" else box[1]
        line_boxes = []
        for line in plan.lines:
            advance, ink = _metrics(line, plan.style, plan.size)
            content_width = max(advance, ink[2]) - min(0, ink[0])
            x = box[0] + ((box[2] - box[0] - content_width) / 2 if align == "center" else 0)
            x -= min(0, ink[0])
            baseline = y + (plan.line_height - (ink[3] - ink[1])) / 2 - ink[1]
            cursor = x
            for run, family in _runs(line, plan.style):
                font = _font(family, plan.size)
                self.draw.text((cursor, baseline), run, font=font, fill=color, anchor="ls")
                cursor += font.getlength(run)
            actual = (x + ink[0], baseline + ink[1], x + ink[2], baseline + ink[3])
            if line.strip():
                self._record(role, "ink", actual)
                if not _inside(actual, box, tolerance=0.5):
                    self.report["errors"].append(f"{role}: text ink outside assigned box")
            line_boxes.append([round(float(v), 3) for v in actual])
            y += plan.line_height
        entry = {"role": role, "text": plan.text, "lines": list(plan.lines),
                 "font_size": plan.size, "style": plan.style, "box": list(box),
                 "line_height": plan.line_height, "ink_boxes": line_boxes}
        self.report["texts"].append(entry)
        return entry

    def label(self, role, text, box, color=MUTED, *, size=26, minimum=24,
              style="regular", align="left", valign="center"):
        plan = _fit(text, box, size=size, minimum=minimum, style=style)
        return self.text(role, plan, box, color, align=align, valign=valign)

    def finish(self, out_path):
        self.report["ok"] = not self.report["errors"]
        stable = {"elements": self.report["elements"], "texts": self.report["texts"],
                  "detail_mode": self.report.get("detail_mode")}
        self.report["layout_signature"] = hashlib.sha256(
            json.dumps(stable, sort_keys=True, ensure_ascii=False).encode("utf-8")).hexdigest()
        if not self.report["ok"]:
            raise LayoutError("; ".join(self.report["errors"]), self.report)
        output = Path(out_path)
        if output.suffix.lower() != ".png":
            raise SceneError("Output must be a .png file")
        output.parent.mkdir(parents=True, exist_ok=True)
        self.image.save(output, format="PNG")
        self.report["out_path"] = str(output.resolve())
        return self.report


def _chrome(c, index, total):
    s = c.scene
    c.rect("brand.rule", (64, 120, 112, 126), TEAL, radius=3)
    c.label("brand", "手机部署机器人", (128, 110, 558, 150), CREAM, size=27, style="bold")
    c.rect("env.pill", (588, 114, 904, 158), PANEL, radius=13, outline=LINE)
    c.label("env", s["env"], (604, 118, 888, 154), TEAL, size=26, minimum=24, align="center")
    c.rect("disclaimer.pill", (64, 176, 488, 228), "#352E2B", radius=12)
    c.label("disclaimer", DISCLAIMER, (80, 179, 474, 225), ORANGE, size=30, minimum=30, style="bold")
    c.label("chapter", f'{s["chapter"]} / {s["chapter_title"]}', (64, 238, 904, 276), MUTED, size=27, minimum=24)
    plan = _fit(s["title"], TITLE_BOX, size=70, minimum=48, style="bold", leading=1.17, max_lines=3)
    c.text("title", plan, TITLE_BOX, CREAM)
    c.label("footer.brand", "ASTRBOT / NAPCAT", (64, 1698, 650, 1733), MUTED, size=24, style="mono")
    c.label("footer.page", f"{index + 1:03d} / {total:03d}", (706, 1698, 904, 1733), CREAM,
            size=26, style="mono", align="center")
    c.rect("footer.track", (64, 1740, 904, 1745), LINE, radius=2)
    end = 64 + max(4, round(840 * (index + 1) / total))
    c.rect("footer.progress", (64, 1740, end, 1745), TEAL, radius=2)


def _bullets(c):
    values = c.scene["bullets"]
    for i, box in enumerate(BULLET_BOXES):
        state = _state(i, len(values), c.phase) if i < len(values) else "empty"
        fills = {"active": CREAM, "done": "#173E42", "pending": PANEL, "empty": BG}
        colors = {"active": INK, "done": "#DAF3EB", "pending": "#9FB6C2", "empty": LINE}
        c.rect(f"bullet.{i}.card", box, fills[state], radius=20,
               outline=LINE if state in ("pending", "empty") else fills[state])
        c.rect(f"bullet.{i}.rail", (box[0] + 2, box[1] + 22, box[0] + 6, box[3] - 22),
               TEAL if state in ("active", "done") else LINE, radius=2)
        circle = (84, box[1] + 26, 128, box[1] + 70)
        c.rect(f"bullet.{i}.number_bg", circle, INK if state == "active" else "#203E4C", radius=22)
        c.label(f"bullet.{i}.number", f"{i + 1:02d}", circle, TEAL if state != "empty" else MUTED,
                size=25, style="mono", align="center")
        if i < len(values):
            text_box = (150, box[1] + 8, 880, box[3] - 8)
            plan = _fit(values[i], text_box, size=36, minimum=32, style="bold", leading=1.14, max_lines=2)
            c.text(f"bullet.{i}", plan, text_box, colors[state], valign="center")
            c.report.setdefault("emphasis", {})[f"bullet.{i}"] = state


def _detail_header(c, title, tag, *, light=False, warning=False):
    fill = "#F4E6D4" if warning else CREAM if light else "#102332"
    c.rect("detail.panel", BODY_BOX, fill, radius=24, outline=ORANGE if warning else LINE, width=2)
    color = INK if light or warning else CREAM
    c.rect("detail.icon", (88, 843, 96, 873), ORANGE if warning else "#178875" if light else TEAL, radius=4)
    c.label("detail.title", title, (112, 836, 512, 880), color, size=29, style="bold")
    c.label("detail.tag", tag, (528, 841, 880, 877), "#52717B" if light else MUTED,
            size=24, minimum=24, align="center")
    c.line("detail.divider", [(88, 888), (880, 888)], "#D7DCD5" if light or warning else LINE, width=2)


def _sources(c):
    source = c.scene["code"] if c.scene["kind"] == "terminal" else (c.scene["code"] or c.scene["bullets"])
    return tuple(part for entry in source for part in entry.split("\n"))


def _draw_rows(c, *, mode="terminal"):
    terminal, evidence = mode == "terminal", mode == "evidence"
    light = not terminal
    labels = {"terminal": ("终端命令", "仅显示，不执行"), "ui": ("配置示意", "非实机界面"),
              "evidence": ("记录摘录", "非实时检测"), "checklist": ("执行清单", "逐项核对"),
              "warning": ("操作边界", "先读提示，再操作")}
    _detail_header(c, *labels[mode], light=light, warning=mode == "warning")
    sources = _sources(c)
    if not sources:
        c.label("detail.empty", "本页没有命令或配置项", (100, 952, 864, 1116),
                MUTED if terminal else INK, size=36, minimum=30, align="center")
        c.report["detail_mode"] = mode
        return
    style = "mono" if terminal or evidence or mode == "ui" else "regular"
    plan = _code_plan(sources, 736, 334, style=style, size=42, minimum=30, gap=5)
    # Expand sparse cards vertically instead of packing small text at the top.
    # Font choice and row allocation depend only on content, never on phase.
    free = 334 - plan.height
    padding = min(44, free // max(1, len(sources)))
    y = 907
    for i, (source, fragments) in enumerate(zip(plan.sources, plan.fragments)):
        state = _state(i, len(sources), c.phase)
        text_height = len(fragments) * plan.line_height
        block_height = text_height + padding
        row_box = (86, y - 2, 882, y + block_height + 1)
        if terminal:
            fill = {"active": "#20433F", "done": "#17332F", "pending": "#122A39"}[state]
            fg = {"active": "#F4FFF9", "done": "#BDDBCF", "pending": "#A3B9C5"}[state]
        else:
            fill = {"active": "#D7EAE0", "done": "#E6EBE1", "pending": "#EEEDE5"}[state]
            fg = {"active": INK, "done": "#345650", "pending": "#586C71"}[state]
            if mode == "warning":
                fill = {"active": "#FAD0AA", "done": "#F3DDC7", "pending": "#F2E7D8"}[state]
        c.rect(f"data.{i}.bg", row_box, fill, radius=8)
        c.rect(f"data.{i}.rail", (87, y + 4, 91, y + block_height - 4),
               ORANGE if mode == "warning" else "#198575" if light else TEAL, radius=2)
        for j, fragment in enumerate(fragments):
            line_y = y + padding / 2 + j * plan.line_height
            gutter_color = "#597870" if light else TEAL
            if j == 0:
                c.label(f"data.{i}.{j}.gutter", f"{i + 1:02d}", (98, line_y, 132, line_y + plan.line_height),
                        gutter_color, size=24, style="mono", align="center")
            else:
                # Native strokes avoid a missing U+21B3 glyph in Windows YaHei.
                mid = line_y + plan.line_height / 2
                c.line(f"data.{i}.{j}.wrap", [(106, mid - 8), (106, mid + 2), (123, mid + 2)], gutter_color, width=2)
                c.line(f"data.{i}.{j}.wrap_head", [(117, mid - 3), (123, mid + 2), (117, mid + 7)], gutter_color, width=2)
            line_plan = TextPlan(fragment, (fragment,), plan.size, style, plan.line_height, plan.line_height)
            c.text(f"data.{i}.{j}", line_plan, (140, line_y, 876, line_y + plan.line_height), fg)
        c.report["command_rows"].append({"source_index": i, "source_line": source,
            "fragments": list(fragments), "soft_wrapped": len(fragments) > 1, "font_size": plan.size,
            "group": _stage(i, len(sources)), "state": state, "box": list(row_box),
            "lossless": "".join(fragments) == source})
        y += block_height + plan.row_gap
    if any(len(parts) > 1 for parts in plan.fragments):
        foot = "转折箭头仅表示视觉折行，不是命令字符"
    elif evidence:
        foot = "只展示提供的记录，不推断未验证的结果"
    elif terminal:
        foot = "行号不属于命令；请以配套文字教程为准"
    elif mode == "ui":
        foot = "位置仅作示意，按实际版本核对字段"
    elif mode == "warning":
        foot = "敏感数据留在本地，不出现在公开视频里"
    else:
        foot = "完成一项再继续，不跳过核对步骤"
    c.label("detail.footnote", foot, (88, 1258, 880, 1295), "#496963" if light else MUTED,
            size=25, minimum=24)
    c.report["detail_mode"] = mode


def _diagram(c):
    items = _sources(c)
    if len(items) > 3:
        c.report["warnings"].append("Diagram has >3 nodes; using a lossless data-card fallback rather than tiny nodes.")
        _draw_rows(c, mode="checklist")
        return
    _detail_header(c, "关系示意", "不是实机连线图", light=True)
    if not items:
        c.label("diagram.empty", "按口播理解组件关系", (100, 953, 864, 1165), INK,
                size=36, minimum=30, align="center")
        c.report["detail_mode"] = "diagram"
        return
    n = len(items)
    node_height = 88 if n == 3 else 122 if n == 2 else 202
    gap = 28
    used = n * node_height + (n - 1) * gap
    top = 910 + (326 - used) / 2
    for i, item in enumerate(items):
        y = top + i * (node_height + gap)
        state = _state(i, n, c.phase)
        fill = {"active": INK, "done": "#D6EAE0", "pending": "#E6EAE3"}[state]
        fg = CREAM if state == "active" else "#365954"
        c.rect(f"node.{i}", (106, y, 862, y + node_height), fill, radius=18)
        c.label(f"node.{i}.number", f"0{i + 1}", (126, y + 12, 181, y + node_height - 12),
                TEAL if state == "active" else "#1C7F70", size=28, style="mono", align="center")
        box = (204, y + 6, 840, y + node_height - 6)
        plan = _fit(item, box, size=36, minimum=30, style="bold", leading=1.12)
        c.text(f"node.{i}.text", plan, box, fg, valign="center")
        c.report["command_rows"].append({"source_index": i, "source_line": item,
            "fragments": list(plan.lines), "font_size": plan.size, "soft_wrapped": len(plan.lines) > 1,
            "group": _stage(i, n), "state": state, "box": [106, y, 862, y + node_height],
            "lossless": "".join(plan.lines) == item})
        if i < n - 1:
            middle = y + node_height + 13
            c.line(f"arrow.{i}.stem", [(484, y + node_height + 5), (484, middle + 8)], "#3B8F7A", width=3)
            c.line(f"arrow.{i}.head", [(478, middle + 2), (484, middle + 8), (490, middle + 2)], "#3B8F7A", width=3)
    c.label("detail.footnote", "图中箭头表示本页讲解顺序或关系", (88, 1258, 880, 1295), "#496963", size=25)
    c.report["detail_mode"] = "diagram"


def _note(c):
    warning = c.scene["kind"] == "warning"
    c.rect("note.panel", NOTE_BOX, "#3C2B25" if warning else "#17343B", radius=19)
    c.label("note.tag", "注意" if warning else "记住", (84, 1348, 164, 1419),
            ORANGE if warning else TEAL, size=28, style="bold", align="center")
    note = c.scene["note"] or "账号、Token 和登录二维码不要出现在公开视频里。"
    box = (190, 1343, 876, 1427)
    plan = _fit(note, box, size=32, minimum=28, leading=1.20, max_lines=2)
    c.text("note", plan, box, CREAM, valign="center")


def render_scene(scene: dict, out_path: Path, phase: int = 2, index: int = 0, total: int = 1) -> dict:
    """Save a PNG, return report. index is ZERO based; extra fields are ignored.

    speech is never painted. Input dict is not mutated. Nothing is executed.
    All phases reserve full text geometry. Invalid layouts fail before saving.
    """
    s = _validate_scene(scene, phase, index, total)
    c = _Canvas(s, phase, index, total)
    _chrome(c, index, total)
    _bullets(c)
    if s["kind"] == "diagram":
        _diagram(c)
    else:
        _draw_rows(c, mode=s["kind"])
    _note(c)
    return c.finish(out_path)


def render_cover(out_path: Path) -> dict:
    """Editorial cover; not a phone recording or installation success claim."""
    scene = {"id": "cover", "chapter": "00", "chapter_title": "从准备到验收",
             "title": "把手机变成\n机器人工作站", "env": "完整教学", "kind": "diagram",
             "bullets": ["分清每一步在哪个环境操作", "安装、连接、登录、排查逐项讲", "保留验证边界，不夸大自动恢复"],
             "code": ["手机 + Termux / Linux", "AstrBot + NapCat", "连接配置 → 功能验收"],
             "note": "跟着教程操作；命令请从配套文档复制。"}
    return render_scene(scene, out_path, phase=2)


def make_contact_sheet(paths: Iterable[Path], out_path: Path) -> dict:
    """Inspection sheet, not a video frame: video safe zones do not apply."""
    values = [Path(p) for p in paths]
    if not values:
        raise SceneError("Contact sheet needs at least one PNG")
    output = Path(out_path)
    if output.suffix.lower() != ".png":
        raise SceneError("Contact sheet output must be PNG")
    if any(p.resolve() == output.resolve() for p in values):
        raise SceneError("Contact sheet must not overwrite a source image")
    columns = min(3, len(values))
    thumb_w, thumb_h, pad, caption = 324, 576, 22, 48
    rows = math.ceil(len(values) / columns)
    image = Image.new("RGB", (pad + columns * (thumb_w + pad), pad + rows * (thumb_h + caption + pad)), BG)
    draw = ImageDraw.Draw(image)
    for i, path in enumerate(values):
        with Image.open(path) as source:
            source = source.convert("RGB")
            source.thumbnail((thumb_w, thumb_h), Image.Resampling.LANCZOS)
            x = pad + i % columns * (thumb_w + pad)
            y = pad + i // columns * (thumb_h + caption + pad)
            image.paste(source, (x + (thumb_w - source.width) // 2, y))
        lines = wrap_text(path.name, thumb_w, 21)
        if len(lines) > 2:
            raise SceneError("Contact sheet filename too long for two caption lines")
        for j, line in enumerate(lines):
            draw.text((x, y + thumb_h + 4 + j * 22), line, fill=CREAM, font=_font("regular", 21))
    output.parent.mkdir(parents=True, exist_ok=True)
    image.save(output, format="PNG")
    return {"ok": True, "count": len(values), "size": list(image.size), "out_path": str(output.resolve())}


def demo_scenes():
    """Design fixtures, NOT a usable installation script."""
    return [
        {"id": "demo_terminal", "chapter": "02", "chapter_title": "进入正确的运行环境",
         "title": "先看提示符\n再输入命令", "env": "Termux", "kind": "terminal",
         "bullets": ["先确认你还在 Termux 环境里", "命令按配套文档逐行执行", "读完提示再进入 Linux 环境"],
         "code": ["pwd", "uname -m", "proot-distro login debian"],
         "note": "环境不同，路径和命令也不同，不要混着执行。"},
        {"id": "demo_checklist", "chapter": "01", "chapter_title": "动手之前",
         "title": "安装前的\n准备清单", "env": "系统设置", "kind": "checklist",
         "bullets": ["先核对教程说明的适用范围", "准备网络、空间和供电条件", "了解账号与数据的安全边界"],
         "code": ["设备条件：按教程逐项确认", "安装来源：使用官方说明", "敏感信息：只保留在本地"],
         "note": "这张图是准备清单，不代表已完成实机验证。"},
        {"id": "demo_diagram", "chapter": "00", "chapter_title": "先理解组件关系",
         "title": "三个组件\n各做什么？", "env": "说明", "kind": "diagram",
         "bullets": ["Termux 提供手机上的运行入口", "NapCat 负责 QQ 协议侧连接", "AstrBot 负责机器人处理流程"],
         "code": ["Termux / Linux · 运行环境", "NapCat · QQ 连接组件", "AstrBot · 机器人处理"],
         "note": "这是概念关系图，不是登录成功的证明。"},
        {"id": "demo_ui", "chapter": "05", "chapter_title": "浏览器中的连接配置",
         "title": "核对地址\n与访问口令", "env": "手机浏览器", "kind": "ui",
         "bullets": ["确认填写的是本机服务地址", "两侧字段要按教程对应核对", "保存后还要检查连接状态"],
         "code": ["服务地址 = http://127.0.0.1:6185", "协议类型 = <按教程选择>", "Token = <YOUR_TOKEN>"],
         "note": "仅示意字段；页面位置随版本可能变化。"},
        {"id": "demo_evidence", "chapter": "08", "chapter_title": "如实记录验证范围",
         "title": "能打开面板\n不等于 QQ 在线", "env": "说明", "kind": "evidence",
         "bullets": ["分别核对面板与账号状态", "不能把一项成功推断为全部成功", "明确记录仍未验证的项目"],
         "code": ["面板访问：<本次实测结果>", "QQ 登录：<本次实测结果>", "整机重启：<待独立验证>"],
         "note": "这里是记录格式示意，没有宣称已检测成功。"},
        {"id": "demo_warning", "chapter": "09", "chapter_title": "公开发布前的检查",
         "title": "这些信息\n不能进入画面", "env": "说明", "kind": "warning",
         "bullets": ["不要展示真实账号和登录二维码", "API Key 与 Token 都使用占位符", "录屏与日志都要做脱敏检查"],
         "code": ["账号：<YOUR_ACCOUNT>", "API_KEY = <YOUR_API_KEY>", "二维码：不渲染、不展示"],
         "note": "打码不只是遮一点；敏感内容最好从源头移除。"},
        {"id": "demo_longcode", "chapter": "03", "chapter_title": "长命令显示与路径核对",
         "title": "长命令怎么读？\n路径一字不少", "env": "Debian", "kind": "terminal",
         "bullets": ["同一行号表示同一条原始行", "折行标记不是要输入的字符", "长路径从配套文档复制最稳妥"],
         "code": ["cd /opt/astrbot/tutorial/configuration", "curl --fail --location \\",
                  "  https://example.invalid/releases/tutorial/arm64/configuration-guide.json \\",
                  "  --output /tmp/tutorial-configuration.json", "printf '%s\\n' '中文路径示意：保留完整内容'"],
         "note": "示例域名不可用于安装；这里仅测试命令排版。"},
        {"id": "demo_longtitle", "chapter": "10", "chapter_title": "将服务恢复与整机重启分开记录",
         "title": "服务能恢复，并不代表整机重启后能无人值守登录", "env": "Ubuntu / Debian", "kind": "evidence",
         "bullets": ["分别记录每种场景的验证结论", "出现风控仍可能需要人工确认", "只承诺你真正验证过的能力"],
         "code": ["服务重启测试：<本次记录>", "整机重启测试：<独立记录>"],
         "note": "不要把单次恢复成功写成永久免登录保证。"},
    ]


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    mode = parser.add_mutually_exclusive_group(required=True)
    mode.add_argument("--scenes", type=Path, help="Read-only JSON array or object with a scenes array")
    mode.add_argument("--demo", action="store_true", help="Demo PNGs only; no scene/TTS edits")
    parser.add_argument("--out-dir", type=Path, help="Defaults to visual_tests for --demo")
    args = parser.parse_args(argv)
    if args.scenes and not args.out_dir:
        parser.error("--scenes requires --out-dir")
    out = args.out_dir or Path(__file__).resolve().parent / "visual_tests"
    if args.demo:
        scenes = demo_scenes()
    else:
        payload = json.loads(args.scenes.read_text(encoding="utf-8-sig"))
        scenes = payload.get("scenes") if isinstance(payload, dict) else payload
        if not isinstance(scenes, list) or not scenes:
            raise SceneError("JSON must be a nonempty scene array or {scenes: [...]}")
    ids = [str(s.get("id", "001")) if isinstance(s, dict) else "" for s in scenes]
    if len(set(ids)) != len(ids):
        raise SceneError("Duplicate scene ids would overwrite frames; make all ids unique")
    reports, failures, paths = [], [], []
    for index, scene in enumerate(scenes):
        try:
            checked = _validate_scene(scene, 0, index, len(scenes))
            for phase in range(3):
                path = out / f'{checked["id"]}_p{phase}.png'
                reports.append(render_scene(scene, path, phase=phase, index=index, total=len(scenes)))
                if phase == 2:
                    paths.append(path)
        except SceneError as exc:
            failures.append({"index": index, "scene_id": ids[index], "error": str(exc),
                             "report": getattr(exc, "report", None)})
    summary = {"ok": not failures, "expected_frames": len(scenes) * 3,
               "written_frames": len(reports), "failed_scenes": failures, "frames": reports,
               "subtitle_box": list(SUBTITLE_BOX), "font_floors": FONT_FLOORS}
    if args.demo:
        if paths:
            make_contact_sheet(paths, out / "contact_kinds.png")
            terminal_paths = [out / f"demo_terminal_p{p}.png" for p in range(3)]
            if all(path.is_file() for path in terminal_paths):
                make_contact_sheet(terminal_paths, out / "contact_phases.png")
        render_cover(out / "cover.png")
    else:
        out.mkdir(parents=True, exist_ok=True)
        (out / "layout_report.json").write_text(json.dumps(summary, ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps({k: v for k, v in summary.items() if k != "frames"}, ensure_ascii=False, indent=2))
    return 0 if summary["ok"] else 1


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except (SceneError, OSError, json.JSONDecodeError) as exc:
        print(f"Renderer error: {exc}", file=sys.stderr)
        raise SystemExit(2)
