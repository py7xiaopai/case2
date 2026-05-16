"""数据清洗层

提供 ETL 管线中的标准化清洗能力：
  - 缺失值标记与阈值报告
  - 类型标准化（数值/日期格式统一）
  - 空值处理策略（填充/丢弃/标记）
  - 异常值检测（IQR / Z-Score）
"""
import logging
from datetime import date, datetime
from decimal import Decimal, InvalidOperation
from typing import Any

import pandas as pd
import numpy as np
from sqlalchemy.orm import Session

from stock_platform.db.models import Stock, DailyPrice, TechnicalIndicator

logger = logging.getLogger("stock_platform.cleaning")


# ─── 缺失值分析 ───────────────────────────────────────


def missing_analysis(session: Session) -> dict:
    """分析 stocks 表各字段缺失率"""
    total = session.query(Stock).count()
    if total == 0:
        return {"total": 0, "fields": {}}

    analysis = {"total": total, "fields": {}}

    nullable_fields = [
        ("market", Stock.market),
        ("exchange", Stock.exchange),
        ("industry", Stock.industry),
        ("board", Stock.board),
        ("listing_date", Stock.listing_date),
        ("total_market_cap", Stock.total_market_cap),
        ("circulating_market_cap", Stock.circulating_market_cap),
        ("source_updated_at", Stock.source_updated_at),
    ]

    for name, column in nullable_fields:
        null_count = session.query(column).filter(column.is_(None)).count()
        analysis["fields"][name] = {
            "null_count": null_count,
            "null_rate": round(null_count / total * 100, 2),
        }

    return analysis


# ─── 类型标准化 ───────────────────────────────────────


def standardize_market_cap(value: Any) -> Decimal | None:
    """标准化市值字段：解析字符串/数字为 Decimal(元)"""
    if value is None or value == "-" or value == "":
        return None
    if isinstance(value, Decimal):
        return value
    try:
        return Decimal(str(value).replace(",", ""))
    except (InvalidOperation, ValueError):
        return None


def standardize_date(value: Any) -> date | None:
    """标准化日期字段：支持多种格式"""
    if value is None or value == "-" or value == "":
        return None
    if isinstance(value, date):
        return value
    if isinstance(value, datetime):
        return value.date()
    try:
        return date.fromisoformat(str(value)[:10])
    except (ValueError, TypeError):
        try:
            # 支持 YYYYMMDD
            s = str(value).strip()
            if s.isdigit() and len(s) == 8:
                return date(int(s[:4]), int(s[4:6]), int(s[6:8]))
        except (ValueError, IndexError):
            pass
        return None


def standardize_number(value: Any) -> Decimal | None:
    """标准化数值字段"""
    if value is None or value == "-" or value == "":
        return None
    try:
        return Decimal(str(value).replace(",", "").replace(" ", ""))
    except (InvalidOperation, ValueError):
        return None


# ─── 异常值检测 ───────────────────────────────────────


def detect_outliers_iqr(data: pd.Series, k: float = 1.5) -> pd.Series:
    """基于 IQR 的异常值检测"""
    if data.empty or data.isna().all():
        return pd.Series([False] * len(data), index=data.index)
    Q1 = data.quantile(0.25)
    Q3 = data.quantile(0.75)
    IQR = Q3 - Q1
    if IQR == 0:
        return pd.Series([False] * len(data), index=data.index)
    return (data < Q1 - k * IQR) | (data > Q3 + k * IQR)


def detect_outliers_zscore(data: pd.Series, threshold: float = 3.0) -> pd.Series:
    """基于 Z-Score 的异常值检测"""
    if data.empty or data.isna().all():
        return pd.Series([False] * len(data), index=data.index)
    mean = data.mean()
    std = data.std()
    if std == 0:
        return pd.Series([False] * len(data), index=data.index)
    z = np.abs((data - mean) / std)
    return z > threshold


# ─── 空值策略 ───────────────────────────────────────


def fill_missing_values(df: pd.DataFrame, strategy: str = "ffill") -> pd.DataFrame:
    """填充缺失值

    策略:
      - "ffill": 向前填充（默认，适用于时间序列）
      - "bfill": 向后填充
      - "zero": 填充为 0
      - "mean": 填充为均值
      - "median": 填充为中位数
    """
    df = df.copy()
    numeric_cols = df.select_dtypes(include=[np.number]).columns

    if strategy == "ffill":
        df[numeric_cols] = df[numeric_cols].fillna(method="ffill")
    elif strategy == "bfill":
        df[numeric_cols] = df[numeric_cols].fillna(method="bfill")
    elif strategy == "zero":
        df[numeric_cols] = df[numeric_cols].fillna(0)
    elif strategy == "mean":
        df[numeric_cols] = df[numeric_cols].fillna(df[numeric_cols].mean())
    elif strategy == "median":
        df[numeric_cols] = df[numeric_cols].fillna(df[numeric_cols].median())
    else:
        raise ValueError(f"未知策略: {strategy}")

    return df


# ─── 数据质量标签 ─────────────────────────────────────


def quality_tags(df: pd.DataFrame) -> dict:
    """为 DataFrame 生成数据质量标签"""
    tags = {}
    total = len(df)
    null_counts = df.isna().sum()
    null_cols = null_counts[null_counts > 0]

    if len(null_cols) > 0:
        tags["null_columns"] = null_cols.to_dict()
        tags["null_rate"] = round(null_counts.sum() / (total * len(df.columns)) * 100, 2) if total > 0 else 0
    else:
        tags["null_rate"] = 0

    tags["total_rows"] = total
    tags["total_cols"] = len(df.columns)
    return tags


# ─── 清洗管线入口 ─────────────────────────────────────


def clean_stock_data(stock: Stock, prices_df: pd.DataFrame) -> pd.DataFrame:
    """对单只股票的数据执行完整清洗管线

    步骤:
      1. 缺失值标记 → 2. 类型标准化 → 3. 空值策略 → 4. 异常标记
    """
    if prices_df.empty:
        return prices_df

    df = prices_df.copy()

    # 1. 确保日期列存在且排序
    if "trade_date" in df.columns:
        df["trade_date"] = pd.to_datetime(df["trade_date"])
        df = df.sort_values("trade_date").reset_index(drop=True)

    # 2. 数值列标准化
    for col in ["open_price", "close_price", "high_price", "low_price"]:
        if col in df.columns:
            df[col] = pd.to_numeric(df[col], errors="coerce")

    # 3. 成交量/额
    if "volume" in df.columns:
        df["volume"] = pd.to_numeric(df["volume"], errors="coerce").fillna(0).astype("int64")
    if "amount" in df.columns:
        df["amount"] = pd.to_numeric(df["amount"], errors="coerce")

    # 4. 涨跌幅
    if "pct_change" in df.columns:
        df["pct_change"] = pd.to_numeric(df["pct_change"], errors="coerce")

    return df
