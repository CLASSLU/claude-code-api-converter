# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## 项目概述

这是一个API转换服务器，将Anthropic格式的请求转换为OpenAI格式，并支持工具调用。主要用于为Claude Code提供兼容的API接口。

## 常用命令

### 服务器管理
```bash
# 启动服务器
python start_server.py start

# 停止服务器
python start_server.py stop

# 重启服务器
python start_server.py restart

# 查看服务器状态
python start_server.py status

# 查看日志
python start_server.py logs

# 直接启动服务器（不推荐生产环境）
python api_server.py
```

### 测试命令
```bash
# 运行基本转换测试
python test_converter.py

# 运行Claude Code模拟测试
python test_claude_simulation.py

# 运行工具调用测试
python test_tool_calling.py

# 运行完整场景测试
python test_real_scenario.py

# 运行限流测试
python test_rate_limit_fix.py

# 运行支持的模型测试
python test_supported.py
```

## 项目架构

### 核心组件

1. **api_server.py** - 主服务器应用
   - Flask应用，提供HTTP API端点
   - 单实例保护机制
   - 请求去重和限流处理
   - 完整的Anthropic API兼容

2. **converter_class.py** - 格式转换器
   - Anthropic到OpenAI格式转换
   - 响应格式转换
   - 工具调用支持
   - 错误处理和日志记录

3. **config_manager.py** - 配置管理
   - 配置文件读写
   - 运行时配置更新
   - 默认配置提供

4. **start_server.py** - 服务器管理器
   - 进程管理
   - 健康检查
   - 日志查看
   - 单实例保护

5. **config.html** - Web配置界面
   - 可视化配置管理
   - API测试功能
   - 模型映射配置

### 关键功能

- **API格式转换**: Anthropic ↔ OpenAI
- **工具调用支持**: 完整的function calling
- **限流处理**: 指数退避重试机制
- **请求防重复**: 缓存机制防止重复调用
- **单实例保护**: 防止多进程冲突
- **健康检查**: 服务状态监控

### 配置文件

- **config.json** - 主配置文件
  - OpenAI API设置
  - 服务器设置
  - 模型映射关系

- **api_server.log** - 日志文件
  - 请求日志
  - 错误信息
  - 性能数据

## 开发注意事项

1. **模型映射**: 当前配置直接使用传入的模型名称，不进行映射转换
2. **智能修复**: 为避免Claude Code循环问题，智能修复功能已禁用
3. **端口占用**: 默认使用8080端口，会自动检查并处理端口冲突
4. **日志轮转**: 日志文件最大10MB，保留5个备份
5. **Windows兼容**: 已针对Windows环境优化文件锁定和进程管理

## API端点

- `/v1/messages` - Anthropic消息API
- `/v1/chat/completions` - OpenAI聊天API
- `/v1/models` - 模型列表
- `/config` - 配置管理
- `/health` - 健康检查
- `/` - 配置页面

## 故障排除

1. **端口冲突**: 检查是否有其他进程占用8080端口
2. **API限流**: 检查日志中的限流错误，自动重试机制已启用
3. **配置错误**: 通过Web界面或直接编辑config.json
4. **进程冲突**: 单实例保护会自动处理冲突进程