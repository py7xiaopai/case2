"""交易日历生成脚本"""
from datetime import date, timedelta
from sqlalchemy.orm import Session
from stock_platform.db.models import TradingCalendar


def seed_trading_calendar(session: Session, start_year: int = 2000, end_year: int = 2030) -> int:
    """生成并写入交易日历"""
    count = 0
    current = date(start_year, 1, 1)
    end = date(end_year, 12, 31)

    while current <= end:
        existing = session.query(TradingCalendar).filter_by(trade_date=current).first()
        if existing:
            current += timedelta(days=1)
            continue

        # Simple rule: Mon-Fri are trading days (approximation)
        is_open = 1 if current.weekday() < 5 else 0

        cal = TradingCalendar(
            trade_date=current,
            is_open=is_open,
            market="ALL",
        )
        session.add(cal)
        count += 1
        current += timedelta(days=1)

    session.commit()
    return count
