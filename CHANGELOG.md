# Changelog

## 1.1.0 (2026-07-04)

### Features

- **Off-Screen 模式** — Chrome 以 `--window-position=-32000,0` 启动，完全隐藏（非 headless），登录态不受影响
- **`--headed` 标志** — 加此参数可恢复窗口显示，调试用
- **发现驱动模型切换** — 5 阶段自动切换：读按钮 → 匹配判断 → 枚举菜单 → 坐标/evaluate 点击 → 验证
- **联合匹配** — (模型, 思考等级) 作为复合键，Pro + standard ≠ Pro + extended
- **`--dry-run` 模式** — 仅测试模型切换，不发送对话
- **支持所有 4 种变体** — Pro + extended, Pro + standard, Flash, Flash-Lite

### Fixes

- **`cur_family` 更新** — 模型切换后更新家族缓存，防止 Flash 被错误匹配思考等级
- **`USER_DATA_DIR` 绝对路径** — 启动时解析为绝对路径，防止冷启动找不到 Profile
- **`THINKING_LEVEL` 重复** — 清理 .env 中重复行
- **Chrome 不真正退出** — `connect_over_cdp().close()` 仅断开 CDP 连接，不杀死 Chrome 进程

### Architecture

- `_ensure_model()` — 发现驱动模型选择（5 阶段），替代固定选择器匹配
- `_parse_menu_items()` — 菜单项解析，提取 family/version 字段
- `_state_matches()` — 联合匹配判断（模型 + 思考等级）
- `_model_info()` — 从页面按钮文本读取当前模型信息

## 1.0.0 (2026-07-03)

### Features

- **Cold Start** — 一次性初始化脚本 (`scripts/bootstrap.py`)，覆盖环境检测、依赖安装、代理配置、Headed 登录
- **Warm Start** — 日常对话 5-20s 完成，通过 SessionManager 复用已有会话
- **Runtime First** — 优先复用 CDP / Browser / Page / Tab，不重复创建
- **8 层页面分析** — `scripts/analyze_page.py` 维护工具 (DOM → Accessibility → Locator → Layout → MO → Network → Screenshot → Report)
- **状态机** — ChatSession 6 状态 (READY / INPUT / SUBMIT / WAIT / STREAMING / FINISHED / ERROR) + 每步 deadline 超时模式
- **代理支持** — 通过 `--proxy-server` 支持 http://、https://、socks5://
- **失败证据** — 异常时自动保存 screenshot / HTML / Accessibility / URL / Console

### Architecture

- BrowserManager — Chrome 生命周期（CDP 优先）
- SessionManager — Warm Start 会话复用核心
- LoginManager — 元素级登录检测（非 URL）
- ChatManager — 对话状态机
- SelectorRegistry — 由 analyze_page.py 自动维护

### Principles

- 7 条 Design Principles（Runtime First / Fail Fast / Reuse / State Driven / Lazy Loading / Self Healing / Low Maintenance）
