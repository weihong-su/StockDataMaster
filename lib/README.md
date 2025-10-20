# 内置依赖库目录

本目录用于存放StockDataMaster的内置依赖库,实现开箱即用。

## 📦 内置库列表

### 核心依赖
- `mootdx/` - 通达信数据接口
- `baostock/` - Baostock数据接口
- `tushare/` - Tushare数据接口
- `pandas/` (可选) - 数据处理库

### 为什么需要内置库?

1. **开箱即用**: 用户无需pip install,复制即可使用
2. **版本锁定**: 避免系统库版本不兼容问题
3. **环境隔离**: 不污染用户的Python环境
4. **离线部署**: 支持无网络环境部署

## 🔧 如何添加内置库

### 方法1: 直接复制(推荐)

```bash
# 从系统Python环境复制库到lib目录
# 示例: 复制mootdx库

# 1. 找到系统库位置
python -c "import mootdx; print(mootdx.__file__)"
# 输出: /path/to/python/site-packages/mootdx/__init__.py

# 2. 复制整个库目录到lib/
cp -r /path/to/python/site-packages/mootdx ./lib/

# 3. 重复以上步骤复制其他库
```

### 方法2: 使用pip下载(适合批量)

```bash
# 下载库到lib目录
pip install --target=./lib mootdx baostock tushare

# 清理不需要的文件
rm -rf ./lib/*.dist-info
rm -rf ./lib/__pycache__
```

### 方法3: 使用提供的脚本

```bash
# 运行自动化脚本(将在后续提供)
python scripts/install_builtin_libs.py
```

## 📁 目录结构

```
lib/
├── README.md           # 本文档
├── mootdx/             # mootdx库文件
│   ├── __init__.py
│   ├── quotes.py
│   └── ...
├── baostock/           # baostock库文件
│   ├── __init__.py
│   ├── data/
│   └── ...
├── tushare/            # tushare库文件
│   ├── __init__.py
│   ├── pro/
│   └── ...
└── .gitignore          # Git忽略规则(库文件不提交)
```

## ⚙️ 配置使用方式

### 方式1: 配置文件(推荐)

编辑 `config.json`:

```json
{
  "use_builtin_libs": true,  // true=使用内置库, false=使用系统库
  "data_sources": {
    ...
  }
}
```

### 方式2: 代码设置

```python
from StockDataMaster import StockDataMaster

# 强制使用内置库
master = StockDataMaster(config_path='config.json')

# 或者通过配置字典
master = StockDataMaster(config={'use_builtin_libs': True})
```

## 🔄 库加载优先级

```
use_builtin_libs = true:
  1. 尝试内置库 (lib/)
  2. 失败则降级到系统库
  3. 都失败则报错

use_builtin_libs = false:
  1. 尝试系统库
  2. 失败则降级到内置库
  3. 都失败则报错
```

## ⚠️ 注意事项

1. **版本兼容**: 确保内置库版本与StockDataMaster兼容
2. **库大小**: 内置库会增加目录大小(~50-100MB)
3. **更新维护**: 定期更新内置库以获取bug修复
4. **Git管理**: 内置库文件通常不提交到Git(见.gitignore)

## 📊 推荐的库版本

| 库名 | 推荐版本 | 大小 | 必需性 |
|------|---------|------|--------|
| mootdx | 0.8.4+ | ~5MB | 必需 |
| baostock | 0.8.8+ | ~10MB | 必需 |
| tushare | 1.2.89+ | ~15MB | 推荐 |
| pandas | 1.3.5+ | ~50MB | 可选(通常系统已有) |

## 🚀 快速部署示例

### 场景1: 开发环境(使用系统库)

```json
{
  "use_builtin_libs": false
}
```

优点: 使用最新的系统库,便于调试

### 场景2: 生产环境(使用内置库)

```json
{
  "use_builtin_libs": true
}
```

优点: 版本锁定,稳定可靠

### 场景3: 离线环境(必须使用内置库)

1. 预先下载库到lib/
2. 设置 `"use_builtin_libs": true`
3. 复制整个StockDataMaster目录到目标环境

## 🛠️ 故障排查

### 问题1: 内置库加载失败

**检查**:
```python
from StockDataMaster.utils import get_lib_loader

loader = get_lib_loader()
status = loader.get_library_status()
print(status)
```

**解决**: 确保lib/目录下有对应的库文件

### 问题2: 版本冲突

**症状**: 导入错误或功能异常

**解决**: 删除lib/下的库,使用系统库 (`"use_builtin_libs": false`)

### 问题3: 库文件缺失

**症状**: ImportError: No module named 'xxx'

**解决**: 重新复制库文件到lib/目录

## 📞 技术支持

如有问题,请查看主文档的故障排查章节或提交Issue。

---

**最后更新**: 2025-01-19
