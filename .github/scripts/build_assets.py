#!/usr/bin/env python3
"""
由 GitHub Actions 每天调用，纯本地生成所有 README 图片（不依赖任何外部渲染服务）：

  1. 统计总 star（含 fork），更新 README 里的 Total Stars 徽章
  2. 生成仓库 pin 卡片  -> assets/pin/<repo>.svg
  3. 生成 stats 卡片    -> assets/stats.svg
  4. 生成 top-langs 卡片-> assets/top-langs.svg

只用 GitHub REST API（Actions 自带 GITHUB_TOKEN），无任何第三方 429 风险。
"""
import json
import os
import re
import sys
import time
import urllib.request
import urllib.error
from xml.sax.saxutils import escape

USERNAME = os.environ.get("GITHUB_USERNAME", "Dainsleif233")
TOKEN = os.environ.get("GH_TOKEN") or os.environ.get("GITHUB_TOKEN") or ""

# GitHub linguist 配色（用于语言圆点与柱状图）
LANG_COLORS = {
    "Python": "#3572A5", "JavaScript": "#f1e05a", "TypeScript": "#3178c6",
    "Java": "#b07219", "Go": "#00ADD8", "Kotlin": "#A97BFF",
    "PHP": "#4F5D95", "Dockerfile": "#384d54", "Shell": "#89e051",
    "C#": "#178600", "Rust": "#dea584", "HTML": "#e34c26", "CSS": "#563d7c",
    "C++": "#f34b7d", "C": "#555555", "Vue": "#41b883", "mcfunction": "#FF6B6B",
}

# 想换 pin 的仓库，改这里即可（顺序即展示顺序）
PIN_REPOS = [
    "MultiJoin",
    "NakiriElectricity",
    "ddddGocr",
    "ddpatch",
    "JustEnoughSkins",
    "directlink",
]


def gh_api(path, retries=4):
    url = f"https://api.github.com{path}"
    headers = {"Accept": "application/vnd.github+json",
               "X-GitHub-Api-Version": "2022-11-28",
               "User-Agent": "dainsleif-readme-bot"}
    if TOKEN:
        headers["Authorization"] = f"Bearer {TOKEN}"
    for i in range(retries):
        try:
            req = urllib.request.Request(url, headers=headers)
            with urllib.request.urlopen(req, timeout=30) as r:
                return json.load(r)
        except Exception as e:  # noqa
            print(f"  [api {i+1}/{retries}] {path} -> {e}", file=sys.stderr)
            if i < retries - 1:
                time.sleep(5)
    raise RuntimeError(f"GitHub API failed: {path}")


def fetch_all_repos():
    repos, page = [], 1
    while True:
        data = gh_api(f"/users/{USERNAME}/repos?per_page=100&page={page}&type=all")
        if not data:
            break
        repos.extend(data)
        if len(data) < 100:
            break
        page += 1
    return repos


def wrap_text(s, width):
    s = (s or "").strip()
    words = s.split()
    lines, cur = [], ""
    for w in words:
        if len(cur) + len(w) + 1 <= width:
            cur = (cur + " " + w).strip()
        else:
            if cur:
                lines.append(cur)
            cur = w
    if cur:
        lines.append(cur)
    return lines


def pin_card(repo):
    name = repo["name"]
    desc = repo.get("description") or ""
    lang = repo.get("language") or "Other"
    stars = repo.get("stargazers_count", 0) or 0
    forks = repo.get("forks_count", 0) or 0
    color = LANG_COLORS.get(lang, "#9aa5ce")
    lines = wrap_text(desc, 54)
    if len(lines) > 2:
        lines = lines[:2]
        lines[1] = lines[1][:50] + "…"
    W, H = 460, 118
    p = [f'<svg xmlns="http://www.w3.org/2000/svg" width="{W}" height="{H}" viewBox="0 0 {W} {H}">',
         f'<rect width="{W}" height="{H}" rx="6" fill="#1a1b27" stroke="#292e42"/>',
         f'<text x="20" y="32" font-family="Segoe UI,Helvetica,Arial,sans-serif" font-size="15" font-weight="600" fill="#7aa2f7">{escape(name)}</text>']
    y = 54
    for ln in lines[:2]:
        p.append(f'<text x="20" y="{y}" font-family="Segoe UI,Helvetica,Arial,sans-serif" font-size="11.5" fill="#9aa5ce">{escape(ln)}</text>')
        y += 16
    p.append(f'<circle cx="20" cy="96" r="5" fill="{color}"/>')
    p.append(f'<text x="32" y="100" font-family="Segoe UI,Helvetica,Arial,sans-serif" font-size="11.5" fill="#9aa5ce">{escape(lang)}</text>')
    p.append(f'<text x="300" y="100" font-family="Segoe UI,Helvetica,Arial,sans-serif" font-size="12" fill="#e0af68">★</text>')
    p.append(f'<text x="312" y="100" font-family="Segoe UI,Helvetica,Arial,sans-serif" font-size="11.5" fill="#9aa5ce">{stars}</text>')
    p.append('<g transform="translate(360,89)" fill="#9aa5ce">')
    p.append('<circle cx="3" cy="3" r="1.7"/>')
    p.append('<circle cx="11" cy="3" r="1.7"/>')
    p.append('<circle cx="7" cy="11" r="1.7"/>')
    p.append('<path d="M3,4.7 V6.6 Q3,7.4 3.8,7.4 H10.2 Q11,7.4 11,6.6 V4.7" fill="none" stroke="#9aa5ce" stroke-width="1"/>')
    p.append('<path d="M7,7.4 V9.3" stroke="#9aa5ce" stroke-width="1"/>')
    p.append('</g>')
    p.append(f'<text x="378" y="100" font-family="Segoe UI,Helvetica,Arial,sans-serif" font-size="11.5" fill="#9aa5ce">{forks}</text>')
    p.append('</svg>')
    return "\n".join(p)


