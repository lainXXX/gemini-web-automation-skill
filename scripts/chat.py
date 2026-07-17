"""
chat.py — Gemini Runtime API

永远返回 JSON。供 Agent 调用。
Agent 仅根据 ok、contract、reply、error.code、next_action 决定下一步。

用法:
    python scripts/chat.py "你好"
    python scripts/chat.py "描述图片" -a photo.jpg
    python scripts/chat.py --health
"""

import os, sys, json, base64, asyncio, argparse, time, socket, uuid, re
from pathlib import Path
from urllib.parse import urlparse
from dotenv import load_dotenv

load_dotenv(Path(__file__).resolve().parent.parent / ".env")
if sys.platform == "win32":
    sys.stdout.reconfigure(encoding="utf-8")

# ── Protocol ──────────────────────────────────────────────────
PROTOCOL = "gemini-runtime-api"
API_VERSION = "1.3"
CAPABILITY = {
    "image": True,
    "pdf": False,
    "audio": False,
    "video": False,
    "thinking": True,
}

# ── Config ─────────────────────────────────────────────────────
TARGET_URL = os.getenv("TARGET_URL", "https://gemini.google.com/app")
_RAW_PORT = os.getenv("REMOTE_DEBUGGING_PORT", "")
CDP_PORT = int(_RAW_PORT) if _RAW_PORT.isdigit() else 9222
_DEFAULT_CHROME = {
    "win32":  r"C:\Program Files\Google\Chrome\Application\chrome.exe",
    "darwin": "/Applications/Google Chrome.app/Contents/MacOS/Google Chrome",
    "linux":  "/usr/bin/google-chrome",
}
CHROME_PATH = os.getenv("CHROME_PATH",
    _DEFAULT_CHROME.get(sys.platform, "google-chrome"))
_raw_udir = os.getenv("USER_DATA_DIR", "")
USER_DATA_DIR = str((Path(__file__).resolve().parent.parent / _raw_udir).resolve()) if _raw_udir else \
    str(Path(__file__).resolve().parent.parent / "userdata")
PROXY_SERVER = os.getenv("PROXY_SERVER")
EXPECTED_MODEL = os.getenv("MODEL_NAME")
EXPECTED_THINKING = os.getenv("THINKING_LEVEL")

# ── Session ─────────────────────────────────────────────────────
SESSION_DIR = Path(USER_DATA_DIR) / ".runtime" / "sessions"

def _session_file(key: str) -> Path:
    return SESSION_DIR / f"{key}.json"

def _load_session(key: str) -> dict | None:
    fp = _session_file(key)
    if fp.exists():
        try:
            return json.loads(fp.read_text(encoding="utf-8"))
        except Exception:
            pass
    return None

def _save_session(data: dict, key: str):
    SESSION_DIR.mkdir(parents=True, exist_ok=True)
    _session_file(key).write_text(json.dumps(data, ensure_ascii=False), encoding="utf-8")

def _clear_session(key: str):
    fp = _session_file(key)
    if fp.exists():
        fp.unlink()

def _resolve_session_key(cli_key: str | None) -> str:
    if cli_key:
        return cli_key
    cwd = Path.cwd().resolve().as_posix()
    return re.sub(r"[^A-Za-z0-9._-]", "_", cwd)

# ── Selectors ─────────────────────────────────────────────────
INPUT_SEL = 'div[contenteditable="true"][role="textbox"]'
SEND_SEL = 'button[aria-label="Send message"], button[aria-label="发送消息"]'
MODEL_SEL = 'button[aria-label*="模式选择器"]'
PROFILE_SEL = '[data-test-id="accounts-profile-button"], button[aria-label*="Google Account"], button[aria-label*="账号"]'
LOGIN_BTN_SEL = 'a[href*="signin"], a[href*="login"], a[aria-label*="登录"], a[aria-label*="Sign in"]'
HISTORY_SEL = 'message-content, nav[aria-label*="历史"], nav[aria-label*="History"]'
MIME_MAP = {'.png': 'image/png', '.jpg': 'image/jpeg', '.jpeg': 'image/jpeg',
            '.webp': 'image/webp', '.gif': 'image/gif'}

# ── Model ──────────────────────────────────────────────────────
MODEL_FAMILY_ALIASES = {
    "pro": "Pro", "3.1 pro": "Pro", "gemini pro": "Pro",
    "flash": "Flash", "3.5 flash": "Flash", "gemini flash": "Flash",
    "flash-lite": "Flash-Lite", "3.1 flash-lite": "Flash-Lite",
    "gemini flash-lite": "Flash-Lite",
}
THINKING_MAP = {
    "extended": "扩展", "扩展": "扩展",
    "extended thinking": "扩展", "deep": "扩展",
    "standard": "标准", "标准": "标准", "normal": "标准",
}
PRO_FAMILIES = {"Pro"}

