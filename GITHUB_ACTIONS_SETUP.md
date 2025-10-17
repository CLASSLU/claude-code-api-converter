# GitHub Actions 代码审查配置

## 🎯 方案概述

不依赖 Claude Code GitHub App，直接在 GitHub Actions 中调用我们的转换器服务，实现 AI 代码审查功能。

## 📋 已创建的文件

### 1. 工作流文件
- `.github/workflows/ai-code-review.yml` - 主要的 AI 代码审查工作流

### 2. 配置文档
- `GITHUB_ACTIONS_SETUP.md` - 本配置文档

## 🔧 配置步骤

### 第1步：设置 GitHub Secrets

在你的 GitHub 仓库中添加以下 Secrets：

1. 进入仓库页面 → **Settings** → **Secrets and variables** → **Actions**
2. 点击 **New repository secret**
3. 添加以下 Secret：

| Secret 名称 | 值 | 说明 |
|-------------|-----|------|
| `UPSTREAM_API_KEY` | `sk-11b8aca58e592cad27412911f86ec8b5` | GLM API 密钥 |

### 第2步：确保本地服务运行

确认以下服务正在运行：

1. ✅ **转换器服务**：端口 10000
2. ✅ **公网隧道**：https://blue-spoons-run.loca.lt

### 第3步：测试工作流

#### 方法A：创建 Pull Request
1. 修改一些代码
2. 创建 PR
3. 观察 Actions 运行

#### 方法B：推送到主分支
1. 直接推送到 main/master 分支
2. 观察 Actions 运行

## 🚀 工作流功能

### 自动触发条件
- **Pull Request**：打开、更新、重新打开时
- **Push**：推送到 main/master 分支时

### 主要功能
1. **连接测试**：验证转换器服务可达性
2. **模型检查**：获取可用模型列表
3. **代码分析**：
   - 获取变更文件列表
   - 提取代码差异内容
   - 发送给 AI 进行分析
4. **结果展示**：
   - 在 PR 中添加评论
   - 生成摘要报告

### AI 分析内容
- 代码质量评估
- 潜在问题和改进建议
- 最佳实践建议
- 安全性检查

## 📊 工作流详解

### Jobs 结构
```
ai-code-review (主要任务)
├── Checkout code
├── Test Converter Connection
├── Check Available Models
├── Get Changed Files
├── AI Code Review
├── Create Review Comment (PR only)
└── Summary Report

test-connection (连接测试)
└── Quick Health Check
```

### 核心流程
1. **健康检查** → 2. **获取变更** → 3. **AI 分析** → 4. **展示结果**

## 🔍 监控和调试

### 查看运行日志
1. 进入仓库 **Actions** 页面
2. 点击对应的工作流运行
3. 查看各个步骤的详细日志

### 常见问题排查

#### 问题1：连接超时
```
❌ Converter service not accessible: HTTP 000
```
**解决方案**：
- 检查本地服务是否运行：`python svc.py status`
- 检查隧道是否正常：访问 https://blue-spoons-run.loca.lt/health

#### 问题2：认证失败
```
Authentication failed with upstream API
```
**解决方案**：
- 检查 `UPSTREAM_API_KEY` 是否正确
- 确认 GLM API 密钥有效性

#### 问题3：模型不存在
```
Model not found: glm-4.6
```
**解决方案**：
- 检查 config.json 中的模型配置
- 更新工作流中的模型名称

## 📈 性能优化

### 响应时间监控
工作流会自动记录：
- 连接建立时间
- AI 响应时间
- 整体执行时间

### 并发控制
- 默认单个运行实例
- 避免频繁调用上游 API
- 设置合理的 token 限制

## 🔒 安全考虑

### 当前状态
- ⚠️ 公网端点无认证保护
- ⚠️ API 密钥存储在 GitHub Secrets
- ⚠️ 网络传输未加密（隧道本身是加密的）

### 建议改进
1. **添加认证**：在转换器中实现 API Key 验证
2. **访问限制**：限制 GitHub IP 访问
3. **日志审计**：记录所有 API 调用

## 🎉 预期效果

### 成功运行时你会看到：
1. **Actions 运行成功**：绿色勾号
2. **PR 评论**：详细的 AI 分析报告
3. **Summary 报告**：统计数据和性能指标
4. **代码质量提升**：基于 AI 的改进建议

### 示例输出
```
## 🤖 AI 代码审查报告

### 📋 完整分析结果
[AI 生成的详细代码分析...]

---
*此审查由 AI 模型通过转换器服务生成*
```

## 🔄 后续优化

1. **增强安全性**：添加认证机制
2. **提升性能**：缓存常见分析结果
3. **扩展功能**：支持更多分析类型
4. **UI 优化**：更好的评论格式

---

现在你可以在不依赖 GitHub App 的情况下，使用任何大模型进行代码审查了！🚀