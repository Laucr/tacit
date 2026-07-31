#!/usr/bin/env python3
"""plumb — compare versions on .claude/{prds,plans,reports}/*.md
and report which features have stale plans, builds, or bailiff verdicts.

Stdlib only. Tiny `key: value` YAML parser, mirrors herald/scripts/render.py.

Tolerant of legacy artifacts that pre-date the frontmatter convention:
  - missing frontmatter → infer `version` from a `**Version:** N.M` body line,
    or a `_v<N.M>` filename suffix; fields show as `v3.7~` (~ = inferred).
  - missing `prd_version` on a plan/report → infer from the PRD's version
    closest in date (fallback: just check whether plan and PRD are within
    one minor rev — silent acceptance otherwise).
  - missing `feature` → fall back to filename stem with the `-build` /
    `-bailiff` / `-r<N>` suffixes stripped.

The script is standalone — it does not invoke any other skill. Use `--strict`
to fail CI on stale drift.

Usage:
    python drift_check.py
    python drift_check.py --feature emb-search
    python drift_check.py --strict
    python drift_check.py --report
    python drift_check.py --root /path/to/project
"""

from __future__ import annotations

import argparse
import os
import re
import sys
from dataclasses import dataclass, field
from pathlib import Path
from typing import Optional


# ── frontmatter parser ────────────────────────────────────────────────────

def split_yaml_frontmatter(text: str) -> dict:
    """If the document opens with --- ... ---, parse a tiny key:value YAML subset.
    Mirrors herald/scripts/render.py:split_yaml_frontmatter."""
    lines = text.splitlines()
    if not lines or lines[0].strip() != "---":
        return {}
    end = None
    for i in range(1, len(lines)):
        if lines[i].strip() == "---":
            end = i
            break
    if end is None:
        return {}
    fm: dict = {}
    for ln in lines[1:end]:
        if ":" in ln:
            k, v = ln.split(":", 1)
            v = v.strip()
            # strip trailing inline comments
            if "#" in v and not v.startswith("#"):
                v = v.split("#", 1)[0].rstrip()
            fm[k.strip()] = v.strip("\"'")
    return fm


# ── version comparison ───────────────────────────────────────────────────

def parse_version(s: str) -> Optional[tuple[int, int]]:
    """Parse semver-ish 'M.N' or plain 'M' into (major, minor). None on failure."""
    if not s:
        return None
    s = str(s).strip().lstrip("vV")
    if not s:
        return None
    parts = s.split(".")
    try:
        major = int(parts[0])
        minor = int(parts[1]) if len(parts) > 1 else 0
        return (major, minor)
    except (ValueError, IndexError):
        return None


def cmp_versions(a: Optional[str], b: Optional[str]) -> Optional[int]:
    """Return -1 if a<b, 0 if equal, 1 if a>b, None on parse failure."""
    pa, pb = parse_version(a or ""), parse_version(b or "")
    if pa is None or pb is None:
        return None
    if pa < pb:
        return -1
    if pa > pb:
        return 1
    return 0


def rev_distance(a: str, b: str) -> str:
    """Human-readable 'N minor revs ahead' / 'N major revs ahead' between two semver-ish strings."""
    pa, pb = parse_version(a), parse_version(b)
    if pa is None or pb is None:
        return "(unparseable versions)"
    if pa[0] != pb[0]:
        d = abs(pa[0] - pb[0])
        return f"{d} major rev{'s' if d != 1 else ''} ahead"
    d = abs(pa[1] - pb[1])
    return f"{d} minor rev{'s' if d != 1 else ''} ahead"


# ── artifact discovery ───────────────────────────────────────────────────

@dataclass
class Artifact:
    path: Path
    kind: str  # prd | plan | build | bailiff
    feature: str
    version: str
    prd_version: str = ""
    plan_version: str = ""
    last_aligned: str = ""
    status: str = "current"
    inferred: set[str] = field(default_factory=set)  # which fields were guessed


@dataclass
class FeatureView:
    feature: str
    prd: Optional[Artifact] = None
    plan: Optional[Artifact] = None
    build: Optional[Artifact] = None
    bailiff: Optional[Artifact] = None
    orphans: list[Artifact] = field(default_factory=list)


KIND_BY_DIR = {
    "prds": "prd",
    "plans": "plan",
    # reports/ holds both build and bailiff; disambiguate via filename or frontmatter
}


# ── legacy inference ─────────────────────────────────────────────────────

