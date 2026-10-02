from __future__ import annotations

import argparse
from pathlib import Path
import sys

from .crawler import crawl_sources, _market_matches
from .diff import build_diff_markdown
from .export import write_evidence, write_offer_details, write_prices, write_providers, write_summary
from .registry import load_registry
from .matching import default_alias_path
from .research_export import export_hf_v3, export_matched
from .validate import validate_csv


def _default_registry() -> Path:
    local = Path(__file__).resolve().parents[2] / "sources.yaml"
    return local if local.exists() else Path(__file__).with_name("sources.yaml")


def cmd_crawl(args: argparse.Namespace) -> int:
    out = Path(args.out)
    names = ["prices.csv", "offer-details.csv", "providers.csv", "evidence.jsonl", "crawl-summary.md"]
    if any((out / name).exists() for name in names):
        raise ValueError("Snapshot already exists; choose a new dated output directory")
    raw, sources = load_registry(args.sources)
    sources = [source for source in sources if source.enabled and _market_matches(source, args.market)]
    records, evidence = crawl_sources(
        sources,
        user_agent=raw.get("user_agent", "MandAPI-Price-Intelligence/0.1"),
        timeout_seconds=int(raw.get("default_timeout_seconds", 20)),
        market=args.market,
    )
    out = Path(args.out)
    out.mkdir(parents=True, exist_ok=True)
    write_prices(out / "prices.csv", records)
    write_offer_details(out / "offer-details.csv", records)
    write_providers(out / "providers.csv", sources)
    write_evidence(out / "evidence.jsonl", evidence)
    write_summary(out / "crawl-summary.md", records, evidence)
    print(f"wrote {len(records)} price records to {out}")
    return 0


def cmd_validate(args: argparse.Namespace) -> int:
    errors = validate_csv(args.input)
    if errors:
        for error in errors:
            print(f"ERROR: {error}", file=sys.stderr)
        return 1
    print("validation passed")
    return 0


def cmd_diff(args: argparse.Namespace) -> int:
    report = build_diff_markdown(args.old, args.new)
    Path(args.out).write_text(report + "\n", encoding="utf-8")
    print(f"wrote {args.out}")
    return 0


def cmd_match(args: argparse.Namespace) -> int:
    sample = export_matched(args.snapshot, args.out, args.aliases)
    print(f"wrote {len(sample.observations)} matched observations for "
          f"{len(sample.summary)} models; {len(sample.unresolved)} seller IDs unresolved")
    return 0


def cmd_hf_export(args: argparse.Namespace) -> int:
    sample = export_hf_v3(args.snapshot, args.out, args.aliases)
    print(f"wrote local Hugging Face V3 package to {args.out}: "
          f"{len(sample.summary)} matched models")
    return 0


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="mandapi-price-intel")
    sub = parser.add_subparsers(dest="command", required=True)

    crawl = sub.add_parser("crawl", help="crawl configured public pricing sources")
    crawl.add_argument("--market", default="brazil", choices=["brazil", "global"])
    crawl.add_argument("--out", required=True)
    crawl.add_argument("--sources", default=str(_default_registry()))
    crawl.set_defaults(func=cmd_crawl)

    validate = sub.add_parser("validate", help="validate a V2-compatible prices.csv")
    validate.add_argument("--input", required=True)
    validate.set_defaults(func=cmd_validate)

    diff = sub.add_parser("diff", help="compare two price snapshots")
    diff.add_argument("--old", required=True)
    diff.add_argument("--new", required=True)
    diff.add_argument("--out", required=True)
    diff.set_defaults(func=cmd_diff)

    match = sub.add_parser("match", help="export conservatively matched seller observations")
    match.add_argument("--snapshot", required=True, help="directory containing prices.csv")
    match.add_argument("--out", required=True)
    match.add_argument("--aliases", default=str(default_alias_path()))
    match.set_defaults(func=cmd_match)

    hf = sub.add_parser("hf-export", help="build a local Hugging Face V3 research package")
    hf.add_argument("--snapshot", required=True)
    hf.add_argument("--out", required=True)
    hf.add_argument("--aliases", default=str(default_alias_path()))
    hf.set_defaults(func=cmd_hf_export)

    return parser


def main() -> int:
    parser = build_parser()
    args = parser.parse_args()
    try:
        return args.func(args)
    except (ValueError, OSError) as exc:
        parser.exit(1, f"ERROR: {exc}\n")


if __name__ == "__main__":
    raise SystemExit(main())
