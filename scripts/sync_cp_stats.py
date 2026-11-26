#!/usr/bin/env python3
"""Synchronize all CP telemetry SVG cards from Pri8899/CP into Pri8899/Pri8899."""

import json
import os
import re
import subprocess
import urllib.request

CP_REPO = "Pri8899/CP"
TARGET_REPO = "Pri8899/Pri8899"
SVG_FILES = [
    "codesync-stats.svg",
    "overview.svg",
    "codeforces.svg",
    "leetcode.svg",
    "atcoder.svg",
    "cses.svg",
    "toph.svg",
]


def http_get(url: str, headers: dict | None = None) -> str:
    req = urllib.request.Request(url, headers=headers or {"User-Agent": "Pri8899-CP-Sync/1.0"})
    with urllib.request.urlopen(req, timeout=15) as resp:
        return resp.read().decode("utf-8", errors="replace")


def fetch_latest_cp_sha() -> str:
    try:
        out = subprocess.check_output(
            ["git", "ls-remote", f"https://github.com/{CP_REPO}.git", "refs/heads/main"],
            text=True,
            timeout=15,
        ).strip()
        if out:
            return out.split()[0]
    except Exception:
        pass

    headers = {
        "User-Agent": "Pri8899-CP-Sync/1.0",
        "Accept": "application/vnd.github+json",
    }
    token = os.environ.get("GITHUB_TOKEN")
    if token:
        headers["Authorization"] = f"Bearer {token}"
    data = json.loads(http_get(f"https://api.github.com/repos/{CP_REPO}/commits/main", headers))
    return data["sha"]


def normalize_svg(name: str, content: str) -> str:
    if name == "codesync-stats.svg":
        content = re.sub(
            r'<g transform="translate\(390,\s*21\)">\s*<rect width="81"',
            '<g transform="translate(380, 21)">\n    <rect width="91"',
            content,
        )
        content = content.replace('letter-spacing="0.4px">AUTO-SYNC</text>', 'letter-spacing="0.3px">AUTO-SYNC</text>')
    elif name == "overview.svg":
        content = content.replace(">Problem Solved by platform<", ">Problems Solved by Platform<")
    return content


def main() -> None:
    sha = fetch_latest_cp_sha()
    short_sha = sha[:7]
    root_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    assets_dir = os.path.join(root_dir, "assets")
    os.makedirs(assets_dir, exist_ok=True)

    for name in SVG_FILES:
        raw_url = f"https://raw.githubusercontent.com/{CP_REPO}/{sha}/assets/{name}"
        svg = http_get(raw_url)
        if "<svg" not in svg or "</svg>" not in svg:
            raise RuntimeError(f"Invalid SVG payload received for {name}")
        svg = normalize_svg(name, svg)
        dest_path = os.path.join(assets_dir, name)
        with open(dest_path, "w", encoding="utf-8", newline="\n") as f:
            f.write(svg)
        print(f"Synced {name} from CP@{short_sha}")

    readme_path = os.path.join(root_dir, "README.md")
    with open(readme_path, "r", encoding="utf-8") as f:
        readme = f.read()

    for name in SVG_FILES:
        pattern = rf"https://raw\.githubusercontent\.com/Pri8899/(?:CP|Pri8899)/main/assets/{re.escape(name)}(?:\?v=[A-Za-z0-9_-]+)?"
        replacement = f"https://raw.githubusercontent.com/{TARGET_REPO}/main/assets/{name}?v={short_sha}"
        readme = re.sub(pattern, replacement, readme)

    with open(readme_path, "w", encoding="utf-8", newline="\n") as f:
        f.write(readme)
    print(f"Updated README.md cache-busters to v={short_sha}")


if __name__ == "__main__":
    main()
