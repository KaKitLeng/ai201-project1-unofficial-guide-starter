"""
ingest.py - load ./documents/, clean per source type, and chunk for the RAG pipeline.

Milestone 3 (ingestion + chunking only; no embedding/retrieval yet). Three document
shapes are handled:

    * listing  - Apartments.com reader-mode copy-paste (legacy202.txt, maywood.txt, ...)
    * legal    - the Urbana Landlord-Tenant Ordinance (occl.txt)
    * reddit   - r/UIUC threads with SOURCE/DATE/TITLE headers (reddit_uiuc_*.txt)

Chunking is a hand-rolled, RecursiveCharacterTextSplitter-style splitter: split on a
priority of separators (paragraph -> line -> sentence -> word -> char), only falling to a
finer separator when a piece exceeds the size cap, then merge adjacent pieces up toward
the target size with a small overlap. Short records (most reviews/listing facts) are
already under the cap and pass through as one intact chunk.

Run:  python ingest.py   (prints the inspection report)

No dependencies beyond the standard library.
"""

import os
import re
import sys
import glob
import html
import random

DOC_DIR = "documents"
CHUNK_SIZE = 500       # target characters (~110-140 tokens; safely < MiniLM's 256 limit)
CHUNK_OVERLAP = 75     # characters; applied only when a document is actually split
SEPARATORS = ["\n\n", "\n", ". ", " ", ""]   # paragraph -> line -> sentence -> word -> char

# filename stem -> display building name (the 8 listings)
LISTING_BUILDING = {
    "legacy202": "Legacy202", "the_linc": "The Linc", "maywood": "Maywood",
    "the_alcove": "The Alcove", "202_e_green_st": "202 E Green by Bankier",
    "pacifica_on_green": "Pacifica on Green", "campus_oak": "Campus Oaks",
    "alley_lofts": "Alley Lofts",
}
# reddit thread id -> building (pairing from planning.md); None = general thread
REDDIT_BUILDING = {
    "16xycks": "Legacy202", "140prcv": "The Linc", "ipx5hh": "Maywood",
    "1bh3d58": "The Alcove", "1o6pln5": "Pacifica on Green",
    "hnsu5a": "Campus Oaks", "166pc1v": None,   # "sophomore recommendations" = breadth
}

# first street-address line in a listing; everything above it is nav/contact boilerplate
ADDR_RE = re.compile(r"^\d+\s+.*,\s+(Champaign|Urbana),\s+IL\s+\d{5}")
# leading breadcrumb nav lines in occl.txt
BREADCRUMB = {"Breadcrumb", "Home", "Rights & Responsibilities", "Tenant Rights"}
# strings that must never survive into a chunk (regression guard)
BOILERPLATE_MARKERS = ["&amp;", "Nearby Apartments", "Report an Issue", "Try These Popular"]


# --------------------------------------------------------------------------- #
# cleaning
# --------------------------------------------------------------------------- #
def shared_clean(text):
    """Cleaning applied to every document, last: unescape HTML entities, strip trailing
    whitespace per line, collapse 3+ blank lines to one."""
    text = text.replace("\r\n", "\n").replace("\r", "\n")
    text = html.unescape(text)                       # &amp; &gt; &lt; -> & > <
    text = "\n".join(line.rstrip() for line in text.split("\n"))
    text = re.sub(r"\n\s*\n\s*\n+", "\n\n", text)    # collapse 3+ newlines -> blank line
    return text.strip()


# Decor/geo sections to drop, as (start header, resume header) pairs. Each runs from its
# start header until the next resume header (which is itself kept). These two boundaries
# are the only ones present in all 8 listings -- the neighborhood header in between varies
# ("City - X", "Neighborhood", or a "Welcome to ..." blurb), so we bracket the whole geo
# tail by Location -> Reviews rather than matching each sub-section.
DROP_SECTIONS = [
    ("Matterport 3D Tours", "About "),   # interior decor descriptions -> resume at About blurb
    ("Location", "Reviews for "),        # city blurb, Average Prices, Education/Schools,
                                         # Transportation/scores, Points of Interest -> resume at Reviews
]


