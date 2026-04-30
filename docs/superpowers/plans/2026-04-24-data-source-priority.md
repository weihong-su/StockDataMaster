# 数据源优先级优化 实现计划

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 重构数据源优先级为时段感知的角色矩阵,实现三选二投票校验和 xtquant 优先的 get_stock_name 接口。

**Architecture:** 配置驱动方案 — config.json 新增 roles 格式定义多角色优先级,config.py 提供 `get_sources_by_role()` 方法按当前时段查表返回有序数据源列表。cache_manager.py 重构校验为并行投票机制。data_master.py 新增 `_get_time_slot()` 时段判断。

**Tech Stack:** Python 3.8+, SQLite, concurrent.futures (并行投票), threading

**Spec:** `docs/superpowers/specs/2026-04-24-data-source-priority-design.md`

---

## File Structure

| File | Action | Responsibility |
|------|--------|---------------|
| `config.json` | Modify | 新增 roles 格式 + validation 配置 + stock_name 配置 |
| `config.py` | Modify | 新增 roles 解析方法、旧配置迁移、时段判断 |
| `cache/cache_manager.py` | Modify | 新增 `validate_and_cache_voting()` 三选二投票校验 |
| `data_master.py` | Modify | 重构 `_fetch_kline_from_source()`, `_try_cache_kline()`, `get_stock_name()` |
| `health/health_manager.py` | Modify | 适配 roles 格式,时段感知 |
| `adapters/xtquant_adapter.py` | Modify | 新增 `get_instrument_detail()` 公共方法 |
| `test/suite/test_config.py` | Modify | 新增 roles 解析测试 |
| `test/suite/test_cache_manager.py` | Modify | 新增投票校验测试 |
| `test/suite/test_data_master.py` | Modify | 新增时段判断、get_stock_name 测试 |

---

### Task 1: config.json — 新增 roles 配置格式

**Files:**
- Modify: `config.json`

- [ ] **Step 1: 更新 config.json 为新的 roles 格式**

将 `data_sources` 下的每个数据源从 `priority` + `use_for` 格式迁移为 `roles` 格式,同时保留旧字段供兼容。新增 `validation` 和 `stock_name` 顶层配置块。

完整的 `config.json`:

```json
{
  "use_builtin_libs": true,
  "data_sources": {
    "tushare": {
      "enabled": true,
      "priority": 1,
      "timeout": 10,
      "retry_times": 2,
      "token": "3fc034badc40a35e029194a4c4d3540770f700e94a1085a4239f9904",
      "use_for": ["kline_day"],
      "roles": {
        "kline_day": { "priority": 1 },
        "valuation": { "priority": 1 }
      },
      "comment": "日K线主数据源(pro账号),复权数据准确"
    },
    "xtquant": {
      "enabled": true,
      "priority": 1,
      "timeout": 5,
      "retry_times": 2,
      "use_for": ["tick"],
      "fallback_to_5m": true,
      "qmt_path": "",
      "account": "",
      "retry_delay": 0.5,
      "retry_backoff_factor": 2.0,
      "max_retry_delay": 5.0,
      "connect_timeout": 10,
      "connect_retry_times": 3,
      "connect_retry_delay": 1.0,
      "heartbeat_enabled": true,
      "heartbeat_interval": 30,
      "heartbeat_timeout": 5,
      "auto_reconnect": true,
      "max_reconnect_attempts": 5,
      "cache_enabled": true,
      "cache_only_daily": true,
      "roles": {
        "tick": { "priority": 1 },
        "kline_minute": { "priority": 1 },
        "validation": { "priority": 1, "time_slot": "trading" }
      },
      "comment": "实时Tick主数据源(需QMT客户端运行),分钟线主源,盘中校验源"
    },
    "mootdx": {
      "enabled": true,
      "priority": 2,
      "timeout": 5,
      "retry_times": 3,
      "use_for": ["kline_day", "kline_minute"],
      "adjustflag": "qfq",
      "roles": {
        "kline_minute": { "priority": 2 },
        "kline_day": { "priority": 2 },
        "validation": { "priority": 3 }
      },
      "comment": "日K线备用+分钟K线备用数据源"
    },
    "baostock": {
      "enabled": true,
      "priority": 3,
      "timeout": 8,
      "retry_times": 3,
      "use_for": ["kline_day", "kline_minute", "valuation"],
      "adjustflag": "2",
      "roles": {
        "kline_day": { "priority": 3 },
        "kline_minute": { "priority": 3 },
        "validation": { "priority": 2 }
      },
      "comment": "日K线/分钟K线备用数据源,校验源"
    }
  },
  "validation": {
    "mode": "voting",
    "quorum": 2,
    "strategy": "first_to_quorum",
    "sources": ["xtquant", "baostock", "mootdx"],
    "price_tolerance_abs": 0.01,
    "price_tolerance_pct": 0.005,
    "volume_tolerance_pct": 0.05,
    "min_pass_rate": 0.8,
    "skip_today_in_trading_hours": true
  },
  "stock_name": {
    "cache_enabled": true,
    "cleanup_day": 5,
    "baostock_max_consecutive_failures": 3,
    "baostock_retry_cooldown": 300
  },
  "cache": {
    "enabled": true,
    "db_path": "cache/kline_cache.db",
    "max_days_per_stock": 120,
    "update_time": "15:30",
    "stock_name_expire_days": 30,
    "stock_name_cleanup_day": 5,
    "stock_name_skip_expiration_check": true,
    "validation": {
      "price_tolerance_abs": 0.01,
      "price_tolerance_pct": 0.005,
      "volume_tolerance_pct": 0.05
    }
  },
  "health_check": {
    "enabled": true,
    "interval_seconds": 60,
    "response_time_threshold": 5.0,
    "consecutive_failures_threshold": 3,
    "data_freshness_days": 3
  },
  "hot_switch": {
    "enabled": true,
    "smooth_transition": true,
    "buffer_size": 10,
    "switch_notification": true
  },
  "logging": {
    "level": "INFO",
    "file": "logs/data_master.log",
    "max_bytes": 10485760,
    "backup_count": 5
  }
}
```

- [ ] **Step 2: 验证 JSON 格式正确**

