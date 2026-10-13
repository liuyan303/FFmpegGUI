"""FFmpeg GUI - a simple, bilingual graphical front-end for FFmpeg.

The application wraps the most common FFmpeg operations (format
conversion, re-encoding, trimming, GIF creation, audio extraction, ...)
in a drag-and-drop desktop GUI.

The application deliberately does NOT bundle FFmpeg. It uses the FFmpeg
executable installed on the user's machine, detected automatically or
configured in the settings dialog (see :mod:`ffmpeg_gui.ffmpeg`).
"""

__app_name__ = "FFmpeg GUI"
__version__ = "1.0.0"
__author__ = "FFmpegGUI Contributors"
__license__ = "MIT"

# NOTE: Replace this placeholder with your real repository URL before
# publishing. It is used by the About dialog, the Help menu and the docs.
__url__ = "https://github.com/liuyan303/FFmpegGUI"

__all__ = [
    "__app_name__",
    "__version__",
    "__author__",
    "__license__",
    "__url__",
]
