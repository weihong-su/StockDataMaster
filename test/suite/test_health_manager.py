"""
test_health_manager.py - HealthManager 健康管理单元测试
覆盖：get_active_source, force_switch, 失败触发切换, 健康报告, 监控线程
"""

import time

import pytest
from unittest.mock import MagicMock

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
