def format_report(report: dict[str, object], only_failed: bool = False) -> str:
    visible_jobs = list(report["visible_jobs"])
    all_jobs = list(report["all_jobs"])
    lines = [str(report["title"])]
    lines.extend(build_rows(visible_jobs))
    lines.append(build_footer(visible_jobs, all_jobs, only_failed=only_failed))
    return "\n".join(lines)


def build_rows(visible_jobs: list[dict[str, object]]) -> list[str]:
    return [f"- {job['name']}: {job['status']}" for job in visible_jobs]


def build_footer(
    visible_jobs: list[dict[str, object]],
    all_jobs: list[dict[str, object]],
    only_failed: bool = False,
) -> str:
    if only_failed:
        return f"{len(all_jobs)} total jobs shown in failure view"
    return f"{len(all_jobs)} total jobs"
