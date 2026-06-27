"""
StockDataMaster主数据接口

提供统一的股票数据访问接口,集成多数据源、缓存、健康检测等功能
"""

import logging
import os
from typing import Optional, Dict, Any
import pandas as pd
from datetime import datetime, timedelta, time

from .config import get_config
from .adapters import AdapterFactory
from .cache import CacheManager
from .health import HealthManager


class StockDataMaster:
    """股票数据主数据接口"""

    _instance = None  # 单例模式

    def __new__(cls, *args, **kwargs):
        """单例模式实现"""
        if cls._instance is None:
            cls._instance = super().__new__(cls)
        return cls._instance

    def __init__(self, config_path: Optional[str] = None):
        """
        初始化StockDataMaster

        Args:
            config_path: 配置文件路径
        """
        # 避免重复初始化
        if hasattr(self, '_initialized'):
            return

        # 加载配置
        self.config = get_config(config_path)

        # 设置日志
        self._setup_logging()
        self.logger = logging.getLogger("StockDataMaster")
        self.logger.info("初始化StockDataMaster...")

        # 创建适配器
        self.adapters = {}
        self._init_adapters()

        # 创建缓存管理器
        self.cache_manager = CacheManager(self.config, self.adapters)

        # 创建健康管理器
        self.health_manager = HealthManager(self.config, self.adapters)

        # 🔥 优化: 股票名称缓存 (减少重复查询)
        self._stock_name_cache = {}  # {code: name}

        # 🔥 优化: baostock会话状态
        self._bs_session_active = False
        self._bs_last_login_time = None

        # 🔥 baostock 冷却机制
        self._baostock_consecutive_failures = 0
        self._baostock_cooldown_until = 0  # time.time() 时间戳

        # 启动健康监控
        if self.config.is_health_check_enabled():
            self.health_manager.start_monitoring()

        self._initialized = True
        self.logger.info("StockDataMaster初始化完成")

    def _setup_logging(self):
        """设置日志系统"""
        log_level = self.config.get('logging.level', 'INFO')
        log_file = self.config.get('logging.file')

        # 创建日志目录
        if log_file:
            log_dir = os.path.dirname(log_file)
            if log_dir and not os.path.exists(log_dir):
                os.makedirs(log_dir, exist_ok=True)

        # 创建处理器列表
        handlers = [logging.StreamHandler()]

        # 添加文件处理器（指定UTF-8编码）
        if log_file:
            file_handler = logging.FileHandler(log_file, encoding='utf-8')
            handlers.append(file_handler)

        # 配置根日志记录器
        logging.basicConfig(
            level=getattr(logging, log_level.upper()),
            format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
            handlers=handlers,
            force=True  # 强制重新配置（如果已经配置过）
        )

    def _init_adapters(self):
        """初始化所有数据源适配器"""
        enabled_sources = self.config.get_enabled_sources()

        for source_name in enabled_sources:
            try:
                source_config = self.config.get_data_source_config(source_name)
                adapter = AdapterFactory.create_adapter(source_name, source_config)

                # 尝试连接
                if adapter.connect():
                    self.adapters[source_name] = adapter
                    self.logger.info(f"数据源{source_name}初始化成功")
                else:
                    self.logger.warning(f"数据源{source_name}连接失败")

            except Exception as e:
                self.logger.error(f"数据源{source_name}初始化失败: {e}")

        if not self.adapters:
            self.logger.error("没有可用的数据源!")

    def get_kline(
        self,
        code: str,
        freq: str = 'd',
        start_date: Optional[str] = None,
        end_date: Optional[str] = None,
        count: Optional[int] = None,
        adjust: str = 'qfq',
        use_cache: bool = True
    ) -> Optional[pd.DataFrame]:
        """
        获取K线数据(统一接口)

        Args:
            code: 股票代码,如'600519'或'sh.600519'
            freq: 频率 'd'=日,'w'=周,'m'=月,'5m'=5分钟,'15m'=15分钟,'30m'=30分钟,'60m'=60分钟
            start_date: 开始日期 'YYYY-MM-DD'
            end_date: 结束日期 'YYYY-MM-DD'
            count: 获取数量(从最新往前)
            adjust: 复权类型,'qfq'=前复权(统一使用)
            use_cache: 是否使用缓存(仅对日线有效)

        Returns:
            DataFrame,包含date,open,high,low,close,volume,amount列
        """
        # 边界条件检查: 空股票代码
        if not code or not code.strip():
            self.logger.warning("股票代码不能为空")
            return None

        # 边界条件检查: count为0或负数
        if count is not None and count <= 0:
            self.logger.warning(f"count参数无效: {count}, 返回空DataFrame")
            return pd.DataFrame(columns=['date', 'open', 'high', 'low', 'close', 'volume', 'amount'])

        # 标准化代码
        code = self._normalize_code(code)

        # 日线数据优先使用缓存
        if freq == 'd' and use_cache and self.cache_manager.enabled:
            cached_df = self.cache_manager.get_cached_kline(code, start_date, end_date, count)

            if cached_df is not None and not cached_df.empty:
                # 检查缓存是否足够新（传入用户请求的 end_date 参数）
                is_fresh = self._is_cache_fresh(cached_df, end_date)
                # 检查数据量是否充足 - 放宽条件,>=95%即可
                # 原因: 双源校验可能导致少数数据校验失败,如119/120
                is_sufficient = count is None or len(cached_df) >= count * 0.95
                # 检查请求的日期范围是否超出缓存范围
                is_date_range_covered = self._is_date_range_covered(cached_df, start_date, end_date)

                self.logger.debug(f"缓存检查: code={code}, is_fresh={is_fresh}, is_sufficient={is_sufficient}, is_date_range_covered={is_date_range_covered}, cached_rows={len(cached_df)}, request_count={count}")

                if is_fresh and is_sufficient and is_date_range_covered:
                    # 确保source字段存在(防止attrs丢失)
                    if 'source' not in cached_df.attrs:
                        cached_df.attrs['source'] = 'cache'
                    self.logger.debug(f"从缓存获取{code}数据: {len(cached_df)}条, source={cached_df.attrs.get('source')}")
                    return cached_df
                elif is_fresh and not is_sufficient:
                    self.logger.debug(f"{code}缓存数据不足({len(cached_df)}/{count}条),从数据源补充")
                elif not is_date_range_covered:
                    self.logger.debug(f"{code}缓存日期范围不覆盖请求范围,重新获取")
                else:
                    self.logger.debug(f"{code}缓存数据不新鲜(latest={cached_df['date'].iloc[-1]}),重新获取")

        # 从数据源获取
        df = self._fetch_kline_from_source(code, freq, start_date, end_date, count, adjust)

        # 日线数据尝试缓存(双源校验)
        # 注意：无论 use_cache 是否为 True，已获取的数据都应尝试缓存。
        # use_cache 仅控制上面的"是否从缓存读取"，不应影响写入。
        # 否则 warmup 路径传入 use_cache=False 时，拉取的新数据不会写入缓存。
        if df is not None and freq == 'd':
            self._try_cache_kline(code, df, start_date, end_date, count, adjust)

        return df

    def _fetch_kline_from_source(
        self,
        code: str,
        freq: str,
        start_date: Optional[str],
        end_date: Optional[str],
        count: Optional[int],
        adjust: str
    ) -> Optional[pd.DataFrame]:
        """
        从数据源获取K线数据(带故障切换,时段感知)
        """
        # 根据频率类型选择角色
        if freq in ['d', 'w', 'm']:
            role = 'kline_day'
        else:
            role = 'kline_minute'

        # 获取当前时段
        time_slot = self._get_time_slot()

        # 优先从 roles 获取数据源列表
        sources = self.config.get_sources_by_role(role, time_slot=time_slot)

        if not sources:
            # fallback 到旧的 use_for 格式
            self.logger.warning(f"roles中未找到{role}数据源,回退到use_for格式")
            sources = self.config.get_sources_by_usage(role)

        if not sources:
            self.logger.error("没有可用的K线数据源")
            return None

        # 依次尝试数据源
        for source_name in sources:
            adapter = self.adapters.get(source_name)
            if not adapter:
                continue

            try:
                actual_count = count
                if count is not None and freq == 'd':
                    actual_count = int(count * 1.1)

                self.logger.debug(f"从{source_name}获取{code} K线数据(role={role}, slot={time_slot})")

                df = adapter.get_kline(code, freq, start_date, end_date, actual_count, adjust)

                if df is not None and not df.empty:
                    df.attrs['source'] = source_name

                    if count is not None and len(df) > count:
                        return_df = df.tail(count).copy()
                        return_df.attrs['source'] = source_name
                        return_df.attrs['full_data'] = df
                    else:
                        return_df = df

                    self.logger.debug(f"成功从{source_name}获取{code}数据: {len(return_df)}条")
                    return return_df
                else:
                    self.logger.warning(f"{source_name}返回空数据")

            except Exception as e:
                self.logger.error(f"{source_name}获取K线失败: {e}")
                continue

        self.logger.error(f"所有数据源均无法获取{code}的K线数据")
        return None

    def _try_cache_kline(
        self,
        code: str,
        df: pd.DataFrame,
        start_date: Optional[str],
        end_date: Optional[str],
        count: Optional[int],
        adjust: str
    ):
        """
        尝试缓存日K线数据(增量校验+串行短路校验)

        策略:
        1. 查询已验证缓存的日期集合
        2. 只对新增日期(未在缓存中)进行校验
        3. 串行短路校验(fast-first):
           - 按响应速度排序校验源(xtquant快 → baostock慢)
           - 逐个串行请求,第一个通过就短路返回
           - 单个校验源: 双源校验
           - 无校验源: 直接缓存主数据

        Args:
            code: 股票代码
            df: 已获取的数据(来自主数据源)
            start_date: 开始日期
            end_date: 结束日期
            count: 数量
            adjust: 复权类型
        """
        if not self.cache_manager.enabled:
            return

        try:
            # 如果df.attrs中包含完整数据(缓存预取优化),使用完整数据进行缓存
            cache_df = df.attrs.get('full_data', df)
            actual_count = count
            if cache_df is not df:
                self.logger.debug(f"使用预取的完整数据进行缓存: {len(cache_df)}条(原{len(df)}条)")
                actual_count = len(cache_df)

            # 获取主数据源名称
            primary_source = df.attrs.get('source', 'unknown')

            # 🔥 增量缓存: 查询已验证的日期集合
            validated_dates = self.cache_manager.get_validated_dates(code)

            if validated_dates:
                # 过滤出未缓存的新数据
                cache_df['date'] = cache_df['date'].astype(str)
                new_data_mask = ~cache_df['date'].isin(validated_dates)
                new_df = cache_df[new_data_mask].copy()

                if new_df.empty:
                    self.logger.info(f"{code}所有数据已在缓存中({len(validated_dates)}条),跳过校验")
                    return

                self.logger.info(f"{code}增量缓存: 已有{len(validated_dates)}条,新增{len(new_df)}条待校验")
                cache_df = new_df
            else:
                self.logger.debug(f"{code}首次缓存,全量校验{len(cache_df)}条")

            # 获取当前时段,用于时段感知的校验源选择
            time_slot = self._get_time_slot()

            # 从 config 获取校验源列表(按角色和时段过滤)
            validation_sources = self.config.get_sources_by_role('validation', time_slot=time_slot)

            # 过滤掉主数据源(避免重复)
            validation_sources = [s for s in validation_sources if s != primary_source]

            if not validation_sources:
                # 无校验源: 降级为旧逻辑(直接缓存主数据)
                self.logger.info(f"{code}无校验源可用,直接缓存主数据")
                self.cache_manager.save_to_cache(code, cache_df, primary_source, 'none', validated=False)
                return

            # 🔥 增量校验: 只请求新数据的日期范围
            if not cache_df.empty:
                incremental_start = cache_df['date'].min()
                incremental_end = cache_df['date'].max()
            else:
                incremental_start = start_date
                incremental_end = end_date

            # 🔥 串行短路校验: 按响应速度排序(xtquant快 → baostock慢)
            # 优先级: xtquant(交易时段50ms) > baostock(2-3s)
            speed_priority = {'xtquant': 1, 'baostock': 2, 'mootdx': 3}
            validation_sources_sorted = sorted(
                validation_sources,
                key=lambda s: speed_priority.get(s, 99)
            )

            active_validation_sources = [
                name for name in validation_sources_sorted
                if self.adapters.get(name) and getattr(self.adapters[name], 'is_connected', False)
            ]
            skipped = [s for s in validation_sources if s not in active_validation_sources]
            for s in skipped:
                self.logger.debug(f"{s}适配器不可用,跳过")

            if not active_validation_sources:
                # 所有校验源不可用,降级为直接缓存
                self.logger.warning(f"{code}所有校验源不可用,直接缓存主数据")
                self.cache_manager.save_to_cache(code, cache_df, primary_source, 'none', validated=False)
                return

            incremental_dates = set(cache_df['date'].astype(str))

            # 🔥 串行短路: 逐个请求,第一个通过就返回
            for vs_name in active_validation_sources:
                vs_adapter = self.adapters[vs_name]
                try:
                    import time
                    start_time = time.time()
                    self.logger.debug(f"请求{vs_name}校验数据: {code} ({incremental_start} ~ {incremental_end})")
                    vs_df = vs_adapter.get_kline(code, 'd', incremental_start, incremental_end, None, adjust)
                    elapsed = time.time() - start_time

                    if vs_df is None or vs_df.empty:
                        self.logger.debug(f"{vs_name}未返回数据,尝试下一个校验源")
                        continue

                    # 检查覆盖率
                    vs_dates = set(vs_df['date'].astype(str))
                    overlap = len(vs_dates & incremental_dates)
                    coverage = overlap / len(incremental_dates) if incremental_dates else 0

                    if coverage < 0.3:
                        self.logger.warning(
                            f"{vs_name}数据覆盖率{coverage:.0%}"
                            f"({overlap}/{len(incremental_dates)}条)不足30%，尝试下一个校验源"
                        )
                        continue

                    self.logger.debug(
                        f"{vs_name}返回{len(vs_df)}条校验数据，覆盖率{coverage:.0%}，耗时{elapsed:.2f}s"
                    )

                    # 🔥 单源校验: 计算通过率
                    pass_rate = self.cache_manager._calculate_pass_rate(cache_df, vs_df, code)

                    if pass_rate >= self.cache_manager.min_pass_rate:
                        # 🔥 短路成功: 第一个通过就直接缓存并返回
                        validated_df = cache_df.copy()
                        self.cache_manager.save_to_cache(
                            code, validated_df, primary_source, vs_name, validated=True
                        )
                        self.logger.info(
                            f"{code}串行短路校验通过: {vs_name} (通过率={pass_rate*100:.1f}%, 耗时{elapsed:.2f}s)"
                        )
                        return  # 短路返回,不再请求后续校验源
                    else:
                        self.logger.debug(
                            f"{code} {vs_name}校验未通过(通过率={pass_rate*100:.1f}%), 尝试下一个校验源"
                        )

                except Exception as e:
                    self.logger.warning(f"{vs_name}校验数据请求失败: {e}, 尝试下一个校验源")
                    continue

            # 所有校验源都未通过
            self.logger.warning(f"{code}所有校验源均未通过,不进入缓存")

        except Exception as e:
            self.logger.error(f"缓存数据失败 {code}: {e}")

    def _is_date_range_covered(self, cached_df: pd.DataFrame, start_date: Optional[str], end_date: Optional[str]) -> bool:
        """
        检查请求的日期范围是否被缓存数据覆盖

        Args:
            cached_df: 缓存数据
            start_date: 请求的开始日期
            end_date: 请求的结束日期

        Returns:
            是否覆盖
        """
        if cached_df is None or cached_df.empty:
            return False

        try:
            # 如果没有指定日期范围，认为覆盖
            if not start_date and not end_date:
                return True

            cached_start = pd.to_datetime(cached_df['date'].iloc[0])
            cached_end = pd.to_datetime(cached_df['date'].iloc[-1])

            # 如果指定了开始日期，检查缓存开始日期是否早于请求开始日期
            if start_date:
                request_start = pd.to_datetime(start_date)
                if cached_start > request_start:
                    self.logger.debug(f"缓存开始日期{cached_start.date()}晚于请求开始日期{request_start.date()}")
                    return False

            # 如果指定了结束日期，检查缓存结束日期是否晚于请求结束日期
            if end_date:
                request_end = pd.to_datetime(end_date)
                if cached_end < request_end:
                    self.logger.debug(f"缓存结束日期{cached_end.date()}早于请求结束日期{request_end.date()}")
                    return False

            return True

        except Exception as e:
            self.logger.error(f"检查日期范围覆盖失败: {e}")
            return False

    def _is_cache_fresh(self, df: pd.DataFrame, request_end_date: Optional[str] = None) -> bool:
        """
        智能缓存新鲜度判断（含盘中/盘后逻辑 + 历史数据优化）

        核心逻辑：
        1. 🔥 如果用户明确请求历史时间段（end_date < 今天）→ 新鲜（历史数据不变）
        2. 🔥 如果缓存最新日期 < 今天 → 新鲜（历史数据不变，解决GUI count场景）
        3. 如果缓存最新日期是今天且盘中时段 → 不新鲜（当日数据动态变化）
        4. 如果缓存最新日期是今天且盘后时段 → 新鲜（当日数据已固定）

        Args:
            df: 缓存数据
            request_end_date: 用户请求的结束日期（YYYY-MM-DD），如果未指定则表示请求最新数据

        Returns:
            bool: 缓存是否新鲜
        """
        if df is None or df.empty:
            return False

        try:
            now = datetime.now()
            today = now.date()

            # 🔥 优化1: 如果用户指定了 end_date 且不是今天，说明请求的是历史数据
            # 历史数据永远不会变化，直接判定为新鲜
            if request_end_date:
                request_end = pd.to_datetime(request_end_date).date()
                if request_end < today:
                    self.logger.debug(f"缓存数据新鲜：用户请求历史时间段(end_date={request_end} < 今天={today})，历史数据不变")
                    return True

            # 获取缓存中最新的日期
            latest_cache_date = pd.to_datetime(df['date']).max().date()

            # 市场收盘时间 15:00
            market_close_time = time(15, 0)
            is_after_market_close = now.time() >= market_close_time

            self.logger.debug(f"缓存新鲜度检查: 缓存最新日期{latest_cache_date}, 今天{today}, 当前时间{now.strftime('%H:%M:%S')}, 当前{now.strftime('%A')}")

            # 🔥 优化2: 如果缓存最新日期 < 今天，说明缓存的都是历史数据
            # 历史数据不会变化，直接判定为新鲜（关键修复：解决GUI count参数场景）
            if latest_cache_date < today:
                self.logger.debug(f"缓存数据新鲜：缓存最新日期{latest_cache_date} < 今天{today}，历史数据不变")
                return True

            # 如果缓存最新日期就是今天
            if latest_cache_date == today:
                # 盘中时段 → 不新鲜（当日数据动态变化）
                if not is_after_market_close:
                    self.logger.debug(f"缓存数据不新鲜：今天盘中时段(时间={now.strftime('%H:%M:%S')} < 15:00)，当日数据动态变化")
                    return False
                # 盘后时段 → 新鲜（当日数据已固定）
                else:
                    self.logger.debug(f"缓存数据新鲜：今天盘后时段(时间={now.strftime('%H:%M:%S')} >= 15:00)，当日数据已固定")
                    return True

            # 如果缓存最新日期 > 今天（理论上不应该出现，但防御性编程）
            if latest_cache_date > today:
                self.logger.warning(f"异常：缓存最新日期{latest_cache_date} > 今天{today}，判定为不新鲜")
                return False

        except Exception as e:
            self.logger.error(f"检查缓存新鲜度失败: {e}")
            return False

    def _get_latest_trading_day(self) -> datetime.date:
        """
        获取最新交易日

        Returns:
            datetime.date: 最新交易日的日期
        """
        current_date = datetime.now().date()
        weekday = datetime.now().weekday()

        # 周一到周五（工作日）
        if weekday <= 4:  # 0=周一, 1=周二, ..., 4=周五
            # 对于工作日，今天就是最新交易日
            # 注意：这里假设当天都是交易日，实际情况可能需要考虑节假日
            return current_date

        # 周六（5）
        elif weekday == 5:
            # 最新交易日是上周五
            return current_date - timedelta(days=1)

        # 周日（6）
        elif weekday == 6:
            # 最新交易日是上周五
            return current_date - timedelta(days=2)

    def get_valuation(
        self,
        code: str,
        start_date: Optional[str] = None,
        end_date: Optional[str] = None
    ) -> Optional[pd.DataFrame]:
        """
        获取估值数据

        Args:
            code: 股票代码
            start_date: 开始日期
            end_date: 结束日期

        Returns:
            DataFrame,包含pe_ttm,pb,ps_ttm等估值指标
        """
        code = self._normalize_code(code)

        # 获取活跃数据源
        active_source = self.health_manager.get_active_source('valuation')

        if not active_source:
            self.logger.error("没有可用的估值数据源")
            return None

        # 获取备用列表
        sources = self.config.get_sources_by_usage('valuation')

        if active_source in sources:
            sources.remove(active_source)
            sources.insert(0, active_source)

        # 依次尝试
        for source_name in sources:
            adapter = self.adapters.get(source_name)

            if not adapter:
                continue

            try:
                df = adapter.get_valuation(code, start_date, end_date)

                if df is not None and not df.empty:
                    self.logger.debug(f"成功从{source_name}获取{code}估值数据")
                    return df

            except Exception as e:
                self.logger.error(f"{source_name}获取估值失败: {e}")
                continue

        self.logger.error(f"所有数据源均无法获取{code}的估值数据")
        return None

    def get_stock_name(self, code: str, use_cache: bool = True) -> Optional[str]:
        """
        获取股票名称 (优化版: 三层缓存 - 内存 → SQLite → baostock)

        Args:
            code: 股票代码 (支持 '600000' 或 'sh.600000')
            use_cache: 是否使用缓存 (默认True)

        Returns:
            股票名称,失败返回None
        """
        try:
            # 标准化代码格式
            clean_code = code.replace('sh.', '').replace('sz.', '')

            # 🔥 优化1: 检查内存缓存 (L1 Cache - 最快)
            if use_cache and clean_code in self._stock_name_cache:
                self.logger.debug(f"股票名称内存缓存命中: {clean_code} -> {self._stock_name_cache[clean_code]}")
                return self._stock_name_cache[clean_code]

            # 🔥 优化2: 检查SQLite缓存 (L2 Cache - 持久化)
            if use_cache:
                cached_name = self.cache_manager.get_cached_stock_name(clean_code)
                if cached_name:
                    # 回填到内存缓存
                    self._stock_name_cache[clean_code] = cached_name
                    self.logger.debug(f"股票名称SQLite缓存命中: {clean_code} -> {cached_name}")
                    return cached_name

            # 标准化为baostock格式 (sh.600000 或 sz.000001)
            if not code.startswith(('sh.', 'sz.')):
                if code.startswith(('6', '688', '689')):
                    bs_code = f'sh.{clean_code}'
                else:
                    bs_code = f'sz.{clean_code}'
            else:
                bs_code = code

            # 🔥 优化3: 从baostock查询 (L3 - 最慢,但权威)
            if 'baostock' in self.adapters:
                try:
                    import baostock as bs
                    from .adapters.baostock_helper import apply_api_key, describe_error

                    # 会话复用 - 确保baostock已登录
                    if not self._bs_session_active:
                        # 新版 baostock 0.9.x: 登录前应用 API Key（旧版无 set_API_key 时自动跳过）
                        bs_api_key = self.config.get('data_sources.baostock.api_key', '')
                        apply_api_key(bs_api_key, self.logger)
                        lg = bs.login()
                        if lg.error_code != '0':
                            self.logger.warning(f"baostock登录失败: {describe_error(lg.error_code, lg.error_msg)}")
                            return None
                        self._bs_session_active = True
                        self._bs_last_login_time = datetime.now()
                        self.logger.debug("baostock会话已建立")

                    # 查询股票基本信息
                    rs = bs.query_stock_basic(code=bs_code)

                    if rs.error_code == '0':
                        data_list = []
                        while (rs.error_code == '0') & rs.next():
                            data_list.append(rs.get_row_data())

                        # 返回第一条记录的股票名称
                        if data_list and len(data_list[0]) > 1:
                            stock_name = data_list[0][1]  # 第二列是code_name

                            # 🔥 优化4: 双层缓存写入
                            if use_cache:
                                # 内存缓存
                                self._stock_name_cache[clean_code] = stock_name
                                # SQLite持久化缓存
                                self.cache_manager.cache_stock_name(clean_code, stock_name, 'baostock')
                                self.logger.debug(f"股票名称已缓存(内存+SQLite): {clean_code} -> {stock_name}")

                            self.logger.debug(f"获取股票名称成功: {clean_code} -> {stock_name}")
                            return stock_name
                    else:
                        self.logger.warning(f"查询股票基本信息失败: {describe_error(rs.error_code, rs.error_msg)}")
                        # 会话可能失效,标记需要重新登录
                        self._bs_session_active = False

                except Exception as e:
                    self.logger.error(f"baostock查询股票名称异常: {e}")
                    # 异常时标记会话失效
                    self._bs_session_active = False

            return None

        except Exception as e:
            self.logger.error(f"获取股票名称失败: {e}")
            return None

    def get_tick(self, code: str) -> Optional[Dict[str, Any]]:
        """
        获取实时tick数据

        Args:
            code: 股票代码

        Returns:
            实时行情字典
        """
        code = self._normalize_code(code)

        # 获取活跃数据源
        active_source = self.health_manager.get_active_source('tick')

        if not active_source:
            self.logger.error("没有可用的tick数据源")
            return None

        # 获取备用列表
        sources = self.config.get_sources_by_usage('tick')

        if active_source in sources:
            sources.remove(active_source)
            sources.insert(0, active_source)

        # 依次尝试
        for source_name in sources:
            adapter = self.adapters.get(source_name)

            if not adapter:
                continue

            try:
                tick = adapter.get_tick(code)

                if tick is not None:
                    # 添加数据源信息到tick数据中
                    tick['source'] = source_name
                    self.logger.debug(f"成功从{source_name}获取{code}实时行情")
                    return tick

            except Exception as e:
                self.logger.error(f"{source_name}获取tick失败: {e}")
                continue

        self.logger.error(f"所有数据源均无法获取{code}的tick数据")
        return None

    def get_health_status(self) -> Dict[str, Any]:
        """
        获取系统健康状态

        Returns:
            健康状态报告
        """
        return self.health_manager.get_health_report()

    def get_cache_statistics(self) -> Dict[str, Any]:
        """
        获取缓存统计信息

        Returns:
            缓存统计信息
        """
        return self.cache_manager.get_cache_statistics()

    def cleanup_cache(self, days: Optional[int] = None):
        """
        清理缓存

        Args:
            days: 保留天数
        """
        self.cache_manager.cleanup_old_cache(days)

    def force_switch_source(self, usage: str, target_source: str) -> bool:
        """
        强制切换数据源

        Args:
            usage: 用途 'kline'/'valuation'/'tick'
            target_source: 目标数据源名称

        Returns:
            是否成功
        """
        return self.health_manager.force_switch(usage, target_source)

    def _get_time_slot(self, current_time=None) -> str:
        """
        判断当前时段

        Args:
            current_time: datetime.time 对象,用于测试注入。None则使用当前时间

        Returns:
            'trading' 或 'after_hours'
        """
        from datetime import time as time_type

        if current_time is None:
            current_time = datetime.now().time()

        market_start = time_type(9, 15)
        market_end = time_type(15, 0)

        if market_start <= current_time <= market_end:
            return 'trading'
        return 'after_hours'

    def _normalize_code(self, code: str) -> str:
        """标准化股票代码为6位纯数字格式"""
        if not code:
            return code

        # 去除前缀 'sh.', 'sz.' (大小写不敏感)
        code_lower = code.lower()
        if code_lower.startswith(('sh.', 'sz.')):
            code = code.split('.')[1]

        # 去除后缀 '.SH', '.SZ' (大小写不敏感)
        if '.' in code:
            code = code.split('.')[0]

        return code

    def _to_baostock_code(self, code: str) -> str:
        """
        转换为 baostock 格式

        Args:
            code: 6位纯数字代码

        Returns:
            baostock 格式代码 (sh.600519 或 sz.000001)
        """
        pure = self._normalize_code(code)

        # 上海: 6开头 或 50x/51x/518 (ETF/债券)
        if pure.startswith(('6', '510', '511', '518')):
            return f"sh.{pure}"

        # 深圳: 其他
        return f"sz.{pure}"

    def _get_stock_name_from_xtquant(self, code: str) -> Optional[str]:
        """
        从 xtquant 获取股票名称 (L2)

        Args:
            code: 6位纯数字代码

        Returns:
            股票名称，失败返回 None
        """
        adapter = self.adapters.get('xtquant')
        if not adapter or not adapter.is_connected:
            return None

        try:
            return adapter.get_stock_name(code)
        except Exception as e:
            self.logger.debug(f"xtquant获取股票名称失败: {code} {e}")
            return None

    def _get_stock_name_from_tushare(self, code: str) -> Optional[str]:
        """
        从 tushare 获取股票名称 (L3)

        Args:
            code: 6位纯数字代码

        Returns:
            股票名称，失败返回 None
        """
        adapter = self.adapters.get('tushare')
        if not adapter or not adapter.is_connected:
            return None

        try:
            return adapter.get_stock_name(code)
        except Exception as e:
            self.logger.debug(f"tushare获取股票名称失败: {code} {e}")
            return None

    def _get_stock_name_from_baostock(self, code: str) -> Optional[str]:
        """
        从 baostock 获取股票名称 (L4)

        Args:
            code: 6位纯数字代码

        Returns:
            股票名称，失败返回 None
        """
        import time

        # 检查冷却期
        if time.time() < self._baostock_cooldown_until:
            self.logger.debug(f"baostock在冷却期，跳过查询: {code}")
            return None

        bs_code = self._to_baostock_code(code)
        adapter = self.adapters.get('baostock')
        if not adapter:
            return None

        try:
            import baostock as bs

            # 确保登录
            if not self._bs_session_active:
                rs = bs.login()
                if rs.error_code == '0':
                    self._bs_session_active = True
                else:
                    self.logger.debug(f"baostock登录失败: {rs.error_msg}")
                    self._baostock_consecutive_failures += 1
                    self._check_baostock_cooldown()
                    return None

            # 查询股票基本信息
            rs = bs.query_stock_basic(code=bs_code)

            if rs.error_code == '0':
                while rs.next():
                    row = rs.get_row_data()
                    if len(row) > 1:
                        name = row[1]  # 第二列是股票名称
                        self._baostock_consecutive_failures = 0  # 重置失败计数
                        self.logger.debug(f"baostock获取股票名称成功: {code} -> {name}")
                        return name
            else:
                self.logger.debug(f"baostock查询失败: {code} {rs.error_msg}")

        except Exception as e:
            self.logger.debug(f"baostock获取股票名称异常: {code} {e}")

        # 失败处理
        self._baostock_consecutive_failures += 1
        self._check_baostock_cooldown()
        return None

    def _check_baostock_cooldown(self):
        """检查并设置 baostock 冷却期"""
        import time

        config = self.config.get_stock_name_config()
        max_failures = config.get('baostock_max_consecutive_failures', 3)
        cooldown = config.get('baostock_retry_cooldown', 300)

        if self._baostock_consecutive_failures >= max_failures:
            self._baostock_cooldown_until = time.time() + cooldown
            self.logger.warning(
                f"baostock连续失败{self._baostock_consecutive_failures}次，"
                f"进入冷却期{cooldown}秒"
            )

    def get_stock_name(self, code: str) -> str:
        """
        获取股票名称 - 四级查找链

        L1: 内存缓存 dict
        L2: baostock query_stock_basic() (免费兜底，数据最全含退市股)
        L3: xtquant.get_stock_name() (QMT用户快速查询)
        L4: tushare pro.stock_basic() (付费用户补充)

        Args:
            code: 股票代码，支持 '600519', 'sh.600519', '600519.SH' 格式

        Returns:
            股票名称字符串，所有级别都失败时返回代码本身
        """
        if not code:
            return code

        # 标准化为6位纯数字
        pure_code = self._normalize_code(code)

        # L1: 内存缓存
        if pure_code in self._stock_name_cache:
            self.logger.debug(f"L1缓存命中: {pure_code} -> {self._stock_name_cache[pure_code]}")
            return self._stock_name_cache[pure_code]

        # L2: baostock (免费无门槛，数据最全含退市股)
        name = self._get_stock_name_from_baostock(pure_code)
        if name:
            self._stock_name_cache[pure_code] = name
            self.cache_manager.cache_stock_name(pure_code, name, 'baostock')
            self.logger.info(f"L2 baostock获取股票名称: {pure_code} -> {name}")
            return name

        # L3: xtquant (QMT用户快速查询)
        name = self._get_stock_name_from_xtquant(pure_code)
        if name:
            self._stock_name_cache[pure_code] = name
            self.cache_manager.cache_stock_name(pure_code, name, 'xtquant')
            self.logger.info(f"L3 xtquant获取股票名称: {pure_code} -> {name}")
            return name

        # L4: tushare (付费用户补充)
        name = self._get_stock_name_from_tushare(pure_code)
        if name:
            self._stock_name_cache[pure_code] = name
            self.cache_manager.cache_stock_name(pure_code, name, 'tushare')
            self.logger.info(f"L4 tushare获取股票名称: {pure_code} -> {name}")
            return name

        # 所有级别失败，返回代码本身
        self.logger.warning(f"所有级别查找失败，返回代码本身: {pure_code}")
        return pure_code

    def warmup_stock_names(self) -> int:
        """
        预热股票名称缓存 - 从 Tushare 批量获取全市场股票名称，
        写入内存缓存和 SQLite 持久化缓存。

        调用时机：初始化后、盘前准备阶段、或缓存为空时。

        Returns:
            缓存的股票名称数量
        """
        adapter = self.adapters.get('tushare')
        if not adapter or not adapter.is_connected:
            self.logger.warning("Tushare未连接，跳过股票名称预热")
            return 0

        try:
            names = adapter.get_all_stock_names()
            if not names:
                self.logger.warning("Tushare未返回股票名称数据")
                return 0

            # 写入内存缓存
            self._stock_name_cache.update(names)

            # 批量写入 SQLite
            count = self.cache_manager.bulk_cache_stock_names(names, source='tushare')

            self.logger.info(f"股票名称预热完成: {count} 只股票已缓存 (内存+SQLite)")
            return count

        except Exception as e:
            self.logger.error(f"股票名称预热失败: {e}")
            return 0

    def close(self):
        """关闭DataMaster,清理资源"""
        self.logger.info("关闭StockDataMaster...")

        # 🔥 优化: 关闭baostock会话
        if self._bs_session_active:
            try:
                import baostock as bs
                bs.logout()
                self._bs_session_active = False
                self.logger.debug("baostock会话已关闭")
            except Exception as e:
                self.logger.warning(f"关闭baostock会话失败: {e}")

        # 停止健康监控
        self.health_manager.stop_monitoring()

        # 断开所有适配器
        for adapter in self.adapters.values():
            try:
                adapter.disconnect()
            except:
                pass

        self.logger.info("StockDataMaster已关闭")

    def __repr__(self):
        return f"<DataMaster: adapters={len(self.adapters)}, cache={self.cache_manager.enabled}>"


# 便捷函数(兼容现有调用方式)
_global_master = None


def get_data_master(config_path: Optional[str] = None) -> 'StockDataMaster':
    """
    获取全局StockDataMaster实例(单例)

    Args:
        config_path: 配置文件路径

    Returns:
        StockDataMaster实例
    """
    global _global_master
    if _global_master is None:
        _global_master = StockDataMaster(config_path)
    return _global_master
