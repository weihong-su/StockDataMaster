# 日线数据缓存验证基准测试

## 概述

`benchmark_cache_validation.py` 是一个全面的性能和可靠性测试脚本，用于验证 StockDataMaster 的数据获取、缓存和 fallback 机制。

## 测试目标

### 1. 数据规模
- **1000只股票** (上海主板、深圳主板、创业板)
- **最近500个交易日** (约2年历史数据)
- **总数据点**: ~50万条K线记录

### 2. 性能指标

#### 响应时间统计
- 平均响应时间 (Mean)
- 最小/最大响应时间 (Min/Max)
- 标准差 (Std)
- 百分位数 (P50/P95/P99)

#### 有效性指标
- 成功率 (Success Rate)
- 失败率 (Failure Rate)
- 数据完整性 (Data Completeness)
- 数据质量分数 (0-100)

#### 鲁棒性指标
- 错误类型分布
- 重试成功率
- 错误恢复能力

### 3. 缓存性能
- 缓存命中率 (Cache Hit Rate)
- 缓存命中/未命中次数
- 冷启动 vs 热启动性能对比

### 4. Fallback机制
- Fallback事件次数
- 数据源切换路径
- 切换原因统计

## 运行方式

### 基本运行
```bash
# Windows (避免GBK编码错误)
python -X utf8 test/benchmark_cache_validation.py

# Linux/Mac
python test/benchmark_cache_validation.py
```

### 使用自定义配置
```bash
python -X utf8 test/benchmark_cache_validation.py --config custom_config.json
```

## 测试流程

### 第一轮: 冷启动测试
1. **禁用缓存** (`use_cache=False`)
2. 直接从数据源获取数据
3. 测试数据源的原始性能
4. 记录响应时间和成功率

### 第二轮: 热启动测试
1. **启用缓存** (`use_cache=True`)
2. 利用第一轮建立的缓存
3. 测试缓存命中率
4. 对比缓存前后性能提升

## 数据质量评分

脚本会对每条数据进行质量评分 (0-100分)，检查项包括:

| 检查项 | 权重 | 说明 |
|--------|------|------|
| 数据完整性 | 20% | 无NaN值 |
| OHLC逻辑 | 30% | high >= low |
| 收盘价合理性 | 30% | close在[low, high]之间 |
| 价格正值 | 5% x 4 | open/high/low/close > 0 |
| 成交量非负 | 10% | volume >= 0 |

## 输出报告

### 1. 控制台输出
实时显示测试进度和关键指标:
```
进度: 500/1000 (50.0%) | 成功: 485 | 失败: 15 | 速度: 12.5 stocks/s | ETA: 40s
```

### 2. 日志文件
详细日志保存在 `logs/benchmark_YYYYMMDD_HHMMSS.log`

### 3. JSON报告
完整测试结果保存在 `logs/benchmark_report_YYYYMMDD_HHMMSS.json`

#### 报告结构
```json
{
  "summary": {
    "timestamp": "2026-04-24T10:30:00",
    "sources": {
      "tushare": {
        "total_requests": 1000,
        "success_rate": 98.5,
        "response_time": {
          "mean": 245.3,
          "p95": 450.2,
          "p99": 680.5
        },
        "data_quality": {
          "mean": 98.7
        }
      }
    },
    "cache": {
      "hits": 950,
      "misses": 50,
      "hit_rate": 95.0
    },
    "fallback": {
      "total_events": 15,
      "events": [...]
    }
  },
  "cold_start_results": [...],
  "warm_start_results": [...]
}
```

## 性能基准参考

### 响应时间 (毫秒)
| 场景 | 优秀 | 良好 | 可接受 | 需优化 |
|------|------|------|--------|--------|
| 缓存命中 | < 5 | < 10 | < 20 | > 20 |
| 网络请求 | < 200 | < 500 | < 1000 | > 1000 |
| P95 | < 300 | < 800 | < 1500 | > 1500 |

### 成功率
| 数据源 | 优秀 | 良好 | 可接受 | 需优化 |
|--------|------|------|--------|--------|
| 主数据源 | > 99% | > 95% | > 90% | < 90% |
| 备用数据源 | > 95% | > 90% | > 85% | < 85% |

