# 数据源优先级优化设计

## 1. 背景与目标

优化 StockDataMaster 的四大数据源（Tushare、Xtquant、Mootdx、Baostock）的优先级策略，实现：
- 交易时段 xtquant 实时 tick 优先
- 分钟线 xtquant 优先
- 日线 tushare 主数据 + 三选二投票校验
- 动态 fallback 机制
- `get_stock_name` 接口

## 2. 时段定义

| 时段键 | 时间范围 | 说明 |
|--------|---------|------|
| `trading` | 09:15-15:00 (工作日) | 交易时段，xtquant 可用 |
| `after_hours` | 其他时间 | 盘后及非交易日 |

## 3. 数据源角色矩阵

### 3.1 tick（实时逐笔）

| 优先级 | 数据源 |
|--------|--------|
| 1 | xtquant |

xtquant 是唯一的实时 tick 数据源，无其他备选。

### 3.2 kline_minute（分钟K线）

| 时段 | 主源 | 备选1 | 备选2 |
|------|------|-------|-------|
| trading | xtquant | mootdx | baostock |
| after_hours | xtquant | mootdx | baostock |

盘中 xtquant 数据最实时，盘后 xtquant 仍可作为主源（提供历史分钟线）。

### 3.3 kline_day（日线数据获取）

| 时段 | 主源 | 备选1 | 备选2 |
|------|------|-------|-------|
| trading | tushare | mootdx | baostock |
| after_hours | tushare | mootdx | baostock |

日线以 Tushare Pro 为主源，保证数据完整性。

### 3.4 validation（日线投票校验源）

| 时段 | 校验源1 | 校验源2 | 校验源3 |
|------|---------|---------|---------|
| trading | xtquant | baostock | mootdx |
| after_hours | baostock | mootdx | - |

交易时段 xtquant 参与校验（盘中数据最新），盘后 xtquant 可能不可用则仅用 baostock + mootdx。

## 4. 三选二投票校验机制

### 4.1 流程

```
请求日线数据
    ├─ 从 tushare 获取主数据 DataFrame
    ├─ 并行向 [xtquant, baostock, mootdx] 发起校验请求
    │     （不串行等待，三个同时请求）
    ├─ 收集到第一个校验源结果时开始与 tushare 比对
    │     ├─ 与 tushare 一致 → 记录"一票通过"
    │     ├─ 再收到一个一致 → 达成"二票" → 直接缓存，终止剩余请求
    │     └─ 两个都失败 → 数据不缓存，进入 fallback
    └─ 若遍历完所有源仍不够二票 → 数据丢弃（不污染缓存）
```

### 4.2 一致性判断标准

- **价格**：|差值| ≤ 0.01 且 |差值%| ≤ 0.5%
- **成交量**：|差值%| ≤ 5%
- **通过率**：至少 80% 的日期记录满足上述条件

### 4.3 盘中特殊处理

交易时段（09:15-15:00）当日数据**不写入缓存**：
- 当日K线可能还在变化，校验结果不稳定
- 只在 15:00 之后才将当日数据写入缓存
- 盘中获取当日数据：直接返回源数据，不触发缓存

## 5. 动态 Fallback 机制

### 5.1 连续失败降级

```
Xtquant 连续失败 N 次（可配置，默认3次）
    → 从当前可用校验源中暂时移除 xtquant
    → 若只剩 [baostock, mootdx] 两个源
          └─ 仍需二选二（而非二选一）
    → HealthManager 检测到 xtquant 恢复后
          └─ 自动将其加回可用源列表
```

### 5.2 HealthManager 联动

- 背景线程每 60 秒检测各数据源连通性
- `available_sources` 集合实时更新
- 数据获取层读取实时的 `available_sources` 而非固定列表

### 5.3 主数据源 Fallback

当 tushare 主数据获取失败时：
1. 尝试 mootdx（日线备选）
2. 尝试 baostock（日线备选）
3. 所有源均失败 → 返回 None

## 6. get_stock_name 接口

### 6.1 三级查找链

