import math
from datetime import date, datetime
from decimal import Decimal
from numbers import Real

import pandas as pd


CHART_TYPES = {"bar", "line", "scatter"}


def _is_finite_number(value: object) -> bool:
    if isinstance(value, bool) or not isinstance(value, (Real, Decimal)):
        return False
    try:
        return math.isfinite(float(value))
    except (OverflowError, ValueError):
        return False


def validate_chart_spec(
    chart: object,
    evidence: dict,
) -> tuple[dict | None, str | None]:
    if chart is None:
        return None, None
    if not isinstance(chart, dict) or set(chart) != {"type", "x", "y", "title"}:
        return None, "The suggested chart specification was incomplete or invalid."
    if (
        not isinstance(chart["type"], str)
        or chart["type"] not in CHART_TYPES
        or not isinstance(chart["x"], str)
        or not isinstance(chart["y"], str)
        or not isinstance(chart["title"], str)
        or not chart["title"].strip()
        or len(chart["title"]) > 120
    ):
        return None, "The suggested chart specification was incomplete or invalid."

    columns = evidence.get("columns")
    rows = evidence.get("rows")
    if (
        not isinstance(columns, list)
        or not isinstance(rows, list)
        or len(rows) < 2
        or columns.count(chart["x"]) != 1
        or columns.count(chart["y"]) != 1
        or chart["x"] == chart["y"]
    ):
        return None, "The suggested chart did not match the query results."

    x_index = columns.index(chart["x"])
    y_index = columns.index(chart["y"])
    for row in rows:
        if not isinstance(row, (list, tuple)) or len(row) != len(columns):
            return None, "The suggested chart did not match the query results."
        x_value = row[x_index]
        y_value = row[y_index]
        if (
            x_value is None
            or isinstance(x_value, bool)
            or not isinstance(x_value, (str, Real, Decimal, date, datetime))
            or (
                isinstance(x_value, (Real, Decimal))
                and not _is_finite_number(x_value)
            )
            or not _is_finite_number(y_value)
        ):
            return None, "The suggested chart requires usable category and numeric values."

    return {
        "type": chart["type"],
        "x": chart["x"],
        "y": chart["y"],
        "title": chart["title"].strip(),
    }, None


def chart_dataframe(chart: dict, evidence: dict) -> pd.DataFrame:
    """Build chart data from only the validated result columns."""
    x_index = evidence["columns"].index(chart["x"])
    y_index = evidence["columns"].index(chart["y"])
    return pd.DataFrame(
        {
            chart["x"]: [row[x_index] for row in evidence["rows"]],
            chart["y"]: [row[y_index] for row in evidence["rows"]],
        }
    )
