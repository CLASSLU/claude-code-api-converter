# Claude Code API Converter - 轻量版

## 概述

轻量化架构重构版本，专为Claude Code提供高效的API格式转换服务。将Anthropic格式的请求转换为OpenAI格式，支持完整的工具调用功能。

## 🚀 性能指标

- **代码量**: 440行（相比原版3641行减少88%）
- **响应时间**: 微秒级别转换速度
- **内存占用**: 33.5MB
- **失败率**: 快速失败策略，无复杂重试逻辑

## 📁 核心文件

### 轻量级组件
- `converter_lite.py` - 简化的格式转换器（163行）
- `server_lite.py` - 轻量级API服务器（206行）
- `config_lite.py` - 环境变量配置管理（71行）

### 测试和验证
- `test_performance_comparison.py` - 性能对比测试
- `PERFORMANCE_VALIDATION_REPORT.md` - 性能验证报告
- `LIGHTWEIGHT_REFACTOR_PLAN.md` - 重构计划文档

## 🛠 快速开始

### 1. 环境配置
```bash
# 设置OpenAI API密钥
export OPENAI_API_KEY="your_api_key_here"

# 可选：设置API基础URL
export OPENAI_BASE_URL="https://api.openai.com/v1"
```

### 2. 启动服务器
```bash
python server_lite.py
```

### 3. 使用API
服务器将在 `http://localhost:8080` 启动，支持以下端点：

- `/v1/messages` - Anthropic消息API
- `/v1/chat/completions` - OpenAI聊天API
- `/v1/models` - 模型列表
- `/health` - 健康检查

## 🔧 配置说明

### 环境变量优先
轻量级版本优先使用环境变量配置：

| 变量名 | 说明 | 默认值 |
|--------|------|--------|
| `OPENAI_API_KEY` | OpenAI API密钥 | 必填 |
| `OPENAI_BASE_URL` | API基础URL | `https://api.openai.com/v1` |
| `HOST` | 服务器主机 | `0.0.0.0` |
| `PORT` | 服务器端口 | `8080` |

### 配置文件回退
如果环境变量未设置，将回退到 `config.json` 文件。

## 🎯 核心特性

### 保留功能
- ✅ Anthropic ↔ OpenAI格式转换
- ✅ 完整工具调用支持
- ✅ 基本错误处理
- ✅ 环境变量配置
- ✅ 透明代理转发

### 移除功能
- ❌ 复杂重试逻辑
- ❌ 请求去重机制
- ❌ 限流控制
- ❌ 缓存系统
- ❌ Web配置界面
- ❌ 性能监控
- ❌ 复杂日志系统

### 日志策略
仅记录ERROR级别日志，减少I/O开销：

```python
logging.basicConfig(level=logging.ERROR)
```

## 📊 性能对比

| 测试项目 | 原版 | 轻量版 | 提升 |
|---------|------|--------|------|
| 代码行数 | 3641行 | 440行 | 88% ⬇️ |
| 消息转换 | 0.005秒 | 0.003秒 | 34.9% ⬆️ |
| 请求转换 | 0.006秒 | 0.005秒 | 25.1% ⬆️ |
| 响应转换 | 0.002秒 | 0.000秒 | 100.0% ⬆️ |

## 🔍 API使用示例

### Anthropic格式请求
```bash
curl -X POST http://localhost:8080/v1/messages \
  -H "Content-Type: application/json" \
  -d '{
    "model": "claude-3-5-sonnet-20241022",
    "max_tokens": 1000,
    "messages": [
      {
        "role": "user",
        "content": "你好，请介绍一下你自己"
      }
    ]
  }'
```

### 工具调用请求
```bash
curl -X POST http://localhost:8080/v1/messages \
  -H "Content-Type: application/json" \
  -d '{
    "model": "claude-3-5-sonnet-20241022",
    "max_tokens": 1000,
    "messages": [
      {
        "role": "user",
        "content": "现在几点了？"
      }
    ],
    "tools": [
      {
        "name": "get_current_time",
        "description": "获取当前时间",
        "input_schema": {
          "type": "object",
          "properties": {}
        }
      }
    ]
  }'
```

## 🧪 测试

### 运行性能测试
```bash
python test_performance_comparison.py
```

### 运行功能测试
```bash
python test_simple_validation.py
```

## 🏗 架构设计

### KISS原则
- **保持简单**: 移除所有不必要的复杂性
- **单一职责**: 每个组件专注单一功能
- **透明代理**: 不修改、不缓存、不存储请求
- **快速失败**: 错误立即返回，不重试

### 核心组件关系
```
请求 → server_lite.py → converter_lite.py → OpenAI API
响应 ← converter_lite.py ← OpenAI API ← server_lite.py
```

## 🔄 Claude Code集成

轻量级版本完全兼容Claude Code的使用模式：

1. **ID格式**: 自动生成有效的消息ID
2. **stop_reason**: 正确映射工具调用状态
3. **工具调用**: 完整支持function calling
4. **错误处理**: 提供清晰的错误信息

## 📝 更新日志

### v2.0.0 (轻量版)
- 代码量减少88%（3641行 → 440行）
- 移除所有复杂中间件
- 性能提升25-100%
- 采用环境变量优先配置
- 简化日志系统（仅ERROR级别）
- 实现透明代理架构

### v1.x.x (原版)
- 完整功能集
- 复杂中间件和监控
- Web配置界面
- 重试和限流机制

## 🤝 贡献

轻量版本专注于简洁性和性能，如需添加功能请：

1. 确认符合KISS原则
2. 评估性能影响
3. 保持代码简洁
4. 更新测试用例

## 📄 许可证

本项目采用原项目许可证。