# ── Errors ─────────────────────────────────────────────────────
ERROR_MESSAGES = {
    "MODEL_MISMATCH":      "模型不匹配，未能切换到期望模型",
    "CHROME_NOT_FOUND":    "Chrome 未找到，请检查 CHROME_PATH",
    "CHROME_START_FAILED": "Chrome 启动失败 (20s 超时)",
    "CHROME_NOT_RUNNING":  "Chrome 未运行，请先运行 bootstrap.py",
    "CDP_CONNECT_FAILED":  "CDP 连接失败",
    "PAGE_NOT_FOUND":      "无法导航到 Gemini 页面",
    "NO_PAGES":            "浏览器中没有页面，请先运行 bootstrap.py",
    "LOGIN_REQUIRED":      "Gemini 未登录，请运行 bootstrap.py",
    "INPUT_NOT_FOUND":     "输入框未就绪 (10s 超时)",
    "STREAM_TIMEOUT":      "AI 回复超时",
    "ATTACHMENT_FAILED":   "附件上传失败",
    "TOO_MANY_IMAGES":     "图片最多 10 张",
    "NETWORK_ERROR":       "网络异常，请检查网络连接",
    "ENV_NOT_FOUND":       ".env 不存在，请复制 .env.example 并配置",
    "INVALID_ENV":         ".env 配置有误，请检查",
    "PROXY_REQUIRED":      "无法连接到 gemini.google.com，请检查 PROXY_SERVER 或系统代理",
    "UNKNOWN":             "未知错误",
    "UNKNOWN_PAGE":        "无法识别页面状态，请检查 Gemini 页面",
}
NEXT_ACTIONS = {
    "ENV_NOT_FOUND":     "CREATE_ENV",
    "LOGIN_REQUIRED":    "RUN_BOOTSTRAP",
    "CHROME_NOT_RUNNING":"RUN_BOOTSTRAP",
    "CDP_CONNECT_FAILED":"RUN_BOOTSTRAP",
    "NO_PAGES":          "RUN_BOOTSTRAP",
    "PROXY_REQUIRED":    "CHECK_PROXY",
    "NETWORK_ERROR":     "CHECK_PROXY",
    "INVALID_ENV":       "FIX_ENV",
    "MODEL_MISMATCH":    "SWITCH_MODEL",
}


# ═══════════════════════════════════════════════════════════════
#  Helpers
# ═══════════════════════════════════════════════════════════════

def _normalize_thinking(val):
    if not val: return "unknown"
    v = val.strip()
    if "扩展" in v: return "extended"
    if "标准" in v: return "standard"
    return v.lower()

def _resolve_family(name):
    n = name.strip()
    n_lower = n.lower()
    if n_lower in MODEL_FAMILY_ALIASES:
        return MODEL_FAMILY_ALIASES[n_lower]
    words = set(n_lower.split())
    for k, v in sorted(MODEL_FAMILY_ALIASES.items(), key=lambda x: -len(x[0])):
        if set(k.split()).issubset(words):
            return v
    for w in n.split():
        if w and w[0].isupper():
            return w
    return name

def _state_matches(cur_name, cur_thinking,
                   check_model=None, check_thinking=None):
    cm = check_model or EXPECTED_MODEL
    ct = check_thinking if check_thinking is not None else EXPECTED_THINKING
    if not cm and not ct:
        return True
    if cm:
        if _resolve_family(cur_name) != _resolve_family(cm):
            return False
    if _resolve_family(cur_name) not in PRO_FAMILIES:
        return True
    if ct:
        exp_norm = THINKING_MAP.get(ct.lower(), ct)
        cur_norm = THINKING_MAP.get(cur_thinking.lower(), cur_thinking) if cur_thinking and cur_thinking != "unknown" else "标准"
        return exp_norm == cur_norm
    if cur_thinking and cur_thinking != "unknown":
        return cur_thinking in ("standard", "标准")
    return True

def _parse_menu_items(raw):
    models, thinking_items = [], []
    for item in raw:
        text = item.get("text", "")
        if "思考等级" in text:
            thinking_items.append({**item, "level": "扩展" if "扩展" in text else "标准"})
        else:
            parts = text.split()
            family = None
            for p in parts:
                if p[0].isupper() and p not in ("AI",):
                    family = p.rstrip(",").rstrip(".")
                    break
            if not family:
                family = parts[-1] if parts else text
            models.append({**item, "family": family,
                          "version": parts[0] if parts and parts[0][0].isdigit() else None})
    return models, thinking_items

def _cdp_available():
    sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    try: return sock.connect_ex(("127.0.0.1", CDP_PORT)) == 0
    finally: sock.close()


# ═══════════════════════════════════════════════════════════════
#  ChatRuntime — encapsulates all Playwright interaction
# ═══════════════════════════════════════════════════════════════

