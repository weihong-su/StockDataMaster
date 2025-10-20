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

    def connect(self) -> bool:
        """
        连接xtquant数据源

        注意: xtquant需要本地QMT客户端运行,这里做简化处理
        """
        try:
            # 尝试导入xtquant
            try:
                from xtquant import xtdata
                self.xt_data = xtdata
                self.is_connected = True
                self.logger.info(f"{self.name} 连接成功")
                return True
            except ImportError:
                self.logger.warning(f"{self.name} xtquant库未安装,将使用降级方案")
                self.is_connected = False
                return False

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

        注意: xtquant主要用于实时数据,K线数据建议使用其他数据源
        """
        self.logger.warning(f"xtquant不建议用于K线数据获取,建议使用Mootdx或Baostock")
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
        健康检查

        xtquant的健康检查较为简单,主要检查库是否可用
        """
        result = {
            'status': 'ok',
            'response_time': 0.0,
            'data_freshness': True,
            'error_message': None
        }

        try:
            if not self.is_connected:
                result['status'] = 'error'
                result['error_message'] = 'xtquant未连接'
                return result

            # 尝试获取测试数据
            test_tick = self.get_tick('600519')

            if test_tick is None:
                result['status'] = 'warning'
                result['error_message'] = 'xtquant数据获取异常'
            else:
                result['status'] = 'ok'

        except Exception as e:
            result['status'] = 'error'
            result['error_message'] = str(e)
            self.error_count += 1

        return result
