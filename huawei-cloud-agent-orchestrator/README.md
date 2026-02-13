# 华为云Agent编排系统

基于华为云全量API的智能云资源编排和自动化部署平台，支持通过自然语言描述自动生成和执行工作流。

## 核心功能

### 1. 智能工作流生成
- **自然语言理解**: 通过AI理解用户需求，自动生成工作流
- **模板匹配**: 内置常用场景模板（Web应用部署、ECS创建、数据库创建等）
- **规则引擎**: 场景识别和参数提取

### 2. 可视化工作流设计器
- **拖拽式设计**: 支持从服务列表拖拽创建任务节点
- **图形化界面**: 直观的节点连接和依赖关系展示
- **参数编辑**: 可视化编辑任务参数和变量
- **实时验证**: 工作流合法性检查和验证

### 3. 工作流执行引擎
- **任务调度**: 智能调度任务执行顺序
- **依赖管理**: 自动处理任务依赖关系
- **错误处理**: 支持重试和失败策略
- **状态追踪**: 实时追踪任务执行状态

### 4. 华为云服务集成
- **全量服务支持**: 集成华为云190+个云服务的SDK
- **统一调用**: 统一的API调用和认证机制
- **动态注册**: 自动发现可用服务和操作

## 技术架构

```
┌─────────────────────────────────────────────┐
│          Web前端界面                        │
│    (HTML5, CSS3, JavaScript, Bootstrap)    │
└──────────────────┬──────────────────────────┘
                   │
┌──────────────────▼──────────────────────────┐
│          FastAPI Web服务                    │
│    (RESTful API, Jinja2模板)              │
└──────────────────┬──────────────────────────┘
                   │
┌──────────────────▼──────────────────────────┐
│       Agent编排引擎                          │
│   (需求分析, 工作流生成, 场景匹配)         │
└──────────────────┬──────────────────────────┘
                   │
┌──────────────────▼──────────────────────────┐
│       Workflow执行引擎                       │
│   (任务调度, 状态管理, 错误重试)           │
└──────────────────┬──────────────────────────┘
                   │
┌──────────────────▼──────────────────────────┐
│       Task执行器                             │
│   (华为云API调用, 动态客户端)              │
└──────────────────┬──────────────────────────┘
                   │
┌──────────────────▼──────────────────────────┐
│     华为云服务注册中心                        │
│  (动态服务发现, API图谱构建)                 │
└─────────────────────────────────────────────┘
```

## 支持的华为云服务

### 计算服务
- **ECS**: 弹性云服务器 (创建、查询、删除实例)
- **CCE**: 云容器引擎 (容器集群管理)
- **FunctionGraph**: 函数计算

### 网络服务
- **VPC**: 虚拟私有云 (VPC、子网、安全组)
- **ELB**: 弹性负载均衡
- **NAT**: NAT网关

### 存储服务
- **OBS**: 对象存储服务
- **EVS**: 云硬盘
- **SFS Turbo**: 文件存储

### 数据库服务
- **RDS**: 关系型数据库 (MySQL, PostgreSQL, SQLServer)
- **GaussDB**: 华为自研数据库

### 其他服务
- **IAM**: 身份认证管理
- **CDN**: 内容分发网络
- **DDoS**: DDoS防护
- ... 更多190+个服务

## 使用场景示例

### 1. Web应用一键部署
**自然语言描述**: `"部署一个Web应用，包括VPC、ECS实例和MySQL数据库"`

**自动生成的工作流**:
1. 创建VPC网络
2. 创建子网
3. 创建安全组并添加规则
4. 创建ECS实例
5. 创建RDS数据库实例
6. 返回所有资源信息

### 2. 快速创建ECS实例
**自然语言描述**: `"创建一台2核4G的ECS服务器，使用CentOS 7.9镜像"`

**自动生成的工作流**:
1. 创建ECS实例
2. 配置网络和磁盘
3. 等待实例就绪
4. 返回实例详细信息

### 3. 数据库环境搭建
**自然语言描述**: `"创建一个MySQL 8.0数据库，规格4核8G，100GB存储"`

**自动生成的工作流**:
1. 创建RDS实例
2. 配置数据库参数
3. 创建默认数据库和用户
4. 返回连接信息

## 安装和部署

### 前置条件

- Python 3.7+
- 华为云账号和Access Key
- pip包管理器

### 安装步骤

1. **克隆项目**
```bash
cd /root/huawei-service-agent
git clone https://github.com/huaweicloud/huaweicloud-sdk-python-v3.git
cd huawei-cloud-agent-orchestrator
```

