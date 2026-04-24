"""
test_cache_manager.py - CacheManager 缓存管理单元测试
覆盖：初始化、读写K线、双源校验、统计、股票名称缓存、并发、盘中策略
"""

import json
import os
import tempfile
import threading
from datetime import date, timedelta

import pytest
import pandas as pd

pytestmark = pytest.mark.unit

REQUIRED_KLINE_COLS = ['date', 'open', 'high', 'low', 'close', 'volume']


# ─── 辅助函数 ────────────────────────────────────────────────────────────────

def make_sample_df(days=5, start_days_ago=10):
    """生成连续历史K线DataFrame，默认5条，从10天前开始"""
    today = date.today()
    rows = []
    for i in range(days):
        d = today - timedelta(days=start_days_ago - i)
        rows.append({
            'date': d.strftime('%Y-%m-%d'),
            'open': 100.0 + i,
            'high': 105.0 + i,
            'low': 98.0 + i,
            'close': 102.0 + i,
            'volume': 1_000_000.0 + i * 100,
            'amount': 102_000_000.0 + i * 10_000
        })
    return pd.DataFrame(rows)


# ─── 测试：初始化 ─────────────────────────────────────────────────────────────

def test_init_creates_db(temp_cache_config):
    """初始化时自动创建 SQLite 数据库文件"""
    from StockDataMaster.cache.cache_manager import CacheManager
    cm = CacheManager(temp_cache_config, {})
    assert cm.enabled is True
    assert os.path.exists(cm.db_path)


# ─── 测试：K线读写 ────────────────────────────────────────────────────────────

def test_save_and_get_kline(temp_cache_config):
    """保存后可正确读取K线数据"""
    from StockDataMaster.cache.cache_manager import CacheManager
    cm = CacheManager(temp_cache_config, {})
    df = make_sample_df(days=5, start_days_ago=10)
    assert cm.save_to_cache("600519", df, "tushare", "mootdx", validated=True)
    cached = cm.get_cached_kline("600519")
    assert cached is not None
    assert len(cached) >= 1
    for col in REQUIRED_KLINE_COLS:
        assert col in cached.columns


def test_get_cached_kline_with_count(temp_cache_config):
    """count 参数限制返回条数"""
    from StockDataMaster.cache.cache_manager import CacheManager
    cm = CacheManager(temp_cache_config, {})
    df = make_sample_df(days=10, start_days_ago=15)
    cm.save_to_cache("600001", df, "tushare", "mootdx", validated=True)
    cached = cm.get_cached_kline("600001", count=3)
    assert cached is not None
    assert len(cached) <= 3


def test_get_cached_kline_nonexistent(temp_cache_config):
    """查询不存在的股票返回 None"""
    from StockDataMaster.cache.cache_manager import CacheManager
    cm = CacheManager(temp_cache_config, {})
    assert cm.get_cached_kline("999999") is None


def test_cache_date_ascending_order(temp_cache_config):
    """缓存数据按日期升序返回"""
    from StockDataMaster.cache.cache_manager import CacheManager
    cm = CacheManager(temp_cache_config, {})
    df = make_sample_df(days=5, start_days_ago=10)
    cm.save_to_cache("600520", df, "tushare", None, validated=True)
    cached = cm.get_cached_kline("600520")
    dates = cached['date'].tolist()
    assert dates == sorted(dates), "日期应按升序排列"


# ─── 测试：双源校验 ───────────────────────────────────────────────────────────

def test_validate_and_cache_identical_pass(temp_cache_config):
    """双源数据完全相同时校验通过"""
    from StockDataMaster.cache.cache_manager import CacheManager
    cm = CacheManager(temp_cache_config, {})
    df1 = make_sample_df(days=5, start_days_ago=10)
    df2 = df1.copy()
    result = cm.validate_and_cache("600521", df1, df2, "tushare", "mootdx")
    assert result is not None
    assert len(result) >= 1


def test_validate_and_cache_price_diff_fail(temp_cache_config):
    """价格差异超过容差时校验失败，返回 None"""
    from StockDataMaster.cache.cache_manager import CacheManager
    cm = CacheManager(temp_cache_config, {})
    df1 = make_sample_df(days=5, start_days_ago=10)
    df2 = df1.copy()
    # 价格提高 50%，远超 ±0.5% 容差
    for col in ['close', 'open', 'high', 'low']:
        df2[col] = df2[col] * 1.5
    result = cm.validate_and_cache("600522", df1, df2, "tushare", "mootdx")
    assert result is None


