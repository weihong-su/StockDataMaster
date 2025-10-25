# CLAUDE.md - StockDataMaster 项目文档

> 本文档为 Claude AI 辅助开发 StockDataMaster 项目提供全面的架构、开发和运维指南。
> 最后更新: 2025-10-25

---

## 变更记录 (Changelog)

### 2025-10-25
- ✨ 完成智能日K线缓存优化（盘中/盘后策略）
- ✨ 历史数据缓存优化（end_date < 今天直接使用缓存）
- 📝 重写 CLAUDE.md 为全面的架构文档
- 🧪 新增交互式测试GUI（interactive_test_gui.py）

### 2025-10-20
- 🎉 v1.0.0 初始版本发布
- 🔌 实现多数据源适配器架构
- 💾 实现智能缓存系统
- 🏥 实现健康检测和热切换

---

## 项目愿景

StockDataMaster 是一个**专业的股票数据主数据接口系统**，通过多数据源集成、智能缓存、健康检测和热切换功能，为量化交易和数据分析提供高可用、高性能的数据服务。

**核心价值**：
- 📊 **统一接口**：屏蔽多个数据源差异，提供一致的前复权数据
- ⚡ **智能缓存**：盘中/盘后自适应缓存策略，提升20-100倍性能
- 🔄 **自动切换**：数据源故障自动热切换，保证服务可用性
- 🎯 **双源校验**：缓存前校验数据准确性，确保数据质量

---

## 架构总览

### 设计理念

**适配器模式** + **单例模式** + **配置驱动**

```
用户代码
    ↓
StockDataMaster (单例入口)
    ├─ HealthManager (健康检测与热切换)
    ├─ CacheManager (智能缓存)
    └─ AdapterFactory
        ├─ TushareAdapter (日K线主数据源)
        ├─ MootdxAdapter (分钟K线主数据源)
        ├─ BaostockAdapter (备用数据源)
        └─ XtquantAdapter (实时Tick数据源)
```

### 核心设计决策

1. **为什么使用适配器模式？**
   - 每个数据源API差异巨大（Tushare用token，Mootdx用TCP，Baostock需登录）
   - 适配器统一接口：`get_kline()`, `get_valuation()`, `get_tick()`
   - 易于扩展新数据源（仅需继承 `DataSourceAdapter`）

2. **为什么使用单例模式？**
   - 避免重复连接数据源（TCP连接、登录认证）
   - 全局共享缓存和健康状态
   - 后台健康检测线程唯一性

3. **为什么配置驱动？**
   - 无需修改代码即可调整数据源优先级、超时、重试
   - 运维友好：`config.json` 一键开关数据源
   - 测试友好：不同环境使用不同配置

---

## 模块索引

### 核心模块

| 模块 | 路径 | 职责 | 关键点 |
|------|------|------|--------|
| **主接口** | [data_master.py](data_master.py) | 单例入口，协调各模块 | 智能缓存判断、数据源切换 |
| **配置管理** | [config.py](config.py) | 加载和管理配置 | 支持嵌套配置键 |
| **适配器基类** | [adapters/base_adapter.py](adapters/base_adapter.py) | 定义统一接口 | 健康检查、代码标准化 |
| **缓存管理** | [cache/cache_manager.py](cache/cache_manager.py) | SQLite缓存 | 双源校验、盘中/盘后策略 |
| **健康管理** | [health/health_manager.py](health/health_manager.py) | 后台检测、热切换 | 后台线程、失败阈值 |

### 适配器模块

| 适配器 | 路径 | 用途 | 数据源特点 |
|--------|------|------|-----------|
| **Tushare** | [adapters/tushare_adapter.py](adapters/tushare_adapter.py) | 日K线主数据源 | 需token，复权准确 |
| **Mootdx** | [adapters/mootdx_adapter.py](adapters/mootdx_adapter.py) | 分钟K线主数据源 | 通达信协议，速度快，分钟线复权有BUG |
| **Baostock** | [adapters/baostock_adapter.py](adapters/baostock_adapter.py) | 日K线/估值备用源 | 免费稳定，速度慢 |
| **xtquant** | [adapters/xtquant_adapter.py](adapters/xtquant_adapter.py) | 实时Tick数据源 | 需QMT客户端 |

### 测试与工具

