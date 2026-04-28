# 数据源鲁棒性优化报告

## 一、优化目标

针对不同用户场景（付费/免费 × QMT/无QMT），优化数据源优先级配置，确保：
1. **免费用户友好**：无token用户也能获得权威数据
2. **付费用户优先**：有token用户享受最优体验
3. **鲁棒性强**：4层fallback，任何场景都有可用数据源
4. **校验可靠**：免费校验源兜底，交易时段补充

## 二、优化前后对比

### 2.1 日K线数据源优先级

| 优先级 | 优化前 | 优化后 | 变更理由 |
|--------|--------|--------|----------|
| P1 | Tushare | Tushare | 保持不变，付费用户首选 |
| P2 | Mootdx | **Baostock** | **提升**：免费兜底，复权准确 |
| P3 | Baostock | **Mootdx** | **降级**：前复权有问题，仅作应急 |
| P4 | Xtquant | Xtquant | 保持不变，QMT用户补充 |

**关键改进**：
- Baostock 从 P3 提升至 P2，作为免费用户的权威兜底
- Mootdx 从 P2 降至 P3，因前复权有已知问题

### 2.2 股票名称获取优先级

| 优先级 | 优化前 | 优化后 | 变更理由 |
|--------|--------|--------|----------|
| L1 | 内存缓存 | 内存缓存 | 保持不变 |
| L2 | Xtquant | **Baostock** | **提升**：免费无门槛，数据最全 |
| L3 | Tushare | **Xtquant** | **调整**：QMT用户快速查询 |
| L4 | Baostock | **Tushare** | **调整**：付费用户补充 |

**关键改进**：
- Baostock 从 L4 提升至 L2，作为免费用户的首选
- 包含退市股票数据，覆盖最全

### 2.3 数据校验源配置

| 项目 | 优化前 | 优化后 | 变更理由 |
|------|--------|--------|----------|
| 校验源 | `["xtquant"]` | `["baostock", "xtquant"]` | 增加免费校验源 |
| 法定人数 | 1 | 2 | 双源校验更可靠 |

**关键改进**：
- Baostock 加入校验源：免费、复权准确、无依赖
- Xtquant 保留：交易时段补充
- Mootdx 排除：前复权有已知问题

## 三、各场景实际效果

| 场景 | 日K线首选 | Tick首选 | 股票名称首选 | 校验源 |
|------|-----------|----------|--------------|--------|
| **付费+QMT** | Tushare | Xtquant | Baostock | Baostock + Xtquant |
| **付费+无QMT** | Tushare | Mootdx | Baostock | Baostock |
| **免费+QMT** | Baostock | Xtquant | Baostock | Baostock + Xtquant |
| **免费+无QMT** | Baostock | Mootdx | Baostock | Baostock |

**关键优势**：
- ✅ 所有场景都有可用数据源
- ✅ 免费用户也能获得权威数据（Baostock）
- ✅ 付费用户享受最优体验（Tushare）
- ✅ 校验源覆盖所有场景

## 四、修改文件清单

| 文件 | 修改内容 | 行数 |
|------|----------|------|
| [config.json](config.json) | 调整数据源优先级和校验配置 | L3-L90 |
| [data_master.py](data_master.py) | 调整股票名称获取顺序 | L967-1019 |
| [test/validate_robustness.py](test/validate_robustness.py) | 新增鲁棒性验证脚本 | 全新文件 |

## 五、验证结果

### 5.1 鲁棒性验证（validate_robustness.py）

```
✅ PASS  日K线优先级
✅ PASS  Tick优先级
✅ PASS  校验源配置
✅ PASS  股票名称优先级
✅ PASS  场景覆盖

总计: 5/5 通过
```

### 5.2 单元测试（pytest）

```
132 passed, 0 failed, 0 skipped (43.65s)
```

### 5.3 冒烟测试（smoke_baostock.py）

```
10/10 PASS (贵州茅台、浦发银行、平安银行等10只代表性股票)
```

## 六、配置详情

### 6.1 完整数据源配置

