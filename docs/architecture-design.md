# 华为云智能编排平台 — 架构设计书

> 版本：v1.0
> 更新日期：2026-02-13

---

## 1. 系统概述

### 1.1 设计目标

构建一个以大语言模型为核心的华为云资源编排平台，实现从自然语言需求到云资源部署的端到端自动化。

### 1.2 设计原则

| 原则 | 说明 |
|------|------|
| 智能优先，规则兜底 | LLM 驱动主流程，规则引擎作为降级方案 |
| 松耦合 | 各组件通过接口交互，可独立替换 |
| 可扩展 | 新增云服务仅需注册，无需修改核心逻辑 |
| 容错设计 | 多级重试、校验纠错、降级策略 |

---

## 2. 系统架构

### 2.1 整体架构

```
┌─────────────────────────────────────────────────────────┐
│                    Web Frontend                         │
│         HTML5 / CSS3 / JavaScript / Bootstrap           │
└──────────────────────┬──────────────────────────────────┘
                       │ HTTP
┌──────────────────────▼──────────────────────────────────┐
│                  FastAPI Application                    │
│  ┌──────────┐  ┌──────────────┐  ┌──────────────────┐  │
│  │ Auth     │  │ Session      │  │ Static File      │  │
│  │ Middleware│  │ Middleware   │  │ Serving          │  │
│  └──────────┘  └──────────────┘  └──────────────────┘  │
│  ┌──────────────────────────────────────────────────┐   │
│  │              REST API Layer (40+ endpoints)      │   │
│  └──────────────────────┬───────────────────────────┘   │
└─────────────────────────┼───────────────────────────────┘
                          │
         ┌────────────────┼────────────────┐
         ▼                ▼                ▼
┌─────────────────┐ ┌──────────┐ ┌─────────────────┐
│ LLM Orchestration│ │ Workflow │ │ Config Manager  │
│ Agent            │ │ Engine   │ │                 │
│                  │ │          │ │                 │
│ ┌──────────────┐│ │┌────────┐│ │ ┌─────────────┐ │
│ │ LLM Client   ││ ││ Task   ││ │ │ config.yaml │ │
│ │ (多提供商)    ││ ││Executor││ │ └─────────────┘ │
│ └──────────────┘│ │└────────┘│ └─────────────────┘
│ ┌──────────────┐│ └──────────┘
│ │ Vector Store ││
│ │ (ChromaDB)   ││
│ └──────────────┘│
│ ┌──────────────┐│
│ │ Service      ││
│ │ Registry     ││
│ └──────────────┘│
└─────────────────┘
         │                │
         ▼                ▼
┌─────────────────┐ ┌──────────────────┐
│ LLM Provider    │ │ Huawei Cloud SDK │
│ (Anthropic /    │ │ (190+ Services)  │
│  OpenAI / Custom)│ │                  │
└─────────────────┘ └──────────────────┘
```

### 2.2 分层架构

| 层级 | 组件 | 职责 |
|------|------|------|
| 表现层 | Web Frontend + Jinja2 Templates | 用户交互、工作流可视化 |
| 接口层 | FastAPI REST API | 请求路由、认证鉴权、参数校验 |
| 业务层 | LLM Orchestration Agent | 需求分析、架构规划、工作流生成 |
| 执行层 | Workflow Engine + Task Executor | 任务调度、依赖管理、API 调用 |
| 数据层 | SQLite + ChromaDB | 工作流持久化、语义检索 |
| 基础设施层 | Huawei Cloud SDK + LLM API | 云资源操作、模型推理 |

---

## 3. 核心组件设计

### 3.1 LLM 编排代理（LLMOrchestrationAgent）

**职责**：将自然语言需求转化为可执行的工作流定义。

**四阶段流水线架构**：