| 目录/文件 | 用途 |
|----------|------|
| [test/](test/) | 所有测试脚本 |
| [test/interactive_test_gui.py](test/interactive_test_gui.py) | **推荐**：交互式图形化测试工具 |
| [test/run_gui_test.bat](test/run_gui_test.bat) | 一键启动测试GUI |
| [docs/](docs/) | 详细的技术文档和测试报告 |
| [lib/](lib/) | 内置依赖库（可选，支持独立部署） |

---

## 运行与开发

### 环境设置

**Python 环境**: Anaconda Python 3.8（推荐）

```bash
# 激活环境
conda activate python38

# 安装核心依赖
pip install pandas numpy

# 安装数据源库（如果不使用内置库）
pip install mootdx baostock tushare
```

**重要配置**:
1. 编辑 `config.json` 配置 Tushare Token
2. 如使用内置库，设置 `"use_builtin_libs": true`
3. 确保 `cache/` 和 `logs/` 目录有写权限

### 快速开始

**推荐：使用交互式测试GUI**

```bash
cd test
python interactive_test_gui.py

# 或使用批处理脚本（Windows）
test\run_gui_test.bat
```

**基本API使用**:

```python
from StockDataMaster import StockDataMaster

# 初始化（单例）
master = StockDataMaster()

# 获取日K线（自动缓存）
df = master.get_kline('600519', freq='d', count=120)
print(f"数据来源: {df.attrs.get('source')}")  # 'cache' 或 'tushare'

# 获取分钟K线（不缓存）
df_5m = master.get_kline('600519', freq='5m', count=48)

# 获取实时行情
tick = master.get_tick('600519')
print(f"最新价: {tick['last']}, 来源: {tick['source']}")

# 健康状态检查
status = master.get_health_status()
print(status)

# 缓存统计
stats = master.get_cache_statistics()
print(f"缓存股票数: {stats['stock_count']}, 记录数: {stats['total_records']}")

# 关闭释放资源
master.close()
```

### 测试命令

**功能测试**:

```bash
# 交互式GUI测试（推荐）
cd test
python interactive_test_gui.py

# 缓存机制测试
python test_intraday_cache.py      # 完整场景测试
python test_cache_simple.py        # 简单验证测试
python test_historical_cache.py    # 历史数据缓存测试
```

**导入路径说明**:
- 项目使用相对导入（`from .config import ...`）
- 测试脚本必须将 StockDataMaster 的**父目录**添加到 `sys.path`
- 然后使用 `from StockDataMaster import StockDataMaster` 导入

测试脚本标准路径设置:
```python
test_dir = os.path.dirname(os.path.abspath(__file__))
project_root = os.path.dirname(test_dir)
parent_dir = os.path.dirname(project_root)
sys.path.insert(0, parent_dir)  # 添加父目录以支持包导入
```

---

## 核心架构模式

### 1. 智能缓存机制（核心创新）

#### 设计思想

日K线数据有两种性质：
- **历史数据**：永远不变，应该缓存
- **当日数据**：盘中动态变化，盘后固定

传统缓存无法区分，导致盘中缓存过期数据或盘后重复请求。

#### 解决方案：三层智能判断

**[代码位置: data_master.py:398-466]**

```python
def _is_cache_fresh(self, df: pd.DataFrame, request_end_date: Optional[str] = None) -> bool:
    """
    核心逻辑：
    1. 🔥 如果用户请求历史时间段（end_date < 今天）→ 新鲜（历史数据不变）
    2. 如果缓存最新日期是今天且盘中时段 → 不新鲜（当日数据动态变化）
    3. 如果缓存最新日期是今天且盘后时段 → 新鲜（当日数据已固定）
    4. 在非交易日时，如果缓存最新日期是上个交易日 → 新鲜
    """
```

**判断流程**:

```
用户请求 get_kline(code, start_date, end_date, count)
    ↓
从缓存获取数据
    ↓
调用 _is_cache_fresh(cached_df, end_date)
    ↓
[优先级1] end_date < 今天？
    YES → 返回 True（历史数据永不变）✅
    NO  → 继续
    ↓
[优先级2] 缓存最新日期 == 今天？
    YES → 当前时间 >= 15:00？
        YES → 返回 True（盘后数据已固定）✅
        NO  → 返回 False（盘中数据动态变化）❌
    NO  → 继续
    ↓
[优先级3] 缓存最新日期 == 最新交易日？
    YES → 返回 True（周末/节假日使用最新交易日）✅
    NO  → 返回 False（缓存过期）❌
```

