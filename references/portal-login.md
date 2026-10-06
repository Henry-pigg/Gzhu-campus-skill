# 校园门户自动登录（数字广大 / 教务系统）

本文件说明如何使用本地加密保存的学号密码，通过浏览器自动化（Playwright / Browser Use / bu plane）登录广州大学校内系统，查询个人信息（课表、成绩、GPA、选课、奖助学金、办事进度等）。

## 安全边界（必须遵守）

1. **凭证绝不进 git**：加密文件路径为 `%USERPROFILE%\.gzhu-campus\credentials.enc`，在本 skill 仓库目录之外，**禁止**把它复制进仓库、推送到 GitHub、或写进任何 references 文件。
2. **DPAPI 加密**：凭证用 Windows DPAPI（CurrentUser scope）加密。只有当前 Windows 用户、当前机器能解密；其他用户/其他机器/其他进程身份都无法读出明文密码。加密时还额外设置了文件 ACL（仅当前用户 + SYSTEM 可读）。
3. **不在日志里回显密码**：`set` 命令执行后不要在最终回复里重复密码；`get` 拿到的 JSON 只用于浏览器自动填表，不要打印到用户可见输出里。
4. **只登录、不替用户做敏感操作**：可以查询（课表/成绩/通知/办事进度），但**不要**替用户提交选课、改密、删除申请、转账、确认报名等不可逆或有后果的操作；遇到提交按钮必须停下让用户确认。
5. **用完即走**：浏览器登录后完成查询即可，不要长期挂着已登录会话；不要保存网站 cookie 到 skill 目录。
6. **用户可随时清除**：`gzhu-credential.ps1 remove` 一键删除本地凭证。

## 凭证存储与读取脚本

脚本位置：本 skill 目录下 `scripts/gzhu-credential.ps1`（PowerShell 5.1+，Windows）。

```powershell
# 保存（用户首次提供学号密码时由 AI 调用）
powershell -NoProfile -ExecutionPolicy Bypass -File scripts\gzhu-credential.ps1 set -StudentId "<学号>" -Password "<密码>"

# 读取（登录前由 AI 调用，输出一行 JSON）
powershell -NoProfile -ExecutionPolicy Bypass -File scripts\gzhu-credential.ps1 get

# 查看状态
powershell -NoProfile -ExecutionPolicy Bypass -File scripts\gzhu-credential.ps1 status

# 清除
powershell -NoProfile -ExecutionPolicy Bypass -File scripts\gzhu-credential.ps1 remove
```

`get` 的输出是一行 JSON：`{"student_id":"202xxxxxx","password":"...","updated_at":"2026-10-06T..."}`。AI 读取后把 `student_id` 填到学号框、`password` 填到密码框，**不要**在最终回复里展示。

## 校内系统入口

| 系统 | URL | 用途 |
|---|---|---|
| 数字广大融合门户 | http://my.gzhu.edu.cn | PC 端统一入口，登录后进服务中心办所有事 |
| 统一身份认证 CAS | https://newcas.gzhu.edu.cn | 所有业务系统 SSO 跳转到此登录 |
| 教务系统 | https://jwxt.gzhu.edu.cn | 选课、个人课表、成绩查询 |
| 网上服务中心 | https://usc.gzhu.edu.cn/taskcenter/ | 请假、报修、勤工助学等办事流程 |

账号 = 学号；初始密码 = 录取证件号码后六位（字母大写），首次登录后建议立即改密。

## 登录操作流程（浏览器自动化）

使用本 skill 的 AI 在需要登录校内系统时，按以下步骤操作（以 `bu` plane / Playwright 为例）：

1. **读取凭证**：先跑 `gzhu-credential.ps1 get`。如果返回错误码 2（未存储），停下来请用户提供学号密码，然后用 `set` 保存，再继续。
2. **导航到登录页**：`bu.navigate("https://jwxt.gzhu.edu.cn")` 或 `http://my.gzhu.edu.cn`，通常会自动跳转到 CAS 登录页 `newcas.gzhu.edu.cn`。
3. **观察登录表单**：`bu.snapshot()` 找到学号框、密码框、登录按钮的 ref。
4. **填表**：`bu.type(学号框ref, student_id)`；`bu.type(密码框ref, password)`。
5. **点登录**：`bu.click(登录按钮ref)`。
6. **验证登录成功**：`bu.wait_for_load()` 后看 URL 是否离开 CAS 页、是否出现用户姓名/学号字样。
7. **按用户需求导航**到对应模块（课表/成绩/选课/服务中心），读取信息。
8. **如果遇到验证码/滑块/二次验证/强制改密**：立即停止自动填表，调用 `interaction.request_action(browserControl)` 让用户接管完成验证，不要尝试绕过。
9. **如果登录失败**：不要反复重试（会触发账号锁定）。把报错截图给用户，让用户确认密码是否正确、是否需要先在网页端改密。

## 适用查询场景

- 个人课表 / 考试安排
- 历年成绩 / GPA 核算
- 选课轮次内查看已选/待选课程（**不替用户点选课提交**）
- 第二课堂 / 综测加分记录
- 请假、报修等办事流程进度
- 奖助学金申请状态

## 不适用场景（不要用自动登录做）

- 替用户选课后直接提交
- 修改密码、绑定手机/邮箱等账号安全设置
- 任何付费、签约、报名类操作
- 教务处通知、制度查询——这些走公开网页就够了，不需要登录

## 已知风险与提示

- 学号密码等同数字广大/教务系统全权凭证。本方案用 Windows DPAPI 加密，但**不是**银行级加密：同一 Windows 用户身份下的恶意程序理论上仍能解密。不要在公共电脑、实验室公用机上开启此功能。
- 如果用户换电脑、重装系统、或怀疑凭证泄露，立即跑 `remove` 清除，再重新 `set`。
- 长期不用时建议 `remove`；下次需要时再让用户提供一次。
- 教务系统/CAS 页面结构若改版，选择器会失效；遇到找不到表单元素时停下来，重新 snapshot 找新 ref，不要硬猜。
