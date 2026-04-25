"""
monitor.py
----------
Stage 4: Monitoring Logic

PURPOSE: Continuously (or on-demand) checks for new issues, evaluates
severity thresholds, and fires alerts. This is the "always-on" brain
of a NOC — equivalent to Nagios, Zabbix, or PRTG in production.

HOW IT WORKS:
  1. Poll the IssueSimulator at a set interval
  2. Evaluate each issue against threshold rules
  3. Emit alert events that the ticketing system can consume
  4. Log everything for audit trail

REAL-WORLD PARALLEL:
  - Zabbix triggers → alert actions
  - PRTG sensors → notifications
  - AWS CloudWatch alarms → SNS topics
"""

import time
import logging
from datetime import datetime
from typing import Callable, Optional

from core.issue_simulator import IssueSimulator, NetworkIssue


# --------------------------------------------------------------------------
# Logging setup — every alert gets written to a structured log file
# --------------------------------------------------------------------------

def setup_logger(log_path: str = "logs/monitor.log") -> logging.Logger:
    logger = logging.getLogger("NetMonitor")
    logger.setLevel(logging.DEBUG)

    fmt = logging.Formatter(
        "%(asctime)s | %(levelname)-8s | %(message)s",
        datefmt="%Y-%m-%d %H:%M:%S",
    )

    # Console handler — you see alerts in the terminal
    ch = logging.StreamHandler()
    ch.setLevel(logging.INFO)
    ch.setFormatter(fmt)

    # File handler — permanent audit log
    fh = logging.FileHandler(log_path)
    fh.setLevel(logging.DEBUG)
    fh.setFormatter(fmt)

    logger.addHandler(ch)
    logger.addHandler(fh)
    return logger


# --------------------------------------------------------------------------
# Threshold rules — defines what counts as "alertable"
# --------------------------------------------------------------------------

SEVERITY_RANK = {"LOW": 1, "MEDIUM": 2, "HIGH": 3, "CRITICAL": 4}

ALERT_RULES = {
    "VPN_FAILURE":          {"min_severity": "HIGH",   "auto_ticket": True},
    "HIGH_LATENCY":         {"min_severity": "MEDIUM", "auto_ticket": True},
    "CONNECTION_TIMEOUT":   {"min_severity": "MEDIUM", "auto_ticket": True},
    "DNS_RESOLUTION_FAILURE":{"min_severity": "MEDIUM","auto_ticket": True},
    "BANDWIDTH_SATURATION": {"min_severity": "LOW",    "auto_ticket": True},
}


# --------------------------------------------------------------------------
# Monitor class
# --------------------------------------------------------------------------

class NetworkMonitor:
    """
    Core monitoring engine.

    In production this would also:
      - Ping devices (ICMP echo)
      - Query SNMP OIDs for interface counters
      - Parse syslog streams
      - Call REST APIs of managed switches/routers

    Here we use IssueSimulator to keep things self-contained.
    """

    def __init__(
        self,
        logger: Optional[logging.Logger] = None,
        on_alert: Optional[Callable[[NetworkIssue], None]] = None,
    ):
        self.simulator  = IssueSimulator()
        self.logger     = logger or setup_logger()
        self.on_alert   = on_alert          # callback → ticketing system
        self.alert_count = 0
        self.checked_count = 0

    # ------------------------------------------------------------------
    # Core check logic
    # ------------------------------------------------------------------

    def _evaluate(self, issue: NetworkIssue) -> bool:
        """
        Decide whether this issue crosses the alert threshold.
        Returns True if an alert should fire.
        """
        rule = ALERT_RULES.get(issue.issue_type)
        if not rule:
            return False

        issue_rank = SEVERITY_RANK.get(issue.severity, 0)
        min_rank   = SEVERITY_RANK.get(rule["min_severity"], 0)
        return issue_rank >= min_rank

    def check_once(self, issue_count: int = 3) -> list[NetworkIssue]:
        """
        Run one monitoring cycle: generate issues, evaluate, alert.
        Returns the list of issues that triggered alerts.
        """
        self.logger.info(f"🔍 Running monitoring cycle — sampling {issue_count} checks...")
        issues  = self.simulator.generate_batch(issue_count)
        alerted = []

        for issue in issues:
            self.checked_count += 1
            self.logger.debug(
                f"CHECK [{issue.issue_id}] {issue.issue_type} on {issue.host} "
                f"| severity={issue.severity}"
            )

            if self._evaluate(issue):
                self.alert_count += 1
                self.logger.warning(
                    f"⚠️  ALERT [{issue.issue_id}] {issue.issue_type} | "
                    f"Host: {issue.host} | Severity: {issue.severity} | "
                    f"{issue.description}"
                )
                alerted.append(issue)

                # Stage 7: Fire the callback → auto-creates a ticket
                if self.on_alert:
                    self.on_alert(issue)
            else:
                self.logger.info(
                    f"✅ OK [{issue.issue_id}] {issue.issue_type} on {issue.host} "
                    f"— below alert threshold"
                )

        return alerted

    def run_continuous(self, cycles: int = 3, interval_s: float = 1.5):
        """
        Simulates a monitoring loop running on a schedule.
        Real systems run this every 30–300 seconds (polling interval).
        """
        self.logger.info("=" * 60)
        self.logger.info("  Network Monitor STARTED")
        self.logger.info(f"  Cycles: {cycles}  |  Interval: {interval_s}s")
        self.logger.info("=" * 60)

        for cycle_num in range(1, cycles + 1):
            self.logger.info(f"\n--- Cycle {cycle_num}/{cycles} ---")
            self.check_once()
            if cycle_num < cycles:
                time.sleep(interval_s)

        self.logger.info("\n" + "=" * 60)
        self.logger.info(
            f"  Monitor FINISHED | Checked: {self.checked_count} | "
            f"Alerts: {self.alert_count}"
        )
        self.logger.info("=" * 60)
