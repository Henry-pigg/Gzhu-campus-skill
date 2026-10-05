# GZHU Campus 广州大学校园助手 Skill

面向广州大学在校生（主校区：大学城校区）的校园知识问答 AI Skill。回答广州大学校园生活、制度、学业、交通、办事流程等任何问题时使用本 Skill。

## 能力范围

- **生活服务**：食堂 / 宿舍 / 图书馆 / 校医院 / 校园网 / 快递 / 运动场 / 校园跑
- **交通信息**：校区地图 / 地铁 / 公交 / 校车
- **线上服务入口**：数字广大 / 企业微信 / 教务系统
- **制度规则**：注册 / 学籍 / 转专业 / 绩点 GPA / 学位授予 / 第二课堂 / 奖助学金 / 违纪处分 / 申诉
- **学业培养**：机电与电气工程学院各专业培养方案、课程学分
- **校历安排**：学期周次、报到注册、考试周、寒暑假
- **办事流程**：请假与离校报备
- **学生经验**：食堂推荐 / 选课技巧 / 宿舍实况

## 仓库结构

```
Gzhu-campus-skill/
├── SKILL.md                          # Skill 主文件：回答流程、领域导航、时效警示
└── references/                       # 知识库参考文件
    ├── academics.md                  # 机电与电气工程学院培养方案（5 个专业）
    ├── calendar.md                   # 2026-2027 学年校历
    ├── campus_knowledge.md           # 生活服务 / 地图交通 / 服务入口 / 学生经验
    ├── leave.md                      # 请假与假期离校报备流程
    └── rules.md                      # 学生手册 37 项制度全文
```

## 在 AI 编码工具中安装

本 Skill 遵循 [Agent Skills](https://agentskills.io) 开放标准，适用于 OpenCode、Claude Code、Codex、Cursor 等 40+ AI 工具。安装时目标文件夹名请使用 `gzhu-campus`（与 `SKILL.md` 中的 `name` 保持一致）。

### 方式一：一条命令装到所有工具（推荐）

需要 Node.js。CLI 会自动检测已安装的 AI 工具并一次性装好：

```bash
npx skills add https://github.com/Henry-pigg/Gzhu-campus-skill
```

### 方式二：手动安装到单个工具

**OpenCode**（全局，所有项目可用）

```bash
git clone https://github.com/Henry-pigg/Gzhu-campus-skill ~/.config/opencode/skills/gzhu-campus
```

项目级：`.opencode/skills/gzhu-campus`。OpenCode 也兼容读取 `.claude/skills` 目录。

**Claude Code**（个人级，所有项目可用）

```bash
git clone https://github.com/Henry-pigg/Gzhu-campus-skill ~/.claude/skills/gzhu-campus
```

项目级：`.claude/skills/gzhu-campus`，提交到仓库即可团队共享。

**Codex**（用户级）

```bash
git clone https://github.com/Henry-pigg/Gzhu-campus-skill ~/.codex/skills/gzhu-campus
```

装完后重启 Codex 生效（也可以在 Codex 中用内置的 `$skill-installer` 从该仓库安装）。

安装后直接在工具中提问广州大学相关问题即可自动触发；Claude Code 中也可用 `/gzhu-campus` 手动调用。

## 使用方式

作为 AI Agent Skill 使用时，回答流程：

1. **定位领域**：判断问题属于哪个板块，按导航读取对应 references 文件。
2. **检索答案**：大文件（rules.md、campus_knowledge.md）按关键词定位相关段落。
3. **标注信息性质**：如实传递信息标签——官方已查证 / 地图数据 / 学生经验（一方说法，需交叉验证）/ 待补充。
4. **主动提示时效**：涉及交通线路、营业时间、制度细则时提醒"以官方最新通知为准"。

## 已知时效警示

- **官洲隧道施工**（2026-06-19 起）：大学城 1/3/4 线、B25、夜48 临时取消行经大学城。
- 学生经验帖以 2025-2026 年为主，2021 年及更早旧帖谨慎采用。
- 校巴时刻表、场地收费、校园跑次数/里程等标注"待补充"的项，以现场公告为准。

> 本仓库内容为个人整理的校园知识库，仅供参考，最终以广州大学官方通知为准。
