# StockDataMaster

[![Python](https://img.shields.io/badge/Python-3.7+-blue.svg)](https://www.python.org/)
[![License](https://img.shields.io/badge/License-MIT-green.svg)](LICENSE)
[![Status](https://img.shields.io/badge/Status-Production-brightgreen.svg)]()
[![Documentation](https://img.shields.io/badge/docs-GitHub%20Pages-blue.svg)](https://su-m10.github.io/StockDataMaster/)

专业的股票数据主数据接口系统，通过多数据源集成、智能缓存和健康检测，为量化交易和数据分析提供高可用、高性能的数据服务。

📚 **[完整文档](https://su-m10.github.io/StockDataMaster/)** | 🚀 **[快速开始](https://su-m10.github.io/StockDataMaster/quick-start)** | 📖 **[API 参考](https://su-m10.github.io/StockDataMaster/api-reference)**

---

## 目录

1. [核心特性](#核心特性)
2. [快速开始](#快速开始)
3. [数据源配置指南](#数据源配置指南)
4. [架构设计](#架构设计)
5. [核心 API](#核心-api)
6. [使用场景](#使用场景)
7. [性能表现](#性能表现)
8. [测试](#测试)
9. [注意事项](#注意事项)
10. [发布指南](#发布指南)
11. [更新日志](#更新日志)

---

## 核心特性

### 多数据源集成
- **4 大数据源无缝集成**: Tushare（日K线）、Baostock（免费兜底）、Mootdx（分钟K线）、xtquant（实时 Tick）
- **统一接口设计**: 一套 API 屏蔽所有数据源差异
- **4 层 fallback**: 任何场景都有可用数据源，付费/免费 × QMT/无QMT 全覆盖

### 智能缓存系统
- **833 倍性能提升**: 日K线缓存响应从 2-3 秒降至 3ms
- **盘中/盘后自适应**: 盘中不缓存当日数据（保证实时性），盘后自动缓存收盘数据
- **串行短路校验**: xtquant（50ms）优先校验，通过即短路，无需等待 baostock（2-3s）
- **100% 缓存命中率**: 智能三层判断，历史数据永不过期

### 健康检测与热切换
- **后台自动监控**: 60 秒间隔健康检测，及时发现数据源异常
- **无感知切换**: 故障自动降级，用户无感知
- **时段感知策略**: 交易时段严格检查，非交易时段宽松容错

### 生产级稳定性
- **高并发支持**: 10 线程 QPS 可达 300+
- **长期稳定运行**: 1000 次连续查询性能退化 < 5%
- **完善的错误处理**: 三层验证连接机制，确保数据有效性

---

## 快速开始

### 安装依赖

```bash
# 核心依赖
pip install pandas numpy mootdx baostock tushare

# xtquant（可选，需要 QMT 客户端）
# 从 https://dict.thinktrader.net/ 下载 miniQMT
```

### 基本使用

```python
from StockDataMaster import StockDataMaster

# 初始化（单例模式）
master = StockDataMaster()

# 获取日K线数据（自动缓存）
df = master.get_kline('600519', freq='d', count=120)
print(f"数据来源: {df.attrs.get('source')}")  # 'cache' 或 'tushare'

# 获取 30 分钟K线
df_30m = master.get_kline('600519', freq='30m', count=50)

# 获取实时行情
tick = master.get_tick('600519')
print(f"最新价: {tick['last']}")

# 查看健康状态
status = master.get_health_status()
print(status['active_sources'])

# 缓存统计
stats = master.get_cache_statistics()
print(f"缓存记录数: {stats['total_records']}")

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

## 数据源配置指南

### 数据源优先级

#### 日K线 fallback 链

| 优先级 | 数据源 | 适用场景 | 说明 |
|--------|--------|----------|------|
| P1 | **Tushare** | 付费用户 | 数据质量最高，需有效 token |
| P2 | **Baostock** | 免费兜底 | 复权准确，权威数据，覆盖退市股 |
| P3 | Mootdx | 应急备用 | 速度快但前复权有已知问题 |
| P4 | xtquant | QMT 用户补充 | 需 QMT 客户端运行 |

#### Tick 数据 fallback 链

| 优先级 | 数据源 | 说明 |
|--------|--------|------|
| P1 | **xtquant** | 真实 tick，需 QMT 客户端 |
| P2 | Mootdx | 5 分钟模拟 tick |

#### 股票名称 fallback 链

| 层级 | 数据源 | 说明 |
|------|--------|------|
| L1 | 内存缓存 | 进程内缓存，< 0.01ms |
| L2 | **Baostock** | 免费，含退市股，覆盖最全 |
| L3 | xtquant | QMT 用户快速查询 |
| L4 | Tushare | 付费用户补充 |

#### 数据校验源（串行短路）

| 顺序 | 数据源 | 响应时间 | 说明 |
|------|--------|----------|------|
| 1st | **xtquant** | ~50ms | 交易时段优先，通过即短路 |
| 2nd | Baostock | 2-3s | 兜底校验，免费权威 |

> 串行短路策略：xtquant 通过则直接缓存，无需等待 baostock，节省 98% 等待时间。

---

### 用户场景覆盖

| 场景 | 日K线首选 | Tick 首选 | 股票名称首选 | 校验源 |
|------|-----------|-----------|--------------|--------|
| **付费 + QMT** | Tushare | xtquant | Baostock | xtquant → Baostock |
| **付费 + 无QMT** | Tushare | Mootdx | Baostock | Baostock |
| **免费 + QMT** | Baostock | xtquant | Baostock | xtquant → Baostock |
| **免费 + 无QMT** | Baostock | Mootdx | Baostock | Baostock |

所有场景均有完整 fallback 链，任何配置下都能正常获取数据。

---

### 按用户类型配置

#### 免费用户（无 Tushare token）

```json
{
  "data_sources": {
    "tushare": { "enabled": false },
    "baostock": { "enabled": true },
    "mootdx":   { "enabled": true },
    "xtquant":  { "enabled": false }
  }
}
```

数据路径：日K线 → baostock；实时 Tick → mootdx（5 分钟模拟）

#### 付费用户（有 Tushare token）

```json
{
  "data_sources": {
    "tushare":  { "enabled": true, "token": "your_token" },
    "baostock": { "enabled": true },
    "mootdx":   { "enabled": true },
    "xtquant":  { "enabled": false }
  }
}
```

数据路径：日K线 → tushare → baostock → mootdx；实时 Tick → mootdx

#### QMT 用户（有 miniQMT 客户端）

```json
{
  "data_sources": {
    "xtquant":  { "enabled": true, "qmt_path": "C:/QMT/..." },
    "baostock": { "enabled": true },
    "mootdx":   { "enabled": true },
    "tushare":  { "enabled": true, "token": "your_token" }
  }
}
```

数据路径：日K线 → tushare/baostock；实时 Tick → xtquant（真实 tick）

---

## 架构设计

**适配器模式 + 单例模式 + 配置驱动**

```
用户代码
    ↓
StockDataMaster（单例入口）
    ├─ HealthManager（健康检测与热切换）
    ├─ CacheManager（智能缓存 + 串行短路校验）
    └─ AdapterFactory
        ├─ TushareAdapter   ── 日K线主数据源（需 token）
        ├─ BaostockAdapter  ── 免费兜底数据源
        ├─ MootdxAdapter    ── 分钟K线数据源
        └─ XtquantAdapter   ── 实时 Tick 数据源（需 QMT）
```

### 核心设计

#### 智能三层缓存判断

```
用户请求 get_kline(code, start_date, end_date)
    ↓
[1] end_date < 今天？         → 直接用缓存（历史数据永不变）
    ↓
[2] 缓存最新日期 == 今天
    且盘后（≥ 15:00）？       → 直接用缓存
    ↓
[3] 缓存覆盖请求区间？        → 直接用缓存
    ↓
重新从数据源获取 → 校验 → 缓存
```

#### 盘中/盘后自适应

| 时段 | 缓存行为 | 说明 |
|------|---------|------|
| 盘中（< 15:00） | 不缓存当日数据 | 保证实时性 |
| 盘后（≥ 15:00） | 缓存当日收盘数据 | 数据已固定 |
| 周末/节假日 | 使用最新交易日缓存 | 避免无效请求 |

---

## 核心 API

### get_kline() — 获取K线数据

```python
def get_kline(
    code: str,                         # 股票代码，如 '600519'
    freq: str = 'd',                   # 'd' / '5m' / '15m' / '30m' / '60m'
    start_date: Optional[str] = None,  # 'YYYY-MM-DD'
    end_date: Optional[str] = None,    # 'YYYY-MM-DD'
    count: Optional[int] = None,       # 获取数量
    adjust: str = 'qfq',              # 复权类型（固定前复权）
    use_cache: bool = True
) -> pd.DataFrame
```

返回格式：

```
         date     open     high      low    close     volume        amount
0  2025-10-20  1455.00  1469.50  1454.88  1457.93  2594988.0  3.793284e+09
1  2025-10-21  1459.00  1469.94  1455.50  1462.26  2544267.0  3.727984e+09
```

### 其他核心接口

```python
# 实时行情
tick = master.get_tick('600519')

# 估值数据（PE/PB 等）
df = master.get_valuation('600519', start_date, end_date)

# 股票名称（含退市股）
name = master.get_stock_name('600519')

# 健康状态
status = master.get_health_status()

# 缓存统计 / 清理
stats = master.get_cache_statistics()
master.cleanup_cache(days=120)

# 强制切换数据源
master.force_switch_source('kline', 'baostock')
```

---

## 使用场景

### 实时监控（盘中）

```python
df = master.get_kline('600519', freq='5m', count=48)
```

盘中不缓存当日数据，保证实时性。

### 历史数据分析

```python
df = master.get_kline('600519', freq='d',
                      start_date='2025-09-25',
                      end_date='2025-10-24')
```

历史数据命中缓存，响应 < 5ms。

### 量化回测

```python
df = master.get_kline('600519', freq='d', count=1200)
```

分段获取，充分利用增量缓存。

### 盘后定时更新

```python
import schedule

def update_daily():
    for code in ['600519', '000001', '000858']:
        master.get_kline(code, freq='d', count=1)

schedule.every().day.at("15:30").do(update_daily)
```

---

## 性能表现

| 操作 | 无缓存 | 有缓存 | 加速比 |
|------|--------|--------|--------|
| 获取 100 条日K线 | 2-3 秒 | 3ms | **833x** |
| 股票名称查询 | 0.77ms | 0.001ms | **672x** |
| 缓存命中率 | — | 100% | — |
| 并发 QPS（10 线程） | — | 298+ | — |

- 串行短路校验：xtquant 通过时总校验耗时 < 100ms（原并行等待 2-3s）
- L1 内存缓存：< 0.01ms
- 长期稳定性：1000 次连续查询性能退化 < 5%

---

## 测试

```bash
# 运行完整测试套件（132 项）
python -X utf8 -m pytest test/suite/ -v

# 只运行单元测试（无需网络）
python -X utf8 -m pytest test/suite/ -v -m unit

# 鲁棒性配置验证
python test/validate_robustness.py

# Baostock 实网冒烟测试
python test/smoke_baostock.py

# 交互式测试 GUI
cd test && python interactive_test_gui.py
```

---

## 注意事项

### 数据格式约束

```python
# 股票代码：6 位数字或带前缀
'600519'      # ✅
'sh.600519'   # ✅（内部自动转换）
'600519.SH'   # ❌ 不支持后缀格式

# 日期格式
'2025-10-24'  # ✅ YYYY-MM-DD only

# 复权类型
adjust='qfq'  # ✅ 仅支持前复权
```

### 数据源限制

| 数据源 | 限制 | 说明 |
|--------|------|------|
| Tushare | 调用频率限制 | 根据积分等级（如 200 次/分钟） |
| Mootdx | 分钟线最多 800 条 | 超过会失败 |
| Baostock | 响应较慢 | 免费但 2-3s/次 |
| xtquant | 依赖 QMT 客户端 | 客户端未运行自动禁用 |

### Windows 注意事项

- 日志必须用 UTF-8 编码：`logging.FileHandler('file.log', encoding='utf-8')`
- pytest 需加 `-X utf8` 参数避免 GBK 编码错误

---

## 发布指南

### 发布前检查清单

**代码质量**

- [ ] `python -X utf8 -m pytest test/suite/ -v` 全部通过（132 项）
- [ ] `python test/validate_robustness.py` 5/5 通过
- [ ] `logs/` 目录已清理，临时文件已删除
- [ ] `config.json` 中无真实 token

**文档**

- [ ] README.md 版本号已更新
- [ ] CHANGELOG.md 已记录本次变更
- [ ] CLAUDE.md 已同步更新

**版本信息**

- [ ] 版本号遵循语义化版本：`vMAJOR.MINOR.PATCH`
- [ ] 发布日期已更新

### 发布步骤

```bash
# 1. 确保主分支最新
git checkout main && git pull origin main

# 2. 运行完整测试
python -X utf8 -m pytest test/suite/ -v

# 3. 提交变更
git add . && git commit -m "chore: prepare for vX.Y.Z release"

# 4. 创建版本标签
git tag -a vX.Y.Z -m "Release vX.Y.Z"

# 5. 推送
git push origin main && git push origin vX.Y.Z

# 6. 创建 GitHub Release（可选）
gh release create vX.Y.Z --title "vX.Y.Z" --notes-file CHANGELOG.md
```

---

## 更新日志

### v1.2.0（2026-04）

**数据源鲁棒性优化**：

- 日K线 fallback 链调整：baostock 升至 P2（免费权威兜底），mootdx 降至 P3（前复权有已知问题）
- 股票名称获取：baostock 升至 L2 首选（含退市股，免费无门槛）
- 串行短路校验：xtquant（50ms）优先，通过即短路，废弃并行等待方案
- 测试：132/132 pytest 通过，5/5 鲁棒性验证通过

### v1.1.0（2025-11）

**xtquant 深度优化**（5 阶段完成）：

- 接口利用率提升 133%，复权因子 < 10ms
- 智能缓存机制：833 倍性能提升（2-3 秒 → 3ms）
- 时段感知 100% 准确，缓存优先策略
- 双源校验 100% 通过率，复权一致性误差 < 0.5%
- 4 数据源无缝切换，60 秒健康检测

### v1.0.0（2025-10）

- 初始版本发布
- 支持 4 个数据源（Tushare、Baostock、Mootdx、xtquant）
- 实现智能缓存系统
- 实现健康检测和热切换

---

## 贡献指南

1. Fork 项目
2. 创建功能分支：`git checkout -b feature/AmazingFeature`
3. 遵循编码规范（参见 [CLAUDE.md](CLAUDE.md)）
4. 编写测试用例并确保全部通过
5. 提交 Pull Request

---

## 许可证

MIT License

---

*Happy Trading!*
