# Huawei Cloud Agent Orchestrator

基于大语言模型的华为云智能编排与自动化部署平台。用户可通过自然语言描述基础设施需求，系统自动生成并执行工作流，完成云资源的创建与配置。

## 功能特性

- **自然语言驱动**：通过 LLM 解析用户需求，自动生成可执行的工作流
- **可视化工作流设计器**：拖拽式界面构建工作流，支持节点连接与依赖可视化
- **智能工作流执行引擎**：自动任务调度、依赖管理、错误重试与状态追踪
- **190+ 华为云服务支持**：覆盖计算、网络、存储、数据库、安全等全品类服务
- **语义化服务检索**：基于向量数据库的 API 操作语义搜索
- **多 LLM 提供商支持**：兼容 Anthropic、OpenAI、HuggingFace 及自定义接口

## 架构概览

```
Web Frontend (HTML5/CSS3/JS)
        │
FastAPI Web Service (RESTful API)
        │
LLM Orchestration Agent (需求分析 & 工作流生成)
        │
Workflow Execution Engine (任务调度 & 状态管理)
        │
Task Executor (华为云 API 调用)
        │
Service Registry & Vector Database (服务发现 & 语义检索)
```

## 技术栈

| 层级 | 技术 |
|------|------|
| Web 框架 | FastAPI + Uvicorn |
| 数据库 | SQLAlchemy + aiosqlite |
| 向量数据库 | Chromadb |
| Embedding | sentence-transformers |
| 华为云 SDK | huaweicloudsdkcore 3.0+ |
| 前端 | Jinja2 + Bootstrap + JavaScript |
| LLM | Anthropic / OpenAI / HuggingFace / Custom |

## 快速开始

### 环境要求

- Python 3.7+
- 华为云账号（Access Key & Secret Key）

### 安装

```bash
cd huawei-cloud-agent-orchestrator
pip install -r requirements.txt
```

### 配置

编辑 `config.yaml` 或通过 Web 界面配置：

- **LLM 配置**：提供商、API Key、模型名称
- **华为云凭证**：AK / SK / Region / Project ID

也可通过环境变量设置华为云凭证：

```bash
export HUAWEICLOUD_SDK_AK="your-access-key"
export HUAWEICLOUD_SDK_SK="your-secret-key"
```

### 启动

```bash
python main.py
# 或
bash start.sh
```

访问 `http://localhost:8000` 进入 Web 界面。

## 使用示例

**输入**：「部署一个 Web 应用，包含 VPC、ECS 实例和 MySQL 数据库」

**自动生成工作流**：
1. 创建 VPC 网络
2. 创建子网
3. 创建安全组及规则
4. 创建 ECS 实例
5. 创建 RDS MySQL 实例
6. 返回资源信息

## 支持的华为云服务

| 类别 | 服务 |
|------|------|
| 计算 | ECS、CCE、FunctionGraph |
| 网络 | VPC、ELB、NAT Gateway、DNS |
| 存储 | OBS、EVS、SFS Turbo |
| 数据库 | RDS、GaussDB |
| 安全 | IAM、KMS、WAF、CTS |
| 监控 | CES、LTS、SMN、APM |
| 其他 | CDN、DDoS 防护、SSL 证书等 190+ 服务 |

## 项目结构

```
huawei-cloud-agent-orchestrator/
├── main.py                          # 应用入口
├── config.yaml                      # 配置文件
├── requirements.txt                 # Python 依赖
├── start.sh                         # 启动脚本
├── agents/                          # LLM 编排代理
├── services/                        # 核心服务（工作流引擎、任务执行、服务注册）
├── models/                          # 数据模型
├── utils/                           # 工具类（配置、向量存储、数据库、认证）
├── templates/                       # Jinja2 页面模板
├── static/                          # 前端静态资源
├── data/                            # 向量数据库 & SQLite 数据
└── logs/                            # 应用日志
```

## Web 界面

| 页面 | 路径 | 说明 |
|------|------|------|
| 首页 | `/` | 工作流生成主界面 |
| 工作流设计器 | `/designer` | 可视化拖拽设计 |
| 智能生成 | `/auto` | AI 自动生成并执行 |
| 服务列表 | `/services` | 浏览可用云服务 |
| 执行监控 | `/monitor` | 实时执行状态 |
| 历史记录 | `/history` | 查看历史工作流 |
| 设置 | `/settings` | LLM 与云凭证配置 |

## License

MIT
