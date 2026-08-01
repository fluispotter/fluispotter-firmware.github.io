#!/usr/bin/env python3
"""
Generator for the Fluispotter project site (docs/site).

Self-contained, offline. Produces static HTML pages that share one stylesheet
(styles.css), a left sidebar + top header. Canonical HTML docs are EMBEDDED via
<iframe> using relative paths back to docs/ so edits to the canonical files are
always reflected. Markdown docs are rendered to styled HTML. .rtf/.docx/.pdf get
open/download links to their relative path.

Run from docs/site/:  python3 _build_site.py
"""
import html
import os
import re
import json

HERE = os.path.dirname(os.path.abspath(__file__))
DOCS = os.path.dirname(HERE)            # one level up = docs/

# --------------------------------------------------------------------------
# DATA
# --------------------------------------------------------------------------

DOCUMENTS = [
    {"file": "fluispotter_spec_repo.html", "title": "Fluispotter Device Specification Repository", "category": "Specification", "kind": "html",
     "blurb": "The authoritative device specification for the Fluispotter instrument, covering hardware, firmware behavior, the ULP pump regulator, and the operational sequence."},
    {"file": "monitor_spec_repo.html", "title": "Fluispotter Monitor Application — Software Specification", "category": "Specification", "kind": "html",
     "blurb": "Software specification for the Monitor desktop app, documenting its tabs, structure, data flow, and hardware interfaces."},
    {"file": "control_spec_repo.html", "title": "Fluispotter Control Application — Software Specification", "category": "Specification", "kind": "html",
     "blurb": "Software specification for the Control desktop app, documenting its tabs, structure, data flow, and hardware interfaces."},
    {"file": "fluispotter_sw_requirements.html", "title": "Fluispotter Software Requirements", "category": "Requirements", "kind": "html",
     "blurb": "The generated software requirements registry of testable, ID'd SW and MECH requirements (a fluispotter_sw_requirements.docx twin exists alongside it)."},
    {"file": "fluispotter_verification_status.html", "title": "Fluispotter Verification Status — Reqs vs Tested vs Verified", "category": "Requirements", "kind": "html",
     "blurb": "Generated evidence report: every requirement scored NOT TESTED / TESTED (CI claim check) / BENCH-TESTED (board-driving suite) / FIELD-VERIFIED (proven by a concluded testlog run), with the firmware version each hardware proof was taken at, plus the locked-without-hardware-evidence gap list."},
    {"file": "main_cpu_architecture.rtf", "title": "Main CPU Architecture", "category": "Architecture", "kind": "rtf",
     "blurb": "Architecture note describing the MicroPython main-CPU firmware: its async state machine, the MainController object graph, and how real-time pump regulation is offloaded to the ULP."},
    {"file": "ulp_pid_code_annotated.rtf", "title": "ULP RISC-V Pump Regulator — PID Code Annotated Reference", "category": "Architecture", "kind": "rtf",
     "blurb": "Annotated walkthrough of the ULP RISC-V pump-regulator source, explaining the DAC inversion convention, encoder/PID constants, timing helpers, and adaptive stall detection."},
    {"file": "multi_mode_ulp.md", "title": "Multi-Mode ULP (Design Note)", "category": "Architecture", "kind": "md",
     "blurb": "Design-only note proposing swapping separate operational and test ULP binaries at runtime, with fixed shared-variable addresses via a custom linker section."},
    {"file": "index.md", "title": "API Reference", "category": "Architecture", "kind": "md",
     "blurb": "The mkdocs API-reference landing page documenting the device firmware's development module and its REPL-oriented sync/async functions."},
    {"file": "ci_release_plan.md", "title": "CI / Release Process Plan", "category": "Process", "kind": "md",
     "blurb": "The staged continuous-integration and release plan covering all five shippable components, including the PR gate, artifact build, bench HIL, and release governance."},
    {"file": "compacting_log.md", "title": "Conversation Compacting Log", "category": "Process", "kind": "md",
     "blurb": "Append-only record of conversation-compaction events, capturing what each summarized stretch of work delivered and what remained open."},
    {"file": "prompts.md", "title": "User Prompts Log", "category": "Other", "kind": "md",
     "blurb": "Chronological log of all user prompts from Claude Code sessions (surfaced by the dedicated history page rather than the main docs nav)."},
]

