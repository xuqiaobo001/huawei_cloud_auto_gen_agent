"""
华为云Agent编排系统 - Web主应用
基于FastAPI的现代Web应用
"""

import os
import secrets
from contextlib import asynccontextmanager
from pathlib import Path
from fastapi import FastAPI, Request, Form, HTTPException, Depends
from fastapi.responses import HTMLResponse, JSONResponse, RedirectResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from starlette.middleware.sessions import SessionMiddleware
import uvicorn

from models.workflow import Workflow, Task, TaskStatus, WorkflowStatus
from services.workflow_engine import WorkflowEngine
from services import huawei_cloud_service_registry
from agents.llm_orchestration_agent import LLMOrchestrationAgent
from utils.database import init_db, save_workflow_record, list_workflow_records, get_workflow_record, delete_workflow_record
from utils.logger import setup_logger
from utils.config_manager import get_config
from utils.vector_store import get_vector_store
from utils.auth import init_default_user, authenticate, get_current_user, AuthMiddleware
from utils.graph_store import get_graph_store
from services.service_dependency_analyzer import get_analyzer

# 初始化配置
config = get_config()

# 初始化服务（全局变量）
logger = setup_logger()
workflow_engine = WorkflowEngine()
service_registry = huawei_cloud_service_registry.get_registry()
agent = LLMOrchestrationAgent()

@asynccontextmanager
async def lifespan(app: FastAPI):
    """应用生命周期管理"""
    # 启动时初始化
    logger.info("=" * 60)
    logger.info("启动华为云Agent编排系统")
    logger.info("=" * 60)

    # 显示配置信息
    llm_config = config.get_llm_config()
    hw_config = config.get_huaweicloud_config()

    logger.info(f"LLM提供商: {llm_config.get('provider', '未配置')}")
    logger.info(f"模型: {llm_config.get('model', '未配置')}")
    logger.info(f"LLM可用: {agent.is_llm_available()}")

    logger.info(f"华为云区域: {hw_config.get('region', '未配置')}")
    logger.info(f"AK已配置: {'是' if hw_config.get('ak') else '否'}")

    init_db()
    init_default_user()
    logger.info(f"已注册 {len(service_registry.services)} 个云服务")

    # 初始化服务依赖图
    try:
        graph_store = get_graph_store()
        if graph_store.is_connected:
            if graph_store.node_count() == 0:
                analyzer = get_analyzer()
                graph_store.populate_from_analyzer(analyzer)
                logger.info("服务依赖图数据已填充到Neo4j")
            else:
                logger.info("Neo4j中已有图数据，跳过填充")
        else:
            logger.warning("Neo4j不可用，将使用Analyzer直接提供图数据")
    except Exception as e:
        logger.warning(f"图数据库初始化失败，降级运行: {e}")

    logger.info("系统启动完成")

    yield

    # 关闭时清理
    logger.info("系统正在关闭...")

# 初始化应用
app = FastAPI(
    title="华为云Agent编排系统",
    description="基于LLM的智能云资源编排和自动化部署平台",
    version="1.1.0",
    lifespan=lifespan
)

# 中间件（注意：后添加的在外层，SessionMiddleware 必须在 AuthMiddleware 外层）
app.add_middleware(AuthMiddleware)
SESSION_SECRET = os.environ.get("SESSION_SECRET", secrets.token_hex(32))
app.add_middleware(SessionMiddleware, secret_key=SESSION_SECRET, max_age=86400)

# 初始化目录
app.mount("/static", StaticFiles(directory="static"), name="static")
templates = Jinja2Templates(directory="templates")


@app.get("/favicon.ico")
async def favicon():
    return RedirectResponse(url="/static/favicon.svg", status_code=301)


# ===== 认证路由（无需登录） =====

@app.get("/login", response_class=HTMLResponse)
async def login_page(request: Request):
    """登录页面"""
    user = get_current_user(request)
    if user:
        return RedirectResponse(url="/", status_code=302)
    return templates.TemplateResponse("login.html", {"request": request})


