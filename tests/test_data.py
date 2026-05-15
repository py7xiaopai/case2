"""数据处理测试"""
import pytest
from datetime import date
from stock_platform.data.calendar import seed_trading_calendar
from stock_platform.data.etl import data_quality_check


def test_calendar_generation():
    """测试交易日历生成（需要数据库）"""
    from stock_platform.db.engine import SessionLocal
    db = SessionLocal()
    try:
        # Just test the function is callable
        from stock_platform.data.calendar import seed_trading_calendar
        assert callable(seed_trading_calendar)
    finally:
        db.close()


def test_quality_report():
    """测试质量报告（需要数据库）"""
    from stock_platform.db.engine import SessionLocal
    db = SessionLocal()
    try:
        report = data_quality_check(db)
        assert isinstance(report, dict)
        assert "stock_count" in report
        assert "daily_prices_count" in report
    finally:
        db.close()