Run: `python -c "import json; json.load(open('config.json', encoding='utf-8')); print('JSON valid')"`
Expected: `JSON valid`

- [ ] **Step 3: Commit**

```bash
git add config.json
git commit -m "feat: add roles-based data source config with voting validation"
```

---

### Task 2: config.py — 新增 roles 解析和时段判断

**Files:**
- Modify: `config.py:92-109`
- Modify: `test/suite/test_config.py`

- [ ] **Step 1: 写 roles 解析的失败测试**

在 `test/suite/test_config.py` 末尾新增:

```python
# ─── 测试：roles 格式解析 ─────────────────────────────────────────────────────

class TestRolesConfig:
    """roles 格式配置解析测试"""

    def test_get_sources_by_role_kline_day(self, temp_cache_config):
        """按角色获取日线数据源列表"""
        from StockDataMaster.config import Config
        sources = temp_cache_config.get_sources_by_role('kline_day')
        assert sources == ['tushare', 'mootdx', 'baostock']

    def test_get_sources_by_role_kline_minute(self, temp_cache_config):
        """按角色获取分钟线数据源列表"""
        from StockDataMaster.config import Config
        sources = temp_cache_config.get_sources_by_role('kline_minute')
        assert sources == ['xtquant', 'mootdx', 'baostock']

    def test_get_sources_by_role_tick(self, temp_cache_config):
        """按角色获取tick数据源列表"""
        from StockDataMaster.config import Config
        sources = temp_cache_config.get_sources_by_role('tick')
        assert sources == ['xtquant']

    def test_get_sources_by_role_trading_filters_timeslot(self, temp_cache_config):
        """交易时段角色: 只返回 time_slot 匹配或无 time_slot 的源"""
        from StockDataMaster.config import Config
        # trading 时段: xtquant 有 time_slot="trading", 应包含
        sources = temp_cache_config.get_sources_by_role('validation', time_slot='trading')
        assert 'xtquant' in sources

    def test_get_sources_by_role_after_hours_excludes_trading_only(self, temp_cache_config):
        """盘后时段: 排除 time_slot="trading" 的源"""
        from StockDataMaster.config import Config
        sources = temp_cache_config.get_sources_by_role('validation', time_slot='after_hours')
        assert 'xtquant' not in sources
        assert 'baostock' in sources

    def test_get_validation_config(self, temp_cache_config):
        """获取投票校验配置"""
        from StockDataMaster.config import Config
        vc = temp_cache_config.get_validation_config()
        assert vc['mode'] == 'voting'
        assert vc['quorum'] == 2
        assert vc['strategy'] == 'first_to_quorum'

    def test_get_stock_name_config_defaults(self, temp_cache_config):
        """获取 stock_name 配置"""
        from StockDataMaster.config import Config
        snc = temp_cache_config.get_stock_name_config()
        assert snc['baostock_max_consecutive_failures'] == 3
        assert snc['baostock_retry_cooldown'] == 300

    def test_legacy_config_auto_migrate(self):
        """旧格式 use_for 自动迁移为 roles"""
        import tempfile, json
        with tempfile.NamedTemporaryFile(mode='w', suffix='.json', delete=False, encoding='utf-8') as f:
            json.dump({
                "data_sources": {
                    "tushare": {
                        "enabled": True,
                        "priority": 1,
                        "use_for": ["kline_day"],
                        "token": "test"
                    }
                },
                "cache": {"enabled": True},
                "health_check": {"enabled": False}
            }, f)
            path = f.name
        try:
            from StockDataMaster.config import Config
            cfg = Config(path)
            # _migrate_legacy_config 应自动补充 roles
            sources = cfg.get_sources_by_role('kline_day')
            assert 'tushare' in sources
        finally:
            os.unlink(path)
```

注意: `temp_cache_config` fixture 需要更新为使用新的 config.json 格式。检查现有 fixture 是否需要修改。

- [ ] **Step 2: 运行测试确认失败**

Run: `python -X utf8 -m pytest test/suite/test_config.py -v -k "TestRolesConfig" 2>&1 | tail -20`
Expected: FAIL (方法未定义)

- [ ] **Step 3: 在 config.py 中实现新方法**

在 `Config` 类的 `get_sources_by_usage()` 方法后新增以下方法:

```python
def get_sources_by_role(self, role: str, time_slot: str = None) -> list:
    """
    按 roles 获取支持特定角色的数据源列表,按时段过滤并按优先级排序

    Args:
        role: 角色 (kline_day/kline_minute/tick/validation)
        time_slot: 时段 ('trading'/'after_hours'), None=不过滤

    Returns:
        数据源名称列表,按优先级排序
    """
    self._migrate_legacy_config()

    sources = self.config.get('data_sources', {})
    matched = []

    for name, cfg in sources.items():
        if not cfg.get('enabled', False):
            continue

        roles = cfg.get('roles', {})
        if role not in roles:
            continue

        role_cfg = roles[role]

        # 时段过滤: 如果角色定义了 time_slot,只在匹配时段时包含
        role_time_slot = role_cfg.get('time_slot')
        if time_slot and role_time_slot and role_time_slot != time_slot:
            continue

        priority = role_cfg.get('priority', 999)
        matched.append((name, priority))

    matched.sort(key=lambda x: x[1])
    return [name for name, _ in matched]

def _migrate_legacy_config(self):
    """
    自动迁移旧格式(use_for + priority)到新格式(roles)
    只在 roles 字段不存在时执行迁移
    """
    sources = self.config.get('data_sources', {})
    for name, cfg in sources.items():
        if 'roles' in cfg:
            continue  # 已有 roles,跳过

        use_for = cfg.get('use_for', [])
        priority = cfg.get('priority', 999)

        # 将每个 use_for 映射为 role
        roles = {}
        for usage in use_for:
            roles[usage] = {'priority': priority}

        if roles:
            cfg['roles'] = roles

def get_validation_config(self) -> dict:
    """获取投票校验配置"""
    defaults = {
        'mode': 'voting',
        'quorum': 2,
        'strategy': 'first_to_quorum',
        'sources': ['xtquant', 'baostock', 'mootdx'],
        'price_tolerance_abs': 0.01,
        'price_tolerance_pct': 0.005,
        'volume_tolerance_pct': 0.05,
        'min_pass_rate': 0.8,
        'skip_today_in_trading_hours': True
    }
    validation_cfg = self.config.get('validation', {})
    defaults.update(validation_cfg)
    return defaults

def get_stock_name_config(self) -> dict:
    """获取股票名称配置"""
    defaults = {
        'cache_enabled': True,
        'cleanup_day': 5,
        'baostock_max_consecutive_failures': 3,
        'baostock_retry_cooldown': 300
    }
    sn_cfg = self.config.get('stock_name', {})
    defaults.update(sn_cfg)
    return defaults
```