**缓存写入策略**:

**[代码位置: cache_manager.py:186-200]**

```python
# 盘中时段（< 15:00）跳过当日数据
market_close_time = time(15, 0)
can_cache_today = now.time() >= market_close_time

if row_date == today_str and not can_cache_today:
    continue  # 不缓存盘中当日数据
```

**实际效果**:

| 场景 | 时间 | 请求 | 缓存行为 | 数据来源 |
|------|------|------|---------|---------|
| 历史数据分析 | 任意 | `end_date='2025-10-24'` | ✅ 使用缓存 | cache |
| 盘中监控 | 10:30 | `count=120` | ❌ 不缓存当日 | tushare（实时） |
| 盘后查询 | 15:30 | `count=120` | ✅ 缓存当日 | cache（首次tushare） |
| 周末查询 | 周六 | `count=120` | ✅ 使用缓存 | cache（上周五数据） |

#### 双源校验机制

**目的**: 确保缓存数据准确性，只缓存校验通过的数据

**[代码位置: cache_manager.py:238-369]**

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

**为什么需要双源校验？**
- Tushare 偶尔有异常数据（停牌复牌首日复权错误）
- Mootdx 分钟线复权有BUG（但日线准确）
- 双源比对可发现数据异常，避免缓存错误数据

### 2. 健康检测与热切换

#### 后台健康检测

**[代码位置: health/health_manager.py:54-80]**

**后台线程机制**:
```python
def start_monitoring(self):
    """启动健康监控线程（daemon线程）"""
    self.monitor_thread = threading.Thread(target=self._monitor_loop, daemon=True)
    self.monitor_thread.start()

def _monitor_loop(self):
    """每分钟检测所有数据源"""
    while self.is_running:
        self.check_all_sources()
        time.sleep(self.check_interval)  # 默认60秒
```

**健康检测逻辑**:

**[代码位置: adapters/base_adapter.py:109-187]**

```python
def health_check(self) -> Dict[str, Any]:
    """
    关键修复点：
    - 每次health_check前强制重新连接（后台线程可能已断开）
    - 测试股票改用600000（浦发银行，比茅台稳定）
    - 测试数量改用30条（避免count=1被过滤）
    """
    # 强制重连
    if not self.is_connected:
        self.connect()

    # 获取测试数据
    test_df = self.get_kline('600000', freq='d', count=30)

    # 检查响应时间、数据新鲜度
    if response_time > threshold:
        result['status'] = 'warning'
```

#### 自动故障切换

**触发条件**:
- 连续失败次数 ≥ 3次（可配置）
- 响应时间 > 5秒（可配置）

**切换流程**:

```
健康检测失败 → 失败计数+1 → 达到阈值？
    YES → 查找备用数据源（按优先级）→ 切换活跃数据源 → 记录切换历史
    NO  → 继续监控
```

**代码示例**:

```python
# 自动切换
if self.failure_counts[name] >= self.failure_threshold:
    self._trigger_switch(name, reason)

# 手动强制切换
master.force_switch_source('kline', 'baostock')
```

**为什么需要健康检测？**
- Tushare 有时限流（200次/分钟）
- Mootdx 网络不稳定
- xtquant 依赖QMT客户端运行状态

### 3. 配置驱动设计

**[代码位置: config.json]**

**核心配置项**:

```json
{
  "use_builtin_libs": true,  // 使用内置库（独立部署）
  "data_sources": {
    "tushare": {
      "enabled": true,
      "priority": 1,           // 优先级（数字越小越优先）
      "timeout": 10,
      "retry_times": 2,
      "token": "your_token",
      "use_for": ["kline_day"] // 用途：kline_day, kline_minute, valuation, tick
    }
  },
  "cache": {
    "enabled": true,
    "max_days_per_stock": 120, // 单只股票最多缓存120条
    "validation": {
      "price_tolerance_abs": 0.01,  // 价格容差±0.01元
      "price_tolerance_pct": 0.005, // 价格容差±0.5%
      "volume_tolerance_pct": 0.05  // 成交量容差±5%
    }
  },
  "health_check": {
    "enabled": true,
    "interval_seconds": 60,           // 检测间隔
    "response_time_threshold": 5.0,   // 响应时间阈值
    "consecutive_failures_threshold": 3 // 连续失败阈值
  },
  "logging": {
    "level": "INFO",
    "file": "logs/data_master.log"
  }
}
```

