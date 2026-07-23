#!/usr/bin/env python3
"""Refresh the project-site data sidecars from the live repo state.

Writes (into docs/site/):
  _commits.json — newest-first git log (hash / date / subject / body), 300
  _status.json  — component versions, requirements registry, CI snapshot,
                  latest commit, generation timestamp

Run from anywhere inside the repo, then rebuild the pages:

    python3 docs/site/_refresh_data.py
    python3 docs/site/_build_site.py

The documentation workflow runs both on every publish (owner instruction
2026-07-23: the published site had a June-12 commits snapshot and no status
at all), so the site can no longer drift from the repo.  The CI snapshot
comes from `gh` when available (GH_TOKEN suffices on Actions runners) and
degrades to an empty list offline.  NOTE: `git log` needs real history —
the workflow checkout uses fetch-depth: 0.
"""
import datetime
import json
import os
import re
import subprocess

HERE = os.path.dirname(os.path.abspath(__file__))
REPO = os.path.abspath(os.path.join(HERE, '..', '..'))


def sh(*args):
    return subprocess.run(args, capture_output=True, text=True, cwd=REPO)


# --- commits ------------------------------------------------------------
SEP, EOR = '\x1f', '\x1e'
r = sh('git', 'log', '-n', '300',
       '--pretty=format:%H' + SEP + '%as' + SEP + '%s' + SEP + '%b' + EOR)
commits = []
for rec in r.stdout.split(EOR):
    rec = rec.strip('\n')
    if not rec:
        continue
    h, date, subject, body = (rec.split(SEP) + ['', '', '', ''])[:4]
    commits.append({'hash': h, 'date': date, 'subject': subject,
                    'body': body.strip()})
with open(os.path.join(HERE, '_commits.json'), 'w', encoding='utf-8') as f:
    json.dump(commits, f, ensure_ascii=False, indent=0)
print('_commits.json: %d commits (latest %s %s)'
      % (len(commits), commits[0]['date'] if commits else '?',
         commits[0]['hash'][:8] if commits else '?'))


# --- versions -----------------------------------------------------------
def rx(path, pattern):
    try:
        with open(os.path.join(REPO, path), encoding='utf-8') as f:
            m = re.search(pattern, f.read())
        return m.group(1) if m else None
    except OSError:
        return None


def op_ulp_version():
    """Operational ULP version from main.c: of every ULP_VERSION_* triple,
    take the one whose preceding context names no TEST build (the
    operational #else branch)."""
    try:
        with open(os.path.join(
                REPO, 'esp32/pump_regulator/main/ulp/main.c'),
                encoding='utf-8') as f:
            src = f.read()
    except OSError:
        return None
    best = None
    for m in re.finditer(
            r'define\s+ULP_VERSION_MAJOR\s+(\d+)\s*(?:/\*.*?\*/\s*)?.*?'
            r'define\s+ULP_VERSION_MINOR\s+(\d+).*?'
            r'define\s+ULP_VERSION_PATCH\s+(\d+)', src, re.S):
        ctx = src[max(0, m.start() - 400):m.start()]
        if 'TESTOP' in ctx or 'TEST2' in ctx or 'ULP_TEST' in ctx:
            continue
        best = '%s.%s.%s' % m.groups()
    return best


def requirements_summary():
    path = os.path.join(REPO, 'verification/requirements.py')
    try:
        with open(path, encoding='utf-8') as f:
            src = f.read()
    except OSError:
        return None
    return {
        'doc_version': (re.search(r"DOC_VERSION = '([^']+)'", src) or
                        [None, None])[1],
        'total': len(re.findall(r"'[A-Z]+-\d+': _r\(", src)),
    }


# --- CI snapshot (graceful offline) -------------------------------------
ci = []
r = sh('gh', 'run', 'list', '--limit', '12', '--json',
       'workflowName,headBranch,conclusion,status,updatedAt')
if r.returncode == 0 and r.stdout.strip():
    try:
        for run in json.loads(r.stdout):
            ci.append({k: run.get(k) for k in (
                'workflowName', 'headBranch', 'conclusion', 'status',
                'updatedAt')})
    except ValueError:
        pass

status = {
    'generated_at': datetime.datetime.now(datetime.timezone.utc)
                    .isoformat(timespec='seconds'),
    'firmware_version': rx('fluispotter/version.py',
                           r'__version__ = "([^"]+)"'),
    'ulp_operational': op_ulp_version(),
    'hub_service': rx(
        'lib/synchronize-service/synchronize_service/version.py',
        r"SERVICE_VERSION = '([^']+)'"),
    'requirements': requirements_summary(),
    'ci': ci,
    'latest_commit': commits[0] if commits else None,
}
with open(os.path.join(HERE, '_status.json'), 'w', encoding='utf-8') as f:
    json.dump(status, f, ensure_ascii=False, indent=1)
print('_status.json:', json.dumps(
    {k: v for k, v in status.items() if k not in ('ci', 'latest_commit')}))
print('  ci runs captured:', len(ci))
