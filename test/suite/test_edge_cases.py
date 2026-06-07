"""
test_edge_cases.py - 边界条件与异常处理测试
覆盖：双源校验（无重叠日期、成交量差异）、无amount列缓存、日期过滤查询、
       is_cache_fresh异常输入、Config None值、空缓存统计
"""

import json
import os
import tempfile
from datetime import date, timedelta

import pytest
import pandas as pd
from unittest.mock import MagicMock, patch

pytestmark = pytest.mark.unit


# ─── 辅助函数 ────────────────────────────────────────────────────────────────

def make_cache_manager_with_temp(tmp_path, db_suffix="t.db"):
    """创建带临时DB的 CacheManager"""
    import json, tempfile
    from StockDataMaster.config import Config
    from StockDataMaster.cache.cache_manager import CacheManager

    config_data = {
        "cache": {
            "enabled": True,
            "db_path": str(tmp_path / db_suffix).replace("\\", "/"),
            "max_days_per_stock": 120,
            "stock_name_expire_days": 30,
            "stock_name_cleanup_day": 0,
            "stock_name_skip_expiration_check": True,
            "validation": {
                "price_tolerance_abs": 0.01,
                "price_tolerance_pct": 0.005,
                "volume_tolerance_pct": 0.05
            }
        },
        "health_check": {"enabled": False},
        "hot_switch": {"enabled": False}
    }
    tmp = tempfile.NamedTemporaryFile(
        mode='w', suffix='.json', delete=False, encoding='utf-8'
    )
    json.dump(config_data, tmp)
    tmp.close()
    config = Config(tmp.name)
    os.unlink(tmp.name)
    return CacheManager(config, {})


# ─── 双源校验边界 ─────────────────────────────────────────────────────────────

def test_validate_and_cache_no_date_overlap(tmp_path):
    """双源数据日期无重叠时返回 df1（无法校验）"""
    cm = make_cache_manager_with_temp(tmp_path, "t1.db")
    df1 = pd.DataFrame([{
        'date': '2024-01-01', 'open': 100.0, 'high': 105.0,
        'low': 98.0, 'close': 102.0, 'volume': 1_000_000.0, 'amount': 0.0
    }])
    df2 = pd.DataFrame([{
        'date': '2024-06-01', 'open': 200.0, 'high': 205.0,
        'low': 198.0, 'close': 202.0, 'volume': 2_000_000.0, 'amount': 0.0
    }])
    result = cm.validate_and_cache("600600", df1, df2, "tushare", "mootdx")
    # 无重叠日期时应返回 df1（不校验）
    assert result is not None


def test_validate_and_cache_volume_mismatch(tmp_path):
    """成交量差异超过容差（10倍）时校验失败"""
    cm = make_cache_manager_with_temp(tmp_path, "t2.db")
    df1 = pd.DataFrame([{
        'date': '2024-01-02', 'open': 100.0, 'high': 105.0,
        'low': 98.0, 'close': 102.0, 'volume': 1_000_000.0, 'amount': 0.0
    }])
    df2 = df1.copy()
    df2['volume'] = 10_000_000.0  # 10倍差异，远超 5% 容差
    result = cm.validate_and_cache("600601", df1, df2, "tushare", "mootdx")
    assert result is None


# ─── 缓存写入边界 ─────────────────────────────────────────────────────────────

def test_cache_without_amount_column(tmp_path):
    """没有 amount 列的数据也可以成功缓存"""
    cm = make_cache_manager_with_temp(tmp_path, "t3.db")
    df = pd.DataFrame([{
        'date': '2024-02-01', 'open': 100.0, 'high': 105.0,
        'low': 98.0, 'close': 102.0, 'volume': 1_000_000.0
        # 故意不包含 amount
    }])
    assert cm.save_to_cache("600602", df, "tushare", None, validated=True)