@app.post("/api/auth/login")
async def api_login(request: Request, data: dict):
    """登录验证"""
    username = data.get("username", "")
    password = data.get("password", "")
    user = authenticate(username, password)
    if not user:
        return JSONResponse({"success": False, "error": "用户名或密码错误"}, status_code=401)
    request.session["user_id"] = user.id
    request.session["username"] = user.username
    return JSONResponse({"success": True, "username": user.username})


@app.get("/logout")
async def logout(request: Request):
    """登出"""
    request.session.clear()
    return RedirectResponse(url="/login", status_code=302)


@app.get("/api/auth/me")
async def auth_me(request: Request):
    """获取当前用户信息"""
    user = get_current_user(request)
    if not user:
        return JSONResponse({"success": False, "error": "未登录"}, status_code=401)
    return JSONResponse({"success": True, "username": user.username, "user_id": user.id})


# ===== 页面路由 =====

@app.get("/", response_class=HTMLResponse)
async def index(request: Request):
    """主页"""
    return templates.TemplateResponse(
        "index.html",
        {
            "request": request,
            "llm_available": agent.is_llm_available(),
            "username": request.session.get("username", "")
        }
    )


@app.get("/designer", response_class=HTMLResponse)
async def workflow_designer(request: Request):
    """工作流设计器页面"""
    # 获取所有可用的云服务
    services = []
    for name, service in service_registry.services.items():
        services.append({
            "name": name,
            "description": service.description,
            "sdk_package": service.sdk_package_name,
            "operations_count": len(service.operations)
        })

    return templates.TemplateResponse(
        "workflow_designer.html",
        {
            "request": request,
            "services": services,
            "llm_available": agent.is_llm_available(),
            "username": request.session.get("username", "")
        }
    )


@app.get("/monitor", response_class=HTMLResponse)
async def monitor(request: Request):
    """监控页面"""
    return templates.TemplateResponse("monitor.html", {"request": request, "username": request.session.get("username", "")})


@app.get("/services", response_class=HTMLResponse)
async def service_list(request: Request):
    """服务列表页面"""
    return templates.TemplateResponse("service_list.html", {"request": request, "username": request.session.get("username", "")})


@app.get("/graph", response_class=HTMLResponse)
async def graph_page(request: Request):
    """服务依赖图页面"""
    return templates.TemplateResponse(
        "graph.html",
        {
            "request": request,
            "llm_available": agent.is_llm_available(),
            "username": request.session.get("username", ""),
        }
    )


# ===== API路由 =====

@app.post("/api/workflow/generate")
async def generate_workflow(requirement: str = Form(...)):
    """
    使用LLM根据用户需求生成工作流

    Args:
        requirement: 用户自然语言描述

    Returns:
        生成的workflow定义
    """
    try:
        logger.info(f"收到工作流生成请求: {requirement}")

        # 检查LLM是否可用
        if not agent.is_llm_available():
            logger.warning("LLM不可用，使用规则引擎生成")

        # 生成工作流
        workflow = agent.plan(requirement)

        response = {
            "success": True,
            "data": workflow.to_dict(),
            "message": "工作流生成成功",
            "llm_used": agent.is_llm_available()
        }

        return JSONResponse(response)

    except Exception as e:
        logger.error(f"工作流生成失败: {str(e)}", exc_info=True)
        return JSONResponse({
            "success": False,
            "error": str(e),
            "message": "工作流生成失败，请检查日志"
        }, status_code=500)


@app.post("/api/workflow/execute")
async def execute_workflow(workflow_data: dict):
    """
    执行工作流

    Args:
        workflow_data: 工作流定义JSON

    Returns:
        执行结果
    """
    try:
        logger.info(f"收到工作流执行请求，任务数: {len(workflow_data.get('tasks', []))}")

        # 创建工作流对象
        workflow = Workflow.from_dict(workflow_data)

        # 执行工作流
        result = await workflow_engine.execute(workflow)

        return JSONResponse({
            "success": True,
            "data": result
        })

    except Exception as e:
        logger.error(f"工作流执行失败: {str(e)}")
        return JSONResponse({
            "success": False,
            "error": str(e)
        }, status_code=500)


