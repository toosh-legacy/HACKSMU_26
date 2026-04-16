import os
import tempfile
import warnings


def configure_runtime() -> None:
    """Set cache directories needed by librosa/numba in this environment."""
    tmp = tempfile.gettempdir()
    os.environ.setdefault("NUMBA_CACHE_DIR", os.path.join(tmp, "rumbleos_numba_cache"))
    os.environ.setdefault("LIBROSA_CACHE_DIR", os.path.join(tmp, "rumbleos_librosa_cache"))
    os.environ.setdefault("MPLCONFIGDIR", os.path.join(tmp, "rumbleos_matplotlib"))

    # Silence TensorFlow info/warning logs (pulled in transitively by UMAP).
    # 0=all, 1=info, 2=warning, 3=error
    os.environ.setdefault("TF_CPP_MIN_LOG_LEVEL", "3")
    os.environ.setdefault("TF_ENABLE_ONEDNN_OPTS", "0")

    # Silence UMAP's n_jobs override notice (expected when random_state is set)
    warnings.filterwarnings(
        "ignore",
        message="n_jobs value.*overridden",
        category=UserWarning,
        module="umap",
    )
