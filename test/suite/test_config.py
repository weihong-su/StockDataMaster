"""
test_config.py - Config 配置管理单元测试
覆盖：Config.get(), get_enabled_sources(), get_sources_by_usage() 等核心方法
"""

import json
import os
import tempfile

import pytest

pytestmark = pytest.mark.unit


# ─── 辅助函数 ────────────────────────────────────────────────────────────────

def make_config(extra: dict = None):
    """创建临时配置文件并返回 Config 实例"""
    base = {
        "use_builtin_libs": True,
        "data_sources": {
            "tushare":  {"enabled": True,  "priority": 1, "token": "test_token",
                         "use_for": ["kline_day"], "timeout": 10},
            "mootdx":   {"enabled": True,  "priority": 2,
                         "use_for": ["kline_day", "kline_minute"], "timeout": 5},
            "baostock": {"enabled": False, "priority": 3,
                         "use_for": ["kline_day"], "timeout": 8},
            "xtquant":  {"enabled": False, "priority": 1,
                         "use_for": ["tick"], "timeout": 5}
        },
        "cache": {
            "enabled": True, "db_path": "cache/test.db",
            "max_days_per_stock": 120,
            "stock_name_expire_days": 30, "stock_name_cleanup_day": 0,
            "stock_name_skip_expiration_check": True,
            "validation": {
                "price_tolerance_abs": 0.01,
                "price_tolerance_pct": 0.005,
                "volume_tolerance_pct": 0.05
            }
        },
        "health_check": {"enabled": False, "interval_seconds": 60,
                         "response_time_threshold": 5.0,
                         "consecutive_failures_threshold": 3,
                         "data_freshness_days": 3},
        "hot_switch": {"enabled": False},
        "logging": {"level": "WARNING", "file": None}
    }
    if extra:
        base.update(extra)

    from StockDataMaster.config import Config
    tmp = tempfile.NamedTemporaryFile(
        mode='w', suffix='.json', delete=False, encoding='utf-8'
    )
    json.dump(base, tmp)
    tmp.close()
    c = Config(tmp.name)
    os.unlink(tmp.name)
    return c


# ─── 测试：基础 get ───────────────────────────────────────────────────────────

def test_get_simple():
    """基础键 get 返回正确值"""
    c = make_config()
    assert c.get('use_builtin_libs') is True


def test_get_nested():
    """嵌套键 get 支持点号分隔"""
    c = make_config()
    assert c.get('cache.max_days_per_stock') == 120
    assert c.get('cache.validation.price_tolerance_abs') == 0.01


def test_get_default():
    """缺失键返回默认值"""
    c = make_config()
    assert c.get('nonexistent.key', 'DEFAULT') == 'DEFAULT'


def test_get_none_default():
    """缺失键无默认值时返回 None"""
    c = make_config()
    assert c.get('nonexistent.key') is None


# ─── 测试：数据源查询 ─────────────────────────────────────────────────────────

def test_get_enabled_sources_sorted():
    """启用数据源按优先级升序排列"""
    c = make_config()
    sources = c.get_enabled_sources()
    # tushare(1) < mootdx(2), baostock 和 xtquant disabled
    assert sources == ['tushare', 'mootdx']


def test_get_sources_by_usage_kline_day():
    """kline_day 用途：按优先级返回启用源"""
    c = make_config()
    sources = c.get_sources_by_usage('kline_day')
    assert sources == ['tushare', 'mootdx']


def test_get_sources_by_usage_kline_minute():
    """kline_minute 用途：只有 mootdx 支持"""
    c = make_config()
    sources = c.get_sources_by_usage('kline_minute')
    assert sources == ['mootdx']


def test_get_sources_by_usage_empty():
    """tick 用途：所有支持的源都被禁用，返回空列表"""
    c = make_config()
    sources = c.get_sources_by_usage('tick')
    assert sources == []


# ─── 测试：状态查询方法 ──────────────────────────────────────────────────────

def test_is_cache_enabled():
    """is_cache_enabled() 返回正确状态"""
    c = make_config()
    assert c.is_cache_enabled() is True


def test_is_health_check_disabled():
    """is_health_check_enabled() 配置为 False 时返回 False"""
    c = make_config()
    assert c.is_health_check_enabled() is False


