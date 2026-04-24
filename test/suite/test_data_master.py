"""
test_data_master.py - StockDataMaster 核心逻辑单元测试（使用 Mock 适配器）
覆盖：_normalize_code, _is_cache_fresh, _is_date_range_covered,
       get_kline (各种边界), get_health_status, get_cache_statistics, 单例模式
"""

import os
from datetime import date, timedelta

import pytest
import pandas as pd
from unittest.mock import patch, MagicMock

pytestmark = pytest.mark.unit


# ─── 测试：_normalize_code ────────────────────────────────────────────────────

def test_normalize_code_various(dm_with_mocks):
    dm, _, _ = dm_with_mocks
    assert dm._normalize_code("600519") == "600519"
    assert dm._normalize_code("sh.600519") == "600519"
    assert dm._normalize_code("sz.000001") == "000001"


# ─── 测试：_is_cache_fresh ────────────────────────────────────────────────────

def test_is_cache_fresh_historical_end_date(dm_with_mocks):
    """end_date 在今天之前 → 历史数据 → 缓存新鲜"""
    dm, _, _ = dm_with_mocks
    df = pd.DataFrame([{'date': '2024-01-01', 'close': 100.0}])
    yesterday = (date.today() - timedelta(days=1)).strftime('%Y-%m-%d')
    assert dm._is_cache_fresh(df, request_end_date=yesterday) is True


def test_is_cache_fresh_old_cache(dm_with_mocks):
    """缓存最新日期 < 今天 → 历史数据 → 新鲜"""
    dm, _, _ = dm_with_mocks
    old_date = (date.today() - timedelta(days=5)).strftime('%Y-%m-%d')
    df = pd.DataFrame([{'date': old_date, 'close': 100.0}])
    assert dm._is_cache_fresh(df, request_end_date=None) is True


def test_is_cache_fresh_future_date(dm_with_mocks):
    """缓存日期 > 今天 → 异常数据 → 不新鲜"""
    dm, _, _ = dm_with_mocks
    future_date = (date.today() + timedelta(days=1)).strftime('%Y-%m-%d')
    df = pd.DataFrame([{'date': future_date, 'close': 100.0}])
    assert dm._is_cache_fresh(df, request_end_date=None) is False


def test_is_cache_fresh_today_after_close(dm_with_mocks):
    """今日数据 + 盘后时间 (15:30) → 已收盘 → 新鲜"""
    dm, _, _ = dm_with_mocks
    today = date.today().strftime('%Y-%m-%d')
    df = pd.DataFrame([{'date': today, 'close': 100.0}])
    from datetime import datetime
    mock_time = datetime.now().replace(hour=15, minute=30, second=0)
    with patch('StockDataMaster.data_master.datetime') as mock_dt:
        mock_dt.now.return_value = mock_time
        result = dm._is_cache_fresh(df, request_end_date=None)
    assert result is True


def test_is_cache_fresh_today_before_close(dm_with_mocks):
    """今日数据 + 盘中时间 (10:00) → 未收盘 → 不新鲜"""
    dm, _, _ = dm_with_mocks
    today = date.today().strftime('%Y-%m-%d')
    df = pd.DataFrame([{'date': today, 'close': 100.0}])
    from datetime import datetime
    mock_time = datetime.now().replace(hour=10, minute=0, second=0)
    with patch('StockDataMaster.data_master.datetime') as mock_dt:
        mock_dt.now.return_value = mock_time
        result = dm._is_cache_fresh(df, request_end_date=None)
    assert result is False


def test_is_cache_fresh_empty_df(dm_with_mocks):
    """空 DataFrame → False"""
    dm, _, _ = dm_with_mocks
    assert dm._is_cache_fresh(pd.DataFrame()) is False


def test_is_cache_fresh_none(dm_with_mocks):
    """None 输入 → False"""
    dm, _, _ = dm_with_mocks
    assert dm._is_cache_fresh(None) is False


# ─── 测试：_is_date_range_covered ────────────────────────────────────────────

