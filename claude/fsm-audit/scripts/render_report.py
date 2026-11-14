#!/usr/bin/env python3
"""render_report.py: turn an fsm-audit report JSON into ONE self-contained HTML file.

Standard library only, no network, no JavaScript in the output. All text from the JSON is
HTML-escaped. The JSON schema is described in references/report-schema.md. Static labels are in
English; override any of them with a top-level "labels" object to localize the report.

Usage:
  render_report.py report.json out.html
  render_report.py --help

Exit codes: 0 ok; 2 bad arguments or invalid JSON (with --strict: or keys the renderer ignores).
"""
import argparse
import html
import json
import re
import sys

LABELS = {
    "summary": "Summary", "coverage": "Scope and coverage", "findings": "Findings", "entities": "Entities",
    "rejected": "Rejected findings", "not_covered": "Not covered", "method": "Method notes",
    "claim": "Claim", "path": "Path to the bad state", "evidence": "Evidence", "impact": "Impact",
    "refuted_if": "Refuted if", "test_idea": "Test idea", "skeptic": "Skeptic", "shared_root": "Shared root cause",
    "projection": "Projection (state-bearing fields)", "excluded": "Excluded", "other_holders": "Other holders of state",
    "domains": "Domains", "declared": "Declared states", "reachable": "Reachable states",
    "writers": "Writers inventory", "unit": "Unit", "control": "Control", "methods": "Methods",
    "set_difference": "Set difference", "not_visible": "Not visible to search", "events": "Events",
    "table": "State by event table", "empty_cells": "EMPTY cells", "forbidden": "Forbidden combinations",
    "unreachable": "Unreachable or dead states", "state_space": "State space", "treatment": "Treatment",
    "outcome": "Outcome", "reason": "Reason", "price": "Price", "reversibility": "Reversibility",
    "where": "Where", "writes": "Writes", "guard": "From-guard", "guard_read": "Guard result read",
    "class": "Class", "severity": "Severity", "provenance": "Provenance", "not_assessed": "not assessed",
    "agents": "Agents", "mode": "Mode", "scope": "Scope", "date": "Date", "repo": "Repository", "commit": "Commit",
    "no_findings": "No findings of this kind. This is not proof of absence: see the not-covered list.",
    "unverified": "Unverified candidates", "questions": "Questions for the owner", "known_to_owners": "Known to owners",
    "side_fields": "Behaviour-changing side fields", "behavioural": "Behavioural states", "reach": "Reach",
    "unverified_note": "Not confirmed by an independent skeptic. These are candidates, not bugs.",
    "absence": "Evidence of absence", "events_considered": "Events considered", "default_cell": "default for this event",
    "unverified_summary": "finding(s) are unverified candidates (no independent skeptic confirmed them): read them as leads, not as bugs.",
}
SEV_NAME = {1: "1 data lost", 2: "2 wrong visible result", 3: "3 stuck, no alarm", 4: "4 silent failure"}
CSS = """
:root{--bg:#fbfaf7;--fg:#1d1d1b;--muted:#6b6a65;--card:#fff;--line:#e4e2dc;--code:#f2f0ea;
--ok:#2e6b3a;--okb:#e1f0e4;--warn:#8a5a00;--warnb:#fbf0d6;--bad:#a8231b;--badb:#fbe3e0;--info:#244d8c;--infob:#e3ebf8}
@media (prefers-color-scheme:dark){:root{--bg:#161615;--fg:#ecebe6;--muted:#a3a29b;--card:#1f1f1d;--line:#34332f;
--code:#2a2a27;--ok:#8fd19c;--okb:#17301c;--warn:#f0c26a;--warnb:#3a2f10;--bad:#f2928a;--badb:#401a17;--info:#9db9ee;--infob:#1b2a45}}
*{box-sizing:border-box}
body{margin:0;background:var(--bg);color:var(--fg);font:16px/1.55 -apple-system,BlinkMacSystemFont,"Segoe UI",Roboto,sans-serif}
main{max-width:980px;margin:0 auto;padding:24px 16px 64px}
h1{font-size:26px;margin:0 0 4px}h2{font-size:21px;margin:38px 0 10px;border-top:2px solid var(--line);padding-top:10px}
h3{font-size:17px;margin:20px 0 6px}h4{font-size:15px;margin:14px 0 4px}
.m{color:var(--muted);font-size:14px}
.card{background:var(--card);border:1px solid var(--line);border-radius:10px;padding:12px 16px;margin:12px 0}
.badge{display:inline-block;padding:1px 8px;border-radius:999px;font-size:12.5px;font-weight:600;margin-right:4px;border:1px solid var(--line)}
.v-N-A{background:var(--code);color:var(--muted)}
.sev1,.bad,.v-FORBIDDEN{background:var(--badb);color:var(--bad)}
.sev2,.warn,.v-EMPTY{background:var(--warnb);color:var(--warn)}
.sev3{background:var(--infob);color:var(--info)}.sev4,.na{background:var(--code);color:var(--muted)}
.ok,.v-ALLOWED{background:var(--okb);color:var(--ok)}.v-NO-CHANGE{background:var(--infob);color:var(--info)}
.wrap{overflow-x:auto}
table{border-collapse:collapse;width:100%;font-size:14px;background:var(--card)}
th,td{border:1px solid var(--line);padding:6px 8px;text-align:left;vertical-align:top}th{background:var(--code)}
td.cell{min-width:120px}td.cell .ev{font-size:12px;color:var(--muted);display:block}
code,pre{background:var(--code);border-radius:4px;font-size:13px}code{padding:1px 5px}
pre{padding:8px 10px;overflow-x:auto;white-space:pre-wrap;margin:6px 0}
ul,ol{margin:6px 0;padding-left:22px}li{margin:3px 0}
dl{display:grid;grid-template-columns:170px 1fr;gap:4px 12px}dt{color:var(--muted);font-size:14px}dd{margin:0}
@media (max-width:640px){dl{grid-template-columns:1fr}dt{margin-top:6px}h1{font-size:22px}}
"""


