"""数据处理测试 — 使用 mock 不依赖真实数据库"""
from datetime import date
from unittest.mock import MagicMock

from stock_platform.data.etl import check_missing_trading_dates, data_quality_check


class MockStock:
    id = 1
    code = "000001"
    name = "平安银行"


class MockDailyPrice:
    def __init__(self, **kwargs):
        for k, v in kwargs.items():
            setattr(self, k, v)


class MockTradingCalendar:
    def __init__(self, trade_date, is_open=1):
        self.trade_date = trade_date
        self.is_open = is_open


def test_quality_report_empty():
    """空数据库的质量报告应返回正确结构"""
    session = MagicMock()
    # query() 接受可变参数，用 *args
    def query_side_effect(*args):
        q = MagicMock()
        q.count.return_value = 0
        q.filter.return_value = q
        q.filter_by.return_value = q
        q.group_by.return_value = q
        q.having.return_value = q
        q.limit.return_value = q
        q.order_by.return_value = q
        q.all.return_value = []
        q.first.return_value = None
        return q

    session.query.side_effect = query_side_effect

    report = data_quality_check(session)
    assert isinstance(report, dict)
    assert report["stock_count"] == 0
    assert report["daily_prices_count"] == 0


def test_quality_report_with_data():
    """模拟 3 只股票和交易日历的数据质量检查"""
    session = MagicMock()

    def query_side_effect(*args):
        q = MagicMock()
        # args[0] 是 model class，取其 __name__
        model_name = args[0].__name__ if hasattr(args[0], '__name__') else args[0].__class__.__name__

        q.count.return_value = 0
        q.filter.return_value = q
        q.filter_by.return_value = q
        q.group_by.return_value = q
        q.having.return_value = q
        q.limit.return_value = q
        q.order_by.return_value = q
        q.all.return_value = []
        q.first.return_value = None

        if model_name == "Stock":
            q.count.return_value = 3
        elif model_name == "DailyPrice":
            q.count.return_value = 1500
        elif model_name == "TechnicalIndicator":
            q.count.return_value = 1200
        elif model_name == "TradingCalendar":
            q.count.return_value = 242
            q.all.return_value = [
                MockTradingCalendar(date(2024, 1, 1)),
                MockTradingCalendar(date(2024, 1, 2)),
                MockTradingCalendar(date(2024, 1, 3)),
                MockTradingCalendar(date(2024, 1, 8)),  # 缺口
                MockTradingCalendar(date(2024, 1, 9)),
            ]
        return q

    session.query.side_effect = query_side_effect
    session.get.return_value = MockStock()

    report = data_quality_check(session)
    assert report["stock_count"] == 3
    assert report["daily_prices_count"] == 1500
    assert report["indicator_count"] == 1200


def test_calendar_generation():
    """验证交易日历生成函数可调用"""
    from stock_platform.data.calendar import seed_trading_calendar
    assert callable(seed_trading_calendar)


def test_missing_trading_dates_stock_not_found():
    """股票不存在时返回错误信息"""
    session = MagicMock()
    session.query.return_value.filter_by.return_value.first.return_value = None
    result = check_missing_trading_dates(session, "999999")
    assert "股票不存在" in result


def test_missing_trading_dates():
    """模拟检查缺失交易日"""
    session = MagicMock()

    stock = MagicMock()
    stock.id = 1

    cal_dates = [
        (date(2024, 1, 2),),
        (date(2024, 1, 3),),
        (date(2024, 1, 4),),
        (date(2024, 1, 5),),
    ]

    existing_dates = [
        (date(2024, 1, 2),),
        (date(2024, 1, 3),),
        (date(2024, 1, 5),),
    ]

    def query_side_effect(*args):
        q = MagicMock()
        q.filter.return_value = q
        q.filter_by.return_value = q
        q.order_by.return_value = q
        q.limit.return_value = q
        q.first.return_value = None
        q.all.return_value = []

        first_arg = args[0]
        # args[0] 可能是 model class 或 column attribute
        arg_str = str(first_arg)

        if 'Stock' in arg_str:
            q.filter_by.return_value.first.return_value = stock
        elif 'TradingCalendar' in arg_str:
            q.filter.return_value.order_by.return_value.all.return_value = cal_dates
        elif 'DailyPrice' in arg_str:
            q.filter.return_value.all.return_value = existing_dates

        return q

    session.query.side_effect = query_side_effect

    result = check_missing_trading_dates(session, "000001")
    assert "2024-01-04" in result