2. **配置认证信息**
```bash
# 设置环境变量
export HUAWEICLOUD_SDK_AK="your-access-key"
export HUAWEICLOUD_SDK_SK="your-secret-key"
```

3. **安装依赖**
```bash
pip install -r requirements.txt
```

4. **启动应用**
```bash
python main.py
```

5. **访问Web界面**
```
http://localhost:8000
```

## API接口

### 工作流相关

#### 生成工作流
```http
POST /api/workflow/generate
Content-Type: application/x-www-form-urlencoded

requirement=部署一个Web应用，包含ECS和RDS
```

**响应**:
```json
{
  "success": true,
  "data": {
    "id": "xxx",
    "name": "部署Web应用",
    "tasks": [...]
  }
}
```

#### 执行工作流
```http
POST /api/workflow/execute
Content-Type: application/json

{
  "name": "工作流名称",
  "tasks": [...]
}
```

#### 验证工作流
```http
POST /api/workflow/validate
Content-Type: application/json

{
  "name": "工作流名称",
  "tasks": [...]
}
```

### 服务管理

#### 获取服务列表
```http
GET /api/services/list
```

#### 获取服务操作列表
```http
GET /api/services/{service_name}/operations
```

### 执行查询

#### 获取执行状态
```http
GET /api/workflow/{workflow_id}/status
```

#### 获取执行历史
```http
GET /api/executions/list?limit=50
```

## Web界面操作指南

### 主页操作
1. **输入需求**: 在文本框中描述您的部署需求
2. **生成工作流**: 点击"AI生成工作流"按钮
3. **选择模板**: 或点击预设模板快速开始
4. **手动设计**: 点击"手动设计"直接进入设计器

### 工作流设计器
1. **添加任务**: 从左侧拖拽服务或任务到画布
2. **配置参数**: 点击任务节点，在右侧编辑属性
3. **设置依赖**: 在属性面板中选择依赖的任务
4. **验证工作流**: 点击"验证工作流"检查错误
5. **执行工作流**: 点击"执行工作流"开始部署

### 监控中心
- 查看执行状态和进度
- 查看任务日志和输出
- 管理历史执行记录

## 变量和参数模板

### 占位符语法
工作流中的参数支持使用占位符引用变量和其他任务的输出：

- `{{ variables.xxx }}` - 引用工作流变量
- `{{ outputs.task_name.xxx }}` - 引用其他任务的输出

### 示例
```json
{
  "parameters": {
    "vpc_id": "{{ variables.vpc_id }}",
    "subnet_id": "{{ outputs.create_subnet.subnet.id }}",
    "name": "web-server-{{ variables.instance_name }}"
  }
}
```

## 高级功能

### 条件执行
```json
{
  "condition": "{{ variables.create_vpc }} == true"
}
```

### 失败重试
```json
{
  "retry_policy": {
    "max_attempts": 3,
    "backoff": "exponential"
  }
}
```

### 超时设置
```json
{
  "timeout": 600  // 秒
}
```

## 项目结构

```
huawei-cloud-agent-orchestrator/
├── main.py                         # FastAPI应用入口
├── agents/
│   └── orchestration_agent.py      # Agent编排引擎
├── services/
│   ├── huawei_cloud_service_registry.py  # 服务注册中心
│   ├── workflow_engine.py          # 工作流执行引擎
│   └── task_executor.py            # 任务执行器
├── models/
│   └── workflow.py                 # 数据模型
├── templates/
│   ├── index.html                  # 主页
│   └── workflow_designer.html      # 工作流设计器
├── static/
│   ├── css/
│   │   └── style.css               # 样式文件
│   └── js/
│       ├── main.js                 # 主页面脚本
│       └── workflow_designer.js    # 设计器脚本
├── utils/
│   └── logger.py                   # 日志工具
└── requirements.txt                # Python依赖
```

## 贡献和反馈

欢迎提交Issue和Pull Request！

## 相关资源

- [华为云Python SDK文档](https://github.com/huaweicloud/huaweicloud-sdk-python-v3)
- [华为云API Explorer](https://console.huaweicloud.com/apiexplorer/)
- [工作流模型参考](https://json.org/)

## 版本信息

- **v1.0.0** - 初始版本
  - 基础工作流引擎
  - Web可视化设计器
  - 华为云服务集成

## 致谢

- 华为云SDK开发团队
- FastAPI团队

## 许可证

Apache License 2.0

---

**注意**: 这是一个示例项目，使用时请根据实际情况配置认证信息和网络环境。
