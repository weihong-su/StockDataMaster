"""
test_base_adapter.py - DataSourceAdapter 基类方法单元测试
覆盖：normalize_code(), add_prefix(), standardize_dataframe(), 初始状态
"""

import pytest
import pandas as pd

pytestmark = pytest.mark.unit


# ─── 辅助：最小化实体适配器 ──────────────────────────────────────────────────

def make_adapter(name="test", config=None):
    from StockDataMaster.adapters.base_adapter import DataSourceAdapter

    class DummyAdapter(DataSourceAdapter):
        def connect(self): return True
        def disconnect(self): pass
        def get_kline(self, *a, **kw): return None
        def get_valuation(self, *a, **kw): return None
        def get_tick(self, *a, **kw): return None

    cfg = config or {"timeout": 5, "use_for": ["kline_day"]}
    return DummyAdapter(name, cfg)


# ─── 测试：normalize_code ─────────────────────────────────────────────────────

def test_normalize_code_clean():
    """无前缀代码原样返回"""
    a = make_adapter()
    assert a.normalize_code("600519") == "600519"


def test_normalize_code_sh_prefix():
    """sh. 前缀被去除"""
    a = make_adapter()
    assert a.normalize_code("sh.600519") == "600519"


def test_normalize_code_sz_prefix():
    """sz. 前缀被去除"""
    a = make_adapter()
    assert a.normalize_code("sz.000001") == "000001"


# ─── 测试：add_prefix ────────────────────────────────────────────────────────

def test_add_prefix_sh():
    """上交所股票（6xx）添加 sh. 前缀"""
    a = make_adapter()
    assert a.add_prefix("600519") == "sh.600519"


def test_add_prefix_sz():
    """深交所主板（0xx）添加 sz. 前缀"""
    a = make_adapter()
    assert a.add_prefix("000001") == "sz.000001"


def test_add_prefix_gem():
    """创业板（3xx）添加 sz. 前缀"""
    a = make_adapter()
    assert a.add_prefix("300001") == "sz.300001"


# ─── 测试：standardize_dataframe ─────────────────────────────────────────────

def test_standardize_dataframe_rename():
    """常见列名被标准化重命名"""
    a = make_adapter()
    df = pd.DataFrame({
        'datetime': ['2024-01-01'],
        'vol': [1000],
        'trade': [5_000_000],
        'close': [100.0]
    })
    result = a.standardize_dataframe(df)
    assert 'date' in result.columns, "datetime 应重命名为 date"
    assert 'volume' in result.columns, "vol 应重命名为 volume"
    assert 'amount' in result.columns, "trade 应重命名为 amount"


def test_standardize_dataframe_date_format():
    """YYYYMMDD 格式日期被转换为 YYYY-MM-DD"""
    a = make_adapter()
    df = pd.DataFrame({'date': ['20240101'], 'close': [100.0]})
    result = a.standardize_dataframe(df)
    assert result['date'].iloc[0] == '2024-01-01'


def test_standardize_empty_dataframe():
    """空 DataFrame 处理后仍为空"""
    a = make_adapter()
    result = a.standardize_dataframe(pd.DataFrame())
    assert result.empty


# ─── 测试：初始状态 ───────────────────────────────────────────────────────────

def test_initial_state():
    """适配器初始状态：未连接、无错误、error_count=0"""
    a = make_adapter()
    assert a.is_connected is False
    assert a.last_error is None
    assert a.error_count == 0
