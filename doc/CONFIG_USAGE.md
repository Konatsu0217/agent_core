# 配置使用与覆盖策略

## 目录结构

- `config/core.json`：Agent Core 主配置
- `config/pe.json`：Prompt Engine(PE) 配置
- `config/mcp_servers.json|yaml`：MCP Hub 服务器列表
- `config/tts.json`：TTS 引擎配置
- `config/motion.json`：运动/VRMA 相关配置
- `config/api.key`：可选的密钥文件（仅示例，不应提交真实值）

## 加载与覆盖顺序

1. 内置默认值
2. 配置文件（`config/*.json|yaml`）
3. `.env`/环境变量（如 `BACKBONE_LLM_API_KEY`, `OPENAI_API_KEY`, `MCP_CONFIG_FILE`）
4. 命令行参数（目前 MCP Hub 支持 `--config` 指定）

## 安全

- 不在代码或仓库中存放真实密钥；使用环境变量或 `config/api.key`
- 前端不包含敏感字段，后端 `/config` 仅返回非敏感摘要

## 迁移说明

- 旧文件（`pe_config.json`, `tools/.../pe_config.json`, `tools/tts/tts_config.json`, `tools/motion_drive/motion_config.json`, `mcp_servers_config.json`）已移除，统一迁移到 `config/` 下
- MCP Hub 默认搜索路径已更新为 `config/mcp_servers.json|yaml`

## 示例环境变量

见 `.env.example`