def test_is_date_range_covered_no_filter(dm_with_mocks):
    """无日期过滤 → 完全覆盖"""
    dm, _, _ = dm_with_mocks
    df = pd.DataFrame([{'date': '2024-01-01'}, {'date': '2024-01-10'}])
    assert dm._is_date_range_covered(df, None, None) is True


def test_is_date_range_covered_start_before_cache(dm_with_mocks):
    """请求 start_date 早于缓存最早日期 → 不覆盖"""
    dm, _, _ = dm_with_mocks
    df = pd.DataFrame([{'date': '2024-06-01'}, {'date': '2024-06-10'}])
    assert dm._is_date_range_covered(df, '2024-01-01', None) is False


def test_is_date_range_covered_full_range(dm_with_mocks):
    """缓存完全覆盖请求范围 → 覆盖"""
    dm, _, _ = dm_with_mocks
    df = pd.DataFrame([{'date': '2024-01-01'}, {'date': '2024-12-31'}])
    assert dm._is_date_range_covered(df, '2024-03-01', '2024-06-30') is True


# ─── 测试：get_kline 边界 ─────────────────────────────────────────────────────

def test_get_kline_empty_code(dm_with_mocks):
    """空代码 → None"""
    dm, _, _ = dm_with_mocks
    assert dm.get_kline('', freq='d', count=10) is None


def test_get_kline_zero_count(dm_with_mocks):
    """count=0 → 空 DataFrame"""
    dm, _, _ = dm_with_mocks
    result = dm.get_kline('600519', freq='d', count=0)
    assert result is not None
    assert result.empty


def test_get_kline_negative_count(dm_with_mocks):
    """count<0 → 空 DataFrame"""
    dm, _, _ = dm_with_mocks
    result = dm.get_kline('600519', freq='d', count=-1)
    assert result is not None
    assert result.empty


def test_get_kline_from_mock_source(dm_with_mocks):
    """Mock 数据源返回数据时 get_kline 应成功"""
    dm, mock_tushare, _ = dm_with_mocks
    sample_df = pd.DataFrame([{
        'date': (date.today() - timedelta(days=5)).strftime('%Y-%m-%d'),
        'open': 100.0, 'high': 105.0, 'low': 98.0,
        'close': 102.0, 'volume': 1_000_000.0, 'amount': 102_000_000.0
    }])
    sample_df.attrs['source'] = 'tushare'
    mock_tushare.get_kline.return_value = sample_df
    result = dm.get_kline('600519', freq='d', count=10, use_cache=False)
    assert result is not None


def test_get_kline_all_sources_fail(dm_with_mocks):
    """所有数据源失败 → None"""
    dm, mock_tushare, mock_mootdx = dm_with_mocks
    mock_tushare.get_kline.return_value = None
    mock_mootdx.get_kline.return_value = None
    result = dm.get_kline('600519', freq='d', count=10, use_cache=False)
    assert result is None


def test_get_kline_whitespace_code(dm_with_mocks):
    """空白字符代码 → None"""
    dm, _, _ = dm_with_mocks
    assert dm.get_kline("   ", freq='d', count=10) is None


# ─── 测试：状态查询 ───────────────────────────────────────────────────────────

def test_get_health_status_structure(dm_with_mocks):
    """get_health_status 返回必要字段"""
    dm, _, _ = dm_with_mocks
    status = dm.get_health_status()
    assert 'timestamp' in status
    assert 'sources' in status
    assert 'active_sources' in status


def test_get_cache_statistics(dm_with_mocks):
    """get_cache_statistics 返回 enabled 字段"""
    dm, _, _ = dm_with_mocks
    stats = dm.get_cache_statistics()
    assert 'enabled' in stats


def test_close_no_exception(dm_with_mocks):
    """close() 不应抛出异常"""
    dm, _, _ = dm_with_mocks
    dm.close()  # 如果抛出异常，测试失败


# ─── 测试：单例模式 ───────────────────────────────────────────────────────────

