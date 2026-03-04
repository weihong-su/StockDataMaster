# StockDataMaster 自动化回归测试指南

## 概述

本目录包含 StockDataMaster 项目的自动化回归测试脚本，用于发布前的完整功能测试和性能测试。

## 测试脚本列表

### 1. 盘前测试 (test_pre_market.py) ✅

**测试时段**: 当前时间 < 9:15
**测试重点**:
- 缓存数据可用性（历史数据）
- 数据源连接状态
- 健康检查机制
- 缓存统计准确性

**执行命令**:
```bash
C:\Users\PC\Anaconda3\envs\python39\python.exe test\test_pre_market.py
```

**测试覆盖**:
- 功能测试: 15项 (数据源健康检查、历史K线获取、缓存命中率、股票名称获取)
- 性能测试: 2项 (缓存性能、批量获取性能)
- 数据质量测试: 7项 (数据完整性、准确性、一致性)

**最新测试结果**: 通过率 96% (24/25)

### 2. 盘中测试 (test_during_market.py) ⏳

**测试时段**: 9:15 - 15:00
**测试重点**:
- 实时Tick数据获取
- xtquant实时性能
- 盘中缓存策略验证（不缓存当日）
- 数据源自动切换测试
- 分钟K线数据测试

**状态**: 待创建

### 3. 盘后测试 (test_post_market.py) ⏳

**测试时段**: 时间 >= 15:00
**测试重点**:
- 当日收盘数据获取
- 盘后缓存写入验证
- 双源校验测试
- 完整性能基准测试

**状态**: 待创建

## 测试环境要求

### Python 环境

- **Python版本**: 3.9.x (推荐使用 Anaconda)
- **虚拟环境**: `C:\Users\PC\Anaconda3\envs\python39`

### 依赖库

```bash
# 核心依赖
pandas>=1.3.5
numpy>=1.21.0

# 数据源库
mootdx>=0.8.4
baostock>=0.8.8
tushare>=1.2.89

# xtquant 需要单独安装 QMT 客户端
```

### 安装依赖

```bash
# 使用国内镜像加速
C:\Users\PC\Anaconda3\envs\python39\python.exe -m pip install pandas numpy mootdx baostock tushare -i https://pypi.tuna.tsinghua.edu.cn/simple
```

## 快速开始

### 1. 运行盘前测试

```bash
# 进入项目根目录
cd c:\github-repo\StockDataMaster

# 运行测试
C:\Users\PC\Anaconda3\envs\python39\python.exe test\test_pre_market.py
```

### 2. 查看测试报告

测试完成后，会在 `test/reports/` 目录生成两份报告：

1. **JSON报告**: `pre_market_test_YYYYMMDD_HHMMSS.json`
   - 机器可读格式
   - 包含完整的测试数据和元数据

2. **Markdown报告**: `pre_market_test_YYYYMMDD_HHMMSS.md`
   - 人类可读格式
   - 包含测试摘要和详细结果表格

**查看报告**:

```bash
# 查看Markdown报告
type test\reports\pre_market_test_20251210_091420.md

# 查看JSON报告
python -m json.tool test\reports\pre_market_test_20251210_091420.json
```

## 测试报告结构

### JSON报告结构

```json
{
  "test_info": {
    "script_name": "盘前回归测试",
    "test_time": "2025-12-10 09:14:14",
    "market_phase": "pre_market",
    "python_version": "3.9.23",
    "platform": "Windows-10-10.0.22631-SP0"
  },
  "test_results": {
    "total_tests": 25,
    "passed": 24,
    "failed": 1,
    "skipped": 0,
    "pass_rate": 96.0
  },
  "test_categories": {
    "功能测试": {...},
    "性能测试": {...},
    "数据质量测试": {...}
  },
  "performance_metrics": {...},
  "detailed_results": [...]
}
```

### Markdown报告结构

1. **测试信息**: 测试时间、环境、股票池
2. **测试结果**: 总体通过率、耗时统计
3. **分类测试结果**: 功能、性能、数据质量
4. **详细测试结果**: 每个测试项的详细信息表格

## 测试配置

### 测试股票池

默认测试 5 只股票：

```python
TEST_STOCKS = [
    ('600519', '贵州茅台'),  # 高价股
    ('000001', '平安银行'),  # 深市股票
    ('600000', '浦发银行'),  # 金融股
    ('000858', '五粮液'),    # 消费股
    ('601318', '中国平安'),  # 大盘股
]
```

### 测试周期

默认测试 3 个周期：

```python
TEST_PERIODS = [30, 60, 120]  # 天数
```

### 性能阈值

| 测试项 | 阈值 | 说明 |
|--------|------|------|
| 缓存性能提升 | ≥ 10x | 缓存 vs 网络请求 |
| 批量获取平均时间 | < 2.0s | 盘前测试（缓存） |
| 单次数据获取 | < 5.0s | 正常情况 |