def _drop_sections(lines):
    """Drop the decor/geo sections in DROP_SECTIONS. State machine: a start header begins
    dropping (header included); the matching resume header ends it (header kept)."""
    kept, resume = [], None
    for ln in lines:
        s = ln.strip()
        if resume is None:
            start = next((r for start, r in DROP_SECTIONS if s == start), None)
            if start is not None:
                resume = start                       # now dropping until this resume header
            else:
                kept.append(ln)
        elif s.startswith(resume):                   # found the resume header -> keep it on
            resume = None
            kept.append(ln)
        # else: still inside a dropped section -> skip
    return kept


# Page-chrome / UI lines with no factual content (exact match after strip).
NAV_NOISE = {
    "Property Website", "Property Management Company Logo", "Read More",
    "filter results by bedrooms", "Verified Listing", "View All Hours",
    "Be the First to Rate & Review", "Be the First to Rate & Review!",
    "Tour Floor Plan", "Matterport 3D Tour",
}
NAV_NOISE_PREFIX = ("PricingFees and Policies", "Cost Calculator:")
NAV_NOISE_RE = re.compile(r"^(View .*Floor Plan Details|\d+ Available units?)$")

# The per-unit "Unit Details" table repeats the plan's price/sqft as bare values and
# column labels for every available unit. These tokens identify its lines; we drop the
# whole block but preserve the availability date(s), keeping the plan-level facts above it.
TABLE_TOKENS = {"Unit", "Base Price", "Sq Ft", "Availability", "Unit Details",
                "Private", "price", "square feet"}


def _is_table_line(s):
    return (s in TABLE_TOKENS or s.startswith("availibility")
            or bool(re.fullmatch(r"\$[\d,]+", s)) or bool(re.fullmatch(r"[\d,]+", s)))


def _trim_listing_noise(lines):
    """Drop floor-plan UI scaffolding (the Unit Details table, keeping availability dates)
    and residual page-nav lines. Keeps each plan's name, rent, beds/baths, and sqft."""
    out, i, n = [], 0, len(lines)
    while i < n:
        s = lines[i].strip()
        if s == "Unit" and i + 1 < n and lines[i + 1].strip() == "Base Price":
            while i < n and _is_table_line(lines[i].strip()):
                if lines[i].strip().startswith("availibility"):
                    out.append(lines[i])             # preserve availability date(s)
                i += 1
            continue
        if s in NAV_NOISE or s.startswith(NAV_NOISE_PREFIX) or NAV_NOISE_RE.match(s):
            i += 1
            continue
        out.append(lines[i])
        i += 1
    return out


def clean_listing(raw):
    """Strip Apartments.com boilerplate. Returns (text, cut_lineno, cut_text) where the
    cut line is the street address we anchored on (everything above it is dropped)."""
    lines = raw.splitlines()

    # 1. drop the nav/contact header: keep from the first street-address line onward.
    anchor = next((i for i, ln in enumerate(lines) if ADDR_RE.match(ln)), 0)
    cut_lineno, cut_text = anchor + 1, (lines[anchor].strip() if lines else "")
    lines = lines[anchor:]

    # 2. drop the footer: everything from "Report an Issue" / "Try These Popular..." on.
    footer = next(
        (i for i, ln in enumerate(lines)
         if ln.strip().startswith("Report an Issue")
         or ln.strip() == "Try These Popular Nearby Searches"),
        None,
    )
    if footer is not None:
        lines = lines[:footer]

    # 3. drop decor (Matterport) and the geo tail (Location -> Reviews), keeping rent/
    #    floor plans, fees, details, property info, amenities, the About blurb, and the FAQ.
    lines = _drop_sections(lines)

    # 4. trim floor-plan UI scaffolding (Unit Details table) and residual page-nav noise.
    lines = _trim_listing_noise(lines)

    # 5. remove the "Nearby Apartments" block (other buildings' names/rents -> wrong-source
    #    attribution). It runs from that header up to the FAQ header; no-op if absent.
    near = next((i for i, ln in enumerate(lines) if ln.strip() == "Nearby Apartments"), None)
    if near is not None:
        end = next(
            (j for j in range(near + 1, len(lines))
             if lines[j].strip() == "Frequently Asked Questions"),
            len(lines),                              # fallback: to end (footer already cut)
        )
        lines = lines[:near] + lines[end:]

    return "\n".join(lines), cut_lineno, cut_text