def test_get_cache_max_days():
    """get_cache_max_days() 返回配置值"""
    c = make_config()
    assert c.get_cache_max_days() == 120


# ─── 测试：错误处理 ───────────────────────────────────────────────────────────

def test_invalid_json_raises():
    """无效 JSON 格式应抛出 ValueError"""
    from StockDataMaster.config import Config
    tmp = tempfile.NamedTemporaryFile(
        mode='w', suffix='.json', delete=False, encoding='utf-8'
    )
    tmp.write("{ invalid json }")
    tmp.close()
    try:
        with pytest.raises(ValueError):
            Config(tmp.name)
    finally:
        os.unlink(tmp.name)


def test_missing_file_raises():
    """不存在的配置文件应抛出 FileNotFoundError"""
    from StockDataMaster.config import Config
    with pytest.raises(FileNotFoundError):
        Config("/nonexistent/path/config.json")


# ─── 测试：roles 格式解析 ─────────────────────────────────────────────────────

class TestRolesConfig:
    """roles 格式配置解析测试"""

    def test_get_sources_by_role_kline_day(self, temp_cache_config):
        """按角色获取日线数据源列表"""
        from StockDataMaster.config import Config
        sources = temp_cache_config.get_sources_by_role('kline_day')
        assert sources == ['tushare', 'mootdx', 'baostock']

    def test_get_sources_by_role_kline_minute(self, temp_cache_config):
        """按角色获取分钟线数据源列表"""
        from StockDataMaster.config import Config
        sources = temp_cache_config.get_sources_by_role('kline_minute')
        assert sources == ['xtquant', 'mootdx', 'baostock']

    def test_get_sources_by_role_tick(self, temp_cache_config):
        """按角色获取tick数据源列表"""
        from StockDataMaster.config import Config
        sources = temp_cache_config.get_sources_by_role('tick')
        assert sources == ['xtquant']

    def test_get_sources_by_role_trading_filters_timeslot(self, temp_cache_config):
        """交易时段角色: 只返回 time_slot 匹配或无 time_slot 的源"""
        from StockDataMaster.config import Config
        # trading 时段: xtquant 有 time_slot="trading", 应包含
        sources = temp_cache_config.get_sources_by_role('validation', time_slot='trading')
        assert 'xtquant' in sources

    def test_get_sources_by_role_after_hours_excludes_trading_only(self, temp_cache_config):
        """盘后时段: 排除 time_slot="trading" 的源"""
        from StockDataMaster.config import Config
        sources = temp_cache_config.get_sources_by_role('validation', time_slot='after_hours')
        assert 'xtquant' not in sources
        assert 'baostock' in sources

    def test_get_validation_config(self, temp_cache_config):
        """获取投票校验配置"""
        from StockDataMaster.config import Config
        vc = temp_cache_config.get_validation_config()
        assert vc['mode'] == 'voting'
        assert vc['quorum'] == 2
        assert vc['strategy'] == 'first_to_quorum'

    def test_get_stock_name_config_defaults(self, temp_cache_config):
        """获取 stock_name 配置"""
        from StockDataMaster.config import Config
        snc = temp_cache_config.get_stock_name_config()
        assert snc['baostock_max_consecutive_failures'] == 3
        assert snc['baostock_retry_cooldown'] == 300

    def test_legacy_config_auto_migrate(self):
        """旧格式 use_for 自动迁移为 roles"""
        import tempfile, json, os
        with tempfile.NamedTemporaryFile(mode='w', suffix='.json', delete=False, encoding='utf-8') as f:
            json.dump({
                "data_sources": {
                    "tushare": {
                        "enabled": True,
                        "priority": 1,
                        "use_for": ["kline_day"],
                        "token": "test"
                    }
                },
                "cache": {"enabled": True},
                "health_check": {"enabled": False}
            }, f)
            path = f.name
        try:
            from StockDataMaster.config import Config
            cfg = Config(path)
            # _migrate_legacy_config 应自动补充 roles
            sources = cfg.get_sources_by_role('kline_day')
            assert 'tushare' in sources
        finally:
            os.unlink(path)
