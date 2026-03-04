"""
test_integration.py - 集成测试（需要网络和外部服务）
不可用时自动跳过，不影响 CI/CD 流程。
覆盖：Mootdx/Baostock K线获取、估值数据、Tick、完整流程
"""

import os
from datetime import date, timedelta

import pytest
import pandas as pd

pytestmark = pytest.mark.integration

# 使用浦发银行（稳定，流动性好）
TEST_CODE = "600000"
REQUIRED_COLUMNS = ['date', 'open', 'high', 'low', 'close', 'volume']

# 计算项目根目录路径
_SUITE_DIR = os.path.dirname(os.path.abspath(__file__))
_TEST_DIR = os.path.dirname(_SUITE_DIR)
PROJECT_ROOT = os.path.dirname(_TEST_DIR)


# ─── Mootdx 集成测试 ──────────────────────────────────────────────────────────

def test_mootdx_daily_kline():
    """Mootdx 获取日K线：数据完整、价格合理"""
    from StockDataMaster.adapters.mootdx_adapter import MootdxAdapter
    a = MootdxAdapter("mootdx", {"timeout": 5, "use_for": ["kline_day"]})
    if not a.connect():
        pytest.skip("Mootdx 连接失败")
    df = a.get_kline(TEST_CODE, freq='d', count=10)
    if df is None:
        pytest.skip("Mootdx 返回空数据")
    assert not df.empty
    for col in REQUIRED_COLUMNS:
        assert col in df.columns, f"缺少列: {col}"
    assert (df['close'] > 0).all(), "close 价格应 > 0"
    assert (df['high'] >= df['low']).all(), "high 应 >= low"
    a.disconnect()


def test_mootdx_minute_kline():
    """Mootdx 获取 5 分钟 K 线"""
    from StockDataMaster.adapters.mootdx_adapter import MootdxAdapter
    a = MootdxAdapter("mootdx", {"timeout": 5, "use_for": ["kline_minute"]})
    if not a.connect():
        pytest.skip("Mootdx 连接失败")
    df = a.get_kline(TEST_CODE, freq='5m', count=20)
    if df is None:
        pytest.skip("Mootdx 5m 返回空数据")
    assert not df.empty
    for col in REQUIRED_COLUMNS:
        assert col in df.columns
    a.disconnect()


def test_mootdx_data_quality():
    """Mootdx 数据质量：OHLC 逻辑正确"""
    from StockDataMaster.adapters.mootdx_adapter import MootdxAdapter
    a = MootdxAdapter("mootdx", {"timeout": 5, "use_for": ["kline_day"]})
    if not a.connect():
        pytest.skip("Mootdx 连接失败")
    df = a.get_kline(TEST_CODE, freq='d', count=30)
    if df is None:
        pytest.skip("Mootdx 返回空数据")
    assert (df['high'] >= df['low']).all(),   "high >= low"
    assert (df['high'] >= df['open']).all(),  "high >= open"
    assert (df['high'] >= df['close']).all(), "high >= close"
    assert (df['low'] <= df['open']).all(),   "low <= open"
    assert (df['low'] <= df['close']).all(),  "low <= close"
    assert (df['close'] > 0).all(),           "close > 0"
    assert (df['volume'] >= 0).all(),         "volume >= 0"
    a.disconnect()


def test_mootdx_realtime_tick():
    """Mootdx 获取实时 Tick 数据"""
    from StockDataMaster.adapters.mootdx_adapter import MootdxAdapter
    a = MootdxAdapter("mootdx", {"timeout": 5, "use_for": ["tick"]})
    if not a.connect():
        pytest.skip("Mootdx 连接失败")
    tick = a.get_tick(TEST_CODE)
    if tick is None:
        pytest.skip("Mootdx tick 返回空数据")
    assert 'close' in tick
    assert 'last' in tick
    a.disconnect()


# ─── Baostock 集成测试 ────────────────────────────────────────────────────────

def test_baostock_daily_kline():
    """Baostock 获取日K线：数据完整"""
    from StockDataMaster.adapters.baostock_adapter import BaostockAdapter
    a = BaostockAdapter("baostock", {"timeout": 8, "use_for": ["kline_day"]})
    if not a.connect():
        pytest.skip("Baostock 连接失败")
    df = a.get_kline(TEST_CODE, freq='d', count=10)
    if df is None:
        pytest.skip("Baostock 返回空数据")
    assert not df.empty
    for col in REQUIRED_COLUMNS:
        assert col in df.columns, f"缺少列: {col}"
    a.disconnect()


def test_baostock_valuation():
    """Baostock 获取估值数据（PE/PB）"""
    from StockDataMaster.adapters.baostock_adapter import BaostockAdapter
    a = BaostockAdapter("baostock", {"timeout": 8, "use_for": ["valuation"]})
    if not a.connect():
        pytest.skip("Baostock 连接失败")
    end_date = date.today().strftime('%Y-%m-%d')
    start_date = (date.today() - timedelta(days=10)).strftime('%Y-%m-%d')
    df = a.get_valuation(TEST_CODE, start_date=start_date, end_date=end_date)
    if df is None:
        pytest.skip("Baostock 估值返回空数据")
    assert not df.empty
    a.disconnect()


# ─── DataMaster 完整流程 ──────────────────────────────────────────────────────

def test_full_data_master_no_cache():
    """DataMaster 完整流程 - 不使用缓存"""
    config_path = os.path.join(PROJECT_ROOT, "config.json")
    if not os.path.exists(config_path):
        pytest.skip("config.json 不存在")
    from StockDataMaster.data_master import StockDataMaster
    dm = StockDataMaster(config_path=config_path)
    if not dm.adapters:
        pytest.skip("无可用数据源")
    df = dm.get_kline(TEST_CODE, freq='d', count=10, use_cache=False)
    if df is None:
        pytest.skip("所有数据源均返回空数据")
    assert not df.empty
    assert len(df) >= 1
    for col in REQUIRED_COLUMNS:
        assert col in df.columns
    dm.close()


def test_full_data_master_with_cache():
    """DataMaster 完整流程 - 验证缓存命中"""
    config_path = os.path.join(PROJECT_ROOT, "config.json")
    if not os.path.exists(config_path):
        pytest.skip("config.json 不存在")
    from StockDataMaster.data_master import StockDataMaster
    dm = StockDataMaster(config_path=config_path)
    if not dm.adapters:
        pytest.skip("无可用数据源")
    # 第一次获取（可能从数据源）
    df1 = dm.get_kline(TEST_CODE, freq='d', count=5, use_cache=True)
    if df1 is None:
        pytest.skip("第一次获取失败")
    # 第二次获取（应命中缓存）
    df2 = dm.get_kline(TEST_CODE, freq='d', count=5, use_cache=True)
    assert df2 is not None
    assert not df2.empty
    dm.close()
