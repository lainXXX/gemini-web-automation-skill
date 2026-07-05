# Architecture — 系统架构

## 核心设计原则

1. **Runtime First** — 默认环境已就绪，优先复用已有 Chrome/Session/Page，不检查/不重建
2. **Fail Fast** — 任何等待必须有 deadline，不允许 while True
3. **Cold/Warm 分离** — Cold Start（首次登录）headed 显示窗口；Warm Start（日常对话）Chrome 最小化到后台运行
4. **Self Healing** — 检测到 CDP 断开 / 页面失效时自动恢复，而非直接崩溃
5. **状态驱动** — 任何操作前先分类页面状态（classify），再决定下一步

## 核心工作流

```
Environment
    │
    ▼
CDP :9222 可用？
    ├── YES → connectOverCDP()
    │           │
    │           ▼
    │     复用已有 Page/Tab？
    │      ├── 是 Gemini 页 → 直接使用
    │      ├── 有其他 Page → 导航到 Gemini
    │      └── 没有 Page → new_page + goto
    │           │
    │           ▼
    │     classify() 判断页面状态
    │      ├── CHAT → 执行状态机
    │      ├── LOGIN → 引导登录
    │      ├── CAPTCHA → 暂停等待人工
    │      └── UNKNOWN → 收集证据 → abort
    │
    └── NO → _launch_chrome() 等待 :9222
```

## 模块职责（设计知识）

### Browser 生命周期
- 单 Chrome 进程 + CDP 暴露，多 Agent 共享
- Warm Start: 仅 connectOverCDP()，不重启 Chrome
- Cold Start: 启动 Chrome（headed），供手动登录
- Self Healing: CDP 断连 → 自动重启 Chrome 并重连
- Proxy: 从 .env 读取，支持 http/https/socks5

### Session 复用
- 优先复用当前 Page（URL 正确直接返回）
- URL 不对时 goto 导航，不创建新 Page
- 全部失效时 new_page
- Session 断开时自动恢复

### Page 分类
- 第一道防线：任何操作前先分类
- 分类依据：URL + DOM 特征（非 URL 唯一判断）
- 类型：LOGIN / GEMINI / CHAT / CAPTCHA / ERROR / UNKNOWN
- 分类耗时：数百毫秒

### 登录管理
- 登录态靠 Chrome User Data 持久化（非 storageState）
- 检测方式：检查页面元素（input / avatar），不依赖 URL
- Cold Start: headed 窗口，用户手动登录
- 登录态过期：自动检测 → collect_evidence → 提示重新 Cold Start

### 对话引擎
- 6 状态状态机（见 gemini.md）
- 每步独立 deadline 超时
- Attachment 策略模式（Clipboard → FileChooser → DOM）
- 回复检测：轮询 + 稳定窗口

## 冷热分离

| 模式 | 频率 | 目标耗时 | 说明 |
|------|------|---------|------|
| Warm Start | 日常 95%+ | 5-20s | 复用已有资源，后台运行 |
| Cold Start | 仅首次 | 一次性 | headed 窗口，手动登录 |
| Maintenance | 页面改版 | 一年几次 | analyze_page，更新 selector |

## 配置

.env 体系（cp .env.example .env 即用）
- CHROME_PATH / USER_DATA_DIR / REMOTE_DEBUGGING_PORT
- PROXY_SERVER: http/https/socks5
- HEADLESS 已废弃；Warm Start 默认 Chrome 最小化到后台，保持登录态且不干扰用户
- MODEL_NAME / THINKING_LEVEL
