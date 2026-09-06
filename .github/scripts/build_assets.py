#!/usr/bin/env python3
"""
由 GitHub Actions 每天调用。负责：
  1. 统计总 star（含 fork），更新 README 里的 Total Stars 徽章
  2. 抓取 github-readme-stats 的 stats / top-langs / pin 卡片 SVG，
     存为本地静态文件（assets/），彻底摆脱公共实例 429 / 自部署依赖
  3. 抓取失败的卡片保留旧文件，不会让 README 变空
"""
import json
import os
import re
import sys
import time
import urllib.request
import urllib.error

USERNAME = os.environ.get("GITHUB_USERNAME", "Dainsleif233")
TOKEN = os.environ.get("GH_TOKEN") or os.environ.get("GITHUB_TOKEN") or ""
STATS_BASE = "https://github-readme-stats.vercel.app/api"
THEME = "tokyonight"

# 想换 pin 的仓库，改这里即可（顺序即展示顺序）
PIN_REPOS = [
    "MultiJoin",
    "NakiriElectricity",
    "ddddGocr",
    "ddpatch",
    "JustEnoughSkins",
    "directlink",
]


def gh_api(path):
    url = f"https://api.github.com{path}"
    headers = {"Accept": "application/vnd.github+json",
               "X-GitHub-Api-Version": "2022-11-28",
               "User-Agent": "dainsleif-readme-bot"}
    if TOKEN:
        headers["Authorization"] = f"Bearer {TOKEN}"
    req = urllib.request.Request(url, headers=headers)
    with urllib.request.urlopen(req, timeout=30) as r:
        return json.load(r)


def fetch_svg(url, retries=6, delay=15):
    """带重试地抓取一个 SVG；全部失败返回 None。"""
    for i in range(retries):
        try:
            req = urllib.request.Request(url, headers={"User-Agent": "dainsleif-readme-bot"})
            with urllib.request.urlopen(req, timeout=30) as r:
                return r.read().decode("utf-8", "replace")
        except Exception as e:  # noqa
            print(f"  [{i+1}/{retries}] {url} -> {e}", file=sys.stderr)
            if i < retries - 1:
                time.sleep(delay)
    return None


def total_stars_including_forks():
    """遍历全部仓库（含 fork），累加 stargazers_count。"""
    total = 0
    page = 1
    while True:
        data = gh_api(f"/users/{USERNAME}/repos?per_page=100&page={page}&type=all")
        if not data:
            break
        for r in data:
            total += r.get("stargazers_count", 0) or 0
        if len(data) < 100:
            break
        page += 1
    return total


def write_file(path, content):
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, "w", encoding="utf-8") as f:
        f.write(content)


def update_readme_stars(stars):
    with open("README.md", "r", encoding="utf-8") as f:
        txt = f.read()
    new = re.sub(r"(Total%20Stars-)\d+(-F59E0B)", rf"\g<1>{stars}\g<2>", txt)
    if new == txt:
        print("README: Total Stars already up to date.")
        return
    with open("README.md", "w", encoding="utf-8") as f:
        f.write(new)
    print(f"README: Total Stars -> {stars}")


def main():
    # 1. 总 star（含 fork）
    stars = total_stars_including_forks()
    print(f"Total stars (incl forks): {stars}")
    update_readme_stars(stars)

    # 2. stats / top-langs
    targets = [
        ("assets/stats.svg",
         f"{STATS_BASE}?username={USERNAME}&show_icons=true&theme={THEME}"
         f"&count_private=true&include_all_commits=true"),
        ("assets/top-langs.svg",
         f"{STATS_BASE}/top-langs/?username={USERNAME}&layout=compact"
         f"&theme={THEME}&langs_count=8"),
    ]
    # 3. pin 卡片
    for repo in PIN_REPOS:
        targets.append((
            f"assets/pin/{repo}.svg",
            f"{STATS_BASE}/pin/?username={USERNAME}&repo={repo}&theme={THEME}",
        ))

    ok = 0
    for path, url in targets:
        print(f"Fetching {path} ...")
        svg = fetch_svg(url)
        if svg:
            write_file(path, svg)
            ok += 1
        else:
            print(f"  FAILED (kept old file if any): {path}", file=sys.stderr)
    print(f"Done: {ok}/{len(targets)} assets written.")


if __name__ == "__main__":
    main()
