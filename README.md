# Repo Update Monitoring

监控 **公开 GitHub 仓库的 Release 更新** 与 **软件版本更新**（微信 PC 版 / 微信输入法），发现新版本时通过 **Server酱** 推送微信通知。

## 工作方式

```
GitHub Actions（每 12 小时：UTC 00:00 / 12:00，即北京时间 08:00 / 20:00）
    → 读取 monitors.json（监控列表，每条带 type）
    → 按 type 拉取各自数据源
    → 与 state.json 中上次记录比对
    → 有更新 → Server酱 → 微信通知
    → 将最新状态写回 state.json（commit 回写，用于去重）
```

> GitHub Actions 的 cron 使用 **UTC** 时间；高峰期调度可能有分钟级延迟，属正常现象。
> 除定时外，随时可在 `Actions → Monitor Releases → Run workflow` 手动触发。

## 监控类型

| type | 监控对象 | 数据源 | 说明 |
|---|---|---|---|
| `github_release` | 公开仓库正式 Release | GitHub API `/releases/latest` | 自动跳过 draft / prerelease |
| `wechat_windows` | 微信 Windows PC 版 | `windows.weixin.qq.com` 下载页 | 服务端渲染，零成本、实时无延迟 |
| `wetype_windows` | 微信输入法 Windows 版 | `z.weixin.qq.com/web/change-log/166` | 取 `appInfo.windows.latest` 实际构建号 |

## 目录结构

```
repo-update-monitoring/
├── .github/workflows/monitor.yml   # 定时任务（cron 每 12 小时 + 可手动触发）
├── monitor.py                      # 核心脚本：多源检查 + 推送（纯标准库，零依赖）
├── monitors.json                   # 监控列表（增加监控项改这里）
├── state.json                      # 状态记录（自动维护，勿手改）
└── README.md
```

## 部署步骤

1. **创建 GitHub 仓库**，将本项目全部文件 push 上去。
2. **获取 Server酱 SENDKEY**：登录 [Server酱](https://sct.ftqq.com) → 扫码绑定微信 → 复制 SendKey。
3. **配置 Secret**：仓库 `Settings → Secrets and variables → Actions → New repository secret`
   - Name: `SENDKEY`
   - Secret: 粘贴你的 SendKey
4. **手动触发一次**：`Actions → Monitor Releases → Run workflow`，观察是否正常。
   - 首次运行只记录当前版本，**不会**推送。
   - 之后被监控项发布新版本时，微信即收到通知。

## 增加监控项

编辑 `monitors.json`，在 `monitors` 数组追加一条后 push 即可（新增项首次运行同样只记录、不推送）：

```json
{ "type": "github_release", "owner": "owner名", "repo": "仓库名", "alias": "显示别名" }
{ "type": "wechat_windows", "alias": "微信PC版" }
{ "type": "wetype_windows", "alias": "微信输入法(Windows)", "changelog_url": "https://z.weixin.qq.com/web/change-log/166" }
```

- `alias` 是推送消息里的显示名，不填则显示 `owner/repo`。
- 改检查频率：编辑 `.github/workflows/monitor.yml` 中的 `cron` 表达式。

## 当前监控清单

| 别名 | 类型 | 基线版本 |
|---|---|---|
| videdown | `github_release` | v1.2.7 |
| ImageForge | `github_release` | 1.1.0 |
| GenOffice | `github_release` | v0.8.440 |
| 微信PC版 | `wechat_windows` | 4.1.13 |
| 微信输入法(Windows) | `wetype_windows` | 2.1.3.18 |

> 基线随实际发布自动更新，上表仅为某次快照。

## 注意事项

- 只监控 **公开仓库** 的 **正式 Release**（自动跳过 draft / prerelease）。
- Server酱免费版有每日推送条数限制，注意用量。
- `state.json` 由 Workflow 自动 commit 回写，无需手动维护。
- `wetype_windows` 的 `changelog_url` 含文章 id（当前 166），若页面失效需手动 bump。
- 微信输入法监控的是**实际可下载构建号**，可能比官网发布页顶部展示的版本领先一个小版本（构建已放出但发布说明未同步）。
