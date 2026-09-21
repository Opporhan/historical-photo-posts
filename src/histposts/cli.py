from __future__ import annotations

import argparse
import json
import re
import sys
from concurrent.futures import ThreadPoolExecutor
from datetime import UTC, datetime
from io import BytesIO
from pathlib import Path

import cv2
import numpy as np
import requests
import yaml
from PIL import Image, ImageDraw

from . import __version__, licensing
from .enhance import EnhanceError
from .http import get_bytes
from .models import Candidate, CaptionError
from .photocheck import is_monochrome, looks_like_photo
from .pipeline import SpecError, build_post, load_specs, series_counters
from .review import build_review
from .sources import search_all, wikimedia
from .video import VideoError

ICON = {licensing.SAFE: "✔", licensing.REVIEW: "?", licensing.BLOCKED: "✘"}


def slug(text: str) -> str:
    table = str.maketrans("çğıöşüÇĞİÖŞÜ", "cgiosuCGIOSU")
    return re.sub(r"[^a-z0-9]+", "-", text.translate(table).lower()).strip("-") or "search"


def _contact_sheet(thumbs: list[Image.Image], path: Path, cols: int = 5, cell: int = 300) -> None:
    rows = max(1, (len(thumbs) + cols - 1) // cols)
    sheet = Image.new("RGB", (cols * cell, rows * cell), "black")
    draw = ImageDraw.Draw(sheet)
    for i, thumb in enumerate(thumbs):
        t = thumb.copy()
        t.thumbnail((cell - 6, cell - 6))
        x, y = (i % cols) * cell, (i // cols) * cell
        sheet.paste(t, (x + 3, y + 3))
        draw.text((x + 8, y + 8), str(i), fill="yellow")
    sheet.save(path, quality=85)


def cmd_search(args: argparse.Namespace) -> int:
    names = args.sources.split(",") if args.sources else None
    candidates, notes = search_all(args.query, args.limit, args.category, names)
    for note in notes:
        print(f"  note: {note}", file=sys.stderr)

    def year_of(c: Candidate) -> int | None:
        return licensing.latest_year(c.date)

    words = [] if args.category else [w for w in re.findall(r"\w+", args.query.lower()) if len(w) >= 3]
    kept = []
    for c in candidates:
        text = f"{c.title} {c.description}".lower()
        if not all(re.search(rf"\b{re.escape(w)}\b", text) for w in words):
            continue  # unrelated (e.g. "Titan" for "Titanic")
        if (y := year_of(c)) and y > args.before:
            continue
        kept.append(c)

    def check(c: Candidate):
        try:
            im = Image.open(BytesIO(get_bytes(c.thumb or c.url))).convert("RGB")
            bgr = cv2.cvtColor(np.array(im), cv2.COLOR_RGB2BGR)
            ok, why = looks_like_photo(bgr, f"{c.title} {c.description[:200]}")
            if ok and not args.allow_color and not is_monochrome(bgr):
                ok, why = False, "renkli fotoğraf"
            return (im if ok else None), why
        except (requests.RequestException, OSError) as exc:
            return None, type(exc).__name__

    with ThreadPoolExecutor(max_workers=3) as pool:
        checked = list(pool.map(check, kept))
    good = [(c, im) for c, (im, _) in zip(kept, checked, strict=True) if im is not None]

    out = Path(args.out) / slug(args.query)
    out.mkdir(parents=True, exist_ok=True)
    (out / "candidates.json").write_text(
        json.dumps([c.to_dict() for c, _ in good], ensure_ascii=False, indent=1), encoding="utf-8"
    )
    _contact_sheet([im for _, im in good], out / "contact.jpg")
    for i, (c, _) in enumerate(good):
        verdict = licensing.classify(c)
        print(f"[{i}] {ICON[verdict.level]} {c.source} | {c.date[:14]} | {c.title[:60]} | {c.license}")
    print(f"\n{len(good)} photo candidates ({len(candidates)} found) -> {out / 'contact.jpg'}")
    print("✔ safe   ? review the source page   ✘ blocked")
    return 0


def cmd_check(args: argparse.Namespace) -> int:
    specs = load_specs(args.spec)
    counts = {licensing.SAFE: 0, licensing.REVIEW: 0, licensing.BLOCKED: 0}
    for spec in specs:
        verdict = licensing.classify(wikimedia.fetch_by_title(spec.file))
        counts[verdict.level] += 1
        print(f"{ICON[verdict.level]} {spec.name:<28} {verdict.level:<8} {'; '.join(verdict.reasons)}")
    print(f"\nsafe: {counts['safe']}  review: {counts['review']}  blocked: {counts['blocked']}")
    return 0


def cmd_build(args: argparse.Namespace) -> int:
    specs = load_specs(args.spec)
    if args.only:
        unknown = set(args.only) - {s.name for s in specs}
        if unknown:
            raise SpecError(f"unknown post name(s): {', '.join(sorted(unknown))}")
    out = Path(args.out)
    out.mkdir(parents=True, exist_ok=True)
    cache = Path(".histposts-cache")
    counters = series_counters(specs)
    report = []
    failed = []
    for n, spec in enumerate(specs, 1):
        if args.only and spec.name not in args.only:
            continue  # numbering always follows the position in the spec file
        try:
            result = build_post(
                spec,
                out / f"{n:02d}-{spec.name}",
                args.enhance,
                args.strict,
                cache,
                counters.get(spec.name, ""),
                args.allow_unverified,
                args.video,
            )
        except (requests.RequestException, LookupError, EnhanceError, VideoError, OSError) as exc:
            # One failing post (e.g. a rate-limited download) must not discard the rest of the batch.
            failed.append(spec.name)
            print(f"{n:02d} ✘ {spec.name:<28} FAILED — {type(exc).__name__}: {exc}")
            report.append({"name": spec.name, "level": "", "skipped": True, "failed": True, "note": str(exc)})
            continue
        state = "skipped" if result.skipped else f"ok ({result.method})"
        print(
            f"{n:02d} {ICON[result.level]} {spec.name:<28} {state}"
            + (f"  — {result.note}" if result.note else "")
        )
        report.append(
            {
                "name": spec.name,
                "level": result.level,
                "skipped": result.skipped,
                "method": result.method,
                "note": result.note,
            }
        )
    this_run = list(report)
    report_path = out / "license_report.json"
    if args.only and report_path.exists():  # partial rebuild: keep entries of the other posts
        rebuilt = {r["name"] for r in report}
        kept = [r for r in json.loads(report_path.read_text(encoding="utf-8")) if r["name"] not in rebuilt]
        report = kept + report
    report_path.write_text(json.dumps(report, ensure_ascii=False, indent=1), encoding="utf-8")
    built = sum(not r["skipped"] for r in this_run)
    print(f"\n{built}/{len(this_run)} posts written to {out}/")
    review = [r["name"] for r in this_run if r["level"] == licensing.REVIEW and not r["skipped"]]
    if review:
        print(f"check the source pages of: {', '.join(review)} (see license_evidence.json)")
    if failed:
        print(
            f"{len(failed)} failed: {', '.join(failed)}. "
            "Run the same command again; finished downloads are cached."
        )
        return 1
    return 0


def cmd_verify(args: argparse.Namespace) -> int:
    from . import verify

    specs = load_specs(args.spec)
    rows, counts = [], {verify.VERIFIED: 0, verify.US_ONLY: 0, verify.UNVERIFIED: 0}
    for spec in specs:
        c = wikimedia.fetch_by_title(spec.file)
        r = verify.verify(c, spec.author_qid, spec.author_died, spec.rights_source)
        counts[r.status] += 1
        print(f"{spec.name:<26} {r.status:<10} {'; '.join(r.basis or r.problems)[:110]}")
        rows.append((spec, c, r))
    print(
        f"\nverified: {counts['verified']}  us-only: {counts['us-only']}  unverified: {counts['unverified']}"
    )
    if args.write:
        lines = [
            "# License audit",
            "",
            f"Generated by `histposts verify` on {datetime.now(UTC).date()}. `verified` = public-domain "
            "template on the source page + author's life+70 term ended (or anonymous and old enough) + "
            "public domain in the US. Not legal advice.",
            "",
            "| Post | Status | Author | Died | Date | Basis | Sources |",
            "|---|---|---|---|---|---|---|",
        ]
        for spec, c, r in rows:
            basis = "; ".join(r.basis + r.problems).replace("|", "/")
            links = " ".join(f"[{i}]({u})" for i, u in enumerate(r.sources, 1))
            lines.append(
                f"| {spec.name} | {r.status} | {c.author[:40]} | {r.author_died or ''} | {c.date[:20]} "
                f"| {basis} | {links} |"
            )
        Path(args.write).write_text("\n".join(lines) + "\n", encoding="utf-8")
        print(f"written to {args.write}")
    return 0 if counts["unverified"] + counts["us-only"] == 0 else 1


def cmd_facts(args: argparse.Namespace) -> int:
    from . import factcheck

    checks = factcheck.run(factcheck.load_facts(args.facts))
    for c in checks:
        mark = "✔" if c.ok else "✘"
        detail = f"  missing: {', '.join(c.missing)}" if c.missing else (f"  {c.note}" if c.note else "")
        print(f"{mark} {c.post:<24} {c.article:<44} {c.claim[:60]}{detail}")
    bad = sum(not c.ok for c in checks)
    print(f"\n{len(checks) - bad}/{len(checks)} claims consistent with Wikipedia")
    if args.write:
        lines = [
            "# Fact check against Wikipedia",
            "",
            f"Generated by `histposts facts` on {datetime.now(UTC).date()} (MediaWiki API, no key). "
            "A check passes when every listed token appears in the article: consistent with Wikipedia, "
            "not proof.",
            "",
            "| Post | Claim | Article | Result |",
            "|---|---|---|---|",
        ]
        for c in checks:
            result = "consistent" if c.ok else "MISSING: " + ", ".join(c.missing or [c.note])
            lines.append(f"| {c.post} | {c.claim} | {c.article} | {result} |")
        Path(args.write).write_text("\n".join(lines) + "\n", encoding="utf-8")
    return 1 if bad else 0


def cmd_doctor(args: argparse.Namespace) -> int:
    from .doctor import check

    findings = check(load_specs(args.spec), Path(args.out))
    for f in findings:
        print(f"{'✘' if f.level == 'error' else '!'} {f.post:<28} {f.message}")
    errors = sum(f.level == "error" for f in findings)
    print(f"\n{errors} error(s), {len(findings) - errors} warning(s)")
    return 1 if errors else 0


def cmd_review(args: argparse.Namespace) -> int:
    print(build_review(Path(args.out)))
    return 0


def cmd_caption(args: argparse.Namespace) -> int:
    candidate = wikimedia.fetch_by_title(args.file)
    try:
        from .captions import generate_caption

        result = generate_caption(candidate, args.topic)
    except ImportError as exc:
        raise CaptionError(
            'caption drafts need the optional dependency: pip install -e ".[captions]"'
        ) from exc
    print(json.dumps(result.draft.model_dump(), ensure_ascii=False, indent=1))
    if result.needs_review:
        print("\nNEEDS REVIEW:")
        for item in result.needs_review:
            print(f"  - {item}")
    else:
        print("\nAll claims are supported by the source metadata.")
    return 0


def build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(prog="histposts", description=__doc__ or "Historical photo posts")
    p.add_argument("--version", action="version", version=f"histposts {__version__}")
    sub = p.add_subparsers(dest="command", required=True)

    s = sub.add_parser("search", help="find public-domain photo candidates and write a contact sheet")
    s.add_argument("query")
    s.add_argument("--category", help="Wikimedia Commons category to crawl instead of a text search")
    s.add_argument("--sources", help="comma-separated: wikimedia,nasa,smithsonian,met,europeana,nara")
    s.add_argument("--limit", type=int, default=15)
    s.add_argument("--before", type=int, default=1950, help="drop photos dated after this year")
    s.add_argument(
        "--allow-color", action="store_true", help="keep colour photographs (default: black-and-white only)"
    )
    s.add_argument("--out", default="output")
    s.set_defaults(func=cmd_search)

    c = sub.add_parser("check", help="license risk report for every post in a spec file")
    c.add_argument("spec")
    c.set_defaults(func=cmd_check)

    b = sub.add_parser("build", help="build Instagram (4:5) and TikTok (9:16) posts from a spec file")
    b.add_argument("spec")
    b.add_argument("--out", default="paylasima-hazir")
    b.add_argument("--strict", action="store_true", help="only build posts whose license level is 'safe'")
    b.add_argument("--enhance", choices=["auto", "gentle", "esrgan"], default="auto")
    b.add_argument(
        "--allow-unverified",
        action="store_true",
        help="also build posts whose rights are not verified worldwide (default: verified only)",
    )
    b.add_argument("--video", action="store_true", help="also write a short MP4 (needs ffmpeg)")
    b.add_argument("--only", nargs="+", metavar="NAME", help="build only these post names")
    b.set_defaults(func=cmd_build)

    v = sub.add_parser(
        "verify", help="evidence-based rights check of every post (author death year, templates)"
    )
    v.add_argument("spec")
    v.add_argument(
        "--write", metavar="FILE", help="also write a Markdown audit table (e.g. docs/license-audit.md)"
    )
    v.set_defaults(func=cmd_verify)

    f = sub.add_parser("facts", help="check claims against Wikipedia (no API key needed)")
    f.add_argument("facts", nargs="?", default="facts.yaml")
    f.add_argument("--write", metavar="FILE", help="also write a Markdown report (e.g. docs/fact-check.md)")
    f.set_defaults(func=cmd_facts)

    d = sub.add_parser("doctor", help="pre-publication checklist over the built posts")
    d.add_argument("spec")
    d.add_argument("--out", default="paylasima-hazir")
    d.set_defaults(func=cmd_doctor)

    r = sub.add_parser("review", help="write an HTML page with every built post and its license evidence")
    r.add_argument("--out", default="paylasima-hazir")
    r.set_defaults(func=cmd_review)

    k = sub.add_parser(
        "caption", help="draft a grounded Turkish caption with Claude (needs ANTHROPIC_API_KEY)"
    )
    k.add_argument("file", help="Wikimedia Commons file name")
    k.add_argument("--topic")
    k.set_defaults(func=cmd_caption)
    return p


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    try:
        return args.func(args)
    except (SpecError, LookupError, EnhanceError, CaptionError, yaml.YAMLError) as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 2
    except requests.RequestException as exc:
        print(f"network error: {exc}", file=sys.stderr)
        return 1
    except KeyboardInterrupt:
        return 130
