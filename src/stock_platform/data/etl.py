"""数据质量检查模块"""
from sqlalchemy import func
from sqlalchemy.orm import Session

from stock_platform.db.models import DailyPrice, Stock, TechnicalIndicator, TradingCalendar


def data_quality_check(session: Session) -> dict:
    """执行完整的数据质量检查，返回质量报告"""
    report = {
        "stock_count": 0,
        "daily_prices_count": 0,
        "indicator_count": 0,
        "calendar_count": 0,
        "stocks_with_missing_dates": [],
        "stocks_with_null_prices": [],
        "stocks_with_outliers": [],
        "date_gaps": [],
        "issues": [],
    }

    report["stock_count"] = session.query(Stock).count()
    report["daily_prices_count"] = session.query(DailyPrice).count()
    report["indicator_count"] = session.query(TechnicalIndicator).count()
    report["calendar_count"] = session.query(TradingCalendar).count()

    # 1. 空值检查
    null_check = (
        session.query(DailyPrice.stock_id, func.count(DailyPrice.id).label("null_count"))
        .filter(
            (DailyPrice.open_price.is_(None))
            | (DailyPrice.close_price.is_(None))
            | (DailyPrice.high_price.is_(None))
            | (DailyPrice.low_price.is_(None))
        )
        .group_by(DailyPrice.stock_id)
        .having(func.count(DailyPrice.id) > 0)
        .limit(10)
        .all()
    )
    for row in null_check:
        stock = session.query(Stock).get(row[0])
        if stock:
            report["stocks_with_null_prices"].append({
                "code": stock.code, "name": stock.name, "null_count": row[1],
            })

    # 2. 异常值检查 (涨跌幅超过 ±10%)
    outliers = (
        session.query(DailyPrice)
        .filter(
            DailyPrice.pct_change.isnot(None),
            func.abs(DailyPrice.pct_change) > 10,
        )
        .limit(20)
        .all()
    )
    for dp in outliers:
        stock = session.get(Stock, dp.stock_id)
        if stock:
            report["stocks_with_outliers"].append({
                "code": stock.code, "name": stock.name,
                "date": str(dp.trade_date), "pct_change": float(dp.pct_change or 0),
            })

    # 3. 交易日缺口检查
    cal = session.query(TradingCalendar).filter_by(is_open=1).order_by(TradingCalendar.trade_date).all()
    if len(cal) > 1:
        for i in range(1, min(len(cal), 20)):
            delta = (cal[i].trade_date - cal[i - 1].trade_date).days
            if delta > 5:
                report["date_gaps"].append({
                    "from": str(cal[i - 1].trade_date),
                    "to": str(cal[i].trade_date),
                    "gap_days": delta - 1,
                })

    if not report["issues"]:
        total_issues = (
            len(report["stocks_with_null_prices"])
            + len(report["stocks_with_outliers"])
            + len(report["date_gaps"])
        )
        if total_issues == 0:
            report["issues"].append("未发现数据质量问题")
        else:
            report["issues"].append(f"发现 {total_issues} 个数据问题")

    report["issues"].append(f"股票: {report['stock_count']} | 日线: {report['daily_prices_count']} | 指标: {report['indicator_count']} | 日历: {report['calendar_count']}")

    return report


def check_missing_trading_dates(session: Session, stock_code: str) -> list[str]:
    """检查指定股票缺失的交易日"""
    stock = session.query(Stock).filter_by(code=stock_code).first()
    if not stock:
        return ["股票不存在"]

    trading_days = (
        session.query(TradingCalendar.trade_date)
        .filter(TradingCalendar.is_open == 1)
        .order_by(TradingCalendar.trade_date)
        .all()
    )
    trading_days = {r[0] for r in trading_days}

    existing_dates = {
        r[0] for r in
        session.query(DailyPrice.trade_date)
        .filter(DailyPrice.stock_id == stock.id)
        .all()
    }

    missing = sorted(trading_days - existing_dates)
    return [str(d) for d in missing[:50]]