```
用户需求
  │
  ▼
┌─────────────────────────────────────┐
│ Stage 0: 架构规划                    │
│ LLM → 部署模式 / DFX等级 / 服务列表  │
│        / 依赖图                      │
│ 失败时降级 → identify_required_ops   │
└──────────────┬──────────────────────┘
               ▼
┌─────────────────────────────────────┐
│ Stage 1: 语义检索                    │
│ 精确检索: search_by_service_ops()   │
│ 降级: search() 广泛语义搜索          │
└──────────────┬──────────────────────┘
               ▼
┌─────────────────────────────────────┐
│ Stage 2: 模板匹配                    │
│ 操作名 → PARAMETER_TEMPLATES 匹配   │
│ 输出: 精确参数结构示例               │
└──────────────┬──────────────────────┘
               ▼
┌─────────────────────────────────────┐
│ Stage 3: LLM 工作流生成              │
│ 输入: 需求 + 架构方案 + API定义      │
│       + 参数模板 + 示例工作流         │
│ 输出: 完整工作流 JSON                │
└──────────────┬──────────────────────┘
               ▼
┌─────────────────────────────────────┐
│ 校验与纠错循环                       │
│ 注册表校验 → 自动纠错 → LLM纠错     │
│ 最多重试 2 次 (指数退避)             │
└──────────────┬──────────────────────┘
               ▼
          验证通过的工作流
```

**降级策略**：当 LLM 不可用时，自动切换到基于规则的 `OrchestrationAgent`，通过关键词匹配和预定义模板生成工作流。

---

### 3.2 LLM 客户端（LLMClient）

**职责**：多提供商 LLM 抽象层，统一调用接口。

**提供商适配**：

```
LLMClient
  ├── AnthropicAdapter  → anthropic.Anthropic
  ├── OpenAIAdapter     → openai.OpenAI
  └── CustomAdapter     → openai.OpenAI(base_url=custom_endpoint)
```

**Prompt 构建策略**：

```
System Prompt
  = 基础系统提示词 (config.yaml)
  + 服务注册表摘要 (服务名 + 描述)
  + 执行流程说明

User Prompt
  = 用户需求
  + 上下文 (Region / Project / AZ)
  + 架构方案 (Stage 0 输出)
  + 相关 API 操作定义 (Stage 1 输出)
  + 参数模板 (Stage 2 输出)
  + 示例工作流 (Few-shot)
```

**JSON 修复流水线**（五级容错）：

| 级别 | 策略 | 说明 |
|------|------|------|
| L1 | 直接解析 | `json.loads()` |
| L2 | 尾逗号修复 | 移除 `}` 和 `]` 前的多余逗号 |
| L3 | 括号修复 | 基于栈的括号匹配与补全 |
| L4 | 截断修复 | 检测不完整 JSON，截取到最后完整结构 |
| L5 | json_repair | 调用第三方修复库 |

---

### 3.3 工作流执行引擎（WorkflowEngine）

**职责**：执行工作流定义，管理任务生命周期。

**执行上下文**：

```python
ExecutionContext:
  workflow_id: str          # 执行实例 ID
  variables: Dict           # 工作流变量（可变）
  outputs: Dict             # 任务输出（task_name → result）
  task_outputs: Dict        # 参数替换缓存
```

**任务调度流程**：

```
工作流输入
  │
  ▼
创建 ExecutionContext (拷贝变量, 初始化输出)
  │
  ▼
拓扑排序 (检测循环依赖)
  │
  ▼
按序执行任务 ──────────────────────┐
  │                                │
  ▼                                │
准备参数 (模板替换)                 │
  │  {{ variables.key }}           │
  │  {{ outputs.task_name.key }}   │
  ▼                                │
TaskExecutor.execute()             │
  │                                │
  ├── 成功 → 存储输出 → 下一任务 ──┘
  │
  └── 失败 → 检查重试策略
              │
              ├── 有剩余次数 → 指数退避 → 重试
              │
              └── 无剩余次数 → 标记 FAILED
```

**任务状态机**：

