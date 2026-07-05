"""
bootstrap.py — Cold Start 一次性初始化

用法:
    python scripts/bootstrap.py

流程: 环境检测 → 安装依赖 → 配置 .env → 启动 Chrome → Headed 登录 → 保存 UserData
仅执行一次，之后日常走 Warm Start。
"""

import os
import sys
import shutil
import subprocess
import urllib.request
from pathlib import Path

if sys.platform == "win32":
    sys.stdout.reconfigure(encoding="utf-8")


BASE = Path(__file__).resolve().parent.parent
ENV_EXAMPLE = BASE / ".env.example"
ENV_TARGET = BASE / ".env"
USERDATA_DIR = BASE / "userdata"


def _find_chrome():
    candidates = [
        shutil.which("chrome"),
        shutil.which("google-chrome"),
        shutil.which("chromium"),
        shutil.which("chromium-browser"),
        shutil.which("edge"),
        shutil.which("msedge"),
    ]
    if sys.platform == "win32":
        candidates += [
            os.path.expandvars(r"%ProgramFiles%\Google\Chrome\Application\chrome.exe"),
            os.path.expandvars(r"%ProgramFiles(x86)%\Google\Chrome\Application\chrome.exe"),
            os.path.expandvars(r"%LocalAppData%\Google\Chrome\Application\chrome.exe"),
            os.path.expandvars(r"%ProgramFiles(x86)%\Microsoft\Edge\Application\msedge.exe"),
        ]
    return next((c for c in candidates if c and os.path.isfile(c)), None)


def check_environment() -> bool:
    """检查 Python 版本、Chrome 可用性、端口占用。"""
    print("[1/5] 检查环境...")

    if sys.version_info < (3, 9):
        print("  ✗ Python >= 3.9  required")
        return False

    chrome = _find_chrome()

    if not chrome:
        print("  ✗ Chrome/Chromium/Edge 未找到，请先安装")
        return False

    print(f"  ✓ Python {sys.version_info.major}.{sys.version_info.minor}")
    print(f"  ✓ Chrome: {chrome}")

    # 检查 CDP 端口是否被占
    try:
        urllib.request.urlopen("http://127.0.0.1:9222/json/version", timeout=2)
        print("  ! 端口 9222 已被占用（Chrome 已在运行）")
        print("  ! 你可以直接使用 Warm Start")
    except Exception:
        print("  ✓ 端口 9222 可用")

    return True


def install_dependencies():
    """安装 Playwright 及浏览器（已安装则跳过）。"""
    print("[2/5] 安装依赖...")
    try:
        import playwright
        print("  ✓ Playwright 已安装，跳过")
        return
    except ImportError:
        pass
    subprocess.run(
        [sys.executable, "-m", "pip", "install", "playwright", "python-dotenv"],
        check=True,
    )
    subprocess.run(
        [sys.executable, "-m", "playwright", "install", "chromium"],
        check=True,
    )
    print("  ✓ 依赖安装完成")


def setup_env():
    """从 .env.example 生成 .env，提示用户配置。"""
    print("[3/5] 配置环境变量...")
    if not ENV_EXAMPLE.exists():
        print(f"  ✗ 未找到 {ENV_EXAMPLE}")
        sys.exit(1)

    if ENV_TARGET.exists():
        print("  ✓ .env 已存在，跳过")
        return

    env_content = ENV_EXAMPLE.read_text(encoding="utf-8")
    print(f"  已生成 {ENV_TARGET}")
    print("  请编辑 .env 中的 PROXY_SERVER（国内用户必填）")
    print("  示例: PROXY_SERVER=http://127.0.0.1:7890")
    ENV_TARGET.write_text(env_content, encoding="utf-8")


def start_chrome_and_login():
    """启动 Headed Chrome → 用户手动登录 → 保存 UserData。"""
    print("[4/5] 启动 Chrome（Headed）...")

    proxy = ""
    if ENV_TARGET.exists():
        for line in ENV_TARGET.read_text(encoding="utf-8").splitlines():
            if line.startswith("PROXY_SERVER="):
                proxy = line.split("=", 1)[1].strip()
                break

    chrome = _find_chrome()
    if not chrome:
        print("  ✗ 未找到 Chrome")
        return

    args = [
        chrome,
        f"--user-data-dir={USERDATA_DIR}",
        "--remote-debugging-port=9222",
        "--no-first-run",
        "--no-default-browser-check",
        "https://gemini.google.com/app",
    ]
    if proxy:
        args.append(f"--proxy-server={proxy}")

    subprocess.Popen(args, shell=(sys.platform == "win32"))
    print(f"  ✓ Chrome 已启动，UserData: {USERDATA_DIR}")
    print()
    print("  ===============================")
    print("  请在浏览器中完成以下操作：")
    print("  1. 登录你的 Google 账号（Gemini 页面已自动打开）")
    print("  2. 确认 Gemini 聊天界面正常显示")
    print("  ===============================")
    input("  完成后按 Enter 继续...")


def verify_login():
    """UserData 持久化，无需验证。"""
    print("[5/5] 保存配置...")
    if USERDATA_DIR.exists():
        print(f"  ✓ UserData 已保存: {USERDATA_DIR}")
    print()
    print("  ===============================")
    print("  Cold Start 完成！现在可以：")
    print("  python scripts/chat.py \"你好\"")
    print("  ===============================")


def main():
    print("=" * 50)
    print("  AI Chat Automation — Cold Start")
    print("=" * 50)
    print()

    if not check_environment():
        sys.exit(1)

    install_dependencies()
    setup_env()
    start_chrome_and_login()
    verify_login()


if __name__ == "__main__":
    main()
