# test/suite/__init__.py
"""
StockDataMaster pytest 测试套件包

包含 8 个测试模块，覆盖所有核心功能：
- test_config.py:         配置管理 (12 tests)
- test_base_adapter.py:   基类方法 (10 tests)
- test_cache_manager.py:  缓存逻辑 (16 tests)
- test_data_master.py:    核心逻辑 (19 tests)
- test_health_manager.py: 健康管理 (8 tests)
- test_adapters.py:       适配器单元 (10 tests)
- test_integration.py:    集成测试 (8 tests, 需要网络)
- test_edge_cases.py:     边界条件 (8 tests)
"""
