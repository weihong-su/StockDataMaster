# StockDataMaster - 股票数据主数据接口

[![Python](https://img.shields.io/badge/Python-3.7+-blue.svg)](https://www.python.org/)
[![License](https://img.shields.io/badge/License-MIT-green.svg)](LICENSE)

专业的股票数据主数据接口系统，提供多数据源集成、智能缓存、健康检测和热切换功能。

## ✨ 核心特性

### 🔌 多数据源集成
- **Mootdx**: 主K线数据源，通达信数据，速度快
- **Baostock**: 估值数据和K线数据，免费稳定
- **Tushare**: 专业金融数据，需要token
- **xtquant**: 实时tick数据，需要QMT客户端

### 💾 智能缓存系统
- SQLite本地缓存，单只股票缓存120条日K线(可配置)
- 双数据源校验机制，确保数据准确性
- 自动缓存更新和清理

### 🏥 健康检测与热切换
- 分钟级健康检测(可配置)
- 自动故障切换，无感知降级
- 平滑数据切换，无数据跳变

### 🎯 统一前复权
- 所有数据源统一使用前复权
- 排除复权计算有问题的数据源

### 📦 易于集成
- 独立Python模块，便捷移植
- 完整的API文档和示例

## 📁 目录结构

```
StockDataMaster/
├── __init__.py              # 模块入口
├── config.py                # 配置管理
├── config.json              # 配置文件
├── data_master.py           # 主数据接口
├── adapters/                # 数据源适配器
│   ├── __init__.py
│   ├── base_adapter.py      # 适配器基类
│   ├── mootdx_adapter.py    # Mootdx适配器
│   ├── baostock_adapter.py  # Baostock适配器
│   ├── tushare_adapter.py   # Tushare适配器
│   └── xtquant_adapter.py   # xtquant适配器
├── cache/                   # 缓存系统
│   ├── __init__.py
│   └── cache_manager.py     # 缓存管理器
├── health/                  # 健康检测
│   ├── __init__.py
│   └── health_manager.py    # 健康管理器
└── README.md                # 本文档
```

## 🚀 快速开始

### 安装依赖

```bash
pip install pandas mootdx baostock tushare
# xtquant需要单独安装QMT客户端
```

### 基本使用

```python
from StockDataMaster import StockDataMaster

# 初始化(单例模式)
master = StockDataMaster()

# 获取日K线数据
df = master.get_kline('600519', freq='d', count=100)
print(df.head())

# 获取30分钟K线
df_30m = master.get_kline('600519', freq='30m', count=50)

# 获取估值数据
df_val = master.get_valuation('600519', start_date='2024-01-01')

# 获取实时行情
tick = master.get_tick('600519')
print(f"最新价: {tick['last']}")

# 查看健康状态
status = master.get_health_status()
print(status)

# 查看缓存统计
stats = master.get_cache_statistics()
print(stats)

# 关闭(释放资源)
master.close()
```

### 配置说明

编辑 `config.json` 配置文件:

```json
{
  "data_sources": {
    "mootdx": {
      "enabled": true,
      "priority": 1,
      "use_for": ["kline", "tick"]
    },
    "tushare": {
      "enabled": true,
      "priority": 3,
      "token": "your_tushare_token_here"
    }
  },
  "cache": {
    "enabled": true,
    "max_days_per_stock": 120
  },
  "health_check": {
    "enabled": true,
    "interval_seconds": 60
  }
}
```

## 📖 API文档

### StockDataMaster主类

#### `get_kline(code, freq='d', start_date=None, end_date=None, count=None, adjust='qfq', use_cache=True)`

获取K线数据

**参数:**
- `code` (str): 股票代码，如'600519'或'sh.600519'
- `freq` (str): 频率，支持'd'(日),'w'(周),'m'(月),'5m','15m','30m','60m'
- `start_date` (str): 开始日期 'YYYY-MM-DD'
- `end_date` (str): 结束日期 'YYYY-MM-DD'
- `count` (int): 获取数量(从最新往前)
- `adjust` (str): 复权类型，'qfq'=前复权(默认)
- `use_cache` (bool): 是否使用缓存(仅日线有效)

**返回:**
- `pd.DataFrame`: 包含date,open,high,low,close,volume,amount列

**示例:**
```python
# 获取最近100条日K线
df = master.get_kline('600519', freq='d', count=100)

# 按日期范围获取
df = master.get_kline('600519', start_date='2024-01-01', end_date='2024-12-31')

# 获取30分钟K线
df = master.get_kline('600519', freq='30m', count=50)
```

#### `get_valuation(code, start_date=None, end_date=None)`

获取估值数据

**参数:**
- `code` (str): 股票代码
- `start_date` (str): 开始日期
- `end_date` (str): 结束日期

**返回:**
- `pd.DataFrame`: 包含pe_ttm,pb,ps_ttm等估值指标

#### `get_tick(code)`

获取实时tick数据

**参数:**
- `code` (str): 股票代码

**返回:**
- `dict`: 实时行情字典，包含open,high,low,close,last,volume,amount等

#### `get_health_status()`

获取系统健康状态

**返回:**
- `dict`: 健康状态报告

#### `get_cache_statistics()`

获取缓存统计信息

**返回:**
- `dict`: 缓存统计信息

#### `cleanup_cache(days=None)`

清理缓存

**参数:**
- `days` (int): 保留天数，默认使用配置值

#### `force_switch_source(usage, target_source)`

强制切换数据源

**参数:**
- `usage` (str): 用途 'kline'/'valuation'/'tick'
- `target_source` (str): 目标数据源名称

**返回:**
- `bool`: 是否成功

## 🔧 高级功能

### 数据源优先级配置

在config.json中设置priority值(数字越小优先级越高):

```json
{
  "data_sources": {
    "mootdx": {"priority": 1},
    "baostock": {"priority": 2},
    "tushare": {"priority": 3}
  }
}
```

### 缓存双源校验

系统自动使用两个数据源进行数据校验:

- 价格容忍度: ±0.01元 或 ±0.5%
- 成交量容忍度: ±5%

只有通过校验的数据才会进入缓存。

### 健康检测配置

```json
{
  "health_check": {
    "enabled": true,
    "interval_seconds": 60,
    "response_time_threshold": 5.0,
    "consecutive_failures_threshold": 3
  }
}
```

### 手动切换数据源

```python
# 强制切换K线数据源到baostock
master.force_switch_source('kline', 'baostock')

# 查看当前活跃数据源
status = master.get_health_status()
print(status['active_sources'])
```

## 🧪 测试

### 运行功能测试

```bash
cd test
python interactive_test_gui.py
```


## 📊 性能指标

基于实际测试(网络环境: 100Mbps):

| 操作 | 平均耗时 | 备注 |
|------|---------|------|
| 获取100条日K线(无缓存) | 0.5-1.5秒 | 取决于数据源 |
| 获取100条日K线(有缓存) | 0.01-0.05秒 | 缓存加速20-100倍 |
| 获取50条30分钟K线 | 0.8-2.0秒 | Mootdx最快 |
| 获取实时tick | 0.3-0.8秒 | 交易时间内 |
| 健康检查 | 0.5-1.0秒 | 每分钟自动执行 |

## ⚠️ 注意事项

1. **Tushare Token**: 需要在config.json中配置有效的token
2. **xtquant**: 需要本地运行QMT客户端，否则自动降级
3. **缓存路径**: 确保cache.db_path目录有写权限
4. **日志文件**: 默认输出到logs目录
5. **数据源限制**:
   - Mootdx: 分钟线最多800条
   - Tushare: 分钟线最多8000条，需要权限
   - Baostock: 免费但速度较慢

## 🐛 故障排查

### 问题: 所有数据源均无法获取数据

**解决方案:**
1. 检查网络连接
2. 查看日志文件: `logs/data_master.log`
3. 运行健康检查: `master.get_health_status()`

### 问题: 缓存不生效

**解决方案:**
1. 检查config.json中cache.enabled是否为true
2. 检查缓存数据库路径是否有写权限
3. 查看缓存统计: `master.get_cache_statistics()`

### 问题: Tushare数据获取失败

**解决方案:**
1. 确认token是否有效
2. 检查Tushare账户权限
3. 查看错误日志

## 📝 更新日志

### v1.0.0 (2025-10-20)
- ✨ 初始版本发布
- 🔌 支持4个数据源(Mootdx, Baostock, Tushare, xtquant)
- 💾 实现智能缓存系统
- 🏥 实现健康检测和热切换
- 📖 完整的文档和测试

## 🤝 贡献

欢迎提交Issue和Pull Request!

## 📄 许可证

MIT License

## 👥 作者

YOLO Team

## 📮 联系方式

如有问题或建议，请提交Issue。

---

**Happy Trading! 📈**
