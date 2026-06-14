"""
test_adapters.py - 适配器单元测试（不需要网络）
覆盖：代码格式转换、频率映射、连接状态、repr 方法
"""

import pytest
import time
from datetime import datetime, timedelta
from unittest.mock import MagicMock, patch

pytestmark = pytest.mark.unit


# ─── Tushare 适配器 ───────────────────────────────────────────────────────────

class TestTushareAdapter:
    """TushareAdapter 单元测试"""

    def _make(self):
        from StockDataMaster.adapters.tushare_adapter import TushareAdapter
        return TushareAdapter("tushare", {"token": "test", "timeout": 10, "use_for": []})

    def test_convert_code_sh(self):
        """上交所代码转换: 600519 → 600519.SH"""
        a = self._make()
        assert a._convert_code("600519") == "600519.SH"

    def test_convert_code_sz(self):
        """深交所代码转换: 000001 → 000001.SZ"""
        a = self._make()
        assert a._convert_code("000001") == "000001.SZ"

    def test_convert_code_with_sh_prefix(self):
        """带 sh. 前缀的代码转换正确"""
        a = self._make()
        assert a._convert_code("sh.600519") == "600519.SH"

    def test_no_token_connect_fails(self):
        """空 Token 时连接应失败"""
        from StockDataMaster.adapters.tushare_adapter import TushareAdapter
        a = TushareAdapter("tushare", {"token": "", "timeout": 10, "use_for": []})
        result = a.connect()
        assert result is False
        assert a.is_connected is False

    def test_freq_map_has_daily(self):
        """频率映射包含日线"""
        from StockDataMaster.adapters.tushare_adapter import TushareAdapter
        assert 'd' in TushareAdapter.FREQ_MAP
        assert 'w' in TushareAdapter.FREQ_MAP

    def test_repr_contains_name(self):
        """repr 输出包含适配器名称"""
        a = self._make()
        assert 'tushare' in repr(a)


# ─── Baostock 适配器 ──────────────────────────────────────────────────────────

class TestBaostockAdapter:
    """BaostockAdapter 单元测试"""

    def _make(self):
        from StockDataMaster.adapters.baostock_adapter import BaostockAdapter
        return BaostockAdapter("baostock", {"timeout": 8, "use_for": []})

    def test_add_prefix_sh(self):
        """上交所代码添加 sh. 前缀"""
        a = self._make()
        assert a._add_bs_prefix("600519") == "sh.600519"

    def test_add_prefix_sz(self):
        """深交所代码添加 sz. 前缀"""
        a = self._make()
        assert a._add_bs_prefix("000001") == "sz.000001"

    def test_freq_map_has_daily(self):
        """频率映射包含日线和5分钟"""
        from StockDataMaster.adapters.baostock_adapter import BaostockAdapter
        assert 'd' in BaostockAdapter.FREQ_MAP
        assert '5m' in BaostockAdapter.FREQ_MAP

    def test_health_check_bypasses_fast_fail_cooldown(self):
        """健康检查应绕过业务快速失败冷却,用于主动探测恢复"""
        a = self._make()
        a.is_connected = True
        a._consecutive_failures = 3
        a._last_failure_time = time.time()

        rs = MagicMock()
        rs.error_code = '0'
        rs.fields = ['date', 'code', 'close', 'volume']
        latest = (datetime.now() - timedelta(days=1)).strftime('%Y-%m-%d')
        rs.next.side_effect = [True, False]
        rs.get_row_data.return_value = [latest, 'sh.600000', '8.88', '1000000']

        with patch('StockDataMaster.adapters.baostock_adapter.bs') as mock_bs:
            mock_bs.query_history_k_data_plus.return_value = rs
            result = a.health_check()

        assert result['status'] == 'ok'
        assert a._consecutive_failures == 0
        mock_bs.query_history_k_data_plus.assert_called_once()

    def test_health_check_records_query_failure(self):
        """健康检查真实查询失败时应记录失败计数和错误信息"""
        a = self._make()
        a.is_connected = True

        rs = MagicMock()
        rs.error_code = '10002007'
        rs.error_msg = '网络接收错误。'

        with patch('StockDataMaster.adapters.baostock_adapter.bs') as mock_bs:
            mock_bs.query_history_k_data_plus.return_value = rs
            result = a.health_check()

        assert result['status'] == 'error'
        assert '网络接收错误' in result['error_message']
        assert a._consecutive_failures == 1


# ─── Mootdx 适配器 ───────────────────────────────────────────────────────────

class TestMootdxAdapter:
    """MootdxAdapter 单元测试"""

    def test_freq_map_complete(self):
        """频率映射包含所有主要周期"""
        from StockDataMaster.adapters.mootdx_adapter import MootdxAdapter
        required_freqs = ['d', '5m', '15m', '30m', '60m']
        for freq in required_freqs:
            assert freq in MootdxAdapter.FREQ_MAP, f"缺少频率: {freq}"

    def test_freq_map_day_value(self):
        """日线频率值正确（mootdx 日线 = 9）"""
        from StockDataMaster.adapters.mootdx_adapter import MootdxAdapter
        assert MootdxAdapter.FREQ_MAP['d'] == 9
