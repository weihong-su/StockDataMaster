"""
配置管理模块

负责加载和管理StockDataMaster的所有配置项
"""

import json
import os
from typing import Dict, Any


class Config:
    """配置管理类"""

    def __init__(self, config_path: str = None):
        """
        初始化配置管理器

        Args:
            config_path: 配置文件路径，默认为StockDataMaster/config.json
        """
        if config_path is None:
            # 获取当前文件所在目录
            current_dir = os.path.dirname(os.path.abspath(__file__))
            config_path = os.path.join(current_dir, "config.json")

        self.config_path = config_path
        self.config: Dict[str, Any] = {}
        self.load()

    def load(self):
        """加载配置文件"""
        try:
            with open(self.config_path, 'r', encoding='utf-8') as f:
                self.config = json.load(f)
        except FileNotFoundError:
            raise FileNotFoundError(f"配置文件不存在: {self.config_path}")
        except json.JSONDecodeError as e:
            raise ValueError(f"配置文件JSON格式错误: {e}")

    def reload(self):
        """热重载配置文件"""
        self.load()

    def get(self, key: str, default: Any = None) -> Any:
        """
        获取配置项

        Args:
            key: 配置键,支持点号分隔的嵌套键,如 'cache.max_days_per_stock'
            default: 默认值

        Returns:
            配置值
        """
        keys = key.split('.')
        value = self.config

        for k in keys:
            if isinstance(value, dict) and k in value:
                value = value[k]
            else:
                return default

        return value

    def get_data_source_config(self, source_name: str) -> Dict[str, Any]:
        """
        获取指定数据源的配置

        Args:
            source_name: 数据源名称 (mootdx/baostock/tushare/xtquant)

        Returns:
            数据源配置字典
        """
        return self.config.get('data_sources', {}).get(source_name, {})

    def get_enabled_sources(self) -> list:
        """
        获取所有启用的数据源名称列表,按优先级排序

        Returns:
            数据源名称列表
        """
        sources = self.config.get('data_sources', {})
        enabled = [(name, cfg) for name, cfg in sources.items() if cfg.get('enabled', False)]
        # 按优先级排序
        enabled.sort(key=lambda x: x[1].get('priority', 999))
        return [name for name, _ in enabled]

    def get_sources_by_usage(self, usage: str) -> list:
        """
        获取支持特定用途的数据源列表,按优先级排序

        Args:
            usage: 用途类型 (kline/valuation/tick)

        Returns:
            数据源名称列表
        """
        sources = self.config.get('data_sources', {})
        matched = [
            (name, cfg) for name, cfg in sources.items()
            if cfg.get('enabled', False) and usage in cfg.get('use_for', [])
        ]
        # 按优先级排序
        matched.sort(key=lambda x: x[1].get('priority', 999))
        return [name for name, _ in matched]

    def is_cache_enabled(self) -> bool:
        """缓存是否启用"""
        return self.get('cache.enabled', False)

    def is_health_check_enabled(self) -> bool:
        """健康检查是否启用"""
        return self.get('health_check.enabled', False)

    def is_hot_switch_enabled(self) -> bool:
        """热切换是否启用"""
        return self.get('hot_switch.enabled', False)

    def get_cache_max_days(self) -> int:
        """获取缓存最大天数"""
        return self.get('cache.max_days_per_stock', 120)

    def get_health_check_interval(self) -> int:
        """获取健康检查间隔(秒)"""
        return self.get('health_check.interval_seconds', 60)

    def __repr__(self):
        return f"<Config: {self.config_path}>"


# 全局配置实例
_global_config = None


def get_config(config_path: str = None) -> Config:
    """
    获取全局配置实例(单例模式)

    Args:
        config_path: 配置文件路径

    Returns:
        Config实例
    """
    global _global_config
    if _global_config is None:
        _global_config = Config(config_path)
    return _global_config