def test_validate_and_cache_empty_df2(temp_cache_config):
    """df2 为空时跳过校验，直接返回 df1"""
    from StockDataMaster.cache.cache_manager import CacheManager
    cm = CacheManager(temp_cache_config, {})
    df1 = make_sample_df(days=3, start_days_ago=10)
    df2 = pd.DataFrame()
    result = cm.validate_and_cache("600523", df1, df2, "tushare", "mootdx")
    assert result is not None
    assert len(result) >= 1


# ─── 测试：清理 ───────────────────────────────────────────────────────────────

def test_cleanup_old_cache(temp_cache_config):
    """清理超过 120 天的旧数据"""
    from StockDataMaster.cache.cache_manager import CacheManager
    cm = CacheManager(temp_cache_config, {})
    old_df = pd.DataFrame([{
        'date': (date.today() - timedelta(days=200)).strftime('%Y-%m-%d'),
        'open': 100.0, 'high': 105.0, 'low': 98.0,
        'close': 102.0, 'volume': 1_000_000.0, 'amount': 102_000_000.0
    }])
    cm.save_to_cache("600524", old_df, "tushare", None, validated=True)
    cm.cleanup_old_cache(days=120)
    assert cm.get_cached_kline("600524") is None


# ─── 测试：统计 ───────────────────────────────────────────────────────────────

def test_get_cache_statistics(temp_cache_config):
    """统计信息结构和内容正确"""
    from StockDataMaster.cache.cache_manager import CacheManager
    cm = CacheManager(temp_cache_config, {})
    df = make_sample_df(days=5, start_days_ago=10)
    cm.save_to_cache("600525", df, "tushare", None, validated=True)
    stats = cm.get_cache_statistics()
    assert stats['enabled'] is True
    assert stats['total_records'] >= 5
    assert stats['stock_count'] >= 1


def test_cache_statistics_empty(temp_cache_config):
    """空缓存统计信息正确"""
    from StockDataMaster.cache.cache_manager import CacheManager
    cm = CacheManager(temp_cache_config, {})
    stats = cm.get_cache_statistics()
    assert stats['enabled'] is True
    assert stats['total_records'] == 0
    assert stats['stock_count'] == 0


# ─── 测试：股票名称缓存 ───────────────────────────────────────────────────────

def test_stock_name_cache_write_read(temp_cache_config):
    """股票名称缓存写入后可正确读取"""
    from StockDataMaster.cache.cache_manager import CacheManager
    cm = CacheManager(temp_cache_config, {})
    cm.cache_stock_name("600519", "贵州茅台", "baostock")
    assert cm.get_cached_stock_name("600519") == "贵州茅台"


def test_stock_name_cache_nonexistent(temp_cache_config):
    """不存在的股票名称查询返回 None"""
    from StockDataMaster.cache.cache_manager import CacheManager
    cm = CacheManager(temp_cache_config, {})
    assert cm.get_cached_stock_name("999999") is None


def test_stock_name_cache_count(temp_cache_config):
    """股票名称缓存计数正确"""
    from StockDataMaster.cache.cache_manager import CacheManager
    cm = CacheManager(temp_cache_config, {})
    cm.cache_stock_name("600519", "贵州茅台", "baostock")
    cm.cache_stock_name("000001", "平安银行", "baostock")
    assert cm.get_stock_name_cache_count() >= 2


# ─── 测试：禁用缓存 ───────────────────────────────────────────────────────────