def test_singleton_behavior(tmp_path):
    """同一进程中多次实例化返回同一对象"""
    import json, tempfile
    from unittest.mock import patch

    db_path = str(tmp_path / "singleton_test.db").replace("\\", "/")
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
    tmp_cfg = tempfile.NamedTemporaryFile(
        mode='w', suffix='.json', delete=False, encoding='utf-8'
    )
    json.dump(config_data, tmp_cfg)
    tmp_cfg.close()

    mock_mootdx = MagicMock()
    mock_mootdx.connect.return_value = True
    mock_mootdx.is_connected = True
    mock_mootdx.name = "mootdx"
    mock_mootdx.config = {"enabled": True, "priority": 2,
                           "use_for": ["kline_day"], "timeout": 5}

    with patch('StockDataMaster.adapters.AdapterFactory.create_adapter',
               return_value=mock_mootdx):
        from StockDataMaster.data_master import StockDataMaster
        dm1 = StockDataMaster(config_path=tmp_cfg.name)
        dm2 = StockDataMaster()  # 不传参，应返回同一实例

    os.unlink(tmp_cfg.name)
    assert dm1 is dm2, "单例模式应返回同一实例"


# ─── 测试：时段判断 ────────────────────────────────────────────────────────────

class TestTimeSlot:
    """时段判断测试"""

    def test_trading_hours_morning(self):
        """09:15-15:00 为交易时段"""
        from StockDataMaster.data_master import StockDataMaster
        dm = StockDataMaster.__new__(StockDataMaster)
        dm._initialized = False
        from datetime import time as time_type
        test_time = time_type(10, 0)
        assert dm._get_time_slot(test_time) == 'trading'

    def test_after_hours_evening(self):
        """16:00 为盘后时段"""
        from StockDataMaster.data_master import StockDataMaster
        dm = StockDataMaster.__new__(StockDataMaster)
        dm._initialized = False
        from datetime import time as time_type
        test_time = time_type(16, 0)
        assert dm._get_time_slot(test_time) == 'after_hours'

    def test_after_hours_before_market(self):
        """08:00 为盘后时段"""
        from StockDataMaster.data_master import StockDataMaster
        dm = StockDataMaster.__new__(StockDataMaster)
        dm._initialized = False
        from datetime import time as time_type
        test_time = time_type(8, 0)
        assert dm._get_time_slot(test_time) == 'after_hours'

    def test_boundary_915(self):
        """09:15 恰好为交易时段"""
        from StockDataMaster.data_master import StockDataMaster
        dm = StockDataMaster.__new__(StockDataMaster)
        dm._initialized = False
        from datetime import time as time_type
        test_time = time_type(9, 15)
        assert dm._get_time_slot(test_time) == 'trading'

    def test_boundary_1500(self):
        """15:00 恰好为交易时段"""
        from StockDataMaster.data_master import StockDataMaster
        dm = StockDataMaster.__new__(StockDataMaster)
        dm._initialized = False
        from datetime import time as time_type
        test_time = time_type(15, 0)
        assert dm._get_time_slot(test_time) == 'trading'

    def test_boundary_1501(self):
        """15:01 为盘后时段"""
        from StockDataMaster.data_master import StockDataMaster
        dm = StockDataMaster.__new__(StockDataMaster)
        dm._initialized = False
        from datetime import time as time_type
        test_time = time_type(15, 1)
        assert dm._get_time_slot(test_time) == 'after_hours'


# ─── 测试：_try_cache_kline 投票机制 ──────────────────────────────────────────

