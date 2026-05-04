# API 参考手册

StockDataMaster 完整API文档

---

## 目录

1. [主接口 API](#主接口-api)
2. [数据格式说明](#数据格式说明)
3. [错误处理](#错误处理)

---

## 主接口 API

### get_kline() - 获取K线数据

```python
def get_kline(
    code: str,                          # 股票代码
    freq: str = 'd',                    # 频率
    start_date: Optional[str] = None,   # 开始日期
    end_date: Optional[str] = None,     # 结束日期
    count: Optional[int] = None,        # 获取数量
    adjust: str = 'qfq',                # 复权类型
    use_cache: bool = True              # 是否使用缓存（仅日线有效）
) -> pd.DataFrame
```

**参数说明**：

| 参数 | 类型 | 必填 | 说明 |
|-----|------|------|------|
| code | str | ✅ | 股票代码，如 `'600519'` |
| freq | str | ❌ | 频率：`'d'`（日线），`'5m'`、`'15m'`、`'30m'`、`'60m'`（分钟线） |
| start_date | str | ❌ | 开始日期 `'YYYY-MM-DD'` |
| end_date | str | ❌ | 结束日期 `'YYYY-MM-DD'` |
| count | int | ❌ | 获取数量（从最新往前） |
| adjust | str | ❌ | 复权类型，固定 `'qfq'`（前复权） |
| use_cache | bool | ❌ | 是否使用缓存（仅日线有效） |

**返回值**：

```python
pd.DataFrame  # 列：date, open, high, low, close, volume, amount
# df.attrs['source']  →  'cache' 或数据源名称（'tushare'/'baostock'/...）
```

**使用示例**：

```python
# 获取最近120条日K线
df = master.get_kline('600519', freq='d', count=120)

# 按日期范围获取（历史数据，优先命中缓存）
df = master.get_kline('600519', start_date='2025-01-01', end_date='2025-10-24')

# 获取5分钟K线（不缓存）
df = master.get_kline('600519', freq='5m', count=48)
```

---

### get_valuation() - 获取估值数据

```python
def get_valuation(
    code: str,
    start_date: Optional[str] = None,
    end_date: Optional[str] = None
) -> pd.DataFrame
```

**参数说明**：

| 参数 | 类型 | 必填 | 说明 |
|-----|------|------|------|
| code | str | ✅ | 股票代码 |
| start_date | str | ❌ | 开始日期 `'YYYY-MM-DD'` |
| end_date | str | ❌ | 结束日期 `'YYYY-MM-DD'` |

**返回值**：`pd.DataFrame`，包含 `pe_ttm`、`pb`、`ps_ttm` 等估值指标。

**使用示例**：

```python
df = master.get_valuation('600519', start_date='2025-01-01')
```

---

### get_tick() - 获取实时Tick数据

```python
def get_tick(code: str) -> Dict[str, Any]
```

**依赖**: 需本地运行 miniQMT 客户端（xtquant），否则回退到 Mootdx 模拟行情。

**返回值**：

```python
{
    'code': '600519',
    'name': '贵州茅台',
    'open': 1455.00,
    'high': 1469.50,
    'low': 1454.88,
    'close': 1457.93,
    'last': 1462.26,
    'volume': 2594988.0,
    'amount': 3793284000.0,
    'change': 4.33,
    'change_pct': 0.30,
    'source': 'xtquant'   # 或 'mootdx'
}
```

**使用示例**：

```python
tick = master.get_tick('600519')
print(f"最新价: {tick['last']}, 涨跌幅: {tick['change_pct']}%")
```

---

### get_stock_name() - 获取股票名称

```python
def get_stock_name(code: str) -> str
```

内部走四级查找链：内存缓存（< 0.01ms）→ SQLite → Baostock → xtquant/Tushare。

**返回值**：股票名称字符串，如 `'贵州茅台'`；查找失败时返回空字符串。

**使用示例**：

```python
name = master.get_stock_name('600519')  # 贵州茅台
```

---

### warmup_stock_names() - 预热股票名称缓存

```python
def warmup_stock_names() -> int
```

从 Tushare 批量拉取全市场股票名称写入缓存，适合在应用启动阶段调用，避免后续逐条查询。

**返回值**：成功写入的记录数（int）。

**依赖**: 需配置有效的 Tushare Token。

**使用示例**：

```python
count = master.warmup_stock_names()
print(f"预热了 {count} 只股票的名称")
```

---

### get_health_status() - 获取健康状态

```python
def get_health_status() -> Dict[str, Any]
```

**返回值**：

```python
{
    'timestamp': '2026-04-30 14:30:00',
    'sources': {
        'tushare': {
            'enabled': True,
            'connected': True,
            'status': 'ok',           # 'ok' / 'error' / 'disabled'
            'last_check': '14:29:45',
            'response_time': '0.52s',
            'failure_count': 0
        },
        # baostock, mootdx, xtquant 结构相同
    },
    'active_sources': {
        'kline_day': 'tushare',
        'kline_minute': 'xtquant',
        'valuation': 'tushare',
        'tick': 'xtquant'
    }
}
```

**使用示例**：

```python
status = master.get_health_status()
print("当前活跃数据源:", status['active_sources'])
```

---

### get_cache_statistics() - 获取缓存统计

```python
def get_cache_statistics() -> Dict[str, Any]
```

**返回值**：

```python
{
    'enabled': True,
    'total_records': 12000,
    'validated_records': 12000,
    'stock_count': 25,
    'date_range': {
        'start': '2024-06-01',
        'end': '2026-04-30'
    },
    'db_size_mb': 1.8,
    'db_path': 'cache/kline_cache.db'
}
```

**使用示例**：

```python
stats = master.get_cache_statistics()
print(f"缓存股票数: {stats['stock_count']}, 大小: {stats['db_size_mb']} MB")
```

---

### cleanup_cache() - 清理缓存

```python
def cleanup_cache(days: Optional[int] = None)
```

| 参数 | 类型 | 必填 | 说明 |
|-----|------|------|------|
| days | int | ❌ | 保留最近 N 天数据，默认使用 `config.json` 中 `cache.max_days_per_stock`（默认 520） |

**使用示例**：

```python
# 保留最近 520 天的数据
master.cleanup_cache(days=520)
```

---

### force_switch_source() - 强制切换数据源

```python
def force_switch_source(usage: str, target_source: str) -> bool
```

| 参数 | 类型 | 必填 | 说明 |
|-----|------|------|------|
| usage | str | ✅ | 角色：`'kline_day'`、`'kline_minute'`、`'valuation'`、`'tick'` |
| target_source | str | ✅ | 目标数据源：`'tushare'`、`'mootdx'`、`'baostock'`、`'xtquant'` |

**返回值**：切换是否成功（bool）。

**使用示例**：

```python
# 强制日K线切换到baostock
success = master.force_switch_source('kline_day', 'baostock')
```

---

### close() - 关闭连接

```python
def close()
```

释放所有资源，关闭数据源连接，停止后台健康检测线程。

**使用示例**：

```python
master.close()
```

---

## 数据格式说明

### 股票代码格式

```python
# ✅ 支持
'600519'      # 6位数字
'sh.600519'   # 带市场前缀（内部自动转换）

# ❌ 不支持
'600519.SH'   # 后缀格式
```

### 日期格式

```python
# ✅ 正确
'2025-10-24'  # YYYY-MM-DD

# ❌ 错误
'2025/10/24'
'20251024'
```

### 复权类型

```python
# ✅ 唯一支持
adjust='qfq'  # 前复权

# ❌ 不支持
adjust='hfq'
adjust=None
```

---

## 错误处理

```python
try:
    df = master.get_kline('600519', count=120)
    if df is None or df.empty:
        print("获取数据失败，所有数据源均不可用")
except Exception as e:
    print(f"异常: {e}")
    # 检查健康状态排查原因
    print(master.get_health_status())
```

---

## 完整示例

```python
from StockDataMaster import StockDataMaster

master = StockDataMaster()

try:
    # 日K线（缓存优先）
    df = master.get_kline('600519', count=120)
    print(f"数据来源: {df.attrs.get('source')}")

    # 估值数据
    df_val = master.get_valuation('600519', start_date='2025-01-01')

    # 实时行情（需 QMT 客户端）
    tick = master.get_tick('600519')
    print(f"最新价: {tick['last']}")

    # 股票名称（四级查找链）
    name = master.get_stock_name('600519')

    # 健康状态
    status = master.get_health_status()
    print("活跃数据源:", status['active_sources'])

finally:
    master.close()
```

---

**更多细节**: 参见 [接口调用规范与最佳实践](接口调用规范与最佳实践.md)