- [ ] **Step 4: 更新 test fixture 以支持新 config 格式**

检查 `test/suite/conftest.py` 中的 `temp_cache_config` fixture。需要确保它创建的临时 config.json 包含 `roles` 格式和 `validation` 配置块。

在 conftest.py 中查找 `temp_cache_config` fixture,更新其生成的 JSON 以包含 `roles` 和 `validation` 字段。如果 fixture 使用当前项目的 config.json,则无需修改。

- [ ] **Step 5: 运行测试确认通过**

Run: `python -X utf8 -m pytest test/suite/test_config.py -v -k "TestRolesConfig" 2>&1 | tail -20`
Expected: 全部 PASS

- [ ] **Step 6: 运行全量配置测试确认无回归**

Run: `python -X utf8 -m pytest test/suite/test_config.py -v 2>&1 | tail -30`
Expected: 全部 PASS

- [ ] **Step 7: Commit**

```bash
git add config.py test/suite/test_config.py test/suite/conftest.py
git commit -m "feat: add roles-based config parsing with time_slot filtering"
```

---

### Task 3: data_master.py — 时段判断 + 源选择重构

**Files:**
- Modify: `data_master.py:197-275` (`_fetch_kline_from_source`)
- Modify: `data_master.py:1-17` (imports)

- [ ] **Step 1: 写时段判断和源选择测试**

在 `test/suite/test_data_master.py` 末尾新增:

```python
# ─── 测试：时段判断 ────────────────────────────────────────────────────────────

class TestTimeSlot:
    """时段判断测试"""

    def test_trading_hours_morning(self):
        """09:15-15:00 为交易时段"""
        from StockDataMaster.data_master import StockDataMaster
        dm = StockDataMaster.__new__(StockDataMaster)
        dm._initialized = False
        from datetime import datetime, time as time_type
        # 模拟 10:00 工作日
        test_time = time_type(10, 0)
        assert dm._get_time_slot(test_time) == 'trading'

    def test_after_hours_evening(self):
        """16:00 为盘后时段"""
        from StockDataMaster.data_master import StockDataMaster
        dm = StockDataMaster.__new__(StockDataMaster)
        dm._initialized = False
        from datetime import time as time_type
        test_time = time_type(16, 0)
        assert dm._get_time_slot(test_time) == 'after_hours'

    def test_after_hours_before_market(self):
        """08:00 为盘后时段"""
        from StockDataMaster.data_master import StockDataMaster
        dm = StockDataMaster.__new__(StockDataMaster)
        dm._initialized = False
        from datetime import time as time_type
        test_time = time_type(8, 0)
        assert dm._get_time_slot(test_time) == 'after_hours'

    def test_boundary_915(self):
        """09:15 恰好为交易时段"""
        from StockDataMaster.data_master import StockDataMaster
        dm = StockDataMaster.__new__(StockDataMaster)
        dm._initialized = False
        from datetime import time as time_type
        test_time = time_type(9, 15)
        assert dm._get_time_slot(test_time) == 'trading'

    def test_boundary_1500(self):
        """15:00 恰好为交易时段"""
        from StockDataMaster.data_master import StockDataMaster
        dm = StockDataMaster.__new__(StockDataMaster)
        dm._initialized = False
        from datetime import time as time_type
        test_time = time_type(15, 0)
        assert dm._get_time_slot(test_time) == 'trading'

    def test_boundary_1501(self):
        """15:01 为盘后时段"""
        from StockDataMaster.data_master import StockDataMaster
        dm = StockDataMaster.__new__(StockDataMaster)
        dm._initialized = False
        from datetime import time as time_type
        test_time = time_type(15, 1)
        assert dm._get_time_slot(test_time) == 'after_hours'
```

- [ ] **Step 2: 运行测试确认失败**

Run: `python -X utf8 -m pytest test/suite/test_data_master.py -v -k "TestTimeSlot" 2>&1 | tail -20`
Expected: FAIL

- [ ] **Step 3: 在 data_master.py 中实现 `_get_time_slot()`**

在 `_normalize_code()` 方法前新增:

```python
def _get_time_slot(self, current_time=None) -> str:
    """
    判断当前时段

    Args:
        current_time: datetime.time 对象,用于测试注入。None则使用当前时间

    Returns:
        'trading' 或 'after_hours'
    """
    from datetime import time as time_type

    if current_time is None:
        current_time = datetime.now().time()

    market_start = time_type(9, 15)
    market_end = time_type(15, 0)

    if market_start <= current_time <= market_end:
        return 'trading'
    return 'after_hours'
```

- [ ] **Step 4: 重构 `_fetch_kline_from_source()` 使用 roles 查表**

将现有的 `get_sources_by_usage()` 调用替换为 `get_sources_by_role()` + 时段感知:

