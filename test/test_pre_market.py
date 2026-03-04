#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
盘前回归测试脚本 (Pre-Market Regression Test)

测试时段：当前时间 < 9:15
测试重点：
1. 缓存数据可用性（历史数据）
2. 数据源连接状态
3. 健康检查机制
4. 缓存统计准确性

执行命令：
C:\\Users\\PC\\Anaconda3\\envs\\python39\\python.exe test\\test_pre_market.py
"""

import sys
import os
import time
import json
import traceback
from datetime import datetime, date, time as datetime_time
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

TEST_PERIODS = [30, 60, 120]  # 测试周期（天）


class PreMarketRegressionTest:
    """盘前回归测试类"""

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
        print("盘前回归测试 - 初始化")
        print("=" * 80)

        try:
            # 初始化 StockDataMaster
            self.master = StockDataMaster()
            self._log_test("初始化StockDataMaster", True, "成功初始化数据主接口")

            # 记录测试环境信息
            self.report["test_info"] = {
                "script_name": "盘前回归测试",
                "test_time": self.start_time.strftime("%Y-%m-%d %H:%M:%S"),
                "market_phase": "pre_market",
                "python_version": platform.python_version(),
                "platform": platform.platform(),
                "test_stocks": [f"{code}({name})" for code, name in TEST_STOCKS],
                "test_periods": TEST_PERIODS
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
            print(f"[WARN]  清理异常: {str(e)}")

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
        """检查当前是否为盘前时段"""
        now = datetime.now()
        market_open = datetime_time(9, 15)

        is_pre_market = now.time() < market_open

        print(f"\n当前时间: {now.strftime('%H:%M:%S')}")
        print(f"盘前时段: {'[是]' if is_pre_market else '[否]（不建议运行盘前测试）'}")

        return is_pre_market

    # ==================== 功能测试 ====================

    def test_functional(self):
        """功能测试模块"""
        print("\n" + "=" * 80)
        print("【1/3】功能测试")
        print("=" * 80)

        functional_results = {
            "total": 0,
            "passed": 0,
            "failed": 0
        }

        # 1.1 数据源健康检查
        self._test_health_check(functional_results)

        # 1.2 历史日K线数据获取
        self._test_historical_kline(functional_results)

        # 1.3 缓存命中率验证
        self._test_cache_hit_rate(functional_results)

        # 1.4 缓存统计验证
        self._test_cache_statistics(functional_results)

        # 1.5 股票名称获取
        self._test_stock_name(functional_results)

        self.report["test_categories"]["功能测试"] = functional_results

        print(f"\n功能测试完成: {functional_results['passed']}/{functional_results['total']} 通过")

    def _test_health_check(self, results: Dict):
        """测试健康检查功能"""
        print("\n[功能测试 1.1] 数据源健康检查")

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
                        "connected_sources": connected_sources,
                        "active_sources": status.get('active_sources', {})
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

    def _test_historical_kline(self, results: Dict):
        """测试历史日K线数据获取"""
        print("\n[功能测试 1.2] 历史日K线数据获取")

        for code, name in TEST_STOCKS[:3]:  # 测试前3只股票
            for period in TEST_PERIODS:
                test_name = f"获取{name}({code})最近{period}天数据"

                try:
                    start_time = time.time()
                    df = self.master.get_kline(code, freq='d', count=period)
                    duration = time.time() - start_time

                    results["total"] += 1

                    if df is not None and len(df) > 0:
                        # 检查数据完整性
                        required_columns = ['date', 'open', 'high', 'low', 'close', 'volume']
                        has_all_columns = all(col in df.columns for col in required_columns)

                        # 检查数据合理性
                        is_valid = (
                            (df['high'] >= df['low']).all() and
                            (df['high'] >= df['open']).all() and
                            (df['high'] >= df['close']).all() and
                            (df['volume'] >= 0).all()
                        )

                        source = df.attrs.get('source', 'unknown')

                        if has_all_columns and is_valid:
                            results["passed"] += 1
                            print(f"   [OK] {test_name}: {len(df)}条, 来源:{source}, {duration:.3f}s")
                            self._log_test(
                                test_name,
                                True,
                                f"成功获取{len(df)}条数据",
                                duration,
                                {
                                    "record_count": len(df),
                                    "data_source": source,
                                    "date_range": f"{df['date'].iloc[0]} ~ {df['date'].iloc[-1]}"
                                }
                            )
                        else:
                            results["failed"] += 1
                            error = "数据不完整" if not has_all_columns else "数据不合理"
                            print(f"   [FAIL] {test_name}: {error}")
                            self._log_test(test_name, False, error, duration)
                    else:
                        results["failed"] += 1
                        print(f"   [FAIL] {test_name}: 返回空数据")
                        self._log_test(test_name, False, "返回空数据", duration)

                except Exception as e:
                    results["total"] += 1
                    results["failed"] += 1
                    error_msg = f"获取数据失败: {str(e)}"
                    print(f"   [FAIL] {test_name}: {error_msg}")
                    self._log_test(test_name, False, error_msg)

    def _test_cache_hit_rate(self, results: Dict):
        """测试缓存命中率"""
        print("\n[功能测试 1.3] 缓存命中率验证")

        test_code = '600519'
        test_name = '贵州茅台'

        try:
            # 第一次请求（可能从网络获取）
            df1 = self.master.get_kline(test_code, freq='d', count=60)
            source1 = df1.attrs.get('source', 'unknown') if df1 is not None else 'none'

            time.sleep(0.5)  # 短暂延迟

            # 第二次请求（应该从缓存获取）
            start_time = time.time()
            df2 = self.master.get_kline(test_code, freq='d', count=60)
            duration = time.time() - start_time
            source2 = df2.attrs.get('source', 'unknown') if df2 is not None else 'none'

            results["total"] += 1

            if source2 == 'cache':
                results["passed"] += 1
                print(f"   [OK] 缓存命中测试: 第1次来源={source1}, 第2次来源={source2}, {duration:.3f}s")
                self._log_test(
                    "缓存命中率验证",
                    True,
                    "第二次请求成功从缓存获取数据",
                    duration,
                    {
                        "first_source": source1,
                        "second_source": source2,
                        "cache_hit": True
                    }
                )
            else:
                results["failed"] += 1
                print(f"   [FAIL] 缓存命中测试: 第2次未从缓存获取 (来源:{source2})")
                self._log_test(
                    "缓存命中率验证",
                    False,
                    f"第二次请求未从缓存获取，来源: {source2}",
                    duration
                )

        except Exception as e:
            results["total"] += 1
            results["failed"] += 1
            error_msg = f"缓存测试失败: {str(e)}"
            print(f"   [FAIL] {error_msg}")
            self._log_test("缓存命中率验证", False, error_msg)

    def _test_cache_statistics(self, results: Dict):
        """测试缓存统计功能"""
        print("\n[功能测试 1.4] 缓存统计验证")

        try:
            start_time = time.time()
            stats = self.master.get_cache_statistics()
            duration = time.time() - start_time

            results["total"] += 1

            if stats and 'total_records' in stats:
                print(f"   缓存记录数: {stats.get('total_records', 0)}")
                print(f"   缓存股票数: {stats.get('stock_count', 0)}")
                print(f"   数据库大小: {stats.get('db_size_mb', 0):.2f} MB")

                results["passed"] += 1
                self._log_test(
                    "缓存统计验证",
                    True,
                    "成功获取缓存统计信息",
                    duration,
                    {
                        "total_records": stats.get('total_records', 0),
                        "stock_count": stats.get('stock_count', 0),
                        "db_size_mb": stats.get('db_size_mb', 0)
                    }
                )
            else:
                results["failed"] += 1
                self._log_test("缓存统计验证", False, "统计信息返回异常", duration)

        except Exception as e:
            results["total"] += 1
            results["failed"] += 1
            error_msg = f"缓存统计失败: {str(e)}"
            print(f"   [FAIL] {error_msg}")
            self._log_test("缓存统计验证", False, error_msg)

    def _test_stock_name(self, results: Dict):
        """测试股票名称获取"""
        print("\n[功能测试 1.5] 股票名称获取")

        for code, expected_name in TEST_STOCKS[:3]:
            try:
                start_time = time.time()
                name = self.master.get_stock_name(code)
                duration = time.time() - start_time

                results["total"] += 1

                if name and name == expected_name:
                    results["passed"] += 1
                    print(f"   [OK] {code}: {name}, {duration:.3f}s")
                    self._log_test(
                        f"获取股票名称({code})",
                        True,
                        f"成功获取: {name}",
                        duration
                    )
                else:
                    results["failed"] += 1
                    print(f"   [FAIL] {code}: 预期={expected_name}, 实际={name}")
                    self._log_test(
                        f"获取股票名称({code})",
                        False,
                        f"名称不匹配: 预期={expected_name}, 实际={name}",
                        duration
                    )

            except Exception as e:
                results["total"] += 1
                results["failed"] += 1
                error_msg = f"获取名称失败: {str(e)}"
                print(f"   [FAIL] {code}: {error_msg}")
                self._log_test(f"获取股票名称({code})", False, error_msg)

    # ==================== 性能测试 ====================

    def test_performance(self):
        """性能测试模块"""
        print("\n" + "=" * 80)
        print("【2/3】性能测试")
        print("=" * 80)

        performance_results = {
            "total": 0,
            "passed": 0,
            "failed": 0,
            "metrics": {}
        }

        # 2.1 缓存性能测试
        self._test_cache_performance(performance_results)

        # 2.2 批量数据获取性能
        self._test_batch_performance(performance_results)

        self.report["test_categories"]["性能测试"] = performance_results

        print(f"\n性能测试完成: {performance_results['passed']}/{performance_results['total']} 通过")

    def _test_cache_performance(self, results: Dict):
        """测试缓存性能"""
        print("\n[性能测试 2.1] 缓存性能测试")

        test_code = '600000'
        test_count = 120

        try:
            # 清除缓存（如果有清除方法）
            # self.master.clear_cache(test_code)  # 假设有这个方法

            # 首次请求（从网络获取）
            start_time = time.time()
            df1 = self.master.get_kline(test_code, freq='d', count=test_count)
            first_request_time = time.time() - start_time
            source1 = df1.attrs.get('source', 'unknown') if df1 is not None else 'none'

            # 第二次请求（从缓存获取）
            start_time = time.time()
            df2 = self.master.get_kline(test_code, freq='d', count=test_count)
            second_request_time = time.time() - start_time
            source2 = df2.attrs.get('source', 'unknown') if df2 is not None else 'none'

            results["total"] += 1

            # 计算性能提升
            if second_request_time > 0:
                improvement = first_request_time / second_request_time

                print(f"   首次请求时间: {first_request_time:.3f}s (来源: {source1})")
                print(f"   缓存请求时间: {second_request_time:.3f}s (来源: {source2})")
                print(f"   性能提升: {improvement:.1f}x")

                # 预期缓存应该至少快10倍
                if source2 == 'cache' and improvement >= 10:
                    results["passed"] += 1
                    results["metrics"]["cache_performance"] = {
                        "first_request_time": f"{first_request_time:.3f}s",
                        "cache_request_time": f"{second_request_time:.3f}s",
                        "improvement": f"{improvement:.1f}x"
                    }
                    self._log_test(
                        "缓存性能测试",
                        True,
                        f"缓存性能提升 {improvement:.1f}x",
                        second_request_time,
                        results["metrics"]["cache_performance"]
                    )
                else:
                    results["failed"] += 1
                    self._log_test(
                        "缓存性能测试",
                        False,
                        f"性能提升不足或未使用缓存 (来源:{source2}, 提升:{improvement:.1f}x)"
                    )
            else:
                results["failed"] += 1
                self._log_test("缓存性能测试", False, "缓存请求时间异常")

        except Exception as e:
            results["total"] += 1
            results["failed"] += 1
            error_msg = f"缓存性能测试失败: {str(e)}"
            print(f"   [FAIL] {error_msg}")
            self._log_test("缓存性能测试", False, error_msg)

    def _test_batch_performance(self, results: Dict):
        """测试批量数据获取性能"""
        print("\n[性能测试 2.2] 批量数据获取性能")

        batch_stocks = TEST_STOCKS[:3]
        batch_times = []

        start_time = time.time()

        for code, name in batch_stocks:
            try:
                t0 = time.time()
                df = self.master.get_kline(code, freq='d', count=60)
                t1 = time.time() - t0

                batch_times.append(t1)
                source = df.attrs.get('source', 'unknown') if df is not None else 'none'
                print(f"   {name}({code}): {t1:.3f}s, 来源:{source}")

            except Exception as e:
                print(f"   [FAIL] {name}({code}): {str(e)}")
                batch_times.append(0)

        total_time = time.time() - start_time
        avg_time = sum(batch_times) / len(batch_times) if batch_times else 0

        results["total"] += 1

        print(f"   批量获取总时间: {total_time:.3f}s")
        print(f"   平均每只股票: {avg_time:.3f}s")

        # 预期平均时间应该小于2秒（盘前主要测试缓存）
        if avg_time < 2.0:
            results["passed"] += 1
            results["metrics"]["batch_performance"] = {
                "total_time": f"{total_time:.3f}s",
                "avg_time": f"{avg_time:.3f}s",
                "stock_count": len(batch_stocks)
            }
            self._log_test(
                "批量数据获取性能",
                True,
                f"平均每只股票 {avg_time:.3f}s",
                total_time,
                results["metrics"]["batch_performance"]
            )
        else:
            results["failed"] += 1
            self._log_test(
                "批量数据获取性能",
                False,
                f"平均时间过长: {avg_time:.3f}s"
            )

    # ==================== 数据质量测试 ====================

    def test_data_quality(self):
        """数据质量测试模块"""
        print("\n" + "=" * 80)
        print("【3/3】数据质量测试")
        print("=" * 80)

        quality_results = {
            "total": 0,
            "passed": 0,
            "failed": 0
        }

        # 3.1 数据完整性检查
        self._test_data_completeness(quality_results)

        # 3.2 数据准确性检查
        self._test_data_accuracy(quality_results)

        # 3.3 历史数据一致性
        self._test_data_consistency(quality_results)

        self.report["test_categories"]["数据质量测试"] = quality_results

        print(f"\n数据质量测试完成: {quality_results['passed']}/{quality_results['total']} 通过")

    def _test_data_completeness(self, results: Dict):
        """测试数据完整性"""
        print("\n[数据质量测试 3.1] 数据完整性检查")

        required_columns = ['date', 'open', 'high', 'low', 'close', 'volume']

        for code, name in TEST_STOCKS[:3]:
            try:
                df = self.master.get_kline(code, freq='d', count=30)

                results["total"] += 1

                if df is not None:
                    missing_columns = [col for col in required_columns if col not in df.columns]
                    null_counts = df[required_columns].isnull().sum()

                    if len(missing_columns) == 0 and null_counts.sum() == 0:
                        results["passed"] += 1
                        print(f"   [OK] {name}({code}): 数据完整, {len(df)}条记录")
                        self._log_test(
                            f"数据完整性({name})",
                            True,
                            "所有必需字段完整，无空值",
                            details={"record_count": len(df)}
                        )
                    else:
                        results["failed"] += 1
                        error = f"缺少列:{missing_columns}" if missing_columns else f"存在空值:{null_counts.sum()}"
                        print(f"   [FAIL] {name}({code}): {error}")
                        self._log_test(f"数据完整性({name})", False, error)
                else:
                    results["failed"] += 1
                    print(f"   [FAIL] {name}({code}): 返回空数据")
                    self._log_test(f"数据完整性({name})", False, "返回空数据")

            except Exception as e:
                results["total"] += 1
                results["failed"] += 1
                error_msg = f"完整性检查失败: {str(e)}"
                print(f"   [FAIL] {name}({code}): {error_msg}")
                self._log_test(f"数据完整性({name})", False, error_msg)

    def _test_data_accuracy(self, results: Dict):
        """测试数据准确性"""
        print("\n[数据质量测试 3.2] 数据准确性检查")

        for code, name in TEST_STOCKS[:3]:
            try:
                df = self.master.get_kline(code, freq='d', count=30)

                results["total"] += 1

                if df is not None and len(df) > 0:
                    # OHLC 逻辑检查
                    ohlc_valid = (
                        (df['high'] >= df['low']).all() and
                        (df['high'] >= df['open']).all() and
                        (df['high'] >= df['close']).all() and
                        (df['low'] <= df['open']).all() and
                        (df['low'] <= df['close']).all()
                    )

                    # 价格范围检查（大于0）
                    price_valid = (
                        (df['open'] > 0).all() and
                        (df['high'] > 0).all() and
                        (df['low'] > 0).all() and
                        (df['close'] > 0).all()
                    )

                    # 成交量检查（非负）
                    volume_valid = (df['volume'] >= 0).all()

                    if ohlc_valid and price_valid and volume_valid:
                        results["passed"] += 1
                        print(f"   [OK] {name}({code}): 数据准确")
                        self._log_test(
                            f"数据准确性({name})",
                            True,
                            "OHLC逻辑正确，价格>0，成交量≥0"
                        )
                    else:
                        results["failed"] += 1
                        errors = []
                        if not ohlc_valid:
                            errors.append("OHLC逻辑错误")
                        if not price_valid:
                            errors.append("价格≤0")
                        if not volume_valid:
                            errors.append("成交量<0")
                        error_msg = ", ".join(errors)
                        print(f"   [FAIL] {name}({code}): {error_msg}")
                        self._log_test(f"数据准确性({name})", False, error_msg)
                else:
                    results["failed"] += 1
                    print(f"   [FAIL] {name}({code}): 返回空数据")
                    self._log_test(f"数据准确性({name})", False, "返回空数据")

            except Exception as e:
                results["total"] += 1
                results["failed"] += 1
                error_msg = f"准确性检查失败: {str(e)}"
                print(f"   [FAIL] {name}({code}): {error_msg}")
                self._log_test(f"数据准确性({name})", False, error_msg)

    def _test_data_consistency(self, results: Dict):
        """测试历史数据一致性"""
        print("\n[数据质量测试 3.3] 历史数据一致性")

        test_code = '600519'
        test_name = '贵州茅台'

        try:
            # 请求两次相同的历史数据
            df1 = self.master.get_kline(test_code, freq='d', count=30)
            time.sleep(0.5)
            df2 = self.master.get_kline(test_code, freq='d', count=30)

            results["total"] += 1

            if df1 is not None and df2 is not None:
                # 比较数据是否一致
                if df1.equals(df2):
                    results["passed"] += 1
                    print(f"   [OK] {test_name}: 历史数据一致")
                    self._log_test(
                        "历史数据一致性",
                        True,
                        "两次请求返回的历史数据完全一致"
                    )
                else:
                    # 进一步检查差异
                    diff_count = (df1 != df2).sum().sum()
                    results["failed"] += 1
                    print(f"   [FAIL] {test_name}: 数据不一致, {diff_count}个差异")
                    self._log_test(
                        "历史数据一致性",
                        False,
                        f"数据不一致，差异数: {diff_count}"
                    )
            else:
                results["failed"] += 1
                print(f"   [FAIL] {test_name}: 数据获取失败")
                self._log_test("历史数据一致性", False, "数据获取失败")

        except Exception as e:
            results["total"] += 1
            results["failed"] += 1
            error_msg = f"一致性检查失败: {str(e)}"
            print(f"   [FAIL] {error_msg}")
            self._log_test("历史数据一致性", False, error_msg)

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
        cache_metrics = self.report["test_categories"].get("性能测试", {}).get("metrics", {})
        self.report["performance_metrics"] = cache_metrics

        # 保存 JSON 报告
        report_dir = os.path.join(test_dir, 'reports')
        os.makedirs(report_dir, exist_ok=True)

        json_file = os.path.join(report_dir, f'pre_market_test_{datetime.now().strftime("%Y%m%d_%H%M%S")}.json')
        with open(json_file, 'w', encoding='utf-8') as f:
            json.dump(self.report, f, ensure_ascii=False, indent=2)

        print(f"\n[OK] JSON报告已保存: {json_file}")

        # 生成 Markdown 报告
        md_file = os.path.join(report_dir, f'pre_market_test_{datetime.now().strftime("%Y%m%d_%H%M%S")}.md')
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

    def _generate_markdown_report(self, filepath: str):
        """生成Markdown格式报告"""

        with open(filepath, 'w', encoding='utf-8') as f:
            f.write("# 盘前回归测试报告\n\n")

            # 测试信息
            f.write("## 测试信息\n\n")
            info = self.report["test_info"]
            f.write(f"- **测试时间**: {info['test_time']}\n")
            f.write(f"- **市场时段**: 盘前 (Pre-Market)\n")
            f.write(f"- **Python版本**: {info['python_version']}\n")
            f.write(f"- **操作系统**: {info['platform']}\n")
            f.write(f"- **测试股票**: {', '.join(info['test_stocks'])}\n")
            f.write(f"- **测试周期**: {info['test_periods']}\n\n")

            # 测试结果
            f.write("## 测试结果\n\n")
            results = self.report["test_results"]
            f.write(f"- **总测试数**: {results['total_tests']}\n")
            f.write(f"- **通过**: {results['passed']} [OK]\n")
            f.write(f"- **失败**: {results['failed']} [FAIL]\n")
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
                        f.write(f"- {key}: {value}\n")
                f.write("\n")

            # 详细测试结果
            f.write("## 详细测试结果\n\n")
            f.write("| 测试项 | 结果 | 说明 | 耗时 |\n")
            f.write("|--------|------|------|------|\n")

            for result in self.report["detailed_results"]:
                status = "[OK]" if result['passed'] else "[FAIL]"
                f.write(f"| {result['test_name']} | {status} | {result['message']} | {result['duration']} |\n")

            # 错误信息
            if self.report["errors"]:
                f.write("\n## 错误信息\n\n")
                for error in self.report["errors"]:
                    f.write(f"### {error['phase']}\n\n")
                    f.write(f"```\n{error['error']}\n```\n\n")

    def run_all_tests(self):
        """运行所有测试"""
        try:
            # 检查市场时段
            if not self._check_market_phase():
                print("\n[WARN]  警告: 当前不是盘前时段，但将继续执行测试")

            self.setup()
            self.test_functional()
            self.test_performance()
            self.test_data_quality()
            self.generate_report()

        except Exception as e:
            print(f"\n[FAIL] 测试执行失败: {str(e)}")
            traceback.print_exc()

        finally:
            self.teardown()


def main():
    """主函数"""
    print("=" * 80)
    print("StockDataMaster 盘前回归测试")
    print("=" * 80)

    test = PreMarketRegressionTest()
    test.run_all_tests()


if __name__ == '__main__':
    main()