DATASHEETS = [
    {"dest": "esp32-s3-wroom-1.pdf", "component": "ESP32-S3-WROOM-1 main MCU module",
     "evidence": "Spec docs/fluispotter_spec_repo.html identifies the MCU as 'ESP32-S3-WROOM-1-N8R8' (designator IC9, line 315/386/1034); README.md and firmware confirm ESP32-S3 runtime. 'wroom' appears in repo, 'mini-1' has zero references, so WROOM-1 is the correct variant."},
    {"dest": "dac7574-quad-dac.pdf", "component": "TI DAC7574 quad DAC (pump power)",
     "evidence": "Vendored MicroPython driver at lib/MicroPython-DAC7574; 132 references across repo. Drives the pump power output (DAC at 0x4C per memory/spec). Core firmware part."},
    {"dest": "veml6035-light-sensor.pdf", "component": "Vishay VEML6035 ambient-light sensor (spot/line)",
     "evidence": "Vendored MicroPython driver at lib/MicroPython-VEML6035; 91 references. Spec §4.1 'VEML Light Sensor - Line Spot'; spec §306 details the CONFIG 0x00 power-on and 0x04 read protocol for the spot/line sensors."},
    {"dest": "faulhaber-1512-ie2-8-gearmotor.pdf", "component": "Faulhaber 1512U 324:1 IE2-8 gearmotor + integrated encoder",
     "evidence": "board_config.py:59 'Faulhaber 1512U012SR 324:1 IE2-8'; spec §2.x cites this exact part and gear ratio; spec datasheet manifest (line 1122) lists 'EN_1512_SR_IE2-8_DFF.pdf / Faulhaber 1512 datasheet / On file'. The integrated IE2-8 optical encoder is the device's rotation feedback (no separate encoder)."},
    {"dest": "kingbright-apda3020p3c-phototransistor.pdf", "component": "Kingbright APDA3020P3C IR phototransistor (Q3/Q7)",
     "evidence": "Spec docs/fluispotter_spec_repo.html line 327 lists 'Phototransistor: Kingbright APDA3020P3C (Q3/Q7)'; candidate filename APDA3020P3C-P22.pdf matches the P3C phototransistor part referenced in the spec."},
]

# Git commits loaded from a sidecar JSON written by the orchestrator step.
with open(os.path.join(HERE, "_commits.json"), encoding="utf-8") as f:
    COMMITS = json.load(f)

try:
    with open(os.path.join(HERE, "_issues.json"), encoding="utf-8") as f:
        ISSUES = json.load(f)
except OSError:
    ISSUES = []

# Optional status sidecar (versions + CI snapshot), written by
# _refresh_data.py alongside _commits.json.  The site renders without it.
try:
    with open(os.path.join(HERE, "_status.json"), encoding="utf-8") as f:
        STATUS = json.load(f)
except OSError:
    STATUS = None


def status_panel_html():
    if not STATUS:
        return ""
    req = STATUS.get("requirements") or {}
    rows = [
        ("Firmware", STATUS.get("firmware_version")),
        ("Operational ULP", STATUS.get("ulp_operational")),
        ("Hub service", STATUS.get("hub_service")),
        ("Requirements registry",
         "%s requirements (doc %s)" % (req.get("total", "?"),
                                       req.get("doc_version", "?"))),
    ]
    ver = req.get("verification") or {}
    if ver:
        hw = ver.get("field_verified", 0) + ver.get("bench_tested", 0)
        tested = hw + ver.get("tested", 0)
        rows.append(("Verification status",
                     "%d tested / %d hardware-verified / %d untested "
                     "(see Requirements \u2192 Verification Status)"
                     % (tested, hw, ver.get("not_tested", 0))))
    lc = STATUS.get("latest_commit") or {}
    if lc:
        rows.append(("Latest commit", "%s — %s (%s)" % (
            lc.get("hash", "")[:8], lc.get("subject", ""), lc.get("date", ""))))
    row_html = "".join(
        '<tr><td>%s</td><td>%s</td></tr>'
        % (html.escape(str(k)), html.escape(str(v if v is not None else "unknown")))
        for k, v in rows)
    badges = []
    seen = set()
    for run in STATUS.get("ci", []):
        key = (run.get("workflowName"), run.get("headBranch"))
        if key in seen:
            continue
        seen.add(key)
        concl = run.get("conclusion") or run.get("status") or "?"
        cls = {"success": "ok", "failure": "bad"}.get(concl, "warn")
        badges.append('<span class="ci-badge %s">%s @ %s: %s</span>' % (
            cls, html.escape(str(run.get("workflowName"))),
            html.escape(str(run.get("headBranch"))), html.escape(str(concl))))
    badge_html = ("<div class=\"ci-badges\">" + "".join(badges) + "</div>"
                  if badges else
                  "<p style=\"color:var(--ink-soft)\">CI snapshot unavailable "
                  "at build time.</p>")
    return """
<div class="panel">
  <h3 style="margin-top:0">Project status
    <span class="status-stamp">snapshot %s &middot;
    <a href="https://github.com/fluispotter/fluispotter-firmware/actions">live CI on GitHub Actions</a></span></h3>
  <table class="status-table">%s</table>
  %s
</div>
""" % (html.escape(STATUS.get("generated_at", "")), row_html, badge_html)

# --------------------------------------------------------------------------
# NAV
# --------------------------------------------------------------------------