class ChatRuntime:
    """Encapsulates browser, page, and Gemini interaction.

    No Playwright details leak outside — Agent only sees JSON.
    """

    STATE_IDLE = "IDLE"
    STATE_READY = "READY"
    STATE_RECONNECTED = "RECONNECTED"
    STATE_LOGIN_REQUIRED = "LOGIN_REQUIRED"
    STATE_FAILED = "FAILED"

    def __init__(self, headed: bool = False, session_url: str | None = None):
        self._p = None
        self._browser = None
        self._page = None
        self._headed = headed
        self._session_url = session_url
        self._startup = "warm"
        self._state = self.STATE_IDLE
        self._browser_version = "unknown"
        self._page_mode = "unknown"
        self._initial_mr_count = 0

    # ── properties ──────────────────────────────────────────────

    @property
    def info(self) -> dict:
        return {
            "startup": self._startup,
            "browser": "reused",
            "session": self._session_url or "new",
            "page": self._page_mode,
            "browser_version": self._browser_version,
            "runtime_state": self._state,
            "health": "healthy" if self._state in (self.STATE_READY, self.STATE_RECONNECTED) else self._state.lower(),
        }

    @property
    def page(self):
        return self._page

    @property
    def startup(self):
        return self._startup

    # ── connect ──────────────────────────────────────────────────

    async def connect(self) -> dict | None:
        """Connect to CDP. Returns error dict or None.
        Does NOT manage Chrome lifecycle — bootstrap.py is responsible for Chrome."""
        from playwright.async_api import async_playwright
        self._p = await async_playwright().start()

        if not _cdp_available():
            return self._result_error("CHROME_NOT_RUNNING", "RUN_BOOTSTRAP")

        try:
            self._browser = await self._p.chromium.connect_over_cdp(
                f"http://127.0.0.1:{CDP_PORT}")
            self._state = self.STATE_RECONNECTED
            self._browser_version = self._browser.version
            return None
        except Exception:
            return self._result_error("CDP_CONNECT_FAILED", "RUN_BOOTSTRAP")

    # ── ensure_chat ──────────────────────────────────────────────

    async def _find_page_by_url(self, url: str) -> object | None:
        normalized = url.rstrip('/')
        for ctx in self._browser.contexts:
            for pg in ctx.pages:
                if pg.url.rstrip('/') == normalized:
                    return pg
        return None

    async def ensure_chat(self) -> tuple[dict, dict | None]:
        """Open a tab to Gemini.

        - Has session:     find bootstrap page at TARGET_URL → reuse + goto(session_url).
                           No bootstrap page → new tab + goto(session_url).
        - No session:      find bootstrap page at TARGET_URL → reuse.
                           No bootstrap page → new tab + goto(TARGET_URL).
        """
        ctx = self._browser.contexts[0]

        if self._session_url:
            existing = await self._find_page_by_url(self._session_url)
            if existing:
                self._page = existing
                self._page_mode = "reused"
                ps = await self._classify()
                if ps["state"] == "CHAT" and not self._headed:
                    await self._background_window()
                return ps, None
            existing = await self._find_page_by_url(TARGET_URL)
            self._page = existing or await ctx.new_page()
            self._page_mode = "reused" if existing else "created"
            target = self._session_url
        else:
            existing = await self._find_page_by_url(TARGET_URL)
            if existing:
                self._page = existing
                self._page_mode = "reused"
                ps = await self._classify()
                if ps["state"] == "CHAT" and not self._headed:
                    await self._background_window()
                return ps, None
            self._page = await ctx.new_page()
            self._page_mode = "created"
            target = TARGET_URL

        try:
            await self._page.goto(target, timeout=60000,
                                  wait_until="domcontentloaded")
            await asyncio.sleep(3)
        except Exception:
            return {}, self._result_error("PAGE_NOT_FOUND")

        await self._page.bring_to_front()
        ps = await self._classify()

        if ps["state"] == "CAPTCHA":
            self._state = self.STATE_LOGIN_REQUIRED
            return ps, self._result_error("LOGIN_REQUIRED", "RUN_BOOTSTRAP")

        # 瞬态保护：LOGIN/UNKNOWN 可能是页面加载中 — reload 一次确认
        if ps["state"] in ("LOGIN", "UNKNOWN"):
            try:
                await self._page.reload(timeout=15000)
                await asyncio.sleep(4)
                ps = await self._classify()
            except Exception:
                pass

        if ps["state"] in ("LOGIN", "CAPTCHA"):
            self._state = self.STATE_LOGIN_REQUIRED
            return ps, self._result_error("LOGIN_REQUIRED", "RUN_BOOTSTRAP")

        if ps["state"] == "UNKNOWN":
            return ps, self._result_error("UNKNOWN_PAGE", "RUN_BOOTSTRAP")

        self._state = self.STATE_READY
        if not self._headed:
            await self._background_window()
        return ps, None

    async def _background_window(self):
        """Minimize Chrome window via CDP (background, not hidden)."""
        try:
            cdp = await self._page.context.new_cdp_session(self._page)
            win = await cdp.send("Browser.getWindowForTarget")
            await cdp.send("Browser.setWindowBounds", {
                "windowId": win["windowId"],
                "bounds": {"windowState": "minimized"},
            })
        except Exception:
            pass

    async def _collect_features(self) -> dict:
        """Use Playwright locators to detect page features.

        Rules:
        - login_button: DOM presence is enough (hidden sign-in = not logged in)
        - profile/textarea/model_switcher: must be visible (only meaningful when rendered)
        - history: DOM presence is enough (cached from prior session)
        """
        features = {"profile": False, "textarea": False,
                     "model_switcher": False, "login_button": False,
                     "history": False}
        # login_button/history: count() > 0 (DOM presence)
        for name, sel in [("login_button", LOGIN_BTN_SEL), ("history", HISTORY_SEL)]:
            try:
                features[name] = await self._page.locator(sel).count() > 0
            except Exception:
                pass
        # profile/textarea/model_switcher: is_visible() (must be rendered)
        for name, sel in [("profile", PROFILE_SEL), ("textarea", INPUT_SEL),
                          ("model_switcher", MODEL_SEL)]:
            try:
                features[name] = await self._page.locator(sel).first.is_visible()
            except Exception:
                pass
        return features

    async def _classify(self) -> dict:
        """Deterministic page state classification. No scoring/probability.

        Returns CHAT | LOGIN | CAPTCHA | UNKNOWN with feature map for debugging.
        """
        url = self._page.url
        title = await self._page.title()
        in_captcha = await self._page.evaluate(
            "() => document.querySelector('iframe[src*=\"captcha\"]') !== null")
        if in_captcha:
            return {"state": "CAPTCHA", "url": url, "title": title}

        # URL fast path: Google SSO page
        if "accounts.google.com" in url or "/signin" in url.lower():
            return {"state": "LOGIN", "url": url, "title": title}

        features = await self._collect_features()

        # Deterministic priority order (each rule individually sufficient)
        if features["profile"]:
            return {"state": "CHAT", "url": url, "title": title, "features": features}

        if features["textarea"] and not features["login_button"]:
            return {"state": "CHAT", "url": url, "title": title, "features": features}

        if features["model_switcher"] and not features["login_button"]:
            return {"state": "CHAT", "url": url, "title": title, "features": features}

        if features["login_button"]:
            return {"state": "LOGIN", "url": url, "title": title, "features": features}

        if features["history"] and not features["login_button"]:
            return {"state": "CHAT", "url": url, "title": title, "features": features}

        return {"state": "UNKNOWN", "url": url, "title": title, "features": features}

    # ── ensure_model ─────────────────────────────────────────────

    async def ensure_model(self, force_model: str | None = None,
                           force_thinking: str | None = None) -> tuple[dict, list, dict]:
        """发现驱动模型选择。5 阶段。同原逻辑。

        force_model / force_thinking: 覆盖 EXPECTED_MODEL / EXPECTED_THINKING，最高优先级。
        """
        effective_model = force_model or EXPECTED_MODEL
        effective_thinking = force_thinking if force_thinking is not None else EXPECTED_THINKING
        warnings = []
        diag = {
            "model": {"status": "skipped", "expected": effective_model},
            "thinking": {"status": "skipped", "expected": effective_thinking},
        }

        # Phase 1: read button, check match
        current = await self._read_model_button()
        if _state_matches(current.get("name", ""), current.get("thinking", ""),
                          effective_model, effective_thinking):
            diag["model"]["status"] = "ok"
            if effective_thinking and _resolve_family(current.get("name", "")) in PRO_FAMILIES:
                diag["thinking"]["status"] = "ok"
            else:
                diag["thinking"]["status"] = "irrelevant"
            return current, warnings, diag

        # Phase 2: open menu, enumerate
        _clear_esc = lambda: None
        try:
            await self._page.keyboard.press("Escape")
            await asyncio.sleep(0.3)
            await self._page.keyboard.press("Escape")
            await asyncio.sleep(0.2)
        except Exception:
            pass
        try:
            await self._page.locator(MODEL_SEL).click()
            await asyncio.sleep(0.8)
        except Exception as e:
            warnings.append(f"模型选择器无法点击: {e}")
            diag["error"] = str(e)
            return current, warnings, diag

        items_raw = await self._page.evaluate("""() => {
            const items = document.querySelectorAll('[role="menuitem"], gem-menu-item');
            return Array.from(items).map((el, i) => {
                const r = el.getBoundingClientRect();
                return { index: i, text: el.innerText.trim().replace(/\\s+/g, ' '),
                         disabled: el.getAttribute('aria-disabled') === 'true',
                         center_x: r.left + r.width / 2, center_y: r.top + r.height / 2 };
            });
        }""")
        models, thinking_items = _parse_menu_items(items_raw)
        diag["model"]["available"] = [m["text"] for m in models]
        if thinking_items:
            diag["thinking"]["available"] = [t["text"] for t in thinking_items]

        # Phase 3: switch model
        exp_family = _resolve_family(effective_model) if effective_model else None
        cur_family = _resolve_family(current.get("name", ""))
        model_changed = False

        if effective_model and exp_family != cur_family:
            target = None
            for m in models:
                if m["disabled"]:
                    continue
                if m.get("family") and m["family"].lower() == exp_family.lower():
                    target = m
                    break
            if not target:
                for m in models:
                    if m["disabled"]:
                        continue
                    if _resolve_family(m["text"]).lower() == exp_family.lower():
                        target = m
                        break
            if target:
                await self._page.mouse.click(target["center_x"], target["center_y"])
                await asyncio.sleep(1.0)
                model_changed = True
                diag["model"]["status"] = "switched"
                diag["model"]["resolved_to"] = target["text"]
                verify_info = await self._read_model_button()
                if verify_info.get("name") and _resolve_family(verify_info["name"]).lower() != exp_family.lower():
                    await self._page.evaluate(
                        '(idx) => document.querySelectorAll(\'[role="menuitem"]\')[idx].click()',
                        target["index"])
                    await asyncio.sleep(0.8)
                    verify_info = await self._read_model_button()
                    if _resolve_family(verify_info.get("name", "")).lower() != exp_family.lower():
                        warnings.append(
                            f"模型 '{effective_model}' 点击切换后未生效，按钮仍显示 '{verify_info.get('name')}'")
                        diag["model"]["status"] = "click_failed"
                current = verify_info
                cur_family = _resolve_family(current.get("name", ""))
            else:
                available = [m["text"] for m in models if not m["disabled"]]
                disabled = [m["text"] for m in models if m["disabled"]]
                diag["model"]["status"] = "not_found"
                warnings.append(f"模型 '{effective_model}' 未在菜单中找到"
                                + (f" (可用: {available})" if available else "")
                                + (f" (已禁用: {disabled})" if disabled else ""))
        else:
            diag["model"]["status"] = "ok"

        # Phase 4: switch thinking level
        check_thinking = (effective_thinking
                          and (cur_family in PRO_FAMILIES
                               or (exp_family and exp_family in PRO_FAMILIES)))
        if check_thinking:
            if model_changed:
                await asyncio.sleep(0.5)
                try:
                    await self._page.locator(MODEL_SEL).click()
                    await asyncio.sleep(0.8)
                except Exception:
                    pass
            exp_zh = THINKING_MAP.get(effective_thinking.lower(), effective_thinking)
            diag["thinking"]["resolved_to"] = exp_zh
            try:
                await self._page.evaluate("""() => {
                    const items = document.querySelectorAll('[role="menuitem"][value="thinking_level"]');
                    for (const el of items) { if (el.innerText.includes('思考等级')) { el.click(); break; } }
                }""")
                await asyncio.sleep(0.8)
                sub_items = await self._page.evaluate("""() => {
                    const items = document.querySelectorAll('[role="menuitem"]');
                    return Array.from(items).map((el, i) => {
                        const r = el.getBoundingClientRect();
                        return { index: i, text: el.innerText.trim().replace(/\\s+/g, ' '),
                                 disabled: el.getAttribute('aria-disabled') === 'true',
                                 center_x: r.left + r.width / 2, center_y: r.top + r.height / 2 };
                    });
                }""")
                diag["thinking"]["available"] = [s["text"] for s in sub_items]
                options = [s for s in sub_items if "思考等级" not in s["text"]]
                if not options:
                    warnings.append("思考等级子菜单未展开：无子选项")
                    diag["thinking"]["status"] = "submenu_empty"
                else:
                    target = None
                    for s in sub_items:
                        if s["disabled"]:
                            continue
                        if exp_zh in s["text"] and "思考等级" not in s["text"]:
                            target = s
                            break
                    if target:
                        await self._page.evaluate(
                            '(idx) => document.querySelectorAll(\'[role="menuitem"]\')[idx].click()',
                            target["index"])
                        await asyncio.sleep(0.8)
                        diag["thinking"]["status"] = "switched"
                        vt = (await self._read_model_button()).get("thinking", "")
                        if _normalize_thinking(vt) not in (exp_zh, EXPECTED_THINKING) and vt != "unknown":
                            warnings.append(f"思考等级点击后验证失败: 期望 {exp_zh}，按钮显示 '{vt}'")
                            diag["thinking"]["status"] = "verification_failed"
                    else:
                        warnings.append(f"思考等级 '{exp_zh}' 未在子菜单中找到 (选项: {[s['text'] for s in options]})")
                        diag["thinking"]["status"] = "not_found"
            except Exception as e:
                warnings.append(f"思考等级切换异常: {e}")
                diag["thinking"]["status"] = "error"
        else:
            diag["thinking"]["status"] = "irrelevant"

        # Phase 5: close menu, final verify
        try:
            await self._page.keyboard.press("Escape")
            await asyncio.sleep(0.2)
            await self._page.keyboard.press("Escape")
            await asyncio.sleep(0.2)
            if await self._page.locator('[role="menu"]').count() > 0:
                await self._page.mouse.click(10, 10)
                await asyncio.sleep(0.2)
            if await self._page.locator('[role="menu"]').count() > 0:
                warnings.append("菜单关闭验证失败：仍存在 [role=\"menu\"] 元素")
                diag["menu_close"] = "failed"
        except Exception:
            pass

        final_info = await self._read_model_button()
        if effective_model and final_info.get("name"):
            if _resolve_family(final_info["name"]).lower() != _resolve_family(effective_model).lower():
                warnings.append(f"最终模型验证失败: 期望 {effective_model} → 实际 '{final_info['name']}'")
                diag["model"]["status"] = "verification_failed"
        if check_thinking and effective_thinking:
            ft = final_info.get("thinking", "")
            if _normalize_thinking(ft) == "unknown":
                pass
            elif _normalize_thinking(ft) != effective_thinking.lower():
                warnings.append(f"最终思考等级验证失败: 期望 {effective_thinking} → 实际 '{ft}'")
                diag["thinking"]["status"] = "verification_failed"
        return final_info, warnings, diag

    async def _read_model_button(self) -> dict:
        info = {"name": None, "thinking": "unknown", "verified": False, "source": "env"}
        try:
            if await self._page.locator(MODEL_SEL).count() > 0:
                text = await self._page.locator(MODEL_SEL).inner_text(timeout=3000)
                info["source"] = "page"
                lines = [l.strip() for l in text.split("\n") if l.strip()]
                if lines:
                    info["name"] = lines[0]
                    for l in lines[1:]:
                        if "思考" in l or l in ("标准", "扩展"):
                            info["thinking"] = _normalize_thinking(l)
                            break
                info["verified"] = bool(info["name"])
        except Exception:
            pass
        if not info["name"]:
            info["name"] = EXPECTED_MODEL or "unknown"
        return info

    # ── send ─────────────────────────────────────────────────────

    async def send(self, prompt: str, attachments: list[str] | None = None) -> dict | None:
        """Send prompt + attachments. Returns error dict or None."""
        deadline = time.time() + 10
        while time.time() < deadline:
            if await self._page.locator(INPUT_SEL).is_visible():
                break
            await asyncio.sleep(0.3)
        else:
            return self._result_error("INPUT_NOT_FOUND")

        await self._page.locator(INPUT_SEL).click()
        await asyncio.sleep(0.3)

        if attachments:
            existing = [p for p in attachments if os.path.isfile(p)]
            if len(existing) > 10:
                return self._result_error("TOO_MANY_IMAGES")
            ok = await self._upload_images(existing)
            if not ok:
                return self._result_error("ATTACHMENT_FAILED")

        # 统一 execCommand 插入文本（比 fill() 快一个数量级，无逐字输入竞态）
        await self._page.evaluate("""(text) => {
            const div = document.querySelector('div[contenteditable="true"][role="textbox"]');
            if (!div) return; div.focus();
            const s = window.getSelection(); const r = document.createRange();
            r.selectNodeContents(div); r.collapse(false); s.removeAllRanges(); s.addRange(r);
            document.execCommand('insertText', false, text);
        }""", prompt)

        # 回读校验：确认 Prompt 已完整写入再发送
        deadline = time.time() + 5
        while time.time() < deadline:
            inserted = await self._page.evaluate("""() => {
                const e = document.querySelector('div[contenteditable="true"][role="textbox"]');
                return e ? e.innerText : '';
            }""")
            if inserted.strip() == prompt.strip():
                break
            await asyncio.sleep(0.1)
        else:
            # 超时后重试一次
            await self._page.evaluate("""(text) => {
                const div = document.querySelector('div[contenteditable="true"][role="textbox"]');
                if (!div) return; div.focus();
                const s = window.getSelection(); const r = document.createRange();
                r.selectNodeContents(div); r.collapse(false); s.removeAllRanges(); s.addRange(r);
                document.execCommand('insertText', false, text);
            }""", prompt)

        self._initial_mr_count = await self._page.evaluate(
            "() => document.querySelectorAll('model-response').length")
        send_btn = self._page.locator(SEND_SEL)
        deadline = time.time() + 3
        while time.time() < deadline:
            if await send_btn.is_visible():
                await send_btn.click()
                break
            await asyncio.sleep(0.2)
        else:
            await self._page.keyboard.press("Enter")

        return None

    async def _upload_images(self, paths: list[str]) -> bool:
        """Upload images via best available strategy. Returns True on success.
        Caller must cap at 10 images."""
        existing = [p for p in paths if os.path.isfile(p)]
        if not existing:
            return False

        # Strategy 1: 单次 ClipboardEvent 批量粘贴多张（避免逐张 paste 竞态）
        if await self._bulk_paste_images(existing):
            await self._wait_images_ready(len(existing))
            return True

        # Strategy 2: 逐个 paste 兜底
        for fp in existing:
            try:
                await self._paste_image(fp)
            except Exception:
                return False
        await self._wait_images_ready(len(existing))
        return True

    async def _bulk_paste_images(self, paths: list[str]) -> bool:
        """上传策略 2: 单次 ClipboardEvent，所有文件在一个 DataTransfer 中。"""
        files = []
        for fp in paths:
            with open(fp, 'rb') as f:
                b64 = base64.b64encode(f.read()).decode('ascii')
            ext = Path(fp).suffix.lower()
            mime = MIME_MAP.get(ext, 'image/png')
            files.append({'b64': b64, 'mime': mime, 'name': Path(fp).name})
        try:
            await self._page.evaluate("""(files) => {
                const div = document.querySelector('div[contenteditable="true"][role="textbox"]');
                if (!div) return; div.focus();
                const dt = new DataTransfer();
                for (const f of files) {
                    const bs = atob(f.b64);
                    const bytes = new Uint8Array(bs.length);
                    for (let i = 0; i < bs.length; i++) bytes[i] = bs.charCodeAt(i);
                    const blob = new Blob([bytes], { type: f.mime });
                    dt.items.add(new File([blob], f.name, { type: f.mime }));
                }
                div.dispatchEvent(new ClipboardEvent('paste',
                    {clipboardData: dt, bubbles: true, cancelable: true}));
            }""", files)
            await asyncio.sleep(2)
            return True
        except Exception:
            return False

    async def _paste_image(self, path: str):
        """上传策略 3: 单张 paste 兜底。"""
        with open(path, 'rb') as f:
            b64 = base64.b64encode(f.read()).decode('ascii')
        ext = Path(path).suffix.lower()
        mime = MIME_MAP.get(ext, 'image/png')
        await self._page.evaluate("""({b64, mime}) => {
            const div = document.querySelector('div[contenteditable="true"][role="textbox"]');
            if (!div) return; div.focus();
            const bs = atob(b64); const bytes = new Uint8Array(bs.length);
            for (let i = 0; i < bs.length; i++) bytes[i] = bs.charCodeAt(i);
            const blob = new Blob([bytes], { type: mime });
            const file = new File([blob], 'image.'+mime.split('/')[1], { type: mime });
            const dt = new DataTransfer(); dt.items.add(file);
            div.dispatchEvent(new ClipboardEvent('paste',
                {clipboardData: dt, bubbles: true, cancelable: true}));
        }""", {'b64': b64, 'mime': mime})
        await asyncio.sleep(1)

    async def _wait_images_ready(self, expected: int):
        """Wait for expected number of image thumbnails in input. 15s timeout."""
        try:
            deadline = time.time() + 15
            while time.time() < deadline:
                ready = await self._page.evaluate("""(exp) => {
                    const div = document.querySelector('div[contenteditable="true"][role="textbox"]');
                    if (!div) return false;
                    const imgs = div.querySelectorAll('img');
                    const chips = div.querySelectorAll('[data-test-id*="image"], [class*="image"], [class*="attachment"]');
                    return (imgs.length + chips.length) >= exp;
                }""", expected)
                if ready:
                    return
                await asyncio.sleep(0.3)
        except Exception:
            pass

    # ── collect_reply ────────────────────────────────────────────

    async def collect_reply(self) -> tuple[str, dict | None, int]:
        """Wait for streaming. Returns (reply, error, attach_count).

        model-response innerText format:
          [thinking headers...]
          Gemini 说

          [actual reply content...]

        We split at "Gemini 说" and track stability on the part after it.
        """
        wait_to = 90 if EXPECTED_THINKING == "extended" else 20
        deadline = time.time() + wait_to
        while time.time() < deadline:
            count = await self._page.evaluate(
                "() => document.querySelectorAll('model-response').length")
            if count > self._initial_mr_count:
                break
            await asyncio.sleep(0.3)
        else:
            return "", self._result_error("STREAM_TIMEOUT"), 0

        def _get_reply(raw: str) -> str:
            """Extract content after 'Gemini 说' marker."""
            idx = raw.find("Gemini 说")
            if idx >= 0:
                return raw[idx + len("Gemini 说"):].strip()
            return raw.strip()

        reply = ""
        stable_dur = 5 if EXPECTED_THINKING == "extended" else 2
        deadline = time.time() + 120
        last = ""
        stable = 0.0
        while time.time() < deadline:
            await asyncio.sleep(0.5)
            raw = await self._page.evaluate(
                "() => { const e = document.querySelectorAll('model-response'); return e.length ? e[e.length-1].innerText : ''; }")
            cur = _get_reply(raw)
            # Don't count empty text as stable — content hasn't arrived yet
            if not cur:
                last = ""
                stable = 0.0
                continue
            if cur == last:
                if stable == 0:
                    stable = time.time()
                elif time.time() - stable >= stable_dur:
                    reply = cur
                    break
            else:
                last = cur
                stable = 0.0
        else:
            reply = _get_reply(last)
        return reply, None, 0

    # ── session ───────────────────────────────────────────────────

    def capture_session(self, key: str = "default") -> str | None:
        """Read page URL after reply and save session ID if present."""
        url = self._page.url if self._page else ""
        if url.startswith(TARGET_URL + "/") and len(url) > len(TARGET_URL) + 1:
            session_id = url[len(TARGET_URL) + 1:]
            _save_session({"session_id": session_id, "url": url}, key)
            return session_id
        return None

    # ── close ────────────────────────────────────────────────────

    async def close(self):
        if self._p:
            await self._p.stop()

    def _result_error(self, code: str, next_action: str = None) -> dict:
        d = {"code": code, "message": ERROR_MESSAGES.get(code, code)}
        if next_action:
            d["next_action"] = next_action
        return d