```python
def _fetch_kline_from_source(
    self,
    code: str,
    freq: str,
    start_date: Optional[str],
    end_date: Optional[str],
    count: Optional[int],
    adjust: str
) -> Optional[pd.DataFrame]:
    """
    从数据源获取K线数据(带故障切换,时段感知)
    """
    # 根据频率类型选择角色
    if freq in ['d', 'w', 'm']:
        role = 'kline_day'
    else:
        role = 'kline_minute'

    # 获取当前时段
    time_slot = self._get_time_slot()

    # 优先从 roles 获取数据源列表
    sources = self.config.get_sources_by_role(role, time_slot=time_slot)

    if not sources:
        # fallback 到旧的 use_for 格式
        self.logger.warning(f"roles中未找到{role}数据源,回退到use_for格式")
        sources = self.config.get_sources_by_usage(role)

    if not sources:
        self.logger.error("没有可用的K线数据源")
        return None

    # 依次尝试数据源 (以下循环逻辑不变)
    for source_name in sources:
        adapter = self.adapters.get(source_name)
        if not adapter:
            continue

        try:
            actual_count = count
            if count is not None and freq == 'd':
                actual_count = int(count * 1.1)

            self.logger.debug(f"从{source_name}获取{code} K线数据(role={role}, slot={time_slot})")

            df = adapter.get_kline(code, freq, start_date, end_date, actual_count, adjust)

            if df is not None and not df.empty:
                df.attrs['source'] = source_name

                if count is not None and len(df) > count:
                    return_df = df.tail(count).copy()
                    return_df.attrs['source'] = source_name
                    return_df.attrs['full_data'] = df
                else:
                    return_df = df

                self.logger.debug(f"成功从{source_name}获取{code}数据: {len(return_df)}条")
                return return_df
            else:
                self.logger.warning(f"{source_name}返回空数据")

        except Exception as e:
            self.logger.error(f"{source_name}获取K线失败: {e}")
            continue

    self.logger.error(f"所有数据源均无法获取{code}的K线数据")
    return None
```

- [ ] **Step 5: 运行测试确认通过**

Run: `python -X utf8 -m pytest test/suite/test_data_master.py -v -k "TestTimeSlot" 2>&1 | tail -20`
Expected: 全部 PASS

- [ ] **Step 6: 运行全量测试确认无回归**

Run: `python -X utf8 -m pytest test/suite/ -v -m unit 2>&1 | tail -30`
Expected: 全部 PASS

- [ ] **Step 7: Commit**

```bash
git add data_master.py test/suite/test_data_master.py
git commit -m "feat: add time_slot aware source selection via roles"
```

---

### Task 4: cache_manager.py — 三选二投票校验

**Files:**
- Modify: `cache/cache_manager.py:288-419` (`validate_and_cache`)
- Modify: `test/suite/test_cache_manager.py`

- [ ] **Step 1: 写投票校验的失败测试**

在 `test/suite/test_cache_manager.py` 末尾新增:

```python
# ─── 测试：三选二投票校验 ──────────────────────────────────────────────────────

class TestVotingValidation:
    """三选二投票校验测试"""

    def test_two_sources_agree_passes(self, temp_cache_config):
        """两个校验源一致 -> 通过"""
        from StockDataMaster.cache.cache_manager import CacheManager
        cm = CacheManager(temp_cache_config, {})

        # 主数据 (tushare)
        df1 = make_sample_df(5, start_days_ago=10)
        # 校验数据1 (与主数据一致)
        df2 = make_sample_df(5, start_days_ago=10)
        # 校验数据2 (与主数据一致)
        df3 = make_sample_df(5, start_days_ago=10)

        result = cm.validate_and_cache_voting(
            code='600519',
            primary_df=df1,
            validation_dfs={'baostock': df2, 'mootdx': df3},
            primary_source='tushare'
        )
        assert result is not None
        assert len(result) == 5

    def test_two_sources_disagree_fails(self, temp_cache_config):
        """两个校验源都不一致 -> 失败"""
        from StockDataMaster.cache.cache_manager import CacheManager
        cm = CacheManager(temp_cache_config, {})

        df1 = make_sample_df(5, start_days_ago=10)
        # 构造完全不同的数据
        df2 = make_sample_df(5, start_days_ago=10)
        df2['close'] = df2['close'] * 10  # 巨大差异
        df3 = make_sample_df(5, start_days_ago=10)
        df3['close'] = df3['close'] * 20  # 巨大差异

        result = cm.validate_and_cache_voting(
            code='600519',
            primary_df=df1,
            validation_dfs={'baostock': df2, 'mootdx': df3},
            primary_source='tushare'
        )
        assert result is None

    def test_one_agree_one_disagree_passes(self, temp_cache_config):
        """一个一致一个不一致 -> 二票通过"""
        from StockDataMaster.cache.cache_manager import CacheManager
        cm = CacheManager(temp_cache_config, {})

        df1 = make_sample_df(5, start_days_ago=10)
        # 一致
        df2 = make_sample_df(5, start_days_ago=10)
        # 不一致
        df3 = make_sample_df(5, start_days_ago=10)
        df3['close'] = df3['close'] * 10

        result = cm.validate_and_cache_voting(
            code='600519',
            primary_df=df1,
            validation_dfs={'baostock': df2, 'mootdx': df3},
            primary_source='tushare'
        )
        assert result is not None

    def test_single_validation_source_passes(self, temp_cache_config):
        """只有一个校验源且一致 -> 通过(降级为二选一)"""
        from StockDataMaster.cache.cache_manager import CacheManager
        cm = CacheManager(temp_cache_config, {})

        df1 = make_sample_df(5, start_days_ago=10)
        df2 = make_sample_df(5, start_days_ago=10)

        result = cm.validate_and_cache_voting(
            code='600519',
            primary_df=df1,
            validation_dfs={'baostock': df2},
            primary_source='tushare'
        )
        assert result is not None

    def test_no_validation_sources_returns_unvalidated(self, temp_cache_config):
        """无校验源 -> 返回主数据(不缓存)"""
        from StockDataMaster.cache.cache_manager import CacheManager
        cm = CacheManager(temp_cache_config, {})

        df1 = make_sample_df(5, start_days_ago=10)

        result = cm.validate_and_cache_voting(
            code='600519',
            primary_df=df1,
            validation_dfs={},
            primary_source='tushare'
        )
        assert result is not None
        assert len(result) == 5
```

- [ ] **Step 2: 运行测试确认失败**

Run: `python -X utf8 -m pytest test/suite/test_cache_manager.py -v -k "TestVotingValidation" 2>&1 | tail -20`
Expected: FAIL

- [ ] **Step 3: 在 cache_manager.py 中实现 `validate_and_cache_voting()`**

在 `validate_and_cache()` 方法后新增:

