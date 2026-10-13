# FFmpeg GUI

[English](README.md) | **简体中文**
一个简洁的**中英双语** FFmpeg 图形界面（Windows）。把视频拖进来、选个预设、
点「开始转换」即可，无需命令行。

!\[界面截图](docs/screenshots/main\_zh.png)

## 功能特性

* **拖放或选择文件**作为输入，自动建议输出路径。
* **一键预设** —— MP4（H.264 / H.265）、MKV、WebM（VP9 + Opus）、MOV、AVI、
GIF、MP3 / M4A / WAV / FLAC 音频，以及**复制流**（仅重封装，不重新编码）。
* **高级选项** —— 视频/音频编码器、CRF 质量滑杆、编码预设、分辨率、帧率、
音频码率、裁剪（开始/结束时间）、GIF 帧率与宽度、附加 FFmpeg 参数。
* **命令实时预览** —— 随时查看即将执行的完整命令。
* **进度显示速度 / 帧率 / 已用时长**，支持取消，内置完整日志面板。
* **FFmpeg 自动检测与安装** —— 启动时自动检测本机 FFmpeg；若未安装会询问一次，
可一键下载静态版本到 `%LOCALAPPDATA%\\FFmpegGUI\\ffmpeg`（仅当前用户，
无需管理员权限，不写系统目录）。
* **媒体信息**：通过 `ffprobe` 读取时长、分辨率、编码、码率等。
* **完整国际化** —— 内置简体中文与英文，可在「设置 → 语言」中即时切换。
语言文件是 [`locales/`](locales) 下的纯 JSON，新增一门语言只需几分钟。
* **主题** —— 浅色 / 深色 / 跟随系统。
* **便携模式** —— 在 exe 旁放一个 `config.ini` 即可把配置保存在文件夹内；
在 exe 旁放 `locales/` 文件夹即可免重新打包新增或修改翻译。

## 下载

到 [**Releases**](https://github.com/liuyan303/FFmpegGUI/releases) 页面下载：

|文件|说明|
|-|-|
|`FFmpegGUI-<版本>-win64.zip`|便携版文件夹：exe + 语言文件 + 文档|
|`FFmpegGUI.exe`|单文件可执行程序|

本软件**不捆绑 FFmpeg**（FFmpeg 是独立项目，有其自己的许可证）。以下几种
方式任选其一：

1. 什么都不做 —— 首次启动时会询问并自动下载 FFmpeg 到
`%LOCALAPPDATA%\\FFmpegGUI\\ffmpeg`（无需管理员权限）。
2. 用包管理器安装：`winget install ffmpeg`、`choco install ffmpeg`
或 `scoop install ffmpeg`。
3. 从 [ffmpeg.org/download.html](https://ffmpeg.org/download.html) 下载并
把 `ffmpeg.exe` 加入 `PATH`。

程序会自动查找 FFmpeg（也可在「设置 → FFmpeg 位置」中手动指定）。

## 使用方法

1. 把媒体文件**拖放**到窗口上（或点击拖放区选择文件）。
2. 选择一个**预设**（默认：MP4 · H.264 + AAC）。
3. 如需微调，展开**高级选项** —— 命令预览会实时更新。
4. 确认**输出文件**路径（已自动生成）。
5. 点击**开始转换**（快捷键 `Ctrl+Enter`）。

小技巧：

* *复制流（仅重封装）* 只更换容器格式 —— 瞬间完成且无损。
* *自定义*预设 + 编码器选「复制」，可组合使用（例如只重新编码音频、
视频直接复制）。
* 硬件编码器（NVIDIA NVENC / Intel QSV / AMD AMF）在显卡和驱动支持时
可直接选用。

## 环境要求

* 预编译版本：Windows 10 / 11（64 位）。
* 从源码运行：Python 3.10+ 与 PySide6。
* FFmpeg：较新的任意版本（程序会自动检测或下载）。

## 从源码运行

```bat
git clone https://github.com/liuyan303/FFmpegGUI.git
cd FFmpegGUI
python -m venv .venv
.venv\\Scripts\\activate
pip install -r requirements-dev.txt
pip install -e .
ffmpeg-gui
```

运行测试（命令构建与 i18n 测试不需要 Qt 或 FFmpeg；运行器测试用当前
解释器作为子进程）：

```bat
python -m pytest tests -q
```

打包独立 exe 与发行 zip：

```bat
python scripts/build.py
```

构建脚本会依次运行测试、PyInstaller 打包（spec 位于
`packaging/ffmpeg\_gui.spec`）、对打包后的 exe 做无界面冒烟测试，并在
`release/FFmpegGUI-<版本>-win64.zip` 生成发行包。

## 新增语言

1. 复制 `locales/en\_US.json` 为 `locales/<语言代码>.json`
（如 `locales/ja\_JP.json`）。
2. 修改 `\_meta`（`code`、`name` —— 用该语言书写的名称、`name\_en`）。
3. 翻译各条目的值 —— 保持键名与 `{占位符}` 不变。
4. 运行 `python -m pytest tests -q` —— 测试会校验所有语言文件的键是否一致。
5. 提交 Pull Request。

便携版无需重新打包：把 JSON 放进 `FFmpegGUI.exe` 旁的 `locales/` 文件夹，
重启后即可在语言菜单中看到。详见
[CONTRIBUTING.md](CONTRIBUTING.md#adding-a-new-language)。

## 项目结构

```
src/ffmpeg\_gui/          应用包（纯逻辑模块 + Qt 界面）
  ffmpeg.py              查找 ffmpeg、探测媒体、构建命令行
  installer.py           下载 / 解压 FFmpeg 静态构建
  i18n.py                JSON 翻译加载器（不依赖 Qt）
  runner.py              subprocess 任务运行器，实时解析进度
  ui/                    主窗口与对话框
locales/                 每种语言一个 JSON（en\_US、zh\_CN……）
tests/                   pytest 测试（命令构建与 i18n 无需 Qt）
packaging/               PyInstaller spec + Windows 版本资源
scripts/                 图标生成、截图、打包脚本
```

## 常见问题

**Windows 提示「已保护你的电脑」（SmartScreen）。** 构建产物未做代码签名。
点击「更多信息 → 仍要运行」，或自行从源码构建。

**为什么 exe 有约 50 MB？** 里面打包了 Qt（PySide6）运行时；换来的是无需
安装 Python、更现代的界面体验。

**配置和日志保存在哪里？** 配置：注册表 `HKCU\\Software\\FFmpegGUI`
（便携模式下为 exe 旁的 `config.ini`）。日志：
`%LOCALAPPDATA%\\FFmpegGUI\\logs` —— 提 Issue 时请附上该文件。

**双击 exe 没有反应 / 打不开。** 单文件版每次启动都会把自己解压到
`%TEMP%`，少数安全软件以及受策略管控、网络或重定向的目录会拦截这一步。
把 `FFmpegGUI.exe` 放到普通的本地目录（桌面、`C:\\Program Files\\FFmpegGUI`、
U 盘等）再试。若仍不行，可改用源码运行（`pip install -e .` 后执行
`ffmpeg-gui`），完全没有自解压步骤；启动失败的详细原因也会记在
`%LOCALAPPDATA%\\FFmpegGUI\\logs` 里的日志中。

**软件包含 FFmpeg 吗？** 不包含。FFmpeg 是独立项目（LGPL/GPL 许可），
本软件只是调用你提供的 FFmpeg 可执行文件。

## 许可证

[MIT](LICENSE)。FFmpeg 是 Fabrice Bellard 的商标；本项目与 FFmpeg 项目
无隶属关系。

