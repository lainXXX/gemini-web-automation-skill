# gemini-web-automation-skill

> 让你的 AI Agent 拥有 Gemini Pro 深度思考能力。默认模型干杂活，硬骨头交给 Gemini。浏览器自动化，零 API 费。

## 这是一个 Skill，不是一个 Python 工具

**Skill** 是 AI 编码 Agent（Claude Code、Codex、OpenCode 等）的指令包。它教会你的 Agent 一项它原本没有的能力。

`gemini-web-automation-skill` 教会你的 Agent：**默认模型搞不定的事，交给 Gemini 3.1 Pro with extended thinking。** 背后的 Python 运行时只是实现细节，Agent 会自动调度它。

## 为什么需要这个 Skill

你日常用的模型（DeepSeek、豆包、GLM、Qwen）快、便宜，日常够用。

但遇到**写技术方案、头脑风暴、设计架构、制定 Plan** 这种需要深度的任务时——Gemini 3.1 Pro with extended thinking 依然是目前最强之一。

这个 Skill 让你的 Agent 在继续用默认模型做日常活的同时，遇到硬骨头时自动调 Gemini。

## 安装

```bash
# 把 Skill 放到你的 Agent 技能目录（以 Claude Code 为例）
cp -r gemini-web-automation-skill ~/.claude/skills/gemini-skill

cd ~/.claude/skills/gemini-skill
cp .env.example .env
# 国内用户务必配置 PROXY_SERVER

# 首次：登录 Gemini
python scripts/bootstrap.py
```

首次登录一次，之后会话持久化，Agent 调用时无需人工干预。

## 它不是一个...

| ❌ 不是 | ✅ 是 |
|---|---|
| Gemini API 封装 | 浏览器自动化，零 API 费用，无速率限制 |
| 通用 Python 脚本 | **AI Agent 的 Skill**，附带 Python 运行时 |
| 替代你日常模型的工具 | 给默认模型兜底——它搞不定时再启用 |
| 需要每次手动操作的 CLI | 一次安装，Agent 自动判断时机并调用 |

## 什么时候触发

Agent 遇到以下场景时，会自动调用这个 Skill：

| 场景 | 会触发吗 |
|---|---|
| 头脑风暴 / 方案设计 | ✅ Gemini Pro + extended thinking |
| 写 Spec / Plan / PRD / 架构文档 | ✅ Gemini Pro + extended thinking |
| 需要看图分析（默认模型无视觉能力） | ✅ Gemini Flash |
| 快速问答 / 简单代码生成 | ❌ 用默认模型处理 |
| 日常闲聊 | ❌ 用默认模型处理 |

## Agent 怎么用这个 Skill

Agent 调用脚本，拿到结构化 JSON 回复：

```json
{
  "ok": true,
  "reply": "深度分析结果...",
  "contract": {
    "expected": {"model": "Pro", "thinking": "extended"},
    "actual": {"model": "Pro", "thinking": "extended"}
  }
}
```

出错时自动处理：

| 错误码 | Agent 自动做什么 |
|---|---|
| `LOGIN_REQUIRED` | 提示你运行 `bootstrap.py` 重新登录 |
| `PROXY_REQUIRED` | 提示检查代理配置 |
| `MODEL_MISMATCH` | 回退到可用模型 |
| `STREAM_TIMEOUT` | 返回超时错误，不重试 |

## 工作原理

```
Agent (Claude Code / Codex ...)
  └─ 遇到复杂任务 → 加载 SKILL.md 指令
       └─ chat.py
            ├─ 环境检查（.env、网络、代理）
            ├─ CDP 连接 Chrome（温启动 / 冷启动）
            ├─ 定位 Gemini 页面，切换模型
            ├─ 发送 Prompt（可选带图）
            └─ 流式回复 → 结构化 JSON
                 └─ Agent 拿到结果继续工作
```

## 另见

[GPT Web Chat Skill](https://github.com/mileist/gpt-web-chat-skill) — 同样的浏览器自动化架构，目标 chatgpt.com。

## 配置

| 变量 | 默认值 | 说明 |
|---|---|---|
| `CHROME_PATH` | 自动检测 | Chrome 浏览器路径 |
| `USER_DATA_DIR` | `./userdata` | 持久化登录态，跨运行保持 |
| `PROXY_SERVER` | — | Google 访问代理（国内用户必填） |
| `MODEL_NAME` | `Pro` | 默认模型（Pro / Flash / Flash-Lite） |
| `THINKING_LEVEL` | `extended` | 思考等级（extended / standard） |

## 项目结构

```
├── scripts/
│   ├── chat.py          # 主运行时 — Agent 日常只调这个
│   └── bootstrap.py     # 首次登录向导
├── references/
│   ├── architecture.md  # 设计决策
│   ├── gemini.md        # 页面交互选择器
│   └── maintenance.md   # 故障排查
├── SKILL.md             # 告诉 Agent 怎么用（核心）
├── .env.example
└── README.md
```

## 许可

MIT
