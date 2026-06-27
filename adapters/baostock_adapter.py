"""
Baostock数据源适配器

使用baostock库获取数据,主要用于K线和估值数据
"""

import time
from typing import Optional, Dict, Any
import pandas as pd
import baostock as bs
from .base_adapter import DataSourceAdapter
from .baostock_helper import apply_api_key, normalize_adjustflag, describe_error


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
        self.api_key = config.get('api_key', '')
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
            # 新版 baostock 0.9.x: 登录前应用 API Key（旧版无 set_API_key 时自动跳过，匿名访问）
            apply_api_key(self.api_key, self.logger)
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
            error_detail = describe_error(self.login_result.error_code, self.login_result.error_msg)
            self.logger.error(f"{self.name} 连接失败: {error_detail}")
            self.last_error = error_detail
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

    def health_check(self) -> Dict[str, Any]:
        """
        Baostock 专属健康检查。

        不能复用基类实现，因为基类会调用 get_kline()，而 get_kline()
        带有快速失败冷却机制。业务查询连续失败后，基类 health_check 会被
        冷却逻辑直接短路为 None，导致健康检查无法主动探测恢复。
        """
        from datetime import datetime, timedelta

        start_time = time.time()
        result = {
            'status': 'ok',
            'response_time': 0.0,
            'data_freshness': True,
            'error_message': None
        }

        try:
            if not self.is_connected:
                self.logger.debug(f"{self.name} 健康检查: 未连接,尝试重连")
                if not self.connect():
                    result['status'] = 'error'
                    result['error_message'] = f'连接失败: {self.last_error or "未知错误"}'
                    result['response_time'] = time.time() - start_time
                    return result

            end_date = datetime.now().strftime('%Y-%m-%d')
            start_date = (datetime.now() - timedelta(days=90)).strftime('%Y-%m-%d')

            rs = bs.query_history_k_data_plus(
                'sh.600000',
                'date,code,close,volume',
                start_date=start_date,
                end_date=end_date,
                frequency='d',
                adjustflag='2'
            )

            result['response_time'] = time.time() - start_time

            if rs.error_code != '0':
                error_detail = describe_error(rs.error_code, rs.error_msg)
                self.last_error = error_detail
                self._consecutive_failures += 1
                self._last_failure_time = time.time()
                self.error_count += 1
                result['status'] = 'error'
                result['error_message'] = f'Baostock查询失败: {error_detail}'
                return result

            rows = []
            while (rs.error_code == '0') and rs.next():
                rows.append(rs.get_row_data())

            if not rows:
                self._consecutive_failures += 1
                self._last_failure_time = time.time()
                self.error_count += 1
                result['status'] = 'error'
                result['error_message'] = '无法获取测试数据'
                return result

            latest_date = pd.to_datetime(rows[-1][0])
            days_diff = (datetime.now() - latest_date).days
            if days_diff > self.config.get('data_freshness_days', 3):
                result['status'] = 'warning'
                result['data_freshness'] = False
                result['error_message'] = f'数据不新鲜,最新数据日期: {latest_date.date()}'

            threshold = self.config.get('timeout', 5)
            if result['response_time'] > threshold:
                result['status'] = 'warning'
                result['error_message'] = f'响应时间过长: {result["response_time"]:.2f}秒'

            self._consecutive_failures = 0
            self.error_count = 0
            self.last_error = None

        except Exception as e:
            result['status'] = 'error'
            result['error_message'] = str(e)
            result['response_time'] = time.time() - start_time
            self.last_error = str(e)
            self.error_count += 1
            self._consecutive_failures += 1
            self._last_failure_time = time.time()
            self.logger.error(f"Baostock健康检查异常: {e}")

        return result

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
            bs_code = self._add_bs_prefix(code)

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

            # 设置复权类型: 归一化为 baostock 接受的 '1'(后复权)/'2'(前复权)/'3'(不复权)
            adjustflag = normalize_adjustflag(adjust)

            # 字段定义：
            # - 日线/周线/月线：包含 turn(换手率)，无 time 字段
            # - 分钟线：包含 time 字段，无 turn/preclose（baostock不支持）
            is_daily_or_higher = bs_freq in ('d', 'w', 'm')
            if is_daily_or_higher:
                fields = "date,code,open,high,low,close,preclose,volume,amount,turn,adjustflag"
            else:
                fields = "date,time,code,open,high,low,close,volume,amount,adjustflag"

            # 使用官方推荐迭代模式获取数据（比 get_data() 更稳定）
            rs = bs.query_history_k_data_plus(
                bs_code,
                fields,
                start_date=start_date,
                end_date=end_date,
                frequency=bs_freq,
                adjustflag=adjustflag
            )

            if rs.error_code != '0':
                error_detail = describe_error(rs.error_code, rs.error_msg)
                self.logger.error(f"Baostock查询失败 {bs_code}: {error_detail}")
                self.last_error = error_detail
                self._consecutive_failures += 1
                self._last_failure_time = time.time()
                return None

            # 迭代收集数据（官方推荐模式）
            data_list = []
            while (rs.error_code == '0') and rs.next():
                data_list.append(rs.get_row_data())

            if not data_list:
                self.logger.debug(f"Baostock未获取到数据: {bs_code}")
                return None

            df = pd.DataFrame(data_list, columns=rs.fields)

            # 分钟线：合并 date + time 为统一 date 列（格式 YYYY-MM-DD HH:MM:SS）
            if not is_daily_or_higher and 'time' in df.columns:
                df['date'] = df['date'] + ' ' + df['time'].str.strip()
                df = df.drop(columns=['time'])

            # 空字符串替换为 NaN，再做数值转换（baostock 停牌时 turn 为空字符串）
            numeric_cols = ['open', 'high', 'low', 'close', 'preclose', 'volume', 'amount', 'turn']
            for col in numeric_cols:
                if col in df.columns:
                    df[col] = df[col].replace('', None)
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
            bs_code = self._add_bs_prefix(code)

            # 默认结束日期为今天
            if not end_date:
                from datetime import datetime
                end_date = datetime.now().strftime('%Y-%m-%d')

            # 默认开始日期为1年前
            if not start_date:
                from datetime import datetime, timedelta
                start_date = (datetime.now() - timedelta(days=365)).strftime('%Y-%m-%d')

            # 查询估值数据（迭代模式）
            rs = bs.query_history_k_data_plus(
                bs_code,
                "date,code,peTTM,pbMRQ,psTTM,pcfNcfTTM",
                start_date=start_date,
                end_date=end_date,
                frequency="d",
                adjustflag="3"
            )

            if rs.error_code != '0':
                error_detail = describe_error(rs.error_code, rs.error_msg)
                self.logger.error(f"Baostock估值查询失败 {bs_code}: {error_detail}")
                self.last_error = error_detail
                return None

            data_list = []
            while (rs.error_code == '0') and rs.next():
                data_list.append(rs.get_row_data())

            if not data_list:
                self.logger.warning(f"Baostock未获取到估值数据: {bs_code}")
                return None

            df = pd.DataFrame(data_list, columns=rs.fields)

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