# ═══════════════════════════════════════════════════════════════
#  Pipeline
# ═══════════════════════════════════════════════════════════════

def _check_env() -> dict | None:
    """Check environment. Returns full error dict or None."""
    env_path = Path(__file__).resolve().parent.parent / ".env"
    if not env_path.exists():
        return _full_error("ENV_NOT_FOUND")
    port_raw = os.getenv("REMOTE_DEBUGGING_PORT", "")
    if port_raw and not port_raw.isdigit():
        return _full_error("INVALID_ENV")
    cp = os.getenv("CHROME_PATH", "")
    if cp and not os.path.isfile(cp):
        return _full_error("CHROME_NOT_FOUND")
    return None


async def _check_network() -> dict | None:
    """Quick connectivity check. Returns full error dict or None."""
    if PROXY_SERVER:
        proxy = urlparse(PROXY_SERVER)
        host = proxy.hostname or "127.0.0.1"
        port = proxy.port or 7890
        try:
            _, writer = await asyncio.wait_for(
                asyncio.open_connection(host, port), timeout=3)
            writer.close()
            await writer.wait_closed()
            return None
        except (OSError, asyncio.TimeoutError):
            return _full_error("PROXY_REQUIRED")
    parsed = urlparse(TARGET_URL)
    if parsed.hostname:
        try:
            _, writer = await asyncio.wait_for(
                asyncio.open_connection(parsed.hostname, 443), timeout=5)
            writer.close()
            await writer.wait_closed()
            return None
        except (OSError, asyncio.TimeoutError):
            return _full_error("NETWORK_ERROR")
    return None