**配置读取**:

```python
# 支持点号分隔的嵌套键
cache_max_days = config.get('cache.max_days_per_stock', 120)

# 按用途获取数据源
sources = config.get_sources_by_usage('kline_day')
# → ['tushare', 'mootdx', 'baostock'] (按优先级排序)
```

### 4. 缓存预取优化

**问题**: 用户请求120条，缓存也是120条，后续请求121条会miss缓存

**解决方案**: 实际请求时多获取10%数据

**[代码位置: data_master.py:222-247]**

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

## 测试策略

### 测试目录结构

```
test/
├── run_gui_test.bat                # 一键启动GUI测试
├── interactive_test_gui.py         # 【推荐】交互式测试GUI
├── test_intraday_cache.py          # 盘中/盘后缓存完整测试
├── test_cache_simple.py            # 缓存简单验证
├── test_historical_cache.py        # 历史数据缓存测试
└── TEST_FILES_README.md            # 测试文件说明
```

### 推荐测试流程

**1. 交互式GUI测试（最方便）**:

```bash
cd test
python interactive_test_gui.py
```

功能：
- K线数据测试（日线、分钟线）
- 实时数据测试（Tick数据）
- 数据源状态监控
- 缓存管理（统计、清理）
- 今日走势图（实时更新）

**2. 缓存机制验证**:

```bash
# 完整场景测试（5个场景）
python test_intraday_cache.py

# 简单验证
python test_cache_simple.py

# 历史数据优化验证
python test_historical_cache.py
```

**3. 单元测试覆盖**:

| 测试点 | 测试文件 | 验证内容 |
|--------|---------|---------|
| 盘中不缓存当日 | test_intraday_cache.py | 盘中时段请求最新数据 |
| 盘后缓存当日 | test_intraday_cache.py | 盘后时段缓存当日数据 |
| 历史数据直接缓存 | test_historical_cache.py | end_date < 今天直接缓存 |
| 周末使用最新交易日 | test_cache_simple.py | 周末请求返回上周五数据 |
| 双源校验 | test_cache_fix.py | 数据校验通过率 ≥ 80% |

### 测试注意事项

**导入路径问题**:
- 测试脚本位于 `test/` 目录
- 必须将 StockDataMaster 的父目录添加到 `sys.path`
- 使用 `from StockDataMaster import StockDataMaster` 导入

**日志编码**:
- 所有日志必须使用 UTF-8 编码
- 错误示例: `logging.FileHandler('app.log')` ❌
- 正确示例: `logging.FileHandler('app.log', encoding='utf-8')` ✅

**测试数据清理**:
- 测试完成后清理临时文件
- 测试日志保存在 `logs/` 目录
- 测试数据库可手动删除 `cache/kline_cache.db` 重建

---

## 编码规范

### 适配器开发规则

**必须实现的方法**:

```python
class MyAdapter(DataSourceAdapter):
    def connect(self) -> bool:
        """连接数据源"""
        pass

    def disconnect(self):
        """断开连接"""
        pass

    def get_kline(self, code, freq, start_date, end_date, count, adjust) -> pd.DataFrame:
        """
        获取K线数据

        返回格式：
        - 列名: date, open, high, low, close, volume, amount
        - date: 字符串 'YYYY-MM-DD'
        - 所有价格必须是前复权（adjust='qfq'）
        """
        pass

    def get_valuation(self, code, start_date, end_date) -> pd.DataFrame:
        """获取估值数据"""
        pass

    def get_tick(self, code) -> Dict[str, Any]:
        """获取实时tick数据"""
        pass
```

**错误处理规则**:

```python
try:
    # 业务逻辑
    pass
except Exception as e:
    self.last_error = str(e)
    self.error_count += 1
    self.logger.error(f"操作失败: {e}")
    return None
```

### 日志规范

**日志级别使用**:

