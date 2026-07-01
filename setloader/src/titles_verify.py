#!/usr/bin/env python3
"""
titles_verify.py — Map, validate, and normalize song titles against a catalog.

This version saves ALL interactive choices into title_mapper.json:
- Picking a suggestion → map variant → chosen suggestion
- Keep-as-is → map variant → itself
- Drop → map variant → "" (empty string means dropped)
"""
import argparse, json, os, sys, re
from typing import List, Dict, Tuple
import difflib
try:
    from .normalize import norm
except ImportError:
    from normalize import norm

def read_lines(path: str) -> List[str]:
    with open(path, 'r', encoding='utf-8') as f:
        return [ln.strip() for ln in f if ln.strip()]

def load_mapper(path: str) -> Dict[str, str]:
    if not path or not os.path.exists(path):
        return {}
    with open(path, 'r', encoding='utf-8') as f:
        data = json.load(f)
    norm = {}
    for k, v in data.items():
        norm[k.casefold()] = v.strip()
    return norm

def save_mapper(path: str, mapper_norm: Dict[str, str]):
    if not path:
        return
    out = {k: v for k, v in mapper_norm.items()}
    with open(path, 'w', encoding='utf-8') as f:
        json.dump(out, f, ensure_ascii=False, indent=2)

def normalize_key(s: str) -> str:
    s = s.strip()
    s = re.sub(r'\s+', ' ', s)
    s = re.sub(r'[“”"\'`’]', '', s)
    s = s.replace('&', 'and')
    s = re.sub(r'\(feat[^\)]*\)', '', s, flags=re.I)
    s = re.sub(r'[^A-Za-z0-9 ]+', ' ', s)
    s = re.sub(r'\s+', ' ', s).strip()
    return s.casefold()

def build_catalog_index(catalog: List[str]) -> Tuple[Dict[str, str], List[str]]:
    exact = {}
    canon_list = []
    for title in catalog:
        canon = title.strip()
        if not canon: 
            continue
        nk = normalize_key(canon)
        exact[nk] = canon
        canon_list.append(canon)
    return exact, canon_list

def map_titles(titles: List[str], mapper_norm: Dict[str, str]) -> List[str]:
    out = []
    for t in titles:
        mapped = mapper_norm.get(t.casefold(), t)
        if mapped == "" or mapped == "__DROP__":
            continue  # dropped
        out.append(mapped)
    return out

def best_suggestions(query: str, choices: List[str], n: int = 5) -> List[Tuple[str, float]]:
    scores = []
    for c in choices:
        r = difflib.SequenceMatcher(a=normalize_key(query), b=normalize_key(c)).ratio()
        scores.append((c, r))
    scores.sort(key=lambda x: x[1], reverse=True)
    return scores[:n]

def verify_titles(titles: List[str], exact: Dict[str, str], canon_list: List[str], threshold: float, interactive: bool, mapper_norm: Dict[str, str]) -> Tuple[List[str], List[Tuple[str, List[Tuple[str, float]]]]]:
    verified = []
    unresolved = []
    for t in titles:
        nk = normalize_key(t)
        if nk in exact:
            verified.append(exact[nk])
            # Persist identity mapping to avoid future OCR variants prompting
            mapper_norm.setdefault(t.casefold(), exact[nk])
            continue
        sugg = best_suggestions(t, canon_list, n=5)
        if not interactive:
            if sugg and sugg[0][1] >= threshold:
                verified.append(sugg[0][0])
            else:
                unresolved.append((t, sugg))
            continue
        # interactive
        print(f"\nUnmatched: '{t}'")
        for i, (cand, score) in enumerate(sugg, 1):
            print(f"  {i}) {cand}  [{score:.2f}]")
        print("  K) keep as-is (will remember)")
        print("  M) map this variant -> canonical (enter target)")
        print("  D) drop (will remember)")
        ans = input("Choose [1-5/K/M/D]: ").strip().lower()
        if ans in [str(i) for i in range(1, min(5, len(sugg)) + 1)]:
            pick = sugg[int(ans)-1][0]
            # Save mapping raw -> chosen suggestion
            mapper_norm[t.casefold()] = pick
            verified.append(pick)
        elif ans == 'm':
            target = input("  Map to (must match catalog exactly; leave blank to cancel): ").strip()
            if target:
                mapper_norm[t.casefold()] = target
                verified.append(target)
            else:
                unresolved.append((t, sugg))
        elif ans == 'd':
            # Save a sentinel empty string mapping to indicate drop in future runs
            mapper_norm[t.casefold()] = ""
            # skip adding to verified
            continue
        else:
            # Keep as-is and remember identity mapping
            mapper_norm[t.casefold()] = t
            verified.append(t)
    return verified, unresolved

def main():
    p = argparse.ArgumentParser(description="Map, validate, and normalize titles against a catalog.")
    p.add_argument("--in", dest="inp", required=True, help="Input .txt of titles (one per line)")
    p.add_argument("--catalog", required=True, help="catalog.txt (one canonical title per line)")
    p.add_argument("--out", required=True, help="Output .txt of verified/normalized titles")
    p.add_argument("--mapper", default=None, help="title_mapper.json (case-insensitive keys)")
    p.add_argument("--report", default=None, help="Optional report of unresolved lines")
    p.add_argument("--threshold", type=float, default=0.88, help="Auto-accept fuzzy match >= threshold (0..1)")
    p.add_argument("--interactive", action="store_true", help="Prompt to resolve unknowns; updates mapper with ALL choices")
    args = p.parse_args()

    titles = read_lines(args.inp)
    catalog = read_lines(args.catalog)

    mapper_norm = load_mapper(args.mapper) if args.mapper else {}

    exact, canon_list = build_catalog_index(catalog)
    mapped = map_titles(titles, mapper_norm)
    verified, unresolved = verify_titles(mapped, exact, canon_list, args.threshold, args.interactive, mapper_norm)

    with open(args.out, 'w', encoding='utf-8') as f:
        for t in verified:
            f.write(t + "\n")

    if args.report:
        with open(args.report, 'w', encoding='utf-8') as f:
            for raw, sugg in unresolved:
                f.write(f"UNRESOLVED: {raw}\n")
                for cand, sc in sugg:
                    f.write(f"  SUGGEST: {cand} [{sc:.2f}]\n")
                f.write("\n")

    if args.interactive and args.mapper:
        save_mapper(args.mapper, mapper_norm)

    print(f"Wrote {len(verified)} titles to {args.out}")
    if unresolved:
        print(f"{len(unresolved)} unresolved; {'see ' + args.report if args.report else 'rerun with --interactive to resolve.'}")

if __name__ == "__main__":
    main()