async def execute(prompt: str, attachments: list[str] | None = None,
                  headed: bool = False, dry_run: bool = False,
                  new_chat: bool = False, reset: bool = False,
                  session_key: str | None = None) -> dict:
    """Execute a Gemini conversation. Returns structured JSON."""
    request_id = time.strftime("%Y%m%d-%H%M%S") + "-" + uuid.uuid4().hex[:4]
    session_key = _resolve_session_key(session_key)

    # Stage 0: Session management
    if reset:
        _clear_session(session_key)
        return _base(request_id) | {"ok": True, "reply": None,
                                     "session": "reset"}

    # Stage 1: Preflight
    err = _check_env()
    if err: return err
    if not os.path.isdir(USER_DATA_DIR):
        return _full_error("LOGIN_REQUIRED", request_id=request_id,
                           next_action="RUN_BOOTSTRAP")
    err = await _check_network()
    if err: return err

    # Load or create session
    if new_chat:
        _clear_session(session_key)
        session_data = None
    else:
        session_data = _load_session(session_key)

    session_url = session_data["url"] if session_data else None

    # Stage 2: Connect Runtime
    runtime = ChatRuntime(headed=headed, session_url=session_url)
    err = await runtime.connect()
    if err:
        return _with_diag(err, runtime.info)

    # Stage 3: Ensure Chat Page
    page_state, err = await runtime.ensure_chat()
    if err:
        return _with_diag(err, runtime.info)

    # Stage 4: Ensure Model
    if attachments:
        expected_model = "Flash"
        expected_thinking = ""
    else:
        expected_model = EXPECTED_MODEL
        expected_thinking = EXPECTED_THINKING

    model_info, _, _ = await runtime.ensure_model(
        force_model=expected_model if attachments else None,
        force_thinking=expected_thinking if attachments else None)

    if dry_run:
        await runtime.close()
        result = _build_result(request_id, model_info,
                               expected_model=expected_model,
                               expected_thinking=expected_thinking)
        return _with_diag(result, runtime.info)

    # Stage 5: Send Prompt
    err = await runtime.send(prompt, attachments)
    if err:
        return _with_diag(err, runtime.info)

    # Stage 6: Collect Reply
    reply, err, _ = await runtime.collect_reply()
    if err:
        return _with_diag(err, runtime.info)

    # Capture session ID from URL after first conversation
    runtime.capture_session(key=session_key)

    await runtime.close()
    result = _build_result(request_id, model_info, reply,
                           expected_model=expected_model,
                           expected_thinking=expected_thinking)
    return _with_diag(result, runtime.info)


