"""
测试增量缓存逻辑

验证:
1. 首次获取数据会进行全量校验
2. 再次获取相同数据会跳过校验(已在缓存中)
3. 获取更多数据只校验新增部分
"""

import sys
import os

# 添加项目根目录到路径
test_dir = os.path.dirname(os.path.abspath(__file__))
project_root = os.path.dirname(test_dir)
parent_dir = os.path.dirname(project_root)
sys.path.insert(0, parent_dir)

from StockDataMaster import StockDataMaster
import logging

# 配置日志
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)

def test_incremental_cache():
    """测试增量缓存"""
    print("=" * 80)
    print("测试增量缓存逻辑")
    print("=" * 80)

    # 初始化
    dm = StockDataMaster()
    test_code = "600519"  # 贵州茅台

    # 清理测试股票的缓存
    print(f"\n1. 清理 {test_code} 的缓存...")
    if dm.cache_manager.enabled:
        import sqlite3
        conn = sqlite3.connect(dm.cache_manager.db_path)
        cursor = conn.cursor()
        cursor.execute("DELETE FROM kline_cache WHERE code=?", (test_code,))
        conn.commit()
        conn.close()
        print(f"   已清理缓存")

    # 第一次获取: 最近10条数据
    print(f"\n2. 首次获取 {test_code} 最近10条数据 (应全量校验)...")
    df1 = dm.get_kline(test_code, count=10, use_cache=True)
    if df1 is not None:
        print(f"   获取成功: {len(df1)}条")
        print(f"   日期范围: {df1['date'].iloc[0]} ~ {df1['date'].iloc[-1]}")
    else:
        print(f"   获取失败")
        return

    # 查询缓存中的数据
    validated_dates = dm.cache_manager.get_validated_dates(test_code)
    print(f"   缓存中已验证日期数: {len(validated_dates)}")

    # 第二次获取: 相同的10条数据
    print(f"\n3. 再次获取 {test_code} 最近10条数据 (应跳过校验)...")
    df2 = dm.get_kline(test_code, count=10, use_cache=True)
    if df2 is not None:
        print(f"   获取成功: {len(df2)}条")
        print(f"   数据来源: {df2.attrs.get('source', 'unknown')}")

    # 第三次获取: 更多数据(50条)
    print(f"\n4. 获取 {test_code} 最近50条数据 (应只校验新增40条)...")
    df3 = dm.get_kline(test_code, count=50, use_cache=True)
    if df3 is not None:
        print(f"   获取成功: {len(df3)}条")
        print(f"   日期范围: {df3['date'].iloc[0]} ~ {df3['date'].iloc[-1]}")

    # 最终缓存状态
    validated_dates_final = dm.cache_manager.get_validated_dates(test_code)
    print(f"\n5. 最终缓存状态:")
    print(f"   已验证日期数: {len(validated_dates_final)}")

    print("\n" + "=" * 80)
    print("测试完成")
    print("=" * 80)

if __name__ == "__main__":
    test_incremental_cache()
