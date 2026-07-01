# src/ai_reader.py
import os, sys, re
from pathlib import Path
from openai import OpenAI

"""
Usage: python src/ai_reader.py <pdf_file> <out_txt>
Writes plain-text titles (one per line) to <out_txt>.
Requires env OPENAI_API_KEY.
"""

def post_filter(lines):
    out = []
    for s in lines:
        t = s.strip()
        if not t:
            continue

        # obvious junk (headers, times, “min/break”, long runs of junk chars)
        junky = (
            re.search(r"\b(min|break|set|^\d+\s*-\s*\d+|^\d+\s*mins?)\b", t, re.I)
            or re.search(r"\b(AM|PM|\d{1,2}:\d{2})\b", t)
            or re.search(r"[|_•·~`]{2,}", t)
        )
        if junky:
            continue

        # strip list indices & leading bullets/punctuation: "7. ", "12) ", "- ", etc.
        t = re.sub(r"^\s*(\d{1,3}[.)]\s*)", "", t)         # numbered list prefix
        t = re.sub(r"^[\s\-\*\.\,;:\|_»«]+", "", t)        # bullet/ punctuation

        if not t:
            continue

        # If the whole line is ONLY a list number like "7" or "12." or "3)"
        if re.fullmatch(r"\d{1,3}[.)]?", t):
            continue

        # keep numeric titles like "1999" (>=2 digits), while filtering real noise
        letters = sum(c.isalpha() for c in t)
        digits  = sum(c.isdigit() for c in t)
        too_long  = len(t) > 60
        # noisy ONLY if it has too few letters AND not a plausible numeric title
        too_noisy = (letters < 3) and not (digits >= 2 and letters == 0)

        if too_long or too_noisy:
            continue

        out.append(t)

    # de-dupe, preserve order
    seen = set()
    uniq = []
    for t in out:
        k = t.casefold()
        if k not in seen:
            seen.add(k)
            uniq.append(t)
    return uniq

def main():
    if len(sys.argv) < 3:
        print("Usage: python src/ai_reader.py <pdf_file> <out_txt>")
        sys.exit(2)

    pdf_path = sys.argv[1]
    out_txt  = sys.argv[2]

    client = OpenAI()  # needs OPENAI_API_KEY
    with open(pdf_path, "rb") as f:
        up = client.files.create(file=f, purpose="user_data")

    prompt = (
        "Extract ONLY the song titles from ALL sets in the PDF. "
        "Output plain text, one title per line. "
        "No section headers, times, keys, or keysigs. No numbering."
    )

    resp = client.responses.create(
        model="gpt-5",
        input=[{
            "role": "user",
            "content": [
                {"type": "input_file", "file_id": up.id},
                {"type": "input_text", "text": prompt},
            ],
        }],
    )
    text = resp.output_text.strip()
    lines = [l for l in text.splitlines()]
    lines = post_filter(lines)

    Path(out_txt).parent.mkdir(parents=True, exist_ok=True)
    Path(out_txt).write_text("\n".join(lines) + "\n", encoding="utf-8")
    print(f"AI extracted {len(lines)} titles → {out_txt}")

def evaluate_pdf_for_song_count(pdf_file: Path) -> dict:
    """Enhanced AI evaluation for accurate song counting"""
    try:
        client = OpenAI()
        
        with open(pdf_file, "rb") as f:
            up = client.files.create(file=f, purpose="user_data")
        
        prompt = """
You are an expert at analyzing setlists and song lists. Analyze this PDF and provide an accurate count of unique songs.

CRITICAL RULES:
1. Count ONLY actual song titles, not headers, timing info, or section breaks
2. Ignore "SET 1", "SET 2", timing like "7-8:30", "20 min break", etc.
3. Count each unique song only once, even if it appears multiple times
4. Ignore musical keys like "– F", "– G", etc.
5. Ignore "Detune" or other non-song items
6. Be very precise - this is for a production system

Provide your analysis in this exact format:
SONG_COUNT: [number]
SAMPLE_TITLES: [comma-separated list of 5-10 song titles]
"""
        
        resp = client.chat.completions.create(
            model="gpt-4o",
            messages=[{
                "role": "user", 
                "content": [
                    {"type": "input_file", "file_id": up.id},
                    {"type": "input_text", "text": prompt}
                ]
            }],
            temperature=0.1
        )
        
        result_text = resp.choices[0].message.content
        
        # Parse the response
        song_count = None
        sample_titles = []
        
        for line in result_text.split('\n'):
            if line.startswith('SONG_COUNT:'):
                try:
                    song_count = int(line.split(':', 1)[1].strip())
                except:
                    pass
            elif line.startswith('SAMPLE_TITLES:'):
                try:
                    sample_titles = [t.strip() for t in line.split(':', 1)[1].split(',')]
                except:
                    pass
        
        return {
            'song_count': song_count or 0,
            'sample_titles': sample_titles[:10]
        }
        
    except Exception as e:
        print(f"AI evaluation error: {e}")
        return {'song_count': 0, 'sample_titles': []}

if __name__ == "__main__":
    main()