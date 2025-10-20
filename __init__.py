"""
StockDataMaster - 股票数据主数据接口系统

多数据源集成、智能缓存、健康检测、热切换的专业股票数据接口

主要功能:
- 多数据源适配(Mootdx, Baostock, Tushare, xtquant)
- 智能缓存系统(SQLite + 双源校验)
- 健康检测与热切换(分钟级监控)
- 平滑数据切换(无数据跳变)
- 统一前复权处理
- 内置库支持(开箱即用,可移植)

作者: StockQuant Team
版本: 1.1.0
"""

from .data_master import StockDataMaster

# 向后兼容：保留 DataMaster 别名
DataMaster = StockDataMaster

__version__ = "1.1.1"
__all__ = ["StockDataMaster", "DataMaster"]  # DataMaster保留向后兼容
