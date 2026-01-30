# 配置使用与覆盖策略

## 目录结构

- `config/core.json`：Agent Core 主配置
- `config/pe.json`：Prompt Engine(PE) 配置
- `config/mcp_servers.json|yaml`：MCP Hub 服务器列表
- `config/tts.json`：TTS 引擎配置
- `config/motion.json`：运动/VRMA 相关配置
- `config/api.key`：可选的密钥文件（仅示例，不应提交真实值）
- `src/agent/agent_profiles/`：Agent 配置文件目录

## 加载与覆盖顺序

### 全局配置（`config/core.json`）
1. 内置默认值
2. 配置文件（`config/*.json|yaml`）
3. `.env`/环境变量（如 `BACKBONE_LLM_API_KEY`, `OPENAI_API_KEY`, `MCP_CONFIG_FILE`）
4. 命令行参数（目前 MCP Hub 支持 `--config` 指定）

### Agent 配置（`src/agent/agent_profiles/*.json`）
1. Agent profile 中的配置（优先使用）
2. 全局配置（作为后备）

## 安全

- 不在代码或仓库中存放真实密钥；使用环境变量或 `config/api.key`
- 前端不包含敏感字段，后端 `/config` 仅返回非敏感摘要

## 迁移说明

- 旧文件（`pe_config.json`, `tools/.../pe_config.json`, `tools/tts/tts_config.json`, `tools/motion_drive/motion_config.json`, `mcp_servers_config.json`）已移除，统一迁移到 `config/` 下
- MCP Hub 默认搜索路径已更新为 `config/mcp_servers.json|yaml`

## Agent Profile 中的 Backbone LLM 配置

现在可以在每个 Agent 的 profile 中定义独立的 `backbone_llm_config`，使每个 Agent 可以使用不同的 LLM 配置。

### 示例配置

```json
{
  "agent_id": "fast_agent_v1",
  "name": "fast_agent",
  "version": "1.0",
  "agent_type": "combined",
  "work_flow_type": "test",
  
  "backbone_llm_config": {
    "openapi_url": "https://api.siliconflow.cn/v1",
    "openapi_key": "",
    "model_name": "Qwen/Qwen3-14B",
    "temperature": 0.7,
    "max_tokens": 1024
  },
  
  "services_needed": [
    ["tool_manager", "set_tool_manager"],
    ["memory_service", "set_memory_service"],
    ["prompt_service", null],
    ["session_service", null],
    ["query_wrapper", null]
  ],
  
  "prompt_config": {
    // 提示词配置...
  }
}
```

### 配置说明

- `openapi_url`：LLM API 的基础 URL
- `openapi_key`：LLM API 的密钥（建议使用环境变量或 `config/api.key`）
- `model_name`：使用的 LLM 模型名称
- `temperature`：生成文本的随机性
- `max_tokens`：生成文本的最大长度

### 向后兼容性

- 如果 Agent profile 中没有定义 `backbone_llm_config`，将使用全局配置作为后备
- 全局配置仍然可以通过 `config/core.json` 或环境变量设置

## 示例环境变量

见 `.env.example`