```
PENDING ──→ RUNNING ──→ SUCCESS
                │
                ├──→ FAILED
                ├──→ TIMEOUT
                └──→ SKIPPED (条件不满足)
```

**最终状态判定**：

```
所有任务 SUCCESS           → WorkflowStatus.SUCCESS
存在 FAILED + 存在 SUCCESS → WorkflowStatus.PARTIAL_SUCCESS
所有任务 FAILED            → WorkflowStatus.FAILED
```

---

### 3.4 任务执行器（TaskExecutor）

**职责**：动态创建华为云 SDK 客户端并执行 API 调用。

**动态客户端创建流程**：

```
服务名 (如 "ecs")
  │
  ▼
推导模块名: huaweicloudsdkecs
推导类名:   EcsClient
  │
  ▼
动态导入: importlib.import_module("huaweicloudsdkecs.v2.ecs_client")
  │
  ▼
获取类:   getattr(module, "EcsClient")
  │
  ▼
构建客户端:
  EcsClient.new_builder()
    .with_credentials(BasicCredentials(ak, sk))
    .with_region(Region)
    .build()
```

**请求对象创建**：

```
操作名 (如 "create_servers")
  │
  ▼
转换为 PascalCase: CreateServersRequest
  │
  ▼
动态导入请求类
  │
  ▼
实例化并设置参数: setattr(request, key, value)
  │
  ▼
调用: client.create_servers(request)
  │
  ▼
处理响应: response.to_dict() 或 response.__dict__
```

---

### 3.5 服务注册表（HuaweiCloudServiceRegistry）

**职责**：集中管理所有华为云服务的元数据。

**数据结构**：

```python
ServiceInfo:
  name: str              # 服务标识 (如 "ecs")
  description: str       # 服务描述
  module_name: str       # SDK 模块名 (如 "huaweicloudsdkecs")
  client_class: str      # 客户端类名 (如 "EcsClient")
  common_operations: []  # 常用操作列表
  usage: str             # 使用说明
```

**注册机制**：应用启动时一次性注册约 190 个服务，运行时通过单例模式全局访问。

---

### 3.6 向量存储（VectorStore）

**职责**：基于 ChromaDB 的语义检索引擎。

**存储架构**：

```
ChromaDB (持久化)
  └── Collection: huawei_cloud_operations
        └── Document:
              id:       "service_name:operation_name"
              content:  "服务: xxx\n操作: xxx\n描述: xxx\n输入参数: ...\n输出参数: ..."
              metadata: {service_name, operation_name, description, ...}
              embedding: all-MiniLM-L6-v2 向量
```

**检索模式**：

| 模式 | 方法 | 场景 |
|------|------|------|
| 精确检索 | `search_by_service_operations()` | Stage 0 已识别具体操作 |
| 语义检索 | `search(query)` | 广泛搜索，降级场景 |
| 服务过滤 | `search(query, service_filter)` | 限定服务范围 |
| 全量查询 | `get_all_operations()` | 服务列表展示 |

**相似度计算**：`similarity = 1 - distance`（ChromaDB 默认 L2 距离）

---

## 4. 数据架构

### 4.1 数据库设计

**SQLite — 工作流历史**

```
workflow_records
├── id: VARCHAR (PK, UUID)
├── requirement: TEXT           -- 用户原始需求
├── workflow_name: VARCHAR
├── workflow_description: TEXT
├── workflow_json: TEXT         -- 完整工作流 JSON
├── task_count: INTEGER
├── services_used: VARCHAR     -- 逗号分隔的服务列表
├── status: VARCHAR            -- generated / executed / failed
└── created_at: DATETIME
```

**ChromaDB — 向量数据库**

```
huawei_cloud_operations (Collection)
├── id: "service:operation"
├── document: 结构化文本 (用于 Embedding)
├── metadata: {service_name, operation_name, description, ...}
└── embedding: float[] (自动生成)
```

### 4.2 数据流

