# StockDataMaster Demo - 监控平台

## 📋 概述

这是一个完整的前后端分离Web监控平台,用于展示StockDataMaster的功能:

- ✅ **数据源健康监控**: 实时查看各数据源(Mootdx、Baostock、Tushare、xtquant)的可用性和响应时间
- ✅ **库加载状态**: 查看内置库/系统库的加载情况
- ✅ **K线图表展示**: 交互式K线图,支持日线/60分/30分/15分/5分周期
- ✅ **实时行情**: 获取和展示实时Tick数据
- ✅ **缓存统计**: 查看SQLite缓存的使用情况
- ✅ **系统日志**: 监控系统运行日志

## 🏗️ 技术架构

### 后端 (Backend)

- **框架**: FastAPI (高性能Python Web框架)
- **API风格**: RESTful JSON API
- **数据处理**: Pandas, NumPy
- **文档**: 自动生成OpenAPI文档 (Swagger UI)

**目录结构**:
```
backend/
├── api_server.py           # FastAPI主服务
├── requirements.txt        # Python依赖
├── start.sh                # Linux/Mac启动脚本
└── start.bat               # Windows启动脚本
```

### 前端 (Frontend)

- **框架**: Vue 3 (响应式前端框架)
- **UI组件**: Element Plus (企业级UI组件库)
- **图表**: ECharts 5 (强大的可视化库)
- **HTTP**: Axios (HTTP客户端)
- **部署**: 单HTML文件,无需编译,开箱即用

**特点**:
- 📱 响应式设计,支持各种屏幕尺寸
- 🎨 美观的渐变色界面
- ⚡ 实时数据刷新
- 📊 交互式K线图,支持缩放和拖拽

## 🚀 快速开始

### 方式1: 本地部署(推荐用于开发)

#### 步骤1: 安装后端依赖

```bash
cd StockDataMaster/demo/backend

# 安装Python依赖
pip install -r requirements.txt
```

#### 步骤2: 启动后端服务

**Linux/Mac**:
```bash
chmod +x start.sh
./start.sh
```

**Windows**:
```bash
start.bat
```

或直接运行:
```bash
python api_server.py
```

后端服务将在 `http://localhost:8000` 启动

#### 步骤3: 打开前端页面

**方式A**: 直接用浏览器打开 `frontend/index.html`

**方式B**: 使用简单的HTTP服务器(推荐)
```bash
cd StockDataMaster/demo/frontend

# Python 3
python -m http.server 8080

# 或使用Node.js http-server
npx http-server -p 8080
```

然后访问: `http://localhost:8080`

### 方式2: VPS部署(生产环境)

#### 使用Nginx部署前端

1. **安装Nginx**:
```bash
sudo apt-get update
sudo apt-get install nginx
```

2. **配置Nginx**:
```bash
sudo nano /etc/nginx/sites-available/stockdatamaster
```

添加以下配置:
```nginx
server {
    listen 80;
    server_name your_domain.com;  # 替换为你的域名或IP

    # 前端静态文件
    location / {
        root /path/to/StockDataMaster/demo/frontend;
        index index.html;
        try_files $uri $uri/ /index.html;
    }

    # 代理后端API
    location /api/ {
        proxy_pass http://127.0.0.1:8000;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
    }
}
```

3. **启用配置**:
```bash
sudo ln -s /etc/nginx/sites-available/stockdatamaster /etc/nginx/sites-enabled/
sudo nginx -t
sudo systemctl restart nginx
```

#### 使用Supervisor管理后端进程

1. **安装Supervisor**:
```bash
sudo apt-get install supervisor
```

2. **配置Supervisor**:
```bash
sudo nano /etc/supervisor/conf.d/stockdatamaster.conf
```

添加以下配置:
```ini
[program:stockdatamaster]
command=/usr/bin/python3 /path/to/StockDataMaster/demo/backend/api_server.py
directory=/path/to/StockDataMaster/demo/backend
user=www-data
autostart=true
autorestart=true
stderr_logfile=/var/log/stockdatamaster.err.log
stdout_logfile=/var/log/stockdatamaster.out.log
```