@app.get("/api/workflow/{workflow_id}/status")
async def get_workflow_status(workflow_id: str):
    """
    获取工作流执行状态

    Args:
        workflow_id: 工作流ID

    Returns:
        状态信息
    """
    try:
        status = workflow_engine.get_status(workflow_id)
        return JSONResponse({
            "success": True,
            "data": status
        })
    except Exception as e:
        logger.error(f"获取状态失败: {str(e)}")
        return JSONResponse({
            "success": False,
            "error": str(e)
        }, status_code=404)


@app.get("/api/services/list")
async def list_services():
    """
    获取所有可用的华为云服务列表（从向量数据库）

    Returns:
        服务列表
    """
    try:
        vector_store = get_vector_store()

        # 从向量数据库获取所有操作
        all_operations = vector_store.get_all_operations()

        # 按服务分组统计操作数
        ops_count = {}
        for op in all_operations:
            svc = op["service_name"]
            ops_count[svc] = ops_count.get(svc, 0) + 1

        # 基于注册表构建服务列表，用向量数据库的操作数
        services = []
        for name, service in service_registry.services.items():
            services.append({
                "name": name,
                "description": service.description,
                "usage": service.usage,
                "operations": ops_count.get(name, len(service.operations))
            })

        return JSONResponse({
            "success": True,
            "data": services
        })

    except Exception as e:
        logger.error(f"获取服务列表失败: {str(e)}")
        return JSONResponse({
            "success": False,
            "error": str(e)
        }, status_code=500)


@app.get("/api/services/{service_name}/operations")
async def get_service_operations(service_name: str):
    """
    获取指定服务的所有操作（从向量数据库）

    Args:
        service_name: 服务名称

    Returns:
        操作列表
    """
    try:
        vector_store = get_vector_store()

        # 从向量数据库获取该服务的所有操作
        all_operations = vector_store.get_all_operations(service_filter=service_name)

        # 如果向量数据库中没有，使用服务注册表作为后备
        if not all_operations:
            logger.warning(f"向量数据库中未找到服务 {service_name}，使用服务注册表作为后备")
            service = service_registry.get_service(service_name)
            if not service:
                raise HTTPException(status_code=404, detail=f"服务不存在: {service_name}")

            operations = []
            for op_name in service.operations:
                operations.append({
                    "name": op_name,
                    "description": f"{service.name} 服务的 {op_name} 操作",
                    "method": "POST",
                    "path": f"/{service.name}/{op_name}"
                })
        else:
            # 格式化向量数据库中的操作
            operations = []
            for op in all_operations:
                operations.append({
                    "name": op["operation_name"],
                    "description": op.get("description", ""),
                    "method": "POST",
                    "path": f"/{service_name}/{op['operation_name']}",
                    "document": op.get("document", "")
                })

        return JSONResponse({
            "success": True,
            "data": operations
        })

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"获取服务操作失败: {str(e)}")
        return JSONResponse({
            "success": False,
            "error": str(e)
        }, status_code=500)


@app.get("/api/executions/list")
async def list_executions(limit: int = 50):
    """
    获取执行历史列表

    Args:
        limit: 返回数量限制

    Returns:
        执行历史列表
    """
    executions = workflow_engine.list_executions(limit)
    return JSONResponse({
        "success": True,
        "data": executions
    })


@app.post("/api/workflow/save")
async def save_workflow(workflow_data: dict):
    """
    保存工作流到数据库

    Args:
        workflow_data: 工作流定义

    Returns:
        保存结果
    """
    try:
        workflow = Workflow.from_dict(workflow_data)
        # TODO: 保存到数据库

        return JSONResponse({
            "success": True,
            "data": {"workflow_id": workflow.id},
            "message": "工作流保存成功"
        })

    except Exception as e:
        logger.error(f"保存工作流失败: {str(e)}")
        return JSONResponse({
            "success": False,
            "error": str(e)
        }, status_code=500)


# ===== 向量搜索API =====

