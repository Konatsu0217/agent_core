# Agent Core - Src 目录结构说明

本项目采用**领域驱动设计(DDD)**的思想重新组织代码结构，从传统的技术分层（clients、handlers、utils）转向按业务领域划分。

## 📁 目录结构

```
src/
├── agent/                      # Agent核心领域
│   ├── __init__.py
│   ├── abs_agent.py           # Agent抽象基类
│   ├── fast_agent.py          # 快速Agent实现
│   ├── one_shot_agent.py      # 单次Agent实现
│   ├── react_agent.py         # ReAct Agent实现
│   ├── plan_and_solve_agent.py # Plan-and-Solve Agent实现
│   └── basic_work_flow.py     # 基础工作流
│
├── infrastructure/            # 基础设施层
│   ├── clients/               # 外部服务客户端
│   │   ├── __init__.py
│   │   ├── llm_client.py      # LLM客户端
│   │   ├── mcp_client.py      # MCP Hub客户端
│   │   ├── mem0ai_client.py   # 记忆管理客户端
│   │   ├── pe_client.py       # PE Server客户端
│   │   ├── session_manager.py # 会话管理器
│   │   └── bilibili_live_client/ # B站直播客户端
│   │
│   └── handlers/              # 特殊处理器
│       ├── __init__.py
│       ├── tts_handler.py     # TTS处理器
│       └── vrma_handler.py    # VRMA处理器
│
├── domain/                    # 领域层
│   └── models/                # 领域模型
│       ├── __init__.py
│       ├── agent_data_models.py    # Agent数据模型
│       └── danmaku_models.py       # 弹幕数据模型
│
├── interfaces/                # 接口层
│   ├── api/                   # REST API路由
│   │   ├── __init__.py
│   │   └── routes.py          # API路由定义
│   │
│   └── websocket/             # WebSocket处理
│       ├── __init__.py
│       └── handler.py         # WebSocket处理器
│
└── shared/                    # 共享模块
    ├── config/                # 配置管理
    │   ├── __init__.py
    │   ├── config_manager.py  # 配置管理器
    │   └── config_schemas.py  # 配置模式定义
    │
    ├── logging/               # 日志管理
    │   ├── __init__.py
    │   └── logger.py          # 日志配置
    │
    └── utils/                 # 工具函数
        ├── __init__.py
        └── connet_manager.py  # 连接管理器
```

## 🎯 设计原则

### 1. 按业务领域划分
- **agent/**: 核心业务逻辑，包含各种Agent的实现
- **infrastructure/**: 外部依赖，如LLM客户端、WebSocket等
- **domain/**: 领域模型，不依赖任何基础设施
- **interfaces/**: 对外接口，API和WebSocket
- **shared/**: 横切关注点，配置、日志、工具函数

### 2. 依赖方向
```
interfaces → agent → domain
interfaces → infrastructure → domain
shared → (被所有层使用)
```

### 3. 导入规范
```python
# ✅ 正确：从src开始绝对导入
from src.agent.fast_agent import FastAgent
from src.infrastructure.clients.llm_client import LLMClientManager
from src.domain.models.agent_data_models import AgentRequest
from src.shared.config.config_manager import ConfigManager

# ❌ 错误：相对导入
from ..agent.fast_agent import FastAgent
from ...infrastructure.clients.llm_client import LLMClientManager
```

## 📦 模块职责

### agent/
- **职责**: 实现各种Agent的核心逻辑
- **包含**: FastAgent、ReActAgent、PlanAndSolveAgent等
- **依赖**: infrastructure（LLM、MCP等）、domain（数据模型）

### infrastructure/
- **职责**: 封装外部服务和基础设施
- **包含**: LLM客户端、WebSocket管理、TTS/VRMA处理器
- **依赖**: domain（数据模型）、shared（配置、日志）

### domain/
- **职责**: 定义领域模型和业务规则
- **包含**: AgentRequest、AgentResponse、DanmakuData等
- **依赖**: 无（最底层）

### interfaces/
- **职责**: 对外暴露接口，处理HTTP请求和WebSocket连接
- **包含**: REST API路由、WebSocket处理器
- **依赖**: agent、infrastructure、domain

### shared/
- **职责**: 提供跨层共享的功能
- **包含**: 配置管理、日志、工具函数
- **依赖**: 无（最底层）

## 🔄 迁移对照表

| 旧路径 | 新路径 | 状态 |
|--------|--------|------|
| `core/` | `src/agent/` | ✅ 已完成 |
| `clients/` | `src/infrastructure/clients/` | ✅ 已完成 |
| `handlers/` | `src/infrastructure/handlers/` | ✅ 已完成 |
| `models/` | `src/domain/models/` | ✅ 已完成 |
| `utils/` | `src/shared/` (按类型细分) | ✅ 已完成 |
| 旧目录删除 | `core/`, `clients/`, `handlers/`, `models/`, `utils/` | ✅ 已完成 |

## 💡 Java/Kotlin开发者适配指南

### 1. 包结构对比
```java
// Java风格
com.example.agent.core
com.example.agent.infrastructure.clients
com.example.agent.domain.models
com.example.agent.interfaces.api
com.example.agent.shared.config
```

```python
# Python风格（本项目）
src.agent
src.infrastructure.clients
src.domain.models
src.interfaces.api
src.shared.config
```

### 2. 导入方式
```java
// Java
import com.example.agent.core.FastAgent;
import com.example.agent.domain.models.AgentRequest;
```

```python
# Python
from src.agent.fast_agent import FastAgent
from src.domain.models.agent_data_models import AgentRequest
```

### 3. 类型提示
```python
# 添加类型提示，让代码更接近Java的静态类型
from typing import Optional, List
from pydantic import BaseModel

class AgentRequest(BaseModel):
    query: str
    session_id: str
    images_b64: Optional[List[str]] = None
```

## 🚀 后续优化建议

### 高优先级
1. **拆分独立项目**: 将`tools/`下的子项目移到独立仓库
2. **统一配置管理**: 将分散的配置文件整合
3. **完善类型提示**: 为所有函数添加类型注解

### 中优先级
4. **添加单元测试**: 为每个模块编写测试
5. **文档完善**: 补充API文档和架构文档
6. **性能优化**: 优化LLM调用和WebSocket处理

### 低优先级
7. **代码风格统一**: 使用black、isort等工具统一代码风格
8. **CI/CD配置**: 添加自动化测试和部署流程

## 📝 注意事项

1. **已完成迁移**: 所有旧目录（`core/`、`clients/`、`handlers/`、`models/`、`utils/`）已删除
2. **使用新结构**: 所有代码现在都使用新的`src/`目录结构
3. **测试验证**: 每次修改后都要运行测试确保功能正常
4. **文档更新**: 及时更新README和相关文档

## 🔗 相关文档

- [agent_core_guide.md](../doc/agent_core_guide.md) - Agent核心指南
- [agent_paradigms_guide.md](../doc/agent_paradigms_guide.md) - Agent范式指南
- [moe_agent_architecture.md](../doc/moe_agent_architecture.md) - MoE Agent架构
