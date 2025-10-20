# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## 项目概述

StockDataMaster 是一个专业的股票数据主数据接口系统，提供多数据源集成、智能缓存、健康检测和热切换功能。这是一个 Python 库，支持内置依赖库的独立部署模式。

**核心特性:**
- 多数据源适配器架构（Mootdx、Baostock、Tushare、xtquant）
- SQLite 智能缓存系统，带双源数据校验
- 自动健康检测与热切换机制
- 统一前复权数据处理
- 单例模式的主接口设计

## 架构要点

### 1. 适配器模式核心

**关键架构:** 所有数据源都通过 `DataSourceAdapter` 基类统一接口：
- [adapters/base_adapter.py](adapters/base_adapter.py) 定义了抽象接口
- 每个数据源（mootdx/baostock/tushare/xtquant）实现独立的适配器
- `AdapterFactory` 负责创建和管理适配器实例
- 所有适配器必须实现 `connect()`, `get_kline()`, `get_valuation()`, `get_tick()` 方法

**数据流:** 用户请求 → StockDataMaster → HealthManager（选择可用源）→ 适配器 → 原始数据源

### 2. 单例模式主接口

[data_master.py](data_master.py) 的 `StockDataMaster` 类是整个系统的入口：
- 使用 `__new__` 实现单例模式，确保全局唯一实例
- 初始化时创建所有适配器、缓存管理器和健康管理器
- 提供 `get_kline()`, `get_valuation()`, `get_tick()` 等统一接口
- **注意**: 类名已从 `DataMaster` 重命名为 `StockDataMaster`，但保留 `DataMaster` 别名以保持向后兼容

### 3. 配置驱动设计

[config.py](config.py) + [config.json](config.json) 驱动所有行为：
- `use_builtin_libs`: 控制是否使用 lib/ 目录的内置库
- `data_sources`: 每个数据源的启用状态、优先级、超时、重试等配置
- `cache`: 缓存策略（日K线最多保存120条/股票，数据校验容差）
- `health_check`: 健康检测间隔、失败阈值、响应时间阈值
- `hot_switch`: 热切换参数（平滑过渡、缓冲区大小）

### 4. 内置库机制

**重要:** 项目支持两种依赖模式：
- **标准模式:** 使用 `pip install` 安装的全局依赖
- **内置模式:** 使用 lib/ 目录的本地依赖库（`use_builtin_libs: true`）

内置库机制位于 [lib/](lib/) 目录：
- lib/install_libs.py 用于安装内置库
- lib/ 目录包含 mootdx、baostock、tushare、xtquant 的完整副本
- 适配器根据 `use_builtin_libs` 配置动态导入相应模块

### 5. 缓存与健康管理

**缓存管理器** ([cache/cache_manager.py](cache/cache_manager.py)):
- SQLite 数据库存储日K线缓存（仅日线，分钟线不缓存）
- 双源校验机制：使用两个数据源比对数据，只缓存一致的数据
- 价格容差: ±0.01元 或 ±0.5%，成交量容差: ±5%

**健康管理器** ([health/health_manager.py](health/health_manager.py)):
- 后台线程每分钟检测各数据源健康状态
- 根据响应时间、连续失败次数判断数据源可用性
- 自动切换到优先级次高的健康数据源

## 开发工作流

### 环境设置

使用 Anaconda 虚拟环境（Python 3.8）：
```bash
# 激活环境
conda activate python38

# 安装核心依赖
pip install pandas numpy

# 安装数据源库（如果不使用内置库）
pip install mootdx baostock tushare
```

### 测试命令

**功能测试:**
```bash

# 进入test目录运行
cd test
python interactive_test_gui.py
```

**导入路径问题说明:**