@app.get("/api/search/operations")
async def search_operations(
    query: str,
    n_results: int = 10,
    service_filter: str = None
):
    """
    向量搜索华为云服务操作

    Args:
        query: 搜索查询（自然语言或关键词）
        n_results: 返回结果数量
        service_filter: 服务过滤条件（可选）

    Returns:
        搜索结果列表
    """
    try:
        vector_store = get_vector_store()

        if not query:
            return JSONResponse({
                "success": False,
                "error": "查询不能为空"
            }, status_code=400)

        results = vector_store.search(
            query=query,
            n_results=n_results,
            service_filter=service_filter
        )

        return JSONResponse({
            "success": True,
            "data": results,
            "count": len(results)
        })

    except Exception as e:
        logger.error(f"向量搜索失败: {str(e)}")
        return JSONResponse({
            "success": False,
            "error": str(e)
        }, status_code=500)


@app.get("/api/search/stats")
async def get_vector_stats():
    """
    获取向量数据库统计信息

    Returns:
        统计信息
    """
    try:
        vector_store = get_vector_store()
        stats = vector_store.get_stats()

        return JSONResponse({
            "success": True,
            "data": stats
        })

    except Exception as e:
        logger.error(f"获取统计信息失败: {str(e)}")
        return JSONResponse({
            "success": False,
            "error": str(e)
        }, status_code=500)


@app.get("/api/search/all")
async def list_all_operations(service_filter: str = None):
    """
    获取所有操作（支持分页和过滤）

    Args:
        service_filter: 服务过滤条件（可选）

    Returns:
        操作列表
    """
    try:
        vector_store = get_vector_store()
        operations = vector_store.get_all_operations(service_filter=service_filter)

        return JSONResponse({
            "success": True,
            "data": operations,
            "count": len(operations)
        })

    except Exception as e:
        logger.error(f"获取所有操作失败: {str(e)}")
        return JSONResponse({
            "success": False,
            "error": str(e)
        }, status_code=500)


# ===== AI自动生成API =====

@app.get("/auto", response_class=HTMLResponse)
async def auto_workflow_page(request: Request):
    """AI自动生成工作流页面"""
    return templates.TemplateResponse(
        "auto_workflow.html",
        {
            "request": request,
            "llm_available": agent.is_llm_available(),
            "username": request.session.get("username", "")
        }
    )


@app.post("/api/auto/generate")
async def auto_generate_workflow(data: dict):
    """
    AI自动生成工作流

    Args:
        data: {
            requirement: str,           # 自然语言需求
            auto_execute: bool,         # 是否自动执行
            generate_explanation: bool  # 是否生成解释
        }

    Returns:
        {
            success: bool,
            workflow: dict,
            explanation: str (可选),
            execution: dict (可选)
        }
    """
    try:
        requirement = data.get('requirement', '')
        auto_execute = data.get('auto_execute', False)
        generate_explanation = data.get('generate_explanation', False)

        if not requirement:
            return JSONResponse({
                "success": False,
                "error": "需求不能为空"
            }, status_code=400)

        logger.info(f"AI自动生成工作流: {requirement}")

        # 使用Agent生成工作流
        workflow = agent.plan(requirement)

        if not workflow:
            return JSONResponse({
                "success": False,
                "error": "无法生成工作流"
            }, status_code=500)

        workflow_dict = workflow.to_dict()

        # 保存到数据库
        try:
            record_id = save_workflow_record(requirement, workflow_dict)
            logger.info(f"工作流已保存到数据库, record_id={record_id}")
        except Exception as save_err:
            logger.warning(f"保存工作流记录失败: {save_err}")
            record_id = None

        result = {
            "success": True,
            "workflow": workflow_dict,
            "record_id": record_id,
        }

        # 生成解释
        if generate_explanation:
            explanation = agent.explain(workflow)
            if explanation:
                result["explanation"] = explanation

        # 自动执行
        if auto_execute:
            logger.info("自动执行工作流...")
            execution_result = await workflow_engine.execute(workflow)
            result["execution"] = execution_result

        return JSONResponse(result)

    except Exception as e:
        logger.error(f"自动生成工作流失败: {str(e)}", exc_info=True)
        return JSONResponse({
            "success": False,
            "error": str(e),
            "message": "生成失败，请检查日志"
        }, status_code=500)


# ===== 工作流历史记录 =====

