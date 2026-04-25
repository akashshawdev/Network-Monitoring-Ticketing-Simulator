"""
main.py
-------
Stage 7 & 8: Automation + Output

PURPOSE: The entry point that wires all components together into one
complete, automated pipeline:

  Issue Detected → Alert Fired → Ticket Created → Runbook Executed → Resolved

This demonstrates the full NOC automation loop that saves engineers from
manually creating tickets and ensures every issue is tracked.

REAL-WORLD PARALLEL:
  - PagerDuty auto-creates incidents from Datadog alerts
  - ServiceNow auto-routes tickets based on CMDB configuration
  - Ansible Playbooks auto-remediate known issues without human touch

HOW TO RUN:
  python main.py                # Full automated run (recommended first time)
  python main.py --mode demo    # Shorter demo with 3 issues
  python main.py --mode report  # Show tickets from previous run
"""

import os
import sys
import json
import argparse
import logging
from datetime import datetime

# Ensure project root is on path
sys.path.insert(0, os.path.dirname(__file__))

os.makedirs("logs",    exist_ok=True)
os.makedirs("tickets", exist_ok=True)
os.makedirs("data",    exist_ok=True)

from core.monitor         import NetworkMonitor, setup_logger
from core.ticketing       import TicketManager, TicketStatus
from core.troubleshooter  import Troubleshooter


# --------------------------------------------------------------------------
# Banner
# --------------------------------------------------------------------------

BANNER = """
╔══════════════════════════════════════════════════════════════╗
║        NETWORK MONITORING & TICKETING SIMULATOR              ║
║        Stage 1-8 | Full Automation Pipeline                  ║
╚══════════════════════════════════════════════════════════════╝
"""


# --------------------------------------------------------------------------
# Report printer — Stage 8 output
# --------------------------------------------------------------------------

def print_ticket_report(tm: TicketManager, logger: logging.Logger):
    """
    Prints a formatted summary of all tickets — mirrors what an L1/L2
    engineer would see on their NOC dashboard at the end of a shift.
    """
    tickets = tm.list_tickets()
    stats   = tm.stats()

    logger.info("\n" + "═" * 62)
    logger.info("  TICKET REPORT — END OF MONITORING CYCLE")
    logger.info("═" * 62)

    logger.info(f"\n  STATS:")
    logger.info(f"    Total tickets : {stats['total']}")
    logger.info(f"    Open          : {stats['open']}")
    logger.info(f"    In Progress   : {stats['in_progress']}")
    logger.info(f"    Resolved      : {stats['resolved']}")
    logger.info(f"    Critical (P1) : {stats['critical_p1']}")

    logger.info(f"\n  TICKET LIST:")
    logger.info(f"  {'─'*58}")
    for t in tickets:
        logger.info(f"  {t.summary_line()}")

    logger.info(f"\n  TICKET DETAILS:")
    for t in tickets:
        logger.info(f"\n  ┌─ {t.ticket_id} ─────────────────────")
        logger.info(f"  │  Title      : {t.title}")
        logger.info(f"  │  Priority   : {t.priority}  |  Status: {t.status.value}")
        logger.info(f"  │  Host       : {t.host}")
        logger.info(f"  │  Assigned   : {t.assigned_to}")
        logger.info(f"  │  Created    : {t.created_at}")
        if t.resolved_at:
            logger.info(f"  │  Resolved   : {t.resolved_at}")
        if t.resolution:
            logger.info(f"  │  Resolution : {t.resolution}")
        logger.info(f"  │  History ({len(t.history)} events):")
        for h in t.history:
            logger.info(f"  │    [{h['at']}] {h['by']}: {h['event']}")
        logger.info(f"  └{'─'*50}")

    logger.info("\n" + "═" * 62)


# --------------------------------------------------------------------------
# Main pipeline
# --------------------------------------------------------------------------

def run_pipeline(mode: str = "full"):
    logger = setup_logger("logs/monitor.log")
    print(BANNER)

    # ── Component initialisation ──────────────────────────────────────────
    logger.info("Initialising components...")
    tm             = TicketManager()
    troubleshooter = Troubleshooter(tm, logger)
    created_tickets = []

    # ── Stage 7: Automation callback ─────────────────────────────────────
    # When the monitor fires an alert, this function runs automatically.
    # No human needed to create the ticket — it just appears.
    def on_alert(issue):
        ticket = tm.create_ticket(issue)
        logger.info(
            f"  🎫 AUTO-TICKET CREATED: {ticket.ticket_id} "
            f"[{ticket.priority}] for {issue.issue_id}"
        )
        created_tickets.append(ticket.ticket_id)

    # ── Stage 4: Monitoring ───────────────────────────────────────────────
    monitor = NetworkMonitor(logger=logger, on_alert=on_alert)

    cycles      = 2 if mode == "demo" else 3
    issue_count = 2 if mode == "demo" else 4

    logger.info(f"\n▶  PHASE 1 — MONITORING  (mode={mode})")
    for cycle in range(1, cycles + 1):
        logger.info(f"\n--- Monitoring Cycle {cycle}/{cycles} ---")
        monitor.check_once(issue_count)

    # ── Stage 6 & 7: Auto-troubleshoot all open tickets ──────────────────
    open_tickets = tm.list_tickets(status=TicketStatus.OPEN)
    logger.info(f"\n▶  PHASE 2 — AUTO-RESOLUTION  ({len(open_tickets)} open tickets)")

    for ticket in open_tickets:
        troubleshooter.resolve(ticket.ticket_id, simulate_delay=True)

    # ── Stage 8: Output ───────────────────────────────────────────────────
    logger.info(f"\n▶  PHASE 3 — FINAL REPORT")
    print_ticket_report(tm, logger)

    # Save JSON export for inspection
    export = {
        "run_at":  datetime.now().isoformat(timespec="seconds"),
        "mode":    mode,
        "tickets": [t.to_dict() for t in tm.list_tickets()],
        "stats":   tm.stats(),
    }
    with open("data/last_run.json", "w") as f:
        json.dump(export, f, indent=2)
    logger.info(f"\n  📄 Full JSON export saved to data/last_run.json")
    logger.info(f"  📝 Full log saved to logs/monitor.log")
    logger.info(f"\n  Pipeline complete. ✓\n")


# --------------------------------------------------------------------------
# Entry point
# --------------------------------------------------------------------------

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Network Monitor & Ticketing Simulator")
    parser.add_argument(
        "--mode",
        choices=["full", "demo", "report"],
        default="full",
        help="full=3 cycles / demo=2 cycles / report=show existing tickets",
    )
    args = parser.parse_args()

    if args.mode == "report":
        logger = setup_logger("logs/monitor.log")
        tm     = TicketManager()
        print_ticket_report(tm, logger)
    else:
        run_pipeline(mode=args.mode)
