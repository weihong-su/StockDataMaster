# StockDataMaster 文档中心

欢迎使用 StockDataMaster —— 专业的股票数据主数据接口系统

---

## 快速导航

### 入门指南
- [快速开始](quick-start.md) - 5分钟上手
- [API 参考](api-reference.md) - 完整API文档
- [常见问题](faq.md) - 问题排查

### 技术深度
- [架构设计](architecture.md) - 设计理念与模式
- [性能报告](StockDataMaster性能深度分析报告.md) - 性能测试数据
- [接口调用规范](接口调用规范与最佳实践.md) - 最佳实践

---

## 核心特性概览

### 多数据源集成
- **4大数据源**: Tushare、Mootdx、Baostock、xtquant
- **统一接口**: 一套 API 屏蔽所有差异
- **roles 配置**: 每个数据源按角色/时段灵活调度

### 智能缓存
- **40倍以上缓存加速**: 冷启动 ~120ms → 热缓存 ~3ms
- **520天缓存容量**: 支持完整回测周期
- **盘中/盘后自适应**: 盘中保证实时性，盘后自动固化

### 串行短路校验
- **速度优先**: xtquant（~50ms）优先校验，通过即短路
- **兜底保障**: baostock 作为全时段校验兜底
- **增量校验**: 只验证新增日期，不重复校验历史

### 健康检测
- **后台监控**: 60秒间隔自动巡检
- **自动切换**: 连续失败 ≥3 次触发无感降级
- **时段感知**: 交易时段严格，盘后宽松

---

## 快速开始示例

```python
from StockDataMaster import StockDataMaster

# 初始化（单例）
master = StockDataMaster()

# 获取日K线（缓存优先）
df = master.get_kline('600519', freq='d', count=120)
print(f"数据来源: {df.attrs.get('source')}")

# 获取股票名称（四级查找链）
name = master.get_stock_name('600519')  # 贵州茅台

# 关闭释放资源
master.close()
```

---

## 数据源优先级一览

| 用途 | P1 | P2 | P3 | P4 |
|------|----|----|----|----|
| 日K线 | Tushare | Baostock | Mootdx | xtquant |
| 分钟K线 | xtquant | Baostock | Mootdx | - |
| 实时Tick | xtquant | Mootdx | - | - |
| 估值数据 | Tushare | Baostock | - | - |
| 校验源 | Baostock | xtquant（仅交易时段）| - | - |
| 股票名称 | Baostock | xtquant | Tushare | - |

---

## 文档版本

- **版本**: 1.2.0
- **最后更新**: 2026-04-30
- **适用版本**: StockDataMaster 1.2.0+
- [更新日志](../CHANGELOG.md)