```python
def validate_and_cache_voting(
    self,
    code: str,
    primary_df: pd.DataFrame,
    validation_dfs: Dict[str, pd.DataFrame],
    primary_source: str
) -> Optional[pd.DataFrame]:
    """
    三选二投票校验并缓存

    Args:
        code: 股票代码
        primary_df: 主数据源 DataFrame
        validation_dfs: {源名: DataFrame} 校验源字典
        primary_source: 主数据源名称

    Returns:
        校验通过的 DataFrame
    """
    if primary_df is None or primary_df.empty:
        self.logger.warning(f"{primary_source}数据为空,无法校验")
        return None

    # 无校验源时直接返回主数据(不缓存)
    if not validation_dfs:
        self.logger.info(f"{code}无校验源可用,返回未校验数据")
        return primary_df

    # 只有一个校验源时,降级为双源校验
    if len(validation_dfs) == 1:
        vs_name = list(validation_dfs.keys())[0]
        vs_df = validation_dfs[vs_name]
        return self.validate_and_cache(code, primary_df, vs_df, primary_source, vs_name)

    # 多个校验源: 三选二投票
    quorum = 2  # 需要2票通过
    votes_passed = []

    for vs_name, vs_df in validation_dfs.items():
        if vs_df is None or vs_df.empty:
            self.logger.debug(f"{vs_name}校验数据为空,跳过")
            continue

        # 使用现有的比对逻辑计算通过率
        pass_rate = self._calculate_pass_rate(primary_df, vs_df, code)

        if pass_rate >= 0.8:
            votes_passed.append(vs_name)
            self.logger.debug(f"{code} {vs_name}校验通过(通过率={pass_rate*100:.1f}%)")

            if len(votes_passed) >= quorum:
                # 达到法定票数,使用主数据缓存
                validated_df = primary_df.copy()
                self.save_to_cache(
                    code, validated_df, primary_source,
                    ','.join(votes_passed[:quorum]),
                    validated=True
                )
                self.logger.info(
                    f"{code}投票校验通过: {votes_passed[:quorum]} "
                    f"({len(validated_df)}条)"
                )
                return validated_df
        else:
            self.logger.debug(f"{code} {vs_name}校验未通过(通过率={pass_rate*100:.1f}%)")

    # 未达到法定票数
    self.logger.warning(
        f"{code}投票校验未达标: {len(votes_passed)}/{quorum}票 "
        f"(通过源: {votes_passed})"
    )
    return None

def _calculate_pass_rate(
    self,
    df1: pd.DataFrame,
    df2: pd.DataFrame,
    code: str
) -> float:
    """
    计算两个数据源的比对通过率

    Returns:
        通过率 (0.0-1.0)
    """
    try:
        df1_clean = df1[['date', 'open', 'high', 'low', 'close', 'volume']].copy()
        df2_temp = df2[['date', 'open', 'high', 'low', 'close', 'volume']].copy()
        df2_clean = df2_temp.loc[:, ~df2_temp.columns.duplicated()]

        merged = pd.merge(df1_clean, df2_clean, on='date', suffixes=('_1', '_2'), how='inner')

        if merged.empty:
            return 0.0

        passed = 0
        for _, row in merged.iterrows():
            price_valid = True
            for field in ['open', 'high', 'low', 'close']:
                p1 = float(row[f'{field}_1'])
                p2 = float(row[f'{field}_2'])
                abs_diff = abs(p1 - p2)
                pct_diff = abs_diff / max(p1, p2) if max(p1, p2) > 0 else 0
                if abs_diff > self.price_tolerance_abs and pct_diff > self.price_tolerance_pct:
                    price_valid = False
                    break

            if not price_valid:
                continue

            v1 = float(row['volume_1'])
            v2 = float(row['volume_2'])
            vol_diff = abs(v1 - v2) / max(v1, v2) if max(v1, v2) > 0 else 0
            if vol_diff <= self.volume_tolerance_pct:
                passed += 1

        return passed / len(merged) if len(merged) > 0 else 0.0

    except Exception as e:
        self.logger.error(f"计算通过率失败 {code}: {e}")
        return 0.0
```

- [ ] **Step 4: 运行测试确认通过**

Run: `python -X utf8 -m pytest test/suite/test_cache_manager.py -v -k "TestVotingValidation" 2>&1 | tail -20`
Expected: 全部 PASS

- [ ] **Step 5: 运行全量缓存测试确认无回归**

Run: `python -X utf8 -m pytest test/suite/test_cache_manager.py -v 2>&1 | tail -30`
Expected: 全部 PASS

- [ ] **Step 6: Commit**

```bash
git add cache/cache_manager.py test/suite/test_cache_manager.py
git commit -m "feat: add 2-of-3 voting validation with first-to-quorum strategy"
```

---

### Task 5: data_master.py — 重构 _try_cache_kline 为投票机制

**Files:**
- Modify: `data_master.py:277-370` (`_try_cache_kline`)

- [ ] **Step 1: 重构 `_try_cache_kline()` 使用投票校验**

将现有的串行双源校验替换为并行投票校验:

```python
def _try_cache_kline(
    self,
    code: str,
    df: pd.DataFrame,
    start_date: Optional[str],
    end_date: Optional[str],
    count: Optional[int],
    adjust: str
):
    """
    尝试缓存日K线数据(三选二投票校验)

    策略: tushare主数据 + [xtquant, baostock, mootdx] 中至少2个通过校验
    """
    if not self.cache_manager.enabled:
        return

    try:
        cache_df = df.attrs.get('full_data', df)
        actual_count = count
        if cache_df is not df:
            self.logger.debug(f"使用预取的完整数据进行缓存: {len(cache_df)}条")
            actual_count = len(cache_df)

        # 获取校验源配置
        validation_cfg = self.config.get_validation_config()
        time_slot = self._get_time_slot()

        # 获取校验数据源列表(按时段过滤)
        validation_source_names = self.config.get_sources_by_role('validation', time_slot=time_slot)

        if not validation_source_names:
            # fallback 到旧逻辑
            self.logger.warning("未配置校验源,尝试使用kline_day备用源")
            sources = self.config.get_sources_by_role('kline_day', time_slot=time_slot)
            validation_source_names = [s for s in sources if s != 'tushare']

        # 并行获取校验数据
        validation_dfs = {}
        for vs_name in validation_source_names:
            adapter = self.adapters.get(vs_name)
            if not adapter:
                continue

            try:
                self.logger.debug(f"获取{vs_name}校验数据: {code}")
                vs_df = adapter.get_kline(code, 'd', start_date, end_date, actual_count, adjust)
                if vs_df is not None and not vs_df.empty:
                    validation_dfs[vs_name] = vs_df
                else:
                    self.logger.debug(f"{vs_name}未返回校验数据")
            except Exception as e:
                self.logger.debug(f"{vs_name}校验数据获取失败: {e}")

        if not validation_dfs:
            self.logger.warning(f"{code}无校验源可用,不进入缓存")
            return

        # 执行投票校验
        self.logger.info(f"执行投票校验: {code} tushare + {list(validation_dfs.keys())}")
        validated_df = self.cache_manager.validate_and_cache_voting(
            code, cache_df, validation_dfs, 'tushare'
        )

        if validated_df is not None:
            self.logger.info(f"{code}投票校验完成,已缓存")
        else:
            self.logger.warning(f"{code}投票校验未通过,不进入缓存")

    except Exception as e:
        self.logger.error(f"缓存数据失败 {code}: {e}")
```