def clean_legal(raw):
    """Strip the leading breadcrumb nav prefix from occl.txt."""
    lines = raw.splitlines()
    i = 0
    while i < len(lines) and lines[i].strip() in BREADCRUMB:
        i += 1
    return "\n".join(lines[i:])


def parse_reddit(raw):
    """Pull SOURCE/DATE/TITLE into metadata and return (body_text, metadata). Header
    values are metadata, not chunk text."""
    lines = raw.splitlines()
    meta = {"subreddit": None, "date": None, "title": None}
    body_start = 0
    for i, line in enumerate(lines[:5]):
        for key, pat in (("subreddit", r"^SOURCE:\s*(.*)$"),
                         ("date", r"^DATE:\s*(.*)$"),
                         ("title", r"^TITLE:\s*(.*)$")):
            m = re.match(pat, line)
            if m:
                meta[key] = m.group(1).strip()
                body_start = i + 1
                break
    return "\n".join(lines[body_start:]), meta


# --------------------------------------------------------------------------- #
# loading
# --------------------------------------------------------------------------- #
def load_documents(verbose=True):
    """Read ./documents/, apply type-specific cleaning, and return a list of
    {"text": ..., "metadata": {...}} dicts."""
    docs, cut_report = [], []
    for path in sorted(glob.glob(os.path.join(DOC_DIR, "*.txt"))):
        source_file = os.path.basename(path)
        stem = source_file[:-4] if source_file.endswith(".txt") else source_file
        with open(path, encoding="utf-8") as f:
            raw = f.read()

        if stem.startswith("reddit_"):
            tid = stem.split("_")[-1]
            body, rmeta = parse_reddit(raw)
            text = shared_clean(body)
            meta = {"source_file": source_file, "source_type": "reddit",
                    "building": REDDIT_BUILDING.get(tid),
                    "date": rmeta["date"], "subreddit": rmeta["subreddit"],
                    "title": rmeta["title"]}
        elif stem.startswith("occl"):
            text = shared_clean(clean_legal(raw))
            meta = {"source_file": source_file, "source_type": "legal",
                    "building": None, "date": None, "subreddit": None, "title": None}
        else:
            cleaned, cut_lineno, cut_text = clean_listing(raw)
            text = shared_clean(cleaned)
            meta = {"source_file": source_file, "source_type": "listing",
                    "building": LISTING_BUILDING.get(stem),
                    "date": None, "subreddit": None, "title": None}
            cut_report.append((source_file, cut_lineno, cut_text))

        docs.append({"text": text, "metadata": meta})

    if verbose and cut_report:
        print("Listing nav-header cut points (everything above this line is dropped):")
        for sf, n, t in cut_report:
            print(f"  {sf:<22} line {n:>3}: {t!r}")
        print()
    return docs


# --------------------------------------------------------------------------- #
# chunking (hand-rolled recursive splitter)
# --------------------------------------------------------------------------- #
def _split(text, separators, size):
    """Recursively split text into pieces each <= size, preferring earlier (coarser)
    separators and only falling to a finer one when a piece is still too big."""
    if len(text) <= size:
        return [text]
    sep, remaining = separators[0], separators[1:]
    if sep == "":                                    # finest fallback: hard char split
        return [text[i:i + size] for i in range(0, len(text), size)]

    raw = text.split(sep)
    parts = [p + sep for p in raw[:-1]] + raw[-1:]   # re-attach sep so no chars are lost
    pieces = []
    for p in parts:
        if not p:
            continue
        pieces.extend([p] if len(p) <= size else _split(p, remaining, size))
    return pieces


def _merge(pieces, size, overlap):
    """Merge adjacent pieces up toward `size`, seeding each new chunk with the last
    `overlap` characters of the one before it. Returns the final list of chunk strings."""
    chunks, current = [], ""
    for p in pieces:
        if current and len(current) + len(p) > size:
            chunks.append(current.strip())
            tail = current[-overlap:] if overlap else ""
            snap = re.search(r"\s", tail)            # snap overlap to next word boundary
            current = (tail[snap.end():] if snap else tail) + p
        else:
            current += p
    if current.strip():
        chunks.append(current.strip())
    return chunks


