"""Renderer tests. Run: python -B tests_render.py

Writes ONLY PNG review fixtures in this directory's visual_tests/. CLI JSON I/O
is mocked, so tests never create or edit scenes.json/layout_report.json. No TTS,
FFmpeg, network, devices, repository operations or third-party test framework.
"""
from __future__ import annotations
import copy
import hashlib
import io
import json
import random
import unittest
from contextlib import redirect_stdout
from pathlib import Path
from unittest.mock import patch
from PIL import Image, ImageChops, ImageColor, ImageDraw
import render_cards as r

ROOT = Path(__file__).resolve().parent
OUT = ROOT / "visual_tests"


def text_entry(report, role):
    return next(item for item in report["texts"] if item["role"] == role)


class RendererTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.scenes = r.demo_scenes()
        cls.reports = {}
        for index, scene in enumerate(cls.scenes):
            for phase in range(3):
                path = OUT / f'{scene["id"]}_p{phase}.png'
                cls.reports[(scene["id"], phase)] = r.render_scene(scene, path, phase, index, len(cls.scenes))
        cls.cover = r.render_cover(OUT / "cover.png")
        r.make_contact_sheet([OUT / f'{s["id"]}_p2.png' for s in cls.scenes], OUT / "contact_kinds.png")
        r.make_contact_sheet([OUT / f"demo_terminal_p{i}.png" for i in range(3)], OUT / "contact_phases.png")

    def render(self, scene, name, phase=2):
        return r.render_scene(scene, OUT / f"test_{name}.png", phase)

    def test_all_six_kinds(self):
        self.assertEqual({s["kind"] for s in self.scenes}, r.KINDS)
        self.assertEqual(len(self.reports), 24)
        for report in self.reports.values():
            self.assertTrue(report["ok"])
            self.assertFalse(report["truncated"])
            self.assertEqual(report["errors"], [])

    def test_all_images_are_rgb_1080x1920(self):
        for report in [*self.reports.values(), self.cover]:
            with Image.open(report["out_path"]) as im:
                self.assertEqual(im.size, (1080, 1920))
                self.assertEqual(im.mode, "RGB")
                self.assertEqual(im.format, "PNG")

    def test_safe_zones_are_pixel_blank(self):
        for report in [*self.reports.values(), self.cover]:
            with Image.open(report["out_path"]) as im:
                for name, zone in r.SAFE_ZONES.items():
                    crop = im.crop(zone)
                    expected = Image.new("RGB", crop.size, r.BG)
                    self.assertIsNone(ImageChops.difference(crop, expected).getbbox(), (report["scene_id"], name))

    def test_real_subtitle_overlay_envelope_is_blank(self):
        # Exact integration coordinates supplied by the main editor.
        with Image.open(OUT / "demo_longcode_p2.png") as im:
            crop = im.crop((60, 1464, 906, 1680))
            self.assertIsNone(ImageChops.difference(crop, Image.new("RGB", crop.size, r.BG)).getbbox())

    def test_all_shapes_and_ink_respect_safe_zones(self):
        for report in self.reports.values():
            for element in report["elements"]:
                self.assertTrue(r._inside(element["box"], (0, 0, r.WIDTH, r.HEIGHT)))
                for zone in r.SAFE_ZONES.values():
                    self.assertFalse(r._intersects(element["box"], zone), element)

    def test_ink_inside_assigned_text_box(self):
        for report in self.reports.values():
            for entry in report["texts"]:
                for box in entry["ink_boxes"]:
                    self.assertTrue(r._inside(box, entry["box"], tolerance=0.5), entry["role"])

    def test_no_text_ink_overlaps_other_text(self):
        for report in self.reports.values():
            leaves = [e for e in report["elements"] if e["kind"] == "ink"]
            for i, first in enumerate(leaves):
                for second in leaves[i + 1:]:
                    self.assertFalse(r._intersects(first["box"], second["box"]),
                                     (report["scene_id"], first["role"], second["role"]))

    def test_every_phase_has_prominent_disclaimer(self):
        for report in self.reports.values():
            tag = text_entry(report, "disclaimer")
            self.assertEqual(tag["text"], "教学示意 · 非实机录屏")
            self.assertGreaterEqual(tag["font_size"], 28)

    def test_phase_layout_identical(self):
        for scene in self.scenes:
            reports = [self.reports[(scene["id"], p)] for p in range(3)]
            self.assertEqual(len({rep["layout_signature"] for rep in reports}), 1)
            self.assertEqual(reports[0]["texts"], reports[1]["texts"])
            self.assertEqual(reports[1]["elements"], reports[2]["elements"])

    def test_phase_emphasis_moves(self):
        for phase in range(3):
            rep = self.reports[("demo_terminal", phase)]
            for i in range(3):
                self.assertEqual(rep["emphasis"][f"bullet.{i}"] == "active", i == phase)
        with Image.open(OUT / "demo_terminal_p0.png") as a, Image.open(OUT / "demo_terminal_p2.png") as b:
            self.assertIsNotNone(ImageChops.difference(a, b).getbbox())

    def test_all_supplied_code_preserved(self):
        for scene in self.scenes:
            expected = [line for item in scene["code"] for line in item.split("\n")]
            for phase in range(3):
                rows = self.reports[(scene["id"], phase)]["command_rows"]
                self.assertEqual([row["source_line"] for row in rows], expected)
                for row in rows:
                    self.assertTrue(row["lossless"])
                    self.assertEqual("".join(row["fragments"]), row["source_line"])

    def test_font_floors(self):
        for rep in self.reports.values():
            for entry in rep["texts"]:
                role = entry["role"]
                minimum = 48 if role == "title" else 32 if role in ("bullet.0", "bullet.1", "bullet.2") else 28 if role == "note" else 30 if role.startswith("data.") and not role.endswith("gutter") else 24
                self.assertGreaterEqual(entry["font_size"], minimum, role)

    def test_long_url_wraps_without_loss(self):
        scene = copy.deepcopy(self.scenes[0])
        scene["code"] = ["https://example.invalid/" + "very-long-configuration-directory/" * 5 + "keep-this-critical-tail.json?arch=arm64&mode=local"]
        report = self.render(scene, "long_url")
        self.assertTrue(report["command_rows"][0]["soft_wrapped"])
        self.assertEqual("".join(report["command_rows"][0]["fragments"]), scene["code"][0])
        self.assertIn("转折箭头", text_entry(report, "detail.footnote")["text"])

    def test_wrapped_marker_is_native_shape_not_missing_font_glyph(self):
        report = self.reports[("demo_longcode", 2)]
        self.assertTrue(any(e["role"].endswith(".wrap") and e["kind"] == "line" for e in report["elements"]))
        self.assertFalse(any("↳" in e["text"] for e in report["texts"]))

    def test_shell_whitespace_quotes_tabs_and_backslash(self):
        scene = copy.deepcopy(self.scenes[0])
        scene["code"] = ["printf '%s\\n' '中文 路径'  ", "\tcd /opt/astrbot/配置目录", "echo \"a&&b\" && echo '\\'", "", "  echo done"]
        report = self.render(scene, "shell_chars")
        self.assertEqual(["".join(row["fragments"]) for row in report["command_rows"]], scene["code"])

    def test_multiline_shell_hard_newlines_retained(self):
        scene = copy.deepcopy(self.scenes[0])
        scene["code"] = ["printf hello \\\n  world\n", "echo done"]
        report = self.render(scene, "multiline")
        self.assertEqual([row["source_line"] for row in report["command_rows"]], ["printf hello " + chr(92), "  world", "", "echo done"])

    def test_crlf_normalization(self):
        scene = copy.deepcopy(self.scenes[0])
        scene["code"] = ["echo one\r\necho two"]
        report = self.render(scene, "crlf")
        self.assertEqual([row["source_line"] for row in report["command_rows"]], ["echo one", "echo two"])

    def test_seven_lines(self):
        for kind in r.KINDS:
            scene = copy.deepcopy(self.scenes[0])
            scene.update(kind=kind, code=[f"step_{i} = <本地填写第{i}项>" for i in range(7)])
            report = self.render(scene, f"seven_{kind}")
            self.assertEqual(len(report["command_rows"]), 7)
            self.assertTrue(report["ok"])
            if kind == "diagram":
                self.assertTrue(report["warnings"])

    def test_long_title_uses_measured_multiline_layout(self):
        scene = copy.deepcopy(self.scenes[0])
        scene["title"] = "把服务重启恢复与手机整机重启后的自动登录能力分别验证记录不要把两种结论混为一谈"
        report = self.render(scene, "long_title")
        title = text_entry(report, "title")
        self.assertGreater(len(title["lines"]), 1)
        self.assertEqual("".join(title["lines"]), scene["title"])
        self.assertGreaterEqual(title["font_size"], 48)

    def test_30_character_bullets_and_42_character_note(self):
        scene = copy.deepcopy(self.scenes[0])
        scene["bullets"] = ["核对当前运行环境并记录每次操作之后的实际结果不要跳过验收步骤再"[:30]] * 3
        scene["note"] = "保留完整路径不要为了塞进画面删掉命令参数没有测试过的结论必须标为未验证敏感信息留在本地"[:42]
        report = self.render(scene, "max_chinese")
        self.assertTrue(report["ok"])
        self.assertEqual("".join(text_entry(report, "note")["lines"]), scene["note"])

    def test_very_dense_code_rejected_before_save(self):
        scene = copy.deepcopy(self.scenes[0])
        scene["code"] = ["/critical/path/" * 30] * 7
        path = OUT / "must_not_exist_overflow.png"
        with patch.object(Image.Image, "save") as save:
            with self.assertRaises(r.LayoutError):
                r.render_scene(scene, path)
            save.assert_not_called()

    def test_dense_title_bullet_and_note_never_truncate(self):
        for field, value in (("title", "标题" * 100), ("note", "提示" * 100), ("bullets", ["要点" * 100])):
            scene = copy.deepcopy(self.scenes[0])
            scene[field] = value
            with patch.object(Image.Image, "save") as save:
                with self.assertRaises(r.LayoutError):
                    r.render_scene(scene, OUT / "must_not_exist_text.png")
                save.assert_not_called()

    def test_long_fields_all_kinds(self):
        for kind in r.KINDS:
            scene = copy.deepcopy(self.scenes[0])
            scene.update(kind=kind, code=["路径 /opt/astrbot/configuration/保留完整目录与参数",
                                         "地址 https://example.invalid/tutorial/configuration.json"])
            report = self.render(scene, f"long_{kind}")
            self.assertTrue(report["ok"])
            self.assertTrue(all(row["lossless"] for row in report["command_rows"]))

    def test_input_is_immutable(self):
        scene = copy.deepcopy(self.scenes[0])
        original = copy.deepcopy(scene)
        self.render(scene, "immutable")
        self.assertEqual(scene, original)

    def test_speech_never_painted(self):
        scene = copy.deepcopy(self.scenes[0])
        scene["speech"] = "ONLY_IN_AUDIO_NOT_ON_SCREEN" * 10000
        report = self.render(scene, "speech_hidden")
        self.assertNotIn("ONLY_IN_AUDIO", json.dumps(report))

    def test_terminal_without_code_does_not_label_prose_as_commands(self):
        scene = copy.deepcopy(self.scenes[0])
        scene["code"] = []
        report = self.render(scene, "no_code")
        self.assertEqual(report["command_rows"], [])
        self.assertIn("没有命令", text_entry(report, "detail.empty")["text"])

    def test_minimal_scene(self):
        report = self.render({"id": "minimal"}, "minimal")
        self.assertTrue(report["ok"])

    def test_invalid_phase_index_kind_and_counts(self):
        scene = copy.deepcopy(self.scenes[0])
        for args in ((-1, 0, 1), (3, 0, 1), (True, 0, 1), (1, -1, 1), (1, 1, 1), (1, 0, 0)):
            with self.assertRaises(r.SceneError):
                r.render_scene(scene, OUT / "must_not_exist_invalid.png", *args)
        for update in ({"kind": "unknown"}, {"bullets": ["x"] * 4}, {"code": ["x"] * 8}, {"code": "echo x"}):
            with self.assertRaises(r.SceneError):
                self.render(dict(scene, **update), "must_not_exist_invalid")

    def test_path_traversal_rejected(self):
        for bad in ("../escape", "C:/tmp/escape", "..\\escape", "x/y", "", "a" * 65):
            with self.assertRaises(r.SceneError):
                self.render(dict(self.scenes[0], id=bad), "must_not_exist_traversal")

    def test_obvious_credentials_rejected(self):
        for code in ("API_KEY = " + "sk-" + "FAKE_TEST_CREDENTIAL_123456789", "Token = fake-private-value",
                     "autoLoginAccount = 123456789", "NAPCAT_QUICK_ACCOUNT=987654321", "Authorization: Bearer FAKE_TEST_TOKEN_1234567890"):
            with self.assertRaises(r.SceneError):
                self.render(dict(self.scenes[0], code=[code]), "must_not_exist_secret")

    def test_placeholder_and_variable_credentials_allowed(self):
        for code in ("Token = <YOUR_TOKEN>", "API_KEY=${API_KEY}", "password = <你自己设置的口令>"):
            checked = r._validate_scene(dict(self.scenes[0], code=[code]), 2, 0, 1)
            self.assertEqual(checked["code"], [code])

    def test_output_must_be_png(self):
        with self.assertRaises(r.SceneError):
            r.render_scene(self.scenes[0], OUT / "not_a_png.jpg")

    def test_failed_render_does_not_touch_existing_file(self):
        existing = OUT / "demo_terminal_p2.png"
        before = existing.read_bytes()
        with self.assertRaises(r.LayoutError):
            r.render_scene(dict(self.scenes[0], code=["data" * 2000]), existing)
        self.assertEqual(hashlib.sha256(before).digest(), hashlib.sha256(existing.read_bytes()).digest())

    def test_proportional_measurement_and_combining_marks(self):
        self.assertGreater(r._width("WWWWW", "regular", 36), r._width("iiiii", "regular", 36))
        value = "Cafe\u0301 文件配置/路径 with WWMii --保留参数"
        lines = r.wrap_text(value, 185, 32, "mono")
        self.assertEqual("".join(lines), value)
        self.assertFalse(any(line.startswith("\u0301") for line in lines))
        self.assertTrue(all(r._width(line, "mono", 32) <= 185 for line in lines))

    def test_random_lossless_wrapping(self):
        rng = random.Random(20261003)
        alphabet = "配置路径中文ABCWMi  /?=;&_-'\\.0123456789"
        for i in range(150):
            value = "".join(rng.choice(alphabet) for _ in range(rng.randint(1, 180)))
            width = rng.randint(90, 730)
            size = rng.randint(30, 42)
            lines = r.wrap_text(value, width, size, "mono")
            self.assertEqual("".join(lines), value)
            self.assertTrue(all(r._width(line, "mono", size) <= width for line in lines))

    def test_reports_are_json_serializable(self):
        for report in self.reports.values():
            decoded = json.loads(json.dumps(report, ensure_ascii=False))
            self.assertEqual(decoded["size"], [1080, 1920])
            self.assertEqual(decoded["layout_signature"], report["layout_signature"])

    def test_contact_sheet_and_source_protection(self):
        paths = [OUT / "demo_terminal_p0.png", OUT / "demo_terminal_p1.png"]
        report = r.make_contact_sheet(paths, OUT / "test_contact.png")
        self.assertEqual(report["count"], 2)
        with self.assertRaises(r.SceneError):
            r.make_contact_sheet(paths, paths[0])
        with self.assertRaises(r.SceneError):
            r.make_contact_sheet([], OUT / "must_not_exist_sheet.png")

    def test_cli_generates_all_three_phases_and_report_with_mocked_json_io(self):
        sample = [dict(self.scenes[0], id="cli001"), dict(self.scenes[1], id="cli002")]
        for payload in (sample, {"scenes": sample}):
            with patch.object(Path, "read_text", return_value=json.dumps(payload)), \
                 patch.object(Path, "write_text") as write, \
                 patch.object(r, "render_scene", return_value={"ok": True, "errors": []}) as render, \
                 redirect_stdout(io.StringIO()):
                result = r.main(["--scenes", str(ROOT / "not_a_real_scene_file.json"), "--out-dir", str(OUT)])
            self.assertEqual(result, 0)
            self.assertEqual(render.call_count, 6)
            self.assertEqual([c.kwargs["phase"] for c in render.call_args_list], [0, 1, 2, 0, 1, 2])
            self.assertEqual([c.args[1].name for c in render.call_args_list],
                             ["cli001_p0.png", "cli001_p1.png", "cli001_p2.png", "cli002_p0.png", "cli002_p1.png", "cli002_p2.png"])
            data = json.loads(write.call_args.args[0])
            self.assertEqual(data["written_frames"], 6)
            self.assertTrue(data["ok"])

    def test_cli_failure_is_machine_readable_and_nonzero(self):
        payload = [dict(self.scenes[0], title="x" * 1000)]
        with patch.object(Path, "read_text", return_value=json.dumps(payload)), \
             patch.object(Path, "write_text") as write, redirect_stdout(io.StringIO()):
            result = r.main(["--scenes", str(ROOT / "mock_scenes.json"), "--out-dir", str(OUT)])
        self.assertEqual(result, 1)
        summary = json.loads(write.call_args.args[0])
        self.assertEqual(summary["written_frames"], 0)
        self.assertEqual(len(summary["failed_scenes"]), 1)

    def test_duplicate_ids_fail_before_render(self):
        with patch.object(Path, "read_text", return_value=json.dumps([self.scenes[0]] * 2)), \
             patch.object(r, "render_scene") as render:
            with self.assertRaises(r.SceneError):
                r.main(["--scenes", "mock.json", "--out-dir", str(OUT)])
            render.assert_not_called()

    def test_overlay_preview_is_inspection_only(self):
        # Does not modify main compositing or TTS. This is just a review PNG.
        with Image.open(OUT / "demo_longcode_p2.png") as original:
            preview = original.copy()
        d = ImageDraw.Draw(preview)
        d.rounded_rectangle((60, 1464, 906, 1680), radius=22, fill="#07131C")
        d.text((78, 1494), "长命令只是视觉折行。\n复制时仍以原始命令为准。", font=r._font("regular", 44), fill=r.CREAM, spacing=16)
        preview.save(OUT / "test_subtitle_overlay.png")
        self.assertEqual(preview.size, (1080, 1920))


if __name__ == "__main__":
    unittest.main(verbosity=2)