NAV = [
    ("Project", [
        ("index.html", "Overview", "home"),
    ]),
    ("Documentation", [
        ("specifications.html", "Specifications", "spec"),
        ("requirements.html", "Requirements", "req"),
        ("architecture.html", "Architecture", "arch"),
        ("process.html", "Process Notes", "proc"),
    ]),
    ("Reference", [
        ("datasheets.html", "Datasheets", "chip"),
        ("issues.html", "Issues", "bug"),
        ("history.html", "History", "history"),
    ]),
]

ICONS = {
    "home":  '<path d="M3 9.5 10 4l7 5.5V17a1 1 0 0 1-1 1h-3v-5H7v5H4a1 1 0 0 1-1-1z"/>',
    "spec":  '<path d="M5 3h7l3 3v11a1 1 0 0 1-1 1H5a1 1 0 0 1-1-1V4a1 1 0 0 1 1-1z"/><path d="M7 9h6M7 12h6M7 15h4" stroke-width="1.4" fill="none"/>',
    "req":   '<path d="M4 4h12v12H4z" fill="none" stroke-width="1.4"/><path d="M7 8l2 2 4-4" fill="none" stroke-width="1.6"/><path d="M7 13h6" stroke-width="1.4" fill="none"/>',
    "arch":  '<rect x="3" y="3" width="5" height="5" rx="1"/><rect x="12" y="3" width="5" height="5" rx="1"/><rect x="7.5" y="12" width="5" height="5" rx="1"/><path d="M5.5 8v2h9V8M10 10v2" fill="none" stroke-width="1.3"/>',
    "proc":  '<circle cx="10" cy="10" r="6.5" fill="none" stroke-width="1.4"/><path d="M10 6v4l3 2" fill="none" stroke-width="1.5"/>',
    "chip":  '<rect x="5" y="5" width="10" height="10" rx="1.5"/><path d="M8 2v3M12 2v3M8 15v3M12 15v3M2 8h3M2 12h3M15 8h3M15 12h3" stroke-width="1.3"/>',
    "bug":   '<circle cx="10" cy="11" r="5" fill="none" stroke-width="1.5"/><path d="M10 6V3M6.5 7.5 4.5 5.5M13.5 7.5l2-2M4 11H1.5M18.5 11H16M6 14.5l-2 2M14 14.5l2 2" stroke-width="1.4" fill="none"/>',
    "history": '<circle cx="10" cy="10" r="7" fill="none" stroke-width="1.4"/><path d="M10 5.5V10l3 2" fill="none" stroke-width="1.5"/>',
}

LOGO_SVG = (
    '<svg class="logo" viewBox="0 0 32 32" xmlns="http://www.w3.org/2000/svg" aria-hidden="true">'
    '<rect width="32" height="32" rx="8" fill="#0a6c74"/>'
    '<path d="M16 6c-3.2 4.2-5.4 7.4-5.4 10.1A5.4 5.4 0 0 0 16 21.5a5.4 5.4 0 0 0 5.4-5.4C21.4 13.4 19.2 10.2 16 6z" fill="#fff"/>'
    '<circle cx="16" cy="16.4" r="1.8" fill="#0a6c74"/>'
    '</svg>'
)


def icon(name, cls="ico"):
    body = ICONS.get(name, "")
    return (f'<svg class="{cls}" viewBox="0 0 20 20" fill="currentColor" '
            f'xmlns="http://www.w3.org/2000/svg" aria-hidden="true">{body}</svg>')


def sidebar(active_href):
    out = ['<aside class="sidebar"><nav>']
    for group_title, items in NAV:
        out.append(f'<div class="navgroup"><div class="navgroup-title">{group_title}</div>')
        for href, label, ic in items:
            cls = " active" if href == active_href else ""
            out.append(f'<a class="navlink{cls}" href="{href}">{icon(ic)}<span>{html.escape(label)}</span></a>')
        out.append('</div>')
    out.append('</nav></aside>')
    return "".join(out)


def page(active_href, title, body, wide=False):
    wide_cls = " wide" if wide else ""
    return f"""<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>{html.escape(title)} · Fluispotter</title>
<link rel="stylesheet" href="styles.css">
</head>
<body>
<div class="app">
  <header class="topbar">
    <a class="brandmark" href="index.html">
      {LOGO_SVG}
      <span class="brandname">Fluispotter</span>
    </a>
    <span class="brandsub">Firmware &amp; Software Documentation</span>
    <span class="spacer"></span>
    <span class="topmeta">Project documentation site</span>
  </header>
  {sidebar(active_href)}
  <main class="main">
    <div class="content{wide_cls}">
      {body}
      <footer class="site-footer">
        Fluispotter project documentation &middot; generated static site &middot;
        fully offline, no external resources. Canonical specs are embedded live from <code>docs/</code>.
      </footer>
    </div>
  </main>
</div>
</body>
</html>
"""


