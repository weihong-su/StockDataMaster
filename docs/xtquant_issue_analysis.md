# xtquant 日线数据问题分析与解决方案

## 问题现象

**错误日志:**
```
17:40:46 - xtquant获取K线失败: 600276 (d) [尝试2/2] 'NoneType' object is not iterable
```

**触发场景:** 盘后时段（17:36-17:42）获取日K线数据

## 根因分析

### 1. download_history_data 返回值未检查

**当前代码 (xtquant_adapter.py:470-475):**
```python
download_result = self.xt_data.download_history_data(
    stock_code=xt_code,
    period=xt_period,
    start_time=start_date,
    end_time=end_date
)
# ❌ download_result 从未被检查
```

**问题:**
- `download_history_data()` 在盘后或数据不可用时可能返回 `None` 或空字典
- 代码直接进入 `time.sleep()` 和 `get_local_data()`，未判断下载是否成功
- 导致后续 `get_local_data()` 读取不存在的本地数据

### 2. xtquant 盘后限制

**xtquant 的已知行为:**
- **交易时段 (9:30-15:00):** 可以下载任意历史数据
- **盘后时段 (15:00-次日9:30):** 
  - tick/分钟线: ✅ 可用（当日数据）
  - 日K线: ❌ 受限（QMT客户端限制）
  - 错误表现: `download_history_data()` 返回 `None` 或抛出异常

### 3. 时间参数格式问题

**当前代码 (xtquant_adapter.py:460-461):**
```python
start_date = start_dt.strftime('%Y%m%d')  # '20240101'
end_date = end_dt.strftime('%Y%m%d')      # '20260424'
```

**xtquant 可能的要求:**
- 某些版本要求带时分秒: `'20240101000000'`
- 或者要求空字符串 `''` 表示"不限制"
- 格式不匹配时可能导致内部迭代 `None` 而报错

### 4. get_local_data 的 field_list 参数

**当前代码 (xtquant_adapter.py:483):**
```python
data = self.xt_data.get_local_data(
    field_list=[],  # ❌ 空列表可能被解释为"不获取任何字段"
    ...
)
```

