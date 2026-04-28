"""
鲁棒性验证脚本 - 验证数据源优先级配置

测试场景：
1. 日K线数据源fallback链
2. 实时Tick数据源fallback链
3. 股票名称获取fallback链
4. 数据校验源配置

用法：
  python test/validate_robustness.py
"""

import sys
import os
from datetime import date, timedelta

# 路径设置
_HERE = os.path.dirname(os.path.abspath(__file__))
_PROJECT = os.path.dirname(_HERE)
_PARENT = os.path.dirname(_PROJECT)
for p in (_PARENT, _PROJECT):
    if p not in sys.path:
        sys.path.insert(0, p)

from StockDataMaster.config import Config


def sep(char="-", n=80):
    print(char * n)


def test_kline_day_priority():
    """测试日K线数据源优先级"""
    print("\n=== 1. 日K线数据源优先级 ===")
    config = Config("config.json")
    sources = config.get_sources_by_role("kline_day")

    print(f"  优先级顺序: {' -> '.join(sources)}")

    expected = ["tushare", "baostock", "mootdx", "xtquant"]
    actual = sources

    if actual == expected:
        print("  ✅ PASS: 优先级正确")
        print("     - tushare (P1): 付费用户首选")
        print("     - baostock (P2): 免费兜底，复权准确")
        print("     - mootdx (P3): 速度备用")
        print("     - xtquant (P4): QMT用户补充")
    else:
        print(f"  ❌ FAIL: 期望 {expected}, 实际 {actual}")

    return actual == expected


def test_tick_priority():
    """测试实时Tick数据源优先级"""
    print("\n=== 2. 实时Tick数据源优先级 ===")
    config = Config("config.json")
    sources = config.get_sources_by_role("tick")

    print(f"  优先级顺序: {' -> '.join(sources)}")

    expected = ["xtquant", "mootdx"]
    actual = sources

    if actual == expected:
        print("  ✅ PASS: 优先级正确")
        print("     - xtquant (P1): 真实tick")
        print("     - mootdx (P2): 5分钟模拟")
    else:
        print(f"  ❌ FAIL: 期望 {expected}, 实际 {actual}")

    return actual == expected


def test_validation_sources():
    """测试数据校验源配置"""
    print("\n=== 3. 数据校验源配置 ===")
    config = Config("config.json")
    validation_config = config.get("validation", {})

    sources = validation_config.get("sources", [])
    quorum = validation_config.get("quorum", 1)

    print(f"  校验源: {sources}")
    print(f"  法定人数: {quorum}")

    expected_sources = ["xtquant", "baostock"]
    expected_quorum = 1

    if sources == expected_sources and quorum == expected_quorum:
        print("  ✅ PASS: 校验配置正确")
        print("     - xtquant: 交易时段优先(50ms,快速短路)")
        print("     - baostock: 兜底校验源(2-3s,免费权威)")
        print("     - quorum=1: 串行短路,第一个通过即返回")
    else:
        print(f"  ❌ FAIL: 期望 sources={expected_sources}, quorum={expected_quorum}")
        print(f"          实际 sources={sources}, quorum={quorum}")

    return sources == expected_sources and quorum == expected_quorum


def test_stock_name_priority():
    """测试股票名称获取优先级"""
    print("\n=== 4. 股票名称获取优先级 ===")
    config = Config("config.json")
    sources = config.get_sources_by_role("stock_name")

    print(f"  优先级顺序: {' -> '.join(sources)}")

    expected = ["baostock", "tushare", "xtquant"]
    actual = sources

    if actual == expected:
        print("  ✅ PASS: 优先级正确")
        print("     - baostock (P1): 免费兜底，数据最全含退市股")
        print("     - tushare (P2): 付费用户补充")
        print("     - xtquant (P3): QMT用户快速查询")
    else:
        print(f"  ❌ FAIL: 期望 {expected}, 实际 {actual}")

    return actual == expected


def test_scenario_coverage():
    """测试各用户场景覆盖"""
    print("\n=== 5. 用户场景覆盖分析 ===")
    config = Config("config.json")

    scenarios = {
        "付费+QMT": {
            "tushare": True,
            "xtquant": True,
            "expected_kline": "tushare",
            "expected_tick": "xtquant",
            "expected_name": "baostock"
        },
        "付费+无QMT": {
            "tushare": True,
            "xtquant": False,
            "expected_kline": "tushare",
            "expected_tick": "mootdx",
            "expected_name": "baostock"
        },
        "免费+QMT": {
            "tushare": False,
            "xtquant": True,
            "expected_kline": "baostock",
            "expected_tick": "xtquant",
            "expected_name": "baostock"
        },
        "免费+无QMT": {
            "tushare": False,
            "xtquant": False,
            "expected_kline": "baostock",
            "expected_tick": "mootdx",
            "expected_name": "baostock"
        }
    }

    all_pass = True
    for scenario_name, scenario in scenarios.items():
        print(f"\n  场景: {scenario_name}")

        # 模拟数据源可用性
        kline_sources = config.get_sources_by_role("kline_day")
        tick_sources = config.get_sources_by_role("tick")
        name_sources = config.get_sources_by_role("stock_name")

        # 过滤不可用的数据源
        available_kline = [s for s in kline_sources
                          if s != 'tushare' or scenario['tushare']]
        available_kline = [s for s in available_kline
                          if s != 'xtquant' or scenario['xtquant']]

        available_tick = [s for s in tick_sources
                         if s != 'xtquant' or scenario['xtquant']]

        available_name = [s for s in name_sources
                         if s != 'tushare' or scenario['tushare']]
        available_name = [s for s in available_name
                         if s != 'xtquant' or scenario['xtquant']]

        # 验证首选数据源
        actual_kline = available_kline[0] if available_kline else None
        actual_tick = available_tick[0] if available_tick else None
        actual_name = available_name[0] if available_name else None

        kline_ok = actual_kline == scenario['expected_kline']
        tick_ok = actual_tick == scenario['expected_tick']
        name_ok = actual_name == scenario['expected_name']

        status = "✅" if (kline_ok and tick_ok and name_ok) else "❌"
        print(f"    {status} 日K线: {actual_kline} (期望: {scenario['expected_kline']})")
        print(f"    {status} Tick: {actual_tick} (期望: {scenario['expected_tick']})")
        print(f"    {status} 股票名称: {actual_name} (期望: {scenario['expected_name']})")

        if not (kline_ok and tick_ok and name_ok):
            all_pass = False

    return all_pass


def main():
    sep("=")
    print("鲁棒性配置验证")
    sep("=")

    results = []

    results.append(("日K线优先级", test_kline_day_priority()))
    results.append(("Tick优先级", test_tick_priority()))
    results.append(("校验源配置", test_validation_sources()))
    results.append(("股票名称优先级", test_stock_name_priority()))
    results.append(("场景覆盖", test_scenario_coverage()))

    sep("=")
    print("\n汇总结果:")
    sep()

    passed = sum(1 for _, result in results if result)
    total = len(results)

    for name, result in results:
        status = "✅ PASS" if result else "❌ FAIL"
        print(f"  {status}  {name}")

    sep()
    print(f"\n总计: {passed}/{total} 通过")

    if passed == total:
        print("\n🎉 所有验证通过！鲁棒性配置正确。")
        return 0
    else:
        print(f"\n⚠️  {total - passed} 项验证失败，请检查配置。")
        return 1


if __name__ == "__main__":
    sys.exit(main())