```json
{
  "data_sources": {
    "tushare": {
      "enabled": true,
      "priority": 1,
      "roles": {
        "kline_day": { "priority": 1 },
        "valuation": { "priority": 1 },
        "stock_name": { "priority": 2 }
      },
      "comment": "付费用户首选，数据质量最高"
    },
    "baostock": {
      "enabled": true,
      "priority": 2,
      "roles": {
        "kline_day": { "priority": 2 },
        "kline_minute": { "priority": 2 },
        "valuation": { "priority": 2 },
        "validation": { "priority": 1 },
        "stock_name": { "priority": 1 }
      },
      "comment": "免费兜底，复权准确，校验源首选，股票名称首选"
    },
    "mootdx": {
      "enabled": true,
      "priority": 3,
      "roles": {
        "kline_day": { "priority": 3 },
        "kline_minute": { "priority": 3 },
        "tick": { "priority": 2 }
      },
      "comment": "速度快但前复权有问题，仅作应急备用"
    },
    "xtquant": {
      "enabled": true,
      "priority": 1,
      "roles": {
        "tick": { "priority": 1 },
        "kline_minute": { "priority": 1 },
        "kline_day": { "priority": 4 },
        "validation": { "priority": 2, "time_slot": "trading" },
        "stock_name": { "priority": 3 }
      },
      "comment": "实时Tick首选，需QMT客户端"
    }
  },
  "validation": {
    "mode": "voting",
    "quorum": 2,
    "sources": ["baostock", "xtquant"],
    "comment": "双源校验: baostock(免费兜底) + xtquant(交易时段补充)"
  }
}
```

### 6.2 股票名称获取链（data_master.py）

```python
def get_stock_name(self, code: str) -> str:
    """
    L1: 内存缓存 dict
    L2: baostock query_stock_basic() (免费兜底，数据最全含退市股)
    L3: xtquant.get_stock_name() (QMT用户快速查询)
    L4: tushare pro.stock_basic() (付费用户补充)
    """
```

## 七、使用建议

### 7.1 免费用户

**推荐配置**：
- 启用 baostock（已默认启用）
- 启用 mootdx（已默认启用）
- 禁用 tushare（无token时自动跳过）
- 可选启用 xtquant（需QMT客户端）

**数据获取路径**：
- 日K线：baostock → mootdx
- 实时Tick：mootdx（5分钟模拟）
- 股票名称：baostock

### 7.2 付费用户

**推荐配置**：
- 启用 tushare（填写token）
- 启用 baostock（校验源）
- 启用 mootdx（应急备用）
- 可选启用 xtquant（需QMT客户端）

**数据获取路径**：
- 日K线：tushare → baostock → mootdx
- 实时Tick：xtquant（真实tick）或 mootdx（5分钟模拟）
- 股票名称：baostock → tushare

### 7.3 QMT用户

**推荐配置**：
- 启用 xtquant（实时tick首选）
- 启用 baostock（日K线兜底）
- 启用 mootdx（应急备用）
- 可选启用 tushare（付费用户）

**数据获取路径**：
- 日K线：tushare（付费）或 baostock（免费）
- 实时Tick：xtquant（真实tick）
- 股票名称：baostock

## 八、关键技术点

### 8.1 Baostock 0.9.1 升级

**问题**：旧版本 0.8.9 服务器地址 `www.baostock.com` TCP 10030 端口不可达

**解决**：升级至 0.9.1，服务器迁移至 `public-api.baostock.com`

**验证**：
```bash
pip install --upgrade baostock
# 0.8.9 -> 0.9.1
```

### 8.2 数据源角色系统

**roles 配置**：每个数据源可定义多个角色及其优先级

```json
"roles": {
  "kline_day": { "priority": 2 },
  "validation": { "priority": 1 },
  "stock_name": { "priority": 1 }
}
```

**时段过滤**：支持 `time_slot` 参数（trading/after_hours）

```json
"validation": { "priority": 2, "time_slot": "trading" }
```

### 8.3 双源校验机制

**配置**：
- `quorum: 2`：需要2个数据源达成一致
- `sources: ["baostock", "xtquant"]`：校验源列表

**逻辑**：
1. 从主数据源获取数据
2. 从校验源获取数据
3. 比较价格/成交量差异
4. 达到法定人数（quorum）则通过

## 九、后续优化建议

1. **动态权重调整**：根据数据源历史成功率动态调整优先级
2. **智能降级**：检测到数据源异常时自动降级
3. **性能监控**：记录各数据源响应时间，优化超时配置
4. **数据质量评分**：建立数据质量评分体系，自动选择最优数据源

## 十、总结

本次优化通过调整数据源优先级和校验配置，实现了：

✅ **免费用户友好**：Baostock 作为 P2，确保无token用户也能获得权威数据  
✅ **付费用户优先**：Tushare 保持 P1，付费用户享受最优体验  
✅ **鲁棒性强**：4层fallback，任何场景都有可用数据源  
✅ **校验可靠**：Baostock 免费校验，Xtquant 交易时段补充  
✅ **股票名称兜底**：Baostock 优先，覆盖退市股，无依赖  

所有验证通过（5/5 鲁棒性验证 + 132/132 单元测试 + 10/10 冒烟测试），配置已生效。