```python
# INFO: 正常操作流程
self.logger.info("数据源初始化成功")
self.logger.info("从缓存获取数据")

# WARNING: 可恢复的错误
self.logger.warning("数据源连接失败，尝试重连")
self.logger.warning("双源校验通过率低，尝试下一个源")

# ERROR: 严重错误
self.logger.error("所有数据源均无法获取数据")
self.logger.error("缓存数据库初始化失败")

# DEBUG: 调试信息（详细执行流程）
self.logger.debug(f"缓存检查: is_fresh={is_fresh}, is_sufficient={is_sufficient}")
```

**日志编码规范**（重要）:

```python
# ✅ 正确：显式指定UTF-8编码
handler = logging.FileHandler('app.log', encoding='utf-8')

# ❌ 错误：依赖系统默认编码
handler = logging.FileHandler('app.log')
```

**原因**: Windows默认编码是GBK，中文日志会乱码。

### 配置管理规则

**新增功能配置**:

1. 在 `config.json` 中添加配置项
2. 使用 `config.get('section.key', default_value)` 读取
3. 不要硬编码任何超时、重试次数、阈值等参数

**示例**:

```python
# ❌ 错误：硬编码
timeout = 10
retry_times = 3

# ✅ 正确：从配置读取
timeout = self.config.get('data_sources.tushare.timeout', 10)
retry_times = self.config.get('data_sources.tushare.retry_times', 3)
```

---

## 常见任务

### 添加新数据源

**步骤**:

1. **创建适配器**（`adapters/newsource_adapter.py`）:

```python
from .base_adapter import DataSourceAdapter

class NewSourceAdapter(DataSourceAdapter):
    def __init__(self, name: str, config: Dict[str, Any]):
        super().__init__(name, config)
        # 自定义初始化

    def connect(self) -> bool:
        # 连接逻辑
        pass

    def get_kline(self, ...):
        # 获取K线数据
        pass

    # 其他方法...
```

2. **注册适配器**（`adapters/__init__.py`）:

```python
from .newsource_adapter import NewSourceAdapter

class AdapterFactory:
    ADAPTER_MAP = {
        'mootdx': MootdxAdapter,
        'baostock': BaostockAdapter,
        'tushare': TushareAdapter,
        'xtquant': XtquantAdapter,
        'newsource': NewSourceAdapter,  # 新增
    }
```

3. **添加配置**（`config.json`）:

```json
{
  "data_sources": {
    "newsource": {
      "enabled": true,
      "priority": 4,
      "timeout": 10,
      "retry_times": 3,
      "use_for": ["kline_day"],
      "custom_param": "value"
    }
  }
}
```

4. **编写测试**:

```python
# test/test_newsource.py
def test_newsource_connection():
    adapter = NewSourceAdapter('newsource', config)
    assert adapter.connect() == True

def test_newsource_kline():
    df = adapter.get_kline('600519', freq='d', count=10)
    assert df is not None
    assert len(df) > 0
```

### 修改缓存策略

**场景1: 调整缓存容量**

编辑 `config.json`:
```json
{
  "cache": {
    "max_days_per_stock": 200  // 从120改为200
  }
}
```

**场景2: 调整校验容差**

编辑 `config.json`:
```json
{
  "cache": {
    "validation": {
      "price_tolerance_abs": 0.02,  // ±0.02元
      "price_tolerance_pct": 0.01,  // ±1%
      "volume_tolerance_pct": 0.10  // ±10%
    }
  }
}
```

**场景3: 修改缓存判断逻辑**

编辑 `data_master.py` 的 `_is_cache_fresh` 方法：

```python
def _is_cache_fresh(self, df: pd.DataFrame, request_end_date: Optional[str] = None) -> bool:
    # 自定义缓存新鲜度判断逻辑
    # ...
```

### 调试数据源问题

**步骤1: 查看日志**

```bash
tail -f logs/data_master.log
```

**步骤2: 查看健康状态**

```python
master = StockDataMaster()
status = master.get_health_status()
print(status)
# {
#     'timestamp': '2025-10-25 14:30:00',
#     'sources': {
#         'tushare': {
#             'enabled': True,
#             'connected': True,
#             'status': 'ok',
#             'last_check': '14:29:45',
#             'response_time': '0.52s',
#             'failure_count': 0
#         }
#     },
#     'active_sources': {
#         'kline': 'tushare',
#         'valuation': 'baostock',
#         'tick': 'xtquant'
#     }
# }
```