def test_try_cache_kline_voting_pass(dm_with_mocks):
    """两个校验源一致,投票通过"""
    dm, mock_tushare, mock_mootdx = dm_with_mocks

    # 准备主数据
    primary_df = pd.DataFrame([
        {'date': '2024-01-01', 'open': 100.0, 'high': 105.0, 'low': 99.0, 'close': 103.0, 'volume': 1000, 'amount': 100000},
        {'date': '2024-01-02', 'open': 103.0, 'high': 108.0, 'low': 102.0, 'close': 107.0, 'volume': 1200, 'amount': 120000}
    ])
    # 设置 source 属性
    primary_df.attrs['source'] = 'tushare'

    # Mock 主数据源返回
    mock_tushare.get_kline.return_value = primary_df.copy()

    # Mock 校验源返回一致数据
    mock_mootdx.get_kline.return_value = primary_df.copy()

    # Mock config.get_sources_by_role 返回校验源列表
    with patch.object(dm.config, 'get_sources_by_role', return_value=['mootdx', 'baostock', 'xtquant']):
        # Mock baostock adapter
        mock_baostock = MagicMock()
        mock_baostock.is_connected = True
        mock_baostock.get_kline.return_value = primary_df.copy()
        dm.adapters['baostock'] = mock_baostock

        # Mock xtquant adapter
        mock_xtquant = MagicMock()
        mock_xtquant.is_connected = True
        mock_xtquant.get_kline.return_value = primary_df.copy()
        dm.adapters['xtquant'] = mock_xtquant

        # Mock validate_and_cache_voting 方法
        with patch.object(dm.cache_manager, 'validate_and_cache_voting', return_value=primary_df.copy()) as mock_voting:
            # 调用 _try_cache_kline（签名：code, df, start_date, end_date, count, adjust）
            dm._try_cache_kline('600519', primary_df.copy(), '2024-01-01', '2024-01-02', None, 'qfq')

            # 验证调用了 validate_and_cache_voting
            assert mock_voting.called, "应该调用 validate_and_cache_voting"
            call_args = mock_voting.call_args
            assert call_args[1]['code'] == '600519'
            assert call_args[1]['primary_source'] == 'tushare'
            # 验证 validation_dfs 包含多个源
            validation_dfs = call_args[1]['validation_dfs']
            assert len(validation_dfs) >= 2, "应该有至少2个校验源"


def test_try_cache_kline_voting_fail(dm_with_mocks):
    """所有校验源不一致,投票失败"""
    dm, mock_tushare, mock_mootdx = dm_with_mocks

    # 准备主数据
    primary_df = pd.DataFrame([
        {'date': '2024-01-01', 'open': 100.0, 'high': 105.0, 'low': 99.0, 'close': 103.0, 'volume': 1000, 'amount': 100000}
    ])

    # Mock 主数据源返回
    mock_tushare.get_kline.return_value = primary_df.copy()

    # Mock 校验源返回不一致数据(价格差异超过容差)
    inconsistent_df = pd.DataFrame([
        {'date': '2024-01-01', 'open': 200.0, 'high': 205.0, 'low': 199.0, 'close': 203.0, 'volume': 1000, 'amount': 100000}
    ])
    mock_mootdx.get_kline.return_value = inconsistent_df.copy()

    # Mock config.get_sources_by_role 返回校验源列表
    with patch.object(dm.config, 'get_sources_by_role', return_value=['mootdx', 'baostock']):
        # Mock baostock adapter
        mock_baostock = MagicMock()
        mock_baostock.is_connected = True
        mock_baostock.get_kline.return_value = inconsistent_df.copy()
        dm.adapters['baostock'] = mock_baostock

        # Mock validate_and_cache_voting 返回 None（投票失败）
        with patch.object(dm.cache_manager, 'validate_and_cache_voting', return_value=None) as mock_voting:
            # 调用 _try_cache_kline
            dm._try_cache_kline('600519', primary_df.copy(), '2024-01-01', '2024-01-01', None, 'qfq')

            # 验证调用了 validate_and_cache_voting
            assert mock_voting.called, "应该调用 validate_and_cache_voting"