### 缓存命中率
| 场景 | 优秀 | 良好 | 可接受 | 需优化 |
|------|------|------|--------|--------|
| 热启动 | > 95% | > 90% | > 80% | < 80% |

### 数据质量分数
| 分数 | 评级 | 说明 |
|------|------|------|
| 95-100 | 优秀 | 数据完全符合规范 |
| 85-94 | 良好 | 少量异常可接受 |
| 70-84 | 可用 | 存在一定问题 |
| < 70 | 不可用 | 数据质量差 |

## 故障排查

### 常见问题

#### 1. 大量请求失败
**可能原因:**
- 数据源token未配置或已过期
- 网络连接问题
- 数据源API限流

**解决方案:**
```bash
# 检查配置
cat config.json | grep token

# 测试单个数据源
python test/test_adapters.py
```

#### 2. 缓存命中率低
**可能原因:**
- 缓存数据库损坏
- 缓存过期时间设置过短
- 首次运行(正常)

**解决方案:**
```bash
# 检查缓存数据库
sqlite3 cache/kline_cache.db "SELECT COUNT(*) FROM kline_cache;"

# 查看缓存配置
cat config.json | grep -A 5 "cache"
```

#### 3. 响应时间过长
**可能原因:**
- 数据源服务器响应慢
- 网络延迟高
- 并发请求过多

**解决方案:**
- 调整 `config.json` 中的 `timeout` 参数
- 减少测试股票数量
- 增加请求间隔 (修改脚本中的 `time.sleep(0.01)`)

## 自定义测试

### 修改测试参数

编辑 `benchmark_cache_validation.py`:

```python
class BenchmarkTest:
    def __init__(self, config_path: Optional[str] = None):
        # ...
        
        # 修改这些参数
        self.num_stocks = 1000    # 股票数量
        self.num_klines = 500     # K线数量
```

### 修改股票代码范围

```python
def generate_stock_codes(self) -> List[str]:
    # 自定义股票代码生成逻辑
    codes = []
    
    # 例: 只测试上海主板
    for i in range(600000, 600100):
        codes.append(f"{i:06d}")
    
    return codes
```

## 与其他测试的对比

| 测试脚本 | 目的 | 数据规模 | 运行时间 |
|----------|------|----------|----------|
| `test_integration.py` | 功能验证 | 少量样本 | < 1分钟 |
| `test_cache_manager.py` | 缓存单元测试 | 单只股票 | < 10秒 |
| `benchmark_cache_validation.py` | 性能基准 | 1000只股票 | 5-15分钟 |
| `test_regression.py` | 回归测试 | 中等规模 | 1-3分钟 |

## 最佳实践

### 1. 定期运行
建议在以下情况运行基准测试:
- 重大代码变更后
- 新增数据源后
- 性能优化后
- 生产环境部署前

### 2. 对比历史数据
保存每次测试的JSON报告，用于:
- 性能趋势分析
- 回归检测
- 容量规划

### 3. 分阶段测试
如果1000只股票测试时间过长:
```python
# 先测试100只
self.num_stocks = 100

# 确认无问题后再测试1000只
self.num_stocks = 1000
```

### 4. 监控资源使用
```bash
# 监控内存和CPU
top -p $(pgrep -f benchmark_cache_validation)

# 监控网络流量
iftop
```

## 扩展功能

### 添加新的性能指标

```python
class BenchmarkStats:
    def __init__(self):
        # 添加自定义指标
        self.custom_metric = defaultdict(list)
    
    def add_custom_metric(self, source: str, value: float):
        self.custom_metric[source].append(value)
```

### 集成监控告警

```python
def _generate_report(self, cold_results, warm_results):
    summary = self.stats.get_summary()
    
    # 检查阈值
    for source, stats in summary['sources'].items():
        if stats['success_rate'] < 90:
            self._send_alert(f"{source} 成功率过低: {stats['success_rate']:.2f}%")
```

## 许可证

本测试脚本遵循 StockDataMaster 项目的许可证。