# Match `**Version:** 1.0`, `Version: 1.0`, `> **Version:** 1.0`, etc.
# Bold markers (`*`) can sit on either side of the key/value, and inside the
# colon, so we allow a `[*\s>]*` "fluff" run between every meaningful token.
BODY_VERSION_RE = re.compile(
    r"(?im)^[*\s>]*version[*\s]*[:：][*\s]*v?(\d+(?:\.\d+)?)"
)
# foo_v1.3.md  /  foo-v1.3.md  /  foo_plan_v1.3.md
FILENAME_VERSION_RE = re.compile(r"[_\-]v(\d+(?:\.\d+)?)$")
# `**PRD Version:** 1.0`, `Plan version: 2.1`, etc. — same fluff handling.
BODY_REF_VERSION_RE = re.compile(
    r"(?im)^[*\s>]*(prd|plan)[*\s]*version[*\s]*[:：][*\s]*v?(\d+(?:\.\d+)?)"
)
# `**Date:** 2026-06-26`
BODY_DATE_RE = re.compile(
    r"(?im)^[*\s>]*date[*\s]*[:：][*\s]*(\d{4}-\d{2}-\d{2})"
)


def infer_version_from_body(text: str) -> Optional[str]:
    m = BODY_VERSION_RE.search(text)
    return m.group(1) if m else None


def infer_version_from_filename(stem: str) -> Optional[str]:
    m = FILENAME_VERSION_RE.search(stem)
    return m.group(1) if m else None


def infer_ref_version(text: str, ref: str) -> Optional[str]:
    """ref: 'prd' | 'plan' — pulls 'PRD version: 1.0' style refs out of the body."""
    for m in BODY_REF_VERSION_RE.finditer(text):
        if m.group(1).lower() == ref:
            return m.group(2)
    return None


def infer_date_from_body(text: str) -> Optional[str]:
    m = BODY_DATE_RE.search(text)
    return m.group(1) if m else None


def infer_feature_from_filename(stem: str) -> str:
    """Strip -build / -bailiff / -inquest / -smoke / -drift / -r<N> / _v<N> / _prd / _plan suffixes."""
    s = stem
    s = re.sub(r"-r\d+$", "", s)
    s = re.sub(r"[_\-]v\d+(?:\.\d+)?$", "", s)
    for suf in ("-build", "-bailiff", "-inquest", "-smoke", "-drift",
                "-bailiff-codex",  # pre-existing convention in some repos
                "_prd", "_plan", "-prd", "-plan"):
        if s.endswith(suf):
            s = s[: -len(suf)]
            break
    return s


def detect_kind(path: Path, fm: dict) -> Optional[str]:
    if fm.get("artifact"):
        return fm["artifact"].strip().lower()
    parent = path.parent.name
    if parent in KIND_BY_DIR:
        return KIND_BY_DIR[parent]
    name = path.stem.lower()
    if name.endswith("-build") or "-build-" in name:
        return "build"
    if name.endswith("-bailiff") or "-bailiff-" in name:
        return "bailiff"
    if name.endswith("-drift") or "-drift-" in name:
        return None  # plumb's own output, ignore
    if name.endswith("-smoke") or "-smoke-" in name:
        return None  # legacy smoke-check output, ignore
    if name.endswith("-inquest") or "-inquest-" in name:
        return None  # inquest output, ignore
    return None


def load_artifact(path: Path) -> Optional[Artifact]:
    try:
        text = path.read_text(encoding="utf-8", errors="replace")
    except OSError:
        return None
    fm = split_yaml_frontmatter(text)
    kind = detect_kind(path, fm)
    if not kind:
        return None

    inferred: set[str] = set()

    feature = fm.get("feature")
    if not feature:
        feature = infer_feature_from_filename(path.stem)
        inferred.add("feature")

    version = fm.get("version", "")
    if not version:
        guess = infer_version_from_body(text) or infer_version_from_filename(path.stem)
        if guess:
            version = guess
            inferred.add("version")
    version = version.lstrip("vV")  # tolerate `**Version:** v1.0`

    prd_version = fm.get("prd_version", "")
    if not prd_version and kind in ("plan", "build", "bailiff"):
        guess = infer_ref_version(text, "prd")
        if guess:
            prd_version = guess
            inferred.add("prd_version")
    prd_version = prd_version.lstrip("vV")

    plan_version = fm.get("plan_version", "")
    if not plan_version and kind in ("build", "bailiff"):
        guess = infer_ref_version(text, "plan")
        if guess:
            plan_version = guess
            inferred.add("plan_version")
    plan_version = plan_version.lstrip("vV")

    last_aligned = fm.get("last_aligned", "")
    if not last_aligned:
        guess = infer_date_from_body(text)
        if guess:
            last_aligned = guess
            inferred.add("last_aligned")

    return Artifact(
        path=path,
        kind=kind,
        feature=feature,
        version=version,
        prd_version=prd_version,
        plan_version=plan_version,
        last_aligned=last_aligned,
        status=fm.get("status", "current"),
        inferred=inferred,
    )


