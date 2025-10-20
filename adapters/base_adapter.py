"""
数据源适配器基类

定义统一的数据源接口规范
"""

from abc import ABC, abstractmethod
from typing import Optional, Dict, Any
import pandas as pd
from datetime import datetime
import logging


class DataSourceAdapter(ABC):
    """数据源适配器抽象基类"""

    def __init__(self, name: str, config: Dict[str, Any]):
        """
        初始化适配器

        Args:
            name: 数据源名称
            config: 数据源配置
        """
        self.name = name
        self.config = config
        self.logger = logging.getLogger(f"DataMaster.{name}")
        self.is_connected = False
        self.last_error = None
        self.error_count = 0

    @abstractmethod
    def connect(self) -> bool:
        """
        连接数据源

        Returns:
            是否连接成功
        """
        pass

    @abstractmethod
    def disconnect(self):
        """断开数据源连接"""
        pass

    @abstractmethod
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
        获取K线数据(统一前复权)

        Args:
            code: 股票代码,如 '600519' 或 'sh.600519'
            freq: 频率 'd'=日线, 'w'=周线, 'm'=月线, '5m'=5分钟, '15m'=15分钟, '30m'=30分钟, '60m'=60分钟
            start_date: 开始日期 'YYYY-MM-DD'
            end_date: 结束日期 'YYYY-MM-DD'
            count: 获取数量(从最新往前数)
            adjust: 复权类型,统一使用'qfq'前复权

        Returns:
            DataFrame,列包含: date,open,high,low,close,volume,amount
            返回None表示失败
        """
        pass

    @abstractmethod
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
            DataFrame,列包含: date,pe_ttm,pb,ps_ttm,pcf_ncf等
            返回None表示失败
        """
        pass

    @abstractmethod
    def get_tick(self, code: str) -> Optional[Dict[str, Any]]:
        """
        获取实时tick数据

        Args:
            code: 股票代码

        Returns:
            字典,包含: open,high,low,close,volume,amount,last,bid,ask等
            返回None表示失败
        """
        pass

    def health_check(self) -> Dict[str, Any]:
        """
        健康检查

        修复说明:
        - 在后台health_check线程中,适配器可能已断开连接
        - 修复方案:每次health_check前强制重新连接
        - 这样确保健康检查准确反映数据源的实际可用性

        Returns:
            健康检查结果字典
            {
                'status': 'ok'|'warning'|'error',
                'response_time': float,  # 响应时间(秒)
                'data_freshness': bool,  # 数据是否新鲜
                'error_message': str|None
            }
        """
        start_time = datetime.now()
        result = {
            'status': 'ok',
            'response_time': 0.0,
            'data_freshness': True,
            'error_message': None
        }

        try:
            # 重要修复:每次health_check前强制重新连接
            # 原因:后台线程调用时,适配器可能已断开连接
            if not self.is_connected:
                self.logger.debug(f"{self.name} health_check: 适配器未连接,尝试重新连接...")
                if not self.connect():
                    result['status'] = 'error'
                    result['error_message'] = f'连接失败: {self.last_error or "未知错误"}'
                    result['response_time'] = (datetime.now() - start_time).total_seconds()
                    return result

            # 尝试获取测试数据(浦发银行600000日K线最近5条 - 活跃股票,数据稳定)
            # 修改原因1:600519(茅台)在某些数据源可能不稳定,改用600000提高健康检查准确性
            # 修改原因2:count=1在某些数据源会被过滤,改用count=30确保能获取到数据
            test_df = self.get_kline('600000', freq='d', count=30)

            # 计算响应时间
            response_time = (datetime.now() - start_time).total_seconds()
            result['response_time'] = response_time

            # 检查数据有效性
            if test_df is None or test_df.empty:
                result['status'] = 'error'
                result['error_message'] = '无法获取测试数据'
                self.error_count += 1
                return result

            # 检查数据新鲜度(最新数据应该是最近3个交易日内的)
            latest_date = pd.to_datetime(test_df['date'].iloc[-1])
            days_diff = (datetime.now() - latest_date).days
            if days_diff > self.config.get('data_freshness_days', 3):
                result['status'] = 'warning'
                result['data_freshness'] = False
                result['error_message'] = f'数据不新鲜,最新数据日期: {latest_date.date()}'

            # 检查响应时间
            threshold = self.config.get('timeout', 5)
            if response_time > threshold:
                result['status'] = 'warning'
                result['error_message'] = f'响应时间过长: {response_time:.2f}秒'

            # 成功则重置错误计数
            self.error_count = 0

        except Exception as e:
            result['status'] = 'error'
            result['error_message'] = str(e)
            result['response_time'] = (datetime.now() - start_time).total_seconds()
            self.error_count += 1
            self.last_error = str(e)
            self.logger.error(f"健康检查失败: {e}")

        return result

    def normalize_code(self, code: str) -> str:
        """
        标准化股票代码为无前缀格式

        Args:
            code: 股票代码,可能带有'sh.'或'sz.'前缀

        Returns:
            标准化后的6位代码
        """
        if code.startswith(('sh.', 'sz.')):
            return code.split('.')[1]
        return code

    def add_prefix(self, code: str) -> str:
        """
        为股票代码添加交易所前缀

        Args:
            code: 6位股票代码

        Returns:
            带前缀的代码,如 'sh.600519' 或 'sz.000001'
        """
        code = self.normalize_code(code)
        if code.startswith(('6', '5')):
            return f'sh.{code}'
        elif code.startswith(('0', '3')):
            return f'sz.{code}'
        return code

    def standardize_dataframe(self, df: pd.DataFrame) -> pd.DataFrame:
        """
        标准化DataFrame格式

        Args:
            df: 原始DataFrame

        Returns:
            标准化后的DataFrame,包含统一列名
        """
        if df is None or df.empty:
            return df

        # 统一列名映射
        column_mapping = {
            'datetime': 'date',
            'vol': 'volume',
            'trade': 'amount'
        }

        # 重命名列
        df = df.rename(columns=column_mapping)

        # 确保date列为字符串格式 YYYY-MM-DD
        if 'date' in df.columns:
            df['date'] = pd.to_datetime(df['date']).dt.strftime('%Y-%m-%d')

        return df

    def __repr__(self):
        return f"<{self.__class__.__name__}: {self.name}, connected={self.is_connected}>"
