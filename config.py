"""
配置管理模块

负责加载和管理StockDataMaster的所有配置项
"""

import json
import os
from typing import Dict, Any


def _project_root() -> str:
    """获取代码库根目录。"""
    return os.path.dirname(os.path.abspath(__file__))


def _strip_env_value(value: str) -> str:
    """清理 .env 配置值两侧的空白和成对引号。"""
    value = value.strip()
    if len(value) >= 2 and value[0] == value[-1] and value[0] in ("'", '"'):
        return value[1:-1]
    return value


class Config:
    """配置管理类"""

    ENV_OVERRIDES = {
        "TUSHARE_TOKEN": ("data_sources", "tushare", "token"),
        "BAOSTOCK_API_KEY": ("data_sources", "baostock", "api_key"),
        "XTQUANT_QMT_PATH": ("data_sources", "xtquant", "qmt_path"),
        "XTQUANT_ACCOUNT": ("data_sources", "xtquant", "account"),
        "STOCKDATAMASTER_LOG_LEVEL": ("logging", "level"),
        "STOCKDATAMASTER_LOG_FILE": ("logging", "file"),
    }

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
            self._load_dotenv()
            self._apply_env_overrides()
        except FileNotFoundError:
            raise FileNotFoundError(f"配置文件不存在: {self.config_path}")
        except json.JSONDecodeError as e:
            raise ValueError(f"配置文件JSON格式错误: {e}")

    def _load_dotenv(self):
        """加载代码库根目录 .env 文件，不覆盖已存在的环境变量。"""
        env_path = os.path.join(_project_root(), ".env")
        if not os.path.exists(env_path):
            return

        with open(env_path, 'r', encoding='utf-8') as f:
            for raw_line in f:
                line = raw_line.strip()
                if not line or line.startswith("#"):
                    continue
                if "=" not in line:
                    continue

                key, value = line.split("=", 1)
                key = key.strip()
                if not key or key in os.environ:
                    continue

                os.environ[key] = _strip_env_value(value)

    def _apply_env_overrides(self):
        """用环境变量覆盖敏感或本地相关配置。"""
        for env_name, path in self.ENV_OVERRIDES.items():
            value = os.getenv(env_name)
            if value:
                self._set_nested(path, value)

    def _set_nested(self, path, value):
        """按路径写入嵌套配置。"""
        current = self.config
        for key in path[:-1]:
            current = current.setdefault(key, {})
        current[path[-1]] = value

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

    def get_sources_by_role(self, role: str, time_slot: str = None) -> list:
        """
        按 roles 获取支持特定角色的数据源列表,按时段过滤并按优先级排序

        Args:
            role: 角色 (kline_day/kline_minute/tick/validation)
            time_slot: 时段 ('trading'/'after_hours'), None=不过滤

        Returns:
            数据源名称列表,按优先级排序
        """
        self._migrate_legacy_config()

        sources = self.config.get('data_sources', {})
        matched = []

        for name, cfg in sources.items():
            if not cfg.get('enabled', False):
                continue

            roles = cfg.get('roles', {})
            if role not in roles:
                continue

            role_cfg = roles[role]

            # 时段过滤: 如果角色定义了 time_slot,只在匹配时段时包含
            role_time_slot = role_cfg.get('time_slot')
            if time_slot and role_time_slot and role_time_slot != time_slot:
                continue

            priority = role_cfg.get('priority', 999)
            matched.append((name, priority))

        matched.sort(key=lambda x: x[1])
        return [name for name, _ in matched]

    def _migrate_legacy_config(self):
        """
        自动迁移旧格式(use_for + priority)到新格式(roles)
        只在 roles 字段不存在时执行迁移
        """
        sources = self.config.get('data_sources', {})
        for name, cfg in sources.items():
            if 'roles' in cfg:
                continue  # 已有 roles,跳过

            use_for = cfg.get('use_for', [])
            priority = cfg.get('priority', 999)

            # 将每个 use_for 映射为 role
            roles = {}
            for usage in use_for:
                roles[usage] = {'priority': priority}

            if roles:
                cfg['roles'] = roles

    def get_validation_config(self) -> dict:
        """获取投票校验配置"""
        defaults = {
            'mode': 'voting',
            'quorum': 2,
            'strategy': 'first_to_quorum',
            'sources': ['xtquant', 'baostock', 'mootdx'],
            'price_tolerance_abs': 0.01,
            'price_tolerance_pct': 0.005,
            'volume_tolerance_pct': 0.05,
            'min_pass_rate': 0.8,
            'skip_today_in_trading_hours': True
        }
        validation_cfg = self.config.get('validation', {})
        defaults.update(validation_cfg)
        return defaults

    def get_stock_name_config(self) -> dict:
        """获取股票名称配置"""
        defaults = {
            'cache_enabled': True,
            'cleanup_day': 5,
            'baostock_max_consecutive_failures': 3,
            'baostock_retry_cooldown': 300
        }
        sn_cfg = self.config.get('stock_name', {})
        defaults.update(sn_cfg)
        return defaults

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