def test_cache_disabled(tmp_path):
    """禁用缓存时所有操作返回安全值"""
    import json, tempfile
    from StockDataMaster.config import Config
    from StockDataMaster.cache.cache_manager import CacheManager

    config_data = {
        "cache": {
            "enabled": False,
            "db_path": str(tmp_path / "disabled.db"),
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

    cm = CacheManager(config, {})
    assert cm.enabled is False
    assert cm.get_cached_kline("600519") is None
    df = make_sample_df()
    assert cm.save_to_cache("600519", df, "tushare", None, validated=True) is False


# ─── 测试：并发 ───────────────────────────────────────────────────────────────

def test_concurrent_cache_access(temp_cache_config):
    """并发写入缓存不应产生异常（线程安全）"""
    from StockDataMaster.cache.cache_manager import CacheManager
    cm = CacheManager(temp_cache_config, {})
    errors = []

    def write_cache(code, days_ago):
        try:
            df = pd.DataFrame([{
                'date': (date.today() - timedelta(days=days_ago)).strftime('%Y-%m-%d'),
                'open': 100.0, 'high': 105.0, 'low': 98.0,
                'close': 102.0, 'volume': 1_000_000.0, 'amount': 102_000_000.0
            }])
            cm.save_to_cache(code, df, "tushare", None, validated=True)
        except Exception as e:
            errors.append(str(e))

    threads = [
        threading.Thread(target=write_cache, args=(f"60052{i}", i + 1))
        for i in range(5)
    ]
    for t in threads:
        t.start()
    for t in threads:
        t.join()

    assert errors == [], f"并发写入出现错误: {errors}"


# ─── 测试：历史数据缓存 ───────────────────────────────────────────────────────

def test_historical_data_can_be_cached(temp_cache_config):
    """历史数据（非当日）应可以正常缓存"""
    from StockDataMaster.cache.cache_manager import CacheManager
    cm = CacheManager(temp_cache_config, {})
    hist_date = (date.today() - timedelta(days=5)).strftime('%Y-%m-%d')
    df = pd.DataFrame([{
        'date': hist_date, 'open': 100.0, 'high': 105.0, 'low': 98.0,
        'close': 102.0, 'volume': 1_000_000.0, 'amount': 102_000_000.0
    }])
    assert cm.save_to_cache("600530", df, "tushare", None, validated=True)
    cached = cm.get_cached_kline("600530")
    assert cached is not None


# ─── 测试：三选二投票校验 ──────────────────────────────────────────────────────

class TestVotingValidation:
    """三选二投票校验测试"""

    def test_two_sources_agree_passes(self, temp_cache_config):
        """两个校验源一致 -> 通过"""
        from StockDataMaster.cache.cache_manager import CacheManager
        cm = CacheManager(temp_cache_config, {})

        # 主数据 (tushare)
        df1 = make_sample_df(5, start_days_ago=10)
        # 校验数据1 (与主数据一致)
        df2 = make_sample_df(5, start_days_ago=10)
        # 校验数据2 (与主数据一致)
        df3 = make_sample_df(5, start_days_ago=10)

        result = cm.validate_and_cache_voting(
            code='600519',
            primary_df=df1,
            validation_dfs={'baostock': df2, 'mootdx': df3},
            primary_source='tushare'
        )
        assert result is not None
        assert len(result) == 5

    def test_two_sources_disagree_fails(self, temp_cache_config):
        """两个校验源都不一致 -> 失败"""
        from StockDataMaster.cache.cache_manager import CacheManager
        cm = CacheManager(temp_cache_config, {})

        df1 = make_sample_df(5, start_days_ago=10)
        # 构造完全不同的数据
        df2 = make_sample_df(5, start_days_ago=10)
        df2['close'] = df2['close'] * 10  # 巨大差异
        df3 = make_sample_df(5, start_days_ago=10)
        df3['close'] = df3['close'] * 20  # 巨大差异

        result = cm.validate_and_cache_voting(
            code='600519',
            primary_df=df1,
            validation_dfs={'baostock': df2, 'mootdx': df3},
            primary_source='tushare'
        )
        assert result is None

    def test_one_agree_one_disagree_passes(self, temp_cache_config):
        """一个一致一个不一致 -> 一票通过，但需要二票，所以失败"""
        from StockDataMaster.cache.cache_manager import CacheManager
        cm = CacheManager(temp_cache_config, {})

        df1 = make_sample_df(5, start_days_ago=10)
        # 一致
        df2 = make_sample_df(5, start_days_ago=10)
        # 不一致
        df3 = make_sample_df(5, start_days_ago=10)
        df3['close'] = df3['close'] * 10

        result = cm.validate_and_cache_voting(
            code='600519',
            primary_df=df1,
            validation_dfs={'baostock': df2, 'mootdx': df3},
            primary_source='tushare'
        )
        # 只有一个源通过，不足二票，应该失败
        assert result is None

    def test_single_validation_source_passes(self, temp_cache_config):
        """只有一个校验源且一致 -> 通过(降级为二选一)"""
        from StockDataMaster.cache.cache_manager import CacheManager
        cm = CacheManager(temp_cache_config, {})

        df1 = make_sample_df(5, start_days_ago=10)
        df2 = make_sample_df(5, start_days_ago=10)

        result = cm.validate_and_cache_voting(
            code='600519',
            primary_df=df1,
            validation_dfs={'baostock': df2},
            primary_source='tushare'
        )
        assert result is not None

    def test_no_validation_sources_returns_unvalidated(self, temp_cache_config):
        """无校验源 -> 返回主数据(不缓存)"""
        from StockDataMaster.cache.cache_manager import CacheManager
        cm = CacheManager(temp_cache_config, {})

        df1 = make_sample_df(5, start_days_ago=10)

        result = cm.validate_and_cache_voting(
            code='600519',
            primary_df=df1,
            validation_dfs={},
            primary_source='tushare'
        )
        assert result is not None
        assert len(result) == 5
