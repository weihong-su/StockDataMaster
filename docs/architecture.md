# 架构设计文档

StockDataMaster 系统架构设计详解

---

## 设计理念

**适配器模式** + **单例模式** + **配置驱动**

通过多数据源集成、智能缓存和健康检测，为量化交易和数据分析提供高可用、高性能的数据服务。

---

## 系统架构

```
用户代码
    ↓
StockDataMaster（单例入口）
    ├─ HealthManager（健康检测与热切换）
    ├─ CacheManager（智能缓存）
    └─ AdapterFactory
        ├─ TushareAdapter（日K线主数据源）
        ├─ MootdxAdapter（分钟K线主数据源）
        ├─ BaostockAdapter（备用数据源）
        └─ XtquantAdapter（实时Tick数据源）
```

---

## 核心设计决策

### 为什么使用适配器模式？

- 每个数据源API差异巨大（Tushare用token，Mootdx用TCP，Baostock需登录）
- 适配器统一接口：`get_kline()`, `get_valuation()`, `get_tick()`
- 易于扩展新数据源（仅需继承 `DataSourceAdapter`）

### 为什么使用单例模式？

- 避免重复连接数据源（TCP连接、登录认证）
- 全局共享缓存和健康状态
- 后台健康检测线程唯一性

### 为什么配置驱动？

- 无需修改代码即可调整数据源优先级、超时、重试
- 运维友好：`config.json` 一键开关数据源
- 测试友好：不同环境使用不同配置

---

## 核心模块

### 1. 主接口模块（data_master.py）

**职责**：
- 单例入口，协调各模块
- 智能缓存判断
- 数据源切换

**核心方法**：
```python
class StockDataMaster:
    def get_kline(...)      # K线数据接口
    def get_valuation(...)  # 估值数据接口
    def get_tick(...)       # 实时Tick接口
    def _is_cache_fresh(...) # 缓存新鲜度判断（核心逻辑）
```

### 2. 适配器基类（base_adapter.py）

**职责**：
- 定义统一接口
- 健康检查
- 代码标准化

**核心方法**：
```python
class DataSourceAdapter:
    def connect() -> bool
    def get_kline(...)
    def get_valuation(...)
    def get_tick(...)
    def health_check() -> Dict[str, Any]
```

### 3. 缓存管理（cache_manager.py）

**职责**：
- SQLite缓存
- 双源校验
- 盘中/盘后策略

**核心功能**：
- 缓存写入：盘中跳过当日，盘后缓存收盘数据
- 缓存读取：三层智能判断
- 数据校验：价格±0.01元，成交量±5%

### 4. 健康管理（health_manager.py）

**职责**：
- 后台检测
- 热切换
- 后台线程

**核心机制**：
- 60秒间隔健康检测
- 连续失败≥3次触发切换
- 响应时间>5秒触发切换

---

## 核心创新

### 1. 智能三层缓存判断

```
用户请求 get_kline(code, start_date, end_date, count)
    ↓
从缓存获取数据
    ↓
调用 _is_cache_fresh(cached_df, end_date)
    ↓
[优先级1] end_date < 今天？
    YES → 返回 True（历史数据永不变）
    NO  → 继续
    ↓
[优先级2] 缓存最新日期 == 今天？
    YES → 当前时间 >= 15:00？
        YES → 返回 True（盘后数据已固定）
        NO  → 返回 False（盘中数据动态变化）
    NO  → 继续
    ↓
[优先级3] 缓存最新日期 == 最新交易日？
    YES → 返回 True（周末/节假日使用最新交易日）
    NO  → 返回 False（缓存过期）
```

**核心价值**：
- 历史数据永不过期（提高缓存命中率）
- 盘中保证实时性（不缓存当日数据）
- 盘后自动缓存（性能和准确性兼顾）

### 2. 盘中/盘后自适应

**缓存写入策略**：

```python
# 盘中时段（< 15:00）跳过当日数据
market_close_time = time(15, 0)
can_cache_today = now.time() >= market_close_time

if row_date == today_str and not can_cache_today:
    continue  # 不缓存盘中当日数据
```

**实际效果**：