async def health() -> dict:
    """Quick health check, no conversation."""
    request_id = time.strftime("%Y%m%d-%H%M%S") + "-" + uuid.uuid4().hex[:4]

    # Env
    env_err = _check_env()
    if env_err:
        return {**env_err, "api_version": API_VERSION, "capability": CAPABILITY,
                "runtime_state": "FAILED", "health": "env_missing"}

    # CDP
    if _cdp_available():
        from playwright.async_api import async_playwright
        p = await async_playwright().start()
        try:
            browser = await p.chromium.connect_over_cdp(
                f"http://127.0.0.1:{CDP_PORT}")
            runtime_state = "READY"
            browser_state = "running"
            session_state = "alive"
            page_state = "unknown"
            model_name = EXPECTED_MODEL or "unknown"
            for ctx in browser.contexts:
                for pg in ctx.pages:
                    if TARGET_URL in pg.url:
                        features = await pg.evaluate("""() => {
                            const body = document.body;
                            return {
                                login_btn: !!body.querySelector('a[href*="signin"], a[href*="login"], a[aria-label*="登录"], a[aria-label*="Sign in"]'),
                                avatar:     !!body.querySelector('img[alt*="avatar"], img[alt*="profile"], button[aria-label*="account"], button[aria-label*="账号"], a[aria-label*="账号"], img.mavatar-image'),
                                model_btn:  !!body.querySelector('button[aria-label*="模式选择器"]'),
                                model_btn_text: (() => {
                                    const btn = document.querySelector('button[aria-label*="模式选择器"]');
                                    return btn ? btn.innerText : '';
                                })(),
                            };
                        }""")
                        if features["login_btn"]:
                            page_state = "LOGIN"
                        elif features["avatar"]:
                            page_state = "CHAT"
                        elif await pg.locator(MODEL_SEL).count() > 0:
                            model_text = await pg.locator(MODEL_SEL).inner_text(timeout=3000)
                            model_text = model_text.split("\n")[0].strip()
                            if "Pro" in model_text and "登录" not in model_text:
                                page_state = "CHAT"
                            else:
                                page_state = "UNKNOWN"
                        else:
                            page_state = "PAGE"
                        try:
                            if await pg.locator(MODEL_SEL).count() > 0:
                                model_name = await pg.locator(MODEL_SEL).inner_text(timeout=3000)
                                model_name = model_name.split("\n")[0].strip()
                        except Exception:
                            pass
                        break
            await p.stop()
            return {
                "protocol": PROTOCOL,
                "api_version": API_VERSION,
                "capability": CAPABILITY,
                "request_id": request_id,
                "success": True,
                "runtime_state": runtime_state,
                "browser": browser_state,
                "session": session_state,
                "page": page_state,
                "model": model_name,
                "health": "healthy",
            }
        except Exception:
            await p.stop()
            return {
                "protocol": PROTOCOL,
                "api_version": API_VERSION,
                "capability": CAPABILITY,
                "request_id": request_id,
                "success": True,
                "runtime_state": "DISCONNECTED",
                "browser": "stopped",
                "health": "degraded",
            }
    else:
        return {
            "protocol": PROTOCOL,
            "api_version": API_VERSION,
            "capability": CAPABILITY,
            "request_id": request_id,
            "success": True,
            "runtime_state": "IDLE",
            "browser": "stopped",
            "health": "idle",
        }


