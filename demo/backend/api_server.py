"""
StockDataMaster Demo - FastAPI后端服务

提供数据接口供前端展示:
- K线数据查询
- 实时行情数据
- 数据源健康状态
- 系统日志
"""

import sys
from pathlib import Path
from datetime import datetime, timedelta
from typing import Optional, List, Dict, Any
import json
import logging

# 添加StockDataMaster到路径
sys.path.insert(0, str(Path(__file__).parent.parent.parent))

from fastapi import FastAPI, HTTPException, Query
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
import pandas as pd

from StockDataMaster import StockDataMaster
from StockDataMaster.utils import get_lib_loader


# ============= 配置 =============
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

app = FastAPI(
    title="StockDataMaster监控平台",
    description="实时监控数据源状态、查看K线图、验证数据准确性",
    version="1.0.0"
)

# CORS设置(允许前端跨域访问)
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # 生产环境应限制具体域名
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# 全局StockDataMaster实例
stock_master: Optional[StockDataMaster] = None


# ============= 数据模型 =============

class KlineRequest(BaseModel):
    """K线数据请求"""
    code: str
    frequency: str = "d"  # d/5/15/30/60
    count: int = 100
    start: Optional[str] = None
    end: Optional[str] = None


class TickRequest(BaseModel):
    """Tick数据请求"""
    code: str


class HealthResponse(BaseModel):
    """健康状态响应"""
    status: str
    sources: Dict[str, Any]
    timestamp: str


class LibraryStatus(BaseModel):
    """库加载状态"""
    libraries: Dict[str, Dict[str, Any]]
    use_builtin: bool


# ============= 启动和关闭事件 =============

@app.on_event("startup")
async def startup_event():
    """启动时初始化StockDataMaster"""
    global stock_master

    try:
        logger.info("正在初始化StockDataMaster...")
        stock_master = StockDataMaster()
        logger.info("✓ StockDataMaster初始化成功")

        # 记录库加载状态
        loader = get_lib_loader()
        lib_status = loader.get_library_status()
        logger.info(f"库加载状态: {json.dumps(lib_status, indent=2, ensure_ascii=False)}")

    except Exception as e:
        logger.error(f"✗ StockDataMaster初始化失败: {e}")
        stock_master = None


@app.on_event("shutdown")
async def shutdown_event():
    """关闭时清理资源"""
    global stock_master

    if stock_master:
        try:
            # 关闭所有数据源连接
            logger.info("正在关闭数据源连接...")
            # stock_master.cleanup()  # 如果有清理方法
            logger.info("✓ 资源清理完成")
        except Exception as e:
            logger.error(f"资源清理失败: {e}")


# ============= API路由 =============

@app.get("/")
async def root():
    """根路由"""
    return {
        "message": "StockDataMaster监控平台API",
        "version": "1.0.0",
        "docs": "/docs",
        "status": "running" if stock_master else "error"
    }


@app.get("/api/health", response_model=HealthResponse)
async def get_health_status():
    """获取数据源健康状态"""

    if not stock_master:
        raise HTTPException(status_code=500, detail="StockDataMaster未初始化")

    try:
        # 获取健康状态
        health = stock_master.get_health_status()

        return HealthResponse(
            status="healthy" if any(s['available'] for s in health['sources'].values()) else "error",
            sources=health['sources'],
            timestamp=datetime.now().isoformat()
        )

    except Exception as e:
        logger.error(f"获取健康状态失败: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/api/libraries", response_model=LibraryStatus)
