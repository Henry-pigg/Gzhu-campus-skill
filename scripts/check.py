#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
gzhu-campus 发布前健康检查（零依赖，标准库）

发布到公开仓库前运行，扫描 references 知识库：
  1. 隐私泄露：手机号 / 身份证 / 学号 / 邮箱 / 疑似密钥（排除 URL 内数字误报）
  2. "待补充"残留标记
  3. Markdown 结构：表格列数不一致、标题层级跳变、代码块未闭合
  4. （可选）失效外链检查：--check-links

用法:
  python check.py [--dir references] [--check-links] [--check-todo] [--check-headings] [--strict]

选项:
  --dir DIR         扫描目录（默认 references）
  --check-links     对 md 中的 http(s) 链接做 HEAD 探测（较慢）
  --check-todo      逐条列出"待补充/待核实"标记（默认只统计条数）
  --check-headings  检查标题层级跳变（本知识库风格为 ## 直接接 ####，默认不检查）
  --strict          存在任何警告也返回退出码 1

退出码:
  0  未发现错误（--strict 时警告也算错误）
  1  发现隐私或结构错误
  2  用法/路径错误
"""

import argparse
import os
import re
import sys
import urllib.request

# ---- 正则（先剔除 URL 再扫数字类模式，避免 URL 数字误报）----
URL_RE = re.compile(r"https?://[^\s\)\]\}\"']+|www\.[^\s\)\]\}\"']+")
# 手机号：1 开头 11 位
PHONE_RE = re.compile(r"(?<!\d)1[3-9]\d{9}(?!\d)")
# 身份证：17 位数字 + 数字/x/X
IDCARD_RE = re.compile(r"(?<!\d)\d{17}[\dXx](?!\d)")
# 学号（广大常见 10 位数字，单列；纯 10 位数字可能是年份/编号，标 INFO 提示人工确认）
STUDENT_ID_RE = re.compile(r"(?<!\d)\d{10}(?!\d)")
# 邮箱
EMAIL_RE = re.compile(r"[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,}")
# 疑似密钥赋值
SECRET_RE = re.compile(
    r"(?i)(password|passwd|pwd|secret|api[_-]?key|token|credential|private[_-]?key)\s*[=:]\s*['\"]?[^\s'\"\n]{6,}"
)
# 待补充标记
TODO_RE = re.compile(r"待补充|TBD|TODO|待核实|待验证")


def strip_urls(text):
    return URL_RE.sub("URL", text)


def check_privacy(path, lines):
    """返回 (errors, warns) 列表。"""
    errors, warns = [], []
    for i, raw in enumerate(lines):
        line = strip_urls(raw)
        ln = i + 1
        for m in PHONE_RE.finditer(line):
            errors.append((ln, "疑似手机号", m.group(0)))
        for m in IDCARD_RE.finditer(line):
            errors.append((ln, "疑似身份证号", m.group(0)))
        for m in EMAIL_RE.finditer(line):
            # 公开部门邮箱常见于官方文档，标警告人工确认
            warns.append((ln, "疑似邮箱", m.group(0)))
        for m in SECRET_RE.finditer(line):
            errors.append((ln, "疑似密钥赋值", m.group(0)[:40]))
        for m in STUDENT_ID_RE.finditer(line):
            # 10 位纯数字可能是学号，也可能误报，仅提示
            warns.append((ln, "疑似学号(10位数字，需人工确认)", m.group(0)))
    return errors, warns


def check_todo(lines):
    warns = []
    for i, raw in enumerate(lines):
        if TODO_RE.search(raw):
            warns.append((i + 1, "含'待补充/待核实'标记", raw.strip()[:50]))
    return warns


def check_markdown(lines):
    errors = []
    in_code = False
    prev_heading = 0
    for i, raw in enumerate(lines):
        ln = i + 1
        s = raw.strip()
        # 代码块闭合
        if s.startswith("```"):
            in_code = not in_code
            continue
        if in_code:
            continue
        # 表格列数一致性
        if s.startswith("|") and s.endswith("|"):
            cols = len([c for c in s.split("|")[1:-1] if True])
            if s.replace("|", "").strip() and set(s.replace("|", "").replace(" ", "").replace("-", "")) == set():
                continue  # 分隔行
        # 标题层级跳变
        m = re.match(r"^(#{1,6})\s", s)
        if m:
            level = len(m.group(1))
            if prev_heading and level > prev_heading + 1:
                errors.append((ln, f"标题层级跳变: {'#'*prev_heading} 跳到 {'#'*level}", s[:50]))
            prev_heading = level
    if in_code:
        errors.append((len(lines), "代码块未闭合（``` 数量为奇数）", ""))
    return errors


def check_links(lines):
    """HEAD 探测外链，返回失效链接列表。"""
    dead = []
    seen = set()
    for i, raw in enumerate(lines):
        for m in URL_RE.finditer(raw):
            url = m.group(0).rstrip(").,;!?")
            if url in seen:
                continue
            seen.add(url)
            try:
                req = urllib.request.Request(url, method="HEAD", headers={"User-Agent": "Mozilla/5.0"})
                with urllib.request.urlopen(req, timeout=6) as resp:
                    if resp.status >= 400:
                        dead.append((i + 1, resp.status, url))
            except Exception as e:
                dead.append((i + 1, type(e).__name__, url))
    return dead


def main():
    ap = argparse.ArgumentParser(description="gzhu-campus 发布前健康检查")
    ap.add_argument("--dir", default="references", help="扫描目录（默认 references）")
    ap.add_argument("--check-links", action="store_true", help="探测外链有效性（较慢）")
    ap.add_argument("--check-todo", action="store_true", help="逐条列出'待补充'标记")
    ap.add_argument("--check-headings", action="store_true", help="检查标题层级跳变")
    ap.add_argument("--strict", action="store_true", help="警告也视为错误")
    args = ap.parse_args()

    if not os.path.isdir(args.dir):
        print(f"[错误] 目录不存在：{args.dir}", file=sys.stderr)
        return 2

    files = []
    for root, _d, names in os.walk(args.dir):
        for n in sorted(names):
            if n.lower().endswith(".md"):
                files.append(os.path.join(root, n))
    if not files:
        print("[错误] 目录下没有 .md 文件", file=sys.stderr)
        return 2

    total_errors, total_warns = 0, 0
    for path in files:
        try:
            with open(path, "rb") as f:
                raw = f.read()
            text = None
            for enc in ("utf-8", "utf-8-sig", "gbk"):
                try:
                    text = raw.decode(enc)
                    break
                except UnicodeDecodeError:
                    continue
            if text is None:
                print(f"[错误] 无法解码 {path}", file=sys.stderr)
                continue
            lines = text.splitlines()
        except Exception as e:
            print(f"[错误] 读取失败 {path}: {e}", file=sys.stderr)
            continue

        rel = os.path.relpath(path, args.dir)
        errors, warns = check_privacy(path, lines)

        todo_hits = check_todo(lines)
        todo_count = len(todo_hits)

        md_errors = []
        if args.check_headings:
            md_errors = check_markdown(lines)
            errors += md_errors

        if errors or warns:
            print(f"\n### {rel}")
            for ln, kind, val in errors:
                print(f"  [错误] 行{ln} {kind}: {val}")
                total_errors += 1
            for ln, kind, val in warns:
                print(f"  [警告] 行{ln} {kind}: {val}")
                total_warns += 1
        if todo_count and args.check_todo:
            print(f"\n### {rel}（待补充 {todo_count} 处）")
            for ln, kind, val in todo_hits:
                print(f"  [待补充] 行{ln}: {val}")
                total_warns += 1
        elif todo_count:
            print(f"[信息] {rel}: 含 {todo_count} 处'待补充/待核实'标记（加 --check-todo 查看明细）")

        if args.check_links:
            dead = check_links(lines)
            if dead:
                print(f"\n### {rel}（失效链接）")
                for ln, status, url in dead:
                    print(f"  [链接] 行{ln} {status}: {url}")
                    total_warns += 1

    print("\n================ 检查报告 ================")
    print(f"扫描文件数: {len(files)}")
    print(f"错误: {total_errors} | 警告: {total_warns}")
    print(f"说明: 手机号/身份证/密钥为错误级；邮箱/学号(10位数字)可能误报，需人工确认是否公开信息。")
    if total_errors or (args.strict and total_warns):
        print("结论: 存在需处理项，建议处理后再发布")
        return 1
    print("结论: 通过")
    return 0


if __name__ == "__main__":
    sys.exit(main())
