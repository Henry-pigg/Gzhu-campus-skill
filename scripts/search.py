#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
gzhu-campus 知识库检索器（零依赖，标准库）

在 references 大文件中按关键词定位段落，输出行号 + 上下文窗口，
供 AI 直接读取，替代手工 Grep。

用法:
  python search.py <文件或目录> <关键词...> [选项]

选项:
  --any            多个关键词任一命中即算（默认全部命中 AND）
  --context N      每个命中输出的上下文行数（默认 3）
  --max N          最多输出命中数（默认 20）
  --ignore-case    忽略大小写
  --list-files     只列出含命中的文件，不输出段落

示例:
  python search.py references/rules.md 转专业 条件
  python search.py references 食堂 营业时间 --any --context 2
  python search.py references/campus_knowledge.md 校园跑 --ignore-case

退出码:
  0  正常（可能无命中）
  2  参数或文件错误
"""

import argparse
import os
import re
import sys

# 知识库常见的几种编码，按序尝试
ENCODINGS = ("utf-8", "gbk", "utf-8-sig")


def read_lines(path):
    """按序尝试编码读取文件，返回行列表。"""
    with open(path, "rb") as f:
        raw = f.read()
    last_err = None
    for enc in ENCODINGS:
        try:
            text = raw.decode(enc)
            return text.splitlines()
        except UnicodeDecodeError as e:
            last_err = e
    raise last_err


def collect_files(target):
    """返回待检索的 .md 文件列表（文件或目录）。"""
    if os.path.isfile(target):
        return [target]
    if os.path.isdir(target):
        out = []
        for root, _dirs, names in os.walk(target):
            for n in sorted(names):
                if n.lower().endswith(".md"):
                    out.append(os.path.join(root, n))
        return sorted(out)
    return None


def build_matcher(keywords, ignore_case):
    """返回正则列表。多词短语拆成多个子模式（顺序不限）。"""
    flags = re.IGNORECASE if ignore_case else 0
    patterns = []
    for kw in keywords:
        if len(kw.split()) > 1:
            parts = [re.escape(p) for p in kw.split()]
            patterns.append(re.compile("|".join(parts), flags))
        else:
            patterns.append(re.compile(re.escape(kw), flags))
    return patterns


def match_line(line, patterns, any_mode):
    if any_mode:
        return any(p.search(line) for p in patterns)
    return all(p.search(line) for p in patterns)


def main():
    ap = argparse.ArgumentParser(description="gzhu-campus 知识库检索器")
    ap.add_argument("target", help="md 文件或目录")
    ap.add_argument("keywords", nargs="+", help="检索关键词")
    ap.add_argument("--any", action="store_true", help="任一关键词命中即算")
    ap.add_argument("--context", type=int, default=3, help="上下文行数（默认 3）")
    ap.add_argument("--max", type=int, default=20, help="最多输出命中数（默认 20）")
    ap.add_argument("--ignore-case", action="store_true", help="忽略大小写")
    ap.add_argument("--list-files", action="store_true", help="只列含命中的文件")
    args = ap.parse_args()

    files = collect_files(args.target)
    if not files:
        print(f"[错误] 找不到目标：{args.target}", file=sys.stderr)
        return 2

    patterns = build_matcher(args.keywords, args.ignore_case)
    any_mode = args.any
    ctx = max(0, args.context)
    limit = max(1, args.max)

    total_hits = 0
    total_files = 0
    printed = 0

    for path in files:
        try:
            lines = read_lines(path)
        except Exception as e:
            print(f"[跳过] 无法读取 {path}: {e}", file=sys.stderr)
            continue

        file_hits = [i for i, l in enumerate(lines) if match_line(l, patterns, any_mode)]
        if not file_hits:
            continue
        total_files += 1

        rel = os.path.relpath(path)
        if args.list_files:
            print(f"{rel}: {len(file_hits)} 处命中")
            continue

        for idx in file_hits:
            if printed >= limit:
                break
            printed += 1
            total_hits += 1
            print(f"\n==== 文件: {rel} | 命中行 {idx + 1} ====")
            start = max(0, idx - ctx)
            end = min(len(lines), idx + ctx + 1)
            for i in range(start, end):
                marker = ">>" if i == idx else "  "
                print(f"{marker} {i + 1:>6} | {lines[i]}")
        if printed >= limit:
            break

    mode = "任一" if any_mode else "全部"
    if args.list_files:
        print(f"\n共 {total_files} 个文件含命中（关键词: {' '.join(args.keywords)}，模式: {mode}）")
    else:
        if printed >= limit:
            print(f"\n[提示] 已显示前 {printed} 处，仍有更多命中，可加 --max 扩大或换更精确的关键词")
        print(f"\n共 {total_hits} 处命中 / {total_files} 个文件（关键词: {' '.join(args.keywords)}，模式: {mode}）")
    return 0


if __name__ == "__main__":
    sys.exit(main())