async def get_library_status():
    """获取库加载状态"""

    try:
        loader = get_lib_loader()
        lib_status = loader.get_library_status()

        return LibraryStatus(
            libraries=lib_status,
            use_builtin=loader.use_builtin
        )

    except Exception as e:
        logger.error(f"获取库状态失败: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@app.post("/api/kline")
async def get_kline(request: KlineRequest):
    """获取K线数据"""

    if not stock_master:
        raise HTTPException(status_code=500, detail="StockDataMaster未初始化")

    try:
        logger.info(f"请求K线数据: {request.code} {request.frequency} count={request.count}")

        # 获取K线数据
        df = stock_master.get_kline(
            code=request.code,
            frequency=request.frequency,
            count=request.count,
            start=request.start,
            end=request.end
        )

        if df is None or df.empty:
            return {
                "success": False,
                "message": "未获取到数据",
                "data": []
            }

        # 转换为JSON格式
        df['date'] = df['date'].astype(str) if 'date' in df.columns else df.index.astype(str)

        data = df.to_dict('records')

        return {
            "success": True,
            "message": f"成功获取{len(data)}条数据",
            "code": request.code,
            "frequency": request.frequency,
            "count": len(data),
            "data": data
        }

    except Exception as e:
        logger.error(f"获取K线数据失败: {e}", exc_info=True)
        return {
            "success": False,
            "message": f"获取数据失败: {str(e)}",
            "data": []
        }


@app.post("/api/tick")
async def get_tick(request: TickRequest):
    """获取实时Tick数据"""

    if not stock_master:
        raise HTTPException(status_code=500, detail="StockDataMaster未初始化")

    try:
        logger.info(f"请求Tick数据: {request.code}")

        # 获取Tick数据
        tick_data = stock_master.get_tick(code=request.code)

        if tick_data is None:
            return {
                "success": False,
                "message": "未获取到实时数据",
                "data": None
            }

        # 转换为字典
        if isinstance(tick_data, pd.DataFrame):
            data = tick_data.to_dict('records')[0] if not tick_data.empty else None
        elif isinstance(tick_data, dict):
            data = tick_data
        else:
            data = None

        return {
            "success": True,
            "message": "成功获取实时数据",
            "code": request.code,
            "data": data
        }

    except Exception as e:
        logger.error(f"获取Tick数据失败: {e}", exc_info=True)
        return {
            "success": False,
            "message": f"获取数据失败: {str(e)}",
            "data": None
        }


@app.get("/api/cache/stats")
async def get_cache_statistics():
    """获取缓存统计信息"""

    if not stock_master:
        raise HTTPException(status_code=500, detail="StockDataMaster未初始化")

    try:
        stats = stock_master.get_cache_statistics()

        return {
            "success": True,
            "stats": stats
        }

    except Exception as e:
        logger.error(f"获取缓存统计失败: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/api/logs")
async def get_logs(
    level: Optional[str] = Query(None, description="日志级别: INFO/WARNING/ERROR"),
    limit: int = Query(100, description="返回最近N条日志")
):
    """获取系统日志"""

    try:
        # 这里简化实现,返回最近的日志
        # 实际应该从日志文件或数据库读取
        logs = [
            {
                "timestamp": datetime.now().isoformat(),
                "level": "INFO",
                "message": "这是演示日志,实际应从日志文件读取"
            }
        ]

        return {
            "success": True,
            "count": len(logs),
            "logs": logs
        }

    except Exception as e:
        logger.error(f"获取日志失败: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/api/stock/search")
async def search_stock(keyword: str = Query(..., description="股票代码或名称关键词")):
    """搜索股票"""

    # 简化版本:返回常用股票列表供演示
    common_stocks = [
        {"code": "sh.600000", "name": "浦发银行"},
        {"code": "sh.600036", "name": "招商银行"},
        {"code": "sh.600519", "name": "贵州茅台"},
        {"code": "sz.000001", "name": "平安银行"},
        {"code": "sz.000002", "name": "万科A"},
        {"code": "sz.000858", "name": "五粮液"},
    ]

    # 简单过滤
    keyword_lower = keyword.lower()
    results = [
        stock for stock in common_stocks
        if keyword_lower in stock['code'].lower() or keyword_lower in stock['name']
    ]

    return {
        "success": True,
        "count": len(results),
        "stocks": results
    }


# ============= 运行服务 =============

if __name__ == "__main__":
    import uvicorn

    uvicorn.run(
        "api_server:app",
        host="0.0.0.0",
        port=8000,
        reload=True,  # 开发模式,代码变更自动重载
        log_level="info"
    )
