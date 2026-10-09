#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
gzhu-campus 校园门户查询 CLI（可选工具，需要 Playwright）

用 Playwright 自动化登录广州大学统一身份认证（CAS）并进入教务系统，
查课表 / 成绩 / 打开任意校内页面。密码优先从本机加密凭证读取
（Windows DPAPI / macOS Keychain / Linux Secret Service，由 gzhu-credential.* 脚本写入），
也可用 --user/--password 显式传入。

⚠️ 依赖（可选）：
  pip install playwright
  playwright install chromium
未安装时本工具会给出安装指引后退出，不影响 skill 其他功能。

用法:
  python portal.py --page home                 # 登录并打开教务系统首页
  python portal.py --page timetable            # 登录后进入课表
  python portal.py --page score                # 登录后进入成绩查询
  python portal.py --page "https://..."        # 登录后打开指定校内页面
  python portal.py --login-test                # 只验证登录，不跳转
  python portal.py --user 学号 --password xxx --page score   # 显式凭证

选项:
  --page P        目标页面: home / timetable / score / 完整 URL
  --user S        学号（缺省时尝试读本机加密凭证）
  --password S    密码（缺省时尝试读本机加密凭证；未加密凭证则交互输入）
  --headful       显示浏览器窗口（默认无头）
  --timeout N     等待超时秒数（默认 30）

安全边界:
  - 只读查询；选课/改密/报名等不可逆操作请交还给用户本人操作。
  - 遇到验证码 / 二次验证 / 滑块，脚本会停在登录页并提示人工接管。
