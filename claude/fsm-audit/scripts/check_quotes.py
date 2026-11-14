#!/usr/bin/env python3
"""check_quotes.py: mechanically verify that every cited evidence location and quote exists.

Models invent line numbers and quotes. This check runs before any meaning check.

It verifies these citations anywhere in the JSON:
  1. quote items: objects with "file", "line" and "quote" (evidence of findings). The file must exist
     inside --root, the line must exist, and the quoted text must appear at the line or within --window
     lines of it (whitespace-normalized, case-sensitive). The result says whether it was exact or how
     many lines off it was.
  2. location strings: values of keys "where" and "evidence" shaped like "path/to/file.ext:123" or
     "path:12-30" (writers rows, table cells). If the same object also has a "quote", it is checked like
     a quote item. Without a quote only the file and line range are checked, and a warning is raised when the
     object claims provenance "quoted" or when the line is blank, a comment, a docstring or an import.

Input: a report JSON (references/report-schema.md), or any JSON with such items.
Output: JSON on stdout. By default only failures and counts are listed; --verbose lists every item.
Problems also go to stderr, one line each.

Example:
  check_quotes.py report.json --root /path/to/audited/repo

Exit codes: 0 all found; 1 at least one failed (with --strict: or warned); 2 bad arguments or input.
Read-only: opens files under --root only and refuses paths that escape it.
"""
import argparse
import json
import os
import re
import sys

LOC = re.compile(r"^\s*([A-Za-z0-9_./\\@+~-][^\s:]*?):(\d+)(?:-(\d+))?\s*$")


def collect(node, path="$", found=None, owner=None):
    """Find citations: quote items, location strings, and objects claiming provenance 'quoted' with no quote."""
    if found is None:
        found = []
    if isinstance(node, dict):
        if "file" in node and "quote" in node:
            found.append(("quote", path, owner, node))
            return found
        oid = node.get("id") or owner
        loc_key = next((k for k in ("where", "evidence") if isinstance(node.get(k), str) and LOC.match(node[k])), None)
        if loc_key:
            m = LOC.match(node[loc_key])
            base = {"file": m.group(1), "line": int(m.group(2)), "end": int(m.group(3) or m.group(2))}
            if isinstance(node.get("quote"), str) and node["quote"].strip():
                found.append(("quote", "%s.%s" % (path, loc_key), oid, {"file": base["file"], "line": base["line"], "quote": node["quote"]}))
            else:
                base["claims_quoted"] = str(node.get("provenance", "")).lower() == "quoted"
                found.append(("loc", "%s.%s" % (path, loc_key), oid, base))
        for k, v in node.items():
            if k in ("where", "evidence") and isinstance(v, str) and LOC.match(v):
                continue
            collect(v, "%s.%s" % (path, k), found, oid)
    elif isinstance(node, list):
        for i, v in enumerate(node):
            collect(v, "%s[%d]" % (path, i), found, owner)
    return found


def norm(s):
    return re.sub(r"\s+", " ", s).strip()


def read_lines(root, rel):
    full = os.path.realpath(os.path.join(root, rel))
    if not (full == root or full.startswith(root + os.sep)):
        return None, "path_outside_root", "refused: path escapes --root"
    if not os.path.isfile(full):
        return None, "file_missing", "file does not exist under --root"
    try:
        with open(full, "r", encoding="utf-8", errors="replace") as fh:
            return fh.read().splitlines(), None, None
    except OSError as e:
        return None, "file_unreadable", str(e)


def check_quote(root, item, window):
    quote = norm(str(item.get("quote", "")))
    try:
        line = int(item.get("line"))
    except (TypeError, ValueError):
        return "bad_line", "line is not a number", None
    if not quote:
        return "quote_empty", "no quote given", None
    lines, st, why = read_lines(root, str(item.get("file", "")))
    if st:
        return st, why, None
    if line < 1 or line > len(lines):
        return "line_out_of_range", "file has %d lines" % len(lines), None
    if quote in norm(lines[line - 1]):
        return "ok", "exact: found at the cited line", 0
    for off in range(1, window + 1):
        for ln in (line - off, line + off):
            if 1 <= ln <= len(lines) and quote in norm(lines[ln - 1]):
                return "ok", "shifted: found %d line(s) %s the cited line (%d)" % (
                    off, "before" if ln < line else "after", ln), ln - line
    lo, hi = max(0, line - 1 - window), min(len(lines), line + window)
    if quote in norm(" ".join(lines[lo:hi])):
        return "ok", "found across lines near the cited line", 0
    for i, ln in enumerate(lines, 1):
        if quote in norm(ln):
            return "wrong_line", "quote exists in the file at line %d, not at %d" % (i, line), i - line
    return "quote_not_found", "quote not present in the file", None


