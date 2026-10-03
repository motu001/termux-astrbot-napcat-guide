# 竖屏详细视频的原创制作源文件

> **历史细节参考，非当前发布版。** 当前方案已改为[人做准备、Agent接手的短视频](../handoff_short_20261003/README.md)，不再要求人跟着长课逐条操作。

本目录用于复现教学视频，不是手机部署时需要安装的软件。

- 内容：18章、109个教学段落；完整分镜与口播见[口播与分镜](口播与分镜.md)，唯一内容源为`scenes.json`。
- 成片对应时长：56分30秒；[章节时间表](章节时间表.md)；[公开字幕](完整教程字幕.srt)。
- 画面：1080×1920、24fps、代码绘制的六类教学卡；三阶段强调，预留竖屏按钮区和字幕区。始终标注教学示意，不伪造实机录像。
- 配音：小米MiMo TTS「冰糖」。本目录不含密钥，也不分发已生成语音或视频。你需要自己合法配置TTS账户；请求可能计费。
- 手机跟做：[完整安装教程](../../docs/从零安装与连接.md)、[检查清单](../../docs/部署检查清单.md)、[故障和维护](../../docs/安全与故障排查.md)、[官方来源及下载限制](../../docs/上游参考.md)。

## 事实边界

2026-10-03官方来源核对发现：安装器旧QQ链接404，官网新ARM64候选包在核对网络403；不能把候选包说成已下载或兼容性已通过。完整新机路线仍待实测。视频在准备和安装章节保留该限制及停止条件。

2026-10-02只验证原机NapCat/QQ服务重启后免点击登录，未验证新机从零安装、Android整机无人值守或AI来源。本教程的Boot范例只请求启动服务，不自动具备原机的登录查询和12轮重试组件。

详细技术检查和未覆盖项见[制作与验证记录](制作与验证记录.md)。

## 制作环境

本版本在Windows制作，使用Python、Pillow、numpy、FFmpeg（含libass），以及微软雅黑/Consolas字体。手机部署本身不需要Windows或这些视频依赖。

先配置你自己的MiMo TTS调用脚本。默认位置是用户目录下`.codex/skills/mimo-tts/scripts/tts.py`，也可用`MIMO_TTS_SCRIPT`指定。调用约定：`text --voice --style --format --out`。API Key应由该调用脚本从环境或私有配置读取，不能放进Git、分镜或命令参数。

```powershell
python -m pip install -r requirements.txt
python tests_pipeline.py
python tests_render.py
python review_content.py
python render_cards.py --scenes scenes.json --out-dir layout_preflight
```

内容/来源和画面预检通过后，按阶段制作：

```powershell
python build_video.py sample
python build_video.py audio --workers 2
python build_video.py graphics
python build_video.py render --workers 2
python build_video.py assemble
python build_video.py verify
python make_publishing_cover.py
```

仅`sample`和缓存缺失/变更的`audio`阶段调用TTS。缓存包含模型、声线、风格、文本哈希；改画面不必重做语音。最大2并发，失败即停，不无限重试。

输出在仓库根目录`06_成片/完整教程_20261003/`，包括完整片、分章片、独立M4A、SRT、章节时间与技术验收。生成媒体与运行缓存已忽略，切勿强制批量添加到Git。

字幕按真实配音长度与静音停顿进行短语级估算，不是ASR逐字强对齐。发布前需要本人听审英文名、数字读法和字幕节奏；不自动上传抖音。

## 编辑与校验

只编辑`scenes.json`，运行`python export_transcript.py`同步可读口播稿。字段过密时画面渲染报错，不截断命令，也不把字缩到不可读。

主目录运行`python tools/verify_public_docs.py`可检查UTF-8、代码围栏、链接和部分敏感信息模式；模式检查不能替代人工逐文件审核。
