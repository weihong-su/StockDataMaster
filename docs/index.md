# StockDataMaster 文档中心

欢迎使用 StockDataMaster - 专业的股票数据主数据接口系统

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

### 🔌 多数据源集成
- **4大数据源**: Tushare、Mootdx、Baostock、xtquant
- **统一接口**: 一套API屏蔽所有差异
- **智能切换**: 故障自动降级

### ⚡ 智能缓存
- **833倍性能提升**: 2-3秒 → 3ms
- **100%缓存命中率**: 智能三层判断
- **盘中/盘后自适应**: 保证实时性和性能

### 🏥 健康检测
- **后台监控**: 60秒间隔
- **自动切换**: 无感知降级
- **时段感知**: 交易时段严格，非交易时段宽松

---

## 快速链接

- [GitHub 仓库](https://github.com/Su-M10/StockDataMaster)
- [问题反馈](https://github.com/Su-M10/StockDataMaster/issues)
- [贡献指南](https://github.com/Su-M10/StockDataMaster#贡献指南)
- [更新日志](https://github.com/Su-M10/StockDataMaster/blob/main/CHANGELOG.md)

---

## 快速开始示例

```python
from StockDataMaster import StockDataMaster

# 初始化
master = StockDataMaster()

# 获取日K线数据
df = master.get_kline('600519', freq='d', count=120)

# 查看数据来源
print(f"数据来源: {df.attrs.get('source')}")

# 关闭释放资源
master.close()
```

---

## 文档版本

- **版本**: 1.2.0
- **最后更新**: 2026-04-30
- **适用版本**: StockDataMaster 1.2.0+

---

**Happy Trading! 📈**