WEAK_START = ("//", "#", "*", "--", "/*", '"""', "'''", "import ", "from ", "package ", "using ", "#include", "use ", "require")


def check_loc(root, item):
    """Returns (status, detail, warning or None)."""
    lines, st, why = read_lines(root, item["file"])
    if st:
        return st, why, None
    if item["line"] < 1 or item["end"] > len(lines) or item["end"] < item["line"]:
        return "line_out_of_range", "file has %d lines" % len(lines), None
    text = lines[item["line"] - 1].strip()
    warn = None
    if not text or text.startswith(WEAK_START):
        warn = "the cited line is blank, a comment, a docstring or an import: cite an executable line"
    elif item.get("claims_quoted"):
        warn = "provenance is 'quoted' but no quote is given: add a quote field so it can be verified"
    return "ok", "location exists (no quote to compare)", warn


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("json_file", help="report or findings JSON")
    ap.add_argument("--root", default=".", help="root of the audited repository (default: .)")
    ap.add_argument("--window", type=int, default=3, help="lines around the cited line to accept (default 3)")
    ap.add_argument("--verbose", action="store_true", help="list every checked item, not only failures")
    ap.add_argument("--strict", action="store_true", help="treat warnings as failures (exit 1)")
    a = ap.parse_args(argv)
    try:
        with open(a.json_file, "r", encoding="utf-8") as fh:
            doc = json.load(fh)
    except (OSError, ValueError) as e:
        print("error: cannot read JSON: %s" % e, file=sys.stderr)
        return 2
    root = os.path.realpath(a.root)
    if not os.path.isdir(root):
        print("error: --root is not a directory", file=sys.stderr)
        return 2
    items = collect(doc)
    results, failed, warned = [], [], []
    counts = {"quotes": 0, "quotes_exact": 0, "quotes_shifted": 0, "locations_only": 0}
    for kind, path, owner, item in items:
        if kind == "quote":
            status, why, off = check_quote(root, item, a.window)
            counts["quotes"] += 1
            if status == "ok":
                counts["quotes_exact" if off == 0 else "quotes_shifted"] += 1
        else:
            status, why, warn = check_loc(root, item)
            off = None
            counts["locations_only"] += 1
            if warn:
                warned.append({"at": path, "finding": owner, "file": item.get("file"), "line": item.get("line"), "warning": warn})
        r = {"kind": kind, "at": path, "finding": owner, "file": item.get("file"), "line": item.get("line"),
             "status": status, "detail": why}
        if off:
            r["offset"] = off
        results.append(r)
        if status != "ok":
            failed.append(r)
    out = {"checked": len(results), "failed": len(failed), "warnings": len(warned), "counts": counts,
           "failures": failed, "warning_items": warned,
           "note": "VERIFIED WITH A QUOTE: %d. LOCATION ONLY (only that the line exists): %d. Quotes are compared after "
                   "whitespace normalization." % (counts["quotes"], counts["locations_only"])}
    if a.verbose:
        out["results"] = results
    json.dump(out, sys.stdout, ensure_ascii=False, indent=2)
    sys.stdout.write("\n")
    for r in failed:
        print("FAIL %s %s:%s %s: %s" % (r["finding"] or "-", r["file"], r["line"], r["status"], r["detail"]), file=sys.stderr)
    for w in warned:
        print("WARN %s %s:%s %s" % (w["finding"] or "-", w["file"], w["line"], w["warning"]), file=sys.stderr)
    if not results:
        print("warning: no citations found in the JSON; nothing was checked", file=sys.stderr)
    return 1 if (failed or (a.strict and warned)) else 0


if __name__ == "__main__":
    sys.exit(main())