def write(name, content):
    with open(os.path.join(HERE, name), "w", encoding="utf-8") as f:
        f.write(content)
    return name


# --------------------------------------------------------------------------
# Minimal, safe Markdown renderer (headings, lists, code, tables, paragraphs)
# --------------------------------------------------------------------------

def _inline(text):
    """Escape then apply inline code, bold, italics, links."""
    text = html.escape(text)
    # inline code first (protect contents)
    code_store = []

    def _stash(m):
        code_store.append(m.group(1))
        return f"\x00{len(code_store) - 1}\x00"

    text = re.sub(r"`([^`]+)`", _stash, text)
    # links [t](u)
    text = re.sub(r"\[([^\]]+)\]\(([^)]+)\)",
                  lambda m: f'<a href="{html.escape(m.group(2), quote=True)}">{m.group(1)}</a>', text)
    # bold then italic
    text = re.sub(r"\*\*([^*]+)\*\*", r"<strong>\1</strong>", text)
    text = re.sub(r"(?<!\*)\*(?!\*)([^*]+)\*(?!\*)", r"<em>\1</em>", text)
    # restore code
    text = re.sub(r"\x00(\d+)\x00", lambda m: f"<code>{code_store[int(m.group(1))]}</code>", text)
    return text


def render_markdown(md):
    lines = md.replace("\r\n", "\n").split("\n")
    out = []
    i = 0
    n = len(lines)
    para = []

    def flush_para():
        if para:
            out.append("<p>" + _inline(" ".join(para).strip()) + "</p>")
            para.clear()

    while i < n:
        line = lines[i]
        stripped = line.strip()

        # fenced code block
        if stripped.startswith("```"):
            flush_para()
            i += 1
            buf = []
            while i < n and not lines[i].strip().startswith("```"):
                buf.append(lines[i])
                i += 1
            i += 1  # skip closing fence
            out.append("<pre><code>" + html.escape("\n".join(buf)) + "</code></pre>")
            continue

        # blank line
        if stripped == "":
            flush_para()
            i += 1
            continue

        # horizontal rule
        if re.match(r"^(-{3,}|\*{3,}|_{3,})$", stripped):
            flush_para()
            out.append("<hr>")
            i += 1
            continue

        # heading
        m = re.match(r"^(#{1,6})\s+(.*)$", stripped)
        if m:
            flush_para()
            level = len(m.group(1))
            out.append(f"<h{level}>{_inline(m.group(2).strip())}</h{level}>")
            i += 1
            continue

        # table (header row | with a separator row of ---)
        if "|" in line and i + 1 < n and re.match(r"^\s*\|?[\s:|-]+\|[\s:|-]+$", lines[i + 1]):
            flush_para()
            header = [c.strip() for c in stripped.strip("|").split("|")]
            i += 2  # skip header + separator
            rows = []
            while i < n and "|" in lines[i] and lines[i].strip():
                rows.append([c.strip() for c in lines[i].strip().strip("|").split("|")])
                i += 1
            thead = "".join(f"<th>{_inline(c)}</th>" for c in header)
            tbody = ""
            for r in rows:
                # pad/truncate to header width
                cells = (r + [""] * len(header))[:len(header)]
                tbody += "<tr>" + "".join(f"<td>{_inline(c)}</td>" for c in cells) + "</tr>"
            out.append(f"<table><thead><tr>{thead}</tr></thead><tbody>{tbody}</tbody></table>")
            continue

        # unordered list
        if re.match(r"^\s*[-*+]\s+", line):
            flush_para()
            items = []
            while i < n and re.match(r"^\s*[-*+]\s+", lines[i]):
                items.append(re.sub(r"^\s*[-*+]\s+", "", lines[i]))
                i += 1
            out.append("<ul>" + "".join(f"<li>{_inline(it)}</li>" for it in items) + "</ul>")
            continue

        # ordered list
        if re.match(r"^\s*\d+\.\s+", line):
            flush_para()
            items = []
            while i < n and re.match(r"^\s*\d+\.\s+", lines[i]):
                items.append(re.sub(r"^\s*\d+\.\s+", "", lines[i]))
                i += 1
            out.append("<ol>" + "".join(f"<li>{_inline(it)}</li>" for it in items) + "</ol>")
            continue

        # blockquote
        if stripped.startswith(">"):
            flush_para()
            buf = []
            while i < n and lines[i].strip().startswith(">"):
                buf.append(re.sub(r"^\s*>\s?", "", lines[i]))
                i += 1
            out.append("<blockquote>" + _inline(" ".join(buf)) + "</blockquote>")
            continue

        para.append(stripped)
        i += 1

    flush_para()
    return "\n".join(out)


def read_doc(fname):
    with open(os.path.join(DOCS, fname), encoding="utf-8") as f:
        return f.read()


# --------------------------------------------------------------------------
# PAGE: index / overview
# --------------------------------------------------------------------------

