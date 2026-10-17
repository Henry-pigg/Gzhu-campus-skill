#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
gzhu-campus 贡献提交器（零依赖：标准库 + gh CLI）

适用场景：用户提问在知识库中检索不到、或信息时效性不足时，邀请用户补充数据；
本工具把贡献整理成符合本库规范的条目，经 GitHub API 建分支、提交并发起 PR
（**绝不直接推送 main**，PR 由维护者复核后合并）。

安全边界:
  - 只发 PR，不推 main；无推送权限时自动 fork 后从 fork 发 PR
  - 提交前跑 check.py 同款隐私扫描，命中手机号/身份证/疑似密钥即终止
  - 来源非官方域名的条目一律标 B 层（学生经验），不允许冒充官方

用法:
  # 交互式（推荐）
  python scripts/contribute.py

  # JSON 输入（AI 整理好字段后调用）
  python scripts/contribute.py --json '{"topic":"...","content":"...","source":"..."}'
  python scripts/contribute.py --json @entry.json
  cat entry.json | python scripts/contribute.py --json -

  # 只预览不提交（可用本地文件代替远程 main 内容）
  python scripts/contribute.py --json '...' --dry-run
  python scripts/contribute.py --json '...' --dry-run --local-file references/campus_knowledge.md

选项:
  --repo owner/name   目标仓库（默认 Henry-pigg/Gzhu-campus-skill）
  --ref REF           基线分支（默认 main）
  --json TEXT         贡献内容 JSON（字符串 / @文件 / - 表示 stdin）
  --dry-run           只本地预览生成的条目与插入位置，不发起 PR
  --local-file PATH   配合 --dry-run：用本地文件代替远程内容做预览
  --yes               跳过交互确认

字段说明（JSON）:
  topic        条目标题（必填）
  content      条目正文（必填；课程评价表风格可不填，改用课程字段）
  source       来源描述，建议带 URL 与年份（必填；亲身经历可写
               "用户自述（亲身经历，2026-10-17）"）
  layer        A=官方已查证 / B=学生经验（默认按来源自动判断；
               仅官方域名来源允许 A，否则自动降级为 B 并警告）
  target_file  campus_knowledge.md（默认）/ course_eval.md / rules.md / calendar.md ...
  section      目标小节标题（如 "## 4. 校医院"、"### 体育类"）；
               缺省按关键词自动路由
  author       贡献者署名（默认 "<某同学>"；严禁真实姓名/学号）
  table 风格字段（target_file=course_eval.md 时使用，可缺省填 "—"）:
    course 课程 / teacher 老师 / attendance 考勤 /
    assessment 考核方式 / reputation 给分口碑

退出码:
  0  成功（或 dry-run 完成 / 用户取消）
  2  用法/字段校验错误
  3  隐私扫描拦截
  4  gh CLI / 网络 / GitHub API 错误