```
用户需求 (文本)
    │
    ├──→ LLM Provider (外部 API)
    │       └──→ 工作流 JSON
    │
    ├──→ ChromaDB (语义检索)
    │       └──→ 相关 API 操作
    │
    ├──→ SQLite (持久化)
    │       └──→ 工作流记录
    │
    └──→ Huawei Cloud SDK (API 调用)
            └──→ 云资源操作结果
```

---

## 5. 接口设计

### 5.1 API 总览

| 模块 | 端点 | 方法 | 说明 |
|------|------|------|------|
| 认证 | `/api/auth/login` | POST | 用户登录 |
| 认证 | `/api/auth/me` | GET | 当前用户信息 |
| 工作流 | `/api/workflow/generate` | POST | 自然语言生成工作流 |
| 工作流 | `/api/workflow/execute` | POST | 执行工作流 |
| 工作流 | `/api/workflow/validate` | POST | 校验工作流 |
| 工作流 | `/api/workflow/save` | POST | 保存工作流 |
| 智能生成 | `/api/auto/generate` | POST | AI 自动生成 + 执行 |
| 服务 | `/api/services/list` | GET | 服务列表 |
| 服务 | `/api/services/{name}/operations` | GET | 服务操作列表 |
| 检索 | `/api/search/operations` | GET | 语义搜索操作 |
| 检索 | `/api/search/stats` | GET | 向量库统计 |
| 历史 | `/api/workflows/history` | GET | 工作流历史 |
| 历史 | `/api/workflows/history/{id}` | GET/DELETE | 单条记录操作 |
| 执行 | `/api/executions/list` | GET | 执行历史 |
| 设置 | `/api/settings/llm` | GET/POST | LLM 配置 |
| 设置 | `/api/settings/llm/test` | POST | 测试 LLM 连接 |
| 设置 | `/api/settings/huaweicloud` | POST | 华为云凭证 |
| 设置 | `/api/settings/prompt` | GET/POST | Prompt 模板 |

### 5.2 核心接口详细设计

**POST /api/workflow/generate**

```json
// Request
{
  "requirement": "部署一个包含VPC和ECS的Web应用",
  "context": {
    "region": "cn-north-4",
    "project_id": "xxx",
    "availability_zone": "cn-north-4a"
  }
}

// Response
{
  "success": true,
  "workflow": {
    "id": "uuid",
    "name": "Web应用部署",
    "description": "...",
    "tasks": [...],
    "variables": {...}
  },
  "explanation": "该工作流将依次创建..."
}
```

**POST /api/workflow/execute**

```json
// Request
{
  "workflow": { /* 工作流 JSON */ },
  "dry_run": false
}

// Response
{
  "success": true,
  "execution_id": "uuid",
  "status": "SUCCESS",
  "report": {
    "total_tasks": 5,
    "succeeded": 5,
    "failed": 0,
    "duration": 45.2,
    "outputs": {...}
  }
}
```

---

## 6. 安全设计

### 6.1 认证机制

```
客户端请求
    │
    ▼
SessionMiddleware (签名 Cookie, 24h TTL)
    │
    ▼
AuthMiddleware
    ├── 白名单路径 → 放行 (/login, /static, /favicon.ico)
    └── 其他路径 → 校验 Session
          ├── 有效 → 注入 user 到 request.state
          └── 无效 → API: 401 JSON / 页面: 302 → /login
```

### 6.2 凭证管理

- 华为云 AK/SK 支持环境变量注入，避免明文存储
- 用户密码使用 SHA-256 哈希存储
- Session 使用 `itsdangerous` 签名，防止篡改

---

## 7. 可靠性设计

### 7.1 多级容错

| 层级 | 容错机制 |
|------|----------|
| LLM 调用 | 提供商切换、规则引擎降级 |
| 工作流生成 | 校验纠错循环（自动纠错 + LLM 纠错，最多 2 次重试） |
| JSON 解析 | 五级修复流水线 |
| 任务执行 | 可配置重试策略，指数退避 |
| 语义检索 | 精确检索失败时降级为广泛语义搜索 |

