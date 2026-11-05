"""Backtest: rebuild past gigs from published data and compare with the schedules the band actually used.

    python3 -m logistics.backtest            # report for both modes
    python3 -m logistics.backtest --mode defaults
"""

from __future__ import annotations

import argparse
import json
import sys
from dataclasses import dataclass, field
from datetime import date, datetime
from pathlib import Path
from typing import Optional

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from gig_calendar import extract_address  # noqa: E402
from logistics.actuals import ActualSchedule, parse_actual  # noqa: E402
from logistics.profiles import LogisticsConfig, load_config  # noqa: E402
from logistics.render import fmt_time, render_markdown  # noqa: E402
from logistics.schedule import MILESTONES, GigInput, LogisticsSchedule, build_schedule, parse_clock  # noqa: E402

FIXTURES = ROOT / "tests" / "fixtures" / "logistics"
MODES = ("profiles", "defaults")


@dataclass
class MilestoneDiff:
    name: str
    actual: datetime
    predicted: Optional[datetime]

    @property
    def delta_minutes(self) -> Optional[int]:
        if self.predicted is None:
            return None
        return int((self.predicted - self.actual).total_seconds() // 60)


@dataclass
class GigResult:
    label: str
    mode: str
    schedule: LogisticsSchedule
    actual: ActualSchedule
    diffs: list[MilestoneDiff] = field(default_factory=list)
    travel_actual: Optional[int] = None
    travel_predicted: Optional[int] = None

    @property
    def matched(self) -> int:
        return sum(1 for d in self.diffs if d.delta_minutes == 0)

    @property
    def max_abs_error(self) -> Optional[int]:
        deltas = [abs(d.delta_minutes) for d in self.diffs if d.delta_minutes is not None]
        return max(deltas) if deltas else None

    def delta(self, name: str) -> Optional[int]:
        return next((d.delta_minutes for d in self.diffs if d.name == name), None)


def load_backtest_gigs(path: Path = FIXTURES / "backtest_gigs.json") -> list[dict]:
    return json.loads(path.read_text(encoding="utf-8"))["gigs"]


def gig_input_from_fixture(row: dict) -> GigInput:
    return GigInput(
        event_date=date.fromisoformat(row["date"]),
        start=parse_clock(row["time"]),  # type: ignore[arg-type]
        end=parse_clock(row.get("end_time", "")),
        title=row["title"],
        address=extract_address(row["title"]),
    )


def compare(schedule: LogisticsSchedule, actual: ActualSchedule) -> list[MilestoneDiff]:
    return [
        MilestoneDiff(name, actual.milestones[name], schedule.milestones.get(name))
        for name in MILESTONES
        if name in actual.milestones
    ]


def run_gig(row: dict, mode: str, config: Optional[LogisticsConfig] = None) -> GigResult:
    config = config or load_config()
    gig = gig_input_from_fixture(row)
    profile = config.match_venue(gig.title)
    if profile is None:
        raise ValueError(f"No venue profile matches backtest gig {row['title']!r}")
    if mode == "defaults":
        profile = config.defaults_profile(profile)
    schedule = build_schedule(gig, config=config, profile=profile, revised=bool(row.get("revised")))
    actual = parse_actual((FIXTURES / "actuals" / row["actual"]).read_text(encoding="utf-8"))
    return GigResult(
        label=Path(row["actual"]).stem,
        mode=mode,
        schedule=schedule,
        actual=actual,
        diffs=compare(schedule, actual),
        travel_actual=actual.travel_minutes,
        travel_predicted=schedule.travel_minutes,
    )


def run_backtest(mode: str, config: Optional[LogisticsConfig] = None) -> list[GigResult]:
    return [run_gig(row, mode, config) for row in load_backtest_gigs()]


def _fmt_delta(delta: Optional[int]) -> str:
    if delta is None:
        return "missing"
    if delta == 0:
        return "exact"
    return f"{delta:+d} min"


def format_report(results: list[GigResult], *, detail: bool = True) -> str:
    mode = results[0].mode if results else ""
    title = {
        "profiles": "Calibrated (venue profiles)",
        "defaults": "Cold start (standard timing + known drive time)",
    }.get(mode, mode)
    out = [f"## Backtest — {title}", ""]
    out.append("| Gig | Milestones exact | Pull-out | Arrival | Dead stage | Max error |")
    out.append("|---|---|---|---|---|---|")
    total = exact = 0
    for r in results:
        total += len(r.diffs)
        exact += r.matched
        max_err = r.max_abs_error
        out.append(
            f"| {r.label} | {r.matched}/{len(r.diffs)} | {_fmt_delta(r.delta('pull_out'))} | "
            f"{_fmt_delta(r.delta('arrival'))} | {_fmt_delta(r.delta('dead_stage'))} | "
            f"{'—' if max_err is None else f'{max_err} min'} |"
        )
    out += ["", f"Overall: {exact}/{total} milestones exact.", ""]
    if detail:
        for r in results:
            misses = [d for d in r.diffs if d.delta_minutes != 0]
            if not misses:
                continue
            out.append(f"**{r.label}** differences:")
            for d in misses:
                predicted = fmt_time(d.predicted) if d.predicted else "—"
                out.append(f"- {d.name}: actual {fmt_time(d.actual)}, predicted {predicted} ({_fmt_delta(d.delta_minutes)})")
            out.append("")
    return "\n".join(out)


def main(argv: Optional[list[str]] = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--mode", choices=(*MODES, "both"), default="both")
    parser.add_argument("--show-schedules", action="store_true", help="Print each predicted schedule")
    args = parser.parse_args(argv)
    modes = MODES if args.mode == "both" else (args.mode,)
    for mode in modes:
        results = run_backtest(mode)
        print(format_report(results))
        if args.show_schedules:
            for r in results:
                print(f"### {r.label} ({mode})\n")
                print(render_markdown(r.schedule))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
