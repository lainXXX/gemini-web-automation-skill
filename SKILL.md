---
name: gemini-web-automation
description: 当用户希望实际使用 Gemini 网页版完成一次对话时使用本 Skill，包括发送 Prompt、继续已有对话、上传图片或文件、获取 Gemini 回复以及恢复 Gemini 登录状态。典型请求包括："帮我问 Gemini"、"用 Gemini 回答"、"把这段话发给 Gemini"、"让 Gemini 看这张图片"、"继续 Gemini 对话"。如果只是询问 Gemini 的功能、模型、API、价格或使用方法，而不需要实际操作 Gemini 网页，则不要使用本 Skill。

allowed-tools:
  - Read
  - Write
  - Edit
  - Grep
  - Glob
  - Bash
---

# Gemini Web Automation

## Mission

本 Skill 负责维护 **Gemini Runtime**。职责包括：

- 将 Prompt 发送给 Gemini 并获取完整回复
- 维护 Gemini Session（登录状态、页面状态、会话状态）
- 在页面变化后恢复 Runtime

除此之外，不承担任何通用浏览器自动化任务。

本 Skill 将 `scripts/chat.py` 视为 Gemini Runtime API。SKILL.md 负责调度，业务逻辑由 Runtime 实现，Reference 提供设计知识。

---

## 默认行为

`scripts/chat.py` 是 Runtime 唯一入口。所有日常任务统一通过它完成。

Agent 不判断是否首次运行，不判断是否已登录，不判断浏览器状态。所有环境检测、Runtime 恢复、登录检查、浏览器管理均由 `chat.py` 自动处理。

除首次部署和页面维护外，不要绕过 `chat.py` 直接操作浏览器。

---

## Runtime Lifecycle

所有初始化由 `chat.py` 在内部自动完成，Agent 无感知：

```
chat.py
  │
  ├── Stage 1: 环境
  │   ├── .env 不存在 → ENV_NOT_FOUND
  │   ├── userdata/ 不存在 → 自动创建
  │   └── 代理不可达 → PROXY_REQUIRED
  │
  ├── Stage 2: Runtime
  │   ├── Chrome 运行中 → CDP 连接
  │   └── 未运行 → 自动启动 Chrome
  │
  ├── Stage 3: 页面
  │   ├── Gemini Tab 存在 → 复用
  │   ├── 未登录 → LOGIN_REQUIRED
  │   └── 不存在 → 打开 Gemini
  │
  └── Stage 4: 对话
      ├── 发送 Prompt
      ├── 等待回复
      └── 返回 JSON
```

Agent 始终处于 Stage 4 视角：调用 → 等待 → 得到结果。无需要关心前三个阶段。`bootstrap.py` 仅在 `LOGIN_REQUIRED` 时作为登录向导执行，它不是初始化脚本。

---

## 三个入口

| 用途 | 脚本 | 频率 |
|------|------|------|
| **日常对话** | `scripts/chat.py` | 99% |
| **登录向导** | `scripts/bootstrap.py` | 仅首次 / 登录过期 |
| **页面改版** | `scripts/analyze_page.py` | 一年几次 |

---

## 日常对话（Hot Path）

日常任务默认直接调用 `scripts/chat.py`。除非发生初始化或页面维护，否则不要运行其它脚本。

`scripts/chat.py` 返回结构化 JSON。Agent 仅根据 `success`、`reply`、`error.code`、`next_action` 决定下一步，不解析浏览器内部状态。

```
执行 scripts/chat.py "提示词"
  │
  ▼
解析返回 JSON
  │
  ├── success: true  → 将 reply 返回给用户
  │
  └── success: false → 按 next_action / error.code 路由
```

### 可选参数

| 参数 | 作用 |
|------|------|
| `-a image.png` | 附带图片 |
| `--headed` | 保持浏览器窗口在前台（默认最小化到后台） |
| `--dry-run` | 仅测试模型切换，不发送对话 |
| `--health` | 健康检查（不执行对话，返回运行时状态） |

### 错误路由

优先依据 `next_action`。仅当 `next_action` 缺失时，根据 `error.code` 处理。

| next_action / error.code | Agent 动作 |
|-------------------------|-----------|
| `next_action: "RUN_BOOTSTRAP"` / `LOGIN_REQUIRED` | 执行 `scripts/bootstrap.py` |
| `next_action: "CREATE_ENV"` / `ENV_NOT_FOUND` | 提示用户复制 `.env.example` → `.env` 并配置 |
| `next_action: "CHECK_PROXY"` / `PROXY_REQUIRED` | 提示用户检查代理配置或网络 |
| `CHROME_NOT_FOUND` | 提示用户检查 CHROME_PATH |
| 未列出 | 直接向用户返回 `error.message`，不自行推测原因 |

---

## 登录向导

仅在收到 `LOGIN_REQUIRED` 时执行 `scripts/bootstrap.py`。它会启动 Chrome、打开 Gemini 登录页、等待用户手动登录，确认成功后退出。完成后即可开始日常对话。

---

## 页面改版

当 Gemini 页面更新导致脚本失效时，执行 `scripts/analyze_page.py` 分析页面结构，然后参考 `references/maintenance.md` 更新选择器。

---

## Reference

按需读取，不主动加载全部文档。

| 当需要…… | 读取 |
|---------|------|
| 修改运行架构 | `references/architecture.md` |
| 修改页面交互 | `references/gemini.md` |
| 修复页面改版 | `references/maintenance.md` |

---

## 核心原则

1. **Runtime API First** — 所有日常任务统一通过 `scripts/chat.py` 完成，Agent 不直接操作浏览器
2. **Runtime First** — 优先复用已有 Session，仅在必要时冷启动
3. **Lifecycle 下沉** — Agent 不判断运行环境，所有状态管理由 Runtime 内部自动完成
4. **Fail Fast** — 超时立即失败并返回结构化错误；异常时收集截图/HTML/URL，不重试

## 窗口行为

默认 Chrome 以**最小化**方式运行在后台，不干扰用户。
需要查看浏览器时加 `--headed` 参数保持窗口在前台。