def e(x):
    return "" if x is None else html.escape(str(x), quote=True)


class R(object):
    def __init__(self, doc):
        self.d = doc
        self.L = dict(LABELS)
        self.L.update(doc.get("labels") or {})

    def l(self, k):
        return e(self.L.get(k, k))

    def badge(self, text, cls):
        return '<span class="badge %s">%s</span>' % (e(cls), e(text))

    def ul(self, items):
        items = [i for i in (items or []) if i not in (None, "")]
        if not items:
            return ""
        return "<ul>%s</ul>" % "".join("<li>%s</li>" % e(i) for i in items)

    def dl(self, pairs):
        rows = "".join("<dt>%s</dt><dd>%s</dd>" % (self.l(k), v) for k, v in pairs if v not in (None, "", "<ul></ul>"))
        return "<dl>%s</dl>" % rows if rows else ""

    # ----- sections
    def header(self):
        m = self.d.get("meta") or {}
        bits = []
        for k in ("repo", "commit", "date", "mode"):
            if m.get(k):
                bits.append("%s: %s" % (self.L.get(k, k), m[k]))
        ag = m.get("agents")
        if ag:
            bits.append("%s: %s" % (self.L["agents"], ", ".join("%s %s" % (k, v) for k, v in ag.items())))
        return "<h1>%s</h1><p class='m'>%s</p>" % (e(m.get("title") or "FSM audit report"), e(" · ".join(bits)))

    def summary(self):
        s = self.d.get("summary") or {}
        out = ["<h2>%s</h2><div class='card'>" % self.l("summary")]
        if s.get("headline"):
            out.append("<p><b>%s</b></p>" % e(s["headline"]))
        out.append(self.ul(s.get("bullets")))
        n_un = sum(1 for f in (self.d.get("findings") or []) if self.is_unverified(f))
        if n_un:
            out.append("<p class='m'><b>%d</b> %s</p>" % (n_un, self.l("unverified_summary")))
        counts = s.get("counts") or []
        if counts:
            out.append("<div class='wrap'><table><tr><th>What</th><th>Value</th><th>Unit</th></tr>%s</table></div>" % "".join(
                "<tr><td>%s</td><td>%s</td><td>%s</td></tr>" % (e(c.get("label")), e(c.get("value")), e(c.get("unit"))) for c in counts))
        out.append("</div>")
        return "".join(out)

    def coverage(self):
        m = self.d.get("meta") or {}
        out = ["<h2>%s</h2><div class='card'>" % self.l("coverage")]
        out.append(self.dl([("scope", e(m.get("scope")))]))
        out.append("<h4>%s</h4>%s" % (self.l("not_covered"), self.ul(self.d.get("not_covered")) or "<p class='m'>—</p>"))
        out.append("</div>")
        return "".join(out)

    def finding(self, f):
        sev = f.get("severity") if f.get("class") != "note" else None
        head = "%s%s%s%s" % (
            self.badge(f.get("class", "finding"), "ok" if f.get("class") == "note" else "warn"),
            self.badge(SEV_NAME.get(sev, "severity %s" % sev), "sev%s" % sev) if sev else "",
            self.badge(f.get("provenance", "unconfirmed"), "ok" if f.get("provenance") in ("quoted", "reproduced") else "na"),
            self.badge("skeptic: %s" % (f.get("skeptic") or {}).get("verdict", "not checked"),
                       "ok" if (f.get("skeptic") or {}).get("verdict") == "confirmed" else "na"),
        )
        ev = "".join("<li><code>%s:%s</code><pre>%s</pre></li>" % (e(x.get("file")), e(x.get("line")), e(x.get("quote")))
                     for x in f.get("evidence") or [])
        path = "<ol>%s</ol>" % "".join("<li>%s</li>" % e(p) for p in f.get("path") or []) if f.get("path") else ""
        sk = f.get("skeptic") or {}
        skt = e(" ".join(x for x in (sk.get("lens"), sk.get("reason")) if x))
        body = self.dl([
            ("claim", e(f.get("claim"))), ("path", path), ("evidence", "<ul>%s</ul>" % ev if ev else ""),
            ("impact", e(f.get("impact"))), ("reach", e(f.get("reach"))), ("refuted_if", e(f.get("refuted_if"))),
            ("test_idea", e(f.get("test_idea"))), ("known_to_owners", e(f.get("known_to_owners"))),
            ("absence", e("; ".join("%s: %s" % (k, v) for k, v in (f.get("absence") or {}).items()))),
            ("skeptic", skt), ("shared_root", e(f.get("shared_root"))),
        ])
        return "<article class='card' id='%s'><h3>%s %s</h3><div>%s</div>%s</article>" % (
            e(f.get("id")), e(f.get("id")), e(f.get("title")), head, body)

    @staticmethod
    def is_unverified(f):
        verdict = (f.get("skeptic") or {}).get("verdict")
        return f.get("class") == "unverified" or (f.get("class", "bug") == "bug" and verdict != "confirmed")

    def findings(self):
        fs = self.d.get("findings") or []
        out = ["<h2>%s</h2>" % self.l("findings")]
        key = lambda f: (f.get("severity") or 9, str(f.get("id")))
        groups = (("bug", "Bugs (confirmed by a skeptic)"), ("risk", "Risks"), ("note", "Notes"))
        shown = 0
        for cls, title in groups:
            items = sorted([f for f in fs if f.get("class", "bug") == cls and not self.is_unverified(f)], key=key)
            if not items:
                continue
            shown += len(items)
            out.append("<h3>%s (%d)</h3>" % (e(title), len(items)))
            out.append("\n".join(self.finding(f) for f in items))
        un = sorted([f for f in fs if self.is_unverified(f)], key=key)
        if un:
            shown += len(un)
            out.append("<h3>%s (%d)</h3><p class='m'>%s</p>" % (self.l("unverified"), len(un), self.l("unverified_note")))
            out.append("\n".join(self.finding(f) for f in un))
        if not shown:
            out.append("<p class='m'>%s</p>" % self.l("no_findings"))
        return "\n".join(out)

    def questions(self):
        qs = self.d.get("questions") or []
        if not qs:
            return ""
        return "<h2>%s</h2><div class='card'>%s</div>" % (self.l("questions"), self.ul(qs))

    def matrix(self, t):
        states, events = t.get("states") or [], t.get("events") or []
        cells = dict(((c.get("state"), c.get("event")), c) for c in t.get("cells") or [])
        defaults = dict((c.get("event"), c) for c in t.get("defaults") or [])
        head = "<tr><th></th>%s</tr>" % "".join("<th>%s</th>" % e(x) for x in events)
        rows = []
        for s in states:
            tds = []
            for ev in events:
                c = cells.get((s, ev))
                if not c and ev in defaults:
                    c = dict(defaults[ev])
                    c["note"] = " ".join(x for x in (c.get("note"), "(" + self.L["default_cell"] + ")") if x)
                if not c:
                    tds.append("<td class='cell'><span class='badge na'>%s</span></td>" % self.l("not_assessed"))
                    continue
                v = str(c.get("value", "")).upper()
                vc = re.sub(r"[^A-Z0-9]+", "-", v)
                tgt = " → %s" % e(c.get("target")) if c.get("target") else ""
                meta = " ".join(x for x in (c.get("evidence"), c.get("provenance")) if x)
                note = "<br>%s" % e(c.get("note")) if c.get("note") else ""
                tds.append("<td class='cell'><span class='badge v-%s'>%s</span>%s<span class='ev'>%s</span>%s</td>" % (
                    e(vc), e(v), tgt, e(meta), note))
            rows.append("<tr><th>%s</th>%s</tr>" % (e(s), "".join(tds)))
        return "<div class='wrap'><table>%s%s</table></div>" % (head, "".join(rows))

    def entity(self, en):
        w = en.get("writers") or {}
        out = ["<section class='card' id='%s'><h3>%s %s</h3>" % (e(en.get("id")), e(en.get("id")), e(en.get("name")))]
        dom = "; ".join("%s: {%s}" % (k, ", ".join(map(str, v))) for k, v in (en.get("domains") or {}).items())
        out.append(self.dl([
            ("projection", e(", ".join(en.get("projection") or []))),
            ("side_fields", e(", ".join(en.get("side_fields") or []))), ("excluded", e("; ".join(en.get("excluded") or []))),
            ("other_holders", e("; ".join(en.get("other_holders") or []))), ("domains", e(dom)),
            ("declared", e(en.get("declared"))), ("reachable", e(en.get("reachable"))),
        ]))
        if w:
            rows = "".join("<tr><td><code>%s</code></td><td>%s</td><td>%s</td><td>%s</td><td>%s</td></tr>" % (
                e(r.get("where")), e(r.get("writes")), e(r.get("guard")), e(r.get("guard_result_read")), e(r.get("provenance")))
                for r in w.get("rows") or [])
            meth = "; ".join("%s: %s%s" % (m.get("name"), m.get("hits"), "" if m.get("independent") is None else (
                " (independent)" if m.get("independent") else " (NOT independent of the other method)")) for m in w.get("methods") or [])
            out.append("<h4>%s</h4>%s" % (self.l("writers"), self.dl([
                ("unit", e(w.get("unit"))), ("control", e(w.get("control"))), ("methods", e(meth)),
                ("set_difference", e(w.get("set_difference"))), ("not_visible", self.ul(w.get("not_visible")))])))
            if rows:
                out.append("<div class='wrap'><table><tr><th>%s</th><th>%s</th><th>%s</th><th>%s</th><th>%s</th></tr>%s</table></div>" % (
                    self.l("where"), self.l("writes"), self.l("guard"), self.l("guard_read"), self.l("provenance"), rows))
        if en.get("events"):
            out.append("<h4>%s</h4>%s" % (self.l("events"), self.ul(en["events"])))
        if en.get("events_considered"):
            rows = "".join("<tr><td>%s</td><td>%s</td><td>%s</td></tr>" % (e(x.get("event")), e(x.get("verdict")), e(x.get("why")))
                           for x in en["events_considered"])
            out.append("<h4>%s</h4><div class='wrap'><table><tr><th>Event</th><th>Applies?</th><th>Why</th></tr>%s</table></div>" % (
                self.l("events_considered"), rows))
        if en.get("table"):
            out.append("<h4>%s</h4>%s" % (self.l("table"), self.matrix(en["table"])))
        if en.get("empty_cells"):
            rows = "".join("<tr><td>%s</td><td>%s</td><td>%s</td><td>%s</td></tr>" % (
                e(c.get("state")), e(c.get("event")), e(c.get("class")), e(c.get("note"))) for c in en["empty_cells"])
            out.append("<h4>%s</h4><div class='wrap'><table><tr><th>State</th><th>Event</th><th>%s</th><th>Note</th></tr>%s</table></div>" % (
                self.l("empty_cells"), self.l("class"), rows))
        if en.get("forbidden_combinations"):
            out.append("<h4>%s</h4>%s" % (self.l("forbidden"), self.ul(en["forbidden_combinations"])))
        if en.get("unreachable"):
            out.append("<h4>%s</h4>%s" % (self.l("unreachable"), self.ul(
                ["%s: %s %s" % (u.get("what"), u.get("why"), u.get("provenance") or "") for u in en["unreachable"]])))
        ss = en.get("state_space")
        if ss:
            out.append("<h4>%s</h4>%s" % (self.l("state_space"), self.dl([
                ("declared", e(ss.get("declared"))), ("reachable", e(ss.get("reachable"))),
                ("behavioural", e(ss.get("behavioural"))),
                ("projection", e(ss.get("regions"))), ("reason", e(ss.get("note")))])))
        tr = en.get("treatment")
        if tr:
            out.append("<h4>%s</h4>%s" % (self.l("treatment"), self.dl([
                ("outcome", e(tr.get("outcome"))), ("reason", e(tr.get("reason"))),
                ("price", e(tr.get("price"))), ("reversibility", e(tr.get("reversibility")))])))
        if en.get("not_covered"):
            out.append("<h4>%s</h4>%s" % (self.l("not_covered"), self.ul(en["not_covered"])))
        out.append("</section>")
        return "".join(out)

    def entities(self):
        return "<h2>%s</h2>%s" % (self.l("entities"), "".join(self.entity(x) for x in self.d.get("entities") or []))

    def rejected(self):
        rj = self.d.get("rejected") or []
        if not rj:
            return ""
        rows = "".join("<tr><td>%s</td><td>%s</td><td>%s</td></tr>" % (e(r.get("id")), e(r.get("title")), e(r.get("reason"))) for r in rj)
        return "<h2>%s (%d)</h2><div class='wrap'><table><tr><th>ID</th><th>Title</th><th>%s</th></tr>%s</table></div>" % (
            self.l("rejected"), len(rj), self.l("reason"), rows)

    def tail(self):
        out = []
        if self.d.get("method_notes"):
            out.append("<h2>%s</h2>%s" % (self.l("method"), self.ul(self.d["method_notes"])))
        return "".join(out)

    def render(self):
        m = self.d.get("meta") or {}
        return ("<!doctype html>\n<html lang='%s'><head><meta charset='utf-8'>"
                "<meta name='viewport' content='width=device-width, initial-scale=1'>"
                "<title>%s</title><style>%s</style></head><body><main>\n%s\n%s\n%s\n%s\n%s\n%s\n%s\n%s\n</main></body></html>\n") % (
            e(m.get("language") or "en"), e(m.get("title") or "FSM audit report"), CSS,
            self.header(), self.summary(), self.coverage(), self.questions(), self.findings(), self.entities(), self.rejected(), self.tail())


