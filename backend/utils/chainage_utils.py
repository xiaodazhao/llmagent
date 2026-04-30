import math


def format_chainage_dk(value, unknown="未知里程"):
    """
    Format TBM chainage as DKxxxx+xxx.

    Supports both meter-style values such as 1014616 and kilometer-decimal
    values such as 1014.616.
    """
    try:
        if value is None:
            return unknown
        x = float(value)
    except (TypeError, ValueError):
        return unknown

    if not math.isfinite(x):
        return unknown

    if abs(x) >= 100000:
        km = int(math.floor(x / 1000))
        meter = int(round(x - km * 1000))
    else:
        km = int(math.floor(x))
        meter = int(round((x - km) * 1000))

    if meter >= 1000:
        km += meter // 1000
        meter = meter % 1000

    return f"DK{km}+{meter:03d}"


def format_chainage_range_dk(start, end, separator="~"):
    return f"{format_chainage_dk(start)}{separator}{format_chainage_dk(end)}"
