"""Update check against the project's GitHub releases (stdlib only)."""

import json
import os
import re
import time
import urllib.error
import urllib.request

from . import __version__

REPO = "greedgoddess/kohaku-tabletd"
REPO_URL = f"https://github.com/{REPO}"
RELEASES_URL = REPO_URL + "/releases/latest"
API_URL = f"https://api.github.com/repos/{REPO}/releases/latest"


# [doc:upd-version]
def parse_version(text):
    """"v0.3.0" / "0.3.0-rc1" -> (0, 3, 0)."""
    numbers = re.findall(r"\d+", text.strip().lstrip("vV").split("-")[0])
    return tuple(int(n) for n in numbers[:3]) or (0,)


def is_newer(latest, current=__version__):
    return parse_version(latest) > parse_version(current)


# [doc:upd-fetch]
def fetch_latest(opener=urllib.request.urlopen, timeout=15):
    """(version, page_url) of the latest release, or None if none is published."""
    request = urllib.request.Request(API_URL, headers={
        "Accept": "application/vnd.github+json",
        "User-Agent": f"kohaku-tabletd/{__version__}",
    })
    try:
        with opener(request, timeout=timeout) as response:
            data = json.load(response)
    except urllib.error.HTTPError as exc:
        if exc.code == 404:
            return None
        raise
    tag = data.get("tag_name") or ""
    if not tag:
        raise ValueError("latest release has no tag")
    return tag.lstrip("vV"), data.get("html_url") or RELEASES_URL


# [doc:upd-check]
def check(opener=urllib.request.urlopen):
    """One check as a result dict; network and parse errors become state "error"."""
    result = {"latest": "", "url": RELEASES_URL, "checked": int(time.time() * 1000), "error": ""}
    try:
        latest = fetch_latest(opener)
    except (OSError, ValueError) as exc:
        return {**result, "state": "error", "error": str(getattr(exc, "reason", exc))}
    if latest is None:
        return {**result, "state": "no-release", "url": REPO_URL}
    version, url = latest
    return {**result, "state": "available" if is_newer(version) else "up-to-date",
            "latest": version, "url": url}


# [doc:upd-state]
def state_path():
    base = os.environ.get("XDG_STATE_HOME") or os.path.expanduser("~/.local/state")
    return os.path.join(base, "kohaku-tabletd", "update.json")


def load_state(path=None):
    try:
        with open(path or state_path()) as fh:
            data = json.load(fh)
    except (OSError, ValueError):
        return {}
    return data if isinstance(data, dict) else {}


def save_state(data, path=None):
    path = path or state_path()
    os.makedirs(os.path.dirname(path), exist_ok=True)
    tmp = path + ".tmp"
    with open(tmp, "w") as fh:
        json.dump(data, fh)
    os.replace(tmp, path)
