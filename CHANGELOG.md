# Changelog

All notable changes to **StockDataMaster** will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

---

## [Unreleased]

---

## [1.2.0] - 2026-04-30

### Added
- **串行短路校验机制**：校验源按响应速度排序（xtquant ~50ms 优先），第一个通过即短路，省去等待慢源（baostock 2-3s）。
- **roles 配置格式**：每个数据源通过 `roles` 字段声明承担的角色及优先级，替代旧的 `use_for` 列表，支持 `time_slot` 过滤（仅交易时段/盘后生效）。
- **股票名称四级查找链**：内存（< 0.01ms）→ Baostock（免费，含退市）→ xtquant（QMT 用户快查）→ Tushare（付费补充），完整覆盖各类账户场景。
- **`warmup_stock_names()` 接口**：从 Tushare 批量预热股票名称缓存，返回写入记录数，适合启动阶段初始化。

### Changed
- **缓存上限 120 → 520 天**（`cache.max_days_per_stock`）：支持更长回测周期，与 A 股典型缓存需求对齐。
- **xtquant 升为分钟K线首选**（`roles.kline_minute: priority 1`）：QMT 用户盘中分钟数据直接使用 xtquant，延迟更低。
- **校验源优先级调整**：Baostock 为全时段校验首选（priority 1），xtquant 作为交易时段补充（priority 2，`time_slot: trading`）。
- **数据源鲁棒性增强**：各适配器 fallback 链顺序重新梳理，任意单源故障不影响业务可用性。

### Fixed
- **Baostock 升级到 0.9.1**：服务器地址从 `www.baostock.com` 迁移至 `public-api.baostock.com`，彻底解决 TCP 10030 连接失败问题。

---

## [1.1.1] - 2026-03-04

### Fixed
- **[HIGH]** `HealthManager.get_active_source()` 传参 Bug：`_find_backup_source(usage)` 应改为 `_find_backup_source(actual_type)`。
  当传入抽象类型 `'kline'` 时，无法匹配适配器 `use_for` 中的细分类型 `'kline_day'`，导致始终返回 `None`。
  影响文件：`health/health_manager.py:315`

### Added
- **集成回归测试套件**（`test/test_regression.py`）：8 个测试套件，91 个测试用例，覆盖所有核心模块。
- **pytest 测试框架**（`test/suite/`）：将回归测试转换为标准 pytest 格式，支持按 marker 过滤执行。
  - `test_config.py`：配置管理 (12 tests)
  - `test_base_adapter.py`：适配器基类 (10 tests)
  - `test_cache_manager.py`：缓存管理 (16 tests)
  - `test_data_master.py`：核心逻辑 (19 tests)
  - `test_health_manager.py`：健康管理 (8 tests)
  - `test_adapters.py`：适配器单元 (10 tests)
  - `test_integration.py`：集成测试，需网络 (8 tests, auto-skip)
  - `test_edge_cases.py`：边界条件 (8 tests)
- **发布前强制检查脚本**（`scripts/pre_release_check.py`）：新版本发布前必须通过的质量门禁。
- **CHANGELOG.md**：规范的版本变更记录文档。
- **pytest.ini**：统一的 pytest 配置（marker 定义、过滤规则）。

### Code Review Findings
- **[MEDIUM]** Tushare `pro.daily()` 接口不支持前复权（qfq），返回未复权数据。影响历史数据准确性。
- **[LOW]** Baostock `get_kline()` 未将成交量从「手」转换为「股」，与 Tushare/Mootdx 不一致，可能触发双源校验失败。
- **[LOW]** Singleton `_instance` 无清理机制，测试环境需手动重置，测试隔离性较差。
- **[LOW]** `BaostockAdapter.disconnect()` 裸 `except: pass`，断连失败无法感知。
- **[INFO]** Tushare 和 Baostock 的 `get_tick()` 用历史 K 线模拟实时 Tick，非真实行情。

---

## [1.1.0] - 2025-11-18

### Added
- **xtquant 深度优化**（5 阶段完成）：
  - 阶段1：扩展 xtquant 核心功能，接口利用率 +133%，`get_adjust_factors` < 10ms
  - 阶段2：智能缓存集成，**833 倍性能提升**（2-3秒 → 3ms），100% 缓存命中率
  - 阶段3：智能数据源选择，时段感知准确率 100%，缓存优先策略
  - 阶段4：数据一致性保障，双源校验 100% 通过率，复权一致性误差 < 0.5%
  - 阶段5：监控和自愈机制，4 数据源无缝切换，60 秒健康检测

### Changed
- `HealthManager`：增强版时段感知切换（交易时段严格检查，非交易时段宽松）
- `HealthManager._auto_recover_xtquant()`：交易时段自动恢复 xtquant 数据源优先级

### Fixed
- `XtquantAdapter.connect()` 返回值判断修正：`connect()` 返回对象而非状态码，应检查 `is None`

---

## [1.0.0] - 2025-10-20

### Added
- **多数据源适配器架构**：Tushare（日K线主力）、Mootdx（分钟K线）、Baostock（备用+估值）、xtquant（实时Tick）
- **智能缓存系统**：SQLite + 双源校验，盘中/盘后自适应缓存策略
- **健康检测与热切换**：后台线程监控，故障自动切换，失败阈值可配置
- **统一前复权处理**：所有数据源输出标准化前复权数据
- **配置驱动设计**：通过 `config.json` 控制所有参数，无需修改代码
- **单例模式**：全局共享数据源连接和缓存状态
- **交互式测试 GUI**：`test/interactive_test_gui.py`，支持图形化数据验证

---

[Unreleased]: https://github.com/Su-M10/StockDataMaster/compare/v1.2.0...HEAD
[1.2.0]: https://github.com/Su-M10/StockDataMaster/compare/v1.1.1...v1.2.0
[1.1.1]: https://github.com/Su-M10/StockDataMaster/compare/v1.1.0...v1.1.1
[1.1.0]: https://github.com/Su-M10/StockDataMaster/compare/v1.0.0...v1.1.0
[1.0.0]: https://github.com/Su-M10/StockDataMaster/releases/tag/v1.0.0
