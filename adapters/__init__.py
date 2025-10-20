"""
适配器工厂

用于创建和管理所有数据源适配器实例
"""

from typing import Dict
from .base_adapter import DataSourceAdapter
from .mootdx_adapter import MootdxAdapter
from .baostock_adapter import BaostockAdapter
from .tushare_adapter import TushareAdapter
from .xtquant_adapter import XtquantAdapter


class AdapterFactory:
    """适配器工厂类"""

    # 适配器映射
    ADAPTER_MAP = {
        'mootdx': MootdxAdapter,
        'baostock': BaostockAdapter,
        'tushare': TushareAdapter,
        'xtquant': XtquantAdapter
    }

    @classmethod
    def create_adapter(cls, name: str, config: Dict) -> DataSourceAdapter:
        """
        创建数据源适配器实例

        Args:
            name: 数据源名称
            config: 数据源配置

        Returns:
            DataSourceAdapter实例

        Raises:
            ValueError: 不支持的数据源类型
        """
        adapter_class = cls.ADAPTER_MAP.get(name)

        if adapter_class is None:
            raise ValueError(f"不支持的数据源类型: {name}")

        return adapter_class(name, config)

    @classmethod
    def get_supported_sources(cls) -> list:
        """
        获取支持的数据源列表

        Returns:
            数据源名称列表
        """
        return list(cls.ADAPTER_MAP.keys())
