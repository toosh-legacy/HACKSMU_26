import os
import tempfile


def configure_runtime() -> None:
    """Set cache directories needed by librosa/numba in this environment."""
    tmp = tempfile.gettempdir()
    os.environ.setdefault("NUMBA_CACHE_DIR", os.path.join(tmp, "rumbleos_numba_cache"))
    os.environ.setdefault("LIBROSA_CACHE_DIR", os.path.join(tmp, "rumbleos_librosa_cache"))
    os.environ.setdefault("MPLCONFIGDIR", os.path.join(tmp, "rumbleos_matplotlib"))