def test_try_cache_kline_voting_single_source(dm_with_mocks):
    """只有一个校验源可用,降级为二选一"""
    dm, mock_tushare, mock_mootdx = dm_with_mocks

    # 准备主数据
    primary_df = pd.DataFrame([
        {'date': '2024-01-01', 'open': 100.0, 'high': 105.0, 'low': 99.0, 'close': 103.0, 'volume': 1000, 'amount': 100000}
    ])

    # Mock 主数据源返回
    mock_tushare.get_kline.return_value = primary_df.copy()

    # Mock 只有一个校验源返回数据
    mock_mootdx.get_kline.return_value = primary_df.copy()

    # Mock config.get_sources_by_role 返回校验源列表
    with patch.object(dm.config, 'get_sources_by_role', return_value=['mootdx']):
        # Mock validate_and_cache_voting 方法（会降级为 validate_and_cache）
        with patch.object(dm.cache_manager, 'validate_and_cache_voting', return_value=primary_df.copy()) as mock_voting:
            # 调用 _try_cache_kline
            dm._try_cache_kline('600519', primary_df.copy(), '2024-01-01', '2024-01-01', None, 'qfq')

            # 验证调用了 validate_and_cache_voting
            assert mock_voting.called, "应该调用 validate_and_cache_voting"
            call_args = mock_voting.call_args
            # 验证只有一个校验源
            validation_dfs = call_args[1]['validation_dfs']
            assert len(validation_dfs) == 1, "应该只有1个校验源"


# ─── 测试：get_stock_name 三级查找 ────────────────────────────────────────────

