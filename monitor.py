#!/usr/bin/env python3
"""Repo Update Monitoring

监控以下类型的更新并通过 Server酱推送微信通知：
- github_release : 公开仓库的 Release（取 latest，已自动跳过 draft/prerelease）
- wechat_windows : 微信 Windows PC 版
- wetype_windows : 微信输入法 Windows 版

无第三方依赖（仅标准库）。在 GitHub Actions 中定时运行。

微信 PC 版数据源：windows.weixin.qq.com 下载页（服务端渲染，plain HTTP，零成本、实时、无延迟）。
正则提取下载链接中的 WeChatWin_X.Y.Z.exe 即得当前版本号。

微信输入法 Windows 版数据源：z.weixin.qq.com 的 change-log 详情页（服务端把版本数据
嵌进 HTML 的 window.injectData，plain HTTP 即可读，零成本、实时）。详情页 URL 见
monitors.json 的 changelog_url。正则提取 appInfo.windows.latest 直链里的
WeTypeSetup_X.Y.Z.B_N.exe，得当前实际构建版本号（如 2.1.3.18）。该 latest 字段为全局
最新构建，发布新版本时会自动变化，可最早感知更新（含静默热修）。
"""

import json
import os
import re
import sys
import urllib.error
import urllib.parse
import urllib.request

BASE = os.path.dirname(os.path.abspath(__file__))
CFG_FILE = os.path.join(BASE, "monitors.json")
STATE_FILE = os.path.join(BASE, "state.json")
GITHUB_TOKEN = os.environ.get("GITHUB_TOKEN", "")

UA = {"User-Agent": "repo-update-monitoring"}


def http_get(url, timeout=30, headers=None):
    h = dict(UA)
    if headers:
        h.update(headers)
    req = urllib.request.Request(url, headers=h)
    with urllib.request.urlopen(req, timeout=timeout) as resp:
        return resp.read().decode("utf-8", "ignore")


def github_api(url):
    h = {"Accept": "application/vnd.github+json"}
    if GITHUB_TOKEN:
        h["Authorization"] = f"Bearer {GITHUB_TOKEN}"
    return json.loads(http_get(url, headers=h))


def load_state():
    if os.path.exists(STATE_FILE):
        with open(STATE_FILE, encoding="utf-8") as f:
            return json.load(f)
    return {}


def save_state(state):
    with open(STATE_FILE, "w", encoding="utf-8") as f:
        json.dump(state, f, ensure_ascii=False, indent=2)


def notify(title, desp):
    key = os.environ.get("SENDKEY", "").strip()
    if not key:
        print("[!] SENDKEY 未配置，跳过推送（不会报错）")
        return
    data = urllib.parse.urlencode({"title": title, "desp": desp}).encode()
    try:
        req = urllib.request.Request(f"https://sctapi.ftqq.com/{key}.send", data=data)
        with urllib.request.urlopen(req, timeout=30) as resp:
            print("[ServerChan]", resp.read().decode("utf-8", "ignore"))
    except Exception as e:
        print(f"[!] 推送失败: {e}")


def version_tuple(v):
    return tuple(int(x) for x in v.split(".") if x.isdigit())


# ---------- GitHub Release ----------
def check_github_release(item):
    owner, repo = item["owner"], item["repo"]
    try:
        rel = github_api(f"https://api.github.com/repos/{owner}/{repo}/releases/latest")
    except urllib.error.HTTPError as e:
        print(f"[{item.get('alias')}] 获取失败 HTTP {e.code}，跳过")
        return None
    except Exception as e:
        print(f"[{item.get('alias')}] 获取失败: {e}，跳过")
        return None
    return {
        "version": rel.get("tag_name", ""),
        "published_at": rel.get("published_at", ""),
        "name": rel.get("name") or rel.get("tag_name", ""),
        "url": rel.get("html_url", ""),
    }


# ---------- 微信 Windows PC 版 ----------
def fetch_wechat_windows_version():
    try:
        html = http_get("https://windows.weixin.qq.com/", timeout=30)
    except Exception as e:
        print(f"[微信PC版] 下载页获取失败: {e}")
        return None
    m = re.search(r"WeChatWin_(\d+\.\d+\.\d+)\.exe", html)
    return m.group(1) if m else None


# ---------- 微信输入法 Windows 版 ----------
BROWSER_UA = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
        "(KHTML, like Gecko) Chrome/120.0 Safari/537.36"
    )
}


