# 常见问题 FAQ

StockDataMaster 常见问题解答

---

## 安装与配置

### Q1: 如何安装依赖？

**A**:

```bash
# 核心依赖
pip install pandas numpy mootdx baostock tushare

# xtquant（可选，需要QMT客户端）
# 从 https://dict.thinktrader.net/ 下载miniQMT
```

### Q2: Tushare Token 如何配置？

**A**: 在 `config.json` 中配置：

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

获取Token：访问 https://tushare.pro/ 注册并获取

### Q3: xtquant 如何配置？

**A**:
1. 下载并安装 miniQMT 客户端
2. 运行 miniQMT
3. StockDataMaster 会自动连接

**注意**: 如果QMT未运行，xtquant会自动禁用，不影响其他功能

---

## 缓存相关

### Q4: 盘中请求数据为什么不使用缓存？

**A**: 盘中时段（09:30-15:00），当日K线数据是动态变化的。为确保数据实时性，系统不缓存当日数据，每次请求都从数据源获取最新数据。盘后时段（15:00后），数据已固定，会正常缓存。

### Q5: 如何判断返回的数据是否来自缓存？

**A**: 检查 `df.attrs['source']` 属性：

```python
df = master.get_kline('600519', count=120)
source = df.attrs.get('source', 'unknown')

if source == 'cache':
    print("数据来自缓存")
else:
    print(f"数据来自数据源: {source}")
```

### Q6: 为什么分钟线不缓存？

**A**: 原因：
1. 分钟线数据量大（1天48条×多股票），缓存成本高
2. 分钟线主要用于实时分析，时效性要求高
3. 数据源限制（Mootdx最多800条），不适合长期缓存

### Q7: 如何提高缓存命中率？

**A**: 最佳实践：

```python
# ✅ 好：请求历史数据（充分利用缓存）
df = master.get_kline('600519', start_date='2025-10-01', end_date='2025-10-24')

# ✅ 好：盘后请求最新数据（使用缓存）
df = master.get_kline('600519', count=120)  # 盘后时段

# ⚠️ 一般：盘中请求最新数据（不使用缓存）
df = master.get_kline('600519', count=120)  # 盘中时段

# ❌ 差：禁用缓存
df = master.get_kline('600519', count=120, use_cache=False)
```

### Q8: 请求超过120条数据会怎样？

**A**:
- 系统会从数据源获取完整数据
- 但只缓存最新120条
- 超过120条的历史数据不缓存
- 建议：如需超长数据，使用日期范围请求，并分段获取

### Q9: 如何清理缓存？

**A**:

```python
# 方法1：清理超过120天的旧数据
master.cleanup_cache(days=120)

# 方法2：手动删除缓存数据库
import os
os.remove('cache/kline_cache.db')
# 下次启动时会自动重建
```

---

## 数据获取

### Q10: 周末请求数据返回什么？

**A**: 周末/节假日请求数据时：
- 返回最后一个交易日（通常是上周五）的数据
- 使用缓存，不会调用数据源API
- 最新数据日期会早于当前日期

```python
# 周六请求
df = master.get_kline('600519', count=120)
print(df['date'].iloc[-1])  # 输出: 2025-10-24（周五）
```

### Q11: 如何获取分钟K线？

**A**:

```python
# 获取5分钟K线（推荐48条，约1个交易日）
df = master.get_kline('600519', freq='5m', count=48)

# 获取15分钟K线
df = master.get_kline('600519', freq='15m', count=80)
```

**注意**: Mootdx分钟线最多800条，超过会失败

### Q12: 实时Tick数据如何获取？

**A**:

```python
# 需要运行QMT客户端
tick = master.get_tick('600519')
print(f"最新价: {tick['last']}")
```

**要求**: 必须运行miniQMT客户端

---

## 性能相关

### Q13: 如何处理API限流？

**A**: 应对策略：

```python
import time

# 1. 添加请求间隔
codes = ['600519', '000001', '000858']
for code in codes:
    df = master.get_kline(code, count=120)
    time.sleep(0.5)  # 每次请求间隔0.5秒

# 2. 批量请求时降低并发数
max_workers = 3  # 限制并发数为3

# 3. 盘后批量更新（利用缓存）
# 盘后首次请求写入缓存，后续请求命中缓存，不调用API
```

### Q14: 性能如何优化？

**A**:
1. **使用缓存**: 确保 `use_cache=True`（默认）
2. **盘后更新**: 在15:00后批量更新数据
3. **历史数据**: 使用 `end_date < 今天` 充分利用缓存
4. **合理并发**: 控制并发数量（推荐 ≤ 3）

---

## 错误排查

### Q15: 所有数据源均无法获取数据怎么办？

**A**: 解决方案：
1. 检查网络连接
2. 查看日志文件: `logs/data_master.log`
3. 运行健康检查: `master.get_health_status()`
4. 检查Tushare Token是否有效

### Q16: 缓存不生效怎么办？

**A**: 解决方案：
1. 检查 `config.json` 中 `cache.enabled` 是否为 `true`
2. 检查缓存数据库路径是否有写权限
3. 查看缓存统计: `master.get_cache_statistics()`

### Q17: Tushare数据获取失败怎么办？

**A**: 解决方案：
1. 确认token是否有效
2. 检查Tushare账户权限
3. 查看错误日志

---

## 其他问题

### Q18: 双源校验是什么？

**A**: 为确保数据准确性，日K线缓存采用双源校验机制：
1. 主数据源（Tushare）获取数据
2. 校验数据源（Mootdx或Baostock）获取相同数据
3. 对比两份数据，检查价格和成交量差异
4. **只有校验通过的数据才会缓存**

容差标准：
- 价格：±0.01元 或 ±0.5%
- 成交量：±5%

### Q19: 如何手动切换数据源？

**A**:

```python
# 强制切换K线数据源到baostock
master.force_switch_source('kline', 'baostock')

# 验证
status = master.get_health_status()
print(status['active_sources'])
# {'kline': 'baostock', ...}
```

### Q20: 日志文件在哪里？

**A**: 默认位置 `logs/data_master.log`

查看日志：

```bash
# Linux/Mac
tail -f logs/data_master.log

# Windows
type logs\data_master.log
```

---

## 更多帮助

- [快速开始指南](quick-start.md)
- [API 参考手册](api-reference.md)
- [架构设计文档](architecture.md)
- [完整文档](../CLAUDE.md)

---

**Happy Trading! 📈**
