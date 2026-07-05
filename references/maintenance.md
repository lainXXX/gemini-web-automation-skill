# Maintenance — 维护指南

## 失败证据收集

异常时自动保存到 `artifacts/`，全部应在 5s 内完成：

| 文件 | 命令 | 排查价值 |
|------|------|---------|
| failure.png | page.screenshot() | 一看就知道页面状态 |
| failure.html | page.content() | 分析 DOM 结构 |
| url.txt | page.url | 确认当前 URL |
| console.log | page.evaluate() / 监听 console 事件 | 检查 JS 错误 |

**何时收集：** 任何状态机阶段超时或异常时立即收集，不要重试。

## Fail Fast 原则

### 每步 deadline（禁止 while True）

```python
# ❌ 错误：永远不会超时
while True:
    if await element.is_visible():
        break
    await asyncio.sleep(0.5)

# ✅ 正确：有 deadline
deadline = time.time() + timeout
while time.time() < deadline:
    if await element.is_visible():
        return
    await asyncio.sleep(0.3)
raise TimeoutError("描述性错误信息")
```

### 各阶段合理超时

| 阶段 | 超时 | 说明 |
|------|------|------|
| 页面就绪 | 10s | 等待输入框出现 |
| 输入 | 5s | 输入 prompt |
| 提交 | 3s | 点击发送按钮 |
| 首响应 | 15s(标准) / 60s(扩展思考) | 等待 AI 开始回复 |
| 流式完成 | 120s | 等待回复稳定 |
| 证据收集 | 5s | 异常时截图+HTML |

## Anti Pattern

| 错误做法 | 问题 | 正确做法 |
|---------|------|---------|
| 每次对话新 Chrome | 10 并发 = 2-3GB 内存 | 单 Chrome + CDP 复用 |
| sleep(30) 等回复 | 短回复浪费，长回复截断 | 轮询 + 稳定窗口 |
| 多进程共享 UserData | Profile already in use | 单 Chrome 进程 |
| 硬编码选择器 | 页面改版就崩 | 配置外置 + fallback 链 |
| 无超时等待 | 卡死到地老天荒 | 每步 deadline |
| 依赖 URL 判断登录 | 不可靠 | 检测页面元素 |
| 并发操作无锁 | DOM 竞争 | asyncio.Lock |

## 上线 Checklist

### Runtime First
- [ ] Session 复用：每次先检查已有 Page
- [ ] CDP 优先：connect_over_cdp() 而非 launch()
- [ ] Warm Start 路径：无维护性检查（环境检测/依赖安装/页面分析）
- [ ] Lazy Loading：仅在需要时 import

### 状态机
- [ ] 6 状态 + ERROR
- [ ] 每步独立 deadline（非全局 timeout）
- [ ] ERROR 状态自动 collect_evidence()
- [ ] 无 while True

### 失败证据
- [ ] 异常时自动保存：screenshot / HTML / URL
- [ ] Console 日志在异常时收集
- [ ] 全部 5s 内完成

### Proxy
- [ ] 启动参数含 `--proxy-server`
- [ ] 支持 http://、https://、socks5://
- [ ] Cold Start 能正确走代理登录

### 通用
- [ ] 默认 Chrome 最小化到后台运行（非 headless，保持登录态）
- [ ] 每个 Selector 有 2-3 级 fallback
- [ ] 无硬编码路径
- [ ] Cold Start 与 Warm Start 严格分离
- [ ] 所有 IO 操作为 async
- [ ] .env 中的敏感值不提交到 git

