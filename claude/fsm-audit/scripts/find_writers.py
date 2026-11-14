#!/usr/bin/env python3
"""find_writers.py: list candidate writers and readers of a state field across a repository.

Read-only, standard library only, no network. Walks the tree, looks for the field names and for the
value literals, and classifies each matching line, per field name, as a candidate write, read, mention,
value-literal or comment. The classification is a line-level heuristic: results are CANDIDATES for a
human or a model to read, not proof. Test files are skipped unless --include-tests is given. Comment
lines are kind "comment" and never counted as writes.

A "write" of a name is: an SQL update or insert that names it BEFORE the WHERE clause, an assignment, a
setter or update call, or the field set to one of the --values literals (object literal `{ state: "x" }`,
keyword argument `status="x"`). A name that appears only in a WHERE clause is a read.
Not detected: multi-line SQL column lists and conditions (each line is judged alone), writes through a
generic setter whose value is a variable, dynamic field names. Check those by reading callers.

Output is one JSON document: totals, totals_by_name (written and read counts per field name: a field that
is written but never read, or read but never written, shows up there), per-file counts, then hits (writes
first). Use --summary for the totals only, or --out FILE to write the full JSON and print the summary.

Examples:
  find_writers.py --root . --names status --values pending,processing,done,dead
  find_writers.py --root src --names state,attempts --path-contains merge --summary
  find_writers.py --root . --names status --weak-values error,ok --out scratch/writers.json

Exit codes: 0 ok; 2 bad arguments or unwritable --out; 3 the --control site was not found.
"""
import argparse
import json
import os
import re
import sys

DEFAULT_EXT = (
    ".go .py .js .jsx .ts .tsx .mjs .cjs .java .kt .kts .scala .rb .rs .php .cs .swift .ex .exs .erl "
    ".c .h .cc .cpp .hpp .m .sql .sh .yaml .yml .json .toml .ini .cfg .conf .tf .proto .graphql"
).split()
DEFAULT_SKIP_DIRS = {
    ".git", "node_modules", "vendor", "dist", "build", "target", "__pycache__", ".venv", "venv",
    ".idea", ".vscode", ".next", ".gradle", "coverage", "third_party",
}
COMMENT_START = ("//", "#", "*", "--", "/*", "<!--", '"""', "'''")
SQL_CONDITION = re.compile(r"\b(?:where|and|or|filter|having|on|when)\b", re.I)
WHERE_SPLIT = re.compile(r"\bwhere\b", re.I)
TEST_PATH = re.compile(r"(_test\.|\.test\.|\.spec\.|/tests?/|/__tests__/|/testdata/|/spec/|/test_[^/]*$)", re.I)
KINDS = ("write", "read", "mention", "value-literal", "comment")
KIND_ORDER = dict((k, i) for i, k in enumerate(KINDS))
LIMITS = [
    "Dynamic field names (setattr, computed keys, **kwargs) are not visible to this search.",
    "Each line is judged alone: multi-line SQL (column lists, conditions on the next line) can be classified "
    "as mention or read; read the whole statement for the guard.",
    "A write through a generic setter whose value is a variable shows up at the setter, not at its callers: "
    "find the callers and the values they pass by reading.",
    "Generated code and other services are not covered unless they are inside --root.",
    "Classification is a heuristic: check the surrounding transaction and guard by reading.",
]


def alt(items):
    return "|".join(re.escape(x) for x in items)


def build_for_name(name, values, weak_values):
    n = re.escape(name)
    name_re = re.compile(r"(?<![A-Za-z0-9_])%s(?![A-Za-z0-9_])" % n, re.I)
    all_vals = list(values) + list(weak_values)
    lit_assign = re.compile(
        r"""(?<![A-Za-z0-9_])%s(?![A-Za-z0-9_])\s*[:=]\s*(['"`])(?:%s)\1""" % (n, alt(all_vals))) if all_vals else None
    sql_write = [
        re.compile(r"\bupdate\b.*\bset\b.*%s" % n, re.I),
        re.compile(r"\bset\b.*(?<![A-Za-z0-9_])%s\s*=" % n, re.I),
        re.compile(r"\binsert\s+into\b.*%s" % n, re.I),
    ]
    assign = re.compile(r"(?<![A-Za-z0-9_])%s(?![A-Za-z0-9_])\s*(?::=|\+=|-=|=(?![=>~]))" % n, re.I)
    call_write = [
        re.compile(r"\bset_?%s\w*\s*\(" % n, re.I),
        re.compile(r"\.(?:update|update_all|updateMany|update_one|save|upsert)\w*\(.*%s\s*[:=]" % n, re.I),
    ]
    read_res = [
        re.compile(r"(?<![A-Za-z0-9_])%s(?![A-Za-z0-9_])\s*(?:==|!=|===|!==|<=|>=|<|>|\bin\b|\bis\b)" % n, re.I),
        re.compile(r"\bwhere\b.*%s" % n, re.I),
        re.compile(r"\b(?:switch|case|match|when|if|elif|unless)\b.*%s" % n, re.I),
    ]
    return name_re, lit_assign, sql_write, assign, call_write, read_res


