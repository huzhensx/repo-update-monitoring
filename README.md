# Repo Update Monitoring

监控公开 GitHub 仓库的 **Release 更新**，发现新版本时通过 **Server酱** 推送微信通知。

## 工作方式

```
GitHub Actions (每 30 分钟)
    → 读取 repos.json（监控列表）
    → 调用 GitHub API 获取各仓库最新 Release
    → 与 state.json 中上次记录比对
    → 有更新 → Server酱 → 微信通知
    → 将最新状态写回 state.json（commit 回写，用于去重）
```

## 目录结构

```
repo-update-monitoring/
├── .github/workflows/monitor.yml   # 定时任务（cron 每 30 分钟 + 可手动触发）
├── monitor.py                      # 核心脚本：检查更新 + 推送（纯标准库，零依赖）
├── repos.json                      # 被监控仓库列表（增加仓库改这里）
├── state.json                      # 状态记录（自动维护，勿手改）
└── README.md
```

## 部署步骤

1. **创建 GitHub 仓库**（如 `repo-update-monitoring`），将本项目全部文件 push 上去。
2. **获取 Server酱 SENDKEY**：登录 [Server酱](https://sct.ftqq.com) → 扫码绑定微信 → 复制 SendKey。
3. **配置 Secret**：仓库 `Settings → Secrets and variables → Actions → New repository secret`
   - Name: `SENDKEY`
   - Secret: 粘贴你的 SendKey
4. **手动触发一次**：仓库 `Actions → Monitor Releases → Run workflow`，观察是否正常。
   - 首次运行只记录当前版本，**不会**推送。
   - 之后被监控仓库发布新 Release 时，微信即收到通知。
5. （可选）改检查频率：编辑 `monitor.yml` 中的 `cron` 表达式。

## 增加监控仓库

编辑 `repos.json`，追加一条记录后 push 即可：

```json
{
  "repos": [
    { "owner": "cshuangyy", "repo": "videdown", "alias": "videdown" },
    { "owner": "LAVARONG", "repo": "ImageForge", "alias": "ImageForge" },
    { "owner": "新owner", "repo": "新仓库名", "alias": "显示别名" }
  ]
}
```

- `alias` 是推送消息里的显示名，不填则显示 `owner/repo`。
- 新增仓库后的第一次运行同样只记录、不推送。

## 注意事项

- 只监控 **公开仓库** 的 **正式 Release**（自动跳过 draft / prerelease）。
- Server酱免费版有每日推送条数限制，注意用量。
- `state.json` 由 Workflow 自动 commit 回写，无需手动维护。
