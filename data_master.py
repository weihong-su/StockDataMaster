"""
StockDataMaster主数据接口

提供统一的股票数据访问接口,集成多数据源、缓存、健康检测等功能
"""

import logging
import os
from typing import Optional, Dict, Any
import pandas as pd
from datetime import datetime

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

        # 配置根日志记录器
        logging.basicConfig(
            level=getattr(logging, log_level.upper()),
            format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
            handlers=[
                logging.StreamHandler(),
                logging.FileHandler(log_file) if log_file else logging.NullHandler()
            ]
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
        # 标准化代码
        code = self._normalize_code(code)

        # 日线数据优先使用缓存
        if freq == 'd' and use_cache and self.cache_manager.enabled:
            cached_df = self.cache_manager.get_cached_kline(code, start_date, end_date, count)

            if cached_df is not None and not cached_df.empty:
                # 检查缓存是否足够新
                is_fresh = self._is_cache_fresh(cached_df)
                # 检查数据量是否充足 - 放宽条件,>=95%即可
                # 原因: 双源校验可能导致少数数据校验失败,如119/120
                is_sufficient = count is None or len(cached_df) >= count * 0.95

                self.logger.debug(f"缓存检查: code={code}, is_fresh={is_fresh}, is_sufficient={is_sufficient}, cached_rows={len(cached_df)}, request_count={count}")

                if is_fresh and is_sufficient:
                    # 确保source字段存在(防止attrs丢失)
                    if 'source' not in cached_df.attrs:
                        cached_df.attrs['source'] = 'cache'
                    self.logger.debug(f"从缓存获取{code}数据: {len(cached_df)}条, source={cached_df.attrs.get('source')}")
                    return cached_df
                elif is_fresh and not is_sufficient:
                    self.logger.debug(f"{code}缓存数据不足({len(cached_df)}/{count}条),从数据源补充")
                else:
                    self.logger.debug(f"{code}缓存数据不新鲜(latest={cached_df['date'].iloc[-1]}),重新获取")

        # 从数据源获取
        df = self._fetch_kline_from_source(code, freq, start_date, end_date, count, adjust)

        # 日线数据尝试缓存(双源校验)
        if df is not None and freq == 'd' and use_cache:
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
        从数据源获取K线数据(带故障切换)

        Returns:
            DataFrame
        """
        # 根据频率类型选择数据源
        # 'd','w','m' = 日K线, 其他 = 分钟K线
        if freq in ['d', 'w', 'm']:
            usage_type = 'kline_day'
        else:
            usage_type = 'kline_minute'

        # 获取备用数据源列表(按优先级)
        sources = self.config.get_sources_by_usage(usage_type)

        if not sources:
            # 如果没有找到特定类型的数据源,回退到通用kline
            self.logger.warning(f"未找到{usage_type}数据源,回退到通用kline源")
            sources = self.config.get_sources_by_usage('kline')

        if not sources:
            self.logger.error("没有可用的K线数据源")
            return None

        # 依次尝试数据源
        for source_name in sources:
            adapter = self.adapters.get(source_name)

            if not adapter:
                continue

            try:
                # 缓存预取优化:为提高缓存命中率,实际请求时多获取10%的数据
                # 例如用户请求120条,实际获取132条,多余的数据可供后续缓存使用
                actual_count = count
                if count is not None and freq == 'd':
                    actual_count = int(count * 1.1)
                    self.logger.debug(f"缓存预取优化: 用户请求{count}条,实际获取{actual_count}条(+10%)")

                self.logger.debug(f"从{source_name}获取{code} K线数据")

                df = adapter.get_kline(code, freq, start_date, end_date, actual_count, adjust)

                if df is not None and not df.empty:
                    # 设置数据来源属性
                    df.attrs['source'] = source_name

                    # 如果多获取了数据,截取用户实际需要的数量返回
                    # 但完整数据保存在attrs中,供_try_cache_kline使用
                    if count is not None and len(df) > count:
                        self.logger.debug(f"获取{len(df)}条数据,截取最新{count}条返回,多余{len(df)-count}条将缓存供后续使用")
                        return_df = df.tail(count).copy()
                        return_df.attrs['source'] = source_name
                        # 将完整数据保存在attrs中,供缓存使用
                        return_df.attrs['full_data'] = df
                    else:
                        return_df = df

                    self.logger.debug(f"成功从{source_name}获取{code}数据: 返回{len(return_df)}条")
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
        尝试缓存日K线数据(双源校验)

        策略: Tushare主数据 + (Mootdx或Baostock至少1个)进行校验
        只有校验通过的数据才会进入缓存

        Args:
            code: 股票代码
            df: 已获取的数据(来自Tushare)
            其他参数同get_kline
        """
        if not self.cache_manager.enabled:
            return

        try:
            # 如果df.attrs中包含完整数据(缓存预取优化),使用完整数据进行缓存
            # 这样可以提高后续缓存命中率
            cache_df = df.attrs.get('full_data', df)
            actual_count = count
            if cache_df is not df:
                self.logger.debug(f"使用预取的完整数据进行缓存: {len(cache_df)}条(原{len(df)}条)")
                # 计算实际的count用于获取校验数据
                actual_count = len(cache_df)
            # 获取日K线数据源列表
            sources = self.config.get_sources_by_usage('kline_day')

            if not sources or sources[0] != 'tushare':
                self.logger.warning(f"缓存策略要求Tushare为主数据源,当前主源: {sources[0] if sources else 'None'}")
                # 如果不是Tushare数据,不进入缓存
                return

            # 尝试从Mootdx和Baostock获取校验数据,任一通过即可缓存
            validation_sources = ['mootdx', 'baostock']
            cached = False
            min_pass_rate = 0.8  # 最低校验通过率80%

            for vs_name in validation_sources:
                if vs_name not in sources:
                    continue

                adapter = self.adapters.get(vs_name)
                if not adapter:
                    continue

                try:
                    self.logger.debug(f"尝试{vs_name}校验: {code}")
                    vs_df = adapter.get_kline(code, 'd', start_date, end_date, actual_count, adjust)

                    if vs_df is None or vs_df.empty:
                        self.logger.debug(f"{vs_name}未返回数据")
                        continue

                    # 执行双源校验 - 使用完整数据
                    self.logger.info(f"执行双源校验: Tushare + {vs_name}")
                    validated_df = self.cache_manager.validate_and_cache(code, cache_df, vs_df, 'tushare', vs_name)

                    if validated_df is not None and not validated_df.empty:
                        # 计算校验通过率
                        expected_count = min(len(cache_df), len(vs_df))
                        actual_count = len(validated_df)
                        pass_rate = actual_count / expected_count if expected_count > 0 else 0

                        self.logger.info(f"{code}校验通过率: {pass_rate*100:.1f}% ({actual_count}/{expected_count})")

                        if pass_rate >= min_pass_rate:
                            # 校验通过率达标,缓存成功
                            self.logger.info(f"{code}通过{vs_name}校验(≥{min_pass_rate*100:.0f}%),已缓存")
                            cached = True
                            break  # 成功缓存,无需尝试下一个源
                        else:
                            # 校验通过率不达标,尝试下一个源
                            self.logger.warning(f"{code}{vs_name}校验通过率过低({pass_rate*100:.1f}% < {min_pass_rate*100:.0f}%),尝试下一个源")
                    else:
                        # 校验未通过,尝试下一个源
                        self.logger.warning(f"{code}未通过{vs_name}校验,尝试下一个源")

                except Exception as e:
                    self.logger.warning(f"{vs_name}校验失败: {e},尝试下一个源")
                    continue

            if not cached:
                self.logger.warning(f"{code}所有校验源都未通过,不进入缓存")

        except Exception as e:
            self.logger.error(f"缓存数据失败 {code}: {e}")

    def _is_cache_fresh(self, df: pd.DataFrame) -> bool:
        """
        检查缓存数据是否新鲜

        Args:
            df: 缓存数据

        Returns:
            是否新鲜
        """
        if df is None or df.empty:
            return False

        try:
            latest_date = pd.to_datetime(df['date'].iloc[-1])
            days_diff = (datetime.now() - latest_date).days

            # 判断规则:
            # 宽松策略: 如果用户勾选了"使用缓存",就信任缓存数据
            # 只要缓存数据存在且在合理范围内(365天),就认为是新鲜的
            # 这样即使是测试环境、非交易日、长假期,缓存都能正常使用
            # 如果用户需要最新数据,可以不勾选"使用缓存"
            return days_diff <= 365

        except:
            return False

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

    def get_stock_name(self, code: str) -> Optional[str]:
        """
        获取股票名称

        Args:
            code: 股票代码 (支持 '600000' 或 'sh.600000')

        Returns:
            股票名称,失败返回None
        """
        try:
            # 标准化代码格式为baostock格式 (sh.600000 或 sz.000001)
            if not code.startswith(('sh.', 'sz.')):
                if code.startswith(('6', '688', '689')):
                    bs_code = f'sh.{code}'
                else:
                    bs_code = f'sz.{code}'
            else:
                bs_code = code

            # 使用baostock查询股票基本信息
            if 'baostock' in self.adapters:
                try:
                    import baostock as bs

                    # 确保baostock已登录
                    lg = bs.login()
                    if lg.error_code != '0':
                        self.logger.warning(f"baostock登录失败: {lg.error_msg}")
                        return None

                    # 查询股票基本信息
                    rs = bs.query_stock_basic(code=bs_code)

                    if rs.error_code == '0':
                        data_list = []
                        while (rs.error_code == '0') & rs.next():
                            data_list.append(rs.get_row_data())

                        # 返回第一条记录的股票名称
                        if data_list and len(data_list[0]) > 1:
                            stock_name = data_list[0][1]  # 第二列是code_name
                            self.logger.debug(f"获取股票名称成功: {code} -> {stock_name}")
                            return stock_name
                    else:
                        self.logger.warning(f"查询股票基本信息失败: {rs.error_msg}")

                    # 登出baostock
                    bs.logout()

                except Exception as e:
                    self.logger.error(f"baostock查询股票名称异常: {e}")

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

    def _normalize_code(self, code: str) -> str:
        """标准化股票代码"""
        if code.startswith(('sh.', 'sz.')):
            return code.split('.')[1]
        return code

    def close(self):
        """关闭DataMaster,清理资源"""
        self.logger.info("关闭StockDataMaster...")

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