def discover(root: Path) -> dict[str, FeatureView]:
    """Walk .claude/{prds,plans,reports} (or claude/ as a fallback) and group by feature."""
    if (root / ".claude").is_dir():
        base = root / ".claude"
    elif (root / "claude").is_dir():
        # Some legacy repos use claude/ (no leading dot).
        base = root / "claude"
    else:
        base = root
    candidates: list[Path] = []
    for sub in ("prds", "plans", "reports"):
        d = base / sub
        if d.is_dir():
            candidates.extend(p for p in d.glob("*.md") if p.is_file())

    features: dict[str, FeatureView] = {}
    for p in sorted(candidates):
        art = load_artifact(p)
        if art is None:
            continue
        if art.status == "superseded":
            continue
        fv = features.setdefault(art.feature, FeatureView(feature=art.feature))
        # Choose the newest current artifact per kind (highest version wins)
        slot = {"prd": "prd", "plan": "plan", "build": "build", "bailiff": "bailiff"}.get(art.kind)
        if slot is None:
            fv.orphans.append(art)
            continue
        existing = getattr(fv, slot)
        if existing is None or (cmp_versions(art.version, existing.version) or 0) > 0:
            setattr(fv, slot, art)
    return features


# ── drift judgement ──────────────────────────────────────────────────────

@dataclass
class Drift:
    artifact: str  # plan | build | bailiff
    severity: str  # CURRENT | STALE | WARN | UNKNOWN
    note: str = ""


def judge(view: FeatureView) -> dict[str, Drift]:
    out: dict[str, Drift] = {}
    prd = view.prd

    def soften_if_inferred(art: Artifact, sev: str) -> str:
        # If the comparison hinged on inferred fields, demote STALE → WARN.
        # The user shouldn't be told their plan is stale because we guessed
        # the version off a filename suffix.
        if sev == "STALE" and (art.inferred & {"version", "prd_version", "plan_version"}):
            return "WARN"
        return sev

    if view.plan:
        if not prd:
            out["plan"] = Drift("plan", "UNKNOWN", "no PRD found")
        elif not view.plan.prd_version and not prd.version:
            out["plan"] = Drift("plan", "LEGACY", "no version on either side")
        elif not view.plan.prd_version or not prd.version:
            out["plan"] = Drift("plan", "UNKNOWN", "frontmatter incomplete")
        else:
            c = cmp_versions(view.plan.prd_version, prd.version)
            if c == 0:
                out["plan"] = Drift("plan", "CURRENT")
            elif c is None:
                out["plan"] = Drift("plan", "UNKNOWN", "version unparseable")
            else:
                sev = soften_if_inferred(view.plan, "STALE")
                if c > 0:
                    # Plan claims a higher PRD version than the PRD itself —
                    # most likely the PRD frontmatter wasn't bumped. Don't
                    # cry "stale" at the user; ask them to reconcile.
                    out["plan"] = Drift("plan", "WARN",
                        f"plan claims newer prd_version than the PRD itself ({rev_distance(view.plan.prd_version, prd.version)})")
                else:
                    out["plan"] = Drift("plan", sev, f"prd {rev_distance(view.plan.prd_version, prd.version)}")

    if view.build:
        notes = []
        sev = "CURRENT"
        if not prd:
            sev, notes = "UNKNOWN", ["no PRD found"]
        elif not view.build.prd_version and not prd.version:
            sev, notes = "LEGACY", ["no version on either side"]
        else:
            c_prd = cmp_versions(view.build.prd_version, prd.version)
            if c_prd is None:
                sev = "UNKNOWN"; notes.append("prd_version unparseable")
            elif c_prd < 0:
                sev = "STALE"; notes.append(f"prd {rev_distance(view.build.prd_version, prd.version)}")
        if view.plan and view.build.plan_version and view.plan.version:
            c_plan = cmp_versions(view.build.plan_version, view.plan.version)
            if c_plan is not None and c_plan < 0:
                sev = "STALE" if sev != "STALE" else sev
                notes.append(f"plan {rev_distance(view.build.plan_version, view.plan.version)}")
        out["build"] = Drift("build", soften_if_inferred(view.build, sev), "; ".join(notes))

    if view.bailiff:
        notes = []
        sev = "CURRENT"
        if not prd:
            sev, notes = "UNKNOWN", ["no PRD found"]
        elif not view.bailiff.prd_version and not prd.version:
            sev, notes = "LEGACY", ["no version on either side"]
        else:
            c_prd = cmp_versions(view.bailiff.prd_version, prd.version)
            if c_prd is None:
                sev = "UNKNOWN"; notes.append("prd_version unparseable")
            elif c_prd < 0:
                sev = "STALE"; notes.append(f"prd {rev_distance(view.bailiff.prd_version, prd.version)} — verdict invalid")
        if view.plan and view.bailiff.plan_version and view.plan.version:
            c_plan = cmp_versions(view.bailiff.plan_version, view.plan.version)
            if c_plan is not None and c_plan < 0:
                if sev == "CURRENT":
                    sev = "WARN"
                notes.append(f"plan {rev_distance(view.bailiff.plan_version, view.plan.version)}")
        out["bailiff"] = Drift("bailiff", soften_if_inferred(view.bailiff, sev), "; ".join(notes))

    return out


