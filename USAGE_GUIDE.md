# 轻量级API转换器使用指南

## 🎯 适用场景

本轻量级版本特别适合以下使用场景：

- **Claude Code集成**: 为Claude Code提供API格式转换
- **简单代理需求**: 仅需基本的格式转换功能
- **资源受限环境**: 需要低内存、高响应速度
- **开发和测试**: 快速启动和调试
- **生产环境**: 稳定、透明的代理服务

## 🚀 快速启动

### 1. 基本启动
```bash
# 设置API密钥
export OPENAI_API_KEY="sk-..."

# 启动服务
python server_lite.py
```

### 2. 自定义配置
```bash
# 完整配置示例
export OPENAI_API_KEY="sk-..."
export OPENAI_BASE_URL="https://api.openai.com/v1"
export HOST="127.0.0.1"
export PORT="8080"

python server_lite.py
```

### 3. 使用配置文件
```bash
# 创建config.json
cat > config.json << EOF
{
  "openai": {
    "api_key": "sk-...",
    "base_url": "https://api.openai.com/v1"
  },
  "server": {
    "host": "0.0.0.0",
    "port": 8080
  }
}
EOF

python server_lite.py
```

## 📡 API端点详解

### `/v1/messages` - Anthropic兼容接口
支持标准的Anthropic消息格式：

```bash
curl -X POST http://localhost:8080/v1/messages \
  -H "Content-Type: application/json" \
  -d '{
    "model": "claude-3-5-sonnet-20241022",
    "max_tokens": 1000,
    "messages": [
      {"role": "user", "content": "你好"}
    ]
  }'
```

### `/v1/chat/completions` - OpenAI兼容接口
支持OpenAI聊天格式：

```bash
curl -X POST http://localhost:8080/v1/chat/completions \
  -H "Content-Type: application/json" \
  -d '{
    "model": "gpt-4",
    "messages": [
      {"role": "user", "content": "Hello"}
    ],
    "max_tokens": 1000
  }'
```

### `/v1/models` - 模型列表
```bash
curl http://localhost:8080/v1/models
```

### `/health` - 健康检查
```bash
curl http://localhost:8080/health
```

## 🔧 工具调用使用

### 定义工具
```json
{
  "tools": [
    {
      "name": "get_weather",
      "description": "获取指定城市的天气信息",
      "input_schema": {
        "type": "object",
        "properties": {
          "city": {
            "type": "string",
            "description": "城市名称"
          }
        },
        "required": ["city"]
      }
    }
  ]
}
```

### 工具调用流程
1. 用户请求包含工具定义
2. 模型返回 `tool_use` 类型的响应
3. 执行工具并提交 `tool_result`
4. 模型基于工具结果生成最终回答

### 完整示例
```bash
curl -X POST http://localhost:8080/v1/messages \
  -H "Content-Type: application/json" \
  -d '{
    "model": "claude-3-5-sonnet-20241022",
    "max_tokens": 1000,
    "messages": [
      {
        "role": "user",
        "content": "北京现在天气怎么样？"
      }
    ],
    "tools": [
      {
        "name": "get_weather",
        "description": "获取天气信息",
        "input_schema": {
          "type": "object",
          "properties": {
            "city": {"type": "string"}
          }
        }
      }
    ]
  }'
```

## 🐛 故障排除

### 常见问题

#### 1. API密钥错误
```json
{
  "error": {
    "message": "Conversion error: OpenAI API error: 401 - Invalid API key",
    "type": "conversion_error"
  }
}
```
**解决方案**: 检查 `OPENAI_API_KEY` 环境变量或config.json中的密钥

#### 2. 端口占用
```
OSError: [Errno 98] Address already in use
```
**解决方案**: 更改端口号或停止占用端口的进程

#### 3. 网络连接问题
```json
{
  "error": {
    "message": "Conversion error: OpenAI API error: timeout",
    "type": "conversion_error"
  }
}
```
**解决方案**: 检查网络连接和防火墙设置

### 调试模式

启用详细日志：
```python
import logging
logging.basicConfig(level=logging.DEBUG)
```

## 📊 性能监控

### 基本指标
轻量级版本移除了复杂的监控系统，但可以通过以下方式监控：

#### 1. 系统资源监控
```bash
# CPU和内存使用
top -p $(pgrep -f server_lite.py)

# 网络连接
netstat -an | grep :8080
```

#### 2. 日志分析
```bash
# 查看错误日志
tail -f /var/log/api_server.log

# 统计错误数量
grep "ERROR" /var/log/api_server.log | wc -l
```

#### 3. 性能测试
```bash
# 运行内建性能测试
python test_performance_comparison.py

# 简单响应时间测试
time curl -s http://localhost:8080/health
```

## 🔄 与原版对比

| 特性 | 轻量版 | 原版 |
|------|--------|------|
| 启动时间 | ~1秒 | ~3秒 |
| 内存占用 | 33.5MB | 50+MB |
| 代码维护 | 极简 | 复杂 |
| 配置复杂度 | 低 | 高 |
| 功能完整性 | 核心功能 | 完整功能 |
| 调试难度 | 简单 | 复杂 |

## 🎯 最佳实践

### 1. 生产环境部署
```bash
# 使用进程管理器
pip install supervisor

# 配置supervisor
cat > /etc/supervisor/conf.d/api-lite.conf << EOF
[program:api-lite]
command=/usr/bin/python3 /path/to/server_lite.py
directory=/path/to/project
autostart=true
autorestart=true
user=www-data
environment=OPENAI_API_KEY="%((ENV_OPENAI_API_KEY)s)"
EOF
```

### 2. Docker部署
```dockerfile
FROM python:3.9-slim
WORKDIR /app
COPY *.py ./
COPY config.json ./
ENV OPENAI_API_KEY=""
EXPOSE 8080
CMD ["python", "server_lite.py"]
```

### 3. 反向代理配置
```nginx
server {
    listen 80;
    server_name your-domain.com;

    location / {
        proxy_pass http://127.0.0.1:8080;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
    }
}
```

## 📝 开发指南

### 添加新功能
1. 在 `converter_lite.py` 中添加转换逻辑
2. 在 `server_lite.py` 中添加API端点
3. 更新测试用例
4. 更新文档

### 性能优化建议
1. 避免在转换路径中添加复杂逻辑
2. 保持简单的错误处理
3. 最小化日志输出
4. 使用环境变量而非配置文件

### 测试新功能
```bash
# 功能测试
python -c "from converter_lite import LiteConverter; print('OK')"

# API测试
curl -f http://localhost:8080/health || echo "FAIL"
```

## 🔗 相关链接

- [轻量化重构计划](./LIGHTWEIGHT_REFACTOR_PLAN.md)
- [性能验证报告](./PERFORMANCE_VALIDATION_REPORT.md)
- [原项目文档](https://github.com/your-repo/claude-code-api-converter)