def fetch_wetype_windows_version(item):
    url = item.get(
        "changelog_url", "https://z.weixin.qq.com/web/change-log/166"
    )
    try:
        html = http_get(url, timeout=30, headers=BROWSER_UA)
    except Exception as e:
        print(f"[{item.get('alias')}] 详情页获取失败: {e}")
        return None
    # 优先取 appInfo.windows.latest 直链里的版本（全局最新构建，4 段）
    m = re.search(
        r'"latest"\s*:\s*"[^"]*WeTypeSetup_(\d+\.\d+\.\d+\.\d+)_\d+\.exe"', html
    )
    if m:
        return m.group(1)
    # 兜底：取页面内所有 WeTypeSetup 直链的最高版本
    vers = re.findall(r"WeTypeSetup_(\d+\.\d+\.\d+\.\d+)_\d+\.exe", html)
    if vers:
        return max(vers, key=version_tuple)
    # 再兜底：3 段版本
    m3 = re.search(r"WeTypeSetup_(\d+\.\d+\.\d+)_\d+\.exe", html)
    return m3.group(1) if m3 else None


def main():
    with open(CFG_FILE, encoding="utf-8") as f:
        cfg = json.load(f)
    state = load_state()
    state_changed = False

    for item in cfg.get("monitors", []):
        t = item.get("type")

        if t == "github_release":
            owner, repo = item["owner"], item["repo"]
            alias = item.get("alias") or f"{owner}/{repo}"
            key = f"{owner}/{repo}"
            info = check_github_release(item)
            if not info:
                continue
            tag = info["version"]
            published = info["published_at"]
            prev = state.get(key, {})
            if prev.get("tag") is None:
                print(f"[{alias}] 首次初始化，记录 {tag}")
            elif tag != prev.get("tag") or published != prev.get("published_at"):
                desp = (
                    f"### {alias} 发布新版本\n\n"
                    f"- **版本**: {info['name']}\n"
                    f"- **Tag**: {tag}\n"
                    f"- **发布时间**: {published}\n\n"
                    f"[查看 Release]({info['url']})\n\n---\n"
                    f"<small>由 Repo Update Monitoring 自动推送</small>"
                )
                notify(f"[Repo监控] {alias} 更新到 {tag}", desp)
                print(f"[{alias}] 检测到新版本 {tag}，已推送")
            state[key] = {"tag": tag, "published_at": published,
                          "name": info["name"], "url": info["url"]}
            state_changed = True

        elif t == "wechat_windows":
            alias = item.get("alias") or "微信PC版"
            key = "wechat_windows"
            ver = fetch_wechat_windows_version()
            if not ver:
                print(f"[{alias}] 未抓到版本，跳过")
                continue
            print(f"[{alias}] 当前版本: {ver}")
            prev = state.get(key, {})
            if prev.get("version") is None:
                print(f"[{alias}] 首次初始化，记录 {ver}")
            elif ver != prev.get("version"):
                desp = (
                    f"### {alias} 发布新版本\n\n"
                    f"- **版本**: {ver}\n\n"
                    f"<small>由 Repo Update Monitoring 自动推送</small>"
                )
                notify(f"[软件监控] {alias} 更新到 {ver}", desp)
                print(f"[{alias}] 检测到新版本 {ver}，已推送")
            state[key] = {"version": ver}
            state_changed = True

        elif t == "wetype_windows":
            alias = item.get("alias") or "微信输入法(Windows)"
            key = "wetype_windows"
            ver = fetch_wetype_windows_version(item)
            if not ver:
                print(f"[{alias}] 未抓到版本，跳过")
                continue
            print(f"[{alias}] 当前版本: {ver}")
            prev = state.get(key, {})
            if prev.get("version") is None:
                print(f"[{alias}] 首次初始化，记录 {ver}")
            elif ver != prev.get("version"):
                desp = (
                    f"### {alias} 发布新版本\n\n"
                    f"- **版本**: {ver}\n\n"
                    f"<small>由 Repo Update Monitoring 自动推送</small>"
                )
                notify(f"[软件监控] {alias} 更新到 {ver}", desp)
                print(f"[{alias}] 检测到新版本 {ver}，已推送")
            state[key] = {"version": ver}
            state_changed = True

        else:
            print(f"[!] 未知监控类型: {t}，跳过")

    if state_changed:
        save_state(state)
    sys.exit(0)


if __name__ == "__main__":
    main()