@app.get("/history", response_class=HTMLResponse)
async def workflow_history_page(request: Request):
    """工作流历史记录页面"""
    return templates.TemplateResponse(
        "workflow_history.html",
        {
            "request": request,
            "llm_available": agent.is_llm_available(),
            "username": request.session.get("username", "")
        }
    )


@app.get("/api/workflows/history")
async def api_list_workflow_history(limit: int = 50, offset: int = 0):
    """获取工作流历史记录列表"""
    try:
        data = list_workflow_records(limit=limit, offset=offset)
        return JSONResponse({"success": True, "data": data})
    except Exception as e:
        logger.error(f"获取工作流历史失败: {e}")
        return JSONResponse({"success": False, "error": str(e)}, status_code=500)


@app.get("/api/workflows/history/{record_id}")
async def api_get_workflow_record(record_id: str):
    """获取单条工作流记录详情（含完整JSON）"""
    try:
        record = get_workflow_record(record_id)
        if not record:
            return JSONResponse({"success": False, "error": "记录不存在"}, status_code=404)
        return JSONResponse({"success": True, "data": record})
    except Exception as e:
        logger.error(f"获取工作流记录失败: {e}")
        return JSONResponse({"success": False, "error": str(e)}, status_code=500)


@app.delete("/api/workflows/history/{record_id}")
async def api_delete_workflow_record(record_id: str):
    """删除工作流记录"""
    try:
        ok = delete_workflow_record(record_id)
        if not ok:
            return JSONResponse({"success": False, "error": "记录不存在"}, status_code=404)
        return JSONResponse({"success": True, "message": "已删除"})
    except Exception as e:
        logger.error(f"删除工作流记录失败: {e}")
        return JSONResponse({"success": False, "error": str(e)}, status_code=500)


@app.post("/api/workflow/validate")
async def validate_workflow(workflow_data: dict):
    """
    验证工作流定义

    Args:
        workflow_data: 工作流定义

    Returns:
        验证结果
    """
    try:
        workflow = Workflow.from_dict(workflow_data)
        errors = workflow.validate()

        return JSONResponse({
            "success": True,
            "data": {
                "valid": len(errors) == 0,
                "errors": errors
            }
        })

    except Exception as e:
        logger.error(f"验证工作流失败: {str(e)}")
        return JSONResponse({
            "success": False,
            "error": str(e)
        }, status_code=500)


# ===== 服务依赖图API =====

@app.get("/api/graph/services")
async def get_graph_services():
    """获取完整图数据（节点+边）供D3.js渲染"""
    try:
        graph_store = get_graph_store()
        if graph_store.is_connected:
            data = graph_store.get_all_nodes_and_edges()
            if data["nodes"]:
                return JSONResponse({"success": True, "data": data})

        # 降级到Analyzer
        analyzer = get_analyzer()
        return JSONResponse({
            "success": True,
            "data": {
                "nodes": analyzer.get_all_nodes(),
                "edges": analyzer.get_all_edges(),
            },
            "source": "analyzer",
        })
    except Exception as e:
        logger.error(f"获取图数据失败: {e}")
        return JSONResponse({"success": False, "error": str(e)}, status_code=500)


@app.get("/api/graph/service/{name}/dependencies")
async def get_service_graph_dependencies(name: str):
    """获取单个服务的上下游依赖"""
    try:
        graph_store = get_graph_store()
        if graph_store.is_connected:
            data = graph_store.get_service_dependencies(name)
            if data and "error" not in data:
                return JSONResponse({"success": True, "data": data})

        # 降级到Analyzer
        analyzer = get_analyzer()
        data = analyzer.get_service_dependencies(name)
        if "error" in data:
            return JSONResponse({"success": False, "error": data["error"]}, status_code=404)
        return JSONResponse({"success": True, "data": data, "source": "analyzer"})
    except Exception as e:
        logger.error(f"获取服务依赖失败: {e}")
        return JSONResponse({"success": False, "error": str(e)}, status_code=500)