```
get_stock_name("600519")
    │
    ├─ L1: 内存缓存 dict
    │         命中 → 直接返回
    │         miss ↓
    │
    ├─ L2: xtquant.get_instrument_detail("600519.SH")
    │         提取 InstrumentName / instrumentName / name 字段
    │         成功 → 缓存 L1+L2 → 返回
    │         失败或不可用 ↓
    │
    └─ L3: baostock.query_stock_basic(code="sh.600519")
              提取股票名称
              成功 → 缓存 L1+L2+L3 → 返回
              失败 → 返回 stock_code 本身
```

### 6.2 代码格式转换

```python
def _to_xtquant_code(code: str) -> str:
    """转换为 xtquant 格式: 600519 → 600519.SH"""
    if code.startswith(('6', '510', '511', '518')):
        return f"{code}.SH"
    return f"{code}.SZ"

def _to_baostock_code(code: str) -> str:
    """转换为 baostock 格式: 600519 → sh.600519"""
    if code.startswith(('6', '510', '511', '518')):
        return f"sh.{code}"
    return f"sz.{code}"
```

### 6.3 冷却机制

baostock 连续失败 3 次后进入 300 秒冷却期，冷却期间跳过 L3 直接返回代码本身。成功一次即重置计数。

### 6.4 股票代码格式支持

支持以下所有格式：
- `'600519'` （6位纯数字）
- `'sh.600519'` （前缀格式）
- `'600519.SH'` （xtquant格式）

## 7. config.json 配置变更

### 7.1 新增字段

```json
{
  "data_sources": {
    "tushare": {
      "enabled": true,
      "roles": {
        "kline_day": { "priority": 1 },
        "valuation": { "priority": 1 }
      }
    },
    "xtquant": {
      "enabled": true,
      "roles": {
        "tick": { "priority": 1 },
        "kline_minute": { "priority": 1 },
        "validation": { "priority": 1, "time_slot": "trading" }
      }
    },
    "mootdx": {
      "enabled": true,
      "roles": {
        "kline_minute": { "priority": 2 },
        "kline_day": { "priority": 2 },
        "validation": { "priority": 3 }
      }
    },
    "baostock": {
      "enabled": true,
      "roles": {
        "kline_day": { "priority": 3 },
        "kline_minute": { "priority": 3 },
        "validation": { "priority": 2 }
      }
    }
  },
  "validation": {
    "mode": "voting",
    "quorum": 2,
    "strategy": "first_to_quorum",
    "sources": ["xtquant", "baostock", "mootdx"],
    "price_tolerance_abs": 0.01,
    "price_tolerance_pct": 0.005,
    "volume_tolerance_pct": 0.05,
    "min_pass_rate": 0.8,
    "skip_today_in_trading_hours": true
  },
  "stock_name": {
    "cache_enabled": true,
    "cleanup_day": "Monday",
    "baostock_max_consecutive_failures": 3,
    "baostock_retry_cooldown": 300
  }
}
```

### 7.2 兼容旧配置

启动时检测 `data_sources` 结构：
- 若为旧格式（`priority` + `use_for`），自动迁移为新格式
- 新旧格式并存时，以新格式为准

## 8. 关键文件变更

| 文件 | 变更内容 |
|------|---------|
| `config.json` | 新增时段角色矩阵、validation 配置、stock_name 配置 |
| `data_master.py` | 新增 `_get_time_slot()` 方法；`_fetch_kline_from_source()` 支持角色矩阵查表；新增 `get_stock_name()` 公共接口 |
| `cache_manager.py` | 重构 `_validate_data()` 为三选二投票；新增 `get_stock_name()` 实现 |
| `adapters/base_adapter.py` | 新增 `roles` 属性，适配器声明自己支持的用途和优先级 |
| `health/health_manager.py` | 与动态可用源列表联动；支持 xtquant 时段感知 |

## 9. 风险与约束

1. **Tushare Pro Token**：日线主数据依赖 Tushare Pro 接口，需要有效的 pro 账号
2. **Xtquant 可用性**：盘中 xtquant 必须保持连接，断开后 HealthManager 自动重连
3. **性能权衡**：三选二并行请求会增加网络开销，但 first_to_quorum 策略保证不会无限等待
4. **盘中数据一致性**：交易时段当日数据不缓存，但盘中获取当日数据时仍需返回源数据