3. **启动服务**:
```bash
sudo supervisorctl reread
sudo supervisorctl update
sudo supervisorctl start stockdatamaster
```

#### 使用systemd管理后端服务

创建服务文件:
```bash
sudo nano /etc/systemd/system/stockdatamaster.service
```

添加以下内容:
```ini
[Unit]
Description=StockDataMaster API Server
After=network.target

[Service]
Type=simple
User=www-data
WorkingDirectory=/path/to/StockDataMaster/demo/backend
ExecStart=/usr/bin/python3 /path/to/StockDataMaster/demo/backend/api_server.py
Restart=on-failure

[Install]
WantedBy=multi-user.target
```

启动服务:
```bash
sudo systemctl daemon-reload
sudo systemctl enable stockdatamaster
sudo systemctl start stockdatamaster
sudo systemctl status stockdatamaster
```

### 方式3: Docker部署(完全容器化)

#### Dockerfile示例

**后端Dockerfile** (`backend/Dockerfile`):
```dockerfile
FROM python:3.8-slim

WORKDIR /app

# 复制整个StockDataMaster目录(包含lib/)
COPY ../.. /app/StockDataMaster

# 安装依赖
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# 暴露端口
EXPOSE 8000

# 启动服务
CMD ["python", "/app/StockDataMaster/demo/backend/api_server.py"]
```

#### Docker Compose示例

创建 `docker-compose.yml`:
```yaml
version: '3.8'

services:
  backend:
    build:
      context: ./backend
      dockerfile: Dockerfile
    ports:
      - "8000:8000"
    volumes:
      - ../../:/app/StockDataMaster
    environment:
      - PYTHONUNBUFFERED=1
    restart: unless-stopped

  frontend:
    image: nginx:alpine
    ports:
      - "80:80"
    volumes:
      - ./frontend:/usr/share/nginx/html:ro
      - ./nginx.conf:/etc/nginx/conf.d/default.conf:ro
    depends_on:
      - backend
    restart: unless-stopped
```

启动:
```bash
docker-compose up -d
```

## 📡 API文档

后端服务启动后,访问以下地址查看自动生成的API文档:

- **Swagger UI**: http://localhost:8000/docs
- **ReDoc**: http://localhost:8000/redoc

### 主要API端点

| 端点 | 方法 | 描述 |
|------|------|------|
| `/api/health` | GET | 获取数据源健康状态 |
| `/api/libraries` | GET | 获取库加载状态 |
| `/api/kline` | POST | 获取K线数据 |
| `/api/tick` | POST | 获取实时Tick数据 |
| `/api/cache/stats` | GET | 获取缓存统计信息 |
| `/api/logs` | GET | 获取系统日志 |
| `/api/stock/search` | GET | 搜索股票 |

### API使用示例

#### 获取K线数据

```bash
curl -X POST "http://localhost:8000/api/kline" \
  -H "Content-Type: application/json" \
  -d '{
    "code": "sh.600000",
    "frequency": "d",
    "count": 100
  }'
```

响应:
```json
{
  "success": true,
  "message": "成功获取100条数据",
  "code": "sh.600000",
  "frequency": "d",
  "count": 100,
  "data": [
    {
      "date": "2025-01-01",
      "open": 10.5,
      "close": 10.8,
      "high": 11.0,
      "low": 10.3,
      "volume": 12345678
    },
    ...
  ]
}
```

## 🖼️ 功能截图

### 数据源健康监控
实时显示Mootdx、Baostock、Tushare、xtquant的可用性和响应时间。

### K线图表
- 支持日线、60分钟、30分钟、15分钟、5分钟周期
- 交互式图表,可缩放、拖拽
- 成交量柱状图联动
- 红绿K线(涨红跌绿)

### 实时行情
- 当前价
- 涨跌幅
- 成交量
- 最高/最低价
- 昨收价

### 库加载状态
- 显示mootdx、baostock、tushare、xtquant的加载情况
- 显示使用内置库还是系统库
- 显示库版本号

## 🔧 配置说明

### 后端配置

修改 `backend/api_server.py`:

