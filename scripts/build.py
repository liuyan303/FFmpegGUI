"""Build the standalone executable and assemble the release package.

Usage::

    python scripts/build.py              # tests + build + selftest + zip
    python scripts/build.py --no-tests   # skip pytest
    python scripts/build.py --no-zip     # only produce dist/ and release/<folder>

Produces:
    dist/FFmpegGUI.exe                       single-file executable
    release/FFmpegGUI-<ver>-win64/           portable folder
    release/FFmpegGUI-<ver>-win64.zip        ready-to-upload release archive
"""

from __future__ import annotations

import argparse
import json
import os
import shutil
import subprocess
import sys
import tempfile
import zipfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
DIST = ROOT / "dist"
BUILD = ROOT / "build"
RELEASE = ROOT / "release"


def run(command: list[str], **kwargs) -> None:
    print(">>", " ".join(str(part) for part in command), flush=True)
    subprocess.run(command, check=True, cwd=ROOT, **kwargs)


def smoke_test(executable: Path) -> dict:
    """Run ``--selftest`` on the frozen exe and return the JSON report.

    The exe is copied to the system temp folder first.  PyInstaller's
    onefile bootloader fails to start from some directories - notably paths
    containing characters outside the active code page, or folders that a
    security policy filters.  Staging in ``%TEMP%`` keeps the build working
    no matter where the source tree lives.
    """
    staging = Path(tempfile.mkdtemp(prefix="ffmpeg-gui-build-"))
    try:
        staged_exe = staging / executable.name
        shutil.copy2(executable, staged_exe)
        report_path = staging / "selftest.json"
        environment = dict(os.environ, QT_QPA_PLATFORM="offscreen")
        try:
            subprocess.run(
                [str(staged_exe), "--selftest", str(report_path)],
                check=True,
                cwd=staging,
                env=environment,
                timeout=180,
            )
        except subprocess.TimeoutExpired as exc:
            raise SystemExit(
                "the frozen executable did not finish its self test within "
                "180s.  If it starts fine from an ASCII-only folder, the "
                "failure is caused by the location it was launched from."
            ) from exc
        if not report_path.is_file():
            raise SystemExit("the frozen executable wrote no self-test report")
        return json.loads(report_path.read_text(encoding="utf-8"))
    finally:
        shutil.rmtree(staging, ignore_errors=True)


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--no-tests", action="store_true", help="skip pytest")
    parser.add_argument("--no-zip", action="store_true", help="skip the release zip")
    args = parser.parse_args()

    if not args.no_tests:
        run([sys.executable, "-m", "pytest", "tests", "-q"])

    shutil.rmtree(BUILD, ignore_errors=True)
    shutil.rmtree(DIST, ignore_errors=True)
    run(
        [
            sys.executable, "-m", "PyInstaller",
            "--noconfirm", "packaging/ffmpeg_gui.spec",
        ]
    )

    exe = DIST / "FFmpegGUI.exe"
    if not exe.is_file():
        raise SystemExit("build failed: dist/FFmpegGUI.exe was not produced")

    # ---- smoke test the frozen application ---------------------------
    report = smoke_test(exe)
    if not report.get("ok"):
        raise SystemExit(f"frozen selftest failed: {report}")
    print("frozen selftest:", json.dumps(report, ensure_ascii=False))

    # ---- assemble the release folder ---------------------------------
    version = report["version"]
    folder = RELEASE / f"FFmpegGUI-{version}-win64"
    shutil.rmtree(folder, ignore_errors=True)
    folder.mkdir(parents=True)
    shutil.copy2(exe, folder / "FFmpegGUI.exe")
    shutil.copy2(ROOT / "LICENSE", folder / "LICENSE")
    shutil.copy2(ROOT / "README.md", folder / "README.md")
    shutil.copytree(ROOT / "locales", folder / "locales")
    if (ROOT / "ffmpeg").is_dir():  # optional portable ffmpeg\bin folder
        shutil.copytree(ROOT / "ffmpeg", folder / "ffmpeg")

    if not args.no_zip:
        archive = RELEASE / f"FFmpegGUI-{version}-win64.zip"
        if archive.exists():
            archive.unlink()
        with zipfile.ZipFile(archive, "w", zipfile.ZIP_DEFLATED) as zip_file:
            for path in sorted(folder.rglob("*")):
                if path.is_file():
                    zip_file.write(path, path.relative_to(folder.parent))
        size_mb = archive.stat().st_size / (1024 * 1024)
        print(f"release archive: {archive} ({size_mb:.1f} MB)")

    print("done.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
