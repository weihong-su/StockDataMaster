# API 参考总览

本节 API 文档由 [mkdocstrings](https://mkdocstrings.github.io/) 从源码 docstring 自动抽取,**修改源码注释即修改文档**,无需另行同步。

## 模块速查

| 模块 | 职责 | 入口 |
|------|------|------|
| [`data_master`](data_master.md) | 单例主接口,统一数据访问入口 | `StockDataMaster()` |
| [`cache`](cache.md) | SQLite 缓存 + 双源校验 | `CacheManager` |
| [`health`](health.md) | 后台健康监控、自动故障切换 | `HealthManager` |
| [`adapters`](adapters.md) | Tushare / Mootdx / Baostock / xtquant 适配器 | `AdapterFactory` |
| [`config`](config.md) | `config.json` 读取与点号路径查询 | `get_config()` |
| [`utils`](utils.md) | 重试、库加载等通用工具 | — |

## docstring 风格约定

抽取使用 **Google 风格** + 类型注解,例如:

```python
def get_kline(
    code: str,
    freq: str = 'd',
    start_date: Optional[str] = None,
) -> Optional[pd.DataFrame]:
    """获取K线数据(统一接口)。

    Args:
        code: 股票代码,如 ``'600519'`` 或 ``'sh.600519'``。
        freq: 频率, ``'d'`` 日 / ``'w'`` 周 / ``'m'`` 月 / ``'5m'``…
        start_date: 开始日期 ``'YYYY-MM-DD'``。

    Returns:
        DataFrame,列为 ``date,open,high,low,close,volume,amount``。
    """
```

新增公共函数时遵循此风格即可被自动收录。