项目使用相对导入（`from .config import ...`），测试脚本必须正确设置 `sys.path`：
- 将 StockDataMaster 的**父目录**添加到 sys.path（如 `C:\github-repo\`）
- 然后使用 `from StockDataMaster import StockDataMaster` 导入（也可以使用向后兼容的 `DataMaster` 别名）

测试脚本已自动处理路径设置：
```python
# test目录脚本的标准路径设置
test_dir = os.path.dirname(os.path.abspath(__file__))
project_root = os.path.dirname(test_dir)
parent_dir = os.path.dirname(project_root)
sys.path.insert(0, parent_dir)  # 添加父目录以支持包导入
```

**单元测试结构:**
- 测试文件统一放在 test/ 目录（项目根目录下）
- 测试文件命名格式: `test_<模块名>.py`
- 测试导出的数据文件保存在 test/ 目录
- 测试日志保存在 logs/ 目录
- 测试完成后需清理测试生成的文件

**验证检查点:**
1. 测试至少两个数据源的连接
2. 验证缓存命中和缓存失效场景
3. 模拟数据源故障测试热切换
4. 验证前复权数据的正确性

**常见测试问题:**
- **导入失败**: 确保从正确的目录运行，或使用提供的 .bat 脚本
- **配置文件未找到**: config.json 必须在项目根目录
- **数据源失败**: 检查网络、token配置、依赖库安装
- 详见 [test/README.md](test/README.md)

### 代码规范

**适配器开发规则:**
- 必须继承 `DataSourceAdapter` 基类
- 实现所有抽象方法（connect, disconnect, get_kline, get_valuation, get_tick, health_check）
- 统一返回 DataFrame，列名为: date, open, high, low, close, volume, amount
- 所有复权数据必须是前复权（adjust='qfq'）
- 错误处理：捕获异常并记录到 `self.last_error`，增加 `self.error_count`

**配置管理规则:**
- 所有新功能的参数必须在 config.json 中定义
- 使用 `config.get('section.key', default_value)` 读取配置
- 不要硬编码任何超时时间、重试次数、阈值等参数

**日志规范:**
- 使用 `self.logger` 记录日志（每个适配器/管理器都有独立的 logger）
- INFO: 正常操作流程（连接成功、数据获取成功、缓存命中）
- WARNING: 可恢复的错误（单次请求失败但会重试、数据源切换）
- ERROR: 严重错误（所有数据源失败、缓存损坏、配置错误）
- **编码规范**: 日志文件必须使用 UTF-8 编码，避免中文乱码
  ```python
  # ✅ 正确：显式指定UTF-8编码
  handler = logging.FileHandler('app.log', encoding='utf-8')

  # ❌ 错误：依赖系统默认编码
  handler = logging.FileHandler('app.log')
  ```

## 常见任务

### 添加新数据源

1. 在 adapters/ 创建 `新源名_adapter.py`
2. 继承 `DataSourceAdapter` 并实现所有抽象方法
3. 在 `adapters/__init__.py` 的 `AdapterFactory` 中注册
4. 在 config.json 的 `data_sources` 中添加配置
5. 编写对应的单元测试

### 修改缓存策略

编辑 [cache/cache_manager.py](cache/cache_manager.py)：
- `max_days_per_stock`: 单只股票最多缓存天数
- `_validate_data()`: 双源校验逻辑
- `_should_update_cache()`: 缓存更新时机判断

### 调整健康检测参数

编辑 config.json 的 `health_check` 部分：
- `interval_seconds`: 检测间隔
- `response_time_threshold`: 响应时间阈值（秒）
- `consecutive_failures_threshold`: 连续失败次数阈值

### 调试数据源问题

1. 检查日志: `logs/data_master.log`
2. 查看健康状态: `master.get_health_status()`
3. 查看缓存统计: `master.get_cache_statistics()`
4. 手动切换数据源测试: `master.force_switch_source('kline', 'baostock')`

## 重要注意事项

1. **Tushare Token**: 必须在 config.json 中配置有效的 token（当前配置的 token 可能已过期）
2. **xtquant 依赖**: 需要本地运行 QMT 客户端，否则会自动禁用
3. **内置库路径**: 如果使用内置库模式，lib/ 目录必须包含完整的依赖库
4. **缓存数据库**: cache.db 路径必须可写，首次运行会自动创建
5. **前复权约束**: 所有适配器必须返回前复权数据，后复权和不复权的数据源应排除
6. **日期格式**: 统一使用 'YYYY-MM-DD' 格式，DataFrame 的 date 列应为字符串或 datetime
7. **股票代码格式**: 支持 '600519' 和 'sh.600519' 两种格式，内部会自动转换

## 测试环境配置

使用 Anaconda 环境 `C:\Users\PC\Anaconda3\envs\python38` 进行测试：
- 所有测试代码放在 test/ 目录
- 测试前确保 config.json 配置正确
- 测试后清理生成的临时文件和测试数据库

## 文档管理

生成的 Markdown 文档统一放在 docs/ 目录：
- 文档命名应有逻辑且易识别
- 包括 API 文档、架构图、迁移指南等

## 已知限制

- Mootdx: 分钟线数据最多获取800条，复权数据存在已知 bug（仅用于分钟线）
- Tushare: 分钟线数据最多8000条，需要权限点数
- Baostock: 免费但速度较慢，适合作为备用数据源
- xtquant: 依赖 QMT 客户端运行状态，仅用于实时 tick 数据
