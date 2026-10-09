#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
gzhu-campus 成绩计算器（零依赖，标准库）

按《广州大学普通本科生成绩管理规定》第四条计算：
  - 百分制：60≤成绩<90 绩点 = (成绩-60)/10+1（保留 1 位小数），≥90 为 4.0，<60 为 0
  - 十一级制：A 4.0 / A- 3.7 / B+ 3.5 / B 3.2 / B- 2.8 / C+ 2.5 / C 2.1 / C- 1.8 / D 1.5 / D- 1.0 / F 0
  - 五级制：优 4.0 / 良 3.5 / 中 2.5 / 及格 1.5 / 不及格 0
  - 平均学分绩点 GPA = Σ(课程绩点×课程学分) / Σ课程学分
  - 加权平均成绩 = Σ(百分制成绩×学分) / Σ百分制课程学分（等级制课程不参与加权成绩）

用法（交互）:
  python gpa.py
  依次输入: 课程名 学分 成绩（支持百分制数字 / 十一级制 A- / 五级制 优），空行结束

用法（文件，每行一条）:
  python gpa.py --file grades.txt
  grades.txt 示例:
    高等数学 4 88
    大学英语 2 A-
    体育 1 良

用法（命令行直接给）:
  python gpa.py "高数 4 88" "思修 3 B+"

退出码:
  0  正常
  2  输入有误
"""

import argparse
import math
import sys

# ---- 等级制绩点表 ----
GRADE_POINTS = {
    # 十一级制
    "A": 4.0, "A-": 3.7, "B+": 3.5, "B": 3.2, "B-": 2.8,
    "C+": 2.5, "C": 2.1, "C-": 1.8, "D": 1.5, "D-": 1.0, "F": 0.0,
    # 五级制
    "优": 4.0, "良": 3.5, "中": 2.5, "及格": 1.5, "不及格": 0.0,
}


def parse_score(raw):
    """把成绩文本解析为 (类型, 绩点, 百分制成绩或None)。"""
    s = raw.strip()
    if not s:
        return None
    up = s.upper()
    if up in GRADE_POINTS:
        return ("等级", GRADE_POINTS[up], None)
    try:
        v = float(s)
    except ValueError:
        return None
    if v < 0 or v > 100:
        return None
    if v < 60:
        return ("百分", 0.0, v)
    if v >= 90:
        return ("百分", 4.0, v)
    # (成绩-60)/10+1，保留 1 位小数（四舍五入）
    gp = round((v - 60) / 10 + 1, 1)
    return ("百分", gp, v)


def parse_line(text):
    """解析一行: 课程名 学分 成绩。返回 (课程, 学分, 类型, 绩点, 百分制成绩)。"""
    parts = text.split()
    if len(parts) < 3:
        return None
    course = " ".join(parts[:-2])
    try:
        credit = float(parts[-2])
    except ValueError:
        return None
    if credit <= 0:
        return None
    parsed = parse_score(parts[-1])
    if parsed is None:
        return None
    typ, gp, score = parsed
    return (course, credit, typ, gp, score)


def compute(records):
    """records: [(课程, 学分, 类型, 绩点, 百分制成绩)] → 统计 dict。"""
    total_credit = sum(r[1] for r in records)
    gp_sum = sum(r[1] * r[3] for r in records)
    gpa = gp_sum / total_credit if total_credit else 0.0
    # 加权平均成绩：仅百分制课程
    pct = [r for r in records if r[2] == "百分"]
    pct_credit = sum(r[1] for r in pct)
    weighted = sum(r[1] * r[4] for r in pct) / pct_credit if pct_credit else None
    # 绩点分布
    dist = {}
    for r in records:
        dist[r[3]] = dist.get(r[3], 0) + 1
    return {
        "total_credit": total_credit,
        "gpa": gpa,
        "weighted": weighted,
        "pct_credit": pct_credit,
        "dist": dist,
    }


def main():
    ap = argparse.ArgumentParser(description="gzhu-campus 成绩计算器（广大成绩管理规定第四条）")
    ap.add_argument("entries", nargs="*", help='直接给条目，如 "高数 4 88"；不给则进入交互/文件模式')
    ap.add_argument("--file", help="从文件读取（每行: 课程名 学分 成绩）")
    args = ap.parse_args()

    records = []

    if args.file:
        try:
            with open(args.file, encoding="utf-8") as f:
                lines = [l for l in f if l.strip()]
        except Exception as e:
            print(f"[错误] 无法读取文件: {e}", file=sys.stderr)
            return 2
        for l in lines:
            r = parse_line(l)
            if r is None:
                print(f"[跳过] 无法解析: {l.strip()}", file=sys.stderr)
                continue
            records.append(r)
    elif args.entries:
        for e in args.entries:
            r = parse_line(e)
            if r is None:
                print(f"[跳过] 无法解析: {e}", file=sys.stderr)
                continue
            records.append(r)
    else:
        print("输入课程（格式: 课程名 学分 成绩；空行结束）。成绩支持 88 / A- / 良 等。")
        while True:
            try:
                line = input("> ").strip()
            except (EOFError, KeyboardInterrupt):
                break
            if not line:
                break
            r = parse_line(line)
            if r is None:
                print("  [提示] 无法解析，格式: 课程名 学分 成绩")
                continue
            records.append(r)

    if not records:
        print("[错误] 没有有效输入", file=sys.stderr)
        return 2

    stats = compute(records)

    print("\n===== 成绩明细 =====")
    print(f"{'课程':<16} {'学分':>5} {'成绩':>8} {'绩点':>5}")
    for course, credit, typ, gp, score in records:
        shown = f"{score:g}" if score is not None else ("等级制" if typ == "等级" else typ)
        print(f"{course:<16} {credit:>5g} {shown:>8} {gp:>5}")
    print("-" * 40)
    print(f"总学分: {stats['total_credit']:g}")
    print(f"平均学分绩点 GPA: {stats['gpa']:.2f}")
    if stats["weighted"] is not None:
        print(f"加权平均成绩（仅百分制课程，{stats['pct_credit']:g} 学分）: {stats['weighted']:.2f}")
    else:
        print("加权平均成绩: 无百分制课程，不计算")
    if stats["dist"]:
        dist_str = ", ".join(f"{k:g} 分:{v}门" for k, v in sorted(stats["dist"].items(), reverse=True))
        print(f"绩点分布: {dist_str}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
