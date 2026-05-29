"""爬虫模块测试 — mock HTTP 响应，不触发真实网络请求"""

from datetime import date
from decimal import Decimal
from unittest.mock import MagicMock, patch

from sqlalchemy.orm import Session

from stock_platform.crawler.daily_price import _fetch_from_sina
from stock_platform.data.utils import to_decimal, to_float


def test_to_decimal():
    """to_decimal 边界情况"""
    assert to_decimal("12.34") == Decimal("12.34")
    assert to_decimal(12.34) == Decimal("12.34")
    assert to_decimal(None) is None
    assert to_decimal("null") is None
    assert to_decimal("") is None


def test_to_float():
    """to_float 边界情况"""
    assert to_float("12.34") == 12.34
    assert to_float(12) == 12.0
    assert to_float(None) is None
    assert to_float("null") is None
    assert to_float("") is None  # empty string


def _make_mock_session():
    """创建一个 mock session，查询返回空"""
    session = MagicMock(spec=Session)
    q = MagicMock()
    q.filter_by.return_value.first.return_value = None
    q.filter.return_value = q
    session.query.return_value = q
    return session


@patch("stock_platform.crawler.daily_price.requests.Session")
def test_fetch_from_sina_parsing(mock_session_cls):
    """验证新浪 K 线 JSON 能正确解析为 DailyPrice"""
    mock_http = MagicMock()
    mock_session_cls.return_value = mock_http

    # 模拟新浪返回的 JSON 数据
    fake_json = [
        {"day": "2024-01-02", "open": "10.50", "close": "10.80",
         "high": "10.90", "low": "10.40", "volume": "12345678"},
        {"day": "2024-01-03", "open": "10.80", "close": "10.60",
         "high": "10.85", "low": "10.55", "volume": "9876543"},
    ]
    resp = MagicMock()
    resp.text = str(fake_json).replace("'", '"')
    resp.status_code = 200
    mock_http.get.return_value = resp

    session = _make_mock_session()
    stock = MagicMock()
    stock.id = 1
    stock.code = "000001"
    stock.market = "SZ"
    stock.name = "平安银行"

    count = _fetch_from_sina(
        session, stock,
        date(2024, 1, 1), date(2024, 1, 31),
    )
    assert count == 2

    # 验证 session.add 被调用了 2 次（每只 K 线添加一条 DailyPrice）
    assert session.add.call_count == 2

    # 验证第一个 DailyPrice 字段正确
    first_call_args = session.add.call_args_list[0][0][0]
    assert first_call_args.open_price == Decimal("10.50")
    assert first_call_args.close_price == Decimal("10.80")
    assert first_call_args.volume == 12345678


@patch("stock_platform.crawler.daily_price.requests.Session")
def test_fetch_from_sina_null_response(mock_session_cls):
    """新浪返回 'null' 时返回 0"""
    mock_http = MagicMock()
    mock_session_cls.return_value = mock_http
    resp = MagicMock()
    resp.text = "null"
    mock_http.get.return_value = resp

    session = _make_mock_session()
    stock = MagicMock()
    stock.id = 1
    stock.code = "000001"
    stock.market = "SZ"

    count = _fetch_from_sina(
        session, stock,
        date(2024, 1, 1), date(2024, 1, 31),
    )
    assert count == 0


@patch("stock_platform.crawler.daily_price.requests.Session")
def test_fetch_from_sina_missing_fields(mock_session_cls):
    """新浪返回缺字段的 K 线数据时不应抛异常"""
    mock_http = MagicMock()
    mock_session_cls.return_value = mock_http

    # 模拟缺少 close 字段
    fake_json = [
        {"day": "2024-01-02", "open": "10.50",         # 缺少 close
         "high": "10.90", "low": "10.40", "volume": "12345678"},
    ]
    resp = MagicMock()
    resp.text = str(fake_json).replace("'", '"')
    resp.status_code = 200
    mock_http.get.return_value = resp

    session = _make_mock_session()
    stock = MagicMock()
    stock.id = 1
    stock.code = "000001"
    stock.market = "SZ"

    count = _fetch_from_sina(
        session, stock,
        date(2024, 1, 1), date(2024, 1, 31),
    )
    assert count == 1  # 缺字段但是不应该抛异常
