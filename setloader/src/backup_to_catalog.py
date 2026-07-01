# src/backup_to_catalog.py
from __future__ import annotations
import argparse, hashlib, io, json, zipfile
from pathlib import Path
from typing import List, Dict, Any, Optional


def _read_zip_member(zf: zipfile.ZipFile, name: str) -> bytes:
    try:
        with zf.open(name, "r") as f:
            return f.read()
    except KeyError as e:
        raise FileNotFoundError(f"Missing '{name}' inside backup") from e


def _md5_hex(data: bytes) -> str:
    m = hashlib.md5()
    m.update(data)
    return m.hexdigest()


def load_json_loosely(text: str):
    """
    Try hard to load dataFile.txt even if it's not strict JSON:
    - Strip BOM
    - Try normal JSON
    - Try JSON Lines (one JSON object per line)
    - Try extracting the largest {...} or [...] block
    - Try removing trailing commas
    """
    import json, re

    s = text.lstrip("\ufeff")

    # 1) strict JSON
    try:
        return json.loads(s)
    except json.JSONDecodeError:
        pass

    # 2) JSON Lines
    lines = [ln.strip() for ln in s.splitlines() if ln.strip()]
    try:
        return [json.loads(ln) for ln in lines]
    except Exception:
        pass

    # 3) Extract biggest JSON object/array substring
    m = re.search(r"(\{.*\}|\[.*\])", s, flags=re.DOTALL)
    if m:
        inner = m.group(1)
        try:
            return json.loads(inner)
        except Exception:
            # 4) Remove trailing commas and retry
            inner2 = re.sub(r",(\s*[}\]])", r"\1", inner)
            try:
                return json.loads(inner2)
            except Exception:
                pass

    # 5) Last resort: remove trailing commas over whole text
    s2 = re.sub(r",(\s*[}\]])", r"\1", s)
    try:
        return json.loads(s2)
    except json.JSONDecodeError as e:
        raise ValueError(f"Invalid JSON in dataFile.txt: {e}")

def process_backup(backup_path: str | Path, out_path: Optional[str | Path] = None) -> Dict[str, Any]:
    """
    Extract titles from a backup file and (optionally) write them to a catalog text file.

    Returns a summary dict:
      {
        "ok": True/False,
        "titles": [..],           # list of strings (may be empty on failure)
        "written": "/path" | None,
        "count": int,
        "error": str | None
      }
    """
    backup_path = Path(backup_path)

    try:
        # Open the backup (ZIP with proprietary extension)
        with zipfile.ZipFile(backup_path, "r") as zf:
            data_bytes = _read_zip_member(zf, "dataFile.txt")
            hash_bytes = _read_zip_member(zf, "dataFile.hash")

        # Validate MD5
        expected = hash_bytes.decode("utf-8").strip()
        actual = _md5_hex(data_bytes)
        if expected.lower() != actual.lower():
            return {
                "ok": False,
                "titles": [],
                "written": None,
                "count": 0,
                "error": f"MD5 mismatch: expected {expected}, got {actual}",
            }




        # --- NEW: write fullcat.txt (raw JSON) ---
        fullcat_path = Path("etc/fullcat.txt")
        fullcat_path.parent.mkdir(parents=True, exist_ok=True)
        fullcat_path.write_bytes(data_bytes)
        # --- end NEW ---

        # Decode text (handle BOM)
        text = data_bytes.decode("utf-8-sig").strip()

        # --- Parse: JSON first, then JSONL fallback ---
        songs_items: List[Any] = []

        def collect_from_obj(obj: Any) -> None:
            # Accept {"songs":[...]}, or a top-level list of song dicts/strings
            if isinstance(obj, dict):
                if isinstance(obj.get("songs"), list):
                    songs_items.extend(obj["songs"])
                # Some catalogs may use other keys; add here if needed:
                # elif isinstance(obj.get("catalog"), list): songs_items.extend(obj["catalog"])
            elif isinstance(obj, list):
                songs_items.extend(obj)

        try:
            obj = json.loads(text)
            collect_from_obj(obj)
        except json.JSONDecodeError:
            # JSONL: parse each non-empty line
            for ln in (ln for ln in text.splitlines() if ln.strip()):
                try:
                    obj = json.loads(ln)
                    collect_from_obj(obj)
                except json.JSONDecodeError:
                    # ignore non-JSON lines in JSONL (be permissive)
                    continue

        # Extract titles
        titles: List[str] = []
        for s in songs_items:
            if isinstance(s, dict):
                # Prefer 'title', fallback to 'name'
                t = s.get("title") or s.get("name")
                if isinstance(t, str) and t.strip():
                    titles.append(t.strip())
            elif isinstance(s, str) and s.strip():
                titles.append(s.strip())

        written_path: Optional[Path] = None
        if out_path:
            outp = Path(out_path)
            outp.parent.mkdir(parents=True, exist_ok=True)
            outp.write_text("\n".join(titles) + ("\n" if titles else ""), encoding="utf-8")
            written_path = outp

        return {
            "ok": True,
            "titles": titles,
            "written": str(written_path) if written_path else None,
            "count": len(titles),
            "error": None,
        }

    except json.JSONDecodeError as e:
        return {"ok": False, "titles": [], "written": None, "count": 0, "error": f"Invalid JSON in dataFile.txt: {e}"}
    except FileNotFoundError as e:
        return {"ok": False, "titles": [], "written": None, "count": 0, "error": str(e)}
    except zipfile.BadZipFile:
        return {"ok": False, "titles": [], "written": None, "count": 0, "error": "Bad backup (not a ZIP)"}
    except Exception as e:
        return {"ok": False, "titles": [], "written": None, "count": 0, "error": f"{type(e).__name__}: {e}"}
    
def _cli() -> None:
    p = argparse.ArgumentParser(description="Extract catalog.txt from backup file")
    p.add_argument("--in", dest="inp", required=True, help="Path to backup file (.bkp)")
    p.add_argument("--out", dest="out", required=True, help="Path to write catalog.txt")
    args = p.parse_args()

    res = process_backup(args.inp, args.out)
    if not res["ok"]:
        raise SystemExit(res["error"])
    print(f"Wrote {res['count']} titles to {res['written']}")


if __name__ == "__main__":
    _cli()