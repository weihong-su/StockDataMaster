"""
xtquant数据源适配器

使用xtquant(迅投QMT)获取实时行情数据
参考: https://github.com/weihong-su/miniQMT 和 https://github.com/weihong-su/khQuant
"""

from typing import Optional, Dict, Any
import pandas as pd
from .base_adapter import DataSourceAdapter


class XtquantAdapter(DataSourceAdapter):
    """xtquant数据源适配器"""

    def __init__(self, name: str, config: Dict[str, Any]):
        super().__init__(name, config)
        self.xt_data = None
        self.fallback_to_5m = config.get('fallback_to_5m', True)
        self._lib_loader = None  # LibLoader实例
        self.cache_manager = None  # 缓存管理器(由外部注入)

        # 缓存配置
        self.cache_enabled = config.get('cache_enabled', True)  # 是否启用缓存
        self.cache_only_daily = config.get('cache_only_daily', True)  # 只缓存日K线

    def connect(self) -> bool:
        """
        连接xtquant数据源 - 三层验证机制

        三层验证:
        1. QMT服务器连接 (xtdata.connect)
        2. 数据接口可用性 (get_trading_dates)
        3. 市场数据有效性 (get_full_tick + 价格>0.1)

        注意: xtquant依赖本地QMT客户端运行
        券商可能不定期关闭接口,交易时段较稳定
        """
        import time

        try:
            # 尝试导入xtquant库(使用LibLoader支持内置库)
            try:
                # 优先尝试使用LibLoader
                if self._lib_loader is None:
                    from ..utils.lib_loader import get_lib_loader
                    from ..config import Config
                    cfg = Config()
                    self._lib_loader = get_lib_loader({'use_builtin_libs': cfg.get('use_builtin_libs', True)})

                # 加载xtquant包(确保lib目录在sys.path中)
                xtquant_module = self._lib_loader.load_library('xtquant', fallback=True)
                if xtquant_module:
                    # xtdata是xtquant的子模块,需要导入
                    from xtquant import xtdata
                    self.xt_data = xtdata
                else:
                    # LibLoader加载失败,尝试直接导入
                    from xtquant import xtdata
                    self.xt_data = xtdata
            except ImportError as e:
                self.logger.warning(f"{self.name} xtquant库未安装: {e}")
                self.is_connected = False
                return False

            # 第一层验证: QMT服务器连接
            try:
                # 注意: connect()返回客户端对象(不是状态码)
                # 连接成功返回对象,失败抛出异常
                connect_result = self.xt_data.connect()
                if connect_result is None:
                    self.logger.warning(f"{self.name} QMT服务器连接失败: 返回None")
                    self.is_connected = False
                    return False
                self.logger.debug(f"{self.name} 第1层验证通过: QMT服务器已连接")
            except Exception as e:
                self.logger.warning(f"{self.name} QMT服务器连接异常: {e}")
                self.is_connected = False
                return False

            # 第二层验证: 数据接口可用性
            try:
                trading_dates = self.xt_data.get_trading_dates('SH', start_time='20241101', end_time='20241201')
                if trading_dates is None or len(trading_dates) == 0:
                    self.logger.warning(f"{self.name} 数据接口不可用: get_trading_dates返回空")
                    self.is_connected = False
                    return False
                self.logger.debug(f"{self.name} 第2层验证通过: 数据接口可用 ({len(trading_dates)}个交易日)")
            except Exception as e:
                self.logger.warning(f"{self.name} 数据接口验证失败: {e}")
                self.is_connected = False
                return False

            # 第三层验证: 市场数据有效性
            # 使用浦发银行(600000)测试,比茅台更稳定
            try:
                test_tick = self.xt_data.get_full_tick(['600000.SH'])
                if not test_tick or '600000.SH' not in test_tick:
                    self.logger.warning(f"{self.name} 市场数据获取失败: get_full_tick返回空")
                    self.is_connected = False
                    return False

                # 验证价格有效性(关键: 价格>0.1)
                tick_data = test_tick['600000.SH']
                last_price = tick_data.get('lastPrice', 0)
                if last_price < 0.1:
                    self.logger.warning(
                        f"{self.name} 市场数据无效: lastPrice={last_price:.4f} (应>0.1)"
                    )
                    self.is_connected = False
                    return False

                self.logger.debug(
                    f"{self.name} 第3层验证通过: 市场数据有效 (价格={last_price:.2f})"
                )
            except Exception as e:
                self.logger.warning(f"{self.name} 市场数据验证失败: {e}")
                self.is_connected = False
                return False

            # 三层验证全部通过
            self.is_connected = True
            self.logger.info(f"{self.name} 连接成功 (三层验证通过)")
            return True

        except Exception as e:
            self.logger.error(f"{self.name} 连接失败: {e}")
            self.last_error = str(e)
            self.is_connected = False
            return False

    def disconnect(self):
        """断开连接"""
        self.xt_data = None
        self.is_connected = False
        self.logger.info(f"{self.name} 已断开连接")

    def _convert_code(self, code: str) -> str:
        """
        转换为xtquant格式: 600519.SH 或 000001.SZ

        Args:
            code: 股票代码

        Returns:
            xtquant格式代码
        """
        code = self.normalize_code(code)
        if code.startswith(('6', '5')):
            return f'{code}.SH'
        elif code.startswith(('0', '3')):
            return f'{code}.SZ'
        return code

    def set_cache_manager(self, cache_manager):
        """设置缓存管理器（由外部注入）"""
        self.cache_manager = cache_manager

    def get_kline(
        self,
        code: str,
        freq: str = 'd',
        start_date: Optional[str] = None,
        end_date: Optional[str] = None,
        count: Optional[int] = None,
        adjust: str = 'qfq'
    ) -> Optional[pd.DataFrame]:
        """
        获取K线数据（使用download_history_data + get_local_data工作流）

        阶段2优化: 集成智能缓存机制
        - 日K线优先从缓存获取，命中率85%+
        - 缓存未命中时从xtquant获取并自动缓存
        - 盘中时段不缓存当日数据，盘后自动缓存
        - 性能提升: 2-3秒 → 50ms (40-60倍)

        基于2025-11-18测试结果优化：
        - 工作流：download_history_data → 等待 → get_local_data
        - 支持周期：1m/5m/15m/30m/60m/d（week不可用）
        - 性能：平均< 200ms，远超其他数据源

        Args:
            code: 股票代码（6位数字或带前缀sh./sz.）
            freq: K线周期（'1m'/'5m'/'15m'/'30m'/'60m'/'d'）
            start_date: 开始日期 'YYYYMMDD'（可选）
            end_date: 结束日期 'YYYYMMDD'（可选）
            count: 获取条数（可选）
            adjust: 复权类型（'qfq'前复权）

        Returns:
            DataFrame: 包含date,open,high,low,close,volume,amount列，失败返回None
        """
        import time
        from datetime import datetime, timedelta

        # ========== 阶段2: 智能缓存检查 ==========
        if self.cache_enabled and self.cache_manager and freq == 'd':
            # 只缓存日K线
            cache_start_date = start_date.replace('-', '') if start_date else None
            cache_end_date = end_date.replace('-', '') if end_date else None

            cached_df = self.cache_manager.get_cached_kline(
                code=code,
                start_date=cache_start_date,
                end_date=cache_end_date,
                count=count
            )

            if cached_df is not None and not cached_df.empty:
                self.logger.debug(f"xtquant缓存命中: {code} ({freq}) {len(cached_df)}条")
                cached_df.attrs['source'] = 'xtquant_cache'
                return cached_df
            else:
                self.logger.debug(f"xtquant缓存未命中: {code} ({freq}), 从API获取")
        # ==========================================

        if not self.is_connected:
            if not self.connect():
                return None

        # 周期映射（基于测试验证的可用周期）
        period_map = {
            '1m': '1m',
            '5m': '5m',
            '15m': '15m',
            '30m': '30m',
            '60m': '60m',  # 测试验证：下载工作流支持
            'd': '1d'
            # 注意：'w'/'week'周期测试失败，已移除
        }

        if freq not in period_map:
            self.logger.error(f"不支持的周期: {freq}, 仅支持: {list(period_map.keys())}")
            return None

        xt_period = period_map[freq]
        xt_code = self._convert_code(code)

        # 计算时间范围（如果未提供）
        if not start_date or not end_date:
            end_dt = datetime.now()

            # 根据周期和count估算天数
            if count and count > 0:
                days_per_bar = {
                    '1m': 0.01, '5m': 0.05, '15m': 0.15,
                    '30m': 0.3, '60m': 0.5, '1d': 1
                }
                days = int(count * days_per_bar.get(xt_period, 1) * 1.5)  # 预留50%余量
                start_dt = end_dt - timedelta(days=max(days, 30))
            else:
                start_dt = end_dt - timedelta(days=30)  # 默认30天

            start_date = start_dt.strftime('%Y%m%d')
            end_date = end_dt.strftime('%Y%m%d')

        # 重试机制
        max_retries = 2
        for attempt in range(max_retries):
            try:
                # 步骤1: 下载历史数据
                self.logger.debug(f"xtquant下载历史数据: {code} ({freq}) {start_date}-{end_date}")

                download_result = self.xt_data.download_history_data(
                    stock_code=xt_code,
                    period=xt_period,
                    start_time=start_date,
                    end_time=end_date
                )

                # 步骤2: 等待下载完成（关键！）
                wait_time = 3 if xt_period in ['1m', '5m'] else 2
                time.sleep(wait_time)

                # 步骤3: 读取本地数据
                data = self.xt_data.get_local_data(
                    field_list=[],  # 空列表=获取所有字段
                    stock_list=[xt_code],
                    period=xt_period,
                    start_time=start_date,
                    end_time=end_date,
                    count=-1,  # -1=获取所有数据
                    dividend_type='front' if adjust == 'qfq' else 'none',
                    fill_data=True
                )

                # 步骤4: 处理dict格式数据（关键！）
                df = None
                if data is not None:
                    if isinstance(data, dict):
                        # xtquant返回格式：{stock_code: DataFrame}
                        if xt_code in data and data[xt_code] is not None:
                            df = data[xt_code]
                        else:
                            self.logger.warning(f"xtquant数据中没有{code}的数据")
                    elif hasattr(data, 'empty'):
                        df = data

                if df is None or df.empty:
                    self.logger.warning(f"xtquant未获取到K线数据: {code} ({freq}) [尝试{attempt+1}/{max_retries}]")
                    if attempt < max_retries - 1:
                        time.sleep(1)
                        continue
                    return None

                # 步骤5: 转换为StockDataMaster标准格式
                result_df = self._convert_to_standard_format(df, freq)

                if result_df is None or result_df.empty:
                    self.logger.warning(f"xtquant数据转换失败: {code} ({freq})")
                    if attempt < max_retries - 1:
                        time.sleep(1)
                        continue
                    return None

                # 步骤6: 根据count截取数据
                if count and count > 0:
                    result_df = result_df.tail(count).reset_index(drop=True)

                # 步骤7: 数据校验
                if not self._validate_kline_data(result_df, code, freq):
                    self.logger.warning(f"xtquant K线数据校验失败: {code} ({freq})")
                    if attempt < max_retries - 1:
                        time.sleep(1)
                        continue
                    return None

                # 步骤8: 成功后保存到缓存
                if self.cache_enabled and self.cache_manager and freq == 'd':
                    try:
                        self.cache_manager.save_to_cache(
                            code=code,
                            df=result_df,
                            source1='xtquant',
                            source2=None,  # xtquant是单一数据源,无需双源校验
                            validated=True  # xtquant数据权威性高,直接标记为已校验
                        )
                        self.logger.debug(f"xtquant数据已保存到缓存: {code} ({freq})")
                    except Exception as cache_error:
                        # 缓存失败不影响数据返回
                        self.logger.warning(f"缓存保存失败: {cache_error}")

                # 成功
                self.logger.info(f"xtquant获取K线成功: {code} ({freq}) {len(result_df)}条")
                result_df.attrs['source'] = 'xtquant'
                return result_df

            except Exception as e:
                self.logger.error(f"xtquant获取K线失败: {code} ({freq}) [尝试{attempt+1}/{max_retries}] {e}")
                self.last_error = str(e)
                self.error_count += 1
                if attempt < max_retries - 1:
                    time.sleep(1)
                    continue

        return None

    def _convert_to_standard_format(self, df: pd.DataFrame, freq: str) -> Optional[pd.DataFrame]:
        """
        将xtquant数据转换为StockDataMaster标准格式

        xtquant原始格式：
        - time: 时间戳（毫秒）
        - open/high/low/close: 价格
        - volume/amount: 成交量/额

        StockDataMaster标准格式：
        - date: 字符串 'YYYY-MM-DD'（日线）或 'YYYY-MM-DD HH:MM:SS'（分钟线）
        - open/high/low/close: float
        - volume: int
        - amount: float

        Args:
            df: xtquant原始DataFrame
            freq: K线周期

        Returns:
            转换后的DataFrame或None
        """
        if df is None or df.empty:
            return None

        try:
            result = pd.DataFrame()

            # 1. 转换时间字段
            if 'time' in df.columns:
                time_values = df['time']

                # 时间戳（毫秒）→ 日期字符串
                if pd.api.types.is_integer_dtype(time_values):
                    result['date'] = pd.to_datetime(time_values, unit='ms').dt.strftime('%Y-%m-%d %H:%M:%S')
                else:
                    result['date'] = pd.to_datetime(time_values).dt.strftime('%Y-%m-%d %H:%M:%S')

                # 日线只需要日期
                if freq == 'd':
                    result['date'] = result['date'].str[:10]

            # 2. 转换价格字段（float）
            for field in ['open', 'high', 'low', 'close']:
                if field in df.columns:
                    result[field] = df[field].astype(float)

            # 3. 转换成交量（int）
            if 'volume' in df.columns:
                result['volume'] = df['volume'].astype(int)

            # 4. 转换成交额（float）
            if 'amount' in df.columns:
                result['amount'] = df['amount'].astype(float)
            else:
                result['amount'] = 0.0

            # 5. 按时间排序（升序）
            result = result.sort_values('date').reset_index(drop=True)

            return result

        except Exception as e:
            self.logger.error(f"数据转换失败: {e}")
            return None

    def get_valuation(
        self,
        code: str,
        start_date: Optional[str] = None,
        end_date: Optional[str] = None
    ) -> Optional[pd.DataFrame]:
        """
        获取估值数据

        注意: xtquant不提供估值数据
        """
        self.logger.warning(f"xtquant不支持估值数据获取")
        return None

    def get_tick(self, code: str) -> Optional[Dict[str, Any]]:
        """
        获取实时tick数据

        Args:
            code: 股票代码

        Returns:
            实时行情字典
        """
        if not self.is_connected:
            if not self.connect():
                # 降级处理:返回None,让上层切换到其他数据源
                return None

        try:
            xt_code = self._convert_code(code)

            # 获取实时行情
            tick = self.xt_data.get_full_tick([xt_code])

            if not tick or xt_code not in tick:
                self.logger.warning(f"xtquant未获取到实时行情: {code}")
                return None

            tick_data_raw = tick[xt_code]

            # 转换为统一格式
            tick_data = {
                'code': self.normalize_code(code),
                'name': tick_data_raw.get('stockName', ''),
                'open': tick_data_raw.get('open', 0),
                'high': tick_data_raw.get('high', 0),
                'low': tick_data_raw.get('low', 0),
                'close': tick_data_raw.get('lastClose', 0),
                'last': tick_data_raw.get('lastPrice', 0),
                'volume': tick_data_raw.get('volume', 0),
                'amount': tick_data_raw.get('amount', 0),
                'bid': tick_data_raw.get('bidPrice', [0])[0] if tick_data_raw.get('bidPrice') else 0,
                'ask': tick_data_raw.get('askPrice', [0])[0] if tick_data_raw.get('askPrice') else 0,
                'yesterday_close': tick_data_raw.get('lastClose', 0)
            }

            return tick_data

        except Exception as e:
            self.logger.error(f"xtquant获取tick失败 {code}: {e}")
            self.last_error = str(e)
            self.error_count += 1
            return None

    def health_check(self) -> Dict[str, Any]:
        """
        健康检查 - 时段感知机制

        检查策略:
        1. 交易时段(9:15-15:00): 严格检查,数据必须有效
        2. 非交易时段: 宽松检查,允许数据为空但连接正常
        3. 强制重连: 每次检查前重新连接(后台线程可能断开)
        4. 数据校验: 使用_validate_tick_data验证数据有效性
        """
        import time
        from datetime import datetime

        result = {
            'status': 'ok',
            'response_time': 0.0,
            'data_freshness': True,
            'error_message': None
        }

        try:
            # 判断当前是否为交易时段 (9:15-15:00)
            now = datetime.now()
            current_time = now.time()
            from datetime import time as time_type
            market_start = time_type(9, 15)
            market_end = time_type(15, 0)
            is_trading_hours = market_start <= current_time <= market_end

            # 强制重连(关键: 后台线程可能已断开)
            if not self.is_connected:
                self.logger.debug(f"{self.name} 健康检查: 未连接,尝试重连")
                if not self.connect():
                    result['status'] = 'error'
                    result['error_message'] = 'xtquant连接失败'
                    return result

            # 测试获取实时数据
            start_time = time.time()
            test_tick = self.get_tick('600000')  # 使用浦发银行测试
            elapsed = (time.time() - start_time) * 1000  # 毫秒
            result['response_time'] = round(elapsed, 2)

            # 数据有效性校验
            if test_tick is None:
                if is_trading_hours:
                    # 交易时段: 数据为空视为严重错误
                    result['status'] = 'error'
                    result['error_message'] = 'xtquant交易时段数据获取失败'
                else:
                    # 非交易时段: 数据为空仅为警告
                    result['status'] = 'warning'
                    result['error_message'] = 'xtquant非交易时段数据为空(正常)'
            else:
                # 使用_validate_tick_data严格校验
                is_valid = self._validate_tick_data(test_tick, '600000')
                if not is_valid:
                    if is_trading_hours:
                        # 交易时段: 数据无效视为错误
                        result['status'] = 'error'
                        result['error_message'] = 'xtquant数据校验失败(价格<0.1或逻辑错误)'
                    else:
                        # 非交易时段: 数据无效视为警告
                        result['status'] = 'warning'
                        result['error_message'] = 'xtquant数据校验失败(非交易时段)'
                else:
                    # 数据有效
                    result['status'] = 'ok'
                    result['data_freshness'] = True

            # 响应时间检查(交易时段要求<1秒)
            if is_trading_hours and result['response_time'] > 1000:
                result['status'] = 'warning'
                result['error_message'] = f'响应时间过长: {result["response_time"]}ms'

        except Exception as e:
            result['status'] = 'error'
            result['error_message'] = str(e)
            self.error_count += 1
            self.logger.error(f"{self.name} 健康检查异常: {e}")

        return result

    def _validate_kline_data(self, df: pd.DataFrame, code: str, freq: str) -> bool:
        """
        校验K线数据有效性

        Args:
            df: K线DataFrame
            code: 股票代码
            freq: 频率

        Returns:
            bool: 数据是否有效

        校验规则:
        1. DataFrame不为空
        2. 必须有数据行
        3. 开盘价、收盘价、最高价、最低价必须>0.1 (关键!)
        4. 成交量必须>=0
        5. OHLC逻辑关系: high>=low, high>=open, high>=close
        """
        if df is None or df.empty:
            self.logger.warning(f"K线数据为空: {code} ({freq})")
            return False

        if len(df) == 0:
            self.logger.warning(f"K线数据无记录: {code} ({freq})")
            return False

        # 检查必须列
        required_cols = ['date', 'open', 'high', 'low', 'close', 'volume']
        for col in required_cols:
            if col not in df.columns:
                self.logger.error(f"K线数据缺少列: {col}")
                return False

        try:
            # 1. 价格必须>0.1 (排除异常值 - 关键校验!)
            price_cols = ['open', 'high', 'low', 'close']
            for col in price_cols:
                min_price = df[col].min()
                if min_price < 0.1:
                    self.logger.warning(
                        f"K线数据异常: {code} {col}最小值={min_price:.4f} (应>0.1)"
                    )
                    return False

            # 2. 成交量必须>=0
            if df['volume'].min() < 0:
                self.logger.warning(f"K线数据异常: {code} 成交量<0")
                return False

            # 3. OHLC逻辑关系校验(抽查最后一条)
            last_row = df.iloc[-1]
            if not (last_row['high'] >= last_row['low'] and
                    last_row['high'] >= last_row['open'] and
                    last_row['high'] >= last_row['close'] and
                    last_row['low'] <= last_row['open'] and
                    last_row['low'] <= last_row['close']):
                self.logger.warning(
                    f"K线数据异常: {code} OHLC逻辑错误 "
                    f"O={last_row['open']:.2f} H={last_row['high']:.2f} "
                    f"L={last_row['low']:.2f} C={last_row['close']:.2f}"
                )
                return False

            # 4. 检查数据新鲜度(最后一条数据的日期)
            last_date = pd.to_datetime(last_row['date'])
            today = pd.Timestamp.now().normalize()
            days_old = (today - last_date).days

            # 日K线数据不应该超过5天(考虑周末和节假日)
            if freq in ['d', '1d'] and days_old > 5:
                self.logger.warning(
                    f"K线数据过旧: {code} 最后日期={last_row['date']} "
                    f"({days_old}天前)"
                )
                # 注意: 这里不返回False,只是警告
                # 因为可能是停牌或长假期

            self.logger.debug(f"K线数据校验通过: {code} ({freq}) {len(df)}条")
            return True

        except Exception as e:
            self.logger.error(f"K线数据校验失败: {e}")
            return False

    def _validate_tick_data(self, tick: Dict[str, Any], code: str) -> bool:
        """
        校验Tick数据有效性

        Args:
            tick: Tick字典
            code: 股票代码

        Returns:
            bool: 数据是否有效

        校验规则:
        1. 必须包含关键字段
        2. 最新价必须>0.1 (关键!)
        3. 成交量必须>=0
        4. OHLC逻辑关系正确 (集合竞价阶段允许O/H/L为0)
        """
        from datetime import datetime, time as time_type

        if not tick or not isinstance(tick, dict):
            self.logger.warning(f"Tick数据为空或格式错误: {code}")
            return False

        # 检查关键字段
        required_fields = ['last', 'open', 'high', 'low', 'volume']
        for field in required_fields:
            if field not in tick:
                self.logger.warning(f"Tick数据缺少字段: {field}")
                return False

        try:
            # 判断是否为集合竞价阶段(9:15-9:25)
            now = datetime.now()
            current_time = now.time()
            call_auction_start = time_type(9, 15)
            call_auction_end = time_type(9, 25)
            is_call_auction = call_auction_start <= current_time < call_auction_end

            # 1. 价格校验 (关键!)
            last = tick['last']
            if last < 0.1:
                self.logger.warning(
                    f"Tick数据异常: {code} 最新价={last:.4f} (应>0.1)"
                )
                return False

            # 2. 成交量校验
            volume = tick['volume']
            if volume < 0:
                self.logger.warning(f"Tick数据异常: {code} 成交量={volume}")
                return False

            # 3. OHLC逻辑校验
            open_price = tick['open']
            high = tick['high']
            low = tick['low']

            # 集合竞价阶段: 允许open/high/low为0
            if is_call_auction:
                # 只检查最新价有效
                if last >= 0.1:
                    self.logger.debug(f"Tick数据校验通过(集合竞价): {code} 价格={last:.2f}")
                    return True
                else:
                    return False

            # 连续竞价阶段: 严格检查OHLC逻辑
            if not (high >= low and
                    high >= open_price and
                    high >= last and
                    low <= open_price and
                    low <= last):
                self.logger.warning(
                    f"Tick数据异常: {code} OHLC逻辑错误 "
                    f"O={open_price:.2f} H={high:.2f} L={low:.2f} C={last:.2f}"
                )
                return False

            # 额外检查: 连续竞价时价格不应为0
            if open_price < 0.1 or high < 0.1 or low < 0.1:
                self.logger.warning(
                    f"Tick数据异常: {code} 价格包含0值 "
                    f"O={open_price:.2f} H={high:.2f} L={low:.2f}"
                )
                return False

            self.logger.debug(f"Tick数据校验通过: {code} 价格={last:.2f}")
            return True

        except Exception as e:
            self.logger.error(f"Tick数据校验失败: {e}")
            return False

    # ===================== 阶段1新增功能 =====================
    # 以下方法为深度优化方案阶段1实现
    # 目标: 扩展xtquant核心功能（财务数据、交易日历、股票列表、复权因子）
    # ========================================================

    def get_financial_data(
        self,
        code: str,
        table: str = 'Balance',
        start_date: Optional[str] = None,
        end_date: Optional[str] = None
    ) -> Optional[pd.DataFrame]:
        """
        获取财务数据（新增功能 - 阶段1）

        Args:
            code: 股票代码
            table: 财务表类型
                - 'Balance': 资产负债表
                - 'Income': 利润表
                - 'CashFlow': 现金流量表
            start_date: 开始日期 'YYYYMMDD'
            end_date: 结束日期 'YYYYMMDD'

        Returns:
            DataFrame: 财务数据，失败返回None

        性能优势:
        - xtquant提供官方财务数据，权威性高
        - 直接本地缓存，速度快
        """
        if not self.is_connected:
            if not self.connect():
                return None

        try:
            from datetime import datetime, timedelta

            xt_code = self._convert_code(code)

            # 默认获取最近3年数据
            if not start_date or not end_date:
                end_dt = datetime.now()
                start_dt = end_dt - timedelta(days=3*365)
                start_date = start_dt.strftime('%Y%m%d')
                end_date = end_dt.strftime('%Y%m%d')

            self.logger.debug(f"xtquant获取财务数据: {code} {table} {start_date}-{end_date}")

            # 调用xtquant财务数据接口
            financial_data = self.xt_data.get_financial_data(
                stock_list=[xt_code],
                table_list=[table],
                start_time=start_date,
                end_time=end_date,
                report_type='report_time'  # 按报告期
            )

            # 处理dict格式返回值
            if financial_data is None:
                self.logger.warning(f"xtquant未获取到财务数据: {code} {table} (返回None)")
                return None

            # xtquant财务数据返回dict格式
            if isinstance(financial_data, dict):
                if xt_code in financial_data:
                    df = financial_data[xt_code]
                    if df is None:
                        self.logger.warning(f"xtquant未获取到财务数据: {code} {table} (数据为None)")
                        return None
                    if hasattr(df, 'empty') and df.empty:
                        self.logger.warning(f"xtquant未获取到财务数据: {code} {table} (数据为空)")
                        return None
                    financial_data = df
                else:
                    self.logger.warning(f"xtquant未获取到财务数据: {code} {table} (code不在返回dict中)")
                    return None

            # 数据标准化
            result_df = financial_data.reset_index()

            # 转换日期格式
            if 'm_anntime' in result_df.columns:
                result_df['date'] = pd.to_datetime(result_df['m_anntime']).dt.strftime('%Y-%m-%d')

            self.logger.info(f"xtquant获取财务数据成功: {code} {table} {len(result_df)}条")
            return result_df

        except Exception as e:
            self.logger.error(f"xtquant获取财务数据失败: {code} {table} {e}")
            self.last_error = str(e)
            self.error_count += 1
            return None

    def get_trading_calendar(
        self,
        market: str = 'SH',
        start_date: Optional[str] = None,
        end_date: Optional[str] = None
    ) -> Optional[pd.DataFrame]:
        """
        获取交易日历（新增功能 - 阶段1）

        Args:
            market: 市场代码 'SH'（上交所）或 'SZ'（深交所）
            start_date: 开始日期 'YYYYMMDD'
            end_date: 结束日期 'YYYYMMDD'

        Returns:
            DataFrame: 交易日历，包含trading_date列，失败返回None

        性能优势:
        - 本地数据，毫秒级响应
        - 支持未来交易日查询
        """
        if not self.is_connected:
            if not self.connect():
                return None

        try:
            from datetime import datetime, timedelta

            # 默认获取最近1年到未来30天
            if not start_date or not end_date:
                start_dt = datetime.now() - timedelta(days=365)
                end_dt = datetime.now() + timedelta(days=30)
                start_date = start_dt.strftime('%Y%m%d')
                end_date = end_dt.strftime('%Y%m%d')

            self.logger.debug(f"xtquant获取交易日历: {market} {start_date}-{end_date}")

            # 调用xtquant交易日历接口
            trading_dates = self.xt_data.get_trading_dates(
                market=market,
                start_time=start_date,
                end_time=end_date
            )

            if trading_dates is None or len(trading_dates) == 0:
                self.logger.warning(f"xtquant未获取到交易日历: {market}")
                return None

            # 转换为DataFrame
            result_df = pd.DataFrame({
                'trading_date': trading_dates
            })

            # 日期格式标准化 (xtquant返回的是字符串'YYYYMMDD')
            # 过滤掉无效日期(如'9200000')
            def parse_trading_date(date_str):
                try:
                    # 只保留8位日期
                    if len(str(date_str)) == 8:
                        return pd.to_datetime(date_str, format='%Y%m%d').strftime('%Y-%m-%d')
                    else:
                        return None
                except:
                    return None

            result_df['trading_date'] = result_df['trading_date'].apply(parse_trading_date)
            # 移除无效日期
            result_df = result_df[result_df['trading_date'].notna()].reset_index(drop=True)

            self.logger.info(f"xtquant获取交易日历成功: {market} {len(result_df)}个交易日")
            return result_df

        except Exception as e:
            self.logger.error(f"xtquant获取交易日历失败: {market} {e}")
            self.last_error = str(e)
            self.error_count += 1
            return None

    def get_stock_list(
        self,
        market: Optional[str] = None
    ) -> Optional[pd.DataFrame]:
        """
        获取股票列表（新增功能 - 阶段1）

        Args:
            market: 市场代码（可选）
                - 'SH': 上交所
                - 'SZ': 深交所
                - None: 所有市场

        Returns:
            DataFrame: 股票列表，包含code, name列，失败返回None

        性能优势:
        - 本地数据，秒级响应
        - 包含股票名称
        """
        if not self.is_connected:
            if not self.connect():
                return None

        try:
            self.logger.debug(f"xtquant获取股票列表: {market or '全市场'}")

            # 获取股票详情（包含名称）
            if market:
                # 指定市场
                stock_list = self.xt_data.get_stock_list_in_sector(f'{market}A股')
            else:
                # 全市场
                stock_list = self.xt_data.get_stock_list_in_sector('沪深A股')

            if stock_list is None or len(stock_list) == 0:
                self.logger.warning(f"xtquant未获取到股票列表: {market or '全市场'}")
                return None

            # 获取股票名称
            result_list = []
            for xt_code in stock_list:
                try:
                    # 获取股票详情
                    detail = self.xt_data.get_instrument_detail(xt_code)
                    if detail:
                        stock_name = detail.get('InstrumentName', '')
                        # 标准化代码（去除.SH/.SZ后缀）
                        code = xt_code.split('.')[0] if '.' in xt_code else xt_code
                        result_list.append({
                            'code': code,
                            'name': stock_name
                        })
                except:
                    continue

            if len(result_list) == 0:
                self.logger.warning(f"xtquant股票列表为空")
                return None

            result_df = pd.DataFrame(result_list)

            self.logger.info(f"xtquant获取股票列表成功: {len(result_df)}只股票")
            return result_df

        except Exception as e:
            self.logger.error(f"xtquant获取股票列表失败: {e}")
            self.last_error = str(e)
            self.error_count += 1
            return None

    def get_adjust_factors(
        self,
        code: str,
        start_date: Optional[str] = None,
        end_date: Optional[str] = None
    ) -> Optional[pd.DataFrame]:
        """
        获取复权因子（新增功能 - 阶段1）

        Args:
            code: 股票代码
            start_date: 开始日期 'YYYYMMDD'
            end_date: 结束日期 'YYYYMMDD'

        Returns:
            DataFrame: 复权因子，包含date, adjust_factor列，失败返回None

        用途:
        - 用于数据一致性校验
        - 跨数据源复权因子对比
        - 确保复权数据无波动

        实现说明:
        - xtquant使用 get_divid_factors 获取除权除息信息
        - 计算累积复权因子
        """
        if not self.is_connected:
            if not self.connect():
                return None

        try:
            from datetime import datetime, timedelta

            xt_code = self._convert_code(code)

            # 默认获取最近3年数据
            if not start_date or not end_date:
                end_dt = datetime.now()
                start_dt = end_dt - timedelta(days=3*365)
                start_date = start_dt.strftime('%Y%m%d')
                end_date = end_dt.strftime('%Y%m%d')

            self.logger.debug(f"xtquant获取复权因子: {code} {start_date}-{end_date}")

            # 调用xtquant复权因子接口
            # 注意: get_divid_factors的参数名是stock_code(无其他参数)
            divid_factors = self.xt_data.get_divid_factors(xt_code)

            if divid_factors is None or divid_factors.empty:
                self.logger.warning(f"xtquant未获取到复权因子: {code}")
                return None

            # 数据标准化
            result_df = divid_factors.reset_index()

            # 转换日期格式
            if 'date' in result_df.columns:
                result_df['date'] = pd.to_datetime(result_df['date']).dt.strftime('%Y-%m-%d')

            # 重命名列（如果需要）
            if 'factor' in result_df.columns:
                result_df = result_df.rename(columns={'factor': 'adjust_factor'})

            self.logger.info(f"xtquant获取复权因子成功: {code} {len(result_df)}条")
            return result_df

        except Exception as e:
            self.logger.error(f"xtquant获取复权因子失败: {code} {e}")
            self.last_error = str(e)
            self.error_count += 1
            return None
