# Claude Code GitHub App 配置指南

## 🎯 配置目标

让 Claude Code GitHub App 通过我们的转换器使用 GLM 等其他大模型，而不是只能使用 Claude 模型。

## 📋 当前配置状态

✅ **本地转换器服务**：运行在端口 10000
✅ **公网隧道**：https://blue-spoons-run.loca.lt
✅ **GitHub Actions 工作流**：已创建 `.github/workflows/claude-app.yml`

## 🔧 配置步骤

### 1. 设置 GitHub Secrets

在 GitHub 仓库中设置以下 Secrets：

1. 进入仓库页面 → Settings → Secrets and variables → Actions
2. 添加以下 Secrets：

| Secret 名称 | 值 | 说明 |
|-------------|-----|------|
| `ANTHROPIC_API_KEY` | `your-api-key` | 上游模型的 API 密钥 |
| `CLAUDE_BASE_URL` | `https://blue-spoons-run.loca.lt` | 我们的转换器地址 |

### 2. 安装 Claude Code GitHub App

#### 方法A：通过 GitHub Marketplace
1. 访问 GitHub Marketplace：https://github.com/marketplace
2. 搜索 "Claude Code" 或 "Claude Code Action"
3. 找到 Anthropic 官方的 Claude Code App
4. 点击 "Install"
5. 选择要安装的仓库

#### 方法B：直接访问（如果可用）
1. 尝试访问：https://github.com/apps/claude-code-action
2. 如果地址失效，请使用方法A

#### 方法C：通过 Claude Code CLI
1. 在终端运行：`/install-github-app`
2. 按照提示完成安装
3. 如果提示 API key 错误，需要先配置正确的认证

#### 注意事项
- 目前应用可能还在测试阶段，可能需要邀请码
- 如果无法通过 Marketplace 找到，可能需要等待公开发布
- 可以关注 Anthropic 官方博客获取最新信息

### 3. 配置 App 设置

在仓库设置中配置环境变量：

```yaml
# .github/workflows/claude-app.yml
env:
  ANTHROPIC_API_KEY: ${{ secrets.ANTHROPIC_API_KEY }}
  ANTHROPIC_BASE_URL: ${{ secrets.CLAUDE_BASE_URL }}
  ANTHROPIC_MODEL: glm-4.6
```

## 🚀 测试配置

### 方法1：通过 GitHub Actions
1. 创建一个 PR 或推送到 main 分支
2. 观察 Actions 运行结果
3. 检查是否能成功调用转换器

### 方法2：手动测试
```bash
# 测试健康检查
curl https://blue-spoons-run.loca.lt/health

# 测试模型列表
curl https://blue-spoons-run.loca.lt/v1/models
```

## 🔄 工作原理

```
GitHub App → 转换器(https://blue-spoons-run.loca.lt) → GLM API
```

1. GitHub App 发送 Anthropic 格式请求
2. 转换器转换为 OpenAI 格式
3. 转发到 GLM API
4. 响应转换回 Anthropic 格式
5. 返回给 GitHub App

## ⚠️ 注意事项

1. **稳定性**：本地服务需要保持运行
2. **安全性**：公网端点无认证，建议添加 API Key 验证
3. **性能**：网络延迟可能影响响应速度
4. **限制**：localtunnel 可能有连接限制

## 🔒 安全增强（可选）

在转换器中添加认证：

```python
# app/server.py
@app.before_request
def authenticate():
    auth_header = request.headers.get('Authorization')
    if auth_header != 'Bearer your-secret-token':
        return jsonify({'error': 'Unauthorized'}), 401
```

## 📞 故障排除

### 问题1：连接超时
- 检查本地服务是否运行
- 确认隧道是否正常工作

### 问题2：认证失败
- 验证 API 密钥是否正确
- 检查环境变量设置

### 问题3：格式错误
- 查看转换器日志
- 确认上游 API 兼容性

## 🎉 完成标志

当看到以下输出时，说明配置成功：
- GitHub Actions 运行成功
- 能看到 GLM 模型的响应
- 代码审查功能正常工作

---

现在 GitHub App 可以通过我们的转换器使用 GLM 模型了！🎊