def build_index():
    sections = [
        ("specifications.html", "Specification",
         "Authoritative device + application specifications, embedded live from the canonical HTML so they never drift."),
        ("requirements.html", "Requirements",
         "The generated, testable software & mechanical requirements registry (SWR-### IDs) with its .docx twin."),
        ("architecture.html", "Architecture",
         "Main-CPU firmware and ULP RISC-V pump-regulator design notes, the multi-mode ULP concept, and the firmware API reference."),
        ("process.html", "Process Notes",
         "CI / release process plan and the append-only conversation compacting log."),
        ("datasheets.html", "Datasheets",
         "Electronic component datasheets (MCU, DAC, light sensor, gearmotor, phototransistor) with their evidence-of-use."),
        ("history.html", "History",
         "Full git commit timeline plus the chronological user-prompt log from the development sessions."),
    ]
    cards = []
    for href, tag, blurb in sections:
        cards.append(f"""<a class="card" href="{href}">
  <span class="card-tag tag-{tag.split()[0]}">{html.escape(tag)}</span>
  <h3>{html.escape(tag)}</h3>
  <p>{html.escape(blurb)}</p>
  <span class="card-cta">Open &rarr;</span>
</a>""")

    body = f"""
<div class="pagehead">
  <div class="eyebrow">Fluispotter</div>
  <h1>Fluispotter firmware &amp; software documentation</h1>
  <p class="lead">A single, offline-capable home for the Fluispotter instrument's specifications,
  testable requirements, architecture notes, component datasheets, and full development history.</p>
</div>

<div class="panel">
  <h3 style="margin-top:0">The device</h3>
  <p style="color:var(--ink-soft)">Fluispotter is a battery-powered medical fluid-sampling instrument built on an
  <strong>ESP32-S3-WROOM-1</strong> module running <strong>MicroPython</strong>. Two Faulhaber 1512U
  gearmotors (324:1, integrated IE2-8 encoders) drive the AC and blood peristaltic pumps. Real-time,
  safety-relevant pump regulation is offloaded to a <strong>ULP RISC-V coprocessor</strong> that runs an
  independent control loop (the bench-validated Simple-P 16-tick regulator), keeping the main asyncio
  state machine free for the session sequence, sensors, and hub synchronization. Pump power is driven
  through a <strong>TI DAC7574</strong> quad DAC; fluid state is read from <strong>VEML6035</strong> spot/line
  light sensors and analog air/blood sensors.</p>

  <h3>The software stack</h3>
  <p style="color:var(--ink-soft)">Five shippable components: the ESP32-S3 firmware image, the three ULP
  binaries (operational / test / test2), the PyQt6 <strong>Monitor</strong> (passive telemetry) and
  <strong>Control</strong> (raw-REPL injection &amp; tuning) desktop apps, and the RPi synchronize-service.
  A machine-readable requirements registry generates the requirements document and drives the automated
  verification framework, gated in CI.</p>
</div>

{status_panel_html()}

<div class="stat-strip">
  <div class="stat"><div class="stat-num">{len(DOCUMENTS)}</div><div class="stat-label">documents catalogued</div></div>
  <div class="stat"><div class="stat-num">{len(DATASHEETS)}</div><div class="stat-label">component datasheets</div></div>
  <div class="stat"><div class="stat-num">{len(COMMITS)}</div><div class="stat-label">git commits</div></div>
  <div class="stat"><div class="stat-num">5</div><div class="stat-label">shippable components</div></div>
  <div class="stat"><div class="stat-num">{sum(1 for i in ISSUES if i["state"] == "OPEN") if ISSUES else "&mdash;"}</div><div class="stat-label">open issues</div></div>
</div>

<h2>Explore the documentation</h2>
<div class="card-grid">
{''.join(cards)}
</div>
"""
    return write("index.html", page("index.html", "Overview", body))


# --------------------------------------------------------------------------
# Doc-viewer pages (Specifications / Requirements / Architecture / Process)
# --------------------------------------------------------------------------

def kind_label(kind):
    return {"html": "HTML", "md": "Markdown", "rtf": "RTF", "docx": "Word", "pdf": "PDF"}.get(kind, kind.upper())


def render_html_viewer(doc, default=False):
    rel = "../" + doc["file"]
    return f"""<div class="doc-frame-wrap" id="view-{slug(doc['file'])}">
  <div class="doc-frame-bar">
    <span class="doc-title">{html.escape(doc['title'])}</span>
    <span class="doc-path">{html.escape(rel)}</span>
    <span class="spacer"></span>
    <a class="openlink" href="{rel}" target="_blank" rel="noopener">Open canonical file &nearr;</a>
  </div>
  <iframe class="docframe" src="{rel}" title="{html.escape(doc['title'])}" loading="lazy"></iframe>
</div>"""