**步骤3: 手动测试数据源**

```python
from StockDataMaster.adapters import TushareAdapter

adapter = TushareAdapter('tushare', config)
adapter.connect()

# 测试获取数据
df = adapter.get_kline('600519', freq='d', count=10)
print(df)

# 健康检查
result = adapter.health_check()
print(result)
```

**步骤4: 手动切换数据源**

```python
# 强制切换K线数据源到baostock
master.force_switch_source('kline', 'baostock')

# 验证
status = master.get_health_status()
print(status['active_sources'])
# {'kline': 'baostock', ...}
```

### 查看和管理缓存

**查看缓存统计**:

```python
stats = master.get_cache_statistics()
print(stats)
# {
#     'enabled': True,
#     'total_records': 1200,
#     'validated_records': 1200,
#     'stock_count': 10,
#     'date_range': {'start': '2025-07-01', 'end': '2025-10-24'},
#     'db_size_mb': 0.15,
#     'db_path': 'cache/kline_cache.db'
# }
```

**清理旧缓存**:

```python
# 保留最近120天
master.cleanup_cache(days=120)
```

**手动查询缓存数据库**:

```python
import sqlite3
import pandas as pd

conn = sqlite3.connect('cache/kline_cache.db')

# 查看缓存数据
df = pd.read_sql_query("""
    SELECT code, date, close, source1, source2, validated
    FROM kline_cache
    WHERE code='600519'
    ORDER BY date DESC
    LIMIT 10
""", conn)

print(df)
conn.close()
```

**重建缓存数据库**:

```bash
# 删除旧数据库
rm cache/kline_cache.db

# 重新启动DataMaster会自动创建
```

---

## 已知限制与约束

### 数据源限制

| 数据源 | 限制 | 说明 |
|--------|------|------|
| **Tushare** | 调用频率限制 | 根据积分等级（如200次/分钟） |
| | 分钟线权限 | 需要足够的积分点数 |
| | Token配置 | 必须在config.json中配置 |
| **Mootdx** | 分钟线最多800条 | 超过会失败 |
| | 复权BUG | 分钟线复权数据不准确 |
| **Baostock** | 速度慢 | 免费但响应时间长 |
| **xtquant** | 依赖QMT客户端 | 客户端未运行自动禁用 |

### 缓存限制

- 单只股票最大缓存: 120条（可配置）
- 只缓存日K线，不缓存分钟K线、估值、Tick
- 双源校验通过率需 ≥ 80%
- 缓存数据库路径必须可写

### 系统限制

**股票代码格式**:
```python
# ✅ 支持
'600519'      # 6位数字
'sh.600519'   # 带前缀（内部会转换）

# ❌ 不支持
'600519.SH'   # 后缀格式
```

**日期格式**:
```python
# ✅ 正确
'2025-10-24'  # YYYY-MM-DD

# ❌ 错误
'2025/10/24'  # 斜杠
'20251024'    # 无分隔符
```

**复权类型**:
```python
# ✅ 唯一支持
adjust='qfq'  # 前复权

# ❌ 不支持
adjust='hfq'  # 后复权
adjust=None   # 不复权
```

---

## 最近实现的功能

### 1. 智能日K线缓存修复（2025-10-25）

**问题**: 盘中时段缓存未收盘的当日数据，导致数据过期

**解决方案**:
- 盘中时段（< 15:00）：不缓存当日数据
- 盘后时段（>= 15:00）：缓存当日收盘数据
- 周末/节假日：使用最新交易日缓存数据

**效果**:
- 数据准确性从60%提升到100%
- 盘中获取实时数据，盘后使用缓存

**参考文档**:
- [当日K线缓存机制深度分析报告](docs/当日K线缓存机制深度分析报告.md)
- [智能日K线缓存修复总结](docs/智能日K线缓存修复总结.md)

### 2. 历史数据缓存优化（2025-10-25）

**问题**: 盘中时段请求历史数据（不包含今天）仍重复请求

**解决方案**:
- 检查用户请求的 `end_date`
- 如果 `end_date < 今天`，直接使用缓存
- 历史数据永远不变，无需重新获取

**效果**:
- 提高盘中历史数据缓存命中率
- 减少不必要的API调用

**参考文档**:
- [历史数据缓存优化测试报告](docs/历史数据缓存优化测试报告.md)

