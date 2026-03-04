# StockDataMaster 发布指导手册

完整的GitHub仓库发布和GitHub Pages部署指南

---

## 目录

1. [发布前检查清单](#发布前检查清单)
2. [GitHub仓库发布步骤](#github仓库发布步骤)
3. [GitHub Pages部署步骤](#github-pages部署步骤)
4. [版本标签规范](#版本标签规范)
5. [发布日志模板](#发布日志模板)
6. [后续维护建议](#后续维护建议)

---

## 发布前检查清单

在发布前，请确保完成以下检查：

### 代码质量

> **⚠️ 必须步骤**：运行发布前强制检查脚本，所有检查通过才可发布：
>
> ```bash
> # 标准检查（含 git 工作区验证）
> python scripts/pre_release_check.py --version X.Y.Z
>
> # CI/CD 环境跳过 git 检查
> python scripts/pre_release_check.py --version X.Y.Z --skip-git
> ```
>
> 脚本会自动验证：版本号一致性、CHANGELOG 记录、单元测试（87项）、git 状态。

- [ ] **发布前检查脚本通过** (`python scripts/pre_release_check.py`)
- [ ] 单元测试全部通过（pytest -m unit，87项）
  ```bash
  # Windows 下需加 -X utf8 处理中文
  python -X utf8 -m pytest test/suite -m unit -v
  ```
- [ ] 集成测试验证（可选，需网络）
  ```bash
  python -X utf8 -m pytest test/suite -m integration -v
  ```
- [ ] 日志文件已清理（`logs/` 目录）
- [ ] 临时文件已删除

### 文档完整性
- [ ] README.md 已更新
- [ ] CLAUDE.md 已更新
- [ ] docs/ 目录文档齐全
- [ ] API文档完整
- [ ] 版本号已更新

### 配置检查
- [ ] `config.json` 示例文件正确
- [ ] 敏感信息已移除（Token等）
- [ ] `.gitignore` 配置正确

### 版本信息
- [ ] 版本号已更新（README.md、CLAUDE.md）
- [ ] CHANGELOG 已完善
- [ ] 发布日期已更新

---

## GitHub仓库发布步骤

### 1. 准备发布分支

```bash
# 确保在main分支且代码最新
git checkout main
git pull origin main

# 查看当前状态
git status

# 添加所有变更
git add .

# 提交变更
git commit -m "chore: prepare for v1.1.0 release"
```

### 2. 创建版本标签

**语义化版本规范**：

- **主版本号（Major）**: 重大更新，不兼容的API变更
- **次版本号（Minor）**: 新增功能，向后兼容
- **修订号（Patch）**: Bug修复，向后兼容

**示例**：

```bash
# v1.0.0: 初始版本
# v1.1.0: 新增功能（xtquant深度优化）
# v1.1.1: Bug修复

# 创建标签
git tag -a v1.1.0 -m "Release v1.1.0 - xtquant深度优化完成"

# 查看标签
git tag -l

# 查看标签详情
git show v1.1.0
```

### 3. 推送到GitHub

```bash
# 推送代码
git push origin main

# 推送标签
git push origin v1.1.0

# 或推送所有标签
git push origin --tags
```

### 4. 创建GitHub Release

**方式1: 通过GitHub网页**

1. 访问仓库页面：`https://github.com/your-username/StockDataMaster`
2. 点击右侧 "Releases" → "Create a new release"
3. 选择标签：`v1.1.0`
4. 填写发布标题：`v1.1.0 - xtquant深度优化完成`
5. 填写发布说明（参考下方模板）
6. 可选：上传附件（如打包的代码）
7. 点击 "Publish release"

**方式2: 使用GitHub CLI**

```bash
# 安装GitHub CLI（如未安装）
# Windows: scoop install gh
# Mac: brew install gh
# Linux: sudo apt install gh

# 登录GitHub
gh auth login

# 创建Release
gh release create v1.1.0 \
  --title "v1.1.0 - xtquant深度优化完成" \
  --notes-file CHANGELOG.md
```

**发布说明模板**：

```markdown
## v1.1.0 - xtquant深度优化完成

### 新增特性

- xtquant深度优化（5阶段完成）
  - 接口利用率6.7%（+133%），复权因子<10ms
  - 智能缓存机制：833倍性能提升（2-3秒→3ms）
  - 时段感知100%准确，缓存优先策略
  - 双源校验100%通过率，复权一致性<0.5%误差
  - 4数据源无缝切换，60秒健康检测

### 改进

- 文档全面更新
- 测试覆盖率提升
- 性能优化

### Bug修复

- 修复xxx问题
- 修复yyy问题

### 升级指南

无需特殊升级步骤，直接更新代码即可。

### 完整更新日志

详见 [CHANGELOG.md](./CHANGELOG.md)
```

---

## GitHub Pages部署步骤

### 1. 启用GitHub Pages

**网页操作**：

1. 访问仓库 Settings
2. 左侧菜单选择 "Pages"
3. 在 "Source" 部分：
   - **Branch**: 选择 `main`
   - **Folder**: 选择 `/docs`
4. 点击 "Save"

**等待构建**：

- GitHub会自动构建，通常需要1-3分钟
- 构建完成后，会显示访问链接

### 2. 配置发布源

**默认配置**（推荐）：

- **分支**: `main`
- **目录**: `/docs`

**高级配置**（可选）：

如需使用独立分支（如 `gh-pages`）：

```bash
# 创建gh-pages分支
git checkout --orphan gh-pages

# 清空工作区
git rm -rf .

# 复制docs内容
cp -r docs/* .

# 提交
git add .
git commit -m "docs: initialize gh-pages"

# 推送
git push origin gh-pages

# 返回main分支
git checkout main
```

然后在Settings → Pages中选择 `gh-pages` 分支。

### 3. 自定义域名（可选）

**添加自定义域名**：

1. 在仓库Settings → Pages → "Custom domain" 输入域名
2. 保存后，会在 `docs/` 目录生成 `CNAME` 文件
3. 在域名DNS设置中添加CNAME记录：
   ```
   docs.yourdomain.com  CNAME  your-username.github.io
   ```

**验证域名**：

- 等待DNS生效（5-30分钟）
- 访问自定义域名测试

### 4. 验证部署

**检查访问链接**：

默认链接格式：
```
https://your-username.github.io/StockDataMaster/
```

**验证内容**：

- [ ] 主页正常显示（index.md）
- [ ] 快速开始链接正常
- [ ] API参考链接正常
- [ ] 架构文档链接正常
- [ ] FAQ链接正常
- [ ] 图片和样式正常加载

**调试问题**：

如果页面404或样式异常：

1. 检查 `_config.yml` 配置
2. 确认文件路径正确
3. 查看GitHub Actions构建日志
4. 强制刷新浏览器缓存（Ctrl+F5）

---

## 版本标签规范

### 语义化版本

**格式**: `vMAJOR.MINOR.PATCH`

**示例**：

| 版本号 | 说明 | 示例场景 |
|--------|------|---------|
| v1.0.0 | 初始版本 | 首次正式发布 |
| v1.1.0 | 新增功能 | xtquant深度优化 |
| v1.1.1 | Bug修复 | 修复缓存问题 |
| v2.0.0 | 重大更新 | 不兼容的API变更 |

### 预发布版本

**格式**: `vMAJOR.MINOR.PATCH-alpha/beta/rc.N`

**示例**：

```bash
# Alpha版本（内部测试）
git tag -a v1.2.0-alpha.1 -m "Alpha release for internal testing"

# Beta版本（公开测试）
git tag -a v1.2.0-beta.1 -m "Beta release for public testing"

# RC版本（发布候选）
git tag -a v1.2.0-rc.1 -m "Release candidate"
```

### 标签命名规范

```bash
# ✅ 正确
v1.0.0
v1.1.0
v2.0.0-beta.1

# ❌ 错误
1.0.0        # 缺少v前缀
v1.0         # 缺少修订号
release-1.0  # 非标准格式
```

---

## 发布日志模板

### CHANGELOG.md 模板

```markdown
# Changelog

All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.0.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [Unreleased]

### Added
- 待发布的新功能

### Changed
- 待发布的改进

### Fixed
- 待发布的Bug修复

## [1.1.0] - 2025-11-18

### Added
- xtquant深度优化方案完美收官（5阶段100%完成）
  - 阶段1: 扩展xtquant核心功能
  - 阶段2: 智能缓存机制（833倍性能提升）
  - 阶段3: 智能数据源选择
  - 阶段4: 数据一致性保障
  - 阶段5: 监控和自愈机制

### Changed
- 文档全面更新
- 测试覆盖率提升

### Fixed
- 修复xtquant连接判断问题
- 修复盘中缓存逻辑

## [1.0.0] - 2025-10-20

### Added
- 初始版本发布
- 支持4个数据源（Mootdx、Baostock、Tushare、xtquant）
- 实现智能缓存系统
- 实现健康检测和热切换
- 完整的文档和测试

[Unreleased]: https://github.com/your-repo/StockDataMaster/compare/v1.1.0...HEAD
[1.1.0]: https://github.com/your-repo/StockDataMaster/compare/v1.0.0...v1.1.0
[1.0.0]: https://github.com/your-repo/StockDataMaster/releases/tag/v1.0.0
```

---

## 后续维护建议

### 定期更新文档

**频率**: 每次重大功能更新

**内容**:
- 更新 README.md
- 更新 CLAUDE.md 的变更记录
- 更新 API 文档
- 更新性能报告

### 版本发布流程

**建议节奏**：

- **Major版本**: 每年1-2次
- **Minor版本**: 每季度1次或按需
- **Patch版本**: 按需发布

**发布前准备**：

1. 完成功能开发和测试
2. 更新所有文档
3. 清理临时文件
4. 运行完整测试
5. 更新CHANGELOG
6. 创建标签并发布

### Issue管理

**标签体系**：

```
bug          - Bug报告
enhancement  - 功能增强
documentation - 文档相关
question     - 使用问题
wontfix      - 不会修复
duplicate    - 重复问题
```

**响应时间**：

- Bug: 24小时内响应
- 功能请求: 3天内响应
- 问题咨询: 48小时内响应

### Pull Request审核流程

**审核标准**：

1. 代码质量检查
2. 测试覆盖验证
3. 文档完整性
4. 编码规范遵循
5. 性能影响评估

**合并要求**：

- [ ] 所有测试通过
- [ ] 代码审查通过
- [ ] 文档已更新
- [ ] 无冲突
- [ ] 符合编码规范

---

## 快速命令参考

### 常用Git命令

```bash
# 查看状态
git status

# 添加所有变更
git add .

# 提交
git commit -m "feat: add new feature"

# 推送
git push origin main

# 创建标签
git tag -a v1.1.0 -m "Release v1.1.0"

# 推送标签
git push origin v1.1.0

# 查看标签
git tag -l

# 删除本地标签
git tag -d v1.1.0

# 删除远程标签
git push origin :refs/tags/v1.1.0
```

### GitHub CLI命令

```bash
# 登录
gh auth login

# 创建Release
gh release create v1.1.0 --title "v1.1.0" --notes "Release notes"

# 查看Release
gh release list

# 查看仓库信息
gh repo view

# 创建Issue
gh issue create --title "Bug report" --body "Description"

# 查看PR
gh pr list
```

---

## 联系支持

如有问题，请：

1. 查阅 [文档](https://your-username.github.io/StockDataMaster/)
2. 搜索 [已有Issues](https://github.com/your-repo/StockDataMaster/issues)
3. 提交 [新Issue](https://github.com/your-repo/StockDataMaster/issues/new)

---

**祝发布顺利！📦**