# ═══════════════════════════════════════════════════════════════
#  Response builders
# ═══════════════════════════════════════════════════════════════

def _base(request_id: str = None) -> dict:
    return {
        "protocol": PROTOCOL,
        "api_version": API_VERSION,
        "capability": CAPABILITY,
        "request_id": request_id or time.strftime("%Y%m%d-%H%M%S") + "-" + uuid.uuid4().hex[:4],
    }


def _full_error(code: str, request_id: str = None,
                next_action: str = None) -> dict:
    result = _base(request_id)
    result["ok"] = False
    result["error"] = {"code": code}
    if next_action:
        result["next_action"] = next_action
    elif code in NEXT_ACTIONS:
        result["next_action"] = NEXT_ACTIONS[code]
    return result


def _check_model_match(model_info: dict,
                       expected_model: str = None,
                       expected_thinking: str = None) -> dict | None:
    """Returns error-code dict or None if match OK."""
    em = expected_model
    et = expected_thinking if expected_thinking is not None else EXPECTED_THINKING
    if not em and not et:
        return None
    cur_name = model_info.get("name", "")
    cur_thinking = model_info.get("thinking", "")
    if _state_matches(cur_name, cur_thinking, em, et):
        return None
    return {"code": "MODEL_MISMATCH"}


def _with_diag(result: dict, runtime_info: dict) -> dict:
    """Merge runtime diagnostics into result."""
    if runtime_info:
        result["diagnostics"] = {
            "startup": runtime_info.get("startup"),
            "page": runtime_info.get("page"),
            "session": runtime_info.get("session"),
        }
    return result


