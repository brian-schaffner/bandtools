# src/normalize.py
import unicodedata, re

_ws_re = re.compile(r"\s+")
_punct_re = re.compile(r"[^\w\s]")  # remove punctuation

def norm(s: str) -> str:
    s = unicodedata.normalize("NFKC", s).replace("\u00A0"," ")
    s = s.strip().casefold()
    s = _punct_re.sub(" ", s)
    s = _ws_re.sub(" ", s)
    return s