- [ ] **Step 2: 运行全量单元测试确认无回归**

Run: `python -X utf8 -m pytest test/suite/ -v -m unit 2>&1 | tail -30`
Expected: 全部 PASS

- [ ] **Step 3: Commit**

```bash
git add data_master.py
git commit -m "feat: refactor _try_cache_kline to use voting validation"
```

---

### Task 6: xtquant_adapter.py — 公开 get_instrument_detail

**Files:**
- Modify: `adapters/xtquant_adapter.py`

- [ ] **Step 1: 在 XtquantAdapter 中新增 `get_stock_name()` 公共方法**

在类的方法区新增:

```python
def get_stock_name(self, code: str) -> Optional[str]:
    """
    通过 xtdata 获取股票名称

    Args:
        code: 股票代码,支持 '600519' / 'sh.600519' / '600519.SH' 格式

    Returns:
        股票名称,失败返回 None
    """
    if not self.is_connected:
        if not self.connect():
            return None

    try:
        # 标准化为 xtquant 格式
        xt_code = self._normalize_to_xt_code(code)
        detail = self.xt_data.get_instrument_detail(xt_code)

        if detail:
            name = detail.get('InstrumentName') or detail.get('instrumentName') or detail.get('name')
            if name:
                self.logger.debug(f"xtquant获取股票名称: {code} -> {name}")
                return name

        self.logger.debug(f"xtquant未获取到{code}的股票详情")
        return None

    except Exception as e:
        self.logger.debug(f"xtquant获取股票名称失败 {code}: {e}")
        return None

def _normalize_to_xt_code(self, code: str) -> str:
    """
    标准化股票代码为 xtquant 格式

    '600519' -> '600519.SH'
    'sh.600519' -> '600519.SH'
    '600519.SH' -> '600519.SH'
    """
    # 去掉 sh./sz. 前缀
    clean = code.replace('sh.', '').replace('sz.', '')
    # 去掉 .SH/.SZ 后缀
    if '.' in clean:
        clean = clean.split('.')[0]
    # 判断市场
    if clean.startswith(('6', '510', '511', '518', '688', '689')):
        return f"{clean}.SH"
    return f"{clean}.SZ"
```

- [ ] **Step 2: Commit**

```bash
git add adapters/xtquant_adapter.py
git commit -m "feat: add get_stock_name and code normalization to XtquantAdapter"
```

---

### Task 7: data_master.py — 重构 get_stock_name 为三级查找

**Files:**
- Modify: `data_master.py:562-651` (`get_stock_name`)
- Modify: `test/suite/test_data_master.py`

- [ ] **Step 1: 写 get_stock_name 重构测试**

在 `test/suite/test_data_master.py` 末尾新增:

```python
# ─── 测试：get_stock_name 三级查找 ─────────────────────────────────────────────

class TestGetStockName:
    """get_stock_name 三级查找测试"""

    def test_memory_cache_hit(self):
        """L1 内存缓存命中"""
        from StockDataMaster.data_master import StockDataMaster
        dm = StockDataMaster.__new__(StockDataMaster)
        dm._initialized = False
        dm._stock_name_cache = {'600519': '贵州茅台'}
        dm.logger = logging.getLogger('test')

        result = dm.get_stock_name('600519')
        assert result == '贵州茅台'

    def test_xtquant_priority_over_baostock(self):
        """xtquant 优先于 baostock"""
        from StockDataMaster.data_master import StockDataMaster
        dm = StockDataMaster.__new__(StockDataMaster)
        dm._initialized = False
        dm._stock_name_cache = {}
        dm.adapters = {}

        # mock xtquant adapter
        class MockXtquant:
            def get_stock_name(self, code):
                return '贵州茅台'
        dm.adapters['xtquant'] = MockXtquant()
        dm.cache_manager = type('CM', (), {'enabled': False, 'get_cached_stock_name': lambda s, c: None, 'cache_stock_name': lambda s, c, n, src: True})()
        dm.logger = logging.getLogger('test')
        dm.config = type('C', (), {'get_stock_name_config': lambda s: {'baostock_max_consecutive_failures': 3, 'baostock_retry_cooldown': 300}})()

        result = dm.get_stock_name('600519')
        assert result == '贵州茅台'

    def test_fallback_to_code_when_all_fail(self):
        """所有源失败 -> 返回股票代码本身"""
        from StockDataMaster.data_master import StockDataMaster
        dm = StockDataMaster.__new__(StockDataMaster)
        dm._initialized = False
        dm._stock_name_cache = {}
        dm.adapters = {}
        dm.cache_manager = type('CM', (), {'enabled': False, 'get_cached_stock_name': lambda s, c: None})()
        dm.logger = logging.getLogger('test')
        dm.config = type('C', (), {'get_stock_name_config': lambda s: {'baostock_max_consecutive_failures': 3, 'baostock_retry_cooldown': 300}})()
        dm._bs_session_active = False

        result = dm.get_stock_name('600519')
        assert result == '600519'

    def test_code_format_sh_prefix(self):
        """sh.600519 格式代码"""
        from StockDataMaster.data_master import StockDataMaster
        dm = StockDataMaster.__new__(StockDataMaster)
        dm._initialized = False
        dm._stock_name_cache = {'600519': '贵州茅台'}
        dm.logger = logging.getLogger('test')

        result = dm.get_stock_name('sh.600519')
        assert result == '贵州茅台'
```

