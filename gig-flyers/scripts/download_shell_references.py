#!/usr/bin/env python3
"""Download shell reference images from Wikimedia / legacy cache."""

from __future__ import annotations

import json
import sys
import time
import urllib.parse
import urllib.request
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from shell_references import BUNDLED_SHELL_REFS, SHELL_CACHE, SHELL_REFERENCES, registry_summary

UA = "bandtools-shell-ref/1.0 (educational research; github.com/brian-schaffner/bandtools)"


def _download(url: str, dest: Path, *, retries: int = 4) -> bool:
    dest.parent.mkdir(parents=True, exist_ok=True)
    for attempt in range(retries):
        req = urllib.request.Request(url, headers={"User-Agent": UA})
        try:
            with urllib.request.urlopen(req, timeout=120) as resp:
                data = resp.read()
        except Exception as exc:
            wait = 2 ** attempt
            print(f"  FAIL download (attempt {attempt + 1}/{retries}): {exc}")
            if attempt + 1 >= retries:
                return False
            time.sleep(wait)
            continue
        if len(data) < 5000:
            print(f"  FAIL tiny payload ({len(data)} bytes)")
            return False
        dest.write_bytes(data)
        return True
    return False


def _wikimedia_file_path_url(title: str) -> str | None:
    q = urllib.parse.urlencode(
        {
            "action": "query",
            "titles": title,
            "prop": "imageinfo",
            "iiprop": "url|size|mime",
            "format": "json",
        }
    )
    req = urllib.request.Request(f"https://commons.wikimedia.org/w/api.php?{q}", headers={"User-Agent": UA})
    try:
        with urllib.request.urlopen(req, timeout=30) as resp:
            pages = json.load(resp).get("query", {}).get("pages", {})
    except Exception as exc:
        print(f"  FAIL wikimedia API: {exc}")
        return None
    for pid, page in pages.items():
        if pid == "-1":
            return None
        ii = (page.get("imageinfo") or [{}])[0]
        return ii.get("url")
    return None


def ensure_shell_image(shell_id: str | None = None) -> dict[str, str]:
    """Download missing shell images. Returns status map shell_id -> ok|skip|fail."""
    SHELL_CACHE.mkdir(parents=True, exist_ok=True)
    targets = SHELL_REFERENCES
    if shell_id:
        targets = [s for s in SHELL_REFERENCES if s.id == shell_id]
        if not targets:
            raise SystemExit(f"Unknown shell: {shell_id}")

    status: dict[str, str] = {}
    for shell in targets:
        dest = SHELL_CACHE / shell.image_filename
        bundled = BUNDLED_SHELL_REFS / shell.image_filename
        if shell.has_image():
            status[shell.id] = "skip"
            print(f"skip {shell.id} ({shell.image_path()})")
            continue
        if bundled.is_file() and bundled.stat().st_size > 5000:
            dest.write_bytes(bundled.read_bytes())
            status[shell.id] = "ok"
            print(f"copy {shell.id} from bundled assets")
            continue

        url = shell.image_url
        if url and "Special:FilePath" in url:
            pass
        elif url:
            pass
        else:
            # Try legacy copy into shell cache
            legacy = shell.image_path()
            if legacy.is_file() and legacy.stat().st_size > 5000:
                dest.write_bytes(legacy.read_bytes())
                status[shell.id] = "ok"
                print(f"copy {shell.id} from legacy")
                continue
            status[shell.id] = "fail"
            print(f"fail {shell.id} (no url)")
            continue

        print(f"get  {shell.id} …")
        ok = _download(url, dest)
        if not ok and shell.image_url:
            # fallback via API title from filename
            title = f"File:{shell.image_filename.replace('_', ' ')}"
            api_url = _wikimedia_file_path_url(title)
            if api_url:
                time.sleep(1)
                ok = _download(api_url, dest)
        status[shell.id] = "ok" if ok else "fail"
        time.sleep(0.8)
    return status


def main() -> int:
    import argparse

    parser = argparse.ArgumentParser(description="Download shell reference poster images")
    parser.add_argument("--shell", default=None, help="Single shell id")
    parser.add_argument("--summary", action="store_true", help="Print registry summary JSON")
    args = parser.parse_args()

    if args.summary:
        print(json.dumps(registry_summary(), indent=2))
        return 0

    status = ensure_shell_image(args.shell)
    ok = sum(1 for v in status.values() if v == "ok")
    skip = sum(1 for v in status.values() if v == "skip")
    fail = sum(1 for v in status.values() if v == "fail")
    print(f"\nDone: {ok} downloaded, {skip} skipped, {fail} failed")
    print(json.dumps(registry_summary(), indent=2))
    return 0 if fail == 0 else 1


if __name__ == "__main__":
    raise SystemExit(main())
