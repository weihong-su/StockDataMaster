# -*- coding: utf-8 -*-
"""
数据源验证脚本 - 对4大数据源进行详尽测评

测试维度:
1. 连接性测试 - 连接成功率、连接时间、稳定性
2. 数据完整性 - 日K线、分钟K线、估值数据、实时tick
3. 数据准确性 - 价格合理性、成交量合理性、OHLC逻辑
4. 性能测试 - 响应时间、并发能力、大批量数据获取
5. 复权准确性 - 前复权数据一致性验证
6. 异常处理 - 错误代码、超时、网络异常
7. 跨源对比 - 多数据源同一时间段数据对比

生成报告:
- 控制台实时输出(UTF-8)
- HTML格式报告
- JSON格式原始数据
"""

import sys
import os
import time
import json
import traceback
from datetime import datetime, timedelta
from typing import Dict, List, Optional, Any, Tuple
from dataclasses import dataclass, field, asdict
from pathlib import Path

import pandas as pd

# 强制UTF-8编码
if sys.platform == 'win32':
    import io
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8', errors='replace')

# 添加项目根目录到路径
test_dir = os.path.dirname(os.path.abspath(__file__))
project_root = os.path.dirname(test_dir)
parent_dir = os.path.dirname(project_root)
if parent_dir not in sys.path:
    sys.path.insert(0, parent_dir)

from StockDataMaster.adapters import AdapterFactory
from StockDataMaster.config import Config


# ============================================================
# 数据结构
# ============================================================

@dataclass
class ConnectionTestResult:
    """连接测试结果"""
    source: str
    success: bool
    connect_time_ms: float
    error_message: str = ""
    retry_count: int = 0


@dataclass
class DataIntegrityResult:
    """数据完整性测试结果"""
    source: str
    data_type: str  # 'kline_day', 'kline_minute', 'valuation', 'tick'
    success: bool
    record_count: int = 0
    columns: List[str] = field(default_factory=list)
    error_message: str = ""


@dataclass
class DataAccuracyResult:
    """数据准确性测试结果"""
    source: str
    data_type: str
    stock_code: str

    # 价格验证
    price_valid: bool = False
    price_min: float = 0.0
    price_max: float = 0.0

    # 成交量验证
    volume_valid: bool = False
    volume_min: float = 0.0
    volume_max: float = 0.0

    # OHLC逻辑验证
    ohlc_valid: bool = False
    ohlc_errors: List[str] = field(default_factory=list)

    # 数据新鲜度
    latest_date: str = ""
    days_old: int = 0
    fresh_data: bool = False

    # 复权验证
    adj_valid: bool = False
    adj_range: Tuple[float, float] = (0.0, 0.0)

    error_message: str = ""


@dataclass
class PerformanceResult:
    """性能测试结果"""
    source: str
    data_type: str

    # 响应时间
    avg_time_ms: float = 0.0
    min_time_ms: float = 0.0
    max_time_ms: float = 0.0
    p50_time_ms: float = 0.0
    p95_time_ms: float = 0.0
    p99_time_ms: float = 0.0

    # 成功率
    success_count: int = 0
    fail_count: int = 0
    success_rate: float = 0.0

    # 吞吐量
    records_per_second: float = 0.0


@dataclass
class CrossSourceComparisonResult:
    """跨源对比结果"""
    stock_code: str
    data_type: str
    date_range: str

    # 各数据源的收盘价
    prices: Dict[str, float] = field(default_factory=dict)

    # 价格差异
    max_diff_pct: float = 0.0
    avg_diff_pct: float = 0.0
    sources_agree: bool = False

    # 数据一致性
    consistent_sources: List[str] = field(default_factory=list)
    inconsistent_sources: Dict[str, str] = field(default_factory=dict)


# ============================================================
# 数据源验证器
# ============================================================

