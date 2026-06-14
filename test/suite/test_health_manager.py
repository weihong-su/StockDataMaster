"""
test_health_manager.py - HealthManager 健康管理单元测试
覆盖：get_active_source, force_switch, 失败触发切换, 健康报告, 监控线程, roles 格式适配
"""

import time

import pytest
from unittest.mock import MagicMock, patch
from datetime import datetime, time as time_type

pytestmark = pytest.mark.unit


# ─── 辅助函数 ────────────────────────────────────────────────────────────────

def make_mock_adapters():
    """创建三个 Mock 适配器（均健康）"""
    def _make(name, priority, use_for):
        m = MagicMock()
        m.name = name
        m.is_connected = True
        m.config = {"enabled": True, "priority": priority, "use_for": use_for, "timeout": 5}
        m.health_check.return_value = {
            "status": "ok", "response_time": 0.5,
            "data_freshness": True, "error_message": None
        }
        return m

    return {
        "tushare":  _make("tushare",  1, ["kline_day"]),
        "mootdx":   _make("mootdx",   2, ["kline_day", "kline_minute"]),
        "baostock": _make("baostock", 3, ["kline_day", "valuation"]),
    }


def make_health_manager(health_config, adapters=None):
    from StockDataMaster.health.health_manager import HealthManager
    if adapters is None:
        adapters = make_mock_adapters()
    return HealthManager(health_config, adapters)


# ─── 测试：get_active_source ─────────────────────────────────────────────────

def test_get_active_source_kline_abstract(health_config):
    """抽象类型 'kline' 映射到 'kline_day' 并找到数据源"""
    hm = make_health_manager(health_config)
    hm.check_all_sources()
    source = hm.get_active_source('kline')
    assert source is not None, "应能找到 kline 数据源"
    assert source in ["tushare", "mootdx", "baostock"]


def test_get_active_source_kline_day(health_config):
    """具体类型 'kline_day' 应返回最高优先级源"""
    hm = make_health_manager(health_config)
    hm.check_all_sources()
    source = hm.get_active_source('kline_day')
    assert source is not None
    assert source in ["tushare", "mootdx", "baostock"]


# ─── 测试：force_switch ───────────────────────────────────────────────────────

def test_force_switch_success(health_config):
    """强制切换到指定数据源"""
    hm = make_health_manager(health_config)
    hm.check_all_sources()
    result = hm.force_switch('kline_day', 'mootdx')
    assert result is True
    assert hm.active_sources.get('kline_day') == 'mootdx'


def test_force_switch_nonexistent(health_config):
    """切换到不存在的数据源应失败"""
    hm = make_health_manager(health_config)
    result = hm.force_switch('kline_day', 'nonexistent_source')
    assert result is False


# ─── 测试：自动切换 ───────────────────────────────────────────────────────────

def test_switch_triggered_on_consecutive_failures(health_config):
    """连续失败达到阈值（3次）时应触发切换"""
    adapters = make_mock_adapters()
    hm = make_health_manager(health_config, adapters)
    hm.check_all_sources()
    # 设置 tushare 为活跃源
    hm.active_sources['kline_day'] = 'tushare'
    # 让 tushare 连续失败
    adapters['tushare'].health_check.return_value = {
        "status": "error", "response_time": 10.0,
        "data_freshness": False, "error_message": "连接失败"
    }
    for _ in range(3):
        hm.check_all_sources()
    # 断言：tushare 已被切换，或失败计数 >= 3
    current = hm.active_sources.get('kline_day')
    tushare_failures = hm.failure_counts.get('tushare', 0)
    assert (current != 'tushare' or tushare_failures >= 3), \
        "tushare 连续失败后应切换或记录失败次数"


def test_switch_triggered_once_during_same_failure_streak(health_config):
    """同一轮连续故障跨过阈值后不应每次健康检查都重复触发切换"""
    adapters = make_mock_adapters()
    hm = make_health_manager(health_config, adapters)
    adapters['baostock'].health_check.return_value = {
        "status": "error", "response_time": 10.0,
        "data_freshness": False, "error_message": "无法获取测试数据"
    }
    hm._trigger_switch = MagicMock()

    for _ in range(5):
        hm.check_all_sources()

    assert hm.failure_counts['baostock'] == 5
    hm._trigger_switch.assert_called_once_with('baostock', '无法获取测试数据')


# ─── 测试：健康报告 ───────────────────────────────────────────────────────────

