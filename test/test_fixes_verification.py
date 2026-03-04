"""
测试修复效果验证脚本

验证以下修复：
1. 实时数据时间戳字段缺失
2. 缺少'kline'活跃源记录
"""
import sys
import os
from datetime import datetime, timedelta

# 添加项目根目录到 sys.path
test_dir = os.path.dirname(os.path.abspath(__file__))
project_root = os.path.dirname(test_dir)
parent_dir = os.path.dirname(project_root)
sys.path.insert(0, parent_dir)

from StockDataMaster import StockDataMaster


def print_separator(title=""):
    """打印分隔线"""
    if title:
        print(f"\n{'='*70}")
        print(f"  {title}")
        print('='*70)
    else:
        print('-'*70)


def test_tick_timestamp_fix():
    """测试1: 验证 Tick 数据时间戳字段修复"""
    print_separator("测试1: 实时数据时间戳字段修复")

    try:
        master = StockDataMaster()

        # 测试股票列表
        test_stocks = ['600000', '600519', '000001']

        all_passed = True
        for code in test_stocks:
            print(f"\n测试股票: {code}")

            # 获取实时Tick数据
            tick = master.get_tick(code)

            if tick is None:
                print(f"  [SKIP] 无法获取Tick数据（可能非交易时段）")
                continue

            # 检查1: timestamp字段是否存在
            if 'timestamp' not in tick:
                print(f"  [FAIL] 缺少 'timestamp' 字段")
                all_passed = False
                continue

            # 检查2: timestamp值是否为None或空
            if tick['timestamp'] is None or tick['timestamp'] == '':
                print(f"  [FAIL] 'timestamp' 字段值为空: {tick['timestamp']}")
                all_passed = False
                continue

            # 检查3: timestamp格式是否正确
            try:
                dt = datetime.strptime(tick['timestamp'], '%Y-%m-%d %H:%M:%S')
                print(f"  [PASS] timestamp: {tick['timestamp']}")
            except ValueError as e:
                print(f"  [FAIL] timestamp格式错误: {tick['timestamp']}, 错误: {e}")
                all_passed = False
                continue

            # 检查4: timestamp是否为今天
            today = datetime.now().date()
            if dt.date() == today:
                print(f"  [PASS] timestamp日期正确（今天）")
            else:
                print(f"  [WARN] timestamp日期不是今天: {dt.date()} (可能是盘前/盘后)")

            # 打印其他字段
            print(f"  - 最新价: {tick.get('last', 0):.2f}")
            print(f"  - 成交量: {tick.get('volume', 0)}")
            print(f"  - 数据来源: {tick.get('source', 'unknown')}")

        master.close()

        if all_passed:
            print("\n[PASS] 测试1: 实时数据时间戳字段修复 - 全部通过")
            return True
        else:
            print("\n[FAIL] 测试1: 实时数据时间戳字段修复 - 部分失败")
            return False

    except Exception as e:
        print(f"\n[ERROR] 测试1执行异常: {e}")
        import traceback
        traceback.print_exc()
        return False


def test_active_source_fix():
    """测试2: 验证活跃数据源记录修复"""
    print_separator("测试2: 活跃数据源记录修复")

    try:
        master = StockDataMaster()

        # 获取健康状态
        status = master.get_health_status()

        if 'active_sources' not in status:
            print("[FAIL] 健康状态中缺少 'active_sources' 字段")
            master.close()
            return False

        active_sources = status['active_sources']
        print(f"\n当前活跃数据源:")
        for usage, source in active_sources.items():
            print(f"  {usage}: {source}")

        all_passed = True

        # 检查1: kline_day 活跃源
        if 'kline_day' in active_sources:
            print(f"\n[PASS] 'kline_day' 活跃源存在: {active_sources['kline_day']}")
        else:
            print(f"\n[FAIL] 缺少 'kline_day' 活跃源")
            all_passed = False

        # 检查2: kline_minute 活跃源
        if 'kline_minute' in active_sources:
            print(f"[PASS] 'kline_minute' 活跃源存在: {active_sources['kline_minute']}")
        else:
            print(f"[FAIL] 缺少 'kline_minute' 活跃源")
            all_passed = False

        # 检查3: valuation 活跃源
        if 'valuation' in active_sources:
            print(f"[PASS] 'valuation' 活跃源存在: {active_sources['valuation']}")
        else:
            print(f"[WARN] 缺少 'valuation' 活跃源（可能未使用）")

        # 检查4: tick 活跃源
        if 'tick' in active_sources:
            print(f"[PASS] 'tick' 活跃源存在: {active_sources['tick']}")
        else:
            print(f"[WARN] 缺少 'tick' 活跃源（可能未使用）")

        master.close()

        if all_passed:
            print("\n[PASS] 测试2: 活跃数据源记录修复 - 全部通过")
            return True
        else:
            print("\n[FAIL] 测试2: 活跃数据源记录修复 - 部分失败")
            return False

    except Exception as e:
        print(f"\n[ERROR] 测试2执行异常: {e}")
        import traceback
        traceback.print_exc()
        return False


def main():
    """主函数"""
    print_separator("StockDataMaster 修复效果验证")
    print(f"测试时间: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")

    # 运行测试
    test1_result = test_tick_timestamp_fix()
    test2_result = test_active_source_fix()

    # 总结
    print_separator("测试总结")
    print(f"测试1 (时间戳字段): {'[PASS]' if test1_result else '[FAIL]'}")
    print(f"测试2 (活跃源记录): {'[PASS]' if test2_result else '[FAIL]'}")

    if test1_result and test2_result:
        print("\n[SUCCESS] 所有修复验证通过！")
        return 0
    else:
        print("\n[FAILED] 部分修复验证失败，请检查日志")
        return 1


if __name__ == '__main__':
    exit_code = main()
    sys.exit(exit_code)
