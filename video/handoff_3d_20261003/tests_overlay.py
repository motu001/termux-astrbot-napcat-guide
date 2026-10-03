"""Run: python -B tests_overlay.py. Previews and contact sheet stay in overlay_tests/."""
import hashlib
import json
import math
from pathlib import Path
import time
import unittest
from unittest.mock import patch

from PIL import Image, ImageDraw

from overlay import COPY, OverlayPainter, envelope, font, raster, stamp

HERE = Path(__file__).resolve().parent
from render_motion import SOURCE


class OverlayTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.timeline = json.loads((SOURCE / "timeline.json").read_text(encoding="utf-8"))
        cls.subtitles = json.loads((SOURCE / "subtitle_events.json").read_text(encoding="utf-8"))
        cls.painter = OverlayPainter(cls.timeline, cls.subtitles)

    def test_rgba_timing_and_deterministic_seek(self):
        p = self.painter
        self.assertAlmostEqual(p.duration, 4600 / 30)
        a = p.frame(8)
        self.assertEqual((a.mode, a.size), ("RGBA", (1080, 1920)))
        self.assertEqual(a.tobytes(), p.frame(8).tobytes())
        self.assertNotEqual(a.tobytes(), p.frame(8.5).tobytes())
        self.assertIsNone(p.frame(-1).getbbox())
        self.assertIsNone(p.frame(p.duration).getbbox())
        with self.assertRaises(ValueError):
            p.frame(float("nan"))
        self.assertEqual(OverlayPainter(self.timeline, self.subtitles, 540, 960).frame(8).size, (540, 960))

    def test_animated_text_bounds_and_word_integrity(self):
        p = self.painter
        for kind, (x0, y0, x1, y1) in p.layout_bounds:
            self.assertGreaterEqual(x0, 72)
            self.assertLessEqual(x1, 915)
            low, high = (180, 430) if kind == "title" else (1510, 1660)
            self.assertGreaterEqual(y0, low)
            self.assertLessEqual(y1, high)
        for source, rows, size in zip(p.subtitles, p.subtitle_lines, p.subtitle_sizes):
            self.assertLessEqual(len(rows), 2)
            self.assertGreaterEqual(size, 44)
            self.assertEqual("".join(source["text"].split()), "".join("".join(rows).split()))
            for word in ("Termux", "Agent", "AstrBot", "NapCat", "OneBot", "SSH", "QQ", "授权", "通过", "交付", "验证", "不需要"):
                if word in source["text"].replace("\n", ""):
                    self.assertTrue(any(word in row for row in rows), word)

    def test_every_second_glyphs_and_protected_regions(self):
        p = self.painter
        strings = [e["text"] for e in p.subtitles] + ["教学动画 · 非实机录屏", "ASTRBOT / MOBILE AUTOMATION 0123456789"]
        strings += [text for title, role, _, states in COPY for text in (title, role, *states)]
        # Verify actual installed font glyph masks against its .notdef glyph, not just nonempty files.
        for bold in (False, True):
            face = font(48, bold)
            missing = bytes(face.getmask("\u0378"))
            for ch in set("".join(strings)) - set(" \n\t"):
                self.assertNotEqual(bytes(face.getmask(ch)), missing, f"Missing glyph: {ch}")
                self.assertIsNotNone(face.getmask(ch).getbbox(), ch)
        samples = list(range(math.ceil(p.duration)))
        samples += [s["start"] + delta for s in p.scenes for delta in (-.55, -.01, 0, .01, .55)]
        hashes = set()
        for t in samples:
            if not 0 <= t < p.duration:
                continue
            alpha = p.frame(t).getchannel("A")
            for box in ((0, 500, 1080, 1321), (940, 0, 1080, 1920), (0, 1740, 1080, 1920)):
                self.assertIsNone(alpha.crop(box).getbbox(), (t, box))
            if isinstance(t, int):
                hashes.add(hashlib.sha256(alpha.tobytes()).digest())
        self.assertEqual(len(hashes), math.ceil(p.duration))

    def test_scene_fades_cached_layout_and_straight_alpha(self):
        for s in self.painter.scenes:
            a, b = s["start"], s["start"] + s["duration"]
            self.assertEqual(envelope(a, a, b), 0)
            self.assertAlmostEqual(envelope(a + .275, a, b), .5)
            self.assertEqual(envelope(a + .55, a, b), 1)
            self.assertAlmostEqual(envelope(b - .275, a, b), .5)
        with patch("overlay.wrap", side_effect=AssertionError("Per-frame reflow")), patch("overlay.raster", side_effect=AssertionError("Per-frame text raster")):
            self.painter.frame(19)
        sample = Image.new("RGBA", (10, 10))
        stamp(sample, Image.new("RGBA", (4, 4), (246, 242, 228, 255)), 2, 2, .5)
        self.assertEqual(sample.getpixel((3, 3)), (246, 242, 228, 128))


def previews():
    p = OverlayTests.painter
    target = HERE / "overlay_tests"
    target.mkdir(exist_ok=True)
    sheet = Image.new("RGB", (1080, 1048), (8, 15, 26))
    start = time.perf_counter()
    for i, scene in enumerate(p.scenes):
        t = scene["start"] + scene["duration"] / 2
        overlay = p.frame(t)
        overlay.save(target / f"{i+1:02d}_mid_overlay.png")
        # Neutral preview only: the central object space remains intentionally unrendered.
        preview = Image.new("RGBA", p.size, (13, 24, 42, 255))
        preview.alpha_composite(overlay)
        tile = preview.convert("RGB").resize((270, 480), Image.Resampling.LANCZOS)
        x, y = (i % 4)*270, (i // 4)*524
        sheet.paste(tile, (x, y+36))
        ImageDraw.Draw(sheet).text((x+12, y+8), f"{i+1:02d}  /  {t:.2f}s", font=font(17), fill=(192, 207, 220))
    sheet.save(target / "contact_sheet.jpg", quality=95)
    print(f"8 RGBA examples + contact sheet: {target} ({time.perf_counter()-start:.2f}s)")


if __name__ == "__main__":
    result = unittest.TextTestRunner(verbosity=2).run(unittest.defaultTestLoader.loadTestsFromTestCase(OverlayTests))
    if result.wasSuccessful():
        previews()
    raise SystemExit(not result.wasSuccessful())