"""

import argparse
import base64
import datetime
import json
import os
import re
import subprocess
import sys
import time
import urllib.error
import urllib.request

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)

from check import check_privacy  # noqa: E402  复用发布前隐私扫描（与 check.py 同一套正则）

DEFAULT_REPO = "Henry-pigg/Gzhu-campus-skill"
DEFAULT_BRANCH = "main"
OFFICIAL_HOSTS = ("gzhu.edu.cn",)  # 只有来源落在这些域内才允许标 A 层
TODAY = datetime.date.today().isoformat()

EXIT_OK, EXIT_USAGE, EXIT_PRIVACY, EXIT_API = 0, 2, 3, 4


def die(code, msg):
    print(f"[错误] {msg}", file=sys.stderr)
    sys.exit(code)


def bye(msg="已取消，未做任何更改。"):
    print(msg)
    sys.exit(EXIT_OK)


def warn(msg):
    print(f"[提示] {msg}")


def info(msg):
    print(f"[信息] {msg}")


def run(cmd, timeout=60):
    return subprocess.run(cmd, capture_output=True, text=True, timeout=timeout)


# ---------------------------------------------------------------- GitHub API

class ApiError(Exception):
    pass


def gh_token():
    """优先取 gh CLI 的 token，其次 GITHUB_TOKEN 环境变量。"""
    env = os.environ.get("GITHUB_TOKEN", "").strip()
    if env:
        return env
    try:
        out = run(["gh", "auth", "token"])
    except FileNotFoundError:
        die(EXIT_API, "未找到 gh CLI（https://cli.github.com），也未设置 GITHUB_TOKEN。"
                      "请先安装 gh 并执行 gh auth login。")
    except Exception as e:
        die(EXIT_API, f"调用 gh 失败：{e}")
    if out.returncode != 0 or not out.stdout.strip():
        die(EXIT_API, "gh 未登录或无 token。请先执行 gh auth login，或设置 GITHUB_TOKEN。")
    return out.stdout.strip()


def api(token, method, path, payload=None):
    url = path if path.startswith("http") else "https://api.github.com" + path
    data = json.dumps(payload).encode("utf-8") if payload is not None else None
    req = urllib.request.Request(url, data=data, method=method)
    req.add_header("Authorization", "Bearer " + token)
    req.add_header("Accept", "application/vnd.github+json")
    req.add_header("X-GitHub-Api-Version", "2022-11-28")
    if data:
        req.add_header("Content-Type", "application/json")
    try:
        with urllib.request.urlopen(req, timeout=30) as resp:
            raw = resp.read().decode("utf-8")
            return json.loads(raw) if raw.strip() else {}
    except urllib.error.HTTPError as e:
        detail = ""
        try:
            detail = json.loads(e.read().decode("utf-8")).get("message", "")
        except Exception:
            pass
        raise ApiError(f"{method} {url.split('api.github.com')[-1]} -> HTTP {e.code} {detail}".strip())
    except urllib.error.URLError as e:
        raise ApiError(f"{method} {url.split('api.github.com')[-1]} 网络错误：{e}")


def get_remote_file(token, full_repo, path, ref):
    data = api(token, "GET", f"/repos/{full_repo}/contents/{path}?ref={ref}")
    return base64.b64decode(data["content"]).decode("utf-8")


# ---------------------------------------------------------------- 条目构建

def multiline_field(text, label):
    """把可能多行的文本挂到 '- **label**：' 下，续行缩进 2 空格保持列表结构。"""
    lines = str(text).strip().split("\n")
    out = [f"- **{label}**：" + lines[0]]
    out += ["  " + l if l.strip() else "" for l in lines[1:]]
    return "\n".join(out)


def table_cell(text):
    return str(text or "—").replace("\n", " ").replace("|", "/").strip() or "—"


def build_field_entry(d, layer, experience_style):
    topic = d["topic"].strip()
    source = d["source"].strip()
    author = d.get("author", "").strip() or "<某同学>"
    lines = [f"#### {'主题：' if experience_style else ''}{topic}"]
    if experience_style:
        lines.append(multiline_field(d["content"], "经验内容"))
        lines.append(multiline_field(source, "来源"))
        lines.append(f"- **发布者身份**：{author}（用户补充）")
        lines.append("- **性质**：学生经验（一方说法，需交叉验证）")
    else:
        lines.append(multiline_field(d["content"], "内容"))
        lines.append(multiline_field(source, "来源"))
        lines.append(f"- **更新时间**：{TODAY}")
        if layer == "A":
            lines.append("- **性质**：官方已查证（用户补充，待维护者复核）")
        else:
            lines.append("- **性质**：学生经验（一方说法，需交叉验证）")
    lines.append(f"- **贡献记录**：{TODAY} 用户补充，经 contribute.py 提交 PR 待复核")
    return "\n".join(lines)


def build_table_row(d):
    cells = [
        table_cell(d.get("course") or d["topic"]),
        table_cell(d.get("teacher")),
        table_cell(d.get("attendance")),
        table_cell(d.get("assessment")),
        table_cell(d.get("reputation") or d.get("content")),
    ]
    return "| " + " | ".join(cells) + " |"


# ---------------------------------------------------------------- 小节路由

COURSE_CATEGORIES = [
    (("思政", "毛概", "马原", "思修", "习思", "近代史", "形势与政策"), "### 思政理论类（毛概 / 习思 / 马原 / 思修 / 近代史）"),
    (("体育", "乒乓球", "排球", "篮球", "足球", "羽毛球", "网球", "武术", "散打", "轮滑", "舞蹈", "形体"), "### 体育类"),
    (("英语", "学术英语", "小语种", "日语", "法语", "德语", "西班牙语"), "### 英语类（通用英语 / 通用学术英语 / 小语种）"),
    (("艺术", "音乐", "美术", "鉴赏", "影视", "书法", "摄影"), "### 艺术与鉴赏类"),
    (("科技", "编程", "计算机", "python", "心理", "健康", "军事"), "### 科技与实用技能类"),
    (("创业", "经济", "管理", "商业", "金融", "职场"), "### 创业与经济类"),
]

OFFICIAL_SECTIONS = [
    (("食堂", "饭堂", "美食"), "## 1. 食堂"),
    (("图书馆", "自习", "借阅", "占座"), "## 2. 图书馆"),
    (("宿舍", "热水", "门禁", "报修", "水电"), "## 3. 宿舍"),
    (("校医院", "门诊", "医保", "看病", "急诊"), "## 4. 校医院"),
    (("校园网", "一卡通", "校园卡", "网费"), "## 5. 校园网与一卡通"),
    (("快递", "驿站", "取件"), "## 6. 快递点"),
    (("体育馆", "运动", "球场", "游泳", "健身房"), "## 7. 体育馆 / 运动场"),
    (("校园跑", "乐跑", "跑步打卡"), "## 8. 校园跑"),
    (("校车", "班车", "校巴", "接驳"), "## 4. 校车 / 班车（校区间与地铁接驳）"),
    (("地铁", "公交", "出行", "地图"), "## 3. 公交（经停校区的线路与站点）"),
    (("数字广大", "企业微信", "教务系统", "缴费", "门户", "选课系统"), "# 三、服务入口（数字广大/企业微信）"),
]

EXPERIENCE_SECTIONS = [
    (("食堂", "饭堂", "吃", "外卖"), "## 1. 食堂推荐"),
    (("选课", "老师", "课"), "## 2. 选课技巧"),
    (("宿舍", "热水", "门禁"), "## 3. 宿舍情况（梅/兰/菊/竹苑）"),
    (("军训",), "## 4. 军训经验"),
    (("考试", "绩点", "转专业", "考证", "竞赛", "学习"), "## 7. 学习与考试（考试周 / 绩点 / 转专业 / 考证 / 竞赛）"),
    (("奖学金", "助学金", "勤工助学", "重修", "学生会", "社团", "办事"), "## 8. 办事体验（奖助学金 / 勤工助学 / 重修 / 学生会社团）"),
    (("水电", "床帘", "收纳", "洗衣机", "校园网", "校园跑"), "## 9. 宿舍生活细节（水电热水 / 床帘收纳 / 洗衣机 / 校园网 / 校园跑体验）"),
]
EXPERIENCE_DEFAULT = "## 5. 校园生活实战"
COURSE_DEFAULT = "### 其他趣味通识"


def match_keywords(text, table):
    for keywords, heading in table:
        if any(k in text for k in keywords):
            return heading
    return None


def is_official_source(source):
    hosts = re.findall(r"https?://([^/\s]+)", source)
    return any(h.endswith(OFFICIAL_HOSTS) for h in hosts)


# ---------------------------------------------------------------- 条目插入

def find_heading(lines, heading):
    """定位小节标题行；支持 '## 4. 校医院' 或 '4. 校医院' 两种写法。"""
    target = heading.strip()
    bare = re.sub(r"^#+\s*", "", target)
    for i, line in enumerate(lines):
        s = line.strip()
        if s == target or (s.startswith("#") and s.lstrip("#").strip() == bare):
            return i
    for i, line in enumerate(lines):
        s = line.strip()
        if s.startswith("#") and (bare in s or s.lstrip("#").strip().startswith(bare)):
            return i
    return None


def section_end(lines, start):
    """返回小节结束位置（下一个同级或更高级标题的下标，或 EOF）。"""
    level = len(lines[start]) - len(lines[start].lstrip("#"))
    for j in range(start + 1, len(lines)):
        s = lines[j]
        if s.startswith("#") and (len(s) - len(s.lstrip("#"))) <= level:
            return j
    return len(lines)


def insert_field_entry(content, heading, entry, experience_style):
    lines = content.split("\n")
    idx = find_heading(lines, heading)
    if idx is None:
        die(EXIT_USAGE, f"找不到小节 {heading!r}（请检查 section 字段；"
                        f"可用 `grep -n '^#' references/<文件>` 查看实际标题）")
    end = section_end(lines, idx)
    while end > idx + 1 and lines[end - 1].strip() == "":
        end -= 1
    block = entry.rstrip("\n")
    if not experience_style:
        block += "\n\n---"
    new = lines[:end] + [""] + block.split("\n") + [""] + lines[end:]
    return "\n".join(new)


def insert_table_row(content, heading, row):
    lines = content.split("\n")
    idx = find_heading(lines, heading)
    if idx is None:
        die(EXIT_USAGE, f"找不到课程分类小节 {heading!r}（course_eval.md 的 ### 标题）")
    end = section_end(lines, idx)
    # 找表头分隔行（|---|---|）：整行只含 | - : 空格
    sep = None
    for j in range(idx + 1, end):
        s = lines[j].strip()
        if s.startswith("|") and set(s) <= set("|-: "):
            sep = j
            break
    if sep is None:
        die(EXIT_USAGE, f"小节 {heading!r} 下没有找到表格（|----| 分隔行）")
    n_cols = lines[sep].count("|") - 1
    if row.count("|") - 1 != n_cols:
        die(EXIT_USAGE, f"表格列数不匹配：表头 {n_cols} 列，本行 {row.count('|') - 1} 列")
    last = sep
    for j in range(sep + 1, end):
        if lines[j].lstrip().startswith("|"):
            last = j
        else:
            break
    new = lines[: last + 1] + [row] + lines[last + 1:]
    return "\n".join(new)


def is_experience_section(content, heading):
    lines = content.split("\n")
    idx = find_heading(lines, heading)
    if idx is None:
        return heading in [h for _, h in EXPERIENCE_SECTIONS] or heading == EXPERIENCE_DEFAULT
    for j in range(idx, -1, -1):
        if lines[j].startswith("# "):
            return "学生经验" in lines[j]
    return False


# ---------------------------------------------------------------- 隐私扫描

def privacy_gate(entry_text):
    errors, warns = check_privacy("<contribute>", entry_text.split("\n"))
    for ln, kind, val in errors:
        print(f"  [拦截] 第 {ln} 行 {kind}：{val}", file=sys.stderr)
    if errors:
        die(EXIT_PRIVACY,
            "条目中包含隐私信息（手机号/身份证/疑似密钥等），已终止提交。"
            "请删除敏感内容后重试；正文中如需留联系方式，请引导对方使用官方渠道。")
    for ln, kind, val in warns:
        warn(f"条目第 {ln} 行{kind}：{val}（请人工确认是否为公开信息）")


# ---------------------------------------------------------------- PR 流程

def ensure_write_access(token, owner, repo):
    """返回 (full_repo, head_prefix)。无推送权限时自动 fork。"""
    me = api(token, "GET", "/user")["login"]
    try:
        info_ = api(token, "GET", f"/repos/{owner}/{repo}")
        if (info_.get("permissions") or {}).get("push"):
            return f"{owner}/{repo}", ""
    except ApiError as e:
        die(EXIT_API, f"读取仓库信息失败：{e}")
    warn(f"当前账号 {me} 对 {owner}/{repo} 无推送权限，自动创建 fork 并从 fork 发 PR。")
    try:
        api(token, "POST", f"/repos/{owner}/{repo}/forks", {"default_branch_only": True})
    except ApiError as e:
        if "already exists" not in str(e):
            die(EXIT_API, f"创建 fork 失败：{e}")
    fork = f"{me}/{repo}"
    for _ in range(30):
        try:
            api(token, "GET", f"/repos/{fork}")
            return fork, f"{me}:"
        except ApiError:
            time.sleep(2)
    die(EXIT_API, "fork 创建超时，请稍后重试。")


def create_branch_commit(token, full_repo, path, new_content, base_branch, new_branch, message):
    ref = api(token, "GET", f"/repos/{full_repo}/git/ref/heads/{base_branch}")
    base_sha = ref["object"]["sha"]
    base_tree = api(token, "GET", f"/repos/{full_repo}/git/commits/{base_sha}")["tree"]["sha"]
    blob = api(token, "POST", f"/repos/{full_repo}/git/blobs",
               {"content": new_content, "encoding": "utf-8"})
    tree = api(token, "POST", f"/repos/{full_repo}/git/trees",
               {"base_tree": base_tree,
                "tree": [{"path": path, "mode": "100644", "type": "blob", "sha": blob["sha"]}]})
    commit = api(token, "POST", f"/repos/{full_repo}/git/commits",
                 {"message": message, "tree": tree["sha"], "parents": [base_sha]})
    try:
        api(token, "POST", f"/repos/{full_repo}/git/refs",
            {"ref": f"refs/heads/{new_branch}", "sha": commit["sha"]})
    except ApiError as e:
        if "already exists" not in str(e):
            raise
        new_branch += "-" + datetime.datetime.now().strftime("%H%M%S")
        api(token, "POST", f"/repos/{full_repo}/git/refs",
            {"ref": f"refs/heads/{new_branch}", "sha": commit["sha"]})
    return new_branch


def create_pr(token, owner, repo, head, title, body):
    return api(token, "POST", f"/repos/{owner}/{repo}/pulls",
               {"title": title, "head": head, "base": DEFAULT_BRANCH, "body": body})


# ---------------------------------------------------------------- 输入与校验

def load_json_arg(text):
    if text == "-":
        raw = sys.stdin.read()
    elif text.startswith("@"):
        p = text[1:]
        if not os.path.isfile(p):
            die(EXIT_USAGE, f"文件不存在：{p}")
        with open(p, encoding="utf-8") as f:
            raw = f.read()
    else:
        raw = text
    try:
        d = json.loads(raw)
    except ValueError as e:
        die(EXIT_USAGE, f"JSON 解析失败：{e}")
    if not isinstance(d, dict):
        die(EXIT_USAGE, "JSON 顶层必须是对象")
    return d


def ask(prompt, default="", required=False):
    suffix = f" [{default}]" if default else ""
    while True:
        try:
            v = input(f"{prompt}{suffix}: ").strip()
        except EOFError:
            print()
            bye()
        if not v:
            if default:
                return default
            if required:
                print("  （必填项）")
                continue
        return v


def ask_multiline(prompt):
    print(f"{prompt}")
    print("  （可多行输入，单独一行输入 . 结束）")
    buf = []
    while True:
        try:
            line = input()
        except EOFError:
            break
        if line.strip() == ".":
            break
        buf.append(line)
    return "\n".join(buf).strip()


def interactive():
    print("=" * 56)
    print(" 广州大学校园知识库 · 贡献提交（contribute.py）")
    print(" 知识库未收录/信息过时，欢迎补充；仅发 PR，由维护者复核")
    print("=" * 56)
    d = {}
    d["topic"] = ask("条目标题", required=True)
    d["content"] = ask_multiline("条目内容")
    d["source"] = ask("来源（平台+标题/URL+年份；亲身经历写“用户自述”）", required=True)
    layer = ask("证据层（A=官方已查证 / B=学生经验）", "B").upper()
    d["layer"] = layer if layer in ("A", "B") else "B"
    author = ask("署名（默认匿名）", "<某同学>")
    if re.fullmatch(r"[\u4e00-\u9fa5]{2,4}", author):
        warn("检测到疑似真实姓名，已按匿名处理。")
        author = "<某同学>"
    d["author"] = author
    return d


def validate(d):
    errors = []
    topic = str(d.get("topic") or "").strip()
    if not topic:
        errors.append("缺少 topic（条目标题）")
    elif len(topic) > 80:
        errors.append("topic 过长（>80 字）")
    content = str(d.get("content") or "").strip()
    table_fields = any(str(d.get(k) or "").strip()
                       for k in ("course", "teacher", "attendance", "assessment", "reputation"))
    style = "table" if (not content and table_fields) else "field"
    if style == "field" and not content:
        errors.append("缺少 content（条目内容）；课程评价请改用 course/teacher/attendance/assessment/reputation 字段")
    source = str(d.get("source") or "").strip()
    if not source:
        errors.append("缺少 source（来源；亲身经历可写“用户自述（亲身经历，日期）”）")
    if errors:
        for e in errors:
            print(f"  [校验] {e}", file=sys.stderr)
        die(EXIT_USAGE, "字段校验未通过")
    d["topic"], d["content"], d["source"] = topic, content, source
    d["_style"] = style
    return d


def resolve_layer(d):
    source = d["source"]
    official = is_official_source(source)
    layer = str(d.get("layer") or "").strip().upper()
    if layer not in ("A", "B"):
        layer = "A" if official else "B"
    if layer == "A" and not official:
        warn(f"来源不是官方域名（{' / '.join(OFFICIAL_HOSTS)}），已自动降级为 B 层（学生经验）。")
        layer = "B"
    if layer == "A" and d["_style"] == "table":
        warn("选课评价库全部为学生经验（B 层），已降级为 B。")
        layer = "B"
    d["_layer"] = layer
    return d


def route(d, content_hint=""):
    style = d["_style"]
    layer = d["_layer"]
    target = str(d.get("target_file") or "").strip()
    section = str(d.get("section") or "").strip()
    text = " ".join([d["topic"], d["content"], d.get("course") or "",
                     d.get("teacher") or "", d.get("reputation") or "", content_hint])
    if style == "table" or target == "course_eval.md":
        if style != "table":
            die(EXIT_USAGE, "course_eval.md 只接受表格风格条目，请提供 "
                            "course/teacher/attendance/assessment/reputation 字段，"
                            "或改投 campus_knowledge.md")
        if not target:
            target = "course_eval.md"
        if not section:
            section = match_keywords(text, COURSE_CATEGORIES) or COURSE_DEFAULT
        return target, section, "table"
    if not target:
        target = "campus_knowledge.md"
    if not section:
        if layer == "A":
            section = match_keywords(text, OFFICIAL_SECTIONS)
            if not section:
                die(EXIT_USAGE, "A 层条目无法自动判断小节，请用 section 字段显式指定"
                                "（如 \"## 4. 校医院\"、\"# 三、服务入口（数字广大/企业微信）\"）")
        else:
            section = match_keywords(text, EXPERIENCE_SECTIONS) or EXPERIENCE_DEFAULT
    return target, section, "field"


def repo_path(target_file):
    t = target_file.strip().lstrip("./")
    if "/" not in t:
        t = "references/" + t
    if not t.endswith(".md"):
        die(EXIT_USAGE, f"只支持提交 .md 文件（收到 {t}）")
    return t


# ---------------------------------------------------------------- 主流程

def main():
    ap = argparse.ArgumentParser(
        description="gzhu-campus 贡献提交器：把用户补充整理为规范条目并发起 PR（绝不直接推 main）")
    ap.add_argument("--repo", default=DEFAULT_REPO, help=f"目标仓库（默认 {DEFAULT_REPO}）")
    ap.add_argument("--ref", default=DEFAULT_BRANCH, help=f"基线分支（默认 {DEFAULT_BRANCH}）")
    ap.add_argument("--json", dest="json_arg", help="贡献内容 JSON（字符串 / @文件 / - 表示 stdin）")
    ap.add_argument("--dry-run", action="store_true", help="只本地预览，不发起 PR")
    ap.add_argument("--local-file", help="配合 --dry-run：用本地文件代替远程内容做预览")
    ap.add_argument("--yes", action="store_true", help="跳过交互确认")
    args = ap.parse_args()

    if args.local_file and not args.dry_run:
        die(EXIT_USAGE, "--local-file 只能配合 --dry-run 使用（避免陈旧本地内容覆盖远程）")
    if "/" not in args.repo:
        die(EXIT_USAGE, f"--repo 需为 owner/name 形式（收到 {args.repo!r}）")
    owner, repo = args.repo.split("/", 1)

    d = load_json_arg(args.json_arg) if args.json_arg else interactive()
    d = validate(d)
    d = resolve_layer(d)

    target_file, section, style = route(d)
    path = repo_path(target_file)

    # ---- 取基线内容
    token = None
    if args.local_file:
        if os.path.basename(args.local_file) != os.path.basename(path):
            die(EXIT_USAGE, f"--local-file 的文件名与路由目标 {path} 不一致；"
                            f"如需预览其他文件，请用 target_file 字段显式指定")
        if not os.path.isfile(args.local_file):
            die(EXIT_USAGE, f"本地文件不存在：{args.local_file}")
        with open(args.local_file, encoding="utf-8") as f:
            content = f.read()
        info(f"使用本地文件预览：{args.local_file}")
    else:
        token = gh_token()
        try:
            content = get_remote_file(token, args.repo, path, args.ref)
        except ApiError as e:
            die(EXIT_API, f"读取远程文件失败：{e}")
        info(f"已拉取远程 {args.repo}:{args.ref} 的 {path}")

    # ---- 生成条目并插入
    experience_style = (style == "field"
                        and is_experience_section(content, section))
    if style == "table":
        entry = build_table_row(d)
        new_content = insert_table_row(content, section, entry)
    else:
        entry = build_field_entry(d, d["_layer"], experience_style)
        new_content = insert_field_entry(content, section, entry, experience_style)

    privacy_gate(entry)

    # ---- 预览
    print()
    print("-" * 56)
    print(f"目标文件：{path}")
    print(f"目标小节：{section}")
    print(f"证据层　：{d['_layer']}（{'官方已查证' if d['_layer'] == 'A' else '学生经验，一方说法'}）")
    print(f"贡献者　：{d.get('author') or '<某同学>'}")
    print("-" * 56)
    print("将插入以下条目：")
    print()
    print(entry)
    print("-" * 56)
    if args.dry_run:
        print("[dry-run] 未发起 PR。插入位置预览（目标小节末尾附近）：")
        lines = new_content.split("\n")
        idx = find_heading(lines, section)
        end = section_end(lines, idx)
        first_entry_line = entry.split("\n")[0]
        ins = next((k for k in range(idx, end) if lines[k] == first_entry_line), None)
        n_ins = len(entry.split("\n"))
        lo = max(idx, (ins if ins is not None else end) - 12)
        for i in range(lo, min(end + 3, len(lines))):
            mark = ">>" if (ins is not None and ins <= i < ins + n_ins) else "  "
            print(f"{mark} {i + 1:4d}| {lines[i]}")
        bye("\n[dry-run] 完成，未做任何更改。")

    if not args.yes:
        if input("确认提交 PR？[y/N]: ").strip().lower() not in ("y", "yes"):
            bye()

    # ---- 建分支 + 提交 + 发 PR
    full_repo, head_prefix = ensure_write_access(token, owner, repo)
    stem = re.sub(r"[^a-z0-9]+", "-", os.path.splitext(os.path.basename(path))[0].lower()).strip("-")
    ts = datetime.datetime.now().strftime("%Y%m%d-%H%M%S")
    branch = f"contribute/{stem}-{ts}"
    message = f"contribute({stem}): {d['topic'][:40]}"
    try:
        branch = create_branch_commit(token, full_repo, path, new_content,
                                      args.ref, branch, message)
        pr = create_pr(token, owner, repo, head_prefix + branch,
                       f"contribute: {d['topic'][:50]}", build_pr_body(d, path, section))
    except ApiError as e:
        die(EXIT_API, f"GitHub API 操作失败：{e}")

    print()
    info(f"PR 已创建：{pr.get('html_url')}")
    info("条目已由隐私扫描门禁；合并前请维护者按 PR 内清单复核。")
    print()
    print("后续：维护者复核合并后，可运行 scripts/check.py --dir references 全量复查，"
          "并用 scripts/log_update.py 记录本次更新。")


def build_pr_body(d, path, section):
    layer_desc = "A（官方已查证）" if d["_layer"] == "A" else "B（学生经验，一方说法，需交叉验证）"
    return f"""## 贡献条目

- **主题**：{d['topic']}
- **目标文件**：`{path}` → `{section}`
- **来源**：{d['source']}
- **证据层**：{layer_desc}
- **贡献者**：{d.get('author') or '<某同学>'}

## 维护者复核清单

- [ ] 来源可访问，且与条目内容一致
- [ ] 与既有条目无重复；若与 A 层条目冲突，以 A 层为准并提示 B 层可能滞后
- [ ] 无隐私信息（手机号 / 学号 / 身份证 / 邮箱 / 真实姓名）
- [ ] 时效标注合理（年份、文号已带上）
- [ ] 合并后运行 `python scripts/check.py --dir references` 复查

> 本 PR 由 `scripts/contribute.py` 自动生成：用户补充数据 → 规范条目 → 新分支 → PR（不直接推 main）。
"""


if __name__ == "__main__":
    main()