### 7.2 重试策略

```yaml
retry_policy:
  max_attempts: 3
  backoff_type: exponential
  initial_delay: 1  # 秒
  # 实际延迟: 2^attempt 秒 (1s, 2s, 4s)
```

---

## 8. 部署架构

### 8.1 单机部署

```
┌─────────────────────────────────┐
│           服务器                 │
│                                 │
│  ┌───────────────────────────┐  │
│  │ FastAPI + Uvicorn         │  │
│  │ (0.0.0.0:8000)           │  │
│  └───────────────────────────┘  │
│                                 │
│  ┌──────────┐  ┌────────────┐  │
│  │ SQLite   │  │ ChromaDB   │  │
│  │ (文件)   │  │ (文件)     │  │
│  └──────────┘  └────────────┘  │
│                                 │
│  data/                          │
│  ├── workflow_history.db        │
│  └── vector_db/                 │
└─────────────────────────────────┘
         │              │
         ▼              ▼
   LLM Provider    Huawei Cloud
   (外部 API)      (外部 API)
```

### 8.2 环境要求

| 项目 | 要求 |
|------|------|
| Python | 3.7+ |
| 内存 | 建议 4GB+（ChromaDB + sentence-transformers） |
| 磁盘 | 建议 2GB+（向量数据库 + SDK） |
| 网络 | 需访问 LLM API 和华为云 API |

---

## 9. 技术选型说明

| 组件 | 选型 | 理由 |
|------|------|------|
| Web 框架 | FastAPI | 原生异步支持、自动 API 文档、高性能 |
| 数据库 | SQLite | 嵌入式、零运维、适合单机部署 |
| 向量数据库 | ChromaDB | 嵌入式、Python 原生、开箱即用 |
| Embedding | sentence-transformers | 开源、多语言支持、本地运行 |
| 模板引擎 | Jinja2 | FastAPI 原生集成、功能丰富 |
| 配置管理 | PyYAML | 可读性强、支持复杂嵌套结构 |

---

## 10. 组件依赖关系

```
main.py (FastAPI Application)
│
├── LLMOrchestrationAgent
│   ├── LLMClient
│   │   ├── ConfigManager (Singleton)
│   │   └── ServiceRegistry (Singleton)
│   ├── VectorStore (Singleton, ChromaDB)
│   ├── ServiceRegistry (Singleton)
│   └── OrchestrationAgent (降级方案)
│
├── WorkflowEngine
│   ├── TaskExecutor
│   │   ├── Huawei Cloud SDK (动态导入)
│   │   └── ConfigManager
│   └── Logger
│
├── AuthMiddleware
│   └── Database (SQLAlchemy + aiosqlite)
│
├── ConfigManager (Singleton)
│   └── config.yaml
│
└── Database
    └── SQLite (workflow_history.db)
```

---

## 11. 关键设计模式

| 模式 | 应用位置 | 说明 |
|------|----------|------|
| 单例模式 | ConfigManager, VectorStore, ServiceRegistry, Logger | 全局唯一实例，避免重复初始化 |
| 工厂模式 | TaskExecutor | 动态创建华为云 SDK 客户端 |
| 策略模式 | LLMClient, LLMOrchestrationAgent | 多 LLM 提供商切换、LLM/规则双引擎 |
| 流水线模式 | LLMOrchestrationAgent | 四阶段工作流生成流水线 |
| 中间件模式 | AuthMiddleware, SessionMiddleware | 请求拦截与处理链 |
| 仓储模式 | Database, VectorStore | 数据访问抽象 |
| 适配器模式 | LLMClient, TaskExecutor | 统一接口适配不同后端 |
| 状态机模式 | WorkflowEngine | 任务状态流转管理 |
| 重试模式 | WorkflowEngine, LLMOrchestrationAgent | 指数退避重试 |