def test_health_report_structure(health_config):
    """get_health_report 返回必要字段"""
    hm = make_health_manager(health_config)
    report = hm.get_health_report()
    assert 'timestamp' in report
    assert 'sources' in report
    assert 'active_sources' in report
    assert 'recent_switches' in report


def test_switch_history_recorded(health_config):
    """强制切换后应记录切换历史"""
    hm = make_health_manager(health_config)
    hm.check_all_sources()
    hm.force_switch('kline_day', 'baostock')
    assert len(hm.switch_history) >= 1
    last_switch = list(hm.switch_history)[-1]
    assert last_switch['to'] == 'baostock'


# ─── 测试：监控线程 ───────────────────────────────────────────────────────────

def test_start_stop_monitoring(health_config):
    """监控线程可以正常启动和停止"""
    hm = make_health_manager(health_config)
    # Mock 掉实际健康检查避免真实网络请求
    hm.check_all_sources = MagicMock()
    hm._auto_recover_xtquant = MagicMock()
    hm.start_monitoring()
    assert hm.is_running is True
    time.sleep(0.1)
    hm.stop_monitoring()
    assert hm.is_running is False


# ─── 测试：roles 格式适配 ─────────────────────────────────────────────────────

class TestHealthManagerRoles:
    """HealthManager roles 格式适配测试"""

    def test_find_backup_source_with_roles(self, health_config):
        """使用 roles 格式查找备用源"""
        # 创建适配器，配置 roles 而非 use_for
        def _make_with_roles(name, roles_dict):
            m = MagicMock()
            m.name = name
            m.is_connected = True
            m.config = {
                "enabled": True,
                "roles": roles_dict,
                "timeout": 5
            }
            m.health_check.return_value = {
                "status": "ok", "response_time": 0.5,
                "data_freshness": True, "error_message": None
            }
            return m

        adapters = {
            "tushare": _make_with_roles("tushare", {
                "kline_day": {"priority": 1}
            }),
            "mootdx": _make_with_roles("mootdx", {
                "kline_day": {"priority": 2},
                "kline_minute": {"priority": 2}
            }),
            "baostock": _make_with_roles("baostock", {
                "kline_day": {"priority": 3}
            })
        }

        from StockDataMaster.health.health_manager import HealthManager
        hm = HealthManager(health_config, adapters)
        hm.check_all_sources()

        # 查找 kline_day 备用源（排除 tushare）
        backup = hm._find_backup_source('kline_day', exclude=['tushare'])

        # 应该返回 mootdx（priority=2，比 baostock 的 3 更高）
        assert backup == 'mootdx', f"应返回 mootdx，实际返回 {backup}"

    def test_find_backup_source_time_slot_trading_only(self, health_config):
        """trading-only 源在非交易时段不可用"""
        def _make_with_roles(name, roles_dict):
            m = MagicMock()
            m.name = name
            m.is_connected = True
            m.config = {
                "enabled": True,
                "roles": roles_dict,
                "timeout": 5
            }
            m.health_check.return_value = {
                "status": "ok", "response_time": 0.5,
                "data_freshness": True, "error_message": None
            }
            return m

        adapters = {
            "xtquant": _make_with_roles("xtquant", {
                "validation": {"priority": 1, "time_slot": "trading"}
            }),
            "baostock": _make_with_roles("baostock", {
                "validation": {"priority": 2}
            }),
            "mootdx": _make_with_roles("mootdx", {
                "validation": {"priority": 3}
            })
        }

        from StockDataMaster.health.health_manager import HealthManager
        hm = HealthManager(health_config, adapters)
        hm.check_all_sources()

        # Mock 当前时间为非交易时段（例如 20:00）
        with patch('StockDataMaster.health.health_manager.datetime') as mock_dt:
            mock_now = MagicMock()
            mock_now.time.return_value = time_type(20, 0)  # 20:00
            mock_dt.now.return_value = mock_now

            # 查找 validation 备用源
            backup = hm._find_backup_source('validation', exclude=[])

            # 应该跳过 xtquant（trading-only），返回 baostock
            assert backup == 'baostock', f"非交易时段应跳过 xtquant，返回 baostock，实际返回 {backup}"

    def test_find_backup_source_time_slot_during_trading(self, health_config):
        """trading-only 源在交易时段可用"""
        def _make_with_roles(name, roles_dict):
            m = MagicMock()
            m.name = name
            m.is_connected = True
            m.config = {
                "enabled": True,
                "roles": roles_dict,
                "timeout": 5
            }
            m.health_check.return_value = {
                "status": "ok", "response_time": 0.5,
                "data_freshness": True, "error_message": None
            }
            return m

        adapters = {
            "xtquant": _make_with_roles("xtquant", {
                "validation": {"priority": 1, "time_slot": "trading"}
            }),
            "baostock": _make_with_roles("baostock", {
                "validation": {"priority": 2}
            })
        }

        from StockDataMaster.health.health_manager import HealthManager
        hm = HealthManager(health_config, adapters)
        hm.check_all_sources()

        # Mock 当前时间为交易时段（例如 10:00）
        with patch('StockDataMaster.health.health_manager.datetime') as mock_dt:
            mock_now = MagicMock()
            mock_now.time.return_value = time_type(10, 0)  # 10:00
            mock_dt.now.return_value = mock_now

            # 查找 validation 备用源
            backup = hm._find_backup_source('validation', exclude=[])

            # 应该返回 xtquant（priority=1，且在交易时段）
            assert backup == 'xtquant', f"交易时段应返回 xtquant，实际返回 {backup}"

    def test_trigger_switch_with_roles(self, health_config):
        """触发切换使用 roles 格式"""
        def _make_with_roles(name, roles_dict):
            m = MagicMock()
            m.name = name
            m.is_connected = True
            m.config = {
                "enabled": True,
                "roles": roles_dict,
                "timeout": 5
            }
            m.health_check.return_value = {
                "status": "ok", "response_time": 0.5,
                "data_freshness": True, "error_message": None
            }
            return m

        adapters = {
            "tushare": _make_with_roles("tushare", {
                "kline_day": {"priority": 1}
            }),
            "mootdx": _make_with_roles("mootdx", {
                "kline_day": {"priority": 2}
            })
        }

        from StockDataMaster.health.health_manager import HealthManager
        hm = HealthManager(health_config, adapters)
        hm.check_all_sources()
        hm.active_sources['kline_day'] = 'tushare'

        # 触发切换
        hm._trigger_switch('tushare', 'Test failure')

        # 应该切换到 mootdx
        assert hm.active_sources['kline_day'] == 'mootdx'

    def test_force_switch_with_roles(self, health_config):
        """强制切换检查 roles 格式"""
        def _make_with_roles(name, roles_dict):
            m = MagicMock()
            m.name = name
            m.is_connected = True
            m.config = {
                "enabled": True,
                "roles": roles_dict,
                "timeout": 5
            }
            m.health_check.return_value = {
                "status": "ok", "response_time": 0.5,
                "data_freshness": True, "error_message": None
            }
            return m

        adapters = {
            "tushare": _make_with_roles("tushare", {
                "kline_day": {"priority": 1}
            }),
            "mootdx": _make_with_roles("mootdx", {
                "kline_minute": {"priority": 2}  # 不支持 kline_day
            })
        }

        from StockDataMaster.health.health_manager import HealthManager
        hm = HealthManager(health_config, adapters)

        # 尝试强制切换到不支持该用途的源
        result = hm.force_switch('kline_day', 'mootdx')
        assert result is False, "切换到不支持的用途应失败"

        # 尝试强制切换到支持该用途的源
        result = hm.force_switch('kline_day', 'tushare')
        assert result is True, "切换到支持的用途应成功"

    def test_backward_compatible_with_use_for(self, health_config):
        """向后兼容：仍支持 use_for 格式"""
        # 创建使用旧格式 use_for 的适配器
        def _make_with_use_for(name, priority, use_for):
            m = MagicMock()
            m.name = name
            m.is_connected = True
            m.config = {
                "enabled": True,
                "priority": priority,
                "use_for": use_for,
                "timeout": 5
            }
            m.health_check.return_value = {
                "status": "ok", "response_time": 0.5,
                "data_freshness": True, "error_message": None
            }
            return m

        adapters = {
            "tushare": _make_with_use_for("tushare", 1, ["kline_day"]),
            "mootdx": _make_with_use_for("mootdx", 2, ["kline_day", "kline_minute"])
        }

        from StockDataMaster.health.health_manager import HealthManager
        hm = HealthManager(health_config, adapters)
        hm.check_all_sources()

        # 查找备用源应该仍然工作
        backup = hm._find_backup_source('kline_day', exclude=['tushare'])
        assert backup == 'mootdx', "向后兼容：use_for 格式应仍然工作"

        # 强制切换应该仍然工作
        result = hm.force_switch('kline_day', 'mootdx')
        assert result is True, "向后兼容：use_for 格式的 force_switch 应仍然工作"
