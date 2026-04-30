# 快速开始指南

5分钟上手 StockDataMaster

---

## 环境要求

- Python 3.7+
- Windows / Linux / macOS
- 推荐使用 Anaconda Python 3.8

---

## 安装步骤

### 1. 安装核心依赖

```bash
pip install pandas numpy mootdx baostock tushare
```

### 2. 安装 xtquant（可选）

如需实时Tick数据，需要安装QMT客户端：
- 下载地址: https://dict.thinktrader.net/
- 安装并运行 miniQMT 客户端

### 3. 配置 Tushare Token

编辑 `config.json`：

```json
{
  "data_sources": {
    "tushare": {
      "enabled": true,
      "token": "你的Tushare Token"
    }
  }
}
```

**获取Token**: 访问 https://tushare.pro/ 注册并获取

---

## 第一个示例

### 基本使用

```python
from StockDataMaster import StockDataMaster

# 初始化（单例模式）
master = StockDataMaster()

# 获取日K线数据
df = master.get_kline('600519', freq='d', count=120)
print(df.head())

# 关闭释放资源
master.close()
```

### 查看数据来源

```python
df = master.get_kline('600519', count=120)
source = df.attrs.get('source', 'unknown')

if source == 'cache':
    print("数据来自缓存")
else:
    print(f"数据来自数据源: {source}")
```

### 获取分钟K线

```python
# 获取最近48条5分钟K线（约1个交易日）
df_5m = master.get_kline('600519', freq='5m', count=48)
print(df_5m.tail())
```

### 获取实时行情

```python
# 获取实时tick数据（需要xtquant）
tick = master.get_tick('600519')
print(f"最新价: {tick['last']}")
print(f"涨跌幅: {tick['change_pct']}%")
```

---

## 常用操作

### 查看健康状态

```python
status = master.get_health_status()
print("当前活跃数据源:")
print(status['active_sources'])
```

### 查看缓存统计

```python
stats = master.get_cache_statistics()
print(f"缓存股票数: {stats['stock_count']}")
print(f"缓存记录数: {stats['total_records']}")
print(f"数据库大小: {stats['db_size_mb']} MB")
```

### 清理缓存

```python
# 保留最近120天的数据
master.cleanup_cache(days=120)
```

### 强制切换数据源

```python
# 强制使用baostock作为K线数据源
master.force_switch_source('kline', 'baostock')
```

---

## 交互式测试GUI

推荐使用图形化测试工具：

```bash
cd test
python interactive_test_gui.py
```

**功能**：
- K线数据测试
- 实时数据测试
- 数据源状态监控
- 缓存管理
- 今日走势图

---

## 下一步

- [API 参考手册](api-reference.md) - 完整API文档
- [架构设计](architecture.md) - 深入了解系统设计
- [常见问题](faq.md) - 问题排查

---

**Happy Trading! 📈**