def stats_card(user, total_stars, total_repos, total_forks):
    W, H = 460, 192
    rows = [
        ("Total Stars", total_stars, "#e0af68"),
        ("Total Repos", total_repos, "#7aa2f7"),
        ("Total Forks", total_forks, "#9ece6a"),
        ("Followers", user.get("followers", 0) or 0, "#bb9af7"),
        ("Following", user.get("following", 0) or 0, "#7dcfff"),
    ]
    p = [f'<svg xmlns="http://www.w3.org/2000/svg" width="{W}" height="{H}" viewBox="0 0 {W} {H}">',
         f'<rect width="{W}" height="{H}" rx="6" fill="#1a1b27" stroke="#292e42"/>',
         f'<text x="20" y="32" font-family="Segoe UI,Helvetica,Arial,sans-serif" font-size="16" font-weight="700" fill="#7aa2f7">{escape(USERNAME + " on GitHub")}</text>']
    y = 64
    for label, val, color in rows:
        p.append(f'<text x="20" y="{y}" font-family="Segoe UI,Helvetica,Arial,sans-serif" font-size="13" fill="#9aa5ce">{escape(label)}</text>')
        p.append(f'<text x="440" y="{y}" text-anchor="end" font-family="Segoe UI,Helvetica,Arial,sans-serif" font-size="13" font-weight="600" fill="{color}">{val}</text>')
        y += 24
    p.append('</svg>')
    return "\n".join(p)


def top_langs_card(lang_counts):
    items = sorted([(l, c) for l, c in lang_counts.items() if l and l != "Other"],
                   key=lambda x: -x[1])[:6]
    total = sum(c for _, c in items) or 1
    W = 460
    H = 50 + len(items) * 24 + 12
    p = [f'<svg xmlns="http://www.w3.org/2000/svg" width="{W}" height="{H}" viewBox="0 0 {W} {H}">',
         f'<rect width="{W}" height="{H}" rx="6" fill="#1a1b27" stroke="#292e42"/>',
         f'<text x="20" y="32" font-family="Segoe UI,Helvetica,Arial,sans-serif" font-size="16" font-weight="700" fill="#7aa2f7">Top Languages</text>']
    y = 52
    bar_x, bar_max = 110, 280
    for lang, c in items:
        pct = c / total
        color = LANG_COLORS.get(lang, "#9aa5ce")
        p.append(f'<text x="20" y="{y+9}" font-family="Segoe UI,Helvetica,Arial,sans-serif" font-size="12" fill="#9aa5ce">{escape(lang)}</text>')
        p.append(f'<rect x="{bar_x}" y="{y}" width="{max(2, int(bar_max*pct))}" height="10" rx="3" fill="{color}"/>')
        p.append(f'<text x="{bar_x+bar_max+12}" y="{y+9}" font-family="Segoe UI,Helvetica,Arial,sans-serif" font-size="11" fill="#565f89">{pct*100:.0f}%</text>')
        y += 24
    p.append('</svg>')
    return "\n".join(p)


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
    user = gh_api(f"/users/{USERNAME}")
    repos = fetch_all_repos()

    total_stars = sum((r.get("stargazers_count", 0) or 0) for r in repos)
    total_forks = sum((r.get("forks_count", 0) or 0) for r in repos)
    total_repos = len(repos)
    print(f"repos={total_repos} stars(incl forks)={total_stars} forks(incl forks)={total_forks}")

    # 语言统计（仅统计自己仓库）
    lang_counts = {}
    for r in repos:
        if r.get("fork"):
            continue
        lang = r.get("language")
        if lang:
            lang_counts[lang] = lang_counts.get(lang, 0) + 1

    by_name = {r["name"]: r for r in repos}

    # pin 卡片
    for repo in PIN_REPOS:
        if repo in by_name:
            write_file(f"assets/pin/{repo}.svg", pin_card(by_name[repo]))
            print(f"pin: {repo}")
        else:
            print(f"pin SKIP (not found): {repo}", file=sys.stderr)

    write_file("assets/stats.svg", stats_card(user, total_stars, total_repos, total_forks))
    write_file("assets/top-langs.svg", top_langs_card(lang_counts))
    print("stats + top-langs written")

    update_readme_stars(total_stars)


if __name__ == "__main__":
    main()