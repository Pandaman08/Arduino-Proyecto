"""Comparaciones descriptivas y pruebas estadísticas con límites explícitos."""

from typing import Any, Iterable, Optional

import numpy as np
from scipy import stats


def _values(items: Iterable[dict[str, Any]], metric: str) -> np.ndarray:
    return np.asarray([float(item[metric]) for item in items if item.get(metric) is not None], dtype=float)


def _summary(values: np.ndarray) -> dict[str, Any]:
    return {"n": int(len(values)), "mean": float(np.mean(values)) if len(values) else None,
            "median": float(np.median(values)) if len(values) else None,
            "std": float(np.std(values, ddof=1)) if len(values) > 1 else None}


def _percent_change(before: Optional[float], after: Optional[float]) -> Optional[float]:
    return None if before is None or after is None or before == 0 else (after - before) / abs(before) * 100.0


def compare_experiments(summaries: Iterable[dict[str, Any]], metric: str, paired: bool = False) -> dict[str, Any]:
    """Compara indicadores; en diseño pareado empareja exclusivamente por ``pair_id``."""
    items = list(summaries)
    before = [item for item in items if item.get("phase") == "antes"]
    after = [item for item in items if item.get("phase") == "despues"]
    if paired:
        pairs: dict[str, dict[str, Any]] = {}
        for item in before:
            if item.get("pair_id") and item.get(metric) is not None:
                pairs.setdefault(item["pair_id"], {})["before"] = item[metric]
        for item in after:
            if item.get("pair_id") and item.get(metric) is not None:
                pairs.setdefault(item["pair_id"], {})["after"] = item[metric]
        valid = [(float(pair["before"]), float(pair["after"])) for pair in pairs.values() if "before" in pair and "after" in pair]
        x, y = np.asarray([item[0] for item in valid]), np.asarray([item[1] for item in valid])
    else:
        x, y = _values(before, metric), _values(after, metric)
    result = {"metric": metric, "design": "paired" if paired else "independent", "before": _summary(x), "after": _summary(y)}
    if len(x) and len(y):
        difference = float(np.mean(y) - np.mean(x))
        result.update(absolute_difference=abs(difference), difference=difference,
                      percent_change=_percent_change(float(np.mean(x)), float(np.mean(y))),
                      direction="después mayor" if difference > 0 else "después menor" if difference < 0 else "sin diferencia")
    else:
        result.update(absolute_difference=None, difference=None, percent_change=None, direction="No disponible")
    return result


def _ci95(values: np.ndarray) -> Optional[tuple[float, float]]:
    if len(values) < 2:
        return None
    if np.std(values, ddof=1) == 0:
        value = float(values[0])
        return value, value
    result = stats.t.interval(0.95, len(values) - 1, loc=float(np.mean(values)), scale=stats.sem(values))
    return float(result[0]), float(result[1])


def _test_dict(result, name: str) -> dict[str, Any]:
    return {"test": name, "statistic": float(result.statistic), "p_value": float(result.pvalue)}


def statistical_tests(before: Iterable[float], after: Iterable[float], paired: bool) -> dict[str, Any]:
    """Reporta pruebas apropiadas y limitaciones; no convierte p-valores en conclusiones automáticas."""
    x, y = np.asarray(list(before), dtype=float), np.asarray(list(after), dtype=float)
    result: dict[str, Any] = {"n_before": len(x), "n_after": len(y), "paired": paired, "shapiro": None, "test": None, "statistic": None, "p_value": None, "ci95": None, "limitation": None}
    if paired:
        n = min(len(x), len(y))
        if n < 2:
            result["limitation"] = "Se requieren al menos dos pares válidos."
            return result
        differences = y[:n] - x[:n]
        if n >= 3 and len(np.unique(differences)) > 1:
            normality = stats.shapiro(differences)
            result["shapiro"] = {"statistic": float(normality.statistic), "p_value": float(normality.pvalue), "n": n}
        result["ci95"] = _ci95(differences)
        if n >= 3:
            result.update(_test_dict(stats.ttest_rel(y[:n], x[:n]), "t pareada"))
            result["test"] = "t pareada"
        else:
            result["limitation"] = "Muestra pareada pequeña: se presenta descripción sin forzar inferencia."
        nonzero = differences[differences != 0]
        if len(nonzero) >= 2:
            result["wilcoxon"] = _test_dict(stats.wilcoxon(nonzero, alternative="two-sided", method="auto"), "Wilcoxon")
        return result
    if len(x) < 2 or len(y) < 2:
        result["limitation"] = "Se requieren al menos dos observaciones por grupo."
        return result
    result["welch"] = _test_dict(stats.ttest_ind(y, x, equal_var=False), "t Welch")
    result["mann_whitney"] = _test_dict(stats.mannwhitneyu(y, x, alternative="two-sided"), "Mann-Whitney")
    result.update(result["welch"])
    return result
