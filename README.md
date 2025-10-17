# 轻量版 API 转换服务

本项目提供一个轻量的 Flask 服务，将 Anthropic 风格的请求/响应在服务端转换为 OpenAI 兼容格式，主要为以openai格式大模型使用claude code提供支持。

## 项目结构
- app/
  - server.py：Flask 路由与转发逻辑（/v1/messages、/v1/chat/completions、/v1/models、/health、/config 等）
  - converter.py：Anthropic 与 OpenAI 消息/工具调用的互转
  - config.py：配置加载（环境变量优先，支持 config.json 覆盖）
  - logger_setup.py：智能日志系统（支持分级日志、请求链路追踪、统一文件输出）
- svc.py：服务管理器（支持前台/后台启动、状态检查、优雅停止）
- tests/：集成测试
- requirements.txt：依赖列表（flask、requests、psutil）
- run_tests.py：测试执行入口
- config.json：示例配置（可被环境变量覆盖）

## 快速开始
1) 安装依赖
   pip install -r requirements.txt

2) 启动服务
   # 前台启动（显示实时日志）
   python svc.py start
   
   # 后台启动（静默运行）
   python svc.py start -b
   
   # 检查服务状态
   python svc.py status
   
   # 停止服务
   python svc.py stop
   
   # 重启服务
   python svc.py restart -b

默认监听：127.0.0.1:10000（可通过环境变量或 /config 接口修改）。

## 主要接口
- POST /v1/messages：Anthropic 消息接口，服务端转换并转发到 OpenAI 兼容 /chat/completions
- POST /v1/chat/completions：直转发 OpenAI 兼容聊天接口
- GET /v1/models：模型列表（上游失败时返回内置兜底）
- POST /v1/messages/count_tokens：粗略 Token 估算（约 4 字符 ≈ 1 token）
- GET /health：健康检查
- GET/POST /config：读取/更新运行配置

## 配置说明
优先读取环境变量，未提供时再读取 config.json：
- OPENAI_API_KEY：上游 API Key
- OPENAI_BASE_URL：上游基础 URL（如 https://api.openai.com/v1 或第三方代理）
- SERVER_HOST：默认 127.0.0.1
- SERVER_PORT：默认 10000
- DEBUG：true/false 控制 Flask debug
- 流式处理：服务端会智能检测上游是否返回 SSE（根据 Content-Type 或首帧 data:），自动进行流式转发，无需额外配置。

日志级别与是否落盘可通过环境变量 LOG_LEVEL、LOG_TO_FILE 或 config.json 中 logging 段配置。

## Claude Code 配置说明

在 `~/.claude/settings.json` 中配置：

### 推荐方式（直接指定模型为自己使用的模型）
```json
{
  "env": {
    "ANTHROPIC_BASE_URL": "http://127.0.0.1:10000",
    "ANTHROPIC_AUTH_TOKEN": "anykey",
    "ANTHROPIC_MODEL": "zai-org/GLM-4.6",
    "ANTHROPIC_DEFAULT_HAIKU_MODEL": "zai-org/GLM-4.5",
    "ANTHROPIC_DEFAULT_OPUS_MODEL": "zai-org/GLM-4.6",
    "ANTHROPIC_DEFAULT_SONNET_MODEL": "zai-org/GLM-4.6"
  }
}
```
✅ 直接使用指定模型，无需维护映射配置

### 基础方式（自动映射）
```json
{
  "env": {
    "ANTHROPIC_BASE_URL": "http://127.0.0.1:10000",
    "ANTHROPIC_AUTH_TOKEN": "anykey"
  }
}
```
⚠️ 需要在 `config.json` 中维护模型映射配置使用claude code当前使用的模型名称

## 日志系统

### 智能分级日志
- **开发环境（DEBUG级别）**：记录完整请求链路，包括请求头、请求体、API转换过程
- **生产环境（ERROR级别）**：仅记录错误和异常信息，保证高性能

### 请求链路追踪
- 每个请求自动生成唯一追踪ID：`[req_5fbb8a04234c]`
- 完整记录API调用链路：Anthropic请求 → OpenAI请求 → OpenAI响应 → Anthropic响应
- 支持跨服务调用追踪，便于问题定位

### 日志配置示例
```json
{
  "logging": {
    "level": "DEBUG",           // DEBUG | INFO | ERROR
    "log_to_file": true,        // 是否写入文件
    "max_file_size": 10485760,  // 10MB
    "backup_count": 5           // 保留5个历史文件
  }
}
```

### 日志文件结构
```
logs/
└── api_server_2025-10-17.log  # 按日期分类的统一日志文件
```

### 日志内容示例
```
2025-10-17 11:24:25 - api_server - INFO - [req_12ebb3171441] HTTP Request - Method: GET, Path: /health?, Client: 127.0.0.1
2025-10-17 11:24:25 - api_server - DEBUG - [req_12ebb3171441] Request Headers: {"User-Agent": "..."}
2025-10-17 11:24:25 - api_server - DEBUG - [req_12ebb3171441] Anthropic Request - {"model": "..."}
2025-10-17 11:24:25 - api_server - DEBUG - [req_12ebb3171441] OpenAI Request - {"model": "..."}
2025-10-17 11:24:25 - api_server - DEBUG - [req_12ebb3171441] OpenAI Response - {"choices": [...]}
2025-10-17 11:24:25 - api_server - DEBUG - [req_12ebb3171441] Anthropic Response - {"content": [...]}
2025-10-17 11:24:25 - api_server - INFO - [req_12ebb3171441] HTTP Response - Status: 200
2025-10-17 11:24:25 - api_server - INFO - [req_12ebb3171441] Request completed in 1.52ms
```

## 测试
- 运行测试：
  python run_tests.py
- 脚本会在测试前安装依赖，并启动一个测试用的 Flask 线程（127.0.0.1:10001）。

## 安全建议
- 不要将真实密钥提交到仓库。推荐通过环境变量注入 OPENAI_API_KEY。
- 如需持久化配置，请仅保存非敏感字段到 config.json。

## 说明
- 针对部分上游返回 data: 前缀的情况已做兼容处理。
- 当上游不支持指定模型时，会返回格式化错误信息；可按需在 app/server.py 增加更丰富的兜底策略。