**正确用法 (根据 miniQMT issue #2):**
```python
field_list=['time', 'open', 'high', 'low', 'close', 'volume']
```

## 解决方案

### 方案1: 检查 download_history_data 返回值（推荐）

```python
# 步骤1: 下载历史数据
download_result = self.xt_data.download_history_data(
    stock_code=xt_code,
    period=xt_period,
    start_time=start_date,
    end_time=end_date
)

# ✅ 检查下载结果
if download_result is None:
    self.logger.warning(f"xtquant下载失败(可能盘后限制): {code} ({freq})")
    if attempt < max_retries - 1:
        time.sleep(1)
        continue
    return None

# 如果返回dict，检查是否为空
if isinstance(download_result, dict) and not download_result:
    self.logger.warning(f"xtquant下载返回空数据: {code} ({freq})")
    if attempt < max_retries - 1:
        time.sleep(1)
        continue
    return None
```

### 方案2: 修正 field_list 参数

```python
data = self.xt_data.get_local_data(
    field_list=['time', 'open', 'high', 'low', 'close', 'volume', 'amount'],  # ✅ 明确字段
    stock_list=[xt_code],
    period=xt_period,
    start_time=start_date,
    end_time=end_date,
    count=-1,
    dividend_type='front' if adjust == 'qfq' else 'none',
    fill_data=True
)
```

### 方案3: 增加时段检查（可选）

```python
def _is_trading_hours(self) -> bool:
    """检查是否在交易时段"""
    now = datetime.now()
    if now.weekday() >= 5:  # 周末
        return False
    
    current_time = now.time()
    morning_start = time(9, 30)
    morning_end = time(11, 30)
    afternoon_start = time(13, 0)
    afternoon_end = time(15, 0)
    
    return (morning_start <= current_time <= morning_end or
            afternoon_start <= current_time <= afternoon_end)

# 在 get_kline 中使用
if freq == 'd' and not self._is_trading_hours():
    self.logger.warning(f"盘后时段xtquant日K线可能不可用: {code}")
    # 可以选择直接返回 None，或者尝试但降低期望
```

### 方案4: 使用 connect_with_retry（增强鲁棒性）

```python
# 当前 get_kline 第 423-425 行
if not self.is_connected:
    if not self.connect():  # ❌ 单次尝试
        return None

# 改为
if not self.is_connected:
    if not self._connect_with_retry():  # ✅ 带重试
        return None
```

## 完整修复代码

### 修改 xtquant_adapter.py:465-510

```python
# 重试机制
max_retries = 2
for attempt in range(max_retries):
    try:
        # 步骤1: 下载历史数据
        self.logger.debug(f"xtquant下载历史数据: {code} ({freq}) {start_date}-{end_date}")

        download_result = self.xt_data.download_history_data(
            stock_code=xt_code,
            period=xt_period,
            start_time=start_date,
            end_time=end_date
        )

        # ✅ 新增: 检查下载结果
        if download_result is None:
            self.logger.warning(
                f"xtquant下载失败(可能盘后限制或数据不可用): {code} ({freq}) [尝试{attempt+1}/{max_retries}]"
            )
            if attempt < max_retries - 1:
                time.sleep(2)
                continue
            return None

        # 步骤2: 等待下载完成
        wait_time = 3 if xt_period in ['1m', '5m'] else 2
        time.sleep(wait_time)

        # 步骤3: 读取本地数据
        # ✅ 修改: 明确指定字段列表
        data = self.xt_data.get_local_data(
            field_list=['time', 'open', 'high', 'low', 'close', 'volume', 'amount'],
            stock_list=[xt_code],
            period=xt_period,
            start_time=start_date,
            end_time=end_date,
            count=-1,
            dividend_type='front' if adjust == 'qfq' else 'none',
            fill_data=True
        )

        # 步骤4: 处理dict格式数据
        df = None
        if data is not None:
            if isinstance(data, dict):
                if xt_code in data and data[xt_code] is not None:
                    df = data[xt_code]
                else:
                    self.logger.warning(f"xtquant数据中没有{code}的数据")
            elif hasattr(data, 'empty'):
                df = data

        if df is None or df.empty:
            self.logger.warning(f"xtquant未获取到K线数据: {code} ({freq}) [尝试{attempt+1}/{max_retries}]")
            if attempt < max_retries - 1:
                time.sleep(1)
                continue
            return None

        # ... 后续处理保持不变
```

## 测试验证

### 测试1: 交易时段测试

```python
# 在交易日 10:00-14:00 运行
from StockDataMaster import StockDataMaster

dm = StockDataMaster()
df = dm.get_kline('600519', freq='d', count=100)
print(f"获取成功: {len(df)}条, 来源: {df.attrs.get('source')}")
```

**预期结果:** ✅ 成功获取，来源 `xtquant`

### 测试2: 盘后时段测试

```python
# 在盘后 17:00-20:00 运行
df = dm.get_kline('600519', freq='d', count=100)
print(f"获取成功: {len(df)}条, 来源: {df.attrs.get('source')}")
```

**预期结果:** 
- 修复前: ❌ `'NoneType' object is not iterable`
- 修复后: ⚠️ xtquant 失败，自动降级到 tushare/baostock

### 测试3: Benchmark 重跑

```bash
# 交易日 10:00-14:00 运行
python -X utf8 test/benchmark_cache_validation.py
```

**预期结果:**
- xtquant 校验源可用
- 校验通过率 > 90%
- 无 `'NoneType' object is not iterable` 错误

## 参考资料

- **miniQMT Issue #2**: https://github.com/weihong-su/miniQMT/issues/2
- **xtquant 官方文档**: https://dict.thinktrader.net
- **常见问题**: 
  - `download_history_data` 返回 `None` 表示下载失败
  - `field_list=[]` 可能导致获取空数据
  - 盘后时段日K线下载受限

## 后续优化

1. **时段感知降级**: 盘后自动跳过 xtquant 日K线，直接使用 tushare
2. **缓存预热**: 交易时段批量下载热门股票数据到本地
3. **监控告警**: xtquant 连续失败时发送告警
4. **版本兼容**: 检测 xtquant 版本，适配不同 API 行为