def render_md_viewer(doc):
    md = read_doc(doc["file"])
    rendered = render_markdown(md)
    rel = "../" + doc["file"]
    return f"""<div class="doc-frame-wrap" id="view-{slug(doc['file'])}">
  <div class="doc-frame-bar">
    <span class="doc-title">{html.escape(doc['title'])}</span>
    <span class="doc-path">{html.escape(rel)}</span>
    <span class="spacer"></span>
    <a class="openlink" href="{rel}" target="_blank" rel="noopener">Open raw Markdown &nearr;</a>
  </div>
  <div class="md-body" style="padding:26px 30px">{rendered}</div>
</div>"""


def render_binary_viewer(doc):
    rel = "../" + doc["file"]
    klabel = kind_label(doc["kind"])
    return f"""<div class="panel" id="view-{slug(doc['file'])}">
  <span class="card-tag tag-{doc['category'].split()[0]}">{klabel} document</span>
  <h3 style="margin-top:10px">{html.escape(doc['title'])}</h3>
  <p style="color:var(--ink-soft)">{html.escape(doc['blurb'])}</p>
  <p style="color:var(--ink-soft); font-size:13.5px">This is a {klabel} file and is best opened in its native
  application. It is not embedded inline; use the link below to open or download the canonical file directly
  from <code>docs/</code> (relative path <code>{html.escape(rel)}</code>).</p>
  <a class="pdf-link" href="{rel}" target="_blank" rel="noopener">{pdf_icon()} Open / download {klabel}</a>
</div>"""


def slug(s):
    return re.sub(r"[^a-z0-9]+", "-", s.lower()).strip("-")


def build_doc_section(page_name, active_href, eyebrow, heading, lead, categories):
    docs = [d for d in DOCUMENTS if d["category"] in categories and d["file"] != "prompts.md"]
    # switcher
    switch = ['<div class="doc-switcher">']
    for idx, d in enumerate(docs):
        cls = " active" if idx == 0 else ""
        switch.append(f'<a class="{cls.strip()}" href="#view-{slug(d["file"])}" data-target="{slug(d["file"])}">{html.escape(d["title"])}</a>')
    switch.append('</div>')

    views = []
    for d in docs:
        if d["kind"] == "html":
            views.append(render_html_viewer(d))
        elif d["kind"] == "md":
            views.append(render_md_viewer(d))
        else:
            views.append(render_binary_viewer(d))

    # small client-side switcher (progressive enhancement; anchors work without JS)
    script = """
<script>
(function () {
  var links = document.querySelectorAll('.doc-switcher a');
  var views = document.querySelectorAll('.doc-frame-wrap, .panel[id^="view-"]');
  function show(id) {
    views.forEach(function (v) { v.style.display = (v.id === 'view-' + id) ? '' : 'none'; });
    links.forEach(function (l) { l.classList.toggle('active', l.dataset.target === id); });
  }
  links.forEach(function (l) {
    l.addEventListener('click', function (e) { e.preventDefault(); show(l.dataset.target); location.hash = l.dataset.target; });
  });
  var initial = location.hash.replace('#view-', '');
  if (initial && document.getElementById('view-' + initial)) { show(initial); }
  else if (links.length) { show(links[0].dataset.target); }
})();
</script>
"""

    body = f"""
<div class="pagehead">
  <div class="eyebrow">{html.escape(eyebrow)}</div>
  <h1>{html.escape(heading)}</h1>
  <p class="lead">{html.escape(lead)}</p>
</div>
{''.join(switch)}
{''.join(views)}
{script}
"""
    return write(page_name, page(active_href, heading, body, wide=True))


def pdf_icon():
    return ('<svg class="pdf-ico" viewBox="0 0 20 20" fill="currentColor" '
            'xmlns="http://www.w3.org/2000/svg" aria-hidden="true">'
            '<path d="M5 2h7l3 3v13a1 1 0 0 1-1 1H5a1 1 0 0 1-1-1V3a1 1 0 0 1 1-1z" '
            'fill="none" stroke="currentColor" stroke-width="1.3"/>'
            '<path d="M11 2v4h4" fill="none" stroke="currentColor" stroke-width="1.3"/>'
            '<text x="10" y="15" font-size="6" font-family="sans-serif" text-anchor="middle" '
            'fill="currentColor" font-weight="700">PDF</text></svg>')


# --------------------------------------------------------------------------
# PAGE: datasheets
# --------------------------------------------------------------------------

