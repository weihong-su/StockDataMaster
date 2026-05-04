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
    ├─ CacheManager（智能缓存 + 双源校验）
    └─ AdapterFactory
        ├─ TushareAdapter   —— 日K线主数据源
        ├─ BaostockAdapter  —— 校验首选 / 股票名称 / 备用K线
        ├─ MootdxAdapter    —— 应急备用（TCP，速度快）
        └─ XtquantAdapter   —— 实时Tick + 分钟K线首选（需QMT）
```

---

## 核心设计决策

### 为什么使用适配器模式？

- 每个数据源 API 差异巨大（Tushare 用 token，Mootdx 用 TCP，Baostock 需登录）
- 适配器统一接口：`get_kline()`、`get_valuation()`、`get_tick()`
- 易于扩展新数据源（仅需继承 `DataSourceAdapter`）

### 为什么使用单例模式？

- 避免重复连接数据源（TCP 连接、登录认证）
- 全局共享缓存和健康状态
- 后台健康检测线程唯一性

### 为什么配置驱动？

- 无需修改代码即可调整数据源优先级、超时、重试
- 运维友好：`config.json` 一键开关数据源
- 测试友好：不同环境使用不同配置

---

## 核心模块

### 1. 主接口模块（data_master.py）

**职责**：单例入口，协调各模块，智能缓存判断，数据源切换。

**公开方法**：

| 方法 | 说明 |
|------|------|
| `get_kline()` | K线数据（日线 + 分钟线） |
| `get_valuation()` | 估值数据（PE/PB 等） |
| `get_tick()` | 实时 Tick |
| `get_stock_name()` | 股票名称（四级查找链） |
| `warmup_stock_names()` | 批量预热股票名称缓存 |
| `get_health_status()` | 系统健康报告 |
| `get_cache_statistics()` | 缓存统计 |
| `cleanup_cache()` | 清理旧缓存 |
| `force_switch_source()` | 强制切换指定角色的数据源 |
| `close()` | 释放所有资源 |

### 2. 适配器基类（base_adapter.py）

**职责**：定义统一接口，健康检查，代码标准化。

```python
class DataSourceAdapter:
    def connect() -> bool
    def disconnect()
    def get_kline(...) -> DataFrame
    def get_valuation(...) -> DataFrame
    def get_tick(...) -> Dict
    def health_check() -> Dict
    def normalize_code(code) -> str    # 去除前缀 → '600519'
    def add_prefix(code) -> str        # 添加前缀 → 'sh.600519'
    def standardize_dataframe(df)      # 标准化列名
```

### 3. 缓存管理（cache_manager.py）

**职责**：SQLite 缓存，双源校验，增量写入，股票名称持久化。

**核心参数**（来自 `config.json`）：

| 参数 | 默认值 | 说明 |
|------|--------|------|
| `cache.max_days_per_stock` | 520 | 单只股票最大缓存天数 |
| `cache.validation.price_tolerance_abs` | 0.01 | 价格绝对容差（元） |
| `cache.validation.price_tolerance_pct` | 0.005 | 价格相对容差（0.5%） |
| `cache.validation.volume_tolerance_pct` | 0.05 | 成交量容差（5%） |
| `cache.validation.min_pass_rate` | 0.8 | 最低通过率（80%） |

### 4. 健康管理（health_manager.py）

**职责**：后台检测，热切换，时段感知恢复。

| 参数 | 默认值 | 说明 |
|------|--------|------|
| `health_check.interval_seconds` | 60 | 检查间隔 |
| `health_check.response_time_threshold` | 5.0 | 响应超时阈值（秒） |
| `health_check.consecutive_failures_threshold` | 3 | 触发切换的连续失败次数 |

---

## 核心创新

### 1. 智能三层缓存判断（_is_cache_fresh）

```
用户请求 get_kline(code, end_date, count)
    ↓
[1] end_date < 今天？
    YES → 返回 True（历史数据永不变）
    ↓
[2] 缓存最新日期 == 今天？
    盘中（< 15:00）→ 返回 False（重新获取）
    盘后（≥ 15:00）→ 返回 True（收盘已固定）
    ↓
[3] 缓存最新日期 == 最新交易日？
    YES → 返回 True（周末/节假日使用最新交易日缓存）
    NO  → 返回 False（缓存过期）
```

### 2. 串行短路校验

双源校验按响应速度排序，第一个通过即短路，避免等待慢速数据源：

```
需要校验新数据 D 条
    ↓
[1] xtquant（~50ms，仅交易时段）
    通过 → 立即缓存，结束校验
    ↓