| 场景 | 时间 | 请求 | 缓存行为 |
|------|------|------|---------|
| 历史数据分析 | 任意 | end_date='2025-10-24' | ✅ 使用缓存 |
| 盘中监控 | 10:30 | count=120 | ❌ 不缓存当日 |
| 盘后查询 | 15:30 | count=120 | ✅ 缓存当日 |
| 周末查询 | 周六 | count=120 | ✅ 使用缓存 |

### 3. 双源校验机制

**目的**: 确保缓存数据准确性，只缓存校验通过的数据

**流程**:
1. 主数据源（Tushare）获取数据
2. 校验数据源（Mootdx或Baostock）获取相同数据
3. 逐条比对价格和成交量，容差标准：
   - 价格：±0.01元 或 ±0.5%
   - 成交量：±5%
4. 只有通过校验的数据才进入缓存（validated=1）
5. 校验通过率 ≥ 80% 才缓存成功

**代码示例**:

```python
# 执行双源校验
validated_df = self.cache_manager.validate_and_cache(
    code, df_tushare, df_mootdx, 'tushare', 'mootdx'
)

# 计算通过率
pass_rate = len(validated_df) / expected_count
if pass_rate >= 0.8:
    # 缓存成功
    self.logger.info(f"校验通过率: {pass_rate*100:.1f}%")
```

---

## 配置驱动设计

### 核心配置项

```json
{
  "data_sources": {
    "tushare": {
      "enabled": true,
      "priority": 1,
      "timeout": 10,
      "retry_times": 2,
      "token": "your_token",
      "use_for": ["kline_day"]
    }
  },
  "cache": {
    "enabled": true,
    "max_days_per_stock": 120,
    "validation": {
      "price_tolerance_abs": 0.01,
      "price_tolerance_pct": 0.005,
      "volume_tolerance_pct": 0.05
    }
  },
  "health_check": {
    "enabled": true,
    "interval_seconds": 60,
    "response_time_threshold": 5.0,
    "consecutive_failures_threshold": 3
  }
}
```

### 配置读取

```python
# 支持点号分隔的嵌套键
cache_max_days = config.get('cache.max_days_per_stock', 120)

# 按用途获取数据源
sources = config.get_sources_by_usage('kline_day')
# → ['tushare', 'mootdx', 'baostock'] (按优先级排序)
```

---

## 数据流

### K线数据请求流程

```
用户请求 get_kline(code, freq, count)
    ↓
[1] 检查频率是否为日线？
    NO → 直接从数据源获取（分钟线不缓存）
    YES → 继续
    ↓
[2] 检查缓存是否启用？
    NO → 直接从数据源获取
    YES → 继续
    ↓
[3] 从缓存获取数据
    ↓
[4] 检查缓存是否新鲜且充足？
    YES → 返回缓存数据 ✅
    NO  → 继续
    ↓
[5] 从数据源获取数据
    ↓
[6] 双源校验
    ↓
[7] 写入缓存（如果盘后时段）
    ↓
[8] 返回数据
```

---

## 扩展性

### 添加新数据源

1. **创建适配器** (`adapters/newsource_adapter.py`)
2. **注册适配器** (`adapters/__init__.py`)
3. **添加配置** (`config.json`)
4. **编写测试**

详见：[CLAUDE.md - 常见任务](../CLAUDE.md#添加新数据源)

---

## 性能优化

### 缓存预取

**问题**: 用户请求120条，缓存也是120条，后续请求121条会miss缓存

**解决方案**: 实际请求时多获取10%数据

```python
# 用户请求120条，实际获取132条
actual_count = int(count * 1.1)  # +10%

df = adapter.get_kline(code, freq, start_date, end_date, actual_count, adjust)

# 返回用户需要的120条
return_df = df.tail(count).copy()

# 完整数据（132条）保存在attrs中供缓存使用
return_df.attrs['full_data'] = df
```

**效果**: 提高后续请求缓存命中率

---

## 更多细节

- [完整架构文档](../CLAUDE.md#架构总览)
- [核心架构模式](../CLAUDE.md#核心架构模式)

---

**Happy Trading! 📈**