KNOWN = {
    "top": "meta labels summary entities findings questions rejected not_covered method_notes",
    "meta": "title repo commit date language mode scope agents",
    "summary": "headline bullets counts",
    "entity": "id name location projection side_fields excluded other_holders domains declared reachable writers events "
              "events_considered table empty_cells forbidden_combinations unreachable state_space treatment not_covered",
    "writers": "unit control methods set_difference not_visible rows",
    "row": "where writes guard guard_result_read provenance quote",
    "table": "states events cells defaults",
    "cell": "state event value target evidence provenance note quote",
    "finding": "id entity class severity title claim path evidence provenance impact reach refuted_if test_idea "
               "known_to_owners absence skeptic shared_root",
    "skeptic": "verdict lens reason",
}


def unknown_keys(doc):
    """Names of keys the renderer ignores (usually a misspelling)."""
    bad = []

    def chk(obj, kind, where):
        if isinstance(obj, dict):
            for k in obj:
                if k not in KNOWN[kind].split():
                    bad.append("%s: unknown key '%s'" % (where, k))

    chk(doc, "top", "report")
    chk(doc.get("meta"), "meta", "meta")
    chk(doc.get("summary"), "summary", "summary")
    for en in doc.get("entities") or []:
        w = "entity %s" % (en.get("id") if isinstance(en, dict) else "?")
        chk(en, "entity", w)
        if isinstance(en, dict):
            chk(en.get("writers"), "writers", w + " writers")
            for r in (en.get("writers") or {}).get("rows") or []:
                chk(r, "row", w + " writers row")
            chk(en.get("table"), "table", w + " table")
            for c in ((en.get("table") or {}).get("cells") or []) + ((en.get("table") or {}).get("defaults") or []):
                chk(c, "cell", w + " table cell")
    for f in doc.get("findings") or []:
        chk(f, "finding", "finding %s" % (f.get("id") if isinstance(f, dict) else "?"))
        if isinstance(f, dict):
            chk(f.get("skeptic"), "skeptic", "finding %s skeptic" % f.get("id"))
    return bad


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("json_file", help="report JSON (see references/report-schema.md)")
    ap.add_argument("out_html", help="output HTML file (created or overwritten)")
    ap.add_argument("--strict", action="store_true", help="exit 2 if the JSON has keys the renderer ignores (misspellings)")
    a = ap.parse_args(argv)
    try:
        with open(a.json_file, "r", encoding="utf-8") as fh:
            doc = json.load(fh)
    except (OSError, ValueError) as ex:
        print("error: cannot read JSON: %s" % ex, file=sys.stderr)
        return 2
    if not isinstance(doc, dict):
        print("error: the JSON root must be an object", file=sys.stderr)
        return 2
    bad = unknown_keys(doc)
    for b in bad:
        print("warning: %s (ignored by the renderer; misspelt?)" % b, file=sys.stderr)
    if bad and a.strict:
        return 2
    page = R(doc).render()
    with open(a.out_html, "w", encoding="utf-8") as fh:
        fh.write(page)
    print("wrote %s (%d bytes)" % (a.out_html, len(page.encode("utf-8"))), file=sys.stderr)
    return 0


if __name__ == "__main__":
    sys.exit(main())
