"""
baostock adapter 冒烟测试
获取 10 只代表性股票的日 K 线数据并打印摘要

用法：
  python test/smoke_baostock.py          # 真实连接
  python test/smoke_baostock.py --mock   # mock 模式（无需网络，验证代码逻辑）
"""

import sys
import os
from datetime import date, timedelta
from unittest.mock import MagicMock, patch

# 路径设置
_HERE = os.path.dirname(os.path.abspath(__file__))
_PROJECT = os.path.dirname(_HERE)
_PARENT = os.path.dirname(_PROJECT)
for p in (_PARENT, _PROJECT):
    if p not in sys.path:
        sys.path.insert(0, p)

from StockDataMaster.adapters.baostock_adapter import BaostockAdapter

# 10 只代表性股票：沪深各类别
STOCKS = [
    ("600519", "贵州茅台"),
    ("600000", "浦发银行"),
    ("000001", "平安银行"),
    ("300750", "宁德时代"),
    ("000858", "五粮液"),
    ("601318", "中国平安"),
    ("002415", "海康威视"),
    ("600036", "招商银行"),
    ("000333", "美的集团"),
    ("601166", "兴业银行"),
]

COUNT = 5  # 每只股票取最近 5 条日线


def sep(char="-", n=62):
    print(char * n)


# ---------- mock 构造 ----------

def _make_mock_bs(code_prefix: str, base_price: float):
    """为单只股票构造 mock baostock 返回值"""
    today = date.today()
    rows = []
    for i in range(COUNT):
        d = today - timedelta(days=COUNT - i)
        p = base_price + i * 0.5
        rows.append([
            d.strftime('%Y-%m-%d'),
            code_prefix,
            f"{p:.2f}", f"{p+1:.2f}", f"{p-0.5:.2f}", f"{p+0.3:.2f}",
            f"{p-0.2:.2f}",
            "1000000", "100000000", "0.12", "2",
        ])
    return rows


def _build_mock_bs_module():
    """构造完整的 mock baostock 模块"""
    import pandas as pd

    mock_bs = MagicMock()

    # login 成功
    login_result = MagicMock()
    login_result.error_code = '0'
    login_result.error_msg = 'success'
    mock_bs.login.return_value = login_result

    # query_history_k_data_plus：根据 code 返回对应数据
    prices = {
        'sh.600519': 1800.0, 'sh.600000': 8.5,  'sz.000001': 12.3,
        'sz.300750': 220.0,  'sz.000858': 150.0, 'sh.601318': 45.0,
        'sz.002415': 35.0,   'sh.600036': 38.0,  'sz.000333': 60.0,
        'sh.601166': 18.0,
    }

    fields = ['date', 'code', 'open', 'high', 'low', 'close',
              'preclose', 'volume', 'amount', 'turn', 'adjustflag']

    def query_side_effect(code, field_str, **kwargs):
        rs = MagicMock()
        rs.error_code = '0'
        rs.fields = fields
        price = prices.get(code, 10.0)
        rows = _make_mock_bs(code, price)
        rs.next.side_effect = [True] * len(rows) + [False]
        rs.get_row_data.side_effect = rows
        return rs

    mock_bs.query_history_k_data_plus.side_effect = query_side_effect
    mock_bs.logout.return_value = None
    return mock_bs


# ---------- 测试主逻辑 ----------

def run(use_mock: bool):
    adapter = BaostockAdapter("baostock", {"timeout": 10, "use_for": ["kline_day"]})

    sep("=")
    mode_tag = "[MOCK]" if use_mock else "[实网]"
    print(f"baostock 冒烟测试 {mode_tag}  日线 / 前复权 / 最近 {COUNT} 条")
    sep("=")

    if use_mock:
        mock_bs = _build_mock_bs_module()
        # patch 适配器模块内已绑定的 bs 名称（模块级 import 已完成，sys.modules 无效）
        ctx = patch('StockDataMaster.adapters.baostock_adapter.bs', mock_bs)
        ctx.start()
        adapter.is_connected = True  # 跳过 login 网络调用
    else:
        ctx = None
        print("\n[1] 连接 baostock...")
        ok = adapter.connect()
        if not ok:
            print(f"  连接失败: {adapter.last_error}")
            print("  请检查网络或 baostock 服务 (TCP 10030)")
            return
        print(f"  连接成功\n")

    passed = 0
    failed = 0

    sep()
    print(f"  {'代码':<8} {'名称':<8} {'状态':<6} 详情")
    sep()

    for code, name in STOCKS:
        df = adapter.get_kline(code, freq='d', count=COUNT, adjust='qfq')

        if df is None or df.empty:
            status = "FAIL"
            failed += 1
            detail = f"返回空数据 (last_error={adapter.last_error})"
        else:
            required = ['date', 'open', 'high', 'low', 'close', 'volume']
            missing   = [c for c in required if c not in df.columns]
            price_ok  = (df['close'] > 0).all()
            ohlc_ok   = (df['high'] >= df['low']).all()

            if missing or not price_ok or not ohlc_ok:
                status = "WARN"
                failed += 1
                issues = []
                if missing:      issues.append(f"缺列:{missing}")
                if not price_ok: issues.append("close<=0")
                if not ohlc_ok:  issues.append("high<low")
                detail = " | ".join(issues)
            else:
                status = "PASS"
                passed += 1
                r = df.iloc[-1]
                detail = (f"rows={len(df)}  date={r['date']}  "
                          f"close={r['close']:.2f}  vol={r['volume']:.0f}")

        print(f"  {code:<8} {name:<8} [{status}]  {detail}")

    sep()
    print(f"汇总: {passed}/{len(STOCKS)} PASS  {failed} FAIL\n")

    if use_mock and ctx:
        ctx.stop()
    else:
        adapter.disconnect()

    if failed == 0:
        print("冒烟测试通过")
    else:
        print(f"冒烟测试发现 {failed} 个问题，请检查日志")


if __name__ == "__main__":
    use_mock = "--mock" in sys.argv
    run(use_mock)