# ── rendering ────────────────────────────────────────────────────────────

SEV_LABEL = {
    "CURRENT": "current",
    "STALE": "STALE",
    "WARN": "WARN",
    "UNKNOWN": "UNKNOWN",
    "LEGACY": "legacy",
}


def fmt_row(label: str, art: Optional[Artifact], drift: Optional[Drift]) -> str:
    if art is None:
        return f"  {label:<8} —"
    sev = SEV_LABEL.get(drift.severity, "current") if drift else "current"
    note = f"   {drift.note}" if drift and drift.note else ""
    inferred_mark = "~" if art.version and "version" in art.inferred else ""
    ver = f"v{art.version}{inferred_mark}" if art.version else "v?"
    date = art.last_aligned or "—"
    return f"  {label:<8} {ver:<9} {date:<12} {sev}{note}"


def render(features: dict[str, FeatureView], only: Optional[str] = None,
           legacy_quiet: bool = False) -> tuple[str, bool]:
    lines: list[str] = []
    any_stale = False
    keys = sorted(features.keys())
    if only:
        keys = [k for k in keys if only in k]
    legend_needed = False
    for k in keys:
        v = features[k]
        drifts = judge(v)
        # In --legacy-quiet mode, hide features whose only drift is UNKNOWN
        # (i.e. legacy artifacts with incomplete frontmatter — no actionable signal).
        if legacy_quiet:
            severities = {d.severity for d in drifts.values()}
            if severities and severities.issubset({"UNKNOWN", "LEGACY", "CURRENT"}):
                continue
        lines.append(f"{v.feature}:")
        lines.append(fmt_row("prd", v.prd, None))
        lines.append(fmt_row("plan", v.plan, drifts.get("plan")))
        lines.append(fmt_row("build", v.build, drifts.get("build")))
        lines.append(fmt_row("bailiff", v.bailiff, drifts.get("bailiff")))
        if v.orphans:
            for o in v.orphans:
                lines.append(f"  ORPHAN   {o.path.name} (kind={o.kind})")
        if any(d.severity == "STALE" for d in drifts.values()):
            any_stale = True
        for art in (v.prd, v.plan, v.build, v.bailiff):
            if art and art.inferred:
                legend_needed = True
        lines.append("")
    if not lines:
        if legacy_quiet:
            lines.append("(no features with actionable drift — re-run without --legacy-quiet to see legacy artifacts)")
        else:
            lines.append("(no features with frontmatter found)")
    if legend_needed:
        lines.append("legend: ~ = field inferred from body/filename (no frontmatter); legacy = no versions on either side")
    return "\n".join(lines), any_stale


def write_report(out_path: Path, body: str) -> None:
    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_text(f"# Drift Report\n\n```\n{body}\n```\n", encoding="utf-8")


# ── CLI ──────────────────────────────────────────────────────────────────

def main(argv: Optional[list[str]] = None) -> int:
    p = argparse.ArgumentParser(description="Detect drift between PRD/plan/build/bailiff via frontmatter.")
    p.add_argument("--root", default=os.getcwd(), help="Project root (default: cwd)")
    p.add_argument("--feature", default=None, help="Filter to one feature (substring match on slug)")
    p.add_argument("--strict", action="store_true", help="Exit 1 if any STALE drift is found")
    p.add_argument("--legacy-quiet", action="store_true",
                   help="Hide features whose only drift is UNKNOWN/LEGACY (no actionable signal). "
                        "Useful when most artifacts predate the frontmatter convention.")
    p.add_argument("--report", action="store_true", help="Also write .claude/reports/<feature>-drift.md")
    args = p.parse_args(argv)

    root = Path(args.root).resolve()
    features = discover(root)
    body, any_stale = render(features, args.feature, legacy_quiet=args.legacy_quiet)
    print(body)

    if args.report:
        base = root / ".claude" / "reports"
        if args.feature and args.feature in features:
            write_report(base / f"{args.feature}-drift.md", body)
            print(f"\n[wrote] {base / (args.feature + '-drift.md')}", file=sys.stderr)
        else:
            write_report(base / "drift.md", body)
            print(f"\n[wrote] {base / 'drift.md'}", file=sys.stderr)

    if args.strict and any_stale:
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
