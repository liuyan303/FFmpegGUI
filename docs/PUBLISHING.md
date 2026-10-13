# 维护与发布指南

本文件说明版本迭代与发布流程。面向仓库维护者。

## 一、仓库地址

本项目的仓库地址为 `https://github.com/liuyan303/FFmpegGUI`，
在以下位置被引用：

| 文件 | 位置 |
| --- | --- |
| `src/ffmpeg_gui/__init__.py` | `__url__` 常量（关于对话框、帮助菜单使用） |
| `pyproject.toml` | `[project.urls]` 三处 |
| `README.md` / `README.zh-CN.md` | 克隆地址与 Releases 链接 |
| `CHANGELOG.md` | 版本对比链接 |

若项目被 fork 或迁移到新地址，需同步替换上表中的 `liuyan303`。

作者信息位置：

- `LICENSE` —— 版权行
- `packaging/version_info.txt` —— `CompanyName`、`LegalCopyright`

## 二、修改版本号

发新版本时同步修改两处：

- `src/ffmpeg_gui/__init__.py` → `__version__`
- `packaging/version_info.txt` → `filevers / prodvers / FileVersion /
  ProductVersion`

## 三、提交与推送

```bat
git add .
git commit -m "feat: ..."
git push origin main
```

仓库使用 SSH 部署密钥（本机配置见 `~/.ssh/config`，通过
`ssh.github.com:443` 连接，适用于 22 端口被封锁的网络）。
若改用 HTTPS 远程地址，推送时需提供 Personal Access Token。

然后在 GitHub 网页上：仓库 → Settings → Actions → General，
把 Workflow permissions 设为 **Read and write permissions**（发布 Release
需要）。

## 四、发布一个版本

```bat
git tag v1.0.0
git push origin v1.0.0
```

推送 `v*` 标签后，GitHub Actions 会自动：

1. 在 Linux 上运行单元测试；
2. 在 windows-latest 上打包 `FFmpegGUI.exe`；
3. 对打包结果做无界面冒烟测试（`--selftest`）；
4. 把 `FFmpegGUI.exe` 和 `FFmpegGUI-1.0.0-win64.zip` 附加到 GitHub Release。

也可以在 Actions 页面手动触发（workflow_dispatch）只构建不发布。

## 五、本地打包（不上 CI 时）

```bat
python -m venv .venv
.venv\Scripts\activate
pip install -r requirements-dev.txt
python scripts/build.py
```

产物：

- `dist/FFmpegGUI.exe` —— 单文件可执行程序
- `release/FFmpegGUI-1.0.0-win64/` —— 便携文件夹
- `release/FFmpegGUI-1.0.0-win64.zip` —— 上传到 Release 的压缩包

## 六、截图（README 用）

```bat
rem 指定 FFmpeg 位置，仅用于生成演示视频素材
set FFMPEG_PATH=C:\ffmpeg\bin\ffmpeg.exe
python scripts/screenshot.py en_US docs/screenshots/main_en.png
python scripts/screenshot.py zh_CN docs/screenshots/main_zh.png
```
