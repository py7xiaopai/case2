"""通用工具函数"""

from decimal import Decimal as _DEC


def to_decimal(val) -> _DEC | None:
    """将值安全转为 Decimal，None/'null' 返回 None"""
    if val is None or val == "null":
        return None
    try:
        return _DEC(str(val))
    except Exception:
        return None


def to_float(val) -> float | None:
    """将值安全转为 float，None/'null' 返回 None"""
    if val is None or val == "null":
        return None
    try:
        return float(val)
    except Exception:
        return None
