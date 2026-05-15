#!/usr/bin/env python3
"""初始化交易日历"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent / "src"))

from stock_platform.db.engine import SessionLocal
from stock_platform.data.calendar import seed_trading_calendar


def main():
    db = SessionLocal()
    try:
        count = seed_trading_calendar(db, start_year=2000, end_year=2030)
        print(f"✅ 交易日历初始化完成: {count} 条")
    except Exception as e:
        print(f"❌ 失败: {e}")
        sys.exit(1)
    finally:
        db.close()


if __name__ == "__main__":
    main()