class TestGetStockName:
    """get_stock_name 三级查找测试"""

    def test_l1_memory_cache_hit(self, dm_with_mocks):
        """L1 内存缓存命中"""
        dm, _, _ = dm_with_mocks
        # 预填充内存缓存
        dm._stock_name_cache['600519'] = '贵州茅台'

        # 调用 get_stock_name 应直接返回缓存值
        result = dm.get_stock_name('600519')
        assert result == '贵州茅台'

        # 测试不同格式都能命中缓存
        result = dm.get_stock_name('sh.600519')
        assert result == '贵州茅台'

        result = dm.get_stock_name('600519.SH')
        assert result == '贵州茅台'

    def test_l2_xtquant_lookup(self, dm_with_mocks):
        """L2 xtquant 查找成功"""
        dm, _, _ = dm_with_mocks

        # Mock xtquant adapter
        mock_xtquant = MagicMock()
        mock_xtquant.is_connected = True
        mock_xtquant.get_stock_name.return_value = '平安银行'
        dm.adapters['xtquant'] = mock_xtquant

        # 调用 get_stock_name
        result = dm.get_stock_name('000001')

        # 验证返回值
        assert result == '平安银行'

        # 验证缓存写入
        assert dm._stock_name_cache.get('000001') == '平安银行'

        # 验证调用了 xtquant
        mock_xtquant.get_stock_name.assert_called_once()

    def test_l3_baostock_fallback(self, dm_with_mocks):
        """L3 baostock 兜底查找"""
        dm, _, _ = dm_with_mocks

        # Mock xtquant 不可用
        mock_xtquant = MagicMock()
        mock_xtquant.is_connected = False
        dm.adapters['xtquant'] = mock_xtquant

        # Mock baostock adapter (确保 adapters 里有)
        mock_baostock = MagicMock()
        dm.adapters['baostock'] = mock_baostock

        # Mock baostock 模块
        mock_bs = MagicMock()
        mock_login_result = MagicMock()
        mock_login_result.error_code = '0'
        mock_bs.login.return_value = mock_login_result

        mock_rs = MagicMock()
        mock_rs.error_code = '0'
        mock_rs.next.side_effect = [True, False]
        mock_rs.get_row_data.return_value = ['sh.600519', '贵州茅台', 'other', 'fields']
        mock_bs.query_stock_basic.return_value = mock_rs

        with patch.dict('sys.modules', {'baostock': mock_bs}):
            result = dm.get_stock_name('600519')

            # 验证返回值
            assert result == '贵州茅台'

            # 验证缓存写入
            assert dm._stock_name_cache.get('600519') == '贵州茅台'

    def test_all_fail_returns_code(self, dm_with_mocks):
        """所有级别失败返回代码本身"""
        dm, _, _ = dm_with_mocks

        # Mock xtquant 不可用
        mock_xtquant = MagicMock()
        mock_xtquant.is_connected = False
        dm.adapters['xtquant'] = mock_xtquant

        # Mock baostock 模块（查询失败）
        mock_bs = MagicMock()
        mock_login_result = MagicMock()
        mock_login_result.error_code = '0'
        mock_bs.login.return_value = mock_login_result

        mock_rs = MagicMock()
        mock_rs.error_code = '1'  # 错误码
        mock_bs.query_stock_basic.return_value = mock_rs

        with patch.dict('sys.modules', {'baostock': mock_bs}):
            result = dm.get_stock_name('600519')

            # 应返回代码本身
            assert result == '600519'

    def test_code_format_normalization(self, dm_with_mocks):
        """代码格式标准化"""
        dm, _, _ = dm_with_mocks

        # 预填充缓存
        dm._stock_name_cache['600519'] = '贵州茅台'

        # 测试各种格式都能正确处理
        assert dm.get_stock_name('600519') == '贵州茅台'
        assert dm.get_stock_name('sh.600519') == '贵州茅台'
        assert dm.get_stock_name('600519.SH') == '贵州茅台'
        assert dm.get_stock_name('SH.600519') == '贵州茅台'  # 大写前缀

    def test_baostock_cooldown(self, dm_with_mocks):
        """baostock 冷却机制"""
        dm, _, _ = dm_with_mocks

        # Mock xtquant 不可用
        mock_xtquant = MagicMock()
        mock_xtquant.is_connected = False
        dm.adapters['xtquant'] = mock_xtquant

        # Mock baostock adapter
        mock_baostock = MagicMock()
        dm.adapters['baostock'] = mock_baostock

        # Mock baostock 模块（连续失败）
        mock_bs = MagicMock()
        mock_login_result = MagicMock()
        mock_login_result.error_code = '0'
        mock_bs.login.return_value = mock_login_result

        mock_rs = MagicMock()
        mock_rs.error_code = '1'  # 失败
        mock_bs.query_stock_basic.return_value = mock_rs

        with patch.dict('sys.modules', {'baostock': mock_bs}):
            # 连续失败 3 次
            for i in range(3):
                result = dm.get_stock_name(f'60051{i}')
                assert result == f'60051{i}'  # 返回代码本身

            # 验证失败计数
            assert dm._baostock_consecutive_failures == 3

            # 验证进入冷却期
            import time
            assert dm._baostock_cooldown_until > time.time()

            # 记录当前 query_stock_basic 调用次数
            call_count_before = mock_bs.query_stock_basic.call_count

            # 冷却期内再次调用，应跳过 baostock
            result = dm.get_stock_name('600519')
            assert result == '600519'

            # 验证 baostock 没有被调用（因为在冷却期）
            assert mock_bs.query_stock_basic.call_count == call_count_before

    def test_baostock_cooldown_reset_on_success(self, dm_with_mocks):
        """baostock 成功后重置失败计数"""
        dm, _, _ = dm_with_mocks

        # Mock xtquant 不可用
        mock_xtquant = MagicMock()
        mock_xtquant.is_connected = False
        dm.adapters['xtquant'] = mock_xtquant

        # Mock baostock adapter
        mock_baostock = MagicMock()
        dm.adapters['baostock'] = mock_baostock

        # 先失败 2 次
        mock_bs = MagicMock()
        mock_login_result = MagicMock()
        mock_login_result.error_code = '0'
        mock_bs.login.return_value = mock_login_result

        mock_rs_fail = MagicMock()
        mock_rs_fail.error_code = '1'
        mock_bs.query_stock_basic.return_value = mock_rs_fail

        with patch.dict('sys.modules', {'baostock': mock_bs}):
            dm.get_stock_name('600510')
            dm.get_stock_name('600511')
            assert dm._baostock_consecutive_failures == 2

            # 第 3 次成功
            mock_rs_success = MagicMock()
            mock_rs_success.error_code = '0'
            mock_rs_success.next.side_effect = [True, False]
            mock_rs_success.get_row_data.return_value = ['sh.600519', '贵州茅台']
            mock_bs.query_stock_basic.return_value = mock_rs_success

            result = dm.get_stock_name('600519')
            assert result == '贵州茅台'

            # 验证失败计数被重置
            assert dm._baostock_consecutive_failures == 0
