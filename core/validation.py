"""Human-vs-AI agreement statistics. Computed only from real, stored human ratings."""
from __future__ import annotations

import numpy as np
import pandas as pd

from . import db
from .rubric import DIMENSIONS

MIN_FOR_CORRELATION = 5


def paired_frame(eval_mode: str | None = None) -> pd.DataFrame:
    return pd.DataFrame(db.paired_rows(eval_mode))


def _spearman(a: pd.Series, b: pd.Series) -> float | None:
    r = np.corrcoef(a.rank(), b.rank())[0, 1]
    return None if np.isnan(r) else float(r)


def metrics(a: pd.Series, h: pd.Series) -> dict:
    d = (a - h).dropna()
    n = len(d)
    out = {"n": n, "mae": None, "rmse": None, "bias": None, "within_1": None, "pearson": None, "spearman": None}
    if n == 0:
        return out
    out.update(mae=float(d.abs().mean()), rmse=float(np.sqrt((d ** 2).mean())), bias=float(d.mean()))
    if n >= MIN_FOR_CORRELATION and a.nunique() > 1 and h.nunique() > 1:
        r = np.corrcoef(a, h)[0, 1]
        out["pearson"] = None if np.isnan(r) else float(r)
        out["spearman"] = _spearman(a, h)
    return out


def summarize(df: pd.DataFrame) -> dict:
    """Overall (0-100) plus per-dimension (0-10) metrics. bias = AI minus human (positive: AI is more generous)."""
    if df.empty:
        return {"overall": metrics(pd.Series(dtype=float), pd.Series(dtype=float)), "dimensions": {}}
    res = {"overall": metrics(df["a_overall"], df["h_overall"]), "dimensions": {}}
    for d in DIMENSIONS:
        sub = df[[f"a_{d}", f"h_{d}"]].dropna()
        res["dimensions"][d] = metrics(sub[f"a_{d}"], sub[f"h_{d}"])
    return res
