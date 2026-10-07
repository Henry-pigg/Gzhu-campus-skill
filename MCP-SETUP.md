# MCP 可选依赖：Playwright MCP + Parallel Search MCP

本 skill 是纯 Markdown 知识库，**默认不需要任何 MCP 也能回答校园问答**。但以下两个场景建议安装对应 MCP：

| MCP | 官方 | 用途 |
|---|---|---|
| **Playwright MCP** | 微软官方 `@playwright/mcp` | 浏览器自动化：校园门户自动登录（查课表/成绩，流程见 `references/portal-login.md`）、打开真实网页核验 |
| **Parallel Search MCP** | Parallel AI 官方 `search.parallel.ai/mcp` | 免费联网搜索：回答校园最新动态、近期通知等需要实时信息的问题 |

> 学号密码加密存储与此无关：凭证存在本机（Windows DPAPI / macOS Keychain / Linux Secret Service），配置 MCP 不会改变任何安全边界。

## 环境要求

- **Node.js 18+**（`npx` 依赖，从 https://nodejs.org 安装）
- 安装后重启你的 AI 客户端使 MCP 生效

---

## 一、Playwright MCP

### 1. Claude Desktop

编辑配置文件（macOS：`~/Library/Application Support/Claude/claude_desktop_config.json`；Windows：`%APPDATA%\Claude\claude_desktop_config.json`）：

```json
{
  "mcpServers": {
    "playwright": {
      "command": "npx",
      "args": ["@playwright/mcp@latest"]
    }
  }
}
```

### 2. Claude Code（命令行）

```bash
claude mcp add playwright npx @playwright/mcp@latest
```

### 3. Codex CLI

```bash
codex mcp add playwright npx @playwright/mcp@latest
```

### 4. Cursor / VS Code 等支持 `.mcp.json` 的工具

项目根目录（或用户级配置）创建 `.mcp.json`（内容见仓库根 `mcp.example.json`，可直接复制）。

### 5. 首次运行需要浏览器内核

```bash
npx playwright install chromium
```

### 验证

让 AI 执行："用 Playwright 打开 https://example.com 并截图"。

### Windows 常见问题

若报错 `Unable to find executable: npx`，把 `command` 改为：

```json
{ "command": "npx.cmd", "args": ["@playwright/mcp@latest"] }
```

---

## 二、Parallel Search MCP

官方文档：https://docs.parallel.ai/integrations/mcp/search-mcp

- **Server URL**：`https://search.parallel.ai/mcp`（Streamable HTTP 传输）
- **免费**：默认匿名使用，**不需要 API key**
- 想获得更高调用限额：到 https://platform.parallel.ai 注册，把 key 设为环境变量 `PARALLEL_API_KEY`（或按下方"带 key"方式传入）
- OAuth 端点（可选）：`https://search.parallel.ai/mcp-oauth`

### 1. Claude Desktop

```json
{
  "mcpServers": {
    "parallel-search": {
      "url": "https://search.parallel.ai/mcp"
    }
  }
}
```

### 2. Claude Code

```bash
claude mcp add parallel-search --url https://search.parallel.ai/mcp
```

带 API key：

```bash
# 先设置环境变量
export PARALLEL_API_KEY=your_key_here
claude mcp add parallel-search --url https://search.parallel.ai/mcp --bearer-token-env-var PARALLEL_API_KEY
```

### 3. Codex CLI

```bash
codex mcp add parallel-search --url https://search.parallel.ai/mcp
```

带 API key：

```bash
codex mcp add parallel-search --url https://search.parallel.ai/mcp --bearer-token-env-var PARALLEL_API_KEY
```

### 4. Cursor / VS Code 等支持 `.mcp.json` 的工具

```json
{
  "mcpServers": {
    "parallel-search": {
      "url": "https://search.parallel.ai/mcp"
    }
  }
}
```

### 验证

让 AI 搜索一个时效性问题（如"广州大学最近有什么通知"），确认能返回带来源的联网结果。

---

## 三、一键复制示例配置

仓库根目录的 [`mcp.example.json`](mcp.example.json) 同时包含两个 MCP，复制到你客户端的 MCP 配置文件即可：

```json
{
  "mcpServers": {
    "playwright": {
      "command": "npx",
      "args": ["@playwright/mcp@latest"]
    },
    "parallel-search": {
      "url": "https://search.parallel.ai/mcp"
    }
  }
}
```

## 四、故障排查

| 现象 | 解决 |
|---|---|
| `npx: command not found` | 安装 Node.js 后重启终端/客户端 |
| `Unable to find executable: npx`（Windows） | 改用 `npx.cmd` 或 `cmd /c npx` |
| MCP 添加后没生效 | 完全退出并重启客户端 |
| Playwright 打开页面报错缺浏览器 | 运行 `npx playwright install chromium` |
| Parallel Search 返回限流 | 免费额度用尽，注册 platform.parallel.ai 设 `PARALLEL_API_KEY` |

---

*文档更新：2026-10-07。配置以各 MCP 官方文档为准。*
