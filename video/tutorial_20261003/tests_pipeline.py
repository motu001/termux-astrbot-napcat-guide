import importlib.util, math, unittest
from unittest.mock import patch
from pathlib import Path
HERE=Path(__file__).resolve().parent
spec=importlib.util.spec_from_file_location('build_video', HERE/'build_video.py')
b=importlib.util.module_from_spec(spec);spec.loader.exec_module(b)

class PipelineTests(unittest.TestCase):
    def test_caption_preserves_text(self):
        examples=[
            '先确认你在Termux主界面，然后执行命令。看到aarch64再继续，不要跳过错误。',
            '这是一段很长的测试文字'*35,
            '在Ubuntu中运行uv tool install astrbot --python 3.12；初始化只做一次。',
            'http://127.0.0.1:6185/是管理面板。ws://127.0.0.1:6199/ws才是反向连接地址。',
            '正常。下一步？检查！不要覆盖密钥。'
        ]
        for text in examples:
            chunks=b.caption_chunks(text)
            self.assertEqual(''.join(chunks),text)
            self.assertTrue(all(len(b.wrap_caption(c))<=2 for c in chunks))
    def test_all_subtitle_lines_fit(self):
        f=b.ImageFont.truetype('C:/Windows/Fonts/msyh.ttc',44)
        for line in b.wrap_caption('Termux管理环境，AstrBot负责对话，NapCat负责QQ接入。'*5):
            self.assertLessEqual(f.getlength(line),785)
    def test_technical_names_do_not_split_across_lines(self):
        for term in ['Termux','NapCat','WebSocket','OneBot','127.0.0.1']:
            text='先查看官方教程'+term+'对应步骤，然后执行。'
            lines=b.wrap_caption(text,width=400)
            self.assertEqual(''.join(lines),text)
            self.assertTrue(any(term in line for line in lines),(term,lines))
    def test_reused_engine_resolves_current_workdir_at_call_time(self):
        from types import SimpleNamespace
        alternate=Path('alternate_course')
        with patch.object(b,'WORK',alternate), patch.object(b.subprocess,'run',return_value=SimpleNamespace(returncode=0,stderr=b'',stdout=b'')) as execute:
            b.run(['fake-command'])
            self.assertEqual(execute.call_args.kwargs['cwd'],alternate)
    def test_time_formats(self):
        self.assertEqual(b.ass_time(3661.23),'1:01:01.23')
        self.assertEqual(b.srt_time(3661.234),'01:01:01,234')
    def test_source_hash_includes_narration(self):
        self.assertNotEqual(b.digest_scene({'speech':'甲'}),b.digest_scene({'speech':'乙'}))
    def test_audio_not_truncated(self):
        for duration in [1.01,26.56,60.123]:
            frames=math.ceil((duration+b.LEAD+.45)*b.FPS)
            self.assertGreaterEqual(frames/b.FPS-b.LEAD-duration,.449)
            self.assertEqual(round(frames/b.FPS*b.RATE),frames*1000)
    def test_chapter_order_rejects_split_chapters(self):
        d={'chapters':[{'id':'01'},{'id':'02'}],'scenes':[
            {'id':'001','chapter':'01','speech':'甲'},
            {'id':'002','chapter':'02','speech':'乙'},
            {'id':'003','chapter':'01','speech':'丙'}]}
        with patch.object(b,'load_json',return_value=d):
            with self.assertRaisesRegex(RuntimeError,'Chapter order'):b.scenes()
    def test_contiguous_chapters_are_accepted(self):
        d={'chapters':[{'id':'01'},{'id':'02'}],'scenes':[
            {'id':'001','chapter':'01','speech':'甲'},
            {'id':'002','chapter':'01','speech':'乙'},
            {'id':'003','chapter':'02','speech':'丙'}]}
        with patch.object(b,'load_json',return_value=d):self.assertEqual(len(b.scenes()['scenes']),3)
    def test_sample_wav(self):
        path=HERE/'audio'/'000.wav'
        if not path.exists(): self.skipTest('Run small TTS sample first')
        info=b.inspect_wav(path)
        self.assertGreater(info['duration'],1)
        self.assertGreater(info['peak_dbfs'],-30)
    def test_caption_events_are_ordered(self):
        if not (HERE/'audio'/'000.wav').exists():self.skipTest('Sample missing')
        info=b.inspect_wav(HERE/'audio'/'000.wav')
        scene={'id':'000','speech':'一部安卓手机，也可以搭建自己的测试机器人。这期我们不跳步骤，从安装环境开始，一直讲到账号登录、模型连接和开机恢复。每一步都先确认在哪个窗口操作，再看真实的成功信号。画面是教学示意，不是实机成功录像。'}
        events=b.caption_events(scene,{'voice_duration':info['duration']})
        self.assertEqual(events[0]['start'],b.LEAD)
        for e in events:self.assertGreater(e['end'],e['start'])
        for a,c in zip(events,events[1:]):self.assertAlmostEqual(a['end'],c['start'])
        self.assertAlmostEqual(events[-1]['end'],info['duration']+b.LEAD)

if __name__=='__main__':unittest.main(verbosity=2)