def _build_result(request_id: str, model_info: dict, reply: str = None,
                   expected_model: str = None,
                   expected_thinking: str = None) -> dict:
    """Decision Layer + Output Layer. Debug state is NOT included."""
    result = _base(request_id)
    result["contract"] = {
        "expected": {
            "model": expected_model or EXPECTED_MODEL,
            "thinking": expected_thinking if expected_thinking is not None else EXPECTED_THINKING,
        },
        "actual": {
            "model": model_info.get("name"),
            "thinking": model_info.get("thinking"),
        },
    }

    model_err = _check_model_match(model_info, expected_model, expected_thinking)
    if model_err:
        result["ok"] = False
        result["error"] = model_err
        result["next_action"] = "SWITCH_MODEL"
        result["reply"] = None
    else:
        result["ok"] = True
        result["reply"] = reply

    return result


# ═══════════════════════════════════════════════════════════════
#  CLI
# ═══════════════════════════════════════════════════════════════

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Gemini Runtime API")
    parser.add_argument("prompt", nargs="*", help="对话文本")
    parser.add_argument("-a", "--attachment", action="append", dest="attachments",
                        help="附件路径（图片，可多次使用）")
    parser.add_argument("--headed", action="store_true",
                        help="保持浏览器窗口在前台（默认后台运行）")
    parser.add_argument("--dry-run", action="store_true",
                        help="仅测试模型切换，不发送对话")
    parser.add_argument("--health", action="store_true",
                        help="健康检查（不执行对话）")
    parser.add_argument("--new", action="store_true", dest="new_chat",
                        help="新建对话（清除 session，打开新标签页）")
    parser.add_argument("--reset", action="store_true",
                        help="清除 session 文件，不执行对话")
    parser.add_argument("--session", default=None,
                        help="会话标识，用于隔离不同场景的会话（默认: 按工作目录自动派生）")
    args = parser.parse_args()
    session_key = _resolve_session_key(args.session)

    if args.health:
        result = asyncio.run(health())
    elif args.reset:
        result = asyncio.run(execute("", reset=True, session_key=session_key))
    elif args.prompt:
        result = asyncio.run(execute(
            " ".join(args.prompt),
            args.attachments or None,
            headed=args.headed,
            dry_run=args.dry_run,
            new_chat=args.new_chat,
            session_key=session_key,
        ))
    else:
        parser.print_help()
        sys.exit(1)

    print(json.dumps(result, ensure_ascii=False))

