"""
conftest.py - pytest 共享 Fixture 和配置

提供全局可用的 Fixture：
- path_setup: 自动将项目路径加入 sys.path (session级)
- suppress_loggers: 抑制测试期间的无关日志 (session级)
- reset_singletons: 每个测试前后重置 DataMaster/Config 单例 (function级)
- temp_cache_config: 带临时SQLite数据库的Config对象
- sample_kline_df: 标准K线测试数据
- mock_adapter_pair: Mock适配器对(tushare + mootdx)
"""

import sys
import os
import json
import logging
import tempfile
import shutil
from datetime import date, timedelta

import pytest
import pandas as pd
from unittest.mock import MagicMock

# ─── 路径设置 ───────────────────────────────────────────────────────────────
# test/suite/ → test/ → StockDataMaster/ → 父目录(包含StockDataMaster包)
_SUITE_DIR = os.path.dirname(os.path.abspath(__file__))
_TEST_DIR = os.path.dirname(_SUITE_DIR)
_PROJECT_ROOT = os.path.dirname(_TEST_DIR)
_PARENT_DIR = os.path.dirname(_PROJECT_ROOT)

# 确保可以 import StockDataMaster
if _PARENT_DIR not in sys.path:
    sys.path.insert(0, _PARENT_DIR)

# 将项目根目录也加入路径（某些相对导入需要）
if _PROJECT_ROOT not in sys.path:
    sys.path.insert(0, _PROJECT_ROOT)

# 暴露给测试模块使用
PROJECT_ROOT = _PROJECT_ROOT
TEST_DIR = _TEST_DIR


# ─── Session 级 Fixture ─────────────────────────────────────────────────────

@pytest.fixture(scope="session", autouse=True)
def suppress_loggers():
    """抑制测试期间的无关日志输出"""
    loggers_to_suppress = [
        "StockDataMaster",
        "DataMaster",
        "DataMaster.HealthManager",
        "DataMaster.CacheManager",
        "baostock",
        "mootdx",
        "urllib3",
        "requests",
    ]
    for name in loggers_to_suppress:
        logging.getLogger(name).setLevel(logging.CRITICAL)
    yield


# ─── Function 级 Fixture ─────────────────────────────────────────────────────

@pytest.fixture(autouse=True)
def reset_singletons():
    """
    每个测试前后重置 DataMaster 和 Config 单例。
    这是测试隔离的关键，防止单例状态污染。
    """
    # 测试前重置
    _reset()
    yield
    # 测试后重置（清理）
    _reset()


def _reset():
    """重置所有单例状态"""
    try:
        import StockDataMaster.data_master as dm_mod
        dm_mod.StockDataMaster._instance = None
    except Exception:
        pass
    try:
        import StockDataMaster.config as cfg_mod
        cfg_mod._global_config = None
    except Exception:
        pass


# ─── 配置相关 Fixture ────────────────────────────────────────────────────────

