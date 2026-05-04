# 常见问题 FAQ

StockDataMaster 常见问题解答

---

## 安装与配置

### Q1: 如何安装依赖？

```bash
# 核心依赖
pip install pandas numpy mootdx baostock tushare

# xtquant（可选，需要 QMT 客户端）
# 下载 miniQMT：https://dict.thinktrader.net/
# 安装并运行后，StockDataMaster 会自动连接
```

### Q2: Tushare Token 如何配置？

在 `config.json` 中配置：

```json
{
  "data_sources": {
    "tushare": {
      "enabled": true,
      "token": "你的 Tushare Token"
    }
  }
}
```

获取 Token：访问 https://tushare.pro/ 注册并获取。

### Q3: xtquant 如何配置？

1. 下载并安装 miniQMT 客户端
2. 运行 miniQMT
3. StockDataMaster 会自动连接

如果 QMT 未运行，xtquant 会自动禁用，不影响其他数据源。

---

## 缓存相关

### Q4: 盘中请求数据为什么不使用缓存？

盘中时段（9:15-15:00），当日 K 线数据动态变化。为保证实时性，系统跳过当日数据的缓存写入，每次从数据源获取最新值。盘后（≥ 15:00）收盘价固定，才会正常缓存。

### Q5: 如何判断返回的数据是否来自缓存？

```python
df = master.get_kline('600519', count=120)
source = df.attrs.get('source', 'unknown')

if source == 'cache':
    print("数据来自缓存")
else:
    print(f"数据来自数据源: {source}")
```

### Q6: 为什么分钟线不缓存？

1. 数据量大（48条/天 × 多股票），缓存成本高
2. 主要用于盘中实时分析，时效性要求高
3. Mootdx 单次最多 800 条，不适合长期存储

### Q7: 如何提高缓存命中率？

```python
# ✅ 最优：请求历史数据（end_date < 今天，永命中缓存）
df = master.get_kline('600519', start_date='2025-10-01', end_date='2025-10-24')

# ✅ 好：盘后请求最新数据（缓存已写入收盘价）
df = master.get_kline('600519', count=120)  # 15:00 后

# ⚠️ 一般：盘中请求最新数据（缓存跳过当日）
df = master.get_kline('600519', count=120)  # 14:00

# ❌ 差：主动禁用缓存
df = master.get_kline('600519', count=120, use_cache=False)
```

### Q8: 单只股票最多缓存多少天？

默认 **520 天**，可在 `config.json` 中调整：

```json
{
  "cache": {
    "max_days_per_stock": 520
  }
}
```

超过阈值的旧数据在下次清理时自动删除。

### Q9: 如何清理缓存？

```python
# 保留最近 520 天的数据
master.cleanup_cache(days=520)

# 或手动删除数据库（下次启动自动重建）
import os
os.remove('cache/kline_cache.db')
```

---

## 数据获取

### Q10: 周末请求数据返回什么？

返回最后一个交易日（通常是上周五）的缓存数据，不会触发数据源请求。

```python
# 周六请求
df = master.get_kline('600519', count=120)
print(df['date'].iloc[-1])  # 2026-04-25（周五）
```

### Q11: 如何获取分钟K线？

```python
# 5分钟线（推荐 48 条，约 1 个交易日）
df = master.get_kline('600519', freq='5m', count=48)

# 15分钟线
df = master.get_kline('600519', freq='15m', count=80)
```

注意：Mootdx 分钟线最多 800 条，超出会失败。

### Q12: 实时 Tick 数据如何获取？

```python
# 需要 QMT 客户端运行
tick = master.get_tick('600519')
print(f"最新价: {tick['last']}, 涨跌幅: {tick['change_pct']}%")
```

未运行 QMT 时，自动回退到 Mootdx 模拟行情（非真实 Tick）。

### Q13: 如何批量预热股票名称缓存？

```python
# 应用启动时调用，从 Tushare 批量写入全市场股票名称
count = master.warmup_stock_names()
print(f"预热了 {count} 只股票")
```

需配置有效的 Tushare Token。预热后 `get_stock_name()` 直接命中内存/SQLite，无需外部请求。

---

## 性能相关

### Q14: 如何处理 API 限流？

```python
import time

# 批量请求时加间隔（Tushare 默认限 500 次/分钟）
codes = ['600519', '000001', '000858']
for code in codes:
    df = master.get_kline(code, count=120)
    time.sleep(0.5)

# 或控制并发数（推荐 ≤ 3 线程）
from concurrent.futures import ThreadPoolExecutor
with ThreadPoolExecutor(max_workers=3) as executor:
    ...
```

### Q15: 性能如何优化？

1. 确保 `use_cache=True`（默认开启）
2. 盘后批量更新，写入缓存后续命中
3. 历史数据请求使用 `end_date < 今天` 格式，100% 命中缓存
4. 应用启动时调用 `warmup_stock_names()` 预热名称缓存

---

## 错误排查

### Q16: 所有数据源均无法获取数据怎么办？

1. 检查网络连接
2. 查看日志：`logs/data_master.log`
3. 运行健康检查：`master.get_health_status()`
4. 检查 Tushare Token 是否有效
5. Baostock 连接问题：确认已升级到 0.9.1（`pip install baostock --upgrade`）

### Q17: 缓存不生效怎么办？

1. 确认 `config.json` 中 `cache.enabled` 为 `true`
2. 确认缓存数据库路径有写权限
3. 查看统计：`master.get_cache_statistics()`
4. 检查是否在盘中时段（盘中不缓存当日数据，属于正常行为）

### Q18: xtquant 连接失败怎么办？

1. 确认 miniQMT 客户端已运行
2. 检查 `connect()` 返回值：应为 `None` 表示失败（不是 0），`StockDataMaster` 内部已处理此判断
3. xtquant 失败不影响其他数据源，系统自动降级到 Baostock/Mootdx

---

## 其他问题

### Q19: 双源校验是什么？

日K线缓存采用双源校验确保数据准确：

1. 主数据源（Tushare）获取数据
2. 校验源（Baostock 全时段 / xtquant 交易时段）验证
3. **串行短路**：xtquant 先校验（~50ms），通过即短路；失败再用 baostock（~2-3s）
4. 只有通过校验的数据才写入缓存（`validated=1`）

容差标准：价格 ±0.01元 或 ±0.5%；成交量 ±5%；最低通过率 80%。

### Q20: 如何手动切换数据源？

```python
# 强制日K线切换到 baostock
master.force_switch_source('kline_day', 'baostock')

# 验证
status = master.get_health_status()
print(status['active_sources'])
# {'kline_day': 'baostock', 'kline_minute': 'xtquant', ...}
```

### Q21: 日志文件在哪里？

默认位置：`logs/data_master.log`

```bash
# Windows
type logs\data_master.log

# Linux/Mac
tail -f logs/data_master.log
```

---

## 更多帮助

- [快速开始指南](quick-start.md)
- [API 参考手册](api-reference.md)
- [架构设计文档](architecture.md)
