# 贡献指南

感谢你愿意参与 StockDataMaster。这个项目关注股票数据源接入、缓存、健康检测和稳定性验证，提交变更时请优先保证可复现、可测试、可回滚。

## 开发流程

1. Fork 仓库并创建功能分支，例如 `feature/cache-improvement`。
2. 使用 Python 3.9 环境开发，推荐环境路径为 `C:\Users\PC\Anaconda3\envs\python39`。
3. 安装依赖：`python -m pip install -r requirements.txt`。
4. 运行单元测试：`python -X utf8 -m pytest test/suite -m unit -q`。
5. 更新相关文档和 `CHANGELOG.md`。
6. 提交 Pull Request，并说明变更背景、影响范围和验证结果。

## 代码要求

- 新增代码应保持中文注释和中文文档风格。
- 不要提交真实 token、账号、私有路径或生产日志。
- 涉及数据源行为的改动，要说明 fallback 链和缓存一致性影响。
- 涉及第三方库的改动，要说明版本来源和许可证影响。

## 许可证提醒

本项目采用 Business Source License 1.1。个人、学习、研究、评估和非商业用途免费；商业用途请联系 `arthur@lovefree.ai` 获取授权。
