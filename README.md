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
├── LICENSE                           # MIT License
├── NOTICE                            # 上游开源项目署名（MIT）
├── scripts/
│   ├── gzhu-credential.ps1           # Windows DPAPI 加密凭证存取脚本
│   ├── gzhu-credential-mac.sh        # macOS Keychain 凭证存取脚本
│   ├── gzhu-credential-linux.sh      # Linux Secret Service (libsecret) 凭证脚本
│   ├── search.py                     # 知识库检索器（多关键词 AND/OR + 上下文）
│   ├── check.py                      # 发布前健康检查（隐私/待补充/格式）
│   ├── contribute.py                 # 贡献提交器（用户补充数据 → 规范条目 → 自动发 PR）
│   ├── gpa.py                        # 成绩计算器（GPA/加权/绩点分布）
│   ├── log_update.py                 # README 更新日志自动插入
│   └── portal.py                     # 校园门户登录 CLI（可选，需 Playwright）
└── references/                       # 知识库参考文件
    ├── academics.md                  # 机电与电气工程学院培养方案（5 个专业）
    ├── calendar.md                   # 2026-2027 学年校历
    ├── campus_knowledge.md           # 生活服务 / 地图交通 / 服务入口 / 学生经验
    ├── leave.md                      # 请假与假期离校报备流程
    ├── portal-login.md               # 数字广大/教务系统自动登录操作手册
    ├── retrieval.md                  # 检索契约：A/B/C 证据分层、引用格式、隐私掩码
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

## 校园门户自动登录（可选）

需要查个人课表、成绩、GPA、办事进度等校内数据时，本 skill 支持把学号密码加密后存在本地，由 AI 通过浏览器自动化（Playwright / Browser Use）登录数字广大（`my.gzhu.edu.cn`）或教务系统（`jwxt.gzhu.edu.cn`）查询。

- **Windows**：用 `scripts/gzhu-credential.ps1`，凭证经 Windows DPAPI 加密存于 `%USERPROFILE%\.gzhu-campus\credentials.enc`。
- **macOS**：用 `scripts/gzhu-credential-mac.sh`，凭证存于 macOS Keychain（钥匙串），服务名 `gzhu-campus`。
- **Linux**：用 `scripts/gzhu-credential-linux.sh`，凭证存于 Secret Service（GNOME Keyring / KWallet），依赖 `secret-tool`（libsecret）。
- 加密存储**不在本仓库目录内**，永远不会被 git 提交或推送到 GitHub；每个用户在自己机器上存自己的凭证，互不相干。
- 安全边界：只查不提交（选课/改密/报名等不可逆操作必须交还给用户）；遇到验证码/二次验证立即交还。
- 详见 `references/portal-login.md`。

## MCP 可选依赖（Playwright / Parallel Search）

本 skill 纯 Markdown 即可运行，但以下场景建议配两个 MCP（很多人没装）：

- **Playwright MCP**（微软官方 `@playwright/mcp`）：校园门户自动登录、真实网页核验需要浏览器自动化
- **Parallel Search MCP**（Parallel AI 官方，免费免 key）：回答校园最新动态需要联网搜索

安装配置（Claude Desktop / Claude Code / Codex / Cursor 等各客户端）见 **[`MCP-SETUP.md`](MCP-SETUP.md)**，仓库根 `mcp.example.json` 可直接复制使用。

## 内置 Python 工具（可选）

`scripts/` 下 6 个工具，**全部零第三方依赖、跨平台**（需 Python 3），各工具 `python scripts/<工具>.py --help` 查看参数：

| 工具 | 用途 |
|---|---|
| `search.py` | 知识库检索器：多关键词 AND/OR，输出命中行号 + 上下文窗口 |
| `check.py` | 发布前健康检查：隐私泄露（手机号/身份证/学号/密钥）、待补充残留、md 结构 |
| `contribute.py` | 贡献提交器：把用户补充整理为规范条目并发起 PR（内置隐私门禁；只发 PR 不推 main，无推送权限时自动 fork） |
| `gpa.py` | 成绩计算器：按《成绩管理规定》第四条算 GPA / 加权成绩 / 绩点分布 |
| `log_update.py` | 更新日志辅助：自动在 README 更新日志顶部插入"日期+一句话" |
| `portal.py` | 校园门户登录 CLI（**可选**，需 `pip install playwright`）：自动登录 CAS 查课表/成绩 |

## 贡献数据（用户补充闭环）

知识库未收录某主题、或信息标注"待补充"时，懂行的用户可以直接补充数据，由工具整理成规范条目、自动提交 PR：

1. 向助手提供三要素：**主题**（一句话标题）、**内容**（具体信息）、**来源**（平台+标题/URL+年份；亲身经历写"用户自述（亲身经历，日期）"）。
2. 助手调 `python scripts/contribute.py --json '<字段>'`（或交互式运行）；条目样式、目标文件、小节自动路由，也可显式指定。
3. 提交前自动过隐私门禁（手机号/学号/身份证/邮箱/疑似密钥命中即终止），非官方来源一律标 B 层（学生经验）。
4. 工具新建 `contribute/<文件>-<时间戳>` 分支并发起 PR——**绝不直接推 main**；无推送权限时自动 fork 后从 fork 发 PR。
5. 维护者按 PR 内清单复核合并；合并后跑 `scripts/check.py --dir references` 复查即可。

准入规则详见 `references/retrieval.md`「贡献准入规则」。

## 数据库更新日志

> 每次更新 references 数据库后在此记录最新日期（最新在上）。

- **2026-10-17**：新增 `scripts/contribute.py` 贡献闭环——用户补充数据 → 规范条目 → 自动发 PR（内置隐私门禁、只发 PR 不推 main、无权限自动 fork）；SKILL.md 回答流程增加第 8 步"空结果/时效不足时邀请补充"，retrieval.md 增加「贡献准入规则」；修复 portal.py 凭证读取集成（三平台 `get` 动作 + JSON 解析，替换原失效的 `-Read` 调用）；search.py Windows 路径显示修复；rules.md / campus_knowledge.md 共 15 处行级个人手机号脱敏（保留办公固话，check.py 门禁恢复通过）；新增 LICENSE（MIT）+ NOTICE（上游项目署名）
- **2026-10-09**：新增 5 个 Python 工具脚本（search 检索 / check 隐私检查 / gpa 计算器 / log_update 日志 / portal 门户 CLI）
- **2026-10-07**：选课数据库（course_eval.md + course_selection.md）+ MCP 配置文档（MCP-SETUP.md + mcp.example.json）
- **2026-10-06**：三平台加密凭证脚本 + retrieval.md + official-docs 13 篇官方制度 + 26 学院专业索引
- **2026-10-05**：小红书/贴吧/B站/抖音多平台补采 + 饭堂小摊实测 + 微信文章
- **2026-10-02**：初始仓库上传（SKILL.md + references 5 个 md + 安装命令）
> 本仓库内容为个人整理的校园知识库，仅供参考，最终以广州大学官方通知为准。
>
> 本仓库以 [MIT License](LICENSE) 发布；包含衍生自上游开源项目的内容，署名见 [NOTICE](NOTICE)。