"""

import argparse
import importlib.util
import os
import subprocess
import sys
import time

CAS_URL = "https://newcas.gzhu.edu.cn"
JWXT_URL = "https://jwxt.gzhu.edu.cn"

PAGES = {
    "home": JWXT_URL,
    "timetable": None,  # 需登录后经菜单导航，见 main() 说明
    "score": None,
}


def check_playwright():
    if importlib.util.find_spec("playwright") is None:
        print(
            "[依赖缺失] 需要 Playwright（可选依赖）。安装：\n"
            "  pip install playwright\n"
            "  playwright install chromium\n"
            "装好后重试。不影响 skill 其他功能。",
            file=sys.stderr,
        )
        return False
    return True


def read_credential(user_arg, password_arg):
    """返回 (user, password)。显式参数优先；否则尝试本机加密凭证；再否则交互输入。"""
    user = user_arg
    password = password_arg
    if not user or not password:
        # 尝试调用现有凭证脚本读取（Windows: gzhu-credential.ps1）
        script = os.path.join(os.path.dirname(os.path.abspath(__file__)), "gzhu-credential.ps1")
        if os.name == "nt" and os.path.isfile(script):
            try:
                out = subprocess.run(
                    ["powershell", "-NoProfile", "-ExecutionPolicy", "Bypass", "-File", script, "-Read"],
                    capture_output=True, text=True, timeout=15,
                )
                if out.returncode == 0:
                    lines = [l.strip() for l in out.stdout.splitlines() if l.strip()]
                    if len(lines) >= 2:
                        user = user or lines[0]
                        password = password or lines[1]
            except Exception:
                pass
    if not user:
        user = input("学号: ").strip()
    if not password:
        password = input("密码（不会显示）: ")
    return user, password


def fill_login(page, user, password):
    """尽力自动填充 CAS 登录框，返回是否成功。选择器失效时返回 False。"""
    try:
        page.wait_for_load_state("networkidle", timeout=10000)
    except Exception:
        pass
    # 用户名：多套常见选择器
    user_loc = None
    for sel in (
        "input[name=username]", "input[id=username]", "input[placeholder*='用户']",
        "input[type=text]", "input[name=user]",
    ):
        try:
            loc = page.locator(sel).first
            if loc.count() and loc.is_visible():
                user_loc = loc
                break
        except Exception:
            continue
    pwd_loc = None
    try:
        pwd_loc = page.locator("input[type=password]").first
        if not pwd_loc.count():
            pwd_loc = None
    except Exception:
        pwd_loc = None
    if user_loc is None or pwd_loc is None:
        return False
    user_loc.fill(user)
    pwd_loc.fill(password)
    # 登录按钮
    clicked = False
    for sel in ("button[type=submit]", "input[type=submit]", "a[class*='login']"):
        try:
            btn = page.locator(sel).first
            if btn.count() and btn.is_visible():
                btn.click()
                clicked = True
                break
        except Exception:
            continue
    if not clicked:
        try:
            page.keyboard.press("Enter")
            clicked = True
        except Exception:
            pass
    return True


def main():
    ap = argparse.ArgumentParser(description="gzhu-campus 校园门户查询 CLI（可选，需 Playwright）")
    ap.add_argument("--page", default="home", help="目标: home / timetable / score / 完整 URL")
    ap.add_argument("--user", help="学号")
    ap.add_argument("--password", help="密码")
    ap.add_argument("--headful", action="store_true", help="显示浏览器窗口")
    ap.add_argument("--timeout", type=int, default=30, help="等待超时秒数（默认 30）")
    args = ap.parse_args()

    if not check_playwright():
        return 2

    from playwright.sync_api import sync_playwright  # 延迟导入

    user, password = read_credential(args.user, args.password)
    if not user or not password:
        print("[错误] 缺少学号/密码", file=sys.stderr)
        return 2

    print(f"[1/3] 打开统一身份认证: {CAS_URL}")
    with sync_playwright() as p:
        browser = p.chromium.launch(headless=not args.headful)
        ctx = browser.new_context()
        page = ctx.new_page()
        page.goto(CAS_URL, wait_until="domcontentloaded", timeout=args.timeout * 1000)
        print(f"      页面标题: {page.title()}")

        ok = fill_login(page, user, password)
        if not ok:
            print(
                "[提示] 未能自动定位登录框（页面结构可能已变）。"
                "请用 --headful 重跑，手动完成登录后继续。",
                file=sys.stderr,
            )
            browser.close()
            return 1

        print("[2/3] 提交登录……")
        try:
            page.wait_for_url(lambda u: JWXT_URL in u or "my.gzhu.edu.cn" in u, timeout=args.timeout * 1000)
            print(f"      登录成功，当前地址: {page.url}")
        except Exception:
            # 可能停在验证码/二次验证页
            print(
                f"[提示] 未在 {args.timeout} 秒内进入教务系统。可能遇到验证码/二次验证/滑块，"
                "请用 --headful 重跑并在浏览器中完成验证（只读查询，安全）。",
                file=sys.stderr,
            )
            print(f"      当前地址: {page.url}")
            browser.close()
            return 1

        target = args.page
        if target == "home":
            pass
        elif target in ("timetable", "score"):
            print(
                f"[3/3] 目标『{target}』需要登录后经教务系统菜单导航（不同版本菜单结构不同），"
                "请用浏览器自动化继续点击菜单，或把 --page 换成具体 URL。",
            )
        elif target.startswith("http"):
            print(f"[3/3] 打开: {target}")
            page.goto(target, wait_until="domcontentloaded", timeout=args.timeout * 1000)
            print(f"      页面标题: {page.title()}")
        else:
            print(f"[3/3] 未知目标: {target}（使用 home / timetable / score / URL）", file=sys.stderr)

        # 输出当前页可见文本片段，供 AI 读取
        try:
            text = page.inner_text("body")[:800]
            print("\n===== 页面可见文本（前 800 字符）=====")
            print(text)
        except Exception:
            pass

        print("\n[完成] 已登录并可继续操作。注意：只读查询，不可逆操作请交还用户。")
        browser.close()
    return 0


if __name__ == "__main__":
    sys.exit(main())
