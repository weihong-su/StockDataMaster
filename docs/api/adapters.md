# `adapters` — 数据源适配器

所有数据源遵循 `DataSourceAdapter` 抽象基类,由 `AdapterFactory` 按配置实例化。

## 基类 `base_adapter`

::: StockDataMaster.adapters.base_adapter
    options:
      show_root_heading: true
      heading_level: 3

## 工厂 `AdapterFactory`

::: StockDataMaster.adapters
    options:
      show_root_heading: true
      heading_level: 3
      members:
        - AdapterFactory

## Tushare 适配器

::: StockDataMaster.adapters.tushare_adapter
    options:
      show_root_heading: true
      heading_level: 3

## Mootdx 适配器

::: StockDataMaster.adapters.mootdx_adapter
    options:
      show_root_heading: true
      heading_level: 3

## Baostock 适配器

::: StockDataMaster.adapters.baostock_adapter
    options:
      show_root_heading: true
      heading_level: 3

## xtquant 适配器

::: StockDataMaster.adapters.xtquant_adapter
    options:
      show_root_heading: true
      heading_level: 3
