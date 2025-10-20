# StockDataMaster 快速开始指南

## 🚀 5分钟快速上手

### 1. 检查环境

```bash
# 确保Python版本>=3.7
python --version

# 检查依赖库
pip list | grep -E "pandas|mootdx|baostock|tushare"
```

### 2. 配置Tushare Token (可选但推荐)

编辑 `StockDataMaster/config.json`:

```json
{
  "data_sources": {
    "tushare": {
      "enabled": true,
      "token": "你的Tushare_Token"
    }
  }
}
```

### 3. 第一个程序

创建 `test_quickstart.py`:

```python
from StockDataMaster import DataMaster

# 初始化
master = DataMaster()

# 获取贵州茅台最近10条日K线
df = master.get_kline('600519', freq='d', count=10)

print("成功获取数据:")
print(df)

# 查看系统健康状态
status = master.get_health_status()
print("\n当前活跃数据源:", status['active_sources'])

# 清理资源
master.close()
```

运行:
```bash
python test_quickstart.py
```

### 4. 集成到现有代码

**无需修改现有代码！** StockDataMaster已经集成到Methods.py中。

```python
# 原有代码保持不变
import Methods

df = Methods.getStockData('600519', freq='d', offset=100)
# 现在自动使用StockDataMaster，享受缓存加速和故障切换！
```

## 📖 常用操作

### 获取不同周期的K线

```python
from StockDataMaster import DataMaster
master = DataMaster()

# 日K线
df_d = master.get_kline('600519', freq='d', count=100)

# 30分钟K线
df_30m = master.get_kline('600519', freq='30m', count=50)

# 周K线
df_w = master.get_kline('600519', freq='w', count=52)
```

### 按日期范围获取

```python
df = master.get_kline(
    '600519',
    freq='d',
    start_date='2024-01-01',
    end_date='2024-12-31'
)
```

### 获取估值数据

```python
df_val = master.get_valuation(
    '600519',
    start_date='2024-01-01'
)
print(df_val[['date', 'pe_ttm', 'pb']])
```

### 获取实时行情

```python
tick = master.get_tick('600519')
print(f"最新价: {tick['last']}")
print(f"涨跌幅: {(tick['last'] - tick['yesterday_close']) / tick['yesterday_close'] * 100:.2f}%")
```

### 查看缓存统计

```python
stats = master.get_cache_statistics()
print(f"缓存记录数: {stats['total_records']}")
print(f"缓存命中率估算: ~80%")
```

### 清理缓存

```python
# 清理90天前的数据
master.cleanup_cache(days=90)
```

## 🔧 高级功能

### 手动切换数据源

```python
# 强制使用Baostock获取K线数据
master.force_switch_source('kline', 'baostock')

# 查看切换结果
status = master.get_health_status()
print(status['active_sources'])
```

### 禁用缓存(临时)

```python
# 不使用缓存
df = master.get_kline('600519', freq='d', count=100, use_cache=False)
```

### 查看详细健康状态

```python
status = master.get_health_status()

for source, info in status['sources'].items():
    print(f"{source}:")
    print(f"  状态: {info['status']}")
    print(f"  响应时间: {info['response_time']}")
    print(f"  失败次数: {info['failure_count']}")
```

## ⚠️ 常见问题

### Q: 首次运行很慢？
**A**: 首次请求需要建立缓存,后续会快很多(30-50倍加速)

### Q: 某个股票获取失败？
**A**:
1. 检查股票代码是否正确
2. 查看日志: `StockDataMaster/logs/data_master.log`
3. 尝试切换数据源

### Q: 如何关闭StockDataMaster,使用原实现？
**A**: 编辑Methods.py,设置:
```python
_use_data_master = False  # 改为False
```

### Q: Tushare数据获取失败？
**A**:
1. 确认token是否正确
2. 检查Tushare账户权限
3. 系统会自动切换到其他数据源

## 📚 更多文档

- [完整API文档](README.md#api文档)
- [移植指导](../docs/StockDataMaster_Migration_Guide.md)
- [测试报告](../docs/StockDataMaster_Test_Report.md)
- [项目总结](../docs/StockDataMaster_Project_Summary.md)

## 🎯 下一步

1. **运行完整测试**:
   ```bash
   cd test/StockDataMaster
   python test_functional.py
   python test_performance.py
   ```

2. **查看性能对比**:
   ```bash
   python test_performance.py
   ```

3. **集成到生产环境**:
   - 参考 [移植指导文档](../docs/StockDataMaster_Migration_Guide.md)
   - 建议先在测试环境验证

## 💪 开始使用

现在你已经掌握了StockDataMaster的基本用法，开始享受高性能、高可靠的股票数据服务吧！

**Happy Trading! 📈**