def build_datasheets():
    rows = []
    for d in DATASHEETS:
        rel = "datasheets/" + d["dest"]
        rows.append(f"""<tr>
  <td class="component">{html.escape(d['component'])}</td>
  <td class="evidence">{html.escape(d['evidence'])}</td>
  <td><a class="pdf-link" href="{rel}" target="_blank" rel="noopener">{pdf_icon()} Open PDF</a></td>
</tr>""")

    body = f"""
<div class="pagehead">
  <div class="eyebrow">Reference</div>
  <h1>Component datasheets</h1>
  <p class="lead">Datasheets for the electronic components used in the Fluispotter instrument. Each entry links
  to the PDF and notes the evidence establishing the part's use in the design.</p>
</div>

<div class="note">
  <strong>Note:</strong> the PDF files live under <code>docs/site/datasheets/</code> and are intentionally
  excluded from version control (they are large binaries). If a link does not resolve, the datasheet has not
  been copied into this checkout; the site HTML/CSS itself is committable.
</div>

<div class="table-wrap">
  <table class="data">
    <thead>
      <tr><th>Component</th><th>Evidence of use</th><th style="text-align:right">Datasheet</th></tr>
    </thead>
    <tbody>
      {''.join(rows)}
    </tbody>
  </table>
</div>
"""
    return write("datasheets.html", page("datasheets.html", "Datasheets", body))


# --------------------------------------------------------------------------
# PAGE: issues (GitHub issues with version + requirement traceability)
# --------------------------------------------------------------------------

def build_issues():
    def cell(v):
        return html.escape(v) if v else "&mdash;"
    rows = []
    ordered = sorted(ISSUES, key=lambda i: (i["state"] != "OPEN",
                                            -i["number"]))
    for i in ordered:
        badge = ('<span class="ci-badge %s">%s</span>'
                 % ("warn" if i["state"] == "OPEN" else "ok",
                    html.escape(i["state"])))
        swrs = ", ".join(i.get("swrs") or []) or None
        url = ("https://github.com/fluispotter/fluispotter-firmware/issues/%d"
               % i["number"])
        rows.append("""<tr>
  <td><a href="%s">#%d</a></td>
  <td class="issue-title">%s</td>
  <td>%s</td>
  <td>%s</td>
  <td>%s</td>
  <td>%s</td>
  <td>%s</td>
  <td>%s</td>
  <td class="issue-swrs">%s</td>
  <td class="issue-fix">%s</td>
</tr>""" % (url, i["number"], cell(i["title"]), badge, cell(i["created"]),
            cell(i.get("fw")), cell(i.get("ulp")), cell(i.get("image")),
            cell(i.get("hub")), cell(swrs), cell(i.get("fix"))))
    if rows:
        table = ("""<div class="panel" style="overflow-x:auto">
<table class="issues-table">
<tr><th>#</th><th>Title</th><th>State</th><th>Opened</th><th>Firmware</th>
<th>ULP</th><th>Image</th><th>Hub</th><th>Requirements</th><th>Fix</th></tr>
%s
</table>
</div>""" % "\n".join(rows))
    else:
        table = ('<div class="panel"><p style="color:var(--ink-soft)">No '
                 'issue data in this build (the refresh step ran without '
                 'GitHub access).</p></div>')
    body = """
<div class="pagehead">
  <div class="eyebrow">Reference</div>
  <h1>Issues</h1>
  <p class="lead">Every GitHub issue with its version association &mdash; the
  firmware, ULP, runtime image and hub versions it was seen on, the
  requirements it touches, and the fix versions.  Parsed from each issue's
  <em>Seen on</em> footer; an em-dash means that unit is not stamped in the
  footer (the issue body on GitHub remains authoritative).</p>
</div>
%s
""" % table
    return write("issues.html", page("issues.html", "Issues", body))


# --------------------------------------------------------------------------
# PAGE: history (git timeline + prompt log)
# --------------------------------------------------------------------------

def build_history():
    # --- git timeline (newest first; data already newest-first) ---
    commits_html = []
    for c in COMMITS:
        short = html.escape(c["hash"][:8])
        subject = html.escape(c["subject"])
        date = html.escape(c["date"])
        body_html = ""
        if c.get("body", "").strip():
            body_html = f'<div class="commit-body">{html.escape(c["body"])}</div>'
        commits_html.append(f"""<div class="commit">
  <div class="commit-head">
    <span class="commit-date">{date}</span>
    <span class="commit-hash">{short}</span>
  </div>
  <div class="commit-subject">{subject}</div>
  {body_html}
</div>""")

    # --- prompt log ---
    prompt_html = render_prompt_log(read_doc("prompts.md"))

    n_bodies = sum(1 for c in COMMITS if c.get("body", "").strip())

    body = f"""
<div class="pagehead">
  <div class="eyebrow">Reference</div>
  <h1>Development history</h1>
  <p class="lead">The complete record of the project's evolution: every git commit as a timeline, and the
  chronological log of user prompts from the Claude Code development sessions.</p>
</div>

<div class="section-tabs">
  <a href="#git" class="active" data-tab="git">Git history</a>
  <a href="#prompts" data-tab="prompts">Prompt log</a>
</div>

<section id="tab-git">
  <div class="history-meta">{len(COMMITS)} commits &middot; {n_bodies} with detailed bodies &middot; newest first</div>
  <div class="timeline">
    {''.join(commits_html)}
  </div>
</section>

<section id="tab-prompts" style="display:none">
  <div class="history-meta">User prompts from Claude Code sessions, grouped by session, with outcome annotations preserved.</div>
  {prompt_html}
</section>

<script>
(function () {{
  var tabs = document.querySelectorAll('.section-tabs a');
  var panes = {{ git: document.getElementById('tab-git'), prompts: document.getElementById('tab-prompts') }};
  function show(name) {{
    Object.keys(panes).forEach(function (k) {{ panes[k].style.display = (k === name) ? '' : 'none'; }});
    tabs.forEach(function (t) {{ t.classList.toggle('active', t.dataset.tab === name); }});
  }}
  tabs.forEach(function (t) {{
    t.addEventListener('click', function (e) {{ e.preventDefault(); show(t.dataset.tab); location.hash = t.dataset.tab; }});
  }});
  if (location.hash === '#prompts') show('prompts');
}})();
</script>
"""
    return write("history.html", page("history.html", "History", body, wide=True))


