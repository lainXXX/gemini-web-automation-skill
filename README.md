# Gemini Web Automation

[English](README.en.md) | <https://github.com/lainXXX/gemini-web-automation-skill>

通过浏览器自动化 [Gemini](https://gemini.google.com/app) 的 Python 运行时，专为 AI Agent 集成设计。

## 关于

你日常使用的模型（DeepSeek V4 Flash、豆包、GLM、Qwen、Kimi）速度快、成本低，但面对复杂任务时——深度头脑风暴、写技术方案、设计架构、制定详细 Plan——它们的表现远不如 **Gemini 2.5 Pro with extended thinking**。

这个项目就是用来弥补这个差距的。

它让任何 AI Agent（Claude Code 等）在遇到高难度任务时，能随时调取 Gemini 的最强能力，然后把结果带回你的工作流。你继续用你喜欢的便宜模型做日常杂活，遇到硬骨头再交给 Gemini。

## 它能做什么

- **头脑风暴 & 方案设计** — 让 Gemini Pro 的 deep thinking 帮你拆解复杂问题、产出高质量方案
- **写 Spec / Plan** — 技术方案、PRD、架构文档，Gemini 的 extended thinking 更擅长结构化输出
- **多模态辅助** — 你用的模型没有视觉能力？让 Gemini（默认 3.5 Flash）帮你看图、分析截图、识别界面
- **任何需要"认真想想"的任务** — 日常模型给不了的那种深度思考

## 特性

- **会话持久化** — 登录一次，后续重复使用浏览器 Profile
- **温/冷启动** — 优先通过 CDP 连接已有 Chrome，必要时自动启动新实例
- **模型管理** — 自动发现、切换、验证模型及思考等级（标准/扩展）
- **图片附件** — 将图片粘贴到对话中
- **结构化 JSON 输出** — `ok`、`contract`、`reply`、`error.code`、`next_action`
- **健康检查** — 快速查看运行状态，不发起对话
- **代理支持** — HTTP、HTTPS、SOCKS5

## 快速开始

```bash
# 1. 克隆
git clone https://github.com/lainXXX/gemini-web-automation-skill.git
cd gemini-web-automation-skill

# 2. 配置
cp .env.example .env
# 编辑 .env — 国内用户务必配置 PROXY_SERVER

# 3. 安装依赖并登录
python scripts/bootstrap.py

# 4. 开始对话
python scripts/chat.py "你好，Gemini！"
```

`bootstrap.py` 会启动 Chrome 并打开 Gemini 登录页，你手动登录后即可开始使用。

## 使用方法

### CLI

```bash
# 发送消息
python scripts/chat.py "解释一下量子计算"

# 附带图片
python scripts/chat.py "这张图里有什么？" -a photo.jpg

# 健康检查
python scripts/chat.py --health

# 保持浏览器窗口可见
python scripts/chat.py --headed "你好"

# 仅测试模型切换（不发送对话）
python scripts/chat.py --dry-run "测试"
```

### Agent 集成（以 Claude Code 为例）

在 SKILL.md 或 CLAUDE.md 中声明本工具，Agent 即可在需要时自动调用：

```yaml
- 日常杂活：用我自己的模型处理
- 遇到复杂任务（头脑风暴、方案设计、写 spec/plan）：
  1. 调用 gemini-web-automation-skill
  2. 将 Gemini 的回复作为参考，继续完成工作
```

默认使用 Gemini 2.5 Pro + extended thinking 处理高难度任务；使用 **3.5 Flash** 作为多模态辅助（为没有视觉能力的模型提供看图能力）。

### JSON 响应格式

```json
{
  "protocol": "gemini-runtime-api",
  "api_version": "1.3",
  "request_id": "20260705-175528-5e03",
  "contract": {
    "expected": {"model": "Pro", "thinking": "extended"},
    "actual": {"model": "Pro", "thinking": "extended"}
  },
  "ok": true,
  "reply": "你好！今天有什么可以帮你的？"
}
```

出错时：

```json
{
  "ok": false,
  "error": {"code": "LOGIN_REQUIRED"},
  "next_action": "RUN_BOOTSTRAP"
}
```

| 错误码 | 含义 |
|---|---|
| `LOGIN_REQUIRED` | 未登录 — 运行 `bootstrap.py` |
| `ENV_NOT_FOUND` | `.env` 不存在 — 从 `.env.example` 复制 |
| `PROXY_REQUIRED` | 无法访问 Gemini — 检查代理 |
| `MODEL_MISMATCH` | 期望的模型不可用 |
| `STREAM_TIMEOUT` | AI 回复超时 |

## 配置项

详见 `.env.example`：

| 变量 | 默认值 | 说明 |
|---|---|---|
| `CHROME_PATH` | 自动检测 | Chrome 可执行文件路径 |
| `USER_DATA_DIR` | `./userdata` | 浏览器 Profile 目录，用于持久化登录态 |
| `REMOTE_DEBUGGING_PORT` | `9222` | CDP 端口 |
| `PROXY_SERVER` | — | Google 访问代理（国内用户必填） |
| `MODEL_NAME` | `Pro` | 默认模型（Pro、Flash、Flash-Lite） |
| `THINKING_LEVEL` | `extended` | 思考等级（extended、standard） |

## 工作原理

```
chat.py
  │
  ├── 1. 环境检查 (.env、网络、代理)
  ├── 2. 连接 Chrome（CDP 温启动 → 冷启动回退）
  ├── 3. 确保 Gemini 页面（复用已有标签页或新建）
  ├── 4. 确保模型（按需切换到期望模型/思考等级）
  ├── 5. 发送 Prompt（可选附带图片）
  └── 6. 流式接收回复（等待稳定 → 返回 JSON）
```

Runtime 复用 Chrome 的用户数据目录，登录状态跨运行持续保存。冷启动（启动新 Chrome）仅在未找到正确 Profile 的已有 Chrome 实例时发生。

## 项目结构

```
├── scripts/
│   ├── chat.py          # 主运行时 — 日常使用的唯一入口
│   └── bootstrap.py     # 一次性设置：登录向导
├── references/
│   ├── architecture.md  # 设计决策
│   ├── gemini.md        # 页面交互选择器与模式
│   └── maintenance.md   # 故障排查与反模式
├── .env.example         # 配置模板
├── CHANGELOG.md
└── SKILL.md             # Agent 集成说明
```

## 许可

MIT
