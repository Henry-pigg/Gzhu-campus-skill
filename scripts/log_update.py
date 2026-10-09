#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
gzhu-campus 更新日志辅助（零依赖，标准库）

在 README「数据库更新日志」小节顶部自动插入一条：
  - **YYYY-MM-DD**：<一句话描述>
满足"每次更新数据库后记录最新日期（最新在上）"的维护约定。

用法:
  python log_update.py "选课数据库更新：新增 course_eval.md"
  python log_update.py "多平台补采" --date 2026-10-09
  python log_update.py "修正宿舍信息" --readme ../Gzhu-campus-skill/README.md

选项:
  --date YYYY-MM-DD   指定日志日期（默认今天）
  --readme PATH       README 路径（默认当前目录 README.md）
  --force             同日已有条目时覆盖该行内容（默认只提示不修改）

退出码:
  0  成功（或同日已有且未 --force）
  1  README 未找到或缺少「数据库更新日志」小节
  2  用法错误
"""

import argparse
import datetime
import os
import re
import sys

SECTION_RE = re.compile(r"^##\s*数据库更新日志\s*$", re.MULTILINE)
ENTRY_RE = re.compile(r"^- \*\*(\d{4}-\d{2}-\d{2})\*\*：?(.*)$")


def find_insert_position(lines, section_idx):
    """返回新条目插入的行号（section 标题后第一个条目之前，或注释块之后）。"""
    i = section_idx + 1
    # 跳过标题后的引用块/空行
    while i < len(lines) and (not lines[i].strip() or lines[i].strip().startswith(">")):
        i += 1
    # 若下一行就是条目，插在其前；否则插在内容区起点
    return i


def main():
    ap = argparse.ArgumentParser(description="gzhu-campus 更新日志辅助")
    ap.add_argument("message", help="一句话描述本次更新")
    ap.add_argument("--date", help="日志日期 YYYY-MM-DD（默认今天）")
    ap.add_argument("--readme", default="README.md", help="README 路径")
    ap.add_argument("--force", action="store_true", help="同日已有条目时覆盖")
    args = ap.parse_args()

    if not args.message.strip():
        print("[错误] 描述不能为空", file=sys.stderr)
        return 2

    if args.date:
        try:
            datetime.date.fromisoformat(args.date)
        except ValueError:
            print(f"[错误] 日期格式应为 YYYY-MM-DD: {args.date}", file=sys.stderr)
            return 2
        today = args.date
    else:
        today = datetime.date.today().isoformat()

    if not os.path.isfile(args.readme):
        print(f"[错误] README 不存在: {args.readme}", file=sys.stderr)
        return 1

    with open(args.readme, encoding="utf-8") as f:
        text = f.read()
    lines = text.splitlines()

    m = SECTION_RE.search(text)
    if not m:
        print("[错误] README 中未找到「## 数据库更新日志」小节", file=sys.stderr)
        return 1
    section_line = text[: m.start()].count("\n")

    # 检查同日条目
    for i, l in enumerate(lines):
        em = ENTRY_RE.match(l)
        if em and em.group(1) == today:
            if not args.force:
                print(f"[提示] 已存在 {today} 的条目，未修改（加 --force 覆盖）")
                return 0
            lines[i] = f"- **{today}**：{args.message.strip()}"
            with open(args.readme, "w", encoding="utf-8") as f:
                f.write("\n".join(lines) + "\n")
            print(f"[更新] 覆盖了 {today} 的条目")
            return 0

    pos = find_insert_position(lines, section_line)
    new_entry = f"- **{today}**：{args.message.strip()}"
    lines.insert(pos, new_entry)
    with open(args.readme, "w", encoding="utf-8") as f:
        f.write("\n".join(lines) + "\n")
    print(f"[成功] 已在「数据库更新日志」顶部插入：{new_entry}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
