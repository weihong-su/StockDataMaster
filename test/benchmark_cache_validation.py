"""
日线数据缓存验证基准测试

测试目标:
1. 1000只股票的最近500个日K线数据
2. 统计所有数据源的性能指标:
   - 响应时间 (平均/最小/最大/P95/P99)
   - 有效性 (成功率/失败率/数据完整性)
   - 鲁棒性 (错误恢复/重试成功率)
3. 验证fallback机制的有效性
4. 缓存命中率和双源校验统计

运行方式:
    python -X utf8 test/benchmark_cache_validation.py
"""

import sys
import os
import time
import json
import logging
from datetime import datetime, timedelta
from typing import Dict, List, Any, Optional
from collections import defaultdict
import pandas as pd
import numpy as np

# 添加项目根目录到路径
test_dir = os.path.dirname(os.path.abspath(__file__))
project_root = os.path.dirname(test_dir)
parent_dir = os.path.dirname(project_root)
sys.path.insert(0, parent_dir)

from StockDataMaster import StockDataMaster


class BenchmarkStats:
    """基准测试统计类"""

    def __init__(self):
        self.response_times = defaultdict(list)  # {source: [times]}
        self.success_counts = defaultdict(int)   # {source: count}
        self.failure_counts = defaultdict(int)   # {source: count}
        self.error_types = defaultdict(lambda: defaultdict(int))  # {source: {error_type: count}}
        self.data_quality = defaultdict(list)    # {source: [quality_scores]}
        self.fallback_events = []                # [{from, to, reason, timestamp}]
        self.cache_hits = 0
        self.cache_misses = 0
        self.incremental_cache_hits = 0  # 增量缓存命中（已验证数据跳过校验）
        self.incremental_validations = 0  # 增量校验（新数据需要校验）
        self.validation_results = {
            'passed': 0,
            'failed': 0,
            'skipped': 0
        }
        self.validation_sources_used = defaultdict(int)  # {source: count} 校验源使用次数
        self.retry_stats = defaultdict(lambda: {'attempts': 0, 'successes': 0})
        self.board_stats = {  # 按板块统计
            'sh_main': {'success': 0, 'failure': 0},  # 上海主板 600xxx
            'sz_main': {'success': 0, 'failure': 0},  # 深圳主板 000xxx
            'chinext': {'success': 0, 'failure': 0}   # 创业板 300xxx
        }

    def add_response_time(self, source: str, time_ms: float):
        """记录响应时间"""
        self.response_times[source].append(time_ms)

    def add_success(self, source: str):
        """记录成功"""
        self.success_counts[source] += 1

    def add_failure(self, source: str, error_type: str = 'unknown'):
        """记录失败"""
        self.failure_counts[source] += 1
        self.error_types[source][error_type] += 1

    def add_data_quality(self, source: str, score: float):
        """记录数据质量分数 (0-100)"""
        self.data_quality[source].append(score)

    def add_fallback_event(self, from_source: str, to_source: str, reason: str):
        """记录fallback事件"""
        self.fallback_events.append({
            'from': from_source,
            'to': to_source,
            'reason': reason,
            'timestamp': datetime.now().isoformat()
        })

    def add_retry(self, source: str, success: bool):
        """记录重试"""
        self.retry_stats[source]['attempts'] += 1
        if success:
            self.retry_stats[source]['successes'] += 1

    def calculate_percentile(self, data: List[float], percentile: float) -> float:
        """计算百分位数"""
        if not data:
            return 0.0
        return np.percentile(data, percentile)

    def get_summary(self) -> Dict[str, Any]:
        """生成统计摘要"""
        summary = {
            'timestamp': datetime.now().isoformat(),
            'sources': {},
            'cache': {
                'hits': self.cache_hits,
                'misses': self.cache_misses,
                'hit_rate': self.cache_hits / (self.cache_hits + self.cache_misses) * 100
                           if (self.cache_hits + self.cache_misses) > 0 else 0,
                'incremental_hits': self.incremental_cache_hits,
                'incremental_validations': self.incremental_validations,
                'incremental_hit_rate': self.incremental_cache_hits / (self.incremental_cache_hits + self.incremental_validations) * 100
                                       if (self.incremental_cache_hits + self.incremental_validations) > 0 else 0
            },
            'validation': self.validation_results.copy(),
            'validation_sources': dict(self.validation_sources_used),
            'board_stats': self.board_stats.copy(),
            'fallback': {
                'total_events': len(self.fallback_events),
                'events': self.fallback_events
            }
        }

        # 每个数据源的统计
        all_sources = set(list(self.response_times.keys()) +
                         list(self.success_counts.keys()) +
                         list(self.failure_counts.keys()))

        for source in all_sources:
            times = self.response_times[source]
            successes = self.success_counts[source]
            failures = self.failure_counts[source]
            total = successes + failures
            quality_scores = self.data_quality[source]

            source_stats = {
                'total_requests': total,
                'successes': successes,
                'failures': failures,
                'success_rate': (successes / total * 100) if total > 0 else 0,
                'response_time': {
                    'count': len(times),
                    'mean': np.mean(times) if times else 0,
                    'min': np.min(times) if times else 0,
                    'max': np.max(times) if times else 0,
                    'p50': self.calculate_percentile(times, 50),
                    'p95': self.calculate_percentile(times, 95),
                    'p99': self.calculate_percentile(times, 99),
                    'std': np.std(times) if times else 0
                },
                'data_quality': {
                    'count': len(quality_scores),
                    'mean': np.mean(quality_scores) if quality_scores else 0,
                    'min': np.min(quality_scores) if quality_scores else 0,
                    'max': np.max(quality_scores) if quality_scores else 0
                },
                'errors': dict(self.error_types[source]),
                'retry': dict(self.retry_stats[source])
            }

            summary['sources'][source] = source_stats

        return summary