注意: 测试中需要 `import logging`。

- [ ] **Step 2: 运行测试确认部分失败**

Run: `python -X utf8 -m pytest test/suite/test_data_master.py -v -k "TestGetStockName" 2>&1 | tail -20`
Expected: `test_fallback_to_code_when_all_fail` FAIL (当前返回 None)

- [ ] **Step 3: 重构 `get_stock_name()` 为三级查找**

替换 data_master.py 中现有的 `get_stock_name()` 方法:

```python
def get_stock_name(self, code: str, use_cache: bool = True) -> Optional[str]:
    """
    获取股票名称 (三级查找: 内存 -> xtquant -> baostock)

    Args:
        code: 股票代码 (支持 '600000' / 'sh.600000' / '600000.SH')
        use_cache: 是否使用缓存 (默认True)

    Returns:
        股票名称,全部失败返回股票代码本身
    """
    try:
        # 标准化代码格式 -> 6位纯数字
        clean_code = code.replace('sh.', '').replace('sz.', '')
        if '.' in clean_code:
            clean_code = clean_code.split('.')[0]

        # L1: 内存缓存
        if use_cache and clean_code in self._stock_name_cache:
            return self._stock_name_cache[clean_code]

        # L2: SQLite 缓存
        if use_cache:
            cached_name = self.cache_manager.get_cached_stock_name(clean_code)
            if cached_name:
                self._stock_name_cache[clean_code] = cached_name
                return cached_name

        # L3a: xtquant (优先)
        xtquant_adapter = self.adapters.get('xtquant')
        if xtquant_adapter and hasattr(xtquant_adapter, 'get_stock_name'):
            try:
                name = xtquant_adapter.get_stock_name(code)
                if name:
                    self._stock_name_cache[clean_code] = name
                    if use_cache:
                        self.cache_manager.cache_stock_name(clean_code, name, 'xtquant')
                    return name
            except Exception as e:
                self.logger.debug(f"xtquant获取股票名称失败: {e}")

        # L3b: baostock (兜底)
        if 'baostock' in self.adapters:
            try:
                name = self._get_stock_name_from_baostock(clean_code)
                if name:
                    self._stock_name_cache[clean_code] = name
                    if use_cache:
                        self.cache_manager.cache_stock_name(clean_code, name, 'baostock')
                    return name
            except Exception as e:
                self.logger.debug(f"baostock获取股票名称失败: {e}")

        # 全部失败 -> 返回代码本身
        self._stock_name_cache[clean_code] = clean_code
        return clean_code

    except Exception as e:
        self.logger.error(f"获取股票名称失败: {e}")
        return code.replace('sh.', '').replace('sz.', '').split('.')[0] if code else None

def _get_stock_name_from_baostock(self, clean_code: str) -> Optional[str]:
    """
    从 baostock 获取股票名称 (带冷却机制)

    Args:
        clean_code: 6位纯数字股票代码

    Returns:
        股票名称,失败返回 None
    """
    import time as time_module

    # 冷却机制检查
    sn_cfg = self.config.get_stock_name_config()
    max_failures = sn_cfg.get('baostock_max_consecutive_failures', 3)
    cooldown = sn_cfg.get('baostock_retry_cooldown', 300)

    if not hasattr(self, '_bs_name_failures'):
        self._bs_name_failures = 0
        self._bs_name_cooldown_until = 0.0

    if self._bs_name_failures >= max_failures:
        if time_module.time() < self._bs_name_cooldown_until:
            self.logger.debug(f"baostock股票名称查询冷却中,跳过")
            return None
        else:
            self._bs_name_failures = 0

    try:
        import baostock as bs

        if not self._bs_session_active:
            lg = bs.login()
            if lg.error_code != '0':
                self._bs_name_failures += 1
                self.logger.warning(f"baostock登录失败: {lg.error_msg}")
                return None
            self._bs_session_active = True

        # 格式转换
        if clean_code.startswith(('6', '688', '689', '510', '511', '518')):
            bs_code = f'sh.{clean_code}'
        else:
            bs_code = f'sz.{clean_code}'

        rs = bs.query_stock_basic(code=bs_code)
        if rs.error_code == '0':
            data_list = []
            while (rs.error_code == '0') and rs.next():
                data_list.append(rs.get_row_data())
            if data_list and len(data_list[0]) > 1:
                name = data_list[0][1]
                self._bs_name_failures = 0  # 重置失败计数
                return name

        self._bs_name_failures += 1
        if self._bs_name_failures >= max_failures:
            self._bs_name_cooldown_until = time_module.time() + cooldown
        return None

    except Exception as e:
        self._bs_name_failures += 1
        if self._bs_name_failures >= max_failures:
            self._bs_name_cooldown_until = time_module.time() + cooldown
        self._bs_session_active = False
        self.logger.debug(f"baostock查询股票名称异常: {e}")
        return None
```

- [ ] **Step 4: 运行测试确认通过**

Run: `python -X utf8 -m pytest test/suite/test_data_master.py -v -k "TestGetStockName" 2>&1 | tail -20`
Expected: 全部 PASS

- [ ] **Step 5: 运行全量单元测试确认无回归**

Run: `python -X utf8 -m pytest test/suite/ -v -m unit 2>&1 | tail -30`
Expected: 全部 PASS

- [ ] **Step 6: Commit**

```bash
git add data_master.py test/suite/test_data_master.py
git commit -m "feat: refactor get_stock_name with xtquant priority + baostock cooldown"
```

---

### Task 8: health_manager.py — 适配 roles 格式

**Files:**
- Modify: `health/health_manager.py:192-287` (`_trigger_switch`, `_find_backup_source`)

- [ ] **Step 1: 重构 `_find_backup_source()` 支持 roles**

