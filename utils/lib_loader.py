"""
动态库加载管理器

支持内置库和系统库的智能加载和切换
"""

import os
import sys
import importlib
import logging
from typing import Optional, Any


class LibLoader:
    """库加载管理器"""

    def __init__(self, config: dict = None):
        """
        初始化库加载器

        Args:
            config: 配置字典,包含use_builtin_libs等选项
        """
        self.config = config or {}
        self.logger = logging.getLogger("LibLoader")

        # 获取StockDataMaster根目录
        self.root_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
        self.lib_dir = os.path.join(self.root_dir, 'lib')

        # 是否使用内置库(默认优先使用内置库)
        self.use_builtin = self.config.get('use_builtin_libs', True)

        # 已加载的库缓存
        self._loaded_libs = {}

    def load_library(self, lib_name: str, fallback: bool = True) -> Optional[Any]:
        """
        智能加载库(内置库或系统库)

        Args:
            lib_name: 库名称 (mootdx/baostock/tushare/pandas等)
            fallback: 是否在失败时降级尝试另一种方式

        Returns:
            加载的库模块,失败返回None
        """
        # 检查缓存
        if lib_name in self._loaded_libs:
            return self._loaded_libs[lib_name]

        lib_module = None

        if self.use_builtin:
            # 优先尝试内置库
            lib_module = self._load_builtin_lib(lib_name)

            if lib_module is None and fallback:
                # 内置库失败,降级到系统库
                self.logger.warning(f"内置库{lib_name}加载失败,尝试系统库")
                lib_module = self._load_system_lib(lib_name)
        else:
            # 优先尝试系统库
            lib_module = self._load_system_lib(lib_name)

            if lib_module is None and fallback:
                # 系统库失败,降级到内置库
                self.logger.warning(f"系统库{lib_name}加载失败,尝试内置库")
                lib_module = self._load_builtin_lib(lib_name)

        # 缓存结果
        if lib_module is not None:
            self._loaded_libs[lib_name] = lib_module
            self.logger.info(f"库{lib_name}加载成功")
        else:
            self.logger.error(f"库{lib_name}加载失败(内置和系统库均不可用)")

        return lib_module

    def _load_builtin_lib(self, lib_name: str) -> Optional[Any]:
        """
        加载内置库

        Args:
            lib_name: 库名称

        Returns:
            库模块或None
        """
        try:
            builtin_path = os.path.join(self.lib_dir, lib_name)

            if not os.path.exists(builtin_path):
                self.logger.debug(f"内置库路径不存在: {builtin_path}")
                return None

            # 临时添加lib目录到sys.path
            if self.lib_dir not in sys.path:
                sys.path.insert(0, self.lib_dir)

            # 导入内置库
            module = importlib.import_module(lib_name)

            self.logger.debug(f"从内置库加载: {lib_name} ({builtin_path})")
            return module

        except Exception as e:
            self.logger.debug(f"内置库{lib_name}加载失败: {e}")
            return None

    def _load_system_lib(self, lib_name: str) -> Optional[Any]:
        """
        加载系统库

        Args:
            lib_name: 库名称

        Returns:
            库模块或None
        """
        try:
            # 从系统环境导入
            module = importlib.import_module(lib_name)

            self.logger.debug(f"从系统环境加载: {lib_name}")
            return module

        except ImportError as e:
            self.logger.debug(f"系统库{lib_name}不可用: {e}")
            return None

    def check_library(self, lib_name: str) -> dict:
        """
        检查库的可用性

        Args:
            lib_name: 库名称

        Returns:
            检查结果字典
        """
        result = {
            'name': lib_name,
            'builtin_available': False,
            'system_available': False,
            'builtin_path': None,
            'system_version': None,
            'loaded_from': None
        }

        # 检查内置库
        builtin_path = os.path.join(self.lib_dir, lib_name)
        if os.path.exists(builtin_path):
            result['builtin_available'] = True
            result['builtin_path'] = builtin_path

        # 检查系统库
        try:
            module = importlib.import_module(lib_name)
            result['system_available'] = True
            result['system_version'] = getattr(module, '__version__', 'unknown')
        except ImportError:
            pass

        # 检查当前加载状态
        if lib_name in self._loaded_libs:
            result['loaded_from'] = 'cached'

        return result

    def get_library_status(self) -> dict:
        """
        获取所有库的加载状态

        Returns:
            状态字典
        """
        libs = ['mootdx', 'baostock', 'tushare', 'pandas']

        status = {
            'use_builtin': self.use_builtin,
            'lib_dir': self.lib_dir,
            'libraries': {}
        }

        for lib in libs:
            status['libraries'][lib] = self.check_library(lib)

        return status

    def reload_library(self, lib_name: str) -> bool:
        """
        重新加载库

        Args:
            lib_name: 库名称

        Returns:
            是否成功
        """
        if lib_name in self._loaded_libs:
            del self._loaded_libs[lib_name]

        lib = self.load_library(lib_name)
        return lib is not None

    def __repr__(self):
        return f"<LibLoader: builtin={self.use_builtin}, loaded={len(self._loaded_libs)}>"


# 全局库加载器实例
_global_loader = None


def get_lib_loader(config: dict = None) -> LibLoader:
    """
    获取全局库加载器实例(单例)

    Args:
        config: 配置字典

    Returns:
        LibLoader实例
    """
    global _global_loader
    if _global_loader is None:
        _global_loader = LibLoader(config)
    return _global_loader
