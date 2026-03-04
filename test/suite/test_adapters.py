"""
test_adapters.py - 适配器单元测试（不需要网络）
覆盖：代码格式转换、频率映射、连接状态、repr 方法
"""

import pytest

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
