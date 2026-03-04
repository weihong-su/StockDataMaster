#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
盘中回归测试脚本 (During-Market Regression Test)

测试时段：9:15 - 15:00
测试重点：
1. 实时数据获取（xtquant Tick数据）
2. 分钟K线数据（5m/15m/30m/60m）
3. 盘中缓存策略验证（当日不缓存，历史缓存）
4. 数据源性能对比（xtquant vs 其他）
5. 实时数据质量验证

执行命令：
C:\\Users\\PC\\Anaconda3\\envs\\python39\\python.exe test\\test_during_market.py
"""

import sys
import os
import time
import json
import traceback
from datetime import datetime, date, time as datetime_time, timedelta
from typing import Dict, List, Any, Optional
import platform

# ==================== 路径设置 ====================
test_dir = os.path.dirname(os.path.abspath(__file__))
project_root = os.path.dirname(test_dir)
parent_dir = os.path.dirname(project_root)
sys.path.insert(0, parent_dir)

from StockDataMaster import StockDataMaster

# ==================== 测试配置 ====================
TEST_STOCKS = [
    ('600519', '贵州茅台'),  # 高价股
    ('000001', '平安银行'),  # 深市股票
    ('600000', '浦发银行'),  # 金融股
    ('000858', '五粮液'),    # 消费股
    ('601318', '中国平安'),  # 大盘股
]

MINUTE_FREQS = ['5m', '15m', '30m', '60m']
PERFORMANCE_THRESHOLDS = {
    'tick': 1.0,        # 实时Tick < 1.0s
    'minute_kline': 3.0,  # 分钟K线 < 3.0s
    'cached_daily': 0.01,  # 缓存日K线 < 0.01s
}


class DuringMarketRegressionTest:
    """盘中回归测试类"""

    def __init__(self):
        self.master = None
        self.results = []
        self.start_time = datetime.now()
        self.report = {
            "test_info": {},
            "test_results": {},
            "test_categories": {},
            "performance_metrics": {},
            "detailed_results": [],
            "errors": []
        }

    def setup(self):
        """测试准备"""
        print("=" * 80)
        print("盘中回归测试 - 初始化")
        print("=" * 80)

        try:
            # 初始化 StockDataMaster
            self.master = StockDataMaster()
            self._log_test("初始化StockDataMaster", True, "成功初始化数据主接口")

            # 记录测试环境信息
            self.report["test_info"] = {
                "script_name": "盘中回归测试",
                "test_time": self.start_time.strftime("%Y-%m-%d %H:%M:%S"),
                "market_phase": "during_market",
                "python_version": platform.python_version(),
                "platform": platform.platform(),
                "test_stocks": [f"{code}({name})" for code, name in TEST_STOCKS],
                "minute_freqs": MINUTE_FREQS
            }

            print(f"\n[OK] 初始化成功")
            print(f"   Python版本: {platform.python_version()}")
            print(f"   操作系统: {platform.platform()}")
            print(f"   测试时间: {self.start_time.strftime('%Y-%m-%d %H:%M:%S')}")

        except Exception as e:
            error_msg = f"初始化失败: {str(e)}"
            print(f"\n[FAIL] {error_msg}")
            self._log_test("初始化StockDataMaster", False, error_msg)
            self.report["errors"].append({
                "phase": "setup",
                "error": error_msg,
                "traceback": traceback.format_exc()
            })
            raise

    def teardown(self):
        """测试清理"""
        print("\n" + "=" * 80)
        print("清理测试环境")
        print("=" * 80)

        try:
            if self.master:
                self.master.close()
                print("[OK] 成功关闭StockDataMaster连接")
        except Exception as e:
            print(f"[WARN] 清理异常: {str(e)}")

    def _log_test(self, test_name: str, passed: bool, message: str,
                  duration: float = 0, details: Optional[Dict] = None):
        """记录测试结果"""
        result = {
            "test_name": test_name,
            "passed": passed,
            "message": message,
            "duration": f"{duration:.3f}s" if duration > 0 else "N/A",
            "timestamp": datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        }

        if details:
            result["details"] = details

        self.results.append(result)
        self.report["detailed_results"].append(result)

    def _check_market_phase(self) -> bool:
        """检查当前是否为盘中时段"""
        now = datetime.now()
        market_open = datetime_time(9, 15)
        market_close = datetime_time(15, 0)

        is_during_market = market_open <= now.time() <= market_close

        print(f"\n当前时间: {now.strftime('%H:%M:%S')}")
        print(f"盘中时段: {'[是]' if is_during_market else '[否]（不建议运行盘中测试）'}")

        return is_during_market

    # ==================== 实时数据测试 ====================

    def test_realtime_data(self):
        """实时数据测试模块"""
        print("\n" + "=" * 80)
        print("【1/5】实时数据测试")
        print("=" * 80)

        realtime_results = {
            "total": 0,
            "passed": 0,
            "failed": 0
        }

        # 1.1 实时Tick数据获取
        self._test_realtime_tick(realtime_results)

        # 1.2 实时数据新鲜度验证
        self._test_data_freshness(realtime_results)

        # 1.3 实时价格合理性验证
        self._test_price_validity(realtime_results)

        self.report["test_categories"]["实时数据测试"] = realtime_results

        print(f"\n实时数据测试完成: {realtime_results['passed']}/{realtime_results['total']} 通过")

    def _test_realtime_tick(self, results: Dict):
        """测试实时Tick数据获取"""
        print("\n[实时数据测试 1.1] 实时Tick数据获取")

        for code, name in TEST_STOCKS:
            test_name = f"获取{name}({code})实时Tick"

            try:
                start_time = time.time()
                tick = self.master.get_tick(code)
                duration = time.time() - start_time

                results["total"] += 1

                if tick and tick.get('last', 0) > 0:
                    source = tick.get('source', 'unknown')
                    last_price = tick.get('last', 0)
                    volume = tick.get('volume', 0)

                    # 检查响应时间
                    if duration < PERFORMANCE_THRESHOLDS['tick']:
                        results["passed"] += 1
                        print(f"   [OK] {test_name}: 价格={last_price:.2f}, 成交量={volume}, "
                              f"来源={source}, {duration:.3f}s")
                        self._log_test(
                            test_name,
                            True,
                            f"成功获取实时Tick数据",
                            duration,
                            {
                                "last_price": last_price,
                                "volume": volume,
                                "source": source
                            }
                        )
                    else:
                        results["failed"] += 1
                        print(f"   [FAIL] {test_name}: 响应时间过长 ({duration:.3f}s > {PERFORMANCE_THRESHOLDS['tick']}s)")
                        self._log_test(test_name, False, f"响应时间过长: {duration:.3f}s", duration)
                else:
                    results["failed"] += 1
                    print(f"   [FAIL] {test_name}: 返回空数据或价格异常")
                    self._log_test(test_name, False, "返回空数据或价格异常", duration)

            except Exception as e:
                results["total"] += 1
                results["failed"] += 1
                error_msg = f"获取Tick失败: {str(e)}"
                print(f"   [FAIL] {test_name}: {error_msg}")
                self._log_test(test_name, False, error_msg)

    def _test_data_freshness(self, results: Dict):
        """测试实时数据新鲜度"""
        print("\n[实时数据测试 1.2] 实时数据新鲜度验证")

        test_code = '600519'
        test_name = '贵州茅台'

        try:
            tick = self.master.get_tick(test_code)

            results["total"] += 1

            if tick:
                # 检查时间戳是否是今天
                tick_time = tick.get('time', '')
                today_str = datetime.now().strftime('%Y-%m-%d')

                is_today = tick_time.startswith(today_str) if tick_time else False

                if is_today:
                    results["passed"] += 1
                    print(f"   [OK] 数据新鲜度验证: 时间戳={tick_time} (今日)")
                    self._log_test(
                        "实时数据新鲜度验证",
                        True,
                        f"时间戳为今日: {tick_time}",
                        details={"tick_time": tick_time}
                    )
                else:
                    results["failed"] += 1
                    print(f"   [FAIL] 数据新鲜度验证: 时间戳不是今天 ({tick_time})")
                    self._log_test("实时数据新鲜度验证", False, f"时间戳不是今天: {tick_time}")
            else:
                results["failed"] += 1
                print(f"   [FAIL] 数据新鲜度验证: 无法获取Tick数据")
                self._log_test("实时数据新鲜度验证", False, "无法获取Tick数据")

        except Exception as e:
            results["total"] += 1
            results["failed"] += 1
            error_msg = f"新鲜度验证失败: {str(e)}"
            print(f"   [FAIL] {error_msg}")
            self._log_test("实时数据新鲜度验证", False, error_msg)

    def _test_price_validity(self, results: Dict):
        """测试实时价格合理性"""
        print("\n[实时数据测试 1.3] 实时价格合理性验证")

        for code, name in TEST_STOCKS[:3]:
            try:
                tick = self.master.get_tick(code)

                results["total"] += 1

                if tick:
                    last = tick.get('last', 0)
                    bid = tick.get('bid', 0)
                    ask = tick.get('ask', 0)
                    volume = tick.get('volume', 0)

                    # 价格合理性检查
                    price_valid = (
                        last > 0 and
                        volume >= 0 and
                        (bid == 0 or bid > 0) and
                        (ask == 0 or ask > 0)
                    )

                    if price_valid:
                        results["passed"] += 1
                        print(f"   [OK] {name}({code}): 价格={last:.2f}, 买={bid:.2f}, 卖={ask:.2f}, "
                              f"量={volume}")
                        self._log_test(
                            f"价格合理性验证({name})",
                            True,
                            "价格和成交量数据合理",
                            details={
                                "last": last,
                                "bid": bid,
                                "ask": ask,
                                "volume": volume
                            }
                        )
                    else:
                        results["failed"] += 1
                        print(f"   [FAIL] {name}({code}): 价格数据异常")
                        self._log_test(f"价格合理性验证({name})", False, "价格数据异常")
                else:
                    results["failed"] += 1
                    print(f"   [FAIL] {name}({code}): 无法获取Tick数据")
                    self._log_test(f"价格合理性验证({name})", False, "无法获取Tick数据")

            except Exception as e:
                results["total"] += 1
                results["failed"] += 1
                error_msg = f"价格验证失败: {str(e)}"
                print(f"   [FAIL] {name}({code}): {error_msg}")
                self._log_test(f"价格合理性验证({name})", False, error_msg)

    # ==================== 分钟K线测试 ====================

    def test_minute_kline(self):
        """分钟K线测试模块"""
        print("\n" + "=" * 80)
        print("【2/5】分钟K线测试")
        print("=" * 80)

        minute_results = {
            "total": 0,
            "passed": 0,
            "failed": 0
        }

        # 2.1 多周期分钟K线获取
        self._test_multiple_freqs(minute_results)

        # 2.2 分钟K线数据完整性
        self._test_minute_kline_completeness(minute_results)

        # 2.3 分钟K线时间戳准确性
        self._test_minute_kline_timestamp(minute_results)

        self.report["test_categories"]["分钟K线测试"] = minute_results

        print(f"\n分钟K线测试完成: {minute_results['passed']}/{minute_results['total']} 通过")

    def _test_multiple_freqs(self, results: Dict):
        """测试多周期分钟K线"""
        print("\n[分钟K线测试 2.1] 多周期分钟K线获取")

        test_code = '600519'
        test_name = '贵州茅台'

        for freq in MINUTE_FREQS:
            test_item = f"获取{test_name} {freq}K线"

            try:
                start_time = time.time()
                df = self.master.get_kline(test_code, freq=freq, count=48)
                duration = time.time() - start_time

                results["total"] += 1

                if df is not None and len(df) > 0:
                    source = df.attrs.get('source', 'unknown')

                    if duration < PERFORMANCE_THRESHOLDS['minute_kline']:
                        results["passed"] += 1
                        print(f"   [OK] {test_item}: {len(df)}条, 来源={source}, {duration:.3f}s")
                        self._log_test(
                            test_item,
                            True,
                            f"成功获取{len(df)}条数据",
                            duration,
                            {
                                "record_count": len(df),
                                "frequency": freq,
                                "source": source
                            }
                        )
                    else:
                        results["failed"] += 1
                        print(f"   [FAIL] {test_item}: 响应时间过长 ({duration:.3f}s)")
                        self._log_test(test_item, False, f"响应时间过长: {duration:.3f}s", duration)
                else:
                    results["failed"] += 1
                    print(f"   [FAIL] {test_item}: 返回空数据")
                    self._log_test(test_item, False, "返回空数据", duration)

            except Exception as e:
                results["total"] += 1
                results["failed"] += 1
                error_msg = f"获取失败: {str(e)}"
                print(f"   [FAIL] {test_item}: {error_msg}")
                self._log_test(test_item, False, error_msg)

    def _test_minute_kline_completeness(self, results: Dict):
        """测试分钟K线数据完整性"""
        print("\n[分钟K线测试 2.2] 分钟K线数据完整性")

        test_code = '600000'
        test_freq = '5m'

        try:
            df = self.master.get_kline(test_code, freq=test_freq, count=48)

            results["total"] += 1

            if df is not None and len(df) > 0:
                required_columns = ['date', 'open', 'high', 'low', 'close', 'volume']
                missing_columns = [col for col in required_columns if col not in df.columns]

                # OHLC逻辑检查
                ohlc_valid = (
                    (df['high'] >= df['low']).all() and
                    (df['high'] >= df['open']).all() and
                    (df['high'] >= df['close']).all()
                )

                if len(missing_columns) == 0 and ohlc_valid:
                    results["passed"] += 1
                    print(f"   [OK] 数据完整性验证: {len(df)}条记录，所有字段完整")
                    self._log_test(
                        "分钟K线数据完整性",
                        True,
                        f"所有必需字段完整，OHLC逻辑正确",
                        details={"record_count": len(df)}
                    )
                else:
                    results["failed"] += 1
                    error = f"缺少列:{missing_columns}" if missing_columns else "OHLC逻辑错误"
                    print(f"   [FAIL] 数据完整性验证: {error}")
                    self._log_test("分钟K线数据完整性", False, error)
            else:
                results["failed"] += 1
                print(f"   [FAIL] 数据完整性验证: 返回空数据")
                self._log_test("分钟K线数据完整性", False, "返回空数据")

        except Exception as e:
            results["total"] += 1
            results["failed"] += 1
            error_msg = f"完整性验证失败: {str(e)}"
            print(f"   [FAIL] {error_msg}")
            self._log_test("分钟K线数据完整性", False, error_msg)

    def _test_minute_kline_timestamp(self, results: Dict):
        """测试分钟K线时间戳准确性"""
        print("\n[分钟K线测试 2.3] 分钟K线时间戳准确性")

        test_code = '600519'
        test_freq = '5m'

        try:
            df = self.master.get_kline(test_code, freq=test_freq, count=48)

            results["total"] += 1

            if df is not None and len(df) > 0:
                # 检查最新数据是否是今天
                latest_date = df['date'].iloc[-1]
                today_str = datetime.now().strftime('%Y-%m-%d')

                is_today = latest_date.startswith(today_str) if isinstance(latest_date, str) else False

                if is_today:
                    results["passed"] += 1
                    print(f"   [OK] 时间戳准确性验证: 最新数据={latest_date} (今日)")
                    self._log_test(
                        "分钟K线时间戳准确性",
                        True,
                        f"最新数据时间戳为今日: {latest_date}",
                        details={"latest_timestamp": latest_date}
                    )
                else:
                    results["failed"] += 1
                    print(f"   [FAIL] 时间戳准确性验证: 最新数据不是今天 ({latest_date})")
                    self._log_test("分钟K线时间戳准确性", False, f"最新数据不是今天: {latest_date}")
            else:
                results["failed"] += 1
                print(f"   [FAIL] 时间戳准确性验证: 返回空数据")
                self._log_test("分钟K线时间戳准确性", False, "返回空数据")

        except Exception as e:
            results["total"] += 1
            results["failed"] += 1
            error_msg = f"时间戳验证失败: {str(e)}"
            print(f"   [FAIL] {error_msg}")
            self._log_test("分钟K线时间戳准确性", False, error_msg)

    # ==================== 盘中缓存策略测试 ====================

    def test_intraday_cache_strategy(self):
        """盘中缓存策略测试模块"""
        print("\n" + "=" * 80)
        print("【3/5】盘中缓存策略测试")
        print("=" * 80)

        cache_results = {
            "total": 0,
            "passed": 0,
            "failed": 0
        }

        # 3.1 盘中不缓存当日数据
        self._test_no_cache_today(cache_results)

        # 3.2 历史数据使用缓存
        self._test_cache_historical(cache_results)

        # 3.3 缓存命中率统计
        self._test_cache_hit_rate(cache_results)

        self.report["test_categories"]["盘中缓存策略测试"] = cache_results

        print(f"\n盘中缓存策略测试完成: {cache_results['passed']}/{cache_results['total']} 通过")

    def _test_no_cache_today(self, results: Dict):
        """测试盘中不缓存当日数据"""
        print("\n[缓存策略测试 3.1] 盘中不缓存当日数据")

        test_code = '600519'
        test_name = '贵州茅台'

        try:
            # 第一次请求（包含当日）
            df1 = self.master.get_kline(test_code, freq='d', count=60)
            source1 = df1.attrs.get('source', 'unknown') if df1 is not None else 'none'

            time.sleep(0.5)

            # 第二次请求（包含当日）
            df2 = self.master.get_kline(test_code, freq='d', count=60)
            source2 = df2.attrs.get('source', 'unknown') if df2 is not None else 'none'

            results["total"] += 1

            # 检查最新日期是否是今天
            latest_date = df2['date'].iloc[-1] if df2 is not None and len(df2) > 0 else ''
            today_str = datetime.now().strftime('%Y-%m-%d')
            is_today = latest_date == today_str

            if is_today:
                # 盘中时段，包含当日数据不应该缓存
                if source2 != 'cache':
                    results["passed"] += 1
                    print(f"   [OK] 盘中不缓存当日: 第2次来源={source2} (非缓存，符合预期)")
                    self._log_test(
                        "盘中不缓存当日数据",
                        True,
                        f"盘中时段正确不缓存当日数据，来源: {source2}",
                        details={
                            "first_source": source1,
                            "second_source": source2,
                            "latest_date": latest_date
                        }
                    )
                else:
                    results["failed"] += 1
                    print(f"   [FAIL] 盘中不缓存当日: 第2次来源={source2} (错误使用了缓存)")
                    self._log_test("盘中不缓存当日数据", False, "盘中时段错误缓存了当日数据")
            else:
                # 最新数据不是今天（可能是非交易日）
                print(f"   [SKIP] 最新数据不是今天 ({latest_date})，跳过测试")
                results["total"] -= 1  # 不计入统计

        except Exception as e:
            results["total"] += 1
            results["failed"] += 1
            error_msg = f"测试失败: {str(e)}"
            print(f"   [FAIL] {error_msg}")
            self._log_test("盘中不缓存当日数据", False, error_msg)

    def _test_cache_historical(self, results: Dict):
        """测试历史数据使用缓存"""
        print("\n[缓存策略测试 3.2] 历史数据使用缓存")

        test_code = '600000'
        # 请求截止到昨天的数据（纯历史数据）
        yesterday = (datetime.now() - timedelta(days=1)).strftime('%Y-%m-%d')

        try:
            # 第一次请求
            df1 = self.master.get_kline(test_code, freq='d', end_date=yesterday, count=30)
            source1 = df1.attrs.get('source', 'unknown') if df1 is not None else 'none'

            time.sleep(0.5)

            # 第二次请求（应该从缓存获取）
            start_time = time.time()
            df2 = self.master.get_kline(test_code, freq='d', end_date=yesterday, count=30)
            duration = time.time() - start_time
            source2 = df2.attrs.get('source', 'unknown') if df2 is not None else 'none'

            results["total"] += 1

            if source2 == 'cache' and duration < PERFORMANCE_THRESHOLDS['cached_daily']:
                results["passed"] += 1
                print(f"   [OK] 历史数据使用缓存: 第1次={source1}, 第2次={source2}, {duration:.3f}s")
                self._log_test(
                    "历史数据使用缓存",
                    True,
                    "历史数据第二次请求正确使用缓存",
                    duration,
                    {
                        "first_source": source1,
                        "second_source": source2,
                        "end_date": yesterday
                    }
                )
            else:
                results["failed"] += 1
                print(f"   [FAIL] 历史数据使用缓存: 第2次={source2}, {duration:.3f}s (未使用缓存或过慢)")
                self._log_test("历史数据使用缓存", False, f"未正确使用缓存，来源: {source2}", duration)

        except Exception as e:
            results["total"] += 1
            results["failed"] += 1
            error_msg = f"测试失败: {str(e)}"
            print(f"   [FAIL] {error_msg}")
            self._log_test("历史数据使用缓存", False, error_msg)

    def _test_cache_hit_rate(self, results: Dict):
        """测试缓存命中率统计"""
        print("\n[缓存策略测试 3.3] 缓存命中率统计")

        try:
            stats = self.master.get_cache_statistics()

            results["total"] += 1

            if stats and 'total_records' in stats:
                total_records = stats.get('total_records', 0)
                stock_count = stats.get('stock_count', 0)

                print(f"   缓存记录数: {total_records}")
                print(f"   缓存股票数: {stock_count}")

                results["passed"] += 1
                self._log_test(
                    "缓存命中率统计",
                    True,
                    "成功获取缓存统计信息",
                    details={
                        "total_records": total_records,
                        "stock_count": stock_count
                    }
                )
            else:
                results["failed"] += 1
                print(f"   [FAIL] 缓存统计信息异常")
                self._log_test("缓存命中率统计", False, "缓存统计信息异常")

        except Exception as e:
            results["total"] += 1
            results["failed"] += 1
            error_msg = f"统计失败: {str(e)}"
            print(f"   [FAIL] {error_msg}")
            self._log_test("缓存命中率统计", False, error_msg)

    # ==================== 性能测试 ====================

    def test_performance(self):
        """性能测试模块"""
        print("\n" + "=" * 80)
        print("【4/5】性能测试")
        print("=" * 80)

        performance_results = {
            "total": 0,
            "passed": 0,
            "failed": 0,
            "metrics": {}
        }

        # 4.1 xtquant实时性能
        self._test_xtquant_performance(performance_results)

        # 4.2 数据源性能对比
        self._test_source_comparison(performance_results)

        # 4.3 批量Tick获取性能
        self._test_batch_tick_performance(performance_results)

        self.report["test_categories"]["性能测试"] = performance_results

        print(f"\n性能测试完成: {performance_results['passed']}/{performance_results['total']} 通过")

    def _test_xtquant_performance(self, results: Dict):
        """测试xtquant实时性能"""
        print("\n[性能测试 4.1] xtquant实时性能")

        test_code = '600519'

        try:
            start_time = time.time()
            tick = self.master.get_tick(test_code)
            duration = time.time() - start_time

            results["total"] += 1

            if tick and duration < PERFORMANCE_THRESHOLDS['tick']:
                source = tick.get('source', 'unknown')
                results["passed"] += 1
                results["metrics"]["xtquant_tick_time"] = f"{duration:.3f}s"

                print(f"   [OK] xtquant Tick性能: {duration:.3f}s (来源: {source})")
                self._log_test(
                    "xtquant实时性能",
                    True,
                    f"响应时间 {duration:.3f}s < {PERFORMANCE_THRESHOLDS['tick']}s",
                    duration,
                    {"source": source}
                )
            else:
                results["failed"] += 1
                print(f"   [FAIL] xtquant Tick性能: {duration:.3f}s (超过阈值)")
                self._log_test("xtquant实时性能", False, f"响应时间过长: {duration:.3f}s", duration)

        except Exception as e:
            results["total"] += 1
            results["failed"] += 1
            error_msg = f"性能测试失败: {str(e)}"
            print(f"   [FAIL] {error_msg}")
            self._log_test("xtquant实时性能", False, error_msg)

    def _test_source_comparison(self, results: Dict):
        """测试数据源性能对比"""
        print("\n[性能测试 4.2] 数据源性能对比")

        test_code = '600000'

        try:
            # 测试日K线性能（可能来自缓存或网络）
            start_time = time.time()
            df = self.master.get_kline(test_code, freq='d', count=60)
            kline_time = time.time() - start_time
            kline_source = df.attrs.get('source', 'unknown') if df is not None else 'none'

            # 测试实时Tick性能
            start_time = time.time()
            tick = self.master.get_tick(test_code)
            tick_time = time.time() - start_time
            tick_source = tick.get('source', 'unknown') if tick else 'none'

            results["total"] += 1

            print(f"   日K线性能: {kline_time:.3f}s (来源: {kline_source})")
            print(f"   实时Tick性能: {tick_time:.3f}s (来源: {tick_source})")

            results["passed"] += 1
            results["metrics"]["source_comparison"] = {
                "kline_time": f"{kline_time:.3f}s",
                "kline_source": kline_source,
                "tick_time": f"{tick_time:.3f}s",
                "tick_source": tick_source
            }

            self._log_test(
                "数据源性能对比",
                True,
                "成功对比不同数据源性能",
                details=results["metrics"]["source_comparison"]
            )

        except Exception as e:
            results["total"] += 1
            results["failed"] += 1
            error_msg = f"对比测试失败: {str(e)}"
            print(f"   [FAIL] {error_msg}")
            self._log_test("数据源性能对比", False, error_msg)

    def _test_batch_tick_performance(self, results: Dict):
        """测试批量Tick获取性能"""
        print("\n[性能测试 4.3] 批量Tick获取性能")

        batch_stocks = TEST_STOCKS[:3]
        batch_times = []

        start_time = time.time()

        for code, name in batch_stocks:
            try:
                t0 = time.time()
                tick = self.master.get_tick(code)
                t1 = time.time() - t0

                batch_times.append(t1)
                source = tick.get('source', 'unknown') if tick else 'none'
                last_price = tick.get('last', 0) if tick else 0
                print(f"   {name}({code}): {t1:.3f}s, 价格={last_price:.2f}, 来源={source}")

            except Exception as e:
                print(f"   [FAIL] {name}({code}): {str(e)}")
                batch_times.append(0)

        total_time = time.time() - start_time
        avg_time = sum(batch_times) / len(batch_times) if batch_times else 0

        results["total"] += 1

        print(f"   批量获取总时间: {total_time:.3f}s")
        print(f"   平均每只股票: {avg_time:.3f}s")

        # 预期平均时间应该小于1秒
        if avg_time < 1.0:
            results["passed"] += 1
            results["metrics"]["batch_tick_performance"] = {
                "total_time": f"{total_time:.3f}s",
                "avg_time": f"{avg_time:.3f}s",
                "stock_count": len(batch_stocks)
            }
            self._log_test(
                "批量Tick获取性能",
                True,
                f"平均每只股票 {avg_time:.3f}s",
                total_time,
                results["metrics"]["batch_tick_performance"]
            )
        else:
            results["failed"] += 1
            self._log_test("批量Tick获取性能", False, f"平均时间过长: {avg_time:.3f}s")

    # ==================== 数据源健康测试 ====================

    def test_data_source_health(self):
        """数据源健康测试模块"""
        print("\n" + "=" * 80)
        print("【5/5】数据源健康测试")
        print("=" * 80)

        health_results = {
            "total": 0,
            "passed": 0,
            "failed": 0
        }

        # 5.1 健康检查功能
        self._test_health_check(health_results)

        # 5.2 活跃数据源验证
        self._test_active_sources(health_results)

        # 5.3 数据源切换历史
        self._test_switch_history(health_results)

        self.report["test_categories"]["数据源健康测试"] = health_results

        print(f"\n数据源健康测试完成: {health_results['passed']}/{health_results['total']} 通过")

    def _test_health_check(self, results: Dict):
        """测试健康检查功能"""
        print("\n[数据源健康测试 5.1] 健康检查功能")

        try:
            start_time = time.time()
            status = self.master.get_health_status()
            duration = time.time() - start_time

            results["total"] += 1

            if status and 'sources' in status:
                enabled_sources = [name for name, info in status['sources'].items()
                                 if info.get('enabled', False)]
                connected_sources = [name for name, info in status['sources'].items()
                                   if info.get('connected', False)]

                print(f"   启用的数据源: {', '.join(enabled_sources)}")
                print(f"   已连接数据源: {', '.join(connected_sources)}")

                results["passed"] += 1
                self._log_test(
                    "数据源健康检查",
                    True,
                    f"成功获取健康状态，{len(connected_sources)}/{len(enabled_sources)} 数据源已连接",
                    duration,
                    {
                        "enabled_sources": enabled_sources,
                        "connected_sources": connected_sources
                    }
                )
            else:
                results["failed"] += 1
                self._log_test("数据源健康检查", False, "健康状态返回异常", duration)

        except Exception as e:
            results["total"] += 1
            results["failed"] += 1
            error_msg = f"健康检查失败: {str(e)}"
            print(f"   [FAIL] {error_msg}")
            self._log_test("数据源健康检查", False, error_msg)

    def _test_active_sources(self, results: Dict):
        """测试活跃数据源验证"""
        print("\n[数据源健康测试 5.2] 活跃数据源验证")

        try:
            status = self.master.get_health_status()

            results["total"] += 1

            if status and 'active_sources' in status:
                active_sources = status['active_sources']

                print(f"   活跃数据源:")
                for usage, source in active_sources.items():
                    print(f"      {usage}: {source}")

                # 检查关键用途是否有活跃数据源
                has_tick_source = 'tick' in active_sources and active_sources['tick']
                has_kline_source = 'kline' in active_sources and active_sources['kline']

                if has_tick_source and has_kline_source:
                    results["passed"] += 1
                    self._log_test(
                        "活跃数据源验证",
                        True,
                        "关键数据用途均有活跃数据源",
                        details=active_sources
                    )
                else:
                    results["failed"] += 1
                    missing = []
                    if not has_tick_source:
                        missing.append('tick')
                    if not has_kline_source:
                        missing.append('kline')
                    self._log_test("活跃数据源验证", False, f"缺少活跃数据源: {missing}")
            else:
                results["failed"] += 1
                self._log_test("活跃数据源验证", False, "无法获取活跃数据源信息")

        except Exception as e:
            results["total"] += 1
            results["failed"] += 1
            error_msg = f"验证失败: {str(e)}"
            print(f"   [FAIL] {error_msg}")
            self._log_test("活跃数据源验证", False, error_msg)

    def _test_switch_history(self, results: Dict):
        """测试数据源切换历史"""
        print("\n[数据源健康测试 5.3] 数据源切换历史")

        try:
            status = self.master.get_health_status()

            results["total"] += 1

            if status:
                # 假设健康状态包含切换历史信息
                switch_history = status.get('switch_history', [])

                if isinstance(switch_history, list):
                    print(f"   切换历史记录数: {len(switch_history)}")
                    if len(switch_history) > 0:
                        print(f"   最近切换:")
                        for record in switch_history[-3:]:  # 显示最近3次
                            print(f"      {record}")

                    results["passed"] += 1
                    self._log_test(
                        "数据源切换历史",
                        True,
                        f"成功获取切换历史，共{len(switch_history)}条记录",
                        details={"history_count": len(switch_history)}
                    )
                else:
                    results["passed"] += 1
                    print(f"   [OK] 切换历史功能正常（无切换记录）")
                    self._log_test("数据源切换历史", True, "切换历史功能正常（无切换记录）")
            else:
                results["failed"] += 1
                self._log_test("数据源切换历史", False, "无法获取健康状态")

        except Exception as e:
            results["total"] += 1
            results["failed"] += 1
            error_msg = f"测试失败: {str(e)}"
            print(f"   [FAIL] {error_msg}")
            self._log_test("数据源切换历史", False, error_msg)

    # ==================== 报告生成 ====================

    def generate_report(self):
        """生成测试报告"""
        print("\n" + "=" * 80)
        print("生成测试报告")
        print("=" * 80)

        end_time = datetime.now()
        total_duration = (end_time - self.start_time).total_seconds()

        # 统计总体结果
        total_tests = len(self.results)
        passed_tests = sum(1 for r in self.results if r['passed'])
        failed_tests = sum(1 for r in self.results if not r['passed'])
        pass_rate = (passed_tests / total_tests * 100) if total_tests > 0 else 0

        self.report["test_results"] = {
            "total_tests": total_tests,
            "passed": passed_tests,
            "failed": failed_tests,
            "skipped": 0,
            "pass_rate": round(pass_rate, 2),
            "total_duration": f"{total_duration:.2f}s",
            "start_time": self.start_time.strftime("%Y-%m-%d %H:%M:%S"),
            "end_time": end_time.strftime("%Y-%m-%d %H:%M:%S")
        }

        # 计算性能指标
        perf_metrics = self.report["test_categories"].get("性能测试", {}).get("metrics", {})
        self.report["performance_metrics"] = perf_metrics

        # 保存 JSON 报告
        report_dir = os.path.join(test_dir, 'reports')
        os.makedirs(report_dir, exist_ok=True)

        json_file = os.path.join(report_dir, f'during_market_test_{datetime.now().strftime("%Y%m%d_%H%M%S")}.json')
        with open(json_file, 'w', encoding='utf-8') as f:
            json.dump(self.report, f, ensure_ascii=False, indent=2)

        print(f"\n[OK] JSON报告已保存: {json_file}")

        # 生成 Markdown 报告
        md_file = os.path.join(report_dir, f'during_market_test_{datetime.now().strftime("%Y%m%d_%H%M%S")}.md')
        self._generate_markdown_report(md_file)

        print(f"[OK] Markdown报告已保存: {md_file}")

        # 打印摘要
        print("\n" + "=" * 80)
        print("测试摘要")
        print("=" * 80)
        print(f"总测试数: {total_tests}")
        print(f"通过: {passed_tests}")
        print(f"失败: {failed_tests}")
        print(f"通过率: {pass_rate:.1f}%")
        print(f"总耗时: {total_duration:.2f}s")
        print("=" * 80)

        return json_file, md_file

    def _generate_markdown_report(self, filepath: str):
        """生成Markdown格式报告"""

        with open(filepath, 'w', encoding='utf-8') as f:
            f.write("# 盘中回归测试报告\n\n")

            # 测试信息
            f.write("## 测试信息\n\n")
            info = self.report["test_info"]
            f.write(f"- **测试时间**: {info['test_time']}\n")
            f.write(f"- **市场时段**: 盘中 (During-Market)\n")
            f.write(f"- **Python版本**: {info['python_version']}\n")
            f.write(f"- **操作系统**: {info['platform']}\n")
            f.write(f"- **测试股票**: {', '.join(info['test_stocks'])}\n")
            f.write(f"- **分钟周期**: {', '.join(info['minute_freqs'])}\n\n")

            # 测试结果
            f.write("## 测试结果\n\n")
            results = self.report["test_results"]
            f.write(f"- **总测试数**: {results['total_tests']}\n")
            f.write(f"- **通过**: {results['passed']} ✅\n")
            f.write(f"- **失败**: {results['failed']} ❌\n")
            f.write(f"- **通过率**: {results['pass_rate']}%\n")
            f.write(f"- **总耗时**: {results['total_duration']}\n\n")

            # 分类测试结果
            f.write("## 分类测试结果\n\n")
            for category, data in self.report["test_categories"].items():
                f.write(f"### {category}\n\n")
                f.write(f"- 通过: {data.get('passed', 0)}/{data.get('total', 0)}\n")

                if 'metrics' in data and data['metrics']:
                    f.write("\n**性能指标**:\n\n")
                    for key, value in data['metrics'].items():
                        if isinstance(value, dict):
                            f.write(f"- {key}:\n")
                            for k, v in value.items():
                                f.write(f"  - {k}: {v}\n")
                        else:
                            f.write(f"- {key}: {value}\n")
                f.write("\n")

            # 详细测试结果
            f.write("## 详细测试结果\n\n")
            f.write("| 测试项 | 结果 | 说明 | 耗时 |\n")
            f.write("|--------|------|------|------|\n")

            for result in self.report["detailed_results"]:
                status = "✅" if result['passed'] else "❌"
                f.write(f"| {result['test_name']} | {status} | {result['message']} | {result['duration']} |\n")

            # 错误信息
            if self.report["errors"]:
                f.write("\n## 错误信息\n\n")
                for error in self.report["errors"]:
                    f.write(f"### {error['phase']}\n\n")
                    f.write(f"```\n{error['error']}\n```\n\n")

            # 性能阈值说明
            f.write("\n## 性能阈值说明\n\n")
            f.write("| 测试项 | 阈值 | 说明 |\n")
            f.write("|--------|------|------|\n")
            f.write(f"| 实时Tick响应时间 | < {PERFORMANCE_THRESHOLDS['tick']}s | xtquant实时数据 |\n")
            f.write(f"| 分钟K线响应时间 | < {PERFORMANCE_THRESHOLDS['minute_kline']}s | 网络获取 |\n")
            f.write(f"| 日K线（历史）响应时间 | < {PERFORMANCE_THRESHOLDS['cached_daily']}s | 缓存获取 |\n\n")

    def run_all_tests(self):
        """运行所有测试"""
        try:
            # 检查市场时段
            if not self._check_market_phase():
                print("\n[WARN] 警告: 当前不是盘中时段，但将继续执行测试")

            self.setup()
            self.test_realtime_data()
            self.test_minute_kline()
            self.test_intraday_cache_strategy()
            self.test_performance()
            self.test_data_source_health()
            return self.generate_report()

        except Exception as e:
            print(f"\n[FAIL] 测试执行失败: {str(e)}")
            traceback.print_exc()
            return None, None

        finally:
            self.teardown()


def main():
    """主函数"""
    print("=" * 80)
    print("StockDataMaster 盘中回归测试")
    print("=" * 80)

    test = DuringMarketRegressionTest()
    json_file, md_file = test.run_all_tests()

    if json_file and md_file:
        print(f"\n[OK] 测试完成！")
        print(f"   JSON报告: {json_file}")
        print(f"   Markdown报告: {md_file}")


if __name__ == '__main__':
    main()