[2] baostock（~2-3s，全时段兜底）
    通过 → 缓存
    失败 → 不缓存（数据可疑）
```

**关键配置**（`config.json` `validation` 节）：

```json
{
  "validation": {
    "sources": ["xtquant", "baostock"],
    "strategy": "fast_first",
    "comment": "串行短路: xtquant(快)优先, 通过即短路"
  }
}
```

### 3. roles 配置格式

每个数据源通过 `roles` 字段声明承担的角色及优先级，支持 `time_slot` 过滤：

```json
{
  "data_sources": {
    "baostock": {
      "roles": {
        "kline_day":   { "priority": 2 },
        "validation":  { "priority": 1 },
        "stock_name":  { "priority": 1 }
      }
    },
    "xtquant": {
      "roles": {
        "tick":         { "priority": 1 },
        "kline_minute": { "priority": 1 },
        "validation":   { "priority": 2, "time_slot": "trading" }
      }
    }
  }
}
```

`time_slot` 可选值：`"trading"`（9:15-15:00）、`"after_hours"`（其他），不指定则全时段生效。

### 4. 股票名称四级查找链

```python
get_stock_name('600519')
    L1: 内存 dict         (< 0.01ms, 不持久)
    L2: SQLite 缓存       (~0.5ms,  持久化，30天过期)
    L3: Baostock 查询     (~0.8ms,  含退市股，免费)
    L4: xtquant / Tushare (~50ms+, 付费用户补充)
```

L1 相比 L3 加速约 **700 倍**，SQLite 持久化几乎无性能损失。

### 5. 盘中/盘后自适应写入

```python
# 盘中（< 15:00）跳过当日数据，避免缓存不完整的盘中 K 线
if row_date == today and now.time() < market_close_time:
    continue  # 不缓存

# 盘后（≥ 15:00）正常写入，收盘价已固定
```

---

## 配置驱动设计

### 最小配置示例

```json
{
  "data_sources": {
    "tushare": {
      "enabled": true,
      "token": "your_token",
      "roles": {
        "kline_day": { "priority": 1 },
        "valuation":  { "priority": 1 }
      }
    },
    "baostock": {
      "enabled": true,
      "roles": {
        "kline_day":  { "priority": 2 },
        "validation": { "priority": 1 },
        "stock_name": { "priority": 1 }
      }
    }
  },
  "cache": {
    "enabled": true,
    "max_days_per_stock": 520
  },
  "health_check": {
    "enabled": true,
    "interval_seconds": 60
  }
}
```

### 配置读取

```python
# 支持点号分隔的嵌套键，第二参数为默认值
cache_max = config.get('cache.max_days_per_stock', 520)

# 按角色获取数据源（已按 priority 排序）
sources = config.get_sources_by_role('kline_day')
# → ['tushare', 'baostock', 'mootdx', 'xtquant']
```

---

## 数据流

### K线数据请求流程（日线）

```
用户请求 get_kline(code, freq='d', count)
    ↓
[1] 缓存启用 且 use_cache=True？
    NO → 直接从数据源获取
    ↓
[2] 缓存是否新鲜且覆盖请求范围？
    YES → 返回缓存数据 ✅
    ↓
[3] 按 kline_day roles 优先级逐源请求
    tushare(P1) → baostock(P2) → mootdx(P3)
    ↓
[4] 串行短路校验（xtquant/baostock）
    ↓
[5] 盘后时段 → 写入缓存（增量，跳过今日盘中）
    ↓
[6] 返回数据
```

---

## 扩展性

### 添加新数据源

1. 创建 `adapters/newsource_adapter.py`，继承 `DataSourceAdapter`
2. 实现：`connect()`、`disconnect()`、`get_kline()`、`get_valuation()`、`get_tick()`
3. 注册到 `adapters/__init__.py` 的 `AdapterFactory.ADAPTER_MAP`
4. 在 `config.json` 的 `data_sources` 下添加配置，设置 `roles`

K线返回格式：列 `date, open, high, low, close, volume, amount`；date 为 `'YYYY-MM-DD'` 字符串；所有价格前复权。

---

## 性能指标

| 指标 | 数值 |
|------|------|
| 热缓存响应时间 | ~3ms |
| 冷启动响应时间 | ~120ms |
| 缓存加速比 | 40x+ |
| L1 股票名称查询 | < 0.01ms |
| 并发 QPS（10线程） | 300+ |
| 缓存容量/股票 | 520 天 |

详细测试数据参见：[性能深度分析报告](StockDataMaster性能深度分析报告.md)
