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

    # 复权模式开关 (从 config.json 读取)
    #   false (默认) → ts.pro_bar(adj='qfq') 原生前复权，数据最准确，需 2000 积分
    #   true          → pro.daily() + pro.adj_factor() 手动拼接，仅需 120 积分
    def __init__(self, name: str, config: Dict[str, Any]):
        super().__init__(name, config)
        self.pro = None
        self.token = config.get('token', '')
        self.use_adj_factor = config.get('use_adj_factor', False)

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

    def _apply_adj_factor(self, df: pd.DataFrame, ts_code: str,
                          start_date: str, end_date: str,
                          adjust: str = 'qfq') -> pd.DataFrame:
        """
        用 pro.adj_factor() 手动计算前复权/后复权价格

        前复权 (qfq): price * adj_factor / latest_adj_factor  (最新价不变)
        后复权 (hfq): price * adj_factor / earliest_adj_factor (最早价不变)

        Args:
            df: 未复权日线数据 (date 列已格式化为 YYYY-MM-DD)
            ts_code: tushare 格式代码
            start_date: 开始日期 YYYYMMDD
            end_date: 结束日期 YYYYMMDD
            adjust: 'qfq' 或 'hfq'

        Returns:
            复权后的 DataFrame; 失败时返回原始 df
        """
        try:
            adj_df = self.pro.adj_factor(
                ts_code=ts_code,
                start_date=start_date,
                end_date=end_date
            )

            if adj_df is None or adj_df.empty:
                self.logger.warning(f"未获取到复权因子: {ts_code}")
                return df

            adj_df = adj_df.rename(columns={'trade_date': 'date'})
            adj_df['date'] = pd.to_datetime(adj_df['date']).dt.strftime('%Y-%m-%d')

            merged = df.merge(adj_df[['date', 'adj_factor']], on='date', how='left')

            if merged['adj_factor'].isna().all():
                self.logger.warning(f"复权因子全为空: {ts_code}")
                return df

            merged['adj_factor'] = merged['adj_factor'].ffill().bfill()

            if adjust == 'qfq':
                base_factor = merged['adj_factor'].iloc[-1]
            else:
                base_factor = merged['adj_factor'].iloc[0]

            if base_factor == 0:
                self.logger.warning(f"基准复权因子为0: {ts_code}")
                return df

            ratio = merged['adj_factor'] / base_factor

            for col in ['open', 'high', 'low', 'close', 'pre_close']:
                if col in merged.columns:
                    merged[col] = merged[col] * ratio

            merged = merged.drop(columns=['adj_factor'])

            self.logger.debug(
                f"{'前' if adjust == 'qfq' else '后'}复权完成: {ts_code}, "
                f"ratio范围 {ratio.min():.4f}-{ratio.max():.4f}"
            )
            return merged

        except Exception as e:
            self.logger.warning(f"复权因子计算失败 {ts_code}: {e}")
            return df

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

            # ---- 数据获取 + 复权 ----
            #
            # use_adj_factor=false (默认, 推荐):
            #   ts.pro_bar(adj='qfq') 原生接口返回前复权数据
            #   优点: 数据准确, 一步到位
            #   要求: tushare 积分 >= 2000
            #
            # use_adj_factor=true (低积分备选):
            #   pro.daily() 取未复权数据 + pro.adj_factor() 取复权因子
            #   手动计算: qfq_price = price * adj_factor / latest_adj_factor
            #   优点: 仅需 120 积分
            #   缺点: 多一次 API 调用; 部分边缘数据可能有微小差异
            #
            if self.use_adj_factor:
                # --- 模式 B: daily + adj_factor 手动复权 (120 积分) ---
                df = self.pro.daily(
                    ts_code=ts_code,
                    start_date=start_date,
                    end_date=end_date
                )

                if df is None or df.empty:
                    self.logger.debug(f"Tushare未获取到数据: {code}")
                    return None

                # 先重命名 + 格式化, 再做手动复权
                df = df.rename(columns={
                    'trade_date': 'date',
                    'ts_code': 'code',
                    'vol': 'volume',
                    'pct_chg': 'pct_change'
                })
                if 'date' in df.columns:
                    df['date'] = pd.to_datetime(df['date']).dt.strftime('%Y-%m-%d')
                df = df.sort_values('date').reset_index(drop=True)

                if adjust in ['qfq', 'hfq']:
                    df = self._apply_adj_factor(df, ts_code, start_date, end_date, adjust)

            else:
                # --- 模式 A: pro_bar 原生复权 (2000 积分, 默认) ---
                # ts.pro_bar 直接返回已复权数据, adj 参数: qfq/hfq/None
                adj_param = adjust if adjust in ('qfq', 'hfq') else None
                df = ts.pro_bar(
                    ts_code=ts_code,
                    start_date=start_date,
                    end_date=end_date,
                    adj=adj_param,
                    freq=freq if freq in ['d', 'w', 'm'] else 'd'
                )

                if df is None or df.empty:
                    self.logger.debug(f"Tushare未获取到数据: {code}")
                    return None

                # pro_bar 返回的列名: trade_date, open, high, low, close, vol, amount ...
                df = df.rename(columns={
                    'trade_date': 'date',
                    'ts_code': 'code',
                    'vol': 'volume',
                    'pct_chg': 'pct_change'
                })
                if 'date' in df.columns:
                    df['date'] = pd.to_datetime(df['date']).dt.strftime('%Y-%m-%d')
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
