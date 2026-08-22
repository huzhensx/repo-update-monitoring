#!/usr/bin/env python3
"""Repo Update Monitoring - 监控公开仓库的 Release 更新，并通过 Server酱推送微信通知。

无第三方依赖（仅标准库）。在 GitHub Actions 中定时运行。
"""

import json
import os
import sys
import urllib.error
import urllib.parse
import urllib.request

BASE = os.path.dirname(os.path.abspath(__file__))
REPOS_FILE = os.path.join(BASE, "repos.json")
STATE_FILE = os.path.join(BASE, "state.json")
TOKEN = os.environ.get("GITHUB_TOKEN", "")


def github_api(url):
    """GET GitHub API，优先带 GITHUB_TOKEN 提升限流。"""
    req = urllib.request.Request(
        url,
        headers={
            "Accept": "application/vnd.github+json",
            "User-Agent": "repo-update-monitoring",
        },
    )
    if TOKEN:
        req.add_header("Authorization", f"Bearer {TOKEN}")
    with urllib.request.urlopen(req, timeout=30) as resp:
        return json.load(resp)


def load_state():
    if os.path.exists(STATE_FILE):
        with open(STATE_FILE, encoding="utf-8") as f:
            return json.load(f)
    return {}


def save_state(state):
    with open(STATE_FILE, "w", encoding="utf-8") as f:
        json.dump(state, f, ensure_ascii=False, indent=2)


def notify(title, desp):
    """通过 Server酱推送微信通知。"""
    key = os.environ.get("SENDKEY", "").strip()
    if not key:
        print("[!] SENDKEY 未配置，跳过推送（不会报错）")
        return
    data = urllib.parse.urlencode({"title": title, "desp": desp}).encode("utf-8")
    req = urllib.request.Request(f"https://sctapi.ftqq.com/{key}.send", data=data)
    with urllib.request.urlopen(req, timeout=30) as resp:
        body = resp.read().decode("utf-8", "ignore")
    print("[ServerChan]", body)


def main():
    with open(REPOS_FILE, encoding="utf-8") as f:
        cfg = json.load(f)

    state = load_state()
    state_changed = False

    for item in cfg.get("repos", []):
        owner, repo = item["owner"], item["repo"]
        alias = item.get("alias") or f"{owner}/{repo}"
        key = f"{owner}/{repo}"

        try:
            rel = github_api(f"https://api.github.com/repos/{owner}/{repo}/releases/latest")
        except urllib.error.HTTPError as e:
            # 404 = 仓库无 release；其他错误打印后跳过，不影响其余仓库
            print(f"[{alias}] 获取失败 HTTP {e.code}，跳过")
            continue
        except Exception as e:
            print(f"[{alias}] 获取失败: {e}，跳过")
            continue

        tag = rel.get("tag_name", "")
        published = rel.get("published_at", "")
        rel_url = rel.get("html_url", "")
        rel_name = rel.get("name") or tag

        prev = state.get(key, {})
        prev_tag = prev.get("tag")
        prev_published = prev.get("published_at")

        if prev_tag is None:
            # 首次监控：只记录当前版本，不推送
            print(f"[{alias}] 首次初始化，记录当前版本 {tag}")
        elif tag != prev_tag or published != prev_published:
            desp = (
                f"### {alias} 发布新版本\n\n"
                f"- **版本**: {rel_name}\n"
                f"- **Tag**: {tag}\n"
                f"- **发布时间**: {published}\n\n"
                f"[查看 Release]({rel_url})\n\n---\n"
                f"<small>由 Repo Update Monitoring 自动推送</small>"
            )
            notify(f"[Repo监控] {alias} 更新到 {tag}", desp)
            print(f"[{alias}] 检测到新版本 {tag}，已推送")

        state[key] = {
            "tag": tag,
            "published_at": published,
            "name": rel_name,
            "url": rel_url,
        }
        state_changed = True

    if state_changed:
        save_state(state)

    sys.exit(0)


if __name__ == "__main__":
    main()
