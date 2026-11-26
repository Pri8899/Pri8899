#!/usr/bin/env python3
"""Synchronize all CP telemetry SVG cards and profile links from Pri8899/CP into Pri8899/Pri8899."""

import json
import os
import re
import subprocess
import urllib.parse
import urllib.request

CP_REPO = "Pri8899/CP"
SVG_FILES = [
    "codesync-stats.svg",
    "overview.svg",
    "codeforces.svg",
    "leetcode.svg",
    "atcoder.svg",
    "cses.svg",
    "toph.svg",
]
PLATFORM_BADGE_SVGS = (
    "codeforces.svg",
    "leetcode.svg",
    "atcoder.svg",
    "cses.svg",
    "toph.svg",
)
FALLBACK_URLS = {
    "https://codeforces.com",
    "https://leetcode.com",
    "https://atcoder.jp",
    "https://cses.fi/problemset",
    "https://toph.co",
}


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


def extract_cp_profile_links(cp_readme: str) -> dict[str, str]:
    """Extract platform badge profile hrefs keyed by badge SVG filename."""
    links: dict[str, str] = {}
    for svg_name in PLATFORM_BADGE_SVGS:
        match = re.search(
            rf'<a\s+href="([^"]+)"[^>]*>\s*<img\s+[^>]*src="[^"]*assets/{re.escape(svg_name)}"',
            cp_readme,
        )
        if match:
            links[svg_name] = match.group(1).strip()
    return links


def resolve_profile_url(svg_name: str, cp_href: str, existing_href: str) -> str:
    """Resolve synced profile URL while avoiding overwriting a real profile link with a bare fallback."""
    clean_cp = cp_href.strip().rstrip("/")
    clean_existing = existing_href.strip().rstrip("/")

    if clean_cp in FALLBACK_URLS and clean_existing and clean_existing not in FALLBACK_URLS:
        return existing_href

    if svg_name == "leetcode.svg":
        parsed = urllib.parse.urlparse(clean_cp)
        parts = [p for p in parsed.path.split("/") if p]
        if parsed.netloc.endswith("leetcode.com") and len(parts) == 1:
            return f"https://leetcode.com/u/{parts[0]}/"

    return cp_href


def sync_readme_platform_links(readme: str, cp_links: dict[str, str]) -> tuple[str, dict[str, str]]:
    """Update platform badge <a href="..."> links in README.md from Pri8899/CP/README.md."""
    applied: dict[str, str] = {}
    for svg_name, cp_href in cp_links.items():
        pattern = re.compile(
            rf'(<a\s+href=")([^"]+)("[^>]*>\s*<img\s+[^>]*src="[^"]*assets/{re.escape(svg_name)}"[^>]*></a>)'
        )

        def _replace(match: re.Match[str]) -> str:
            target = resolve_profile_url(svg_name, cp_href, match.group(2))
            applied[svg_name] = target
            return f"{match.group(1)}{target}{match.group(3)}"

        readme = pattern.sub(_replace, readme)
    return readme, applied


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
        dest_path = os.path.join(assets_dir, name)
        with open(dest_path, "w", encoding="utf-8", newline="\n") as f:
            f.write(svg)
        print(f"Synced {name} from CP@{short_sha}")

    cp_readme = http_get(f"https://raw.githubusercontent.com/{CP_REPO}/{sha}/README.md")
    cp_links = extract_cp_profile_links(cp_readme)

    readme_path = os.path.join(root_dir, "README.md")
    with open(readme_path, "r", encoding="utf-8") as f:
        readme = f.read()

    for name in SVG_FILES:
        pattern = rf"https://raw\.githubusercontent\.com/Pri8899/(?:CP|Pri8899)/(?:main|[0-9a-f]{{7,40}})/assets/{re.escape(name)}(?:\?v=[A-Za-z0-9_-]+)?"
        replacement = f"https://raw.githubusercontent.com/{CP_REPO}/{sha}/assets/{name}"
        readme = re.sub(pattern, replacement, readme)

    readme, applied_links = sync_readme_platform_links(readme, cp_links)

    with open(readme_path, "w", encoding="utf-8", newline="\n") as f:
        f.write(readme)
    print(f"Pinned README.md stats URLs & synced {len(applied_links)} platform links from CP@{short_sha}")


if __name__ == "__main__":
    main()
