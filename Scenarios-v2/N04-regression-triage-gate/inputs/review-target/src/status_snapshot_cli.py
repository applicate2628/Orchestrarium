from pathlib import Path

from .report_formatter import format_report


def run_status_snapshot(args, storage: Path, collect_report):
    report = collect_report(
        include_paused=args.include_paused,
        only_failed=args.only_failed,
    )
    persist_run_marker(storage, report["generated_at"])
    rendered = format_report(report, only_failed=args.only_failed)
    if args.dry_run:
        return rendered
    (storage / "last-report.txt").write_text(rendered, encoding="utf-8")
    return rendered


def persist_run_marker(storage: Path, generated_at: str) -> None:
    marker_path = storage / ".status-cache" / "last-run.json"
    marker_path.parent.mkdir(parents=True, exist_ok=True)
    marker_path.write_text(
        f'{{"generated_at":"{generated_at}"}}',
        encoding="utf-8",
    )
