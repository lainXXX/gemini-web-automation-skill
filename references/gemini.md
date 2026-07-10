# Gemini — 页面状态机与交互

## 页面状态识别

首次进入 Gemini 页面或导航后，必须运行 classify() 判断当前状态。

| 状态 | 判断依据 | 处理 |
|------|---------|------|
| GEMINI | URL 含 gemini.google.com，DOM 含 contenteditable 输入框 | 可直接对话 |
| CHAT | URL 含 gemini.google.com，DOM 含 message-content 元素 | 对话已在进行 |
| LOGIN | URL 含 accounts.google.com/signin，或页面上有邮箱/密码输入框 | 引导手动登录 |
| CAPTCHA | DOM 特征匹配 Cloudflare / reCAPTCHA | 暂停，通知人工处理 |
| ERROR | HTTP 40x/50x，或页面含错误提示 | 收集证据 → abort |
| UNKNOWN | 以上均不匹配 | 收集证据 → abort |

**注意：** 不要只依赖 URL 判断登录态。Google 的 SSO 可能已登录但页面未跳转，需检测页面元素。

## 对话状态机

```
READY ──→ INPUT ──→ SUBMIT ──→ WAIT_RESPONSE ──→ STREAMING ──→ FINISHED
  │          │          │             │                │             │
  └──────────┴──────────┴─────────────┴────────────────┴─────────────┘
                                     │
                                     ▼
                                   ERROR（任一阶段超时或异常）
```

### 各阶段说明

| 阶段 | 动作 | 超时 | 说明 |
|------|------|------|------|
| READY | 等待聊天界面就绪 | 10s | 检测 contenteditable 输入框可见 |
| INPUT | 输入提示词 + 上传附件 | 5s | 有附件时先用 execCommand 插入文本（fill 会清空附件预览） |
| SUBMIT | 点击发送 / 按 Enter | 3s | 优先找发送按钮，其次 Enter |
| WAIT_RESPONSE | 等待 AI 开始回复 | 15s(标准) / 60s(扩展思考) | 轮询 message-content 直到有文本 |
| STREAMING | 等待回复稳定 | 120s | 连续 2s 无变化认为完成 |
| FINISHED | 提取最终文本 | 5s | 读取最后一个 message-content |

### 超时策略（Deadline Pattern）

每阶段独立 deadline，失败时精确知道哪个阶段超时：

```
deadline = time.time() + timeout
while time.time() < deadline:
    # do work
    await asyncio.sleep(interval)
raise TimeoutError("阶段名 + 超时时间")
```

### 扩展思考（Extended Thinking）

Gemini 的"扩展思考"模式会在回复前增加一段 Thinking 阶段：
- WAIT_RESPONSE 超时应从 15s 增加到 60s
- 回复内容可能包含思考过程和最终回答两部分
- 首次回复可能更长（模型加载）

## Selector 优先级

Gemini 页面使用 Angular，DOM 结构较复杂。Selector 应遵循以下优先级：

1. **data-testid / data-test** — 显式测试标识（最可靠）
2. **get_by_role() + name** — 语义角色不变
3. **aria-label** — 语义属性，相对稳定
4. **CSS [attr*=value]** — 属性包含匹配
5. **innerText** — 最后选择，且用 includes 而非 exact

### 关键 Selector（Gemini 当前版本）

```
输入框:       div[contenteditable="true"][role="textbox"]
发送按钮:     button[aria-label="Send message"] / button[aria-label="发送消息"]
上传按钮:     button[aria-label*="上传"]
模型选择器:   button[aria-label*="模式选择器"]
菜单项:       gem-menu-item  // Angular CDK overlay 自定义元素
消息内容:     message-content // 最后一个即最新回复
附件预览:     uploader-file-preview
底部菜单按钮: mat-bottom-sheet-container button.mdc-button
```

### Angular CDK 注意事项

Gemini 的菜单（模型选择、思考等级）使用 Angular CDK Overlay：
- CDP 的 locator.click() 可能不触发 Angular zone.js
- **顶层菜单项** → 优先使用 `page.mouse.click(x, y)` 坐标点击（模拟真实鼠标事件）
- **子菜单项**（如思考等级选项）→ `page.evaluate('el.click()')` 有效（元素已在 Accessibility 树中）
- 坐标通过 `element.getBoundingClientRect()` 获取
- 模型切换后菜单自动关闭，切换思考等级需重新打开菜单
- 菜单关闭策略：2x Escape + 点击页面空白区域兜底，处理后验证 `[role="menu"]` 已消失

## Attachment 上传策略

### 优先级

```
Bulk ClipboardStrategy（优先）
    │  单次 ClipboardEvent，所有文件一个 DataTransfer
    │  避免多张 paste 的竞态问题
    ▼
Individual ClipboardStrategy（兜底）
    │  逐个 paste，间隔 1s
    │  全部失败 → ATTACHMENT_FAILED
```

### Bulk ClipboardStrategy

单次 ClipboardEvent 粘贴多张图片，避免连续 paste 的竞态问题：

```
读取全部图片 → base64 数组
    ↓
page.evaluate()
    ↓
atob() → Uint8Array → Blob → File 数组
    ↓
一个 DataTransfer，items.add() 添加所有 File
    ↓
单次 new ClipboardEvent('paste', {clipboardData: dt})
    ↓
div.dispatchEvent(event)
    ↓
Gemini 认为一次粘贴了多张图片
```

**为什么不用系统剪贴板：** CDP 下 `Control+V` keyboard 事件无法访问系统剪贴板（安全限制）。直接构造 ClipboardEvent 绕过此限制且更稳定。

**注意：** 此事件是非 trusted 事件（`isTrusted=false`），Gemini 接受此模式，已验证可用。

### 等待策略

```
_wait_images_ready(expected_count)
    │  轮询输入框中 <img> + attachment 元素数量
    │  直到 ≥ expected 或 15s 超时
    │  避免单张 thumbnail 出现就误判全部完成
```

### 已知限制

- 非 trusted 的 paste 事件可能被部分页面拒绝（Gemini 接受）
- 三种策略依次降级尝试，不跳过

## 回复检测（Streaming）

采用**轮询 + 稳定窗口**策略：

```
每 0.5s 读取最后一个 message-content 的文本
连续 2s 无变化 → 认为回复完成
超时 120s → 返回已有内容
```

这种方法比固定 sleep 更好：短回复快（秒级返回），长回复不截断。

## 登录检测

判断是否已登录 Gemini：
- URL 不在 accounts.google.com/signin
- 页面上无邮箱/密码输入框
- 页面上有 contenteditable 输入框（已登录标志）
- 或页面右上角有用户头像

未登录时的处理：
- Warm Start → collect_evidence → 提示运行 Cold Start
- Cold Start → headed 窗口 → 用户手动登录 → UserData 持久化