@app.get("/api/graph/stats")
async def get_graph_stats():
    """获取图统计信息"""
    try:
        graph_store = get_graph_store()
        analyzer = get_analyzer()
        analyzer_stats = analyzer.get_stats()

        if graph_store.is_connected:
            neo4j_stats = graph_store.get_stats()
            analyzer_stats["neo4j_connected"] = True
            analyzer_stats["neo4j_stats"] = neo4j_stats
        else:
            analyzer_stats["neo4j_connected"] = False

        return JSONResponse({"success": True, "data": analyzer_stats})
    except Exception as e:
        logger.error(f"获取图统计失败: {e}")
        return JSONResponse({"success": False, "error": str(e)}, status_code=500)


@app.post("/api/graph/refresh")
async def refresh_graph():
    """重新分析并刷新图数据"""
    try:
        analyzer = get_analyzer()
        graph_store = get_graph_store()

        if graph_store.is_connected:
            graph_store.clear_all()
            graph_store.populate_from_analyzer(analyzer)
            return JSONResponse({"success": True, "message": "图数据已刷新（Neo4j）"})
        else:
            return JSONResponse({"success": True, "message": "图数据已刷新（Analyzer内存模式）"})
    except Exception as e:
        logger.error(f"刷新图数据失败: {e}")
        return JSONResponse({"success": False, "error": str(e)}, status_code=500)


# ===== 设置页面 =====

@app.get("/settings", response_class=HTMLResponse)
async def settings_page(request: Request):
    """设置入口页"""
    hw_config = config.get_huaweicloud_config()
    agent_config = config.get('agent', {})
    examples = agent_config.get('examples', []) if agent_config else []
    return templates.TemplateResponse(
        "settings.html",
        {
            "request": request,
            "llm_available": agent.is_llm_available(),
            "hw_ak_configured": bool(hw_config.get('ak')),
            "examples_count": len(examples),
            "username": request.session.get("username", "")
        }
    )


@app.get("/settings/llm", response_class=HTMLResponse)
async def settings_llm_page(request: Request):
    """LLM & 云认证配置页面"""
    llm_config = config.get_llm_config()
    hw_config = config.get_huaweicloud_config()
    return templates.TemplateResponse(
        "settings_llm.html",
        {
            "request": request,
            "llm_available": agent.is_llm_available(),
            "llm_config": llm_config,
            "hw_config": hw_config,
            "username": request.session.get("username", "")
        }
    )


@app.get("/settings/prompt", response_class=HTMLResponse)
async def settings_prompt_page(request: Request):
    """Prompt模板配置页面"""
    agent_config = config.get('agent', {})
    return templates.TemplateResponse(
        "settings_prompt.html",
        {
            "request": request,
            "llm_available": agent.is_llm_available(),
            "agent_config": agent_config,
            "username": request.session.get("username", "")
        }
    )


@app.get("/api/settings/llm")
async def get_llm_settings():
    """获取当前LLM配置"""
    llm_config = config.get_llm_config()
    # 脱敏API Key
    api_key = llm_config.get('api_key', '')
    masked_key = ''
    if api_key:
        masked_key = api_key[:8] + '***' + api_key[-4:] if len(api_key) > 12 else '***'
    return JSONResponse({
        "success": True,
        "data": {
            "provider": llm_config.get('provider', ''),
            "endpoint": llm_config.get('endpoint', ''),
            "model": llm_config.get('model', ''),
            "max_tokens": llm_config.get('max_tokens', 4096),
            "temperature": llm_config.get('temperature', 0.1),
            "api_key_masked": masked_key,
            "is_available": agent.is_llm_available()
        }
    })


@app.post("/api/settings/llm")
async def update_llm_settings(data: dict):
    """更新LLM配置并重新初始化客户端"""
    try:
        allowed_fields = ['provider', 'api_key', 'endpoint', 'model', 'max_tokens', 'temperature']
        for field in allowed_fields:
            if field in data:
                value = data[field]
                if field == 'max_tokens':
                    value = int(value)
                elif field == 'temperature':
                    value = float(value)
                config.set(f'llm.{field}', value)

        config.save()
        config.reload()

        # 重新初始化LLM客户端
        agent.llm_client.reinitialize()

        logger.info(f"LLM配置已更新: provider={config.get('llm.provider')}, model={config.get('llm.model')}")

        return JSONResponse({
            "success": True,
            "message": "LLM配置已更新",
            "is_available": agent.is_llm_available()
        })
    except Exception as e:
        logger.error(f"更新LLM配置失败: {str(e)}")
        return JSONResponse({
            "success": False,
            "error": str(e)
        }, status_code=500)