def chunk_text(text, size=CHUNK_SIZE, overlap=CHUNK_OVERLAP):
    """Recursive, content-aware chunking. Text already under `size` returns as one chunk
    (no overlap added); longer text is split on natural boundaries and merged."""
    text = text.strip()
    if not text:
        return []
    return _merge(_split(text, SEPARATORS, size), size, overlap)


def build_chunks():
    """Load + clean + chunk everything, copying doc metadata onto each chunk plus a
    per-document chunk_index."""
    chunks = []
    for doc in load_documents():
        for i, piece in enumerate(chunk_text(doc["text"])):
            chunks.append({"text": piece, "metadata": dict(doc["metadata"], chunk_index=i)})
    return chunks


# --------------------------------------------------------------------------- #
# inspection
# --------------------------------------------------------------------------- #
def assert_clean(chunks):
    """Regression guard: no boilerplate marker may survive into any chunk."""
    for c in chunks:
        for marker in BOILERPLATE_MARKERS:
            assert marker not in c["text"], (
                f"boilerplate {marker!r} leaked into {c['metadata']['source_file']} "
                f"chunk {c['metadata']['chunk_index']}"
            )


def test_occl_merge():
    """Exercise _merge via chunk_text on the long OCCL document: report chunk-length
    distribution, confirm the size cap holds, and that the function terminates."""
    occl = next(d for d in load_documents(verbose=False)
                if d["metadata"]["source_file"] == "occl.txt")["text"]
    chunks = chunk_text(occl)                         # returning at all proves termination
    lengths = [len(c) for c in chunks]
    cap = CHUNK_SIZE + CHUNK_OVERLAP
    over = [n for n in lengths if n > cap]

    print("OCCL _merge test:")
    print(f"  source length           : {len(occl)} chars")
    print(f"  chunks produced         : {len(chunks)}  (function returned -> terminates)")
    print(f"  chunk length min/avg/max: {min(lengths)} / {sum(lengths) // len(lengths)} / {max(lengths)}")
    print(f"  chunks over {cap}-char cap : {len(over)}  -> {'OK' if not over else over}")
    if len(chunks) > 1:                              # show the overlap _merge produced
        print(f"  overlap demo, chunk0 tail : ...{chunks[0][-60:]!r}")
        print(f"  overlap demo, chunk1 head : {chunks[1][:60]!r}...")
    print()


def show_counts(chunks):
    """Print chunk count per source file, grouped by type."""
    counts, types = {}, {}
    for c in chunks:
        sf = c["metadata"]["source_file"]
        counts[sf] = counts.get(sf, 0) + 1
        types[sf] = c["metadata"]["source_type"]
    print("Chunks per file:")
    for t in ("listing", "legal", "reddit"):
        for sf in sorted(f for f in counts if types[f] == t):
            print(f"  [{t:<7}] {sf:<26} {counts[sf]:>3}")
    print()


def show_samples(chunks, n_random=2):
    """Print representative chunks: one listing, one legal, one reddit, plus n_random."""
    by_type = {}
    for c in chunks:
        by_type.setdefault(c["metadata"]["source_type"], []).append(c)

    random.seed(0)                                   # reproducible selection
    picks = []
    for t in ("listing", "legal", "reddit"):
        if by_type.get(t):
            picks.append((f"{t} (representative)", random.choice(by_type[t])))
    for _ in range(n_random):
        picks.append(("random", random.choice(chunks)))

    print("=" * 78)
    print("REPRESENTATIVE CHUNKS")
    print("=" * 78)
    for label, c in picks:
        m = c["metadata"]
        print(f"\n--- {label} | {m['source_file']} | chunk {m['chunk_index']} "
              f"| {len(c['text'])} chars ---")
        print("metadata:", m)
        print(c["text"])


def main():
    # documents/ is UTF-8 (curly apostrophes etc.); make the console preview match so
    # smart quotes render instead of showing as a replacement glyph on Windows.
    try:
        sys.stdout.reconfigure(encoding="utf-8")
    except (AttributeError, OSError):
        pass

    chunks = build_chunks()
    print(f"TOTAL CHUNKS: {len(chunks)}\n")

    assert_clean(chunks)
    print("Boilerplate assertions passed "
          "(no &amp; / Nearby Apartments / Report an Issue / Try These Popular).\n")

    show_counts(chunks)
    test_occl_merge()
    show_samples(chunks)


if __name__ == "__main__":
    main()
