# src/inspect_backup.py
import zipfile, json, hashlib, sys
from pathlib import Path

def md5_hex(b: bytes) -> str:
    h=hashlib.md5(); h.update(b); return h.hexdigest()

def main(p):
    p = Path(p)
    with zipfile.ZipFile(p, "r") as z:
        data = z.read("dataFile.txt")
        got = md5_hex(data)
        try:
            exp = z.read("dataFile.hash").decode().strip()
            print(f"MD5: expected={exp} got={got} match={exp.lower()==got.lower()}")
        except KeyError:
            print("MD5: dataFile.hash MISSING")
        s = data.decode("utf-8-sig")

    # try strict JSON first
    try:
        obj = json.loads(s)
        print(f"Top-level type: {type(obj).__name__}")
        if isinstance(obj, dict):
            print("Dict keys:", list(obj.keys())[:30])
            # peek into likely arrays
            for k,v in obj.items():
                if isinstance(v, list) and v and isinstance(v[0], dict):
                    print(f"Sample list '{k}' length={len(v)}; item keys:", list(v[0].keys())[:20])
        elif isinstance(obj, list):
            print(f"List length: {len(obj)}")
            if obj and isinstance(obj[0], dict):
                print("Item keys:", list(obj[0].keys())[:20])
        return
    except json.JSONDecodeError as e:
        print("Strict JSON failed:", e)

    # JSON Lines fallback
    lines = [ln for ln in s.splitlines() if ln.strip()]
    ok, items = True, []
    for ln in lines:
        try: items.append(json.loads(ln))
        except Exception: ok=False; break
    if ok:
        print(f"Detected JSONL with {len(items)} lines")
        if items and isinstance(items[0], dict):
            print("First line keys:", list(items[0].keys())[:20])
    else:
        print("Could not parse as JSON or JSONL. Dumping first 400 chars:")
        print(s[:400])

if __name__ == "__main__":
    if len(sys.argv)<2:
        print("Usage: python src/inspect_backup.py <backup.bkp>")
        sys.exit(1)
    main(sys.argv[1])