## 常见问题

### Q1: 测试失败怎么办？

**A**: 查看详细的测试报告和日志：

1. 查看测试报告中的错误信息
2. 查看 `logs/data_master.log` 日志文件
3. 检查数据源连接状态
4. 确认测试环境配置正确

### Q2: 如何只运行特定测试？

**A**: 修改测试脚本，注释掉不需要的测试方法：

```python
def run_all_tests(self):
    self.setup()
    self.test_functional()      # 功能测试
    # self.test_performance()   # 注释掉性能测试
    # self.test_data_quality()  # 注释掉数据质量测试
    self.generate_report()
    self.teardown()
```

### Q3: 测试报告乱码怎么办？

**A**: 确保使用 UTF-8 编码打开报告：

```bash
# Windows PowerShell
Get-Content test\reports\pre_market_test_*.md -Encoding UTF8

# 或使用支持 UTF-8 的文本编辑器（如 VS Code, Notepad++）
```

### Q4: 如何清理测试报告？

**A**: 手动删除 `test/reports/` 目录中的旧报告：

```bash
# 删除所有报告
del test\reports\*.json
del test\reports\*.md

# 或只删除特定日期的报告
del test\reports\pre_market_test_20251210_*.json
```

### Q5: 测试运行很慢怎么办？

**A**: 盘前测试主要测试缓存，应该很快（< 10秒）。如果慢，检查：

1. 缓存数据库是否存在且正常
2. 数据源连接是否超时
3. 网络连接是否正常

## 测试开发指南

### 添加新测试项

1. 在测试类中添加新的测试方法：

```python
def _test_my_feature(self, results: Dict):
    """测试我的新功能"""
    print("\n[功能测试 1.X] 测试我的新功能")

    try:
        # 测试逻辑
        result = self.master.my_new_method()

        results["total"] += 1

        if result is not None:
            results["passed"] += 1
            self._log_test("我的新功能", True, "测试通过")
        else:
            results["failed"] += 1
            self._log_test("我的新功能", False, "测试失败")

    except Exception as e:
        results["total"] += 1
        results["failed"] += 1
        self._log_test("我的新功能", False, str(e))
```

2. 在 `test_functional()` 中调用：

```python
def test_functional(self):
    # ... 现有测试 ...
    self._test_my_feature(functional_results)
```

### 修改测试配置

直接修改脚本顶部的常量：

```python
# 修改测试股票
TEST_STOCKS = [
    ('600519', '贵州茅台'),
    ('000001', '平安银行'),
    # 添加新股票
    ('688111', '某科创板股票'),
]

# 修改测试周期
TEST_PERIODS = [10, 30, 60, 120]  # 增加10天周期
```

## 测试最佳实践

### 1. 测试前准备

- ✅ 确保数据源配置正确（`config.json`）
- ✅ 确保缓存数据库存在（`cache/kline_cache.db`）
- ✅ 确保日志目录可写（`logs/`）
- ✅ 确保测试报告目录存在（`test/reports/`）

### 2. 测试时注意

- ⚠️ 盘前测试主要测试缓存，不会触发网络请求
- ⚠️ 盘中测试会触发实时数据请求，消耗API配额
- ⚠️ 盘后测试会写入大量缓存数据

### 3. 测试后清理

- 🧹 清理旧的测试报告（保留最近3次）
- 🧹 清理测试日志（可选）
- 🧹 检查缓存数据库大小（过大时清理）

## 持续集成（CI/CD）

### 自动化测试运行

可以创建自动化脚本，在不同时段运行对应的测试：

```python
# run_scheduled_tests.py
import datetime

now = datetime.datetime.now()
hour = now.hour
minute = now.minute

if hour < 9 or (hour == 9 and minute < 15):
    # 盘前测试
    os.system("python test/test_pre_market.py")
elif 9 <= hour < 15:
    # 盘中测试
    os.system("python test/test_during_market.py")
else:
    # 盘后测试
    os.system("python test/test_post_market.py")
```

### 定时任务配置

**Windows 任务计划程序**:

1. 打开"任务计划程序"
2. 创建基本任务
3. 设置触发器（每天特定时间）
4. 设置操作：运行测试脚本

## 贡献指南

欢迎贡献新的测试用例！请遵循以下规范：

1. **测试方法命名**: `_test_xxx`
2. **测试日志**: 使用 `self._log_test()` 记录
3. **异常处理**: 完善的 try-except 包装
4. **性能记录**: 记录测试耗时
5. **文档更新**: 更新本README

## 相关文档

- [StockDataMaster 项目文档](../README.md)
- [自动化回归测试总结报告](../docs/自动化回归测试总结报告.md)
- [测试文件说明](TEST_FILES_README.md)

## 联系方式

如有问题或建议，请提交 GitHub Issue。

---

**最后更新**: 2025-12-10
**版本**: v1.0.0
