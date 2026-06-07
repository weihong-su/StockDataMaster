# 开源与授权

StockDataMaster 以开放协作的方式发布代码、文档和测试，但许可证采用 Business Source License 1.1。它不是 OSI 认证的传统开源许可证；它更适合“非商业免费、商业使用授权、到期后转宽松许可证”的项目模式。

---

## 许可证摘要

- 许可证：Business Source License 1.1
- 非商业用途：个人、学习、研究、评估等场景免费
- 商业用途：需要联系作者获取商业授权
- Change Date：2030-06-07
- Change License：MIT License
- 联系邮箱：`arthur@lovefree.ai`

完整条款以仓库根目录 `LICENSE` 为准。

---

## 第三方组件

仓库保留了部分第三方数据源库和二进制运行文件，目的是降低版本不一致导致的运行问题。需要注意：

- 这些组件仍受各自上游许可证和服务条款约束。
- StockDataMaster 的许可证不会改变第三方组件的授权范围。
- 商业使用或二次分发前，应单独核对 Tushare、Baostock、Mootdx、xtquant/QMT 等组件和数据服务条款。

更多说明见仓库根目录 `NOTICE`。

---

## 贡献方式

欢迎通过 Issue 和 Pull Request 参与改进。提交前建议：

1. 阅读 `CONTRIBUTING.md`
2. 不提交真实 token、账号、私有路径或生产日志
3. 运行单元测试：`python -X utf8 -m pytest test/suite -m unit -q`
4. 更新相关文档和 `CHANGELOG.md`

---

## 赞助

如果 StockDataMaster 对你的研究、学习或项目有帮助，欢迎支持维护：

- Buy Me a Coffee: <https://buymeacoffee.com/suweihongc>

赞助不是商业授权。如需商业使用，请通过 `arthur@lovefree.ai` 联系授权。
