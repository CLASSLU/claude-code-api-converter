# CLAUDE.md

本文件为 Claude Code（claude.ai/code）在处理代码时提供指导。

## 原则

1. 专注于API转换服务器的开发和优化，确保Anthropic到OpenAI格式的准确转换
2. 保持代码质量和可维护性，添加新功能时需要相应更新文档和测试
3. 重视日志系统的有效性和性能，确保问题可追踪可定位

## 项目概述

这是一个轻量级 API 转换服务器，将 Anthropic 格式的请求转换为 OpenAI 兼容格式，主要为 Claude Code 提供兼容的 API 接口。项目经过轻量化重构，专注核心功能，简化运行与维护。

## 常用命令

### 服务器管理
```bash
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
```

### 测试命令
```bash
# 运行所有测试
python run_tests.py

# 运行特定测试
python -m pytest tests/test_integration.py -v
```

## 项目架构

### 核心组件

1. **app/server.py** - 主服务器应用
   - Flask 应用，提供 HTTP API 端点
   - 请求去重和限流处理
   - 完整的 Anthropic API 兼容
   - SSE 流式响应处理和聚合
   - 智能流式/非流式检测

2. **app/converter.py** - 格式转换器
   - Anthropic 到 OpenAI 格式转换
   - 响应格式转换
   - 工具调用支持
   - 错误处理和日志记录

3. **app/config.py** - 配置管理
   - 环境变量优先读取
   - 配置文件支持
   - 运行时配置更新

4. **app/logger_setup.py** - 智能日志系统
   - 分级日志记录（DEBUG/INFO/ERROR）
   - 请求链路追踪（唯一追踪ID）
   - 统一文件输出（按日期分类）
   - 完整API调用链路记录

5. **svc.py** - 服务管理器
   - 前台/后台启动支持
   - 环境配置加载
   - 进程管理和优雅停止
   - 端口占用检测

### 关键功能特性

- **API 格式转换**: Anthropic ↔ OpenAI
- **工具调用支持**: 完整的 function calling
- **智能流式处理**: 自动检测上游响应类型
- **SSE 流聚合**: 将流式响应聚合成 JSON
- **UTF-8 编码支持**: 修复了中文内容处理问题
- **环境变量配置**: 支持环境变量覆盖配置文件
- **智能日志系统**: 分级日志、请求链路追踪、统一文件输出
- **服务管理**: 前台/后台启动、优雅停止、状态监控

## API 端点

- **POST /v1/messages** - Anthropic 消息接口
- **POST /v1/chat/completions** - OpenAI 聊天接口
- **GET /v1/models** - 模型列表
- **POST /v1/messages/count_tokens** - Token 估算
- **GET /health** - 健康检查
- **GET/POST /config** - 配置管理

## 配置文件

### config.json 结构
```json
{
  "openai": {
    "api_key": "your-api-key",
    "base_url": "https://api.gitcode.com/api/v5",
    "base_model": "zai-org/GLM-4.6"
  },
  "server": {
    "host": "0.0.0.0",
    "port": 8080,
    "debug": false
  },
  "features": {
    "disable_stream": false
  },
  "logging": {
    "level": "DEBUG",
    "log_to_file": true,
    "max_file_size": 10485760,
    "backup_count": 5
  },
  "model_mappings": [
    {
      "anthropic": "claude-3-5-haiku-20241022",
      "openai": "zai-org/GLM-4.6"
    }
  ]
}
```

### 环境变量优先级
- `OPENAI_API_KEY` - 上游 API 密钥
- `OPENAI_BASE_URL` - 上游基础 URL
- `SERVER_HOST` - 服务器主机（默认 0.0.0.0）
- `SERVER_PORT` - 服务器端口（默认 10000）
- `DEBUG` - Flask debug 模式
- `LOG_LEVEL` - 日志级别
- `LOG_TO_FILE` - 是否记录到文件

## 智能日志系统

### 分级日志记录
- **DEBUG级别**：完整请求链路，包括请求头、请求体、API转换过程
- **INFO级别**：基础请求信息，包括HTTP方法、路径、响应状态、耗时
- **ERROR级别**：仅记录错误和异常信息，保证生产环境高性能

### 请求链路追踪
每个请求自动生成唯一追踪ID，格式：`[req_5fbb8a04234c]`
- 完整记录API调用链路：Anthropic请求 → OpenAI请求 → OpenAI响应 → Anthropic响应
- 支持跨服务调用追踪，便于问题定位和性能分析

### 统一文件输出
- 所有日志输出到按日期分类的文件：`logs/api_server_YYYY-MM-DD.log`
- 自动日志轮转，避免单个文件过大
- 消除了临时日志文件的产生

### 日志配置
通过config.json中的logging段配置：
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

## 重要修复记录

### SSE 流处理修复 (app/server.py:305-313)
修复了上游返回中文内容时的编码问题：
```python
for line in nonstream_resp.iter_lines(decode_unicode=False):
    # 安全解码字节行
    try:
        line_str = line.decode('utf-8', errors='replace')
    except Exception:
        line_str = line.decode('latin1', errors='replace')
```

### 工具调用修复 (app/converter.py:177-179)
修复了 tool_calls 为 None 时的处理问题。

## 开发注意事项

1. **模型映射**: 当前配置直接使用传入的模型名称，不进行映射转换
2. **编码处理**: 已修复 SSE 流中的 UTF-8 编码问题，支持中文内容
3. **流式检测**: 服务端会智能检测上游是否返回 SSE，自动进行流式转发
4. **日志安全**: 日志系统使用 ensure_ascii=True 避免编码问题
5. **Windows 兼容**: 已针对 Windows 环境优化文件锁定和进程管理

## 测试验证

项目包含完整的集成测试，验证以下功能：
- 基本 API 转换
- 工具调用支持
- 流式响应处理
- 中文内容支持
- 错误处理机制

运行 `python run_tests.py` 执行完整测试套件。

## 故障排除

1. **端口冲突**: 默认使用 8080 端口，检查是否有其他进程占用
2. **API 连接**: 检查上游 API 配置和网络连接
3. **编码问题**: 已修复中文内容处理，如仍有问题检查日志
4. **配置错误**: 通过环境变量或 config.json 检查配置

## 安全建议

- 不要将真实 API 密钥提交到仓库
- 推荐通过环境变量注入敏感配置
- 生产环境应关闭 debug 模式
- 定期检查日志文件大小和备份

## 项目结构图

```
D:\project\test1\
├── app\                    # 核心应用模块
│   ├── server.py          # Flask 服务器主程序
│   ├── converter.py       # API 格式转换器
│   ├── config.py          # 配置管理
│   └── logger_setup.py    # 智能日志系统
├── tests\                  # 集成测试
│   ├── test_integration.py
│   └── test_anthropic_tools.py
├── logs\                   # 日志文件目录
│   └── api_server_2025-10-17.log  # 按日期分类的统一日志文件
├── svc.py                  # 服务管理器
├── run_tests.py           # 测试运行脚本
├── config.json            # 配置文件
├── requirements.txt       # 依赖列表
├── README.md              # 项目说明
└── CLAUDE.md              # Claude Code 指导文档
```

本项目专注提供稳定可靠的 API 转换服务，已针对 Claude Code 的使用场景进行优化。
