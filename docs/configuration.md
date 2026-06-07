# 配置指南

StockDataMaster 默认读取根目录 `config.json`，并在加载配置时自动读取代码库根目录 `.env`。推荐把真实凭据放在 `.env`，不要写入 `config.json`。

---

## 快速配置

复制模板：

```bash
copy .env.example .env
```

编辑 `.env`：

```dotenv
TUSHARE_TOKEN=你的Tushare Token
XTQUANT_QMT_PATH=
XTQUANT_ACCOUNT=
STOCKDATAMASTER_LOG_LEVEL=INFO
STOCKDATAMASTER_LOG_FILE=logs/data_master.log
```

`.env` 已被 `.gitignore` 忽略，不应提交到 Git。

---

## 配置优先级

同一个配置项存在多个来源时，优先级从高到低为：

1. 系统环境变量
2. 根目录 `.env`
3. `config.json`

这个顺序适合本地开发和 CI/CD 共用：本地使用 `.env`，CI 使用平台密钥或环境变量临时覆盖。

---

## 支持的环境变量

| 环境变量 | 覆盖配置 | 说明 |
| --- | --- | --- |
| `TUSHARE_TOKEN` | `data_sources.tushare.token` | Tushare 访问 token |
| `XTQUANT_QMT_PATH` | `data_sources.xtquant.qmt_path` | QMT 客户端路径 |
| `XTQUANT_ACCOUNT` | `data_sources.xtquant.account` | QMT 账号 |
| `STOCKDATAMASTER_LOG_LEVEL` | `logging.level` | 日志级别 |
| `STOCKDATAMASTER_LOG_FILE` | `logging.file` | 日志文件路径 |

---

## Demo Key 说明

`config.json` 中保留的 Tushare token 是已吊销 demo key，仅用于展示配置结构。实际使用时请通过 `.env` 或系统环境变量提供自己的 token。

---

## 示例配置文件

`config.example.json` 展示了可提交的配置形态，其中 token 使用 `${TUSHARE_TOKEN}` 占位。真实本地配置可以保留 `config.json` 的结构，再用 `.env` 覆盖敏感值。