def in_string(prefix):
    """True if the end of prefix is inside a quoted string (odd number of unescaped quotes)."""
    for q in ('"', "'", "`"):
        if len(re.findall(r"(?<!\\)" + re.escape(q), prefix)) % 2 == 1:
            return True
    return False


def classify_name(line, p):
    """Kind of one field name on one (non-comment) line, or None if the name is absent."""
    name_re, lit_assign, sql_write, assign, call_write, read_res = p
    if not name_re.search(line):
        return None, None
    head = WHERE_SPLIT.split(line, maxsplit=1)[0]  # SQL: only the part before WHERE can write
    for r in sql_write:
        if r.search(head) and name_re.search(head):
            return "write", "SQL update or insert sets the field"
    if lit_assign:
        m = lit_assign.search(line)
        if m and not in_string(line[:m.start()]):
            if SQL_CONDITION.search(line[:m.start()]):
                return "read", "SQL condition on the field"
            return "write", "field set to a state value literal"
    m = assign.search(line)
    if m and not in_string(line[:m.start()]):
        if SQL_CONDITION.search(line[:m.start()]):
            return "read", "SQL condition on the field"
        return "write", "assignment of the field"
    for r in call_write:
        if r.search(line):
            return "write", "setter or update call with the field"
    for r in read_res:
        if r.search(line):
            return "read", "comparison, branch or WHERE on the field"
    return "mention", "field name appears"


def iter_files(root, exts, skip_dirs, max_bytes, skipped):
    for dirpath, dirnames, filenames in os.walk(root):
        dirnames[:] = sorted(d for d in dirnames if d not in skip_dirs)
        for fn in sorted(filenames):
            p = os.path.join(dirpath, fn)
            if exts and os.path.splitext(fn)[1].lower() not in exts:
                continue
            try:
                if os.path.islink(p) or os.path.getsize(p) > max_bytes:
                    skipped.append(os.path.relpath(p, root))
                    continue
            except OSError:
                continue
            yield p


