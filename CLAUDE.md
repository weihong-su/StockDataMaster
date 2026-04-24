# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Commands

```bash
# Run pytest test suite
python -X utf8 -m pytest test/suite/ -v

# Run a single test file
python -X utf8 -m pytest test/suite/test_cache_manager.py -v

# Run only unit tests (no network needed)
python -X utf8 -m pytest test/suite/ -v -m unit

# Run interactive test GUI
cd test && python interactive_test_gui.py

# Activate dev environment
conda activate python38

# Install dependencies
pip install pandas numpy mootdx baostock tushare
```

**Note**: `-X utf8` flag is required on Windows to avoid GBK encoding errors in test output.

## Architecture

**Pattern**: Adapter + Singleton + Config-driven

```
StockDataMaster (singleton entry point, data_master.py)
  +-- HealthManager (health/health_manager.py) - background health monitoring, auto failover
  +-- CacheManager (cache/cache_manager.py) - SQLite cache with dual-source validation
  +-- AdapterFactory (adapters/__init__.py)
       +-- TushareAdapter   - daily K-line primary source (needs token)
       +-- MootdxAdapter    - minute K-line primary source (TCP protocol)
       +-- BaostockAdapter  - backup source (free, slow)
       +-- XtquantAdapter   - real-time tick source (requires QMT client)
```

**Data flow**: User calls `get_kline()` -> check cache freshness (`_is_cache_fresh`) -> if stale, fetch from adapter -> dual-source validate -> cache -> return.

**Config**: All parameters (timeouts, retries, thresholds, source priorities) live in `config.json`. Read with `config.get('cache.max_days_per_stock', 120)` (dot-notation nested keys). Never hardcode these values.

## Critical Gotchas

1. **UTF-8 logging on Windows**: Always use `logging.FileHandler('file.log', encoding='utf-8')`. Windows defaults to GBK, which corrupts Chinese log messages.

2. **Test import path**: Tests in `test/` must add the **parent** of the StockDataMaster directory to `sys.path`, then import as `from StockDataMaster import StockDataMaster`. Test scripts follow this pattern:
   ```python
   test_dir = os.path.dirname(os.path.abspath(__file__))
   project_root = os.path.dirname(test_dir)
   parent_dir = os.path.dirname(project_root)
   sys.path.insert(0, parent_dir)
   ```

3. **Intraday cache behavior** (data_master.py `_is_cache_fresh`):
   - `end_date < today` -> always use cache (historical data never changes)
   - Cache latest date == today AND time < 15:00 -> cache stale (intraday data changing)
   - Cache latest date == today AND time >= 15:00 -> cache fresh (market closed)
   - Cache write: skip today's data during market hours (< 15:00)

4. **xtquant `connect()` check**: Use `if xtdata.connect() is None:` not `!= 0`. `connect()` returns an IPythonApiClient object on success, None on failure.

5. **xtquant data validation**: Always validate price > 0.1, volume >= 0, OHLC logic correct. Brokers may disable miniQMT without warning, returning empty data even when QMT appears running.

6. **Health check requires reconnect**: Background thread connections may be stale. Every `health_check()` must check `is_connected` and reconnect if needed (base_adapter.py).

7. **Stock code format**: Only `'600519'` (6 digits) or `'sh.600519'` (with prefix). Does NOT support `'600519.SH'` suffix format.

8. **Date format**: Only `'YYYY-MM-DD'`. No slashes or compact formats.

9. **Adjust type**: Only `'qfq'` (forward-adjusted) is supported. No `'hfq'` or `None`.

10. **Mootdx minute-line bug**: Mootdx minute K-line adjusted data is inaccurate. Daily line data from Mootdx is fine.

## Extending with a New Data Source

1. Create `adapters/newsource_adapter.py` inheriting from `DataSourceAdapter` (base_adapter.py)
2. Implement: `connect()`, `disconnect()`, `get_kline()`, `get_valuation()`, `get_tick()`
3. Register in `adapters/__init__.py` AdapterFactory.ADAPTER_MAP
4. Add config entry in `config.json` under `data_sources`
5. K-line return format: columns `date, open, high, low, close, volume, amount`; date as `'YYYY-MM-DD'` string; all prices forward-adjusted

## Test Suite

- `test/suite/` - pytest suite (discovered by pytest.ini)
  - `test_data_master.py`, `test_cache_manager.py`, `test_adapters.py`, `test_integration.py`, `test_health_manager.py`, `test_edge_cases.py`, `test_config.py`, `test_base_adapter.py`
- `test/interactive_test_gui.py` - Tkinter GUI for manual testing
- Various standalone test scripts in `test/` for specific features (cache, xtquant, etc.)
- pytest markers: `unit` (no network), `integration` (needs network), `slow`

## Built-in Libraries

The `lib/` directory contains vendored data source libraries (mootdx, baostock, tushare, tdxpy, xtquant) for portable deployment. Controlled by `use_builtin_libs` in config.json. `lib/install_libs.py` handles installation.
