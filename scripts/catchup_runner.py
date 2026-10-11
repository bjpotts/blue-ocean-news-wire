#!/usr/bin/env python3
"""Catch-up runner: execute a scheduled Market Wrap Up edition if it was missed.

Designed to be invoked via launchctl with RunAtLoad. It compares the most
recent local PDF filename against the expected schedule. If a scheduled run
was missed because the machine was off, it triggers the edition's run_daily.sh.

Evening Edition: Mon-Fri at 18:00 Australia/Sydney.
Morning Edition: Mon-Sat at 08:00 Australia/Sydney.
"""
import argparse
import os
import re
import subprocess
import sys
from datetime import datetime, timedelta
from pathlib import Path

SYDNEY_TZ = "Australia/Sydney"

PROJECTS = {
    "evening": {
        "name": "Evening Edition",
        "project": "/Users/brandonpotts/.verdent/verdent-projects/run-the-public-news",
        "weekdays": {1, 2, 3, 4, 5},
        "hour": 18,
        "pdf_glob": "market-wrap-up-*-pm.pdf",
    },
    "morning": {
        "name": "Morning Edition",
        "project": "/Users/brandonpotts/.verdent/verdent-projects/run-the-public-news-morning",
        "weekdays": {1, 2, 3, 4, 5, 6},
        "hour": 8,
        "pdf_glob": "market-wrap-up-*-am.pdf",
    },
}


def latest_pdf_date(project, glob):
    pattern = re.compile(r"market-wrap-up-(\d{4}-\d{2}-\d{2})-(am|pm)\.pdf")
    dates = []
    for p in Path(project).glob(glob):
        m = pattern.search(p.name)
        if m:
            dates.append(datetime.strptime(m.group(1), "%Y-%m-%d").date())
    return max(dates) if dates else None


def expected_runs(edition_cfg, now):
    """Return the set of scheduled run dates that should have happened by now."""
    expected = set()
    today = now.date()
    for days_back in range(0, 7):
        d = today - timedelta(days=days_back)
        if d.weekday() + 1 in edition_cfg["weekdays"]:
            run_time = datetime(d.year, d.month, d.day, edition_cfg["hour"], 0)
            if run_time <= now:
                expected.add(d)
    return expected


def needs_run(edition_cfg):
    # Use Sydney local time so we align with the schedule.
    os.environ["TZ"] = SYDNEY_TZ
    import time as _time
    _time.tzset()
    now_syd = datetime.fromtimestamp(_time.time())

    latest = latest_pdf_date(edition_cfg["project"], edition_cfg["pdf_glob"])
    expected = expected_runs(edition_cfg, now_syd)

    if not expected:
        return False, "no scheduled runs have passed yet today"

    if latest is None:
        return True, "no local PDF found; at least one run is overdue"

    # Find any scheduled run date that does not have a PDF on or after it.
    # This catches gaps: if Sat is missed but a later manual run exists, we
    # still want to backfill Saturday before moving on.
    missing = [d for d in sorted(expected) if d > latest]
    if not missing:
        return False, "latest PDF %s covers all scheduled runs so far" % latest

    return True, "missed scheduled runs: %s" % ", ".join(str(d) for d in missing)


def run_edition(edition_cfg):
    script = os.path.join(edition_cfg["project"], "scripts", "run_daily.sh")
    print("CATCH-UP: starting %s via %s" % (edition_cfg["name"], script))
    result = subprocess.run(["/bin/bash", script], cwd=edition_cfg["project"])
    return result.returncode == 0


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--edition", choices=["morning", "evening", "both"], default="both")
    parser.add_argument("--dry-run", action="store_true")
    args = parser.parse_args()

    editions = ["morning", "evening"] if args.edition == "both" else [args.edition]
    any_action = False
    exit_code = 0

    for key in editions:
        cfg = PROJECTS[key]
        overdue, reason = needs_run(cfg)
        print("%s: %s (%s)" % (cfg["name"], "OVERDUE" if overdue else "OK", reason))
        if overdue:
            any_action = True
            if args.dry_run:
                print("  DRY RUN: would execute %s" % cfg["project"])
            else:
                if not run_edition(cfg):
                    exit_code = 1

    if not any_action:
        print("No catch-up runs needed.")
    return exit_code


if __name__ == "__main__":
    sys.exit(main())