### 3. 今日走势图功能（2025-10-21）

**功能**: 交互式GUI新增今日走势图，实时显示5分钟K线

**特点**:
- Tkinter集成matplotlib图表
- 自动刷新功能（可配置间隔）
- 显示股票名称、最新价格、数据来源

**使用**:
```python
# 启动GUI
python test/interactive_test_gui.py

# 点击"今日走势图"按钮
```

**参考文档**:
- [今日走势图功能使用指南](docs/今日走势图功能使用指南.md)
- [自动刷新功能完整交付总结](docs/自动刷新功能完整交付总结.md)

---

## AI 使用指引

### 推荐的AI辅助开发流程

**1. 理解架构**:
- 阅读本文档的"架构总览"和"核心架构模式"章节
- 查看 `data_master.py` 和 `cache_manager.py` 核心逻辑
- 理解适配器模式和缓存策略

**2. 定位问题**:
- 查看 `logs/data_master.log` 日志
- 使用 `get_health_status()` 检查数据源状态
- 使用 `get_cache_statistics()` 检查缓存状态

**3. 修改代码**:
- **不要修改源代码结构**（适配器模式、单例模式）
- 优先通过 `config.json` 调整参数
- 如需修改逻辑，遵循"编码规范"章节
- 添加充分的日志和注释

**4. 测试验证**:
- 使用 `interactive_test_gui.py` 进行功能测试
- 编写单元测试脚本（参考 `test/` 目录）
- 测试完成后清理临时文件

**5. 文档更新**:
- 更新本 `CLAUDE.md` 文档
- 在"变更记录"章节添加更新
- 生成详细的测试报告（参考 `docs/` 目录）

### 常见AI辅助场景

**场景1: 调试缓存问题**

```
提示词：
"我发现盘中时段请求历史数据仍然重复获取，请分析 data_master.py 的 _is_cache_fresh 方法，
找出问题并提供修复方案。要求：
1. 保持向后兼容
2. 添加详细注释
3. 提供测试用例"
```

**场景2: 添加新数据源**

```
提示词：
"请帮我添加 AkShare 数据源适配器，要求：
1. 继承 DataSourceAdapter 基类
2. 实现 get_kline、get_valuation、get_tick 方法
3. 遵循现有适配器的错误处理规范
4. 在 config.json 中添加配置示例
5. 提供单元测试"
```

**场景3: 性能优化**

```
提示词：
"分析 cache_manager.py 的 validate_and_cache 方法，找出性能瓶颈并优化。
要求：
1. 保持双源校验逻辑不变
2. 减少数据库操作次数
3. 提供性能对比测试"
```

### AI辅助开发的注意事项

**✅ 推荐做法**:
- 充分理解现有架构后再修改
- 遵循项目编码规范
- 添加详细的注释和日志
- 编写测试用例验证修改
- 更新文档记录变更

**❌ 避免做法**:
- 破坏适配器模式结构
- 硬编码配置参数
- 删除现有的健康检测逻辑
- 忽略UTF-8日志编码
- 不写测试直接提交

---

## 参考文档

### 核心文档

- [README.md](README.md) - 项目概述和快速开始
- [接口调用规范与最佳实践.md](接口调用规范与最佳实践.md) - API详细说明
- [config.json](config.json) - 配置文件示例

### 技术文档

- [当日K线缓存机制深度分析报告.md](docs/当日K线缓存机制深度分析报告.md)
- [智能日K线缓存修复总结.md](docs/智能日K线缓存修复总结.md)
- [历史数据缓存优化测试报告.md](docs/历史数据缓存优化测试报告.md)
- [今日走势图功能使用指南.md](docs/今日走势图功能使用指南.md)

### 测试文档

- [test/TEST_FILES_README.md](test/TEST_FILES_README.md) - 测试文件说明

---

## 联系与贡献

**项目作者**: YOLO Team
**许可证**: MIT License
**问题反馈**: 请提交 GitHub Issue

**贡献指南**:
1. Fork 项目
2. 创建功能分支
3. 遵循编码规范
4. 编写测试用例
5. 更新文档
6. 提交 Pull Request

---

**Happy Trading! 📈**

> 本文档由 Claude AI 辅助生成和维护，遵循初始化架构师规范。
