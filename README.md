# Gemini Web Automation

[English](README.en.md)

通过浏览器自动化 [Gemini](https://gemini.google.com/app) 的 Python 运行时——发送 Prompt、上传图片、切换模型、获取回复，全部通过结构化 JSON 返回。

专为 AI Agent（Claude Code 等）集成设计，也可作为独立 CLI 工具使用。

## 特性

- **会话持久化** — 登录一次，后续重复使用浏览器 Profile
- **温/冷启动** — 优先通过 CDP 连接已有 Chrome，必要时自动启动新实例
- **模型管理** — 自动发现、切换、验证模型及思考等级（标准/扩展）
- **图片附件** — 将图片粘贴到对话中
- **结构化 JSON 输出** — `ok`、`contract`、`reply`、`error.code`、`next_action`
- **健康检查** — 快速查看运行状态，不发起对话
- **代理支持** — HTTP、HTTPS、SOCKS5

## 环境要求

- Python 3.9+
- Google Chrome、Chromium 或 Microsoft Edge
- 可访问 [Gemini](https://gemini.google.com) 的 Google 账号
- （中国用户）能访问 Google 服务的代理

## 快速开始

```bash
# 1. 克隆
git clone https://github.com/YOUR_USERNAME/gemini-web-automation.git
cd gemini-web-automation

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
