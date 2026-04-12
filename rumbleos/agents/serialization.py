import numpy as np


def tabular_result(result: dict) -> dict:
    """Drop array-like fields so CSV outputs stay one row per call."""
    scalar_result = {}
    for key, value in result.items():
        if isinstance(value, np.ndarray):
            continue
        if isinstance(value, (list, tuple, dict, set)):
            continue
        if isinstance(value, np.generic):
            scalar_result[key] = value.item()
            continue
        scalar_result[key] = value
    return scalar_result