def split(s):
    return [x.strip() for x in s.split(",") if x.strip()]


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--root", default=".", help="repository root to search (default: .)")
    ap.add_argument("--names", required=True, help="comma-separated field or column names")
    ap.add_argument("--values", default="", help="comma-separated state value literals, e.g. pending,done")
    ap.add_argument("--weak-values", default="", help="values too common to search alone (for example error, ok): "
                    "counted only when assigned to the field, never as stand-alone value-literal hits")
    ap.add_argument("--ext", default="", help="comma-separated extensions to scan (default: common code and config)")
    ap.add_argument("--skip-dirs", default="", help="extra directory names to skip, comma-separated")
    ap.add_argument("--path-contains", default="", help="only scan files whose relative path contains any of these substrings")
    ap.add_argument("--control", default="", help="known write site as relative/path:line (the line where the field "
                    "name appears in the statement); exit 3 if the search misses it")
    ap.add_argument("--limit", type=int, default=200, help="max hits returned (default 200)")
    ap.add_argument("--offset", type=int, default=0, help="skip this many hits (paging)")
    ap.add_argument("--kind", default="", help="only this kind: write, read, mention, value-literal, comment")
    ap.add_argument("--summary", action="store_true", help="print totals and per-file counts only, no hits")
    ap.add_argument("--out", default="", help="write the full JSON to this file and print only the summary")
    ap.add_argument("--max-bytes", type=int, default=1000000, help="skip files larger than this (default 1000000)")
    ap.add_argument("--include-tests", action="store_true", help="also scan test files (skipped by default)")
    a = ap.parse_args(argv)

    names, values, weak = split(a.names), split(a.values), split(a.weak_values)
    if not names:
        print("error: --names must list at least one field name", file=sys.stderr)
        return 2
    root = os.path.realpath(a.root)
    if not os.path.isdir(root):
        print("error: --root %s is not a directory" % a.root, file=sys.stderr)
        return 2
    exts = {e if e.startswith(".") else "." + e for e in (x.lower() for x in split(a.ext))} or set(DEFAULT_EXT)
    skip_dirs = set(DEFAULT_SKIP_DIRS) | set(split(a.skip_dirs))
    only = split(a.path_contains)
    if a.out:
        try:
            parent = os.path.dirname(os.path.abspath(a.out))
            os.makedirs(parent, exist_ok=True)
            with open(a.out, "a", encoding="utf-8"):
                pass
        except OSError as e:
            print("error: cannot write --out %s: %s" % (a.out, e), file=sys.stderr)
            return 2

    per_name = dict((n, build_for_name(n, values, weak)) for n in names)
    val_re = re.compile(r"""(['"`])(?:%s)\1""" % alt(values)) if values else None
    hits, by_file, skipped = [], {}, []
    by_name = dict((n, dict((k, 0) for k in KINDS)) for n in names)
    scanned = tests_skipped = 0
    for p in iter_files(root, exts, skip_dirs, a.max_bytes, skipped):
        rel = os.path.relpath(p, root)
        if only and not any(s in rel for s in only):
            continue
        if not a.include_tests and TEST_PATH.search("/" + rel.replace(os.sep, "/")):
            tests_skipped += 1
            continue
        scanned += 1
        try:
            with open(p, "r", encoding="utf-8", errors="replace") as fh:
                for i, line in enumerate(fh, 1):
                    matched = [n for n in names if per_name[n][0].search(line)]
                    has_val = bool(val_re.search(line)) if val_re else False
                    if not matched and not has_val:
                        continue
                    is_comment = line.strip().startswith(COMMENT_START)
                    kinds, why = {}, ""
                    if is_comment:
                        kinds = dict((n, "comment") for n in matched) if matched else {}
                        kind, why = "comment", "comment line"
                    elif matched:
                        reasons = {}
                        for n in matched:
                            kinds[n], reasons[n] = classify_name(line, per_name[n])
                        kind = min(kinds.values(), key=lambda k: KIND_ORDER[k])
                        why = next(reasons[n] for n in matched if kinds[n] == kind)
                    else:
                        kind, why = "value-literal", "a state value literal appears without the field name"
                    indent = len(line) - len(line.lstrip(" \t"))
                    hit = {"file": rel, "line": i, "kind": kind, "indent": indent, "reason": why, "text": line.strip()[:240]}
                    if kinds:
                        hit["by_name"] = kinds
                    hits.append(hit)
                    d = by_file.setdefault(rel, dict((k, 0) for k in KINDS))
                    d[kind] += 1
                    for n, k in kinds.items():
                        by_name[n][k] += 1
        except OSError as e:
            print("warning: cannot read %s: %s" % (rel, e), file=sys.stderr)

    control = None
    if a.control:
        m = re.match(r"^(.*):(\d+)$", a.control)
        if not m:
            print("error: --control must look like path:line", file=sys.stderr)
            return 2
        cf, cl = m.group(1), int(m.group(2))
        found = [h for h in hits if h["file"] == cf and h["line"] == cl]
        control = {"requested": a.control, "found": bool(found), "kind": found[0]["kind"] if found else None}
        if found and found[0]["kind"] != "write":
            control["warning"] = ("the control line was found but classified as '%s', not 'write': the search sees the "
                                  "site but write detection does not recognise its form (a multi-line statement? give the "
                                  "line where the field name appears); count writers by reading, not by totals" % found[0]["kind"])

    totals = dict((k, 0) for k in KINDS)
    for h in hits:
        totals[h["kind"]] += 1
    ordered = sorted(hits, key=lambda h: (KIND_ORDER[h["kind"]], h["file"], h["line"]))
    shown = [h for h in ordered if not a.kind or h["kind"] == a.kind]
    page = shown[a.offset:a.offset + a.limit]
    notes = []
    for n in names:
        if by_name[n]["write"] and not by_name[n]["read"]:
            notes.append("'%s' is written at %d line(s) and never read (as classified): check for a missing reader or dead field" % (n, by_name[n]["write"]))
        if by_name[n]["read"] and not by_name[n]["write"]:
            notes.append("'%s' is read at %d line(s) and never written (as classified): check for a missing writer or a writer outside --root" % (n, by_name[n]["read"]))
    summary = {
        "unit": "matching source lines (candidate write / read / mention / value-literal / comment); a line naming several fields counts once in totals and once per field in totals_by_name",
        "method": "python tree walk with regex heuristics",
        "root": root, "names": names, "values": values, "weak_values": weak,
        "files_scanned": scanned, "test_files_skipped": tests_skipped,
        "files_skipped_too_large_or_symlink": skipped[:50],
        "totals_by_kind": totals,
        "totals_by_name": by_name,
        "observations": notes,
        "by_file": dict(sorted(by_file.items(), key=lambda kv: (-kv[1]["write"], -kv[1]["read"]))[:40]),
        "control": control,
        "cannot_see": LIMITS,
        "next": "Read each write candidate: record its from-guard and whether the guard result is read. "
                "Cross-check with a second method (a different mechanism) and compare the two sets.",
    }
    full = dict(summary)
    full.update({"total_hits": len(shown), "offset": a.offset, "returned": len(page),
                 "truncated": len(shown) > a.offset + a.limit, "hits": page})
    if a.out:
        with open(a.out, "w", encoding="utf-8") as fh:
            json.dump(full, fh, ensure_ascii=False, indent=2)
        summary["full_json_written_to"] = a.out
        out = summary
    elif a.summary:
        out = summary
    else:
        out = full
    json.dump(out, sys.stdout, ensure_ascii=False, indent=2)
    sys.stdout.write("\n")
    if control is not None and not control["found"]:
        print("control site %s was NOT found: do not trust this search" % a.control, file=sys.stderr)
        return 3
    if control is not None and control.get("warning"):
        print("warning: " + control["warning"], file=sys.stderr)
    return 0


if __name__ == "__main__":
    sys.exit(main())