def render_prompt_log(md):
    """Parse prompts.md: '## <session>' headers, numbered prompt entries, and
    free-text outcome lines. Numbered items become prompt cards; non-numbered
    paragraphs that follow attach as outcome annotations."""
    lines = md.replace("\r\n", "\n").split("\n")
    out = []
    i = 0
    n = len(lines)
    in_session = False
    open_entry = False

    def close_entry():
        nonlocal open_entry
        if open_entry:
            out.append("</div></div>")  # close prompt-text + prompt-entry
            open_entry = False

    def close_session():
        nonlocal in_session
        close_entry()
        if in_session:
            out.append("</div>")  # close prompt-session
            in_session = False

    while i < n:
        line = lines[i]
        stripped = line.strip()

        # skip the doc title and intro/hr at the very top
        if stripped.startswith("# "):
            i += 1
            continue
        if stripped == "---":
            i += 1
            continue

        # session header
        m = re.match(r"^##\s+(.*)$", stripped)
        if m:
            close_session()
            out.append('<div class="prompt-session">')
            out.append(f"<h3>{_inline(m.group(1).strip())}</h3>")
            in_session = True
            i += 1
            continue

        # numbered prompt entry
        m = re.match(r"^(\d+)\.\s+(.*)$", stripped)
        if m:
            close_entry()
            if not in_session:
                out.append('<div class="prompt-session">')
                in_session = True
            num = m.group(1)
            text = m.group(2).strip()
            # split a leading "X → outcome" or detect outcome markers later
            out.append('<div class="prompt-entry">')
            out.append(f'<span class="prompt-num">{html.escape(num)}</span>')
            out.append('<div class="prompt-text">')
            # If the line itself contains an arrow outcome, split it.
            parts = re.split(r"\s+(?:→|->)\s+", text, maxsplit=1)
            if len(parts) == 2:
                out.append(_inline(parts[0].strip()))
                out.append(f'<span class="outcome">{_inline(parts[1].strip())}</span>')
            else:
                out.append(_inline(text))
            open_entry = True
            i += 1
            continue

        # blank line
        if stripped == "":
            i += 1
            continue

        # continuation / outcome text within an open entry or session
        if open_entry:
            out.append(f'<span class="outcome">{_inline(stripped)}</span>')
        elif in_session:
            # a stray bullet or note line inside a session, no numbered entry
            txt = re.sub(r"^[-*]\s+", "", stripped)
            out.append(f'<div class="prompt-entry"><span class="prompt-num">&middot;</span>'
                       f'<div class="prompt-text">{_inline(txt)}</div></div>')
        i += 1

    close_session()
    return "\n".join(out)


# --------------------------------------------------------------------------
# BUILD ALL
# --------------------------------------------------------------------------

def main():
    written = []
    written.append(build_index())
    written.append(build_doc_section(
        "specifications.html", "specifications.html", "Documentation", "Specifications",
        "Authoritative device and application specifications, embedded live from the canonical HTML in docs/ so they always reflect the latest edits.",
        {"Specification"}))
    written.append(build_doc_section(
        "requirements.html", "requirements.html", "Documentation", "Requirements",
        "The generated software & mechanical requirements registry (testable, ID'd SWR-### entries). A .docx twin is generated alongside the HTML.",
        {"Requirements"}))
    written.append(build_doc_section(
        "architecture.html", "architecture.html", "Documentation", "Architecture",
        "Firmware architecture: the main-CPU async state machine, the annotated ULP RISC-V pump regulator, the multi-mode ULP design note, and the firmware API reference.",
        {"Architecture"}))
    written.append(build_doc_section(
        "process.html", "process.html", "Documentation", "Process Notes",
        "Engineering process: the staged CI / release plan, and the append-only conversation compacting log.",
        {"Process"}))
    written.append(build_datasheets())
    written.append(build_issues())
    written.append(build_history())
    print("WROTE:", ", ".join(written))


if __name__ == "__main__":
    main()
