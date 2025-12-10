# StockDataMaster

[![Python](https://img.shields.io/badge/Python-3.7+-blue.svg)](https://www.python.org/)
[![License](https://img.shields.io/badge/License-MIT-green.svg)](LICENSE)
[![Status](https://img.shields.io/badge/Status-Production-brightgreen.svg)]()

专业的股票数据主数据接口系统，通过多数据源集成、智能缓存和健康检测，为量化交易和数据分析提供高可用、高性能的数据服务。

---

## 核心特性

### 多数据源集成
- **4大数据源无缝集成**: Tushare（日K线）、Mootdx（分钟K线）、Baostock（备用）、xtquant（实时Tick）
- **统一接口设计**: 一套API屏蔽所有数据源差异
- **智能故障切换**: 数据源异常自动切换备用源，保证服务可用性

### 智能缓存系统
- **833倍性能提升**: 日K线缓存响应从2-3秒降至3ms
- **盘中/盘后自适应**: 盘中不缓存当日数据（保证实时性），盘后自动缓存收盘数据
- **双源校验机制**: 缓存前校验数据准确性，价格容差±0.01元，成交量容差±5%
- **100%缓存命中率**: 智能三层判断，历史数据永不过期

### 健康检测与热切换
- **后台自动监控**: 60秒间隔健康检测，及时发现数据源异常
- **无感知切换**: 故障自动降级，用户无感知
- **时段感知策略**: 交易时段严格检查，非交易时段宽松容错

### 生产级稳定性
- **高并发支持**: 10线程QPS可达300+
- **长期稳定运行**: 1000次连续查询性能退化<5%
- **完善的错误处理**: 三层验证连接机制，确保数据有效性

---

## 快速开始

### 安装依赖

```bash
# 核心依赖
pip install pandas numpy mootdx baostock tushare

# xtquant（可选，需要QMT客户端）
# 从 https://dict.thinktrader.net/ 下载miniQMT
```

### 基本使用

```python
from StockDataMaster import StockDataMaster

# 初始化（单例模式）
master = StockDataMaster()

# 获取日K线数据（自动缓存）
df = master.get_kline('600519', freq='d', count=120)
print(f"数据来源: {df.attrs.get('source')}")  # 'cache' 或 'tushare'

# 获取30分钟K线
df_30m = master.get_kline('600519', freq='30m', count=50)

# 获取实时行情
tick = master.get_tick('600519')
print(f"最新价: {tick['last']}")

# 查看健康状态
status = master.get_health_status()
print(status['active_sources'])

# 缓存统计
stats = master.get_cache_statistics()
print(f"缓存命中率: {stats['total_records']} 条记录")

# 关闭释放资源
master.close()
```

### 配置说明

编辑 `config.json` 配置数据源和缓存策略：

```json
{
  "data_sources": {
    "tushare": {
      "enabled": true,
      "priority": 1,
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

---

## 性能表现

基于生产环境实际测试数据：

| 操作 | 无缓存 | 有缓存 | 加速比 |
|------|-------|-------|-------|
| 获取100条日K线 | 2-3秒 | 3ms | **833x** |
| 股票名称查询 | 0.77ms | 0.001ms | **672x** |
| 缓存命中率 | - | 100% | - |
| 并发QPS（10线程） | - | 298+ | - |

**关键亮点**：
- 缓存加速效果：41.82倍（平均）
- L1内存缓存响应：< 0.01ms
- 长期稳定性：1000次连续查询性能退化 < 5%

详见：[性能深度分析报告](docs/StockDataMaster性能深度分析报告.md)

---

## 架构设计

### 设计理念

**适配器模式** + **单例模式** + **配置驱动**

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

### 核心创新

#### 1. 智能三层缓存判断

```python
用户请求 get_kline(code, start_date, end_date, count)
    ↓
[优先级1] end_date < 今天？ → 使用缓存（历史数据永不变）
    ↓
[优先级2] 缓存最新日期 == 今天 且 盘后时段？ → 使用缓存
    ↓
[优先级3] 缓存最新日期 == 最新交易日？ → 使用缓存
    ↓
其他情况 → 重新获取
```

#### 2. 盘中/盘后自适应

| 时段 | 缓存行为 | 说明 |
|------|---------|------|
| 盘中（< 15:00） | 不缓存当日数据 | 保证实时性 |
| 盘后（≥ 15:00） | 缓存当日收盘数据 | 数据已固定 |
| 周末/节假日 | 使用最新交易日缓存 | 避免无效请求 |

#### 3. 双源校验机制

- 主数据源（Tushare）获取数据
- 校验数据源（Mootdx/Baostock）获取相同数据
- 逐条比对价格和成交量（容差标准：价格±0.01元，成交量±5%）
- 只缓存通过校验的数据（validated=1）
- 校验通过率 ≥ 80% 才缓存成功

---

## 文档中心

### 快速入门
- [快速开始指南](docs/quick-start.md) - 5分钟上手
- [API 参考手册](docs/api-reference.md) - 完整API文档
- [常见问题 FAQ](docs/faq.md) - 问题排查

### 技术深度
- [架构设计文档](docs/architecture.md) - 设计理念与模式
- [性能分析报告](docs/StockDataMaster性能深度分析报告.md) - 性能测试数据
- [接口调用规范](docs/接口调用规范与最佳实践.md) - 最佳实践

### 开发指南
- [CLAUDE.md](CLAUDE.md) - 完整开发文档
- [测试指南](test/README.md) - 测试策略

---

## 核心API

### get_kline() - 获取K线数据

```python
def get_kline(
    code: str,                    # 股票代码
    freq: str = 'd',              # 频率：'d','5m','15m','30m','60m'
    start_date: Optional[str] = None,  # 开始日期 'YYYY-MM-DD'
    end_date: Optional[str] = None,    # 结束日期 'YYYY-MM-DD'
    count: Optional[int] = None,       # 获取数量
    adjust: str = 'qfq',          # 复权类型（固定前复权）
    use_cache: bool = True        # 是否使用缓存
) -> pd.DataFrame
```

**返回数据格式**：
```python
         date     open     high      low    close     volume        amount
0  2025-10-20  1455.00  1469.50  1454.88  1457.93  2594988.0  3.793284e+09
1  2025-10-21  1459.00  1469.94  1455.50  1462.26  2544267.0  3.727984e+09
```

### 其他核心接口

```python
# 获取估值数据
df = master.get_valuation(code, start_date, end_date)

# 获取实时tick数据
tick = master.get_tick(code)

# 获取股票名称
name = master.get_stock_name(code)

# 健康状态检查
status = master.get_health_status()

# 缓存统计
stats = master.get_cache_statistics()

# 清理缓存
master.cleanup_cache(days=120)

# 强制切换数据源
master.force_switch_source('kline', 'baostock')
```

详见：[API 参考手册](docs/api-reference.md)

---

## 使用场景

### 场景1：实时监控（盘中）

```python
# 获取最新5分钟K线
df = master.get_kline('600519', freq='5m', count=48)
```

**特点**：盘中不缓存当日数据，保证实时性

### 场景2：历史数据分析

```python
# 分析过去一个月走势
df = master.get_kline('600519', freq='d',
                      start_date='2025-09-25',
                      end_date='2025-10-24')
```

**特点**：历史数据使用缓存，响应快，缓存命中率高

### 场景3：量化回测

```python
# 获取5年历史数据
df = master.get_kline('600519', freq='d', count=1200)
```

**特点**：分段获取，充分利用缓存

### 场景4：盘后数据更新

```python
import schedule

def update_daily_data():
    """每天15:30更新持仓股票数据"""
    codes = ['600519', '000001', '000858']
    for code in codes:
        df = master.get_kline(code, freq='d', count=1)
        print(f"{code} 更新完成")

schedule.every().day.at("15:30").do(update_daily_data)
```

**特点**：盘后首次请求缓存当日收盘数据，后续查询命中缓存

---

## 测试

### 交互式测试GUI（推荐）

```bash
cd test
python interactive_test_gui.py
```

**功能**：
- K线数据测试（日线、分钟线）
- 实时数据测试（Tick数据）
- 数据源状态监控
- 缓存管理（统计、清理）
- 今日走势图（实时更新）

---

## 注意事项

### 数据源配置

1. **Tushare Token**: 需在 `config.json` 配置有效token
2. **xtquant**: 需本地运行QMT客户端，否则自动降级
3. **缓存路径**: 确保 `cache/` 目录有写权限
4. **日志文件**: 默认输出到 `logs/` 目录

### 数据源限制

| 数据源 | 限制 | 说明 |
|--------|------|------|
| Tushare | 调用频率限制 | 根据积分等级（如200次/分钟） |
| Mootdx | 分钟线最多800条 | 超过会失败 |
| Baostock | 速度慢 | 免费但响应时间长 |
| xtquant | 依赖QMT客户端 | 客户端未运行自动禁用 |

### 数据格式约束

```python
# ✅ 支持的股票代码格式
'600519'      # 6位数字
'sh.600519'   # 带前缀（内部会转换）

# ✅ 支持的日期格式
'2025-10-24'  # YYYY-MM-DD

# ✅ 唯一支持的复权类型
adjust='qfq'  # 前复权
```

---

## 更新日志

### v1.1.0 (2025-11-18)

**xtquant深度优化**（5阶段完成）：
- 接口利用率6.7%（+133%），复权因子<10ms
- 智能缓存机制：833倍性能提升（2-3秒→3ms）
- 时段感知100%准确，缓存优先策略
- 双源校验100%通过率，复权一致性<0.5%误差
- 4数据源无缝切换，60秒健康检测

### v1.0.0 (2025-10-20)

- 初始版本发布
- 支持4个数据源（Mootdx、Baostock、Tushare、xtquant）
- 实现智能缓存系统
- 实现健康检测和热切换
- 完整的文档和测试

---

## 贡献指南

欢迎提交Issue和Pull Request！

**贡献步骤**：
1. Fork 项目
2. 创建功能分支 (`git checkout -b feature/AmazingFeature`)
3. 遵循编码规范（参见 [CLAUDE.md](CLAUDE.md)）
4. 编写测试用例
5. 更新文档
6. 提交 Pull Request

---

## 许可证

MIT License

---

## 作者

YOLO Team

---

## 联系方式

如有问题或建议，请提交 [GitHub Issue](https://github.com/your-repo/StockDataMaster/issues)。

---

**Happy Trading! 📈**
