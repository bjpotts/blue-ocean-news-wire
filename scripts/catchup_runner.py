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
        "hour": 7,
        "pdf_glob": "market-wrap-up-*-am.pdf",
    },
}


def latest_pdf_for_date(project, glob, run_date):
    """Return the newest PDF matching glob whose filename date == run_date and
    whose filesystem mtime is on or after that day's scheduled run hour.

    A manual early-morning run can create a -pm PDF for today, but it must not
    count as covering the scheduled 18:00 Evening Edition. Creation-time check
    catches that.
    """
    pattern = re.compile(r"market-wrap-up-(\d{4}-\d{2}-\d{2})-(am|pm)\.pdf")
    candidates = []
    for p in Path(project).glob(glob):
        m = pattern.search(p.name)
        if not m:
            continue
        file_date = datetime.strptime(m.group(1), "%Y-%m-%d").date()
        if file_date != run_date:
            continue
        mtime = datetime.fromtimestamp(p.stat().st_mtime)
        candidates.append((mtime, p))
    if not candidates:
        return None
    candidates.sort(reverse=True)
    return candidates[0][1]


def latest_pdf_date(project, glob):
    """Return the latest filename date among all matching PDFs."""
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

    expected = expected_runs(edition_cfg, now_syd)
    if not expected:
        return False, "no scheduled runs have passed yet today"

    # Find any scheduled run date that does not have a PDF created at/after
    # its scheduled hour. Manual runs outside the scheduled window create a
    # PDF with the right filename but the wrong timestamp, so they don't mask
    # a missed scheduled run.
    missing = []
    for d in sorted(expected):
        pdf = latest_pdf_for_date(edition_cfg["project"], edition_cfg["pdf_glob"], d)
        if pdf is None:
            missing.append(d)
            continue
        scheduled = datetime(d.year, d.month, d.day, edition_cfg["hour"], 0)
        mtime = datetime.fromtimestamp(pdf.stat().st_mtime)
        if mtime < scheduled:
            missing.append(d)

    if not missing:
        latest = latest_pdf_date(edition_cfg["project"], edition_cfg["pdf_glob"])
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
