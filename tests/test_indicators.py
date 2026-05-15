"""技术指标计算测试"""
import pytest
import numpy as np
from datetime import date

from stock_platform.data.indicators import _ma, _rsi, _bollinger


def test_ma():
    arr = np.array([1.0, 2.0, 3.0, 4.0, 5.0, 6.0])
    assert _ma(arr, 4, 5) == 3.0  # arr[0:5] = [1,2,3,4,5] mean=3.0
    assert _ma(arr, 5, 3) == 5.0  # arr[3:6] = [4,5,6] mean=5.0
    assert _ma(arr, 2, 5) is None  # not enough data


def test_rsi():
    closes = np.array([44.34, 44.09, 44.15, 43.61, 44.33, 44.83, 45.10, 45.42, 45.84, 46.08,
                       45.89, 46.03, 45.61, 46.28, 46.28, 46.00, 46.03, 46.41, 46.22, 46.21])
    rsi = _rsi(closes, 14)
    assert rsi is not None
    assert 30 <= rsi <= 70  # reasonable range


def test_bollinger():
    closes = np.arange(20, dtype=float) + 100
    up, mid, down = _bollinger(closes)
    assert mid == pytest.approx(109.5)
    assert up > mid > down


def test_ma_insufficient_data():
    arr = np.array([1.0, 2.0, 3.0])
    result = _ma(arr, 2, 5)
    assert result is None


def test_indicators_module_import():
    from stock_platform.data.indicators import calculate_all_indicators, calculate_indicators
    assert callable(calculate_all_indicators)
    assert callable(calculate_indicators)