def test_cache_get_with_date_filter(tmp_path):
    """日期过滤查询返回正确范围内的数据"""
    cm = make_cache_manager_with_temp(tmp_path, "t4.db")

    # 插入 2024-01-01 到 2024-01-10 的数据
    rows = []
    for i in range(10):
        d = date(2024, 1, 1) + timedelta(days=i)
        rows.append({
            'date': d.strftime('%Y-%m-%d'), 'open': 100.0, 'high': 105.0,
            'low': 98.0, 'close': 102.0, 'volume': 1_000_000.0, 'amount': 0.0
        })
    df = pd.DataFrame(rows)
    cm.save_to_cache("600603", df, "tushare", "baostock", validated=True)

    # 查询 2024-01-03 ~ 2024-01-07（最多5条）
    result = cm.get_cached_kline("600603", start_date='2024-01-03', end_date='2024-01-07')
    assert result is not None
    assert len(result) <= 5
    # 所有日期应在范围内
    for d in result['date']:
        assert d >= '2024-01-03'
        assert d <= '2024-01-07'


# ─── _is_cache_fresh 边界 ─────────────────────────────────────────────────────

def test_is_cache_fresh_none_input(tmp_path):
    """_is_cache_fresh 接受 None 输入时返回 False"""
    import json, tempfile
    from StockDataMaster.config import Config

    db_path = str(tmp_path / "fresh_test.db").replace("\\", "/")
    config_data = {
        "use_builtin_libs": True,
        "data_sources": {
            "mootdx": {
                "enabled": True, "priority": 2,
                "use_for": ["kline_day"], "timeout": 5, "retry_times": 3
            }
        },
        "cache": {
            "enabled": False, "db_path": db_path,
            "max_days_per_stock": 120,
            "stock_name_expire_days": 30, "stock_name_cleanup_day": 0,
            "stock_name_skip_expiration_check": True,
            "validation": {
                "price_tolerance_abs": 0.01, "price_tolerance_pct": 0.005,
                "volume_tolerance_pct": 0.05
            }
        },
        "health_check": {
            "enabled": False, "interval_seconds": 60,
            "response_time_threshold": 5.0, "consecutive_failures_threshold": 3,
            "data_freshness_days": 3
        },
        "hot_switch": {"enabled": False},
        "logging": {"level": "WARNING", "file": None}
    }
    tmp = tempfile.NamedTemporaryFile(
        mode='w', suffix='.json', delete=False, encoding='utf-8'
    )
    json.dump(config_data, tmp)
    tmp.close()

    mock_mootdx = MagicMock()
    mock_mootdx.connect.return_value = True
    mock_mootdx.is_connected = True
    mock_mootdx.name = "mootdx"
    mock_mootdx.config = {"enabled": True, "priority": 2,
                           "use_for": ["kline_day"], "timeout": 5}

    with patch('StockDataMaster.adapters.AdapterFactory.create_adapter',
               return_value=mock_mootdx):
        from StockDataMaster.data_master import StockDataMaster
        dm = StockDataMaster(config_path=tmp.name)

    os.unlink(tmp.name)
    assert dm._is_cache_fresh(None) is False


# ─── Config 边界 ─────────────────────────────────────────────────────────────

def test_config_get_none_value():
    """Config.get 能正确返回值为 None 的配置项"""
    from StockDataMaster.config import Config
    config_data = {"key": None, "nested": {"inner": None}}
    tmp = tempfile.NamedTemporaryFile(
        mode='w', suffix='.json', delete=False, encoding='utf-8'
    )
    json.dump(config_data, tmp)
    tmp.close()
    c = Config(tmp.name)
    os.unlink(tmp.name)
    assert c.get('key') is None
    assert c.get('nested.inner') is None


# ─── 统计边界 ────────────────────────────────────────────────────────────────

def test_cache_statistics_when_empty(tmp_path):
    """空缓存的统计信息：记录数和股票数为 0"""
    cm = make_cache_manager_with_temp(tmp_path, "empty.db")
    stats = cm.get_cache_statistics()
    assert stats['enabled'] is True
    assert stats['total_records'] == 0
    assert stats['stock_count'] == 0
