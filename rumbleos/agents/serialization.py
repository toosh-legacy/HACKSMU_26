import numpy as np


def tabular_result(result: dict) -> dict:
    """Drop array-like fields so CSV outputs stay one row per call."""
    scalar_result = {}
    for key, value in result.items():
        if isinstance(value, np.ndarray):
            continue
        if isinstance(value, dict):
            for sub_key, sub_value in value.items():
                if isinstance(sub_value, np.ndarray):
                    continue
                if isinstance(sub_value, (list, tuple, dict, set)):
                    continue
                if isinstance(sub_value, np.generic):
                    scalar_result[f"{key}_{sub_key}"] = sub_value.item()
                    continue
                scalar_result[f"{key}_{sub_key}"] = sub_value
            continue
        if isinstance(value, (list, tuple, set)):
            continue
        if isinstance(value, np.generic):
            scalar_result[key] = value.item()
            continue
        scalar_result[key] = value
    return scalar_result