```python
# 修改监听端口
if __name__ == "__main__":
    import uvicorn

    uvicorn.run(
        "api_server:app",
        host="0.0.0.0",  # 监听所有IP(VPS部署)
        port=8000,        # 修改端口
        reload=False,     # 生产环境设为False
        log_level="info"
    )
```

### 前端配置

修改 `frontend/index.html`:

```javascript
// 修改API地址
data() {
    return {
        apiBaseUrl: 'http://your-server-ip:8000',  // 修改为实际地址
        ...
    }
}
```

### CORS配置(跨域)

如果前后端部署在不同域名,修改 `backend/api_server.py`:

```python
app.add_middleware(
    CORSMiddleware,
    allow_origins=["https://your-frontend-domain.com"],  # 指定允许的域名
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)
```

## 📊 使用场景

### 场景1: 开发环境验证

开发者在本地运行demo,验证StockDataMaster的数据准确性:
- 对比多个数据源的K线数据
- 检查数据源切换是否无缝
- 验证缓存机制是否正常

### 场景2: 生产环境监控

部署到VPS上,实时监控生产环境的数据源状态:
- 7x24小时监控数据源健康
- 实时告警(可集成钉钉/邮件)
- 远程查看K线图验证数据

### 场景3: 开盘时段对比验证

开盘时间使用demo对比股票软件的实时数据:
- 实时Tick数据验证
- 分钟K线延迟测试
- 数据准确性验证

## 🛠️ 故障排查

### 后端无法启动

**问题**: `ModuleNotFoundError: No module named 'fastapi'`

**解决**:
```bash
cd backend
pip install -r requirements.txt
```

### 前端无法连接后端

**问题**: CORS错误或Network Error

**解决**:
1. 检查后端是否启动: `curl http://localhost:8000`
2. 检查防火墙设置
3. 修改前端的 `apiBaseUrl` 为正确地址
4. 检查CORS配置

### K线图不显示

**问题**: 图表区域空白

**解决**:
1. 检查浏览器控制台错误
2. 确认ECharts CDN加载成功
3. 检查数据格式是否正确
4. 尝试刷新页面

### 数据源全部不可用

**问题**: 健康状态显示全部不可用

**解决**:
1. 检查StockDataMaster库是否正确安装
2. 检查内置库是否存在: `ls StockDataMaster/lib/`
3. 查看后端日志: 运行`python api_server.py`查看详细错误
4. 验证配置文件 `config.json`

## 📝 扩展开发

### 添加新的API端点

在 `backend/api_server.py` 中添加:

```python
@app.get("/api/custom")
async def custom_endpoint():
    # 你的逻辑
    return {"message": "自定义端点"}
```

### 添加新的前端组件

在 `frontend/index.html` 中的 `<div id="app">` 内添加:

```html
<div class="card">
    <div class="card-title">🆕 新功能</div>
    <!-- 你的内容 -->
</div>
```

并在Vue实例的 `methods` 中添加对应方法。

### 集成告警通知

修改 `backend/api_server.py`,在健康检查失败时发送通知:

```python
from notifications import send_dingtalk, send_email

@app.get("/api/health")
async def get_health_status():
    health = stock_master.get_health_status()

    # 检查是否有数据源不可用
    unavailable_sources = [
        name for name, status in health['sources'].items()
        if not status['available']
    ]

    if unavailable_sources:
        message = f"⚠️ 数据源告警: {', '.join(unavailable_sources)} 不可用"
        send_dingtalk(message)  # 发送钉钉通知
        send_email(message)     # 发送邮件通知

    return HealthResponse(...)
```

## 📄 许可证

本Demo遵循StockDataMaster项目的许可证。仅用于学习交流,不得用于商业用途。

## 🤝 贡献

欢迎提交Issue和Pull Request改进这个Demo!

## 📞 支持

如有问题,请查看:
- StockDataMaster主文档: `../README.md`
- API文档: http://localhost:8000/docs
- 项目Issues

---

**开发者**: Claude Code Agent
**最后更新**: 2025-10-19
**版本**: 1.0.0
