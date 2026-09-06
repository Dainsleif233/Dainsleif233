#!/usr/bin/env python3
"""
由 GitHub Actions 每天调用，纯本地生成所有 README 图片（不依赖任何外部渲染服务）：

  1. 统计总 star（含 fork），更新 README 里的 Total Stars 徽章
  2. 生成 stats 卡片    -> assets/stats.svg
  3. 生成 top-langs 卡片-> assets/top-langs.svg

所有卡片内置 @media (prefers-color-scheme) 主题：浅色/深色自动切换。
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

# GitHub linguist 配色（语言圆点/柱状图，两套主题下都保持品牌色）
LANG_COLORS = {
    "Python": "#3572A5", "JavaScript": "#f1e05a", "TypeScript": "#3178c6",
    "Java": "#b07219", "Go": "#00ADD8", "Kotlin": "#A97BFF",
    "PHP": "#4F5D95", "Dockerfile": "#384d54", "Shell": "#89e051",
    "C#": "#178600", "Rust": "#dea584", "HTML": "#e34c26", "CSS": "#563d7c",
    "C++": "#f34b7d", "C": "#555555", "Vue": "#41b883", "mcfunction": "#FF6B6B",
}

# 浅色为默认，深色通过 @media 覆盖；全部走 CSS 变量
THEME_STYLE = (
    "<style>"
    ":root{"
    "--bg:#ffffff;--border:#d0d7de;--title:#0969da;--text:#57606a;"
    "--muted:#6e7781;--star:#bf8700;"
    "--c-stars:#bf8700;--c-repos:#0969da;--c-forks:#1a7f37;"
    "--c-followers:#8250df;--c-following:#0a3069;"
    "}"
    "@media (prefers-color-scheme: dark){"
    ":root{"
    "--bg:#1a1b27;--border:#292e42;--title:#7aa2f7;--text:#9aa5ce;"
    "--muted:#565f89;--star:#e0af68;"
    "--c-stars:#e0af68;--c-repos:#7aa2f7;--c-forks:#9ece6a;"
    "--c-followers:#bb9af7;--c-following:#7dcfff;"
    "}"
    "}"
    ".frame{fill:var(--bg);stroke:var(--border);}"
    ".title{fill:var(--title);}"
    ".desc{fill:var(--text);}"
    ".lang{fill:var(--text);}"
    ".star{fill:var(--star);}"
    ".muted{fill:var(--muted);}"
    ".barlabel{fill:var(--text);}"
    ".barpct{fill:var(--muted);}"
    ".v-stars{fill:var(--c-stars);}"
    ".v-repos{fill:var(--c-repos);}"
    ".v-forks{fill:var(--c-forks);}"
    ".v-followers{fill:var(--c-followers);}"
    ".v-following{fill:var(--c-following);}"
    ".icon{fill:var(--text);stroke:var(--text);}"
    "</style>"
)


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


def stats_card(user, total_stars, total_repos, total_forks):
    W, H = 460, 192
    rows = [
        ("Total Stars", total_stars, "v-stars"),
        ("Total Repos", total_repos, "v-repos"),
        ("Total Forks", total_forks, "v-forks"),
        ("Followers", user.get("followers", 0) or 0, "v-followers"),
        ("Following", user.get("following", 0) or 0, "v-following"),
    ]
    ff = 'font-family="Segoe UI,Helvetica,Arial,sans-serif"'
    p = [f'<svg xmlns="http://www.w3.org/2000/svg" width="{W}" height="{H}" viewBox="0 0 {W} {H}">',
         THEME_STYLE,
         f'<rect class="frame" width="{W}" height="{H}" rx="6"/>',
         f'<text class="title" x="20" y="32" {ff} font-size="16" font-weight="700">{escape(USERNAME + " on GitHub")}</text>']
    y = 64
    for label, val, cls in rows:
        p.append(f'<text class="desc" x="20" y="{y}" {ff} font-size="13">{escape(label)}</text>')
        p.append(f'<text class="{cls}" x="440" y="{y}" text-anchor="end" {ff} font-size="13" font-weight="600">{val}</text>')
        y += 24
    p.append('</svg>')
    return "\n".join(p)


def top_langs_card(lang_counts):
    items = sorted([(l, c) for l, c in lang_counts.items() if l and l != "Other"],
                   key=lambda x: -x[1])[:6]
    total = sum(c for _, c in items) or 1
    W = 460
    H = 50 + len(items) * 24 + 12
    ff = 'font-family="Segoe UI,Helvetica,Arial,sans-serif"'
    p = [f'<svg xmlns="http://www.w3.org/2000/svg" width="{W}" height="{H}" viewBox="0 0 {W} {H}">',
         THEME_STYLE,
         f'<rect class="frame" width="{W}" height="{H}" rx="6"/>',
         f'<text class="title" x="20" y="32" {ff} font-size="16" font-weight="700">Top Languages</text>']
    y = 52
    bar_x, bar_max = 110, 280
    for lang, c in items:
        pct = c / total
        color = LANG_COLORS.get(lang, "#9aa5ce")
        p.append(f'<text class="barlabel" x="20" y="{y+9}" {ff} font-size="12">{escape(lang)}</text>')
        p.append(f'<rect x="{bar_x}" y="{y}" width="{max(2, int(bar_max*pct))}" height="10" rx="3" fill="{color}"/>')
        p.append(f'<text class="barpct" x="{bar_x+bar_max+12}" y="{y+9}" {ff} font-size="11">{pct*100:.0f}%</text>')
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

    lang_counts = {}
    for r in repos:
        if r.get("fork"):
            continue
        lang = r.get("language")
        if lang:
            lang_counts[lang] = lang_counts.get(lang, 0) + 1

    write_file("assets/stats.svg", stats_card(user, total_stars, total_repos, total_forks))
    write_file("assets/top-langs.svg", top_langs_card(lang_counts))
    print("stats + top-langs written")

    update_readme_stars(total_stars)


if __name__ == "__main__":
    main()