class DataSourceValidator:
    """数据源验证器"""

    def __init__(self):
        self.config = Config()
        self.results: Dict[str, Any] = {
            'timestamp': datetime.now().strftime('%Y-%m-%d %H:%M:%S'),
            'environment': self._get_env_info(),
            'sources': {}
        }

        # 打印彩色消息
        self._print_banner()

        # 测试股票池
        self.test_stocks = {
            'active': ['600519', '000001', '600000'],  # 活跃股票
            'index': ['000001', '399001', '399006'],   # 指数
            'etf': ['510300', '159919'],              # ETF
            'border': ['600036', '601318'],            # 边界股票
        }

        # 测试时间范围
        self.test_date_range = {
            'short': 30,   # 30天
            'medium': 120, # 120天
            'long': 365    # 365天
        }

        # 适配器缓存
        self.adapters: Dict[str, Any] = {}

        # 测试报告
        self.report_data: Dict[str, Any] = {
            'connection': {},
            'integrity': {},
            'accuracy': {},
            'performance': {},
            'cross_source': {}
        }

    def _get_env_info(self) -> Dict[str, str]:
        """获取环境信息"""
        return {
            'python_version': sys.version.split()[0],
            'platform': sys.platform,
            'pandas_version': pd.__version__,
        }

    def _print_banner(self):
        """打印横幅"""
        banner = """
╔══════════════════════════════════════════════════════════════╗
║                  数据源验证脚本 v1.0                          ║
║                  Data Source Validator                        ║
╚══════════════════════════════════════════════════════════════╝
        """
        print(banner)

    def _print_header(self, text: str):
        """打印标题"""
        line = "=" * 60
        print(f"\n{line}")
        print(f"  {text}")
        print(line)

    def _print_subheader(self, text: str):
        """打印子标题"""
        print(f"\n--- {text} ---")

    def _print_success(self, text: str):
        """打印成功消息"""
        print(f"  [OK] {text}")

    def _print_fail(self, text: str):
        """打印失败消息"""
        print(f"  [FAIL] {text}")

    def _print_warning(self, text: str):
        """打印警告消息"""
        print(f"  [WARN] {text}")

    def _print_info(self, text: str):
        """打印信息消息"""
        print(f"  [INFO] {text}")

    def _print_score(self, source: str, score: float, max_score: float = 100):
        """打印评分"""
        pct = score / max_score * 100
        if pct >= 90:
            grade = "A"
        elif pct >= 80:
            grade = "B"
        elif pct >= 70:
            grade = "C"
        elif pct >= 60:
            grade = "D"
        else:
            grade = "F"

        bar_len = int(pct / 100 * 30)
        bar = "█" * bar_len + "░" * (30 - bar_len)
        print(f"\n  [{source}] 综合评分: {bar} {score:.1f}/{max_score} (Grade: {grade})")

    # ============================================================
    # 初始化数据源
    # ============================================================

    def init_adapters(self) -> Dict[str, bool]:
        """初始化所有数据源适配器"""
        self._print_header("1. 初始化数据源适配器")

        sources = ['tushare', 'xtquant', 'mootdx', 'baostock']
        init_results = {}

        for source in sources:
            source_config = self.config.get(f'data_sources.{source}', {})
            enabled = source_config.get('enabled', False)

            if not enabled:
                self._print_warning(f"{source}: 配置中已禁用")
                init_results[source] = None
                continue

            try:
                adapter = AdapterFactory.create_adapter(source, source_config)
                self.adapters[source] = {
                    'adapter': adapter,
                    'config': source_config
                }
                self._print_success(f"{source}: 适配器已创建")
                init_results[source] = True
            except Exception as e:
                self._print_fail(f"{source}: 创建失败 - {e}")
                init_results[source] = False

        return init_results

    # ============================================================
    # 1. 连接性测试
    # ============================================================

    def test_connection(self) -> Dict[str, ConnectionTestResult]:
        """测试所有数据源的连接性"""
        self._print_header("2. 连接性测试")

        results = {}

        for source, adapter_info in self.adapters.items():
            if adapter_info is None:
                continue

            adapter = adapter_info['adapter']
            self._print_subheader(f"测试 {source}")

            # 记录测试结果
            result = ConnectionTestResult(
                source=source,
                success=False,
                connect_time_ms=0.0,
                retry_count=0
            )

            # 多次连接测试
            for retry in range(3):
                try:
                    start_time = time.time()
                    success = adapter.connect()
                    elapsed_ms = (time.time() - start_time) * 1000

                    if success:
                        result.success = True
                        result.connect_time_ms = elapsed_ms
                        result.retry_count = retry
                        self._print_success(
                            f"连接成功 (耗时: {elapsed_ms:.1f}ms, 重试: {retry}次)"
                        )
                        break
                    else:
                        result.retry_count = retry + 1
                        self._print_fail(f"第{retry+1}次连接失败")
                        time.sleep(1)
                except Exception as e:
                    result.retry_count = retry + 1
                    result.error_message = str(e)
                    self._print_fail(f"第{retry+1}次连接异常: {e}")
                    time.sleep(1)

            # 记录到报告
            self.report_data['connection'][source] = asdict(result)
            results[source] = result

        return results

    # ============================================================
    # 2. 数据完整性测试
    # ============================================================

    def test_data_integrity(
        self,
        stock_code: str = '600519',
        test_types: List[str] = None
    ) -> Dict[str, DataIntegrityResult]:
        """测试数据完整性"""
        self._print_header("3. 数据完整性测试")
        self._print_info(f"测试股票: {stock_code}")

        if test_types is None:
            test_types = ['kline_day', 'kline_minute', 'valuation', 'tick']

        results = {}

        for source, adapter_info in self.adapters.items():
            if adapter_info is None:
                continue

            adapter = adapter_info['adapter']
            self._print_subheader(f"测试 {source}")

            source_results = {}

            for data_type in test_types:
                self._print_info(f"  测试 {data_type}...")

                result = DataIntegrityResult(
                    source=source,
                    data_type=data_type,
                    success=False
                )

                try:
                    if data_type == 'kline_day':
                        df = adapter.get_kline(
                            code=stock_code,
                            freq='d',
                            count=30,
                            adjust='qfq'
                        )
                        if df is not None and not df.empty:
                            result.success = True
                            result.record_count = len(df)
                            result.columns = df.columns.tolist()

                    elif data_type == 'kline_minute':
                        df = adapter.get_kline(
                            code=stock_code,
                            freq='5m',
                            count=100,
                            adjust='qfq'
                        )
                        if df is not None and not df.empty:
                            result.success = True
                            result.record_count = len(df)
                            result.columns = df.columns.tolist()

                    elif data_type == 'valuation':
                        df = adapter.get_valuation(
                            code=stock_code,
                            start_date=(datetime.now() - timedelta(days=30)).strftime('%Y-%m-%d'),
                            end_date=datetime.now().strftime('%Y-%m-%d')
                        )
                        if df is not None and not df.empty:
                            result.success = True
                            result.record_count = len(df)
                            result.columns = df.columns.tolist()

                    elif data_type == 'tick':
                        tick = adapter.get_tick(stock_code)
                        if tick is not None:
                            result.success = True
                            result.record_count = 1
                            result.columns = list(tick.keys())

                    if result.success:
                        self._print_success(
                            f"  {data_type}: {result.record_count}条记录, 列: {result.columns}"
                        )
                    else:
                        self._print_fail(f"  {data_type}: 获取失败")

                except Exception as e:
                    result.error_message = str(e)
                    self._print_fail(f"  {data_type}: 异常 - {e}")

                source_results[data_type] = asdict(result)

            self.report_data['integrity'][source] = source_results
            results[source] = source_results

        return results

    # ============================================================
    # 3. 数据准确性测试
    # ============================================================

    def test_data_accuracy(
        self,
        stock_code: str = '600519',
        count: int = 100
    ) -> Dict[str, DataAccuracyResult]:
        """测试数据准确性"""
        self._print_header("4. 数据准确性测试")

        results = {}

        for source, adapter_info in self.adapters.items():
            if adapter_info is None:
                continue

            adapter = adapter_info['adapter']
            self._print_subheader(f"验证 {source}")

            try:
                # 获取日K线数据
                df = adapter.get_kline(
                    code=stock_code,
                    freq='d',
                    count=count,
                    adjust='qfq'
                )

                result = DataAccuracyResult(
                    source=source,
                    data_type='kline_day',
                    stock_code=stock_code
                )

                if df is None or df.empty:
                    result.error_message = "无数据"
                    self._print_fail(f"  无数据返回")
                    results[source] = result
                    continue

                # 3.1 价格验证
                price_cols = ['open', 'high', 'low', 'close']
                prices = {col: df[col].dropna() for col in price_cols if col in df.columns}

                if prices:
                    all_prices = pd.concat(prices.values())
                    result.price_min = float(all_prices.min())
                    result.price_max = float(all_prices.max())
                    result.price_valid = result.price_min > 0.1

                    self._print_info(
                        f"  价格范围: {result.price_min:.2f} - {result.price_max:.2f}"
                    )
                    if result.price_valid:
                        self._print_success(f"  价格验证: 通过")
                    else:
                        self._print_fail(f"  价格验证: 失败 (存在价格<=0.1)")

                # 3.2 成交量验证
                if 'volume' in df.columns:
                    result.volume_min = float(df['volume'].min())
                    result.volume_max = float(df['volume'].max())
                    result.volume_valid = result.volume_min >= 0

                    self._print_info(
                        f"  成交量范围: {result.volume_min:,.0f} - {result.volume_max:,.0f}"
                    )
                    if result.volume_valid:
                        self._print_success(f"  成交量验证: 通过")
                    else:
                        self._print_fail(f"  成交量验证: 失败 (存在负成交量)")

                # 3.3 OHLC逻辑验证
                ohlc_errors = []
                for idx, row in df.iterrows():
                    if not (
                        row['high'] >= row['low'] and
                        row['high'] >= row['open'] and
                        row['high'] >= row['close'] and
                        row['low'] <= row['open'] and
                        row['low'] <= row['close']
                    ):
                        ohlc_errors.append({
                            'date': row['date'],
                            'open': row['open'],
                            'high': row['high'],
                            'low': row['low'],
                            'close': row['close']
                        })

                result.ohlc_errors = [str(e) for e in ohlc_errors[:5]]  # 只保留前5个
                result.ohlc_valid = len(ohlc_errors) == 0

                if result.ohlc_valid:
                    self._print_success(f"  OHLC逻辑: 全部正确")
                else:
                    self._print_fail(f"  OHLC逻辑: {len(ohlc_errors)}个错误")
                    for err in ohlc_errors[:3]:
                        self._print_info(f"    {err['date']}: O={err['open']:.2f} H={err['high']:.2f} L={err['low']:.2f} C={err['close']:.2f}")

                # 3.4 数据新鲜度
                latest_date = pd.to_datetime(df['date'].iloc[-1])
                days_old = (datetime.now() - latest_date).days
                result.latest_date = latest_date.strftime('%Y-%m-%d')
                result.days_old = days_old
                result.fresh_data = days_old <= 5

                self._print_info(f"  最新数据: {result.latest_date} ({days_old}天前)")
                if result.fresh_data:
                    self._print_success(f"  新鲜度: 正常")
                else:
                    self._print_warning(f"  新鲜度: 数据可能过旧")

                # 3.5 复权因子验证
                if 'factor' in df.columns:
                    factors = df['factor'].dropna()
                    if not factors.empty:
                        result.adj_range = (float(factors.min()), float(factors.max()))
                        result.adj_valid = factors.min() > 0
                        self._print_info(
                            f"  复权因子: {result.adj_range[0]:.4f} - {result.adj_range[1]:.4f}"
                        )

            except Exception as e:
                result = DataAccuracyResult(
                    source=source,
                    data_type='kline_day',
                    stock_code=stock_code,
                    error_message=str(e)
                )
                self._print_fail(f"  异常: {e}")

            results[source] = result
            self.report_data['accuracy'][source] = asdict(result)

        return results

    # ============================================================
    # 4. 性能测试
    # ============================================================

    def test_performance(
        self,
        stock_code: str = '600519',
        iterations: int = 10
    ) -> Dict[str, PerformanceResult]:
        """测试数据获取性能"""
        self._print_header("5. 性能测试")
        self._print_info(f"测试股票: {stock_code}, 迭代次数: {iterations}")

        results = {}

        for source, adapter_info in self.adapters.items():
            if adapter_info is None:
                continue

            adapter = adapter_info['adapter']
            self._print_subheader(f"测试 {source}")

            times = []
            success_count = 0
            fail_count = 0

            for i in range(iterations):
                try:
                    start_time = time.time()
                    df = adapter.get_kline(
                        code=stock_code,
                        freq='d',
                        count=30,
                        adjust='qfq'
                    )
                    elapsed_ms = (time.time() - start_time) * 1000

                    times.append(elapsed_ms)

                    if df is not None and not df.empty:
                        success_count += 1
                    else:
                        fail_count += 1

                    # 间隔
                    time.sleep(0.1)

                except Exception as e:
                    fail_count += 1
                    self._print_fail(f"  第{i+1}次: 异常 - {e}")

            # 计算统计
            result = PerformanceResult(
                source=source,
                data_type='kline_day'
            )

            if times:
                times_sorted = sorted(times)
                result.avg_time_ms = sum(times) / len(times)
                result.min_time_ms = min(times)
                result.max_time_ms = max(times)
                result.p50_time_ms = times_sorted[len(times) // 2]
                result.p95_time_ms = times_sorted[int(len(times) * 0.95)]
                result.p99_time_ms = times_sorted[int(len(times) * 0.99)]
                result.success_count = success_count
                result.fail_count = fail_count
                result.success_rate = success_count / iterations * 100

                # 计算吞吐量
                if result.avg_time_ms > 0:
                    result.records_per_second = (30 / result.avg_time_ms) * 1000

                self._print_info(f"  响应时间:")
                self._print_info(f"    平均: {result.avg_time_ms:.1f}ms")
                self._print_info(f"    P50:  {result.p50_time_ms:.1f}ms")
                self._print_info(f"    P95:  {result.p95_time_ms:.1f}ms")
                self._print_info(f"    P99:  {result.max_time_ms:.1f}ms")
                self._print_info(f"  成功率: {result.success_rate:.0f}% ({success_count}/{iterations})")
                self._print_info(f"  吞吐量: {result.records_per_second:.1f} records/s")

                if result.success_rate >= 90:
                    self._print_success(f"  性能评分: 优秀")
                elif result.success_rate >= 70:
                    self._print_success(f"  性能评分: 良好")
                else:
                    self._print_warning(f"  性能评分: 一般")

            else:
                self._print_fail(f"  无有效测试数据")
                result.success_rate = 0

            results[source] = result
            self.report_data['performance'][source] = asdict(result)

        return results

    # ============================================================
    # 5. 跨源数据对比
    # ============================================================

    def test_cross_source_comparison(
        self,
        stock_code: str = '600519',
        count: int = 30
    ) -> List[CrossSourceComparisonResult]:
        """跨数据源数据对比"""
        self._print_header("6. 跨源数据对比")
        self._print_info(f"测试股票: {stock_code}")

        # 收集各数据源数据
        source_data = {}

        for source, adapter_info in self.adapters.items():
            if adapter_info is None:
                continue

            adapter = adapter_info['adapter']
            try:
                df = adapter.get_kline(
                    code=stock_code,
                    freq='d',
                    count=count,
                    adjust='qfq'
                )
                if df is not None and not df.empty:
                    source_data[source] = df
                    self._print_success(f"  {source}: 获取到 {len(df)} 条数据")
                else:
                    self._print_fail(f"  {source}: 无数据")
            except Exception as e:
                self._print_fail(f"  {source}: {e}")

        if len(source_data) < 2:
            self._print_warning("  数据源不足,无法进行对比")
            return []

        # 按日期对比
        self._print_subheader("收盘价对比 (最新5条)")

        # 找到共同日期
        common_dates = None
        for source, df in source_data.items():
            df_dates = set(df['date'].tolist())
            if common_dates is None:
                common_dates = df_dates
            else:
                common_dates = common_dates.intersection(df_dates)

        if not common_dates:
            self._print_warning("  无共同日期")
            return []

        # 获取最新5个共同日期
        common_dates = sorted(list(common_dates))[-5:]

        # 构建对比结果
        results = []

        for date in common_dates:
            result = CrossSourceComparisonResult(
                stock_code=stock_code,
                data_type='kline_day',
                date_range=f"{common_dates[0]} 至 {common_dates[-1]}"
            )

            prices = {}
            for source, df in source_data.items():
                row = df[df['date'] == date]
                if not row.empty:
                    close_price = row['close'].iloc[0]
                    prices[source] = close_price

            result.prices = prices

            # 计算价格差异
            if len(prices) >= 2:
                price_values = list(prices.values())
                max_price = max(price_values)
                min_price = min(price_values)

                if min_price > 0:
                    result.max_diff_pct = abs(max_price - min_price) / min_price * 100
                    result.avg_diff_pct = result.max_diff_pct / 2

                result.sources_agree = result.max_diff_pct < 1.0  # 差异小于1%视为一致

                # 标记一致/不一致的数据源
                if result.sources_agree:
                    result.consistent_sources = list(prices.keys())
                else:
                    for src, price in prices.items():
                        if abs(price - sum(price_values) / len(price_values)) > 0.5:
                            result.inconsistent_sources[src] = f"价格异常: {price:.2f}"

            results.append(result)

            # 打印对比
            price_str = " | ".join([f"{src}: {p:.2f}" for src, p in prices.items()])
            diff_str = f"差异: {result.max_diff_pct:.3f}%" if result.max_diff_pct > 0 else ""

            if result.sources_agree:
                self._print_success(f"  {date}: {price_str} {diff_str}")
            else:
                self._print_warning(f"  {date}: {price_str} {diff_str}")

        return results

    # ============================================================
    # 6. 批量股票测试
    # ============================================================

    def test_batch_stocks(
        self,
        stock_list: List[str] = None,
        data_type: str = 'kline_day'
    ) -> Dict[str, Dict[str, Any]]:
        """批量股票测试"""
        if stock_list is None:
            stock_list = self.test_stocks.get('active', ['600519', '000001', '600000'])

        self._print_header("7. 批量股票测试")
        self._print_info(f"测试数据: {data_type}")
        self._print_info(f"股票数量: {len(stock_list)}")

        results = {}

        for source, adapter_info in self.adapters.items():
            if adapter_info is None:
                continue

            adapter = adapter_info['adapter']
            self._print_subheader(f"测试 {source}")

            success_count = 0
            fail_count = 0
            stock_results = {}

            for stock_code in stock_list:
                try:
                    if data_type == 'kline_day':
                        df = adapter.get_kline(code=stock_code, freq='d', count=10)
                    elif data_type == 'kline_minute':
                        df = adapter.get_kline(code=stock_code, freq='5m', count=50)
                    else:
                        df = None

                    if df is not None and not df.empty:
                        success_count += 1
                        stock_results[stock_code] = {
                            'success': True,
                            'record_count': len(df)
                        }
                        self._print_success(f"  {stock_code}: {len(df)}条")
                    else:
                        fail_count += 1
                        stock_results[stock_code] = {
                            'success': False,
                            'error': 'No data'
                        }
                        self._print_fail(f"  {stock_code}: 无数据")

                except Exception as e:
                    fail_count += 1
                    stock_results[stock_code] = {
                        'success': False,
                        'error': str(e)
                    }
                    self._print_fail(f"  {stock_code}: {e}")

            success_rate = success_count / len(stock_list) * 100 if stock_list else 0

            results[source] = {
                'total': len(stock_list),
                'success': success_count,
                'fail': fail_count,
                'success_rate': success_rate,
                'stocks': stock_results
            }

            if success_rate >= 90:
                self._print_success(f"  批量测试成功率: {success_rate:.0f}%")
            elif success_rate >= 70:
                self._print_info(f"  批量测试成功率: {success_rate:.0f}%")
            else:
                self._print_warning(f"  批量测试成功率: {success_rate:.0f}%")

        return results

    # ============================================================
    # 7. 综合评分
    # ============================================================

    def calculate_scores(self) -> Dict[str, float]:
        """计算各数据源综合评分"""
        self._print_header("8. 综合评分计算")

        scores = {}

        for source in self.adapters.keys():
            if self.adapters[source] is None:
                scores[source] = 0.0
                continue

            # 各项权重
            weights = {
                'connection': 0.15,    # 连接性
                'integrity': 0.20,     # 完整性
                'accuracy': 0.25,      # 准确性
                'performance': 0.20,   # 性能
                'batch': 0.20          # 批量成功率
            }

            source_score = 0.0

            # 连接性评分
            conn = self.report_data.get('connection', {}).get(source, {})
            if conn:
                conn_score = 100 if conn.get('success', False) else 0
                # 响应时间加权
                if conn.get('connect_time_ms', 0) > 0:
                    time_ms = conn['connect_time_ms']
                    if time_ms < 1000:
                        conn_score = 100
                    elif time_ms < 3000:
                        conn_score = 90
                    elif time_ms < 5000:
                        conn_score = 80
                    else:
                        conn_score = 60
                source_score += conn_score * weights['connection']

            # 完整性评分
            integ = self.report_data.get('integrity', {}).get(source, {})
            if integ:
                total_tests = len(integ)
                passed_tests = sum(1 for v in integ.values() if v.get('success', False))
                source_score += (passed_tests / total_tests * 100 if total_tests > 0 else 0) * weights['integrity']

            # 准确性评分
            acc = self.report_data.get('accuracy', {}).get(source, {})
            if acc:
                acc_score = 100
                if not acc.get('price_valid', True):
                    acc_score -= 30
                if not acc.get('volume_valid', True):
                    acc_score -= 20
                if not acc.get('ohlc_valid', True):
                    acc_score -= 30
                if not acc.get('fresh_data', True):
                    acc_score -= 20
                source_score += max(0, acc_score) * weights['accuracy']

            # 性能评分
            perf = self.report_data.get('performance', {}).get(source, {})
            if perf:
                perf_score = perf.get('success_rate', 0)
                # 响应时间加权
                avg_time = perf.get('avg_time_ms', 999999)
                if avg_time < 500:
                    perf_score = min(100, perf_score + 10)
                elif avg_time > 3000:
                    perf_score = max(0, perf_score - 20)
                source_score += perf_score * weights['performance']

            scores[source] = min(100, max(0, source_score))

        # 打印评分
        for source, score in scores.items():
            self._print_score(source, score)

        return scores

    # ============================================================
    # 8. 生成报告
    # ============================================================

    def generate_report(self, output_dir: str = None) -> str:
        """生成测试报告"""
        if output_dir is None:
            output_dir = os.path.join(test_dir, 'reports')

        os.makedirs(output_dir, exist_ok=True)

        timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')

        # 生成JSON报告
        json_path = os.path.join(output_dir, f'datasource_validation_{timestamp}.json')

        # 计算评分
        scores = self.calculate_scores()

        # 构建完整报告
        full_report = {
            'timestamp': self.results['timestamp'],
            'environment': self.results['environment'],
            'summary': {
                'total_sources': len([a for a in self.adapters.values() if a is not None]),
                'scores': scores
            },
            'reports': self.report_data
        }

        # 保存JSON
        with open(json_path, 'w', encoding='utf-8') as f:
            json.dump(full_report, f, ensure_ascii=False, indent=2, default=str)

        self._print_info(f"JSON报告已保存: {json_path}")

        # 生成HTML报告
        html_path = os.path.join(output_dir, f'datasource_validation_{timestamp}.html')
        self._generate_html_report(html_path, full_report)
        self._print_info(f"HTML报告已保存: {html_path}")

        return json_path

    def _generate_html_report(self, html_path: str, report: Dict):
        """生成HTML报告"""
        scores = report['summary']['scores']

        html = f"""<!DOCTYPE html>
<html lang="zh-CN">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>数据源验证报告 - {report['timestamp']}</title>
    <style>
        body {{
            font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, 'Helvetica Neue', Arial, sans-serif;
            max-width: 1200px;
            margin: 0 auto;
            padding: 20px;
            background: #f5f7fa;
            color: #333;
        }}
        .header {{
            background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
            color: white;
            padding: 30px;
            border-radius: 10px;
            margin-bottom: 30px;
        }}
        .header h1 {{
            margin: 0 0 10px 0;
        }}
        .header .timestamp {{
            opacity: 0.8;
            font-size: 14px;
        }}
        .card {{
            background: white;
            border-radius: 10px;
            padding: 20px;
            margin-bottom: 20px;
            box-shadow: 0 2px 4px rgba(0,0,0,0.1);
        }}
        .card h2 {{
            margin-top: 0;
            color: #667eea;
            border-bottom: 2px solid #f0f0f0;
            padding-bottom: 10px;
        }}
        .score-grid {{
            display: grid;
            grid-template-columns: repeat(auto-fit, minmax(200px, 1fr));
            gap: 15px;
        }}
        .score-item {{
            background: #f8f9fa;
            padding: 15px;
            border-radius: 8px;
            text-align: center;
        }}
        .score-item .source {{
            font-weight: bold;
            font-size: 18px;
            margin-bottom: 10px;
        }}
        .score-item .score {{
            font-size: 36px;
            font-weight: bold;
            margin-bottom: 5px;
        }}
        .score-item .grade {{
            font-size: 14px;
            opacity: 0.7;
        }}
        .score-item.excellent .score {{ color: #28a745; }}
        .score-item.good .score {{ color: #17a2b8; }}
        .score-item.average .score {{ color: #ffc107; }}
        .score-item.poor .score {{ color: #dc3545; }}
        table {{
            width: 100%;
            border-collapse: collapse;
        }}
        th, td {{
            padding: 12px;
            text-align: left;
            border-bottom: 1px solid #eee;
        }}
        th {{
            background: #f8f9fa;
            font-weight: 600;
        }}
        .status-ok {{ color: #28a745; }}
        .status-fail {{ color: #dc3545; }}
        .status-warn {{ color: #ffc107; }}
        .metric {{
            display: inline-block;
            background: #e9ecef;
            padding: 5px 10px;
            border-radius: 4px;
            margin: 5px;
            font-size: 12px;
        }}
        .footer {{
            text-align: center;
            margin-top: 30px;
            opacity: 0.6;
            font-size: 12px;
        }}
    </style>
</head>
<body>
    <div class="header">
        <h1>数据源验证报告</h1>
        <div>生成时间: {report['timestamp']}</div>
        <div class="timestamp">Python: {report['environment']['python_version']} | Pandas: {report['environment']['pandas_version']}</div>
    </div>

    <div class="card">
        <h2>综合评分</h2>
        <div class="score-grid">
"""

        for source, score in scores.items():
            if score >= 90:
                grade = 'A'
                cls = 'excellent'
            elif score >= 80:
                grade = 'B'
                cls = 'good'
            elif score >= 70:
                grade = 'C'
                cls = 'average'
            else:
                grade = 'D/F'
                cls = 'poor'

            source_display = {
                'tushare': 'Tushare',
                'xtquant': 'Xtquant (QMT)',
                'mootdx': 'Mootdx (通达信)',
                'baostock': 'Baostock'
            }.get(source, source)

            html += f"""
            <div class="score-item {cls}">
                <div class="source">{source_display}</div>
                <div class="score">{score:.1f}</div>
                <div class="grade">Grade: {grade}</div>
            </div>
"""

        html += """
        </div>
    </div>

    <div class="card">
        <h2>连接性测试</h2>
        <table>
            <tr>
                <th>数据源</th>
                <th>状态</th>
                <th>响应时间</th>
                <th>重试次数</th>
                <th>备注</th>
            </tr>
"""

        for source, data in report['reports'].get('connection', {}).items():
            status = '<span class="status-ok">成功</span>' if data.get('success') else '<span class="status-fail">失败</span>'
            time_ms = data.get('connect_time_ms', 0)
            retry = data.get('retry_count', 0)
            error = data.get('error_message', '-')

            html += f"""
            <tr>
                <td>{source}</td>
                <td>{status}</td>
                <td>{time_ms:.1f} ms</td>
                <td>{retry}</td>
                <td>{error}</td>
            </tr>
"""

        html += """
        </table>
    </div>

    <div class="card">
        <h2>数据完整性</h2>
        <table>
            <tr>
                <th>数据源</th>
                <th>数据类型</th>
                <th>状态</th>
                <th>记录数</th>
                <th>列信息</th>
            </tr>
"""

        for source, data in report['reports'].get('integrity', {}).items():
            for dtype, info in data.items():
                status = '<span class="status-ok">通过</span>' if info.get('success') else '<span class="status-fail">失败</span>'
                count = info.get('record_count', 0)
                cols = ', '.join(info.get('columns', [])) if info.get('columns') else '-'

                html += f"""
            <tr>
                <td>{source}</td>
                <td>{dtype}</td>
                <td>{status}</td>
                <td>{count}</td>
                <td><small>{cols}</small></td>
            </tr>
"""

        html += """
        </table>
    </div>

    <div class="card">
        <h2>数据准确性</h2>
        <table>
            <tr>
                <th>数据源</th>
                <th>价格范围</th>
                <th>成交量范围</th>
                <th>OHLC逻辑</th>
                <th>新鲜度</th>
            </tr>
"""

        for source, data in report['reports'].get('accuracy', {}).items():
            price_range = f"{data.get('price_min', 0):.2f} - {data.get('price_max', 0):.2f}" if data.get('price_min') else '-'
            volume_range = f"{data.get('volume_min', 0):,.0f} - {data.get('volume_max', 0):,.0f}" if data.get('volume_min') else '-'
            ohlc = '<span class="status-ok">正确</span>' if data.get('ohlc_valid') else '<span class="status-fail">错误</span>'
            fresh = '<span class="status-ok">新鲜</span>' if data.get('fresh_data') else '<span class="status-warn">过旧</span>'

            html += f"""
            <tr>
                <td>{source}</td>
                <td>{price_range}</td>
                <td>{volume_range}</td>
                <td>{ohlc}</td>
                <td>{fresh}</td>
            </tr>
"""

        html += """
        </table>
    </div>

    <div class="card">
        <h2>性能测试</h2>
        <table>
            <tr>
                <th>数据源</th>
                <th>平均响应</th>
                <th>P50</th>
                <th>P95</th>
                <th>P99</th>
                <th>成功率</th>
                <th>吞吐量</th>
            </tr>
"""

        for source, data in report['reports'].get('performance', {}).items():
            avg = data.get('avg_time_ms', 0)
            p50 = data.get('p50_time_ms', 0)
            p95 = data.get('p95_time_ms', 0)
            p99 = data.get('p99_time_ms', 0)
            rate = data.get('success_rate', 0)
            tput = data.get('records_per_second', 0)

            html += f"""
            <tr>
                <td>{source}</td>
                <td>{avg:.1f} ms</td>
                <td>{p50:.1f} ms</td>
                <td>{p95:.1f} ms</td>
                <td>{p99:.1f} ms</td>
                <td>{rate:.0f}%</td>
                <td>{tput:.1f}/s</td>
            </tr>
"""

        html += f"""
        </table>
    </div>

    <div class="footer">
        Generated by DataSourceValidator | {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}
    </div>
</body>
</html>
"""

        with open(html_path, 'w', encoding='utf-8') as f:
            f.write(html)

    # ============================================================
    # 运行所有测试
    # ============================================================

    def run_all_tests(self):
        """运行所有测试"""
        self._print_header("开始全面数据源验证")

        try:
            # 1. 初始化适配器
            init_results = self.init_adapters()

            # 2. 连接性测试
            self.test_connection()

            # 3. 数据完整性测试
            self.test_data_integrity(stock_code='600519')

            # 4. 数据准确性测试
            self.test_data_accuracy(stock_code='600519', count=100)

            # 5. 性能测试
            self.test_performance(stock_code='600519', iterations=10)

            # 6. 跨源对比
            self.test_cross_source_comparison(stock_code='600519', count=30)

            # 7. 批量股票测试
            self.test_batch_stocks(
                stock_list=['600519', '000001', '600000', '600036', '601318'],
                data_type='kline_day'
            )

            # 8. 生成报告
            self._print_header("9. 生成报告")
            report_path = self.generate_report()
            self._print_success(f"报告已生成: {report_path}")

            # 最终评分
            self._print_header("测试完成 - 最终评分")
            scores = self.calculate_scores()

            print("\n" + "=" * 60)
            print("  测试总结")
            print("=" * 60)
            for source, score in sorted(scores.items(), key=lambda x: x[1], reverse=True):
                source_display = {
                    'tushare': 'Tushare',
                    'xtquant': 'Xtquant',
                    'mootdx': 'Mootdx',
                    'baostock': 'Baostock'
                }.get(source, source)
                print(f"  {source_display:12s}: {score:6.1f}/100")
            print("=" * 60)

        except Exception as e:
            self._print_fail(f"测试异常: {e}")
            traceback.print_exc()


# ============================================================
# 主函数
# ============================================================

def main():
    """主函数"""
    print("\n" + "=" * 60)
    print("  数据源验证脚本")
    print("  Data Source Validator")
    print("=" * 60)

    validator = DataSourceValidator()
    validator.run_all_tests()

    print("\n按任意键退出...")
    try:
        input()
    except:
        pass


if __name__ == '__main__':
    main()
