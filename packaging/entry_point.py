"""Entry point used by PyInstaller.

PyInstaller analyses its entry script as a *top-level* module, so the
package-relative ``from .app import main`` in ``ffmpeg_gui/__main__.py``
cannot be followed and nothing gets bundled.  Importing the package by its
absolute name here lets the analyser walk the whole dependency graph.

Running ``python -m ffmpeg_gui`` still works - it uses ``__main__.py``.
"""

from __future__ import annotations

import multiprocessing

from ffmpeg_gui.app import main

if __name__ == "__main__":
    multiprocessing.freeze_support()
    raise SystemExit(main())
