"""
Baostock数据源适配器

使用baostock库获取数据,主要用于K线和估值数据
"""

import time
from typing import Optional, Dict, Any
import pandas as pd
import baostock as bs
from .base_adapter import DataSourceAdapter


class BaostockAdapter(DataSourceAdapter):
    """Baostock数据源适配器"""

    # 频率映射
    FREQ_MAP = {
        'd': 'd',
        'w': 'w',
        'm': 'm',
        '5': '5',      # 5分钟
        '5m': '5',     # 5分钟(兼容)
        '15': '15',    # 15分钟
        '15m': '15',   # 15分钟(兼容)
        '30': '30',    # 30分钟
        '30m': '30',   # 30分钟(兼容)
        '60': '60',    # 60分钟
        '60m': '60'    # 60分钟(兼容)
    }

    # 快速失败参数（类级常量）
    _FAST_FAIL_THRESHOLD = 3   # 连续失败 N 次后启用快速失败
    _FAST_FAIL_COOLDOWN = 300  # 快速失败冷却窗口（秒）

    def __init__(self, name: str, config: Dict[str, Any]):
        super().__init__(name, config)
        self.login_result = None
        self._consecutive_failures = 0
        self._last_failure_time = 0.0

    # 连接超时（秒）：通过 socket.setdefaulttimeout 控制 bs.login() 的 TCP 超时
    _CONNECT_TIMEOUT = 5

    def connect(self) -> bool:
        """连接Baostock数据源（带超时保护，最多等待 _CONNECT_TIMEOUT 秒）"""
        import socket
        original_timeout = socket.getdefaulttimeout()
        socket.setdefaulttimeout(self._CONNECT_TIMEOUT)
        try:
            self.login_result = bs.login()
        except Exception as e:
            self.logger.error(f"{self.name} 连接失败: {e}")
            self.last_error = str(e)
            self.is_connected = False
            return False
        finally:
            socket.setdefaulttimeout(original_timeout)

        if self.login_result.error_code == '0':
            self.is_connected = True
            self.logger.info(f"{self.name} 连接成功")
            return True
        else:
            self.logger.error(f"{self.name} 连接失败: {self.login_result.error_msg}")
            self.last_error = self.login_result.error_msg
            self.is_connected = False
            return False

    def disconnect(self):
        """断开连接"""
        try:
            bs.logout()
            self.is_connected = False
            self.logger.info(f"{self.name} 已断开连接")
        except:
            pass

    def _add_bs_prefix(self, code: str) -> str:
        """为股票代码添加baostock前缀"""
        code = self.normalize_code(code)
        if code.startswith(('6', '5')):
            return f'sh.{code}'
        elif code.startswith(('0', '3')):
            return f'sz.{code}'
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
            start_date: 开始日期
            end_date: 结束日期
            count: 获取数量(baostock通过日期范围获取,此参数用于计算start_date)
            adjust: 复权类型 'qfq'=前复权(adjustflag='2')

        Returns:
            DataFrame
        """
        # 快速失败：连续失败超过阈值且在冷却窗口内，立即返回 None
        if (self._consecutive_failures >= self._FAST_FAIL_THRESHOLD and
                time.time() - self._last_failure_time < self._FAST_FAIL_COOLDOWN):
            self.logger.debug(
                f"baostock快速失败(连续{self._consecutive_failures}次网络故障，"
                f"冷却剩余{self._FAST_FAIL_COOLDOWN - (time.time() - self._last_failure_time):.0f}s)"
            )
            return None

        if not self.is_connected:
            if not self.connect():
                self._consecutive_failures += 1
                self._last_failure_time = time.time()
                return None

        try:
            # 添加前缀
            code = self._add_bs_prefix(code)

            # 转换频率
            if freq not in self.FREQ_MAP:
                self.logger.error(f"不支持的频率: {freq}")
                return None

            bs_freq = self.FREQ_MAP[freq]

            # 如果提供count但没有start_date,计算start_date
            if count and not start_date:
                from datetime import datetime, timedelta
                # 估算天数(count * 2倍,充分考虑节假日和周末)
                days = int(count * 2)
                start_date = (datetime.now() - timedelta(days=days)).strftime('%Y-%m-%d')

            # 默认结束日期为今天
            if not end_date:
                from datetime import datetime
                end_date = datetime.now().strftime('%Y-%m-%d')

            # 设置复权类型: 2=前复权
            adjustflag = '2' if adjust == 'qfq' else '1' if adjust == 'hfq' else '3'

            # 定义字段（turn=换手率，仅日线有效；分钟线忽略该字段）
            if bs_freq == 'd':
                fields = "date,code,open,high,low,close,preclose,volume,amount,turn,adjustflag"
            else:
                fields = "date,code,open,high,low,close,preclose,volume,amount,adjustflag"

            # 查询数据
            result = bs.query_history_k_data_plus(
                code,
                fields,
                start_date=start_date,
                end_date=end_date,
                frequency=bs_freq,
                adjustflag=adjustflag
            )

            if result.error_code != '0':
                self.logger.error(f"Baostock查询失败 {code}: {result.error_msg}")
                self.last_error = result.error_msg
                self._consecutive_failures += 1
                self._last_failure_time = time.time()
                return None

            # 转换为DataFrame
            df = result.get_data()
            if df.empty:
                # 改为debug级别,避免重复警告
                self.logger.debug(f"Baostock未获取到数据: {code}")
                return None

            # 数值类型转换
            numeric_cols = ['open', 'high', 'low', 'close', 'preclose', 'volume', 'amount', 'turn']
            for col in numeric_cols:
                if col in df.columns:
                    df[col] = pd.to_numeric(df[col], errors='coerce')

            # 如果指定了count,只取最近count条
            if count:
                df = df.tail(count)

            # 标准化
            df = self.standardize_dataframe(df)

            # 成功：重置连续失败计数
            self._consecutive_failures = 0
            return df

        except Exception as e:
            self.logger.error(f"Baostock获取K线失败 {code}: {e}")
            self.last_error = str(e)
            self.error_count += 1
            self._consecutive_failures += 1
            self._last_failure_time = time.time()
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
            DataFrame,包含pe_ttm,pb,ps_ttm,pcf_ncf等估值指标
        """
        if not self.is_connected:
            if not self.connect():
                return None

        try:
            code = self._add_bs_prefix(code)

            # 默认结束日期为今天
            if not end_date:
                from datetime import datetime
                end_date = datetime.now().strftime('%Y-%m-%d')

            # 默认开始日期为1年前
            if not start_date:
                from datetime import datetime, timedelta
                start_date = (datetime.now() - timedelta(days=365)).strftime('%Y-%m-%d')

            # 查询估值数据
            result = bs.query_history_k_data_plus(
                code,
                "date,code,peTTM,pbMRQ,psTTM,pcfNcfTTM",
                start_date=start_date,
                end_date=end_date,
                frequency="d",
                adjustflag="3"
            )

            if result.error_code != '0':
                self.logger.error(f"Baostock估值查询失败 {code}: {result.error_msg}")
                return None

            df = result.get_data()
            if df.empty:
                self.logger.warning(f"Baostock未获取到估值数据: {code}")
                return None

            # 重命名列
            df = df.rename(columns={
                'peTTM': 'pe_ttm',
                'pbMRQ': 'pb',
                'psTTM': 'ps_ttm',
                'pcfNcfTTM': 'pcf_ncf'
            })

            # 数值转换
            numeric_cols = ['pe_ttm', 'pb', 'ps_ttm', 'pcf_ncf']
            for col in numeric_cols:
                if col in df.columns:
                    df[col] = pd.to_numeric(df[col], errors='coerce')

            return df

        except Exception as e:
            self.logger.error(f"Baostock获取估值失败 {code}: {e}")
            self.last_error = str(e)
            self.error_count += 1
            return None

    def get_tick(self, code: str) -> Optional[Dict[str, Any]]:
        """
        获取实时tick数据

        注意: Baostock不提供实时tick,可以使用5分钟K线最新一条模拟
        """
        try:
            # 获取最近2条5分钟K线
            df = self.get_kline(code, freq='5m', count=2, adjust='qfq')

            if df is None or df.empty:
                return None

            # 使用最新一条数据
            latest = df.iloc[-1]

            tick_data = {
                'code': self.normalize_code(code),
                'open': float(latest['open']),
                'high': float(latest['high']),
                'low': float(latest['low']),
                'close': float(latest['close']),
                'last': float(latest['close']),
                'volume': float(latest['volume']),
                'amount': float(latest.get('amount', 0)),
                'yesterday_close': float(df.iloc[-2]['close']) if len(df) > 1 else float(latest['close'])
            }

            return tick_data

        except Exception as e:
            self.logger.error(f"Baostock模拟tick失败 {code}: {e}")
            self.last_error = str(e)
            return None
