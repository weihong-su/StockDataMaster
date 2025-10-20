"""
Mootdx数据源适配器

使用mootdx库获取通达信数据,主要用于K线和实时行情
"""

from typing import Optional, Dict, Any
import pandas as pd
from mootdx.quotes import Quotes
from .base_adapter import DataSourceAdapter


class MootdxAdapter(DataSourceAdapter):
    """Mootdx数据源适配器"""

    # 频率映射: 统一格式 -> mootdx格式
    FREQ_MAP = {
        'd': 9,      # 日线
        'w': 5,      # 周线
        'm': 6,      # 月线
        '1': 8,      # 1分钟
        '1m': 8,     # 1分钟(兼容)
        '5': 0,      # 5分钟
        '5m': 0,     # 5分钟(兼容)
        '15': 1,     # 15分钟
        '15m': 1,    # 15分钟(兼容)
        '30': 2,     # 30分钟
        '30m': 2,    # 30分钟(兼容)
        '60': 3,     # 60分钟
        '60m': 3     # 60分钟(兼容)
    }

    def __init__(self, name: str, config: Dict[str, Any]):
        super().__init__(name, config)
        self.client = None

    def connect(self) -> bool:
        """连接Mootdx数据源"""
        try:
            self.client = Quotes.factory('std')  # 使用标准版通达信
            self.is_connected = True
            self.logger.info(f"{self.name} 连接成功")
            return True
        except Exception as e:
            self.logger.error(f"{self.name} 连接失败: {e}")
            self.last_error = str(e)
            self.is_connected = False
            return False

    def disconnect(self):
        """断开连接"""
        self.client = None
        self.is_connected = False
        self.logger.info(f"{self.name} 已断开连接")

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
        获取K线数据

        Args:
            code: 股票代码
            freq: 频率
            start_date: 开始日期(mootdx不支持日期范围,此参数用于后过滤)
            end_date: 结束日期(mootdx不支持日期范围,此参数用于后过滤)
            count: 获取数量(offset参数)
            adjust: 复权类型 'qfq'=前复权, 'hfq'=后复权, None=不复权

        Returns:
            DataFrame
        """
        if not self.is_connected:
            if not self.connect():
                return None

        try:
            # 标准化代码
            code = self.normalize_code(code)

            # 转换频率
            if freq not in self.FREQ_MAP:
                self.logger.error(f"不支持的频率: {freq}")
                return None

            mootdx_freq = self.FREQ_MAP[freq]

            # 默认获取数量
            if count is None:
                count = 800  # mootdx默认值

            # 获取数据
            df = self.client.bars(
                symbol=code,
                frequency=mootdx_freq,
                offset=count,
                adjust=adjust
            )

            if df is None or df.empty:
                self.logger.warning(f"Mootdx未获取到数据: {code}")
                return None

            # 修复mootdx重复列问题: 原始数据包含'vol'和'volume'两列
            # 删除'vol'列,保留'volume'列(因为它是复权后的成交量)
            if 'vol' in df.columns and 'volume' in df.columns:
                df = df.drop(columns=['vol'])
                self.logger.debug("删除重复的vol列,保留复权后的volume列")

            # 标准化列名
            df = self.standardize_dataframe(df)

            # 统一成交量单位为"股" (mootdx返回的是手,需要*100)
            if 'volume' in df.columns:
                df['volume'] = df['volume'] * 100
                self.logger.debug(f"成交量单位转换: 手 -> 股 (*100)")

            # 日期过滤(如果提供了日期范围)
            if start_date:
                df = df[df['date'] >= start_date]
            if end_date:
                df = df[df['date'] <= end_date]

            # 确保必要列存在
            required_cols = ['date', 'open', 'high', 'low', 'close', 'volume']
            if not all(col in df.columns for col in required_cols):
                self.logger.error(f"数据列不完整: {df.columns.tolist()}")
                return None

            # 复权因子统一化处理(修复mootdx部分复权问题)
            if adjust in ['qfq', 'hfq'] and 'factor' in df.columns:
                # 前复权(qfq):以最新日期为基准(最新的factor),历史数据按factor调整
                # 找到最新交易日的factor(DataFrame末尾,时间最新)
                latest_factor = df['factor'].iloc[-1] if len(df) > 0 else 1.0

                # 如果存在factor变化,需要统一化
                if df['factor'].nunique() > 1:
                    # 前复权公式: 调整后价格 = 原价格 × (最新factor / 历史factor)
                    # 这样可以消除除权除息导致的价格跳跃
                    price_cols = ['open', 'high', 'low', 'close']
                    for col in price_cols:
                        if col in df.columns:
                            # 关键修复:历史数据(factor>latest_factor的)需要向下调整
                            # 最新数据(factor=latest_factor的)保持不变
                            df[col] = df[col] * (latest_factor / df['factor'])

                    self.logger.info(
                        f"复权因子统一化: {code}, "
                        f"factor范围 {df['factor'].min():.6f}-{df['factor'].max():.6f}, "
                        f"以最新factor {latest_factor:.6f}为基准"
                    )

            # 清理NaN值
            df = df.dropna(subset=['close'])  # 至少close不能为空

            if df.empty:
                self.logger.warning(f"Mootdx数据清理后为空: {code}")
                return None

            return df

        except Exception as e:
            self.logger.error(f"Mootdx获取K线失败 {code}: {e}")
            self.last_error = str(e)
            self.error_count += 1
            return None

    def get_valuation(
        self,
        code: str,
        start_date: Optional[str] = None,
        end_date: Optional[str] = None
    ) -> Optional[pd.DataFrame]:
        """
        获取估值数据

        注意: Mootdx不提供估值数据,返回None
        """
        self.logger.warning(f"Mootdx不支持估值数据获取")
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
                return None

        try:
            code = self.normalize_code(code)

            # 获取实时行情
            quotes = self.client.quotes([code])

            # 处理DataFrame或列表返回
            if isinstance(quotes, pd.DataFrame):
                if quotes.empty:
                    self.logger.warning(f"Mootdx未获取到实时行情: {code}")
                    return None
                quote = quotes.iloc[0].to_dict()
            elif isinstance(quotes, list):
                if not quotes or len(quotes) == 0:
                    self.logger.warning(f"Mootdx未获取到实时行情: {code}")
                    return None
                quote = quotes[0] if isinstance(quotes[0], dict) else quotes[0].to_dict()
            else:
                self.logger.warning(f"Mootdx未获取到实时行情: {code}")
                return None

            # 转换为统一格式
            tick_data = {
                'code': code,
                'name': quote.get('name', ''),
                'open': quote.get('open', 0),
                'high': quote.get('high', 0),
                'low': quote.get('low', 0),
                'close': quote.get('close', 0),
                'last': quote.get('price', 0),
                'volume': quote.get('vol', 0),
                'amount': quote.get('amount', 0),
                'bid': quote.get('bid1', 0),
                'ask': quote.get('ask1', 0),
                'yesterday_close': quote.get('last_close', 0)
            }

            return tick_data

        except Exception as e:
            self.logger.error(f"Mootdx获取tick失败 {code}: {e}")
            self.last_error = str(e)
            self.error_count += 1
            return None
