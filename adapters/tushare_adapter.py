"""
Tushare数据源适配器

使用tushare库获取数据,主要用于估值数据和K线数据
"""

from typing import Optional, Dict, Any
import pandas as pd
import tushare as ts
from .base_adapter import DataSourceAdapter


class TushareAdapter(DataSourceAdapter):
    """Tushare数据源适配器"""

    # 频率映射
    FREQ_MAP = {
        'd': 'D',
        'w': 'W',
        'm': 'M',
        '5m': '5min',
        '15m': '15min',
        '30m': '30min',
        '60m': '60min'
    }

    def __init__(self, name: str, config: Dict[str, Any]):
        super().__init__(name, config)
        self.pro = None
        self.token = config.get('token', '')

    def connect(self) -> bool:
        """连接Tushare数据源"""
        try:
            if not self.token:
                self.logger.error(f"{self.name} token未配置")
                self.is_connected = False
                return False

            ts.set_token(self.token)
            self.pro = ts.pro_api()
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
        self.pro = None
        self.is_connected = False
        self.logger.info(f"{self.name} 已断开连接")

    def _convert_code(self, code: str) -> str:
        """
        转换为Tushare格式: 600519.SH 或 000001.SZ

        Args:
            code: 股票代码

        Returns:
            Tushare格式代码
        """
        code = self.normalize_code(code)
        if code.startswith(('6', '5')):
            return f'{code}.SH'
        elif code.startswith(('0', '3')):
            return f'{code}.SZ'
        return code

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
            start_date: 开始日期 YYYY-MM-DD
            end_date: 结束日期 YYYY-MM-DD
            count: 获取数量
            adjust: 复权类型 'qfq'=前复权

        Returns:
            DataFrame
        """
        if not self.is_connected:
            if not self.connect():
                return None

        try:
            ts_code = self._convert_code(code)

            # 转换日期格式: YYYY-MM-DD -> YYYYMMDD
            if start_date:
                start_date = start_date.replace('-', '')
            if end_date:
                end_date = end_date.replace('-', '')

            # 如果提供count但没有start_date,计算start_date
            if count and not start_date:
                from datetime import datetime, timedelta
                # 估算天数(count * 2倍,充分考虑节假日和周末)
                days = int(count * 2)
                start_date = (datetime.now() - timedelta(days=days)).strftime('%Y%m%d')

            # 默认结束日期
            if not end_date:
                from datetime import datetime
                end_date = datetime.now().strftime('%Y%m%d')

            # 选择API - 使用daily接口(120积分可用)
            # 注意: pro_bar需要2000积分,daily只需120积分
            if freq in ['d', 'w', 'm']:
                # 使用日线接口 (120积分)
                df = self.pro.daily(
                    ts_code=ts_code,
                    start_date=start_date,
                    end_date=end_date
                )

                # 如果需要复权,手动处理(因为daily接口不支持复权参数)
                # 注意: 完整的复权需要获取除权除息数据,这里返回未复权数据
                if adjust in ['qfq', 'hfq']:
                    # 改为debug级别,避免重复警告
                    self.logger.debug(f"daily接口不支持复权,返回未复权数据(如需复权需使用pro_bar接口,但需2000积分)")

            else:
                # 分钟线数据: Tushare的分钟线需要2000积分
                # 这里使用daily接口的最新数据作为替代
                self.logger.warning(f"Tushare分钟线需要2000积分,使用日线数据替代")
                df = self.pro.daily(
                    ts_code=ts_code,
                    start_date=start_date,
                    end_date=end_date
                )

            if df is None or df.empty:
                # 改为debug级别,避免重复警告
                self.logger.debug(f"Tushare未获取到数据: {code}")
                return None

            # 列名映射
            # daily接口返回: ts_code, trade_date, open, high, low, close, pre_close, change, pct_chg, vol, amount
            df = df.rename(columns={
                'trade_date': 'date',
                'ts_code': 'code',
                'vol': 'volume',  # daily接口的vol单位是"手"
                'pct_chg': 'pct_change'
            })

            # 日期格式转换: YYYYMMDD -> YYYY-MM-DD
            if 'date' in df.columns:
                df['date'] = pd.to_datetime(df['date']).dt.strftime('%Y-%m-%d')

            # 排序(Tushare返回的是倒序)
            df = df.sort_values('date').reset_index(drop=True)

            # 如果指定了count,只取最近count条
            if count:
                df = df.tail(count)

            # 统一成交量单位为"股" (daily接口的vol单位是"手",需要*100)
            if 'volume' in df.columns:
                df['volume'] = df['volume'] * 100
                self.logger.debug(f"成交量单位转换: 手 -> 股 (*100)")

            # 统一成交额单位为"元" (daily接口的amount单位是"千元",需要*1000)
            if 'amount' in df.columns:
                df['amount'] = df['amount'] * 1000
                self.logger.debug(f"成交额单位转换: 千元 -> 元 (*1000)")

            # 确保必要列
            required_cols = ['date', 'open', 'high', 'low', 'close', 'volume']
            if not all(col in df.columns for col in required_cols):
                self.logger.error(f"数据列不完整: {df.columns.tolist()}")
                return None

            return df

        except Exception as e:
            self.logger.error(f"Tushare获取K线失败 {code}: {e}")
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

        Args:
            code: 股票代码
            start_date: 开始日期
            end_date: 结束日期

        Returns:
            DataFrame
        """
        if not self.is_connected:
            if not self.connect():
                return None

        try:
            ts_code = self._convert_code(code)

            # 转换日期格式
            if start_date:
                start_date = start_date.replace('-', '')
            if end_date:
                end_date = end_date.replace('-', '')

            # 默认日期范围
            if not end_date:
                from datetime import datetime
                end_date = datetime.now().strftime('%Y%m%d')
            if not start_date:
                from datetime import datetime, timedelta
                start_date = (datetime.now() - timedelta(days=365)).strftime('%Y%m%d')

            # 查询每日指标
            df = self.pro.daily_basic(
                ts_code=ts_code,
                start_date=start_date,
                end_date=end_date,
                fields='ts_code,trade_date,pe_ttm,pb,ps_ttm,total_mv,circ_mv'
            )

            if df is None or df.empty:
                self.logger.warning(f"Tushare未获取到估值数据: {code}")
                return None

            # 列名映射
            df = df.rename(columns={
                'trade_date': 'date',
                'ts_code': 'code'
            })

            # 日期格式转换
            df['date'] = pd.to_datetime(df['date']).dt.strftime('%Y-%m-%d')

            # 排序
            df = df.sort_values('date').reset_index(drop=True)

            return df

        except Exception as e:
            self.logger.error(f"Tushare获取估值失败 {code}: {e}")
            self.last_error = str(e)
            self.error_count += 1
            return None

    def get_tick(self, code: str) -> Optional[Dict[str, Any]]:
        """
        获取实时tick数据

        注意: Tushare实时行情需要高级权限,这里使用最新日线数据模拟
        """
        try:
            # 获取最近1天数据
            df = self.get_kline(code, freq='d', count=1, adjust='qfq')

            if df is None or df.empty:
                return None

            latest = df.iloc[-1]

            tick_data = {
                'code': self.normalize_code(code),
                'open': float(latest['open']),
                'high': float(latest['high']),
                'low': float(latest['low']),
                'close': float(latest['close']),
                'last': float(latest['close']),
                'volume': float(latest['volume']),
                'amount': float(latest.get('amount', 0))
            }

            return tick_data

        except Exception as e:
            self.logger.error(f"Tushare模拟tick失败 {code}: {e}")
            self.last_error = str(e)
            return None