@app.post("/api/settings/llm/test")
async def test_llm_connection():
    """测试LLM连接"""
    try:
        if not agent.is_llm_available():
            return JSONResponse({
                "success": False,
                "error": "LLM客户端未初始化，请检查配置"
            })

        llm_client = agent.llm_client
        llm_config = config.get_llm_config()
        max_tokens = llm_config.get('max_tokens', 4096)
        temperature = llm_config.get('temperature', 0.1)

        if llm_client.provider in ('openai', 'custom'):
            response = llm_client.client.chat.completions.create(
                model=llm_client.model,
                messages=[{"role": "user", "content": "请回复：连接成功"}],
                max_tokens=min(max_tokens, 64),
                temperature=temperature
            )
            reply = response.choices[0].message.content
        elif llm_client.provider == 'anthropic':
            response = llm_client.client.messages.create(
                model=llm_client.model,
                max_tokens=min(max_tokens, 64),
                temperature=temperature,
                messages=[{"role": "user", "content": "请回复：连接成功"}]
            )
            reply = response.content[0].text
        else:
            return JSONResponse({"success": False, "error": f"不支持的提供商: {llm_client.provider}"})

        return JSONResponse({
            "success": True,
            "message": "连接测试成功",
            "reply": reply
        })
    except Exception as e:
        logger.error(f"LLM连接测试失败: {str(e)}")
        return JSONResponse({
            "success": False,
            "error": str(e)
        })


@app.post("/api/settings/huaweicloud")
async def update_huaweicloud_settings(data: dict):
    """更新华为云认证配置"""
    try:
        allowed_fields = ['ak', 'sk', 'region', 'project_id']
        for field in allowed_fields:
            if field in data:
                config.set(f'huaweicloud.{field}', data[field])

        config.save()
        config.reload()

        logger.info(f"华为云配置已更新: region={config.get('huaweicloud.region')}")

        return JSONResponse({
            "success": True,
            "message": "华为云配置已更新"
        })
    except Exception as e:
        logger.error(f"更新华为云配置失败: {str(e)}")
        return JSONResponse({
            "success": False,
            "error": str(e)
        }, status_code=500)


@app.get("/api/settings/prompt")
async def get_prompt_settings():
    """获取Prompt模板配置"""
    agent_config = config.get('agent', {})
    return JSONResponse({
        "success": True,
        "data": {
            "system_prompt": agent_config.get('system_prompt', ''),
            "examples": agent_config.get('examples', [])
        }
    })


@app.post("/api/settings/prompt")
async def update_prompt_settings(data: dict):
    """更新Prompt模板配置"""
    try:
        if 'system_prompt' in data:
            config.set('agent.system_prompt', data['system_prompt'])
        if 'examples' in data:
            config.set('agent.examples', data['examples'])

        config.save()
        config.reload()

        logger.info("Prompt模板配置已更新")
        return JSONResponse({
            "success": True,
            "message": "Prompt模板已更新"
        })
    except Exception as e:
        logger.error(f"更新Prompt模板失败: {str(e)}")
        return JSONResponse({
            "success": False,
            "error": str(e)
        }, status_code=500)


@app.get("/api/settings/prompt/preview")
async def preview_assembled_prompt():
    """预览组装后的完整Prompt"""
    try:
        full_prompt = agent.llm_client.get_assembled_prompt()
        return JSONResponse({
            "success": True,
            "data": full_prompt
        })
    except Exception as e:
        logger.error(f"预览Prompt失败: {str(e)}")
        return JSONResponse({
            "success": False,
            "error": str(e)
        }, status_code=500)


if __name__ == "__main__":
    server_config = config.get_server_config()

    uvicorn.run(
        "main:app",
        host=server_config.get('host', '0.0.0.0'),
        port=server_config.get('port', 8000),
        log_level=server_config.get('log_level', 'info')
    )