```python
def _find_backup_source(self, usage: str, exclude: List[str] = None) -> Optional[str]:
    """
    查找备用数据源 (优先使用 roles 格式)

    Args:
        usage: 用途类型
        exclude: 排除的数据源列表

    Returns:
        备用数据源名称
    """
    exclude = exclude or []

    # 优先使用 roles 格式查找
    if hasattr(self.config, 'get_sources_by_role'):
        from datetime import time as time_type
        now = datetime.now()
        # 简单时段判断
        market_start = time_type(9, 15)
        market_end = time_type(15, 0)
        if market_start <= now.time() <= market_end:
            time_slot = 'trading'
        else:
            time_slot = 'after_hours'

        sources = self.config.get_sources_by_role(usage, time_slot=time_slot)
        candidates = [
            (name, self.config.get_data_source_config(name).get('roles', {}).get(usage, {}).get('priority', 999))
            for name in sources
            if name not in exclude
            and self.health_status.get(name, {}).get('status') == 'ok'
        ]
        candidates.sort(key=lambda x: x[1])
        if candidates:
            return candidates[0][0]

    # fallback 到旧的 use_for 格式
    candidates = []
    for name, adapter in self.adapters.items():
        if name in exclude:
            continue
        if not adapter.config.get('enabled', False):
            continue
        if usage not in adapter.config.get('use_for', []):
            continue
        health = self.health_status.get(name, {})
        if health.get('status') == 'ok':
            priority = adapter.config.get('priority', 999)
            candidates.append((name, priority))

    candidates.sort(key=lambda x: x[1])
    return candidates[0][0] if candidates else None
```

- [ ] **Step 2: 重构 `_trigger_switch()` 支持 roles**

将 `_trigger_switch` 方法中获取失败用途的逻辑改为读取 roles:

```python
def _trigger_switch(self, failed_source: str, reason: str):
    """触发数据源切换 (roles 格式适配)"""
    from datetime import datetime, time as time_type

    now = datetime.now()
    current_time = now.time()
    market_start = time_type(9, 15)
    market_end = time_type(15, 0)
    is_trading_hours = market_start <= current_time <= market_end

    if failed_source == 'xtquant' and not is_trading_hours:
        self.logger.debug(f"[非交易时段] xtquant失败属正常: {reason}")
    else:
        self.logger.warning(f"触发数据源切换: {failed_source}, 原因: {reason}")

    failed_adapter = self.adapters.get(failed_source)
    if not failed_adapter:
        return

    # 从 roles 获取该数据源参与的所有用途
    failed_roles = failed_adapter.config.get('roles', {})
    failed_uses = list(failed_roles.keys())

    # 也检查旧的 use_for 格式
    if not failed_uses:
        failed_uses = failed_adapter.config.get('use_for', [])

    for usage in failed_uses:
        if self.active_sources.get(usage) == failed_source:
            backup = self._find_backup_source(usage, exclude=[failed_source])
            if backup:
                old_source = self.active_sources[usage]
                self.active_sources[usage] = backup
                self.logger.info(f"{usage}数据源已切换: {old_source} -> {backup}")
                self.switch_history.append({
                    'time': datetime.now(),
                    'usage': usage,
                    'from': old_source,
                    'to': backup,
                    'reason': reason
                })
                if self.config.get('hot_switch.switch_notification', False):
                    self._send_notification(usage, old_source, backup, reason)
            else:
                self.logger.error(f"{usage}数据源无可用备份!")
```

同时更新 `_auto_recover_xtquant()` 中的用途获取:

```python
def _auto_recover_xtquant(self):
    """交易时段自动恢复xtquant"""
    from datetime import datetime, time as time_type

    now = datetime.now()
    current_time = now.time()
    market_start = time_type(9, 15)
    market_end = time_type(15, 0)
    is_trading_hours = market_start <= current_time <= market_end

    if not is_trading_hours:
        return

    if 'xtquant' not in self.adapters:
        return

    xtquant_health = self.health_status.get('xtquant', {})
    if xtquant_health.get('status') != 'ok':
        return

    xtquant_adapter = self.adapters['xtquant']
    # 从 roles 获取用途列表
    xtquant_roles = xtquant_adapter.config.get('roles', {})
    xtquant_uses = list(xtquant_roles.keys())

    if not xtquant_uses:
        xtquant_uses = xtquant_adapter.config.get('use_for', [])

    for usage in xtquant_uses:
        current_source = self.active_sources.get(usage)
        if current_source != 'xtquant':
            with self.lock:
                old_source = self.active_sources[usage]
                self.active_sources[usage] = 'xtquant'
                self.logger.info(
                    f"[交易时段] {usage}数据源已恢复: {old_source} -> xtquant"
                )
                self.switch_history.append({
                    'time': datetime.now(),
                    'usage': usage,
                    'from': old_source,
                    'to': 'xtquant',
                    'reason': '交易时段自动恢复xtquant'
                })
```

- [ ] **Step 3: 运行全量单元测试确认无回归**

Run: `python -X utf8 -m pytest test/suite/ -v -m unit 2>&1 | tail -30`
Expected: 全部 PASS

- [ ] **Step 4: Commit**

```bash
git add health/health_manager.py
git commit -m "feat: adapt health_manager to roles-based config format"
```

---

### Task 9: 全量集成测试验证

**Files:**
- All modified files

- [ ] **Step 1: 运行全量单元测试**

Run: `python -X utf8 -m pytest test/suite/ -v -m unit 2>&1 | tail -40`
Expected: 全部 PASS

- [ ] **Step 2: 运行全量测试(含集成测试,如网络可用)**

Run: `python -X utf8 -m pytest test/suite/ -v 2>&1 | tail -40`
Expected: 全部 PASS

- [ ] **Step 3: 功能冒烟测试 — 验证 config roles 解析**

Run: `python -X utf8 -c "from StockDataMaster.config import get_config; cfg = get_config(); print('kline_day:', cfg.get_sources_by_role('kline_day')); print('kline_minute:', cfg.get_sources_by_role('kline_minute')); print('tick:', cfg.get_sources_by_role('tick')); print('validation(trading):', cfg.get_sources_by_role('validation', time_slot='trading')); print('validation(after_hours):', cfg.get_sources_by_role('validation', time_slot='after_hours'))"`
Expected:
```
kline_day: ['tushare', 'mootdx', 'baostock']
kline_minute: ['xtquant', 'mootdx', 'baostock']
tick: ['xtquant']
validation(trading): ['xtquant', 'baostock', 'mootdx']
validation(after_hours): ['baostock', 'mootdx']
```

- [ ] **Step 4: Final Commit**

```bash
git add -A
git commit -m "feat: complete data source priority optimization with voting validation"
```