# 标准测试配置数据（禁用健康检测，使用内存友好设置）
BASE_CONFIG = {
    "use_builtin_libs": True,
    "data_sources": {
        "tushare": {
            "enabled": True,
            "priority": 1,
            "token": "test_token_for_testing",
            "use_for": ["kline_day"],
            "timeout": 10,
            "retry_times": 2,
            "roles": {
                "kline_day": {"priority": 1},
                "valuation": {"priority": 1}
            }
        },
        "mootdx": {
            "enabled": True,
            "priority": 2,
            "use_for": ["kline_day", "kline_minute"],
            "timeout": 5,
            "retry_times": 3,
            "roles": {
                "kline_minute": {"priority": 2},
                "kline_day": {"priority": 2},
                "validation": {"priority": 3}
            }
        },
        "baostock": {
            "enabled": True,
            "priority": 3,
            "use_for": ["kline_day", "valuation"],
            "timeout": 8,
            "retry_times": 3,
            "roles": {
                "kline_day": {"priority": 3},
                "kline_minute": {"priority": 3},
                "validation": {"priority": 2}
            }
        },
        "xtquant": {
            "enabled": True,
            "priority": 1,
            "use_for": ["tick"],
            "timeout": 5,
            "retry_times": 2,
            "roles": {
                "tick": {"priority": 1},
                "kline_minute": {"priority": 1},
                "validation": {"priority": 1, "time_slot": "trading"}
            }
        }
    },
    "validation": {
        "mode": "voting",
        "quorum": 2,
        "strategy": "first_to_quorum",
        "sources": ["xtquant", "baostock", "mootdx"],
        "price_tolerance_abs": 0.01,
        "price_tolerance_pct": 0.005,
        "volume_tolerance_pct": 0.05,
        "min_pass_rate": 0.8,
        "skip_today_in_trading_hours": True
    },
    "stock_name": {
        "cache_enabled": True,
        "cleanup_day": 5,
        "baostock_max_consecutive_failures": 3,
        "baostock_retry_cooldown": 300
    },
    "cache": {
        "enabled": True,
        "db_path": "cache/test.db",  # 将被 temp_cache_config 覆盖
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
    "health_check": {
        "enabled": False,
        "interval_seconds": 60,
        "response_time_threshold": 5.0,
        "consecutive_failures_threshold": 3,
        "data_freshness_days": 3
    },
    "hot_switch": {
        "enabled": False,
        "switch_notification": False
    },
    "logging": {
        "level": "WARNING",
        "file": None
    }
}


@pytest.fixture
def temp_dir(tmp_path):
    """提供临时目录路径（pytest内置tmp_path的别名）"""
    return str(tmp_path)


@pytest.fixture
def temp_cache_config(tmp_path):
    """
    创建带临时SQLite数据库的Config对象。
    每个测试获得独立的数据库，完全隔离。
    """
    from StockDataMaster.config import Config

    db_path = str(tmp_path / "test_cache.db").replace("\\", "/")
    config_data = {**BASE_CONFIG}
    config_data["cache"] = {**BASE_CONFIG["cache"], "db_path": db_path}

    tmp_cfg = tempfile.NamedTemporaryFile(
        mode='w', suffix='.json', delete=False, encoding='utf-8'
    )
    json.dump(config_data, tmp_cfg)
    tmp_cfg.close()

    config = Config(tmp_cfg.name)
    os.unlink(tmp_cfg.name)
    return config


@pytest.fixture
def minimal_config(tmp_path):
    """最小化配置（仅cache，禁用所有数据源和健康检测）"""
    from StockDataMaster.config import Config

    db_path = str(tmp_path / "minimal.db").replace("\\", "/")
    config_data = {
        "cache": {
            "enabled": True,
            "db_path": db_path,
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
    tmp_cfg = tempfile.NamedTemporaryFile(
        mode='w', suffix='.json', delete=False, encoding='utf-8'
    )
    json.dump(config_data, tmp_cfg)
    tmp_cfg.close()
    config = Config(tmp_cfg.name)
    os.unlink(tmp_cfg.name)
    return config


@pytest.fixture
def health_config():
    """用于 HealthManager 测试的Config（启用多数据源）"""
    from StockDataMaster.config import Config

    config_data = {
        "data_sources": {
            "tushare": {
                "enabled": True, "priority": 1,
                "use_for": ["kline_day"], "timeout": 10
            },
            "mootdx": {
                "enabled": True, "priority": 2,
                "use_for": ["kline_day", "kline_minute"], "timeout": 5
            },
            "baostock": {
                "enabled": True, "priority": 3,
                "use_for": ["kline_day", "valuation"], "timeout": 8
            },
        },
        "cache": {
            "enabled": False, "max_days_per_stock": 120,
            "stock_name_expire_days": 30, "stock_name_cleanup_day": 0,
            "stock_name_skip_expiration_check": True,
            "validation": {
                "price_tolerance_abs": 0.01, "price_tolerance_pct": 0.005,
                "volume_tolerance_pct": 0.05
            }
        },
        "health_check": {
            "enabled": True, "interval_seconds": 60,
            "response_time_threshold": 5.0, "consecutive_failures_threshold": 3,
            "data_freshness_days": 3
        },
        "hot_switch": {"enabled": True, "switch_notification": False},
    }
    tmp = tempfile.NamedTemporaryFile(
        mode='w', suffix='.json', delete=False, encoding='utf-8'
    )
    json.dump(config_data, tmp)
    tmp.close()
    config = Config(tmp.name)
    os.unlink(tmp.name)
    return config


# ─── 数据 Fixture ────────────────────────────────────────────────────────────

@pytest.fixture
def sample_kline_df():
    """
    标准测试用K线DataFrame（5条历史记录，避免今日数据缓存问题）。
    日期范围：10天前 ~ 6天前
    """
    today = date.today()
    rows = []
    for i in range(5):
        d = today - timedelta(days=10 - i)
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


@pytest.fixture
def large_kline_df():
    """较大的K线DataFrame（10条记录）"""
    today = date.today()
    rows = []
    for i in range(10):
        d = today - timedelta(days=15 - i)
        rows.append({
            'date': d.strftime('%Y-%m-%d'),
            'open': 100.0 + i,
            'high': 106.0 + i,
            'low': 97.0 + i,
            'close': 103.0 + i,
            'volume': 1_500_000.0 + i * 100,
            'amount': 154_500_000.0 + i * 10_000
        })
    return pd.DataFrame(rows)


# ─── 适配器 Mock Fixture ──────────────────────────────────────────────────────

@pytest.fixture
def mock_tushare():
    """Mock Tushare 适配器"""
    m = MagicMock()
    m.name = "tushare"
    m.is_connected = True
    m.connect.return_value = True
    m.config = {
        "enabled": True, "priority": 1,
        "use_for": ["kline_day"], "timeout": 10
    }
    m.health_check.return_value = {
        "status": "ok", "response_time": 0.5,
        "data_freshness": True, "error_message": None
    }
    return m


@pytest.fixture
def mock_mootdx():
    """Mock Mootdx 适配器"""
    m = MagicMock()
    m.name = "mootdx"
    m.is_connected = True
    m.connect.return_value = True
    m.config = {
        "enabled": True, "priority": 2,
        "use_for": ["kline_day", "kline_minute"], "timeout": 5
    }
    m.health_check.return_value = {
        "status": "ok", "response_time": 0.3,
        "data_freshness": True, "error_message": None
    }
    return m


@pytest.fixture
def mock_baostock():
    """Mock Baostock 适配器"""
    m = MagicMock()
    m.name = "baostock"
    m.is_connected = True
    m.connect.return_value = True
    m.config = {
        "enabled": True, "priority": 3,
        "use_for": ["kline_day", "valuation"], "timeout": 8
    }
    m.health_check.return_value = {
        "status": "ok", "response_time": 1.0,
        "data_freshness": True, "error_message": None
    }
    return m


@pytest.fixture
def mock_adapters(mock_tushare, mock_mootdx, mock_baostock):
    """包含三个Mock适配器的字典"""
    return {
        "tushare": mock_tushare,
        "mootdx": mock_mootdx,
        "baostock": mock_baostock,
    }


# ─── DataMaster Mock Fixture ──────────────────────────────────────────────────

@pytest.fixture
def dm_with_mocks(tmp_path, mock_tushare, mock_mootdx):
    """
    创建带 Mock 适配器的 DataMaster 实例。
    自动管理生命周期（测试结束后 close）。
    """
    from unittest.mock import patch

    db_path = str(tmp_path / "dm_test.db").replace("\\", "/")
    config_data = {
        "use_builtin_libs": True,
        "data_sources": {
            "tushare": {
                "enabled": True, "priority": 1, "token": "mock_token",
                "use_for": ["kline_day"], "timeout": 10, "retry_times": 2
            },
            "mootdx": {
                "enabled": True, "priority": 2,
                "use_for": ["kline_day", "kline_minute"],
                "timeout": 5, "retry_times": 3
            }
        },
        "cache": {
            "enabled": True, "db_path": db_path,
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

    tmp_cfg = tempfile.NamedTemporaryFile(
        mode='w', suffix='.json', delete=False, encoding='utf-8'
    )
    json.dump(config_data, tmp_cfg)
    tmp_cfg.close()

    def factory_side_effect(name, cfg):
        if name == 'tushare':
            return mock_tushare
        elif name == 'mootdx':
            return mock_mootdx
        raise ValueError(f"Unexpected adapter: {name}")

    with patch('StockDataMaster.adapters.AdapterFactory.create_adapter') as mock_factory:
        mock_factory.side_effect = factory_side_effect
        from StockDataMaster.data_master import StockDataMaster
        dm = StockDataMaster(config_path=tmp_cfg.name)

    os.unlink(tmp_cfg.name)
    yield dm, mock_tushare, mock_mootdx

    # 清理
    try:
        dm.close()
    except Exception:
        pass
    _reset()
