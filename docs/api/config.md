# `config` — 配置读取

所有可调参数集中在 `config.json`,通过点号路径访问:

```python
from StockDataMaster.config import get_config
cfg = get_config()
max_days = cfg.get('cache.max_days_per_stock', 120)
```

::: StockDataMaster.config
    options:
      show_root_heading: true
      heading_level: 2