class BenchmarkTest:
    """基准测试类"""

    def __init__(self, config_path: Optional[str] = None):
        self.logger = self._setup_logging()
        self.logger.info("=" * 80)
        self.logger.info("日线数据缓存验证基准测试")
        self.logger.info("=" * 80)

        # 初始化StockDataMaster
        self.master = StockDataMaster(config_path)
        self.stats = BenchmarkStats()

        # 测试参数
        self.num_stocks = 1000
        self.num_klines = 500

    def _setup_logging(self) -> logging.Logger:
        """设置日志"""
        log_dir = os.path.join(project_root, 'logs')
        os.makedirs(log_dir, exist_ok=True)

        log_file = os.path.join(log_dir, f'benchmark_{datetime.now().strftime("%Y%m%d_%H%M%S")}.log')

        logging.basicConfig(
            level=logging.INFO,
            format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
            handlers=[
                logging.FileHandler(log_file, encoding='utf-8'),
                logging.StreamHandler()
            ],
            force=True
        )

        return logging.getLogger("BenchmarkTest")

    def generate_stock_codes(self) -> List[str]:
        """
        生成测试用股票代码列表

        策略: 从baostock获取真实的股票列表,避免测试已退市/不存在的股票
        """
        self.logger.info(f"从数据源获取真实股票列表...")

        codes = []

        try:
            # 尝试从baostock获取股票列表
            import baostock as bs

            # 登录
            lg = bs.login()
            if lg.error_code != '0':
                self.logger.warning(f"baostock登录失败: {lg.error_msg}, 使用预定义列表")
                return self._get_predefined_stock_codes()

            # 获取沪深A股列表
            rs = bs.query_stock_basic()
            if rs.error_code != '0':
                self.logger.warning(f"获取股票列表失败: {rs.error_msg}, 使用预定义列表")
                bs.logout()
                return self._get_predefined_stock_codes()

            # 解析结果
            while (rs.error_code == '0') & rs.next():
                row = rs.get_row_data()
                code = row[0]  # 股票代码 (格式: sh.600000)

                # 去掉前缀,只保留6位代码
                if '.' in code:
                    code = code.split('.')[1]

                # 只要沪深主板和创业板 (6/0/3开头)
                if code.startswith(('6', '0', '3')):
                    codes.append(code)

                # 达到目标数量就停止
                if len(codes) >= self.num_stocks:
                    break

            bs.logout()

            if len(codes) < self.num_stocks:
                self.logger.warning(f"只获取到{len(codes)}只股票,少于目标{self.num_stocks}只")

            self.logger.info(f"从baostock获取完成: {len(codes)}只股票")
            return codes

        except Exception as e:
            self.logger.warning(f"从baostock获取股票列表失败: {e}, 使用预定义列表")
            return self._get_predefined_stock_codes()

    def _get_predefined_stock_codes(self) -> List[str]:
        """
        获取预定义的股票代码列表 (活跃股票)

        当无法从数据源获取时使用
        """
        self.logger.info(f"使用预定义股票列表...")

        # 精选活跃股票 (确保存在且有交易)
        predefined_codes = [
            # 上海主板 - 大盘蓝筹
            '600000', '600004', '600009', '600010', '600011', '600015', '600016', '600018', '600019', '600028',
            '600029', '600030', '600031', '600036', '600048', '600050', '600104', '600109', '600111', '600115',
            '600150', '600170', '600177', '600188', '600196', '600208', '600219', '600221', '600276', '600297',
            '600309', '600315', '600332', '600340', '600346', '600352', '600362', '600369', '600372', '600376',
            '600380', '600383', '600390', '600398', '600406', '600415', '600436', '600438', '600482', '600487',
            '600489', '600498', '600499', '600516', '600519', '600522', '600547', '600570', '600585', '600588',
            '600606', '600637', '600660', '600663', '600674', '600690', '600703', '600705', '600741', '600745',
            '600760', '600795', '600809', '600837', '600848', '600867', '600886', '600887', '600893', '600900',
            '600905', '600919', '600926', '600958', '600968', '600977', '600989', '600999', '601006', '601009',
            '601012', '601018', '601021', '601066', '601088', '601098', '601099', '601100', '601111', '601117',
            '601128', '601138', '601155', '601166', '601169', '601186', '601198', '601211', '601216', '601225',
            '601228', '601229', '601231', '601236', '601238', '601288', '601318', '601328', '601336', '601360',
            '601377', '601390', '601398', '601555', '601600', '601601', '601607', '601618', '601628', '601633',
            '601658', '601668', '601669', '601688', '601698', '601727', '601766', '601788', '601800', '601808',
            '601818', '601828', '601838', '601857', '601866', '601868', '601872', '601877', '601878', '601881',
            '601888', '601898', '601899', '601901', '601916', '601919', '601933', '601939', '601958', '601985',
            '601988', '601989', '601990', '601991', '601992', '601995', '601997', '601998',

            # 深圳主板
            '000001', '000002', '000004', '000006', '000008', '000009', '000012', '000021', '000025', '000027',
            '000028', '000031', '000039', '000050', '000060', '000061', '000063', '000066', '000069', '000078',
            '000089', '000100', '000157', '000166', '000333', '000338', '000400', '000401', '000402', '000413',
            '000415', '000417', '000418', '000425', '000488', '000498', '000501', '000503', '000513', '000516',
            '000519', '000528', '000536', '000538', '000540', '000543', '000547', '000550', '000551', '000553',
            '000559', '000560', '000563', '000568', '000581', '000596', '000598', '000600', '000601', '000623',
            '000625', '000627', '000629', '000630', '000636', '000651', '000656', '000661', '000671', '000686',
            '000703', '000708', '000709', '000712', '000717', '000718', '000725', '000728', '000729', '000738',
            '000750', '000768', '000776', '000778', '000783', '000786', '000792', '000800', '000807', '000810',
            '000826', '000830', '000831', '000848', '000858', '000860', '000876', '000877', '000878', '000895',
            '000898', '000900', '000901', '000903', '000905', '000910', '000917', '000921', '000923', '000925',
            '000930', '000932', '000933', '000937', '000938', '000959', '000960', '000961', '000963', '000977',
            '000983', '001979', '002001', '002007', '002008', '002024', '002027', '002032', '002044', '002049',
            '002050', '002065', '002074', '002081', '002120', '002129', '002142', '002146', '002153', '002174',
            '002179', '002202', '002230', '002236', '002241', '002252', '002271', '002304', '002311', '002352',
            '002371', '002385', '002410', '002415', '002422', '002424', '002426', '002430', '002456', '002460',
            '002463', '002466', '002475', '002493', '002508', '002555', '002594', '002601', '002602', '002607',
            '002624', '002648', '002673', '002714', '002736', '002739', '002797', '002812', '002821', '002841',
            '002916', '002920', '002938', '002945', '002958', '002966',

            # 创业板
            '300001', '300002', '300003', '300009', '300012', '300014', '300015', '300017', '300024', '300027',
            '300033', '300036', '300037', '300059', '300070', '300072', '300073', '300122', '300124', '300136',
            '300142', '300144', '300146', '300168', '300182', '300207', '300223', '300251', '300274', '300285',
            '300296', '300308', '300315', '300316', '300347', '300357', '300363', '300373', '300408', '300413',
            '300433', '300450', '300454', '300458', '300463', '300474', '300496', '300498', '300502', '300529',
            '300558', '300568', '300595', '300601', '300628', '300633', '300661', '300676', '300699', '300750',
            '300751', '300759', '300760', '300763', '300769', '300782', '300896', '300957', '300999',
        ]

        # 截取到目标数量
        codes = predefined_codes[:self.num_stocks]

        self.logger.info(f"预定义列表加载完成: {len(codes)}只股票")
        return codes

    def calculate_data_quality_score(self, df: pd.DataFrame) -> float:
        """
        计算数据质量分数 (0-100)

        检查项:
        - 数据完整性 (无NaN)
        - OHLC逻辑正确性 (high >= low, close在[low, high]之间)
        - 价格合理性 (> 0)
        - 成交量合理性 (>= 0)
        """
        if df is None or df.empty:
            return 0.0

        score = 100.0
        total_rows = len(df)

        # 检查NaN
        nan_count = df.isnull().sum().sum()
        if nan_count > 0:
            score -= (nan_count / (total_rows * len(df.columns))) * 20

        # 检查OHLC逻辑
        if 'high' in df.columns and 'low' in df.columns:
            invalid_hl = (df['high'] < df['low']).sum()
            score -= (invalid_hl / total_rows) * 30

        if 'close' in df.columns and 'high' in df.columns and 'low' in df.columns:
            invalid_close = ((df['close'] > df['high']) | (df['close'] < df['low'])).sum()
            score -= (invalid_close / total_rows) * 30

        # 检查价格合理性
        price_cols = ['open', 'high', 'low', 'close']
        for col in price_cols:
            if col in df.columns:
                invalid_price = (df[col] <= 0).sum()
                score -= (invalid_price / total_rows) * 5

        # 检查成交量
        if 'volume' in df.columns:
            invalid_volume = (df['volume'] < 0).sum()
            score -= (invalid_volume / total_rows) * 10

        return max(0.0, score)

    def test_single_stock(self, code: str, use_cache: bool = True, round_name: str = '') -> Dict[str, Any]:
        """
        测试单只股票

        Returns:
            测试结果字典
        """
        result = {
            'code': code,
            'success': False,
            'source': None,
            'response_time_ms': 0,
            'data_rows': 0,
            'quality_score': 0,
            'cache_hit': False,
            'error': None,
            'round': round_name
        }

        start_time = time.time()

        try:
            # 使用 count=500 参数：让缓存日期范围与请求完全一致，热启动可命中缓存
            df = self.master.get_kline(
                code=code,
                freq='d',
                count=500,
                adjust='qfq',
                use_cache=use_cache
            )

            response_time_ms = (time.time() - start_time) * 1000
            result['response_time_ms'] = response_time_ms

            if df is not None and not df.empty:
                result['success'] = True
                result['data_rows'] = len(df)
                result['quality_score'] = self.calculate_data_quality_score(df)

                # 从DataFrame属性获取实际数据源
                source = df.attrs.get('source', 'unknown')
                result['source'] = source

                # 判断缓存命中: source='cache' 或 响应极快
                if source == 'cache':
                    result['cache_hit'] = True
                    self.stats.cache_hits += 1
                else:
                    result['cache_hit'] = False
                    self.stats.cache_misses += 1

            else:
                result['error'] = 'Empty data returned'
                self.stats.cache_misses += 1

        except Exception as e:
            result['error'] = str(e)
            response_time_ms = (time.time() - start_time) * 1000
            result['response_time_ms'] = response_time_ms

        return result

    def _classify_board(self, code: str) -> str:
        """根据股票代码分类板块"""
        if code.startswith('6'):
            return 'sh_main'
        elif code.startswith('0') or code.startswith('2'):
            return 'sz_main'
        elif code.startswith('3'):
            return 'chinext'
        return 'other'

    def _clear_cache(self):
        """清空缓存数据库"""
        import sqlite3
        db_path = self.master.cache_manager.db_path
        if os.path.exists(db_path):
            conn = sqlite3.connect(db_path)
            cursor = conn.cursor()
            cursor.execute("DELETE FROM kline_cache")
            conn.commit()
            conn.close()
            self.logger.info(f"缓存数据库已清空: {db_path}")

    def run_benchmark(self):
        """运行基准测试"""
        self.logger.info("\n" + "=" * 80)
        self.logger.info("日线数据缓存验证基准测试 v2 (增量缓存+优化校验)")
        self.logger.info("=" * 80)

        # 生成股票代码
        stock_codes = self.generate_stock_codes()

        # 打印配置信息
        self.logger.info(f"\n测试配置:")
        self.logger.info(f"  股票数量: {len(stock_codes)}")
        self.logger.info(f"  K线数量: {self.num_klines} (约2年历史数据)")
        self.logger.info(f"  数据源: {list(self.master.adapters.keys())}")
        self.logger.info(f"  缓存启用: {self.master.cache_manager.enabled}")

        # 打印校验源配置
        validation_config = self.master.config.get('validation', {})
        self.logger.info(f"  校验模式: {validation_config.get('mode', 'N/A')}")
        self.logger.info(f"  校验源: {validation_config.get('sources', [])}")
        self.logger.info(f"  投票法定人数: {validation_config.get('quorum', 'N/A')}")

        # 记录冷启动前的缓存状态
        cache_stats_before = self.master.get_cache_statistics()
        self.logger.info(f"\n初始缓存状态: {cache_stats_before.get('total_records', 0)}条记录, {cache_stats_before.get('stock_count', 0)}只股票")

        # 第一轮: 冷启动测试 (清空缓存后全量校验)
        self.logger.info("\n" + "-" * 80)
        self.logger.info("第一轮: 冷启动测试 (清空缓存, 全量校验)")
        self.logger.info("-" * 80)

        self._clear_cache()

        cold_start_results = self._run_test_round(stock_codes, use_cache=True, round_name="cold_start")

        # 记录冷启动后的缓存状态
        cache_stats_cold = self.master.get_cache_statistics()
        self.logger.info(f"\n冷启动后缓存: {cache_stats_cold.get('validated_records', 0)}条已验证, {cache_stats_cold.get('stock_count', 0)}只股票, {cache_stats_cold.get('db_size_mb', 0)}MB")

        # 第二轮: 热启动测试 (使用缓存, 验证增量效果)
        self.logger.info("\n" + "-" * 80)
        self.logger.info("第二轮: 热启动测试 (使用已有缓存, 验证增量效果)")
        self.logger.info("-" * 80)

        warm_start_results = self._run_test_round(stock_codes, use_cache=True, round_name="warm_start")

        # 记录热启动后的缓存状态
        cache_stats_warm = self.master.get_cache_statistics()
        self.logger.info(f"\n热启动后缓存: {cache_stats_warm.get('validated_records', 0)}条已验证, {cache_stats_warm.get('stock_count', 0)}只股票, {cache_stats_warm.get('db_size_mb', 0)}MB")

        # 生成报告
        self._generate_report(cold_start_results, warm_start_results, cache_stats_cold, cache_stats_warm)

    def _run_test_round(self, stock_codes: List[str], use_cache: bool, round_name: str) -> List[Dict]:
        """运行一轮测试"""
        results = []
        total = len(stock_codes)
        success_count = 0
        failure_count = 0

        start_time = time.time()

        for i, code in enumerate(stock_codes, 1):
            # 进度显示
            if i % 50 == 0 or i == total:
                elapsed = time.time() - start_time
                rate = i / elapsed if elapsed > 0 else 0
                eta = (total - i) / rate if rate > 0 else 0
                self.logger.info(
                    f"进度: {i}/{total} ({i/total*100:.1f}%) | "
                    f"成功: {success_count} | 失败: {failure_count} | "
                    f"速度: {rate:.1f} stocks/s | ETA: {eta:.0f}s"
                )

            # 测试单只股票
            result = self.test_single_stock(code, use_cache=use_cache, round_name=round_name)
            results.append(result)

            if result['success']:
                success_count += 1
                source = result.get('source', 'unknown')
                self.stats.add_success(source)
                self.stats.add_response_time(source, result['response_time_ms'])
                self.stats.add_data_quality(source, result['quality_score'])

                # 板块统计
                board = self._classify_board(code)
                if board in self.stats.board_stats:
                    self.stats.board_stats[board]['success'] += 1
            else:
                failure_count += 1
                error_type = result.get('error', 'unknown')[:50]  # 截断错误信息
                self.stats.add_failure('unknown', error_type)

                # 板块统计
                board = self._classify_board(code)
                if board in self.stats.board_stats:
                    self.stats.board_stats[board]['failure'] += 1

            # 避免请求过快
            time.sleep(0.01)

        total_time = time.time() - start_time

        self.logger.info(f"\n{round_name} 完成:")
        self.logger.info(f"  总耗时: {total_time:.2f}s")
        self.logger.info(f"  成功: {success_count}/{total} ({success_count/total*100:.1f}%)")
        self.logger.info(f"  失败: {failure_count}/{total} ({failure_count/total*100:.1f}%)")
        self.logger.info(f"  平均速度: {total/total_time:.2f} stocks/s")

        return results

    def _generate_report(self, cold_results: List[Dict], warm_results: List[Dict],
                         cache_stats_cold: Dict, cache_stats_warm: Dict):
        """生成测试报告"""
        self.logger.info("\n" + "=" * 80)
        self.logger.info("基准测试报告")
        self.logger.info("=" * 80)

        # 获取统计摘要
        summary = self.stats.get_summary()

        # 1. 缓存性能分析
        self.logger.info(f"\n【缓存性能】")
        self.logger.info(f"  总命中: {summary['cache']['hits']}")
        self.logger.info(f"  总未命中: {summary['cache']['misses']}")
        self.logger.info(f"  命中率: {summary['cache']['hit_rate']:.2f}%")

        if summary['cache']['incremental_hits'] > 0 or summary['cache']['incremental_validations'] > 0:
            self.logger.info(f"  增量缓存命中: {summary['cache']['incremental_hits']}次")
            self.logger.info(f"  增量校验: {summary['cache']['incremental_validations']}次")
            self.logger.info(f"  增量命中率: {summary['cache']['incremental_hit_rate']:.2f}%")

        # 2. 数据源性能对比
        self.logger.info(f"\n【数据源性能】")
        for source, stats in summary['sources'].items():
            if stats['total_requests'] == 0:
                continue
            self.logger.info(f"\n  {source}:")
            self.logger.info(f"    请求数: {stats['total_requests']}")
            self.logger.info(f"    成功率: {stats['success_rate']:.2f}%")
            self.logger.info(f"    响应时间:")
            self.logger.info(f"      平均: {stats['response_time']['mean']:.2f}ms")
            self.logger.info(f"      P50: {stats['response_time']['p50']:.2f}ms")
            self.logger.info(f"      P95: {stats['response_time']['p95']:.2f}ms")
            self.logger.info(f"      P99: {stats['response_time']['p99']:.2f}ms")
            self.logger.info(f"    数据质量:")
            self.logger.info(f"      平均分: {stats['data_quality']['mean']:.2f}/100")
            if stats['errors']:
                self.logger.info(f"    错误类型: {stats['errors']}")

        # 3. 校验源使用统计
        if summary.get('validation_sources'):
            self.logger.info(f"\n【校验源使用】")
            for source, count in summary['validation_sources'].items():
                self.logger.info(f"  {source}: {count}次")

        # 4. 板块统计
        self.logger.info(f"\n【板块统计】")
        for board, stats in summary['board_stats'].items():
            total = stats['success'] + stats['failure']
            if total > 0:
                success_rate = stats['success'] / total * 100
                board_name = {'sh_main': '上海主板', 'sz_main': '深圳主板', 'chinext': '创业板'}.get(board, board)
                self.logger.info(f"  {board_name}: {stats['success']}/{total} ({success_rate:.1f}%)")

        # 5. 冷启动 vs 热启动对比
        self.logger.info(f"\n【冷启动 vs 热启动】")

        cold_times = [r['response_time_ms'] for r in cold_results if r['success']]
        warm_times = [r['response_time_ms'] for r in warm_results if r['success']]

        if cold_times and warm_times:
            cold_avg = np.mean(cold_times)
            warm_avg = np.mean(warm_times)
            speedup = cold_avg / warm_avg if warm_avg > 0 else 0

            self.logger.info(f"  冷启动平均响应: {cold_avg:.2f}ms")
            self.logger.info(f"  热启动平均响应: {warm_avg:.2f}ms")
            self.logger.info(f"  加速比: {speedup:.2f}x")

        # 6. 热启动增量缓存明细
        self.logger.info(f"\n【热启动增量缓存】")
        warm_cache_hits = sum(1 for r in warm_results if r.get('cache_hit'))
        warm_total = len([r for r in warm_results if r['success']])
        warm_cache_rate = warm_cache_hits / warm_total * 100 if warm_total > 0 else 0
        self.logger.info(f"  缓存直接命中: {warm_cache_hits}/{warm_total} ({warm_cache_rate:.1f}%)")

        warm_fresh = sum(1 for r in warm_results if r['success'] and not r.get('cache_hit'))
        warm_fresh_cache_times = [r['response_time_ms'] for r in warm_results
                                   if r['success'] and r.get('cache_hit')]
        warm_miss_times = [r['response_time_ms'] for r in warm_results
                           if r['success'] and not r.get('cache_hit')]
        if warm_fresh_cache_times:
            self.logger.info(f"  缓存命中响应: avg={np.mean(warm_fresh_cache_times):.1f}ms  "
                             f"P50={np.median(warm_fresh_cache_times):.1f}ms")
        if warm_miss_times:
            self.logger.info(f"  缓存未命中响应: avg={np.mean(warm_miss_times):.1f}ms  "
                             f"P50={np.median(warm_miss_times):.1f}ms")
        if warm_fresh_cache_times and warm_miss_times:
            accel = np.mean(warm_miss_times) / np.mean(warm_fresh_cache_times)
            self.logger.info(f"  缓存加速比: {accel:.1f}x")

        # 增量缓存日志统计（从日志中计算）
        self.logger.info(f"  增量缓存统计: hits={summary['cache']['incremental_hits']}  "
                         f"validations={summary['cache']['incremental_validations']}")

        # 7. Fallback事件
        if summary['fallback']['total_events'] > 0:
            self.logger.info(f"\n【Fallback事件】: {summary['fallback']['total_events']}次")
            for event in summary['fallback']['events'][:10]:  # 只显示前10个
                self.logger.info(f"  {event['from']} -> {event['to']}: {event['reason']}")

        # 8. 关键洞察
        self.logger.info(f"\n【关键洞察】")

        # 洞察1: 校验通过率
        validation_total = summary['validation']['passed'] + summary['validation']['failed']
        if validation_total > 0:
            validation_pass_rate = summary['validation']['passed'] / validation_total * 100
            self.logger.info(f"  ✓ 校验通过率: {validation_pass_rate:.1f}% ({summary['validation']['passed']}/{validation_total})")

        # 洞察2: 缓存效率
        if summary['cache']['hit_rate'] > 90:
            self.logger.info(f"  ✓ 缓存命中率优秀 ({summary['cache']['hit_rate']:.1f}%)")
        elif summary['cache']['hit_rate'] > 70:
            self.logger.info(f"  ⚠ 缓存命中率良好 ({summary['cache']['hit_rate']:.1f}%), 可进一步优化")
        else:
            self.logger.info(f"  ✗ 缓存命中率偏低 ({summary['cache']['hit_rate']:.1f}%), 需要优化")

        # 洞察3: 数据源可靠性
        for source, stats in summary['sources'].items():
            if stats['total_requests'] > 100:  # 只分析请求量大的源
                if stats['success_rate'] > 95:
                    self.logger.info(f"  ✓ {source} 可靠性优秀 ({stats['success_rate']:.1f}%)")
                elif stats['success_rate'] < 85:
                    self.logger.info(f"  ⚠ {source} 可靠性需关注 ({stats['success_rate']:.1f}%)")

        # 保存详细报告到JSON
        project_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
        report_dir = os.path.join(project_root, 'logs')
        os.makedirs(report_dir, exist_ok=True)
        report_file = os.path.join(report_dir, f'benchmark_report_{datetime.now().strftime("%Y%m%d_%H%M%S")}.json')

        full_report = {
            'summary': summary,
            'cache_stats': {
                'cold': cache_stats_cold,
                'warm': cache_stats_warm
            },
            'cold_start_results': cold_results,
            'warm_start_results': warm_results
        }

        with open(report_file, 'w', encoding='utf-8') as f:
            json.dump(full_report, f, indent=2, ensure_ascii=False)

        self.logger.info(f"\n详细报告已保存: {report_file}")

        self.logger.info("\n" + "=" * 80)
        self.logger.info("测试完成")
        self.logger.info("=" * 80)


def main():
    """主函数"""
    try:
        # 创建并运行基准测试
        benchmark = BenchmarkTest()
        benchmark.run_benchmark()

    except KeyboardInterrupt:
        print("\n\n测试被用户中断")
    except Exception as e:
        print(f"\n\n测试失败: {e}")
        import traceback
        traceback.print_exc()
    finally:
        # 清理资源
        try:
            if 'benchmark' in locals():
                benchmark.master.close()
        except:
            pass


if __name__ == '__main__':
    main()
