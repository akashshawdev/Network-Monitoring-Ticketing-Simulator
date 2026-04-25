"""
issue_simulator.py
------------------
Stage 3: Issue Simulation

PURPOSE: Simulates real network problems that a first-level support engineer
would encounter daily — VPN drops, high latency, timeouts, DNS failures.

WHY IT EXISTS: Instead of needing a live network, we generate realistic
issue events with timestamps, affected hosts, and severity levels. This
mirrors how monitoring tools like Zabbix or PRTG detect real anomalies.
"""

import random
import time
from datetime import datetime
from dataclasses import dataclass, field
from typing import Optional


# --------------------------------------------------------------------------
# Data Model — what an "issue" looks like
# --------------------------------------------------------------------------

@dataclass
class NetworkIssue:
    issue_id: str
    issue_type: str          # e.g. "VPN_FAILURE"
    host: str                # which device/server is affected
    severity: str            # LOW / MEDIUM / HIGH / CRITICAL
    description: str
    detected_at: str         # ISO timestamp
    metrics: dict            # raw numbers (latency ms, packet loss %, etc.)
    resolved: bool = False
    resolved_at: Optional[str] = None

    def to_dict(self) -> dict:
        return self.__dict__.copy()


# --------------------------------------------------------------------------
# Issue definitions — based on real-world NOC scenarios
# --------------------------------------------------------------------------

ISSUE_TEMPLATES = [
    {
        "issue_type":   "VPN_FAILURE",
        "severity":     "CRITICAL",
        "hosts":        ["vpn-gateway-01", "vpn-gateway-02", "remote-vpn-03"],
        "descriptions": [
            "VPN tunnel dropped — IKE Phase 2 negotiation failed",
            "VPN authentication timeout — RADIUS server not responding",
            "VPN concentrator CPU at 98% — tunnel establishment failing",
        ],
        "metrics_fn":   lambda: {
            "tunnel_status":  "DOWN",
            "last_seen_ago_s": random.randint(30, 300),
            "failed_logins":   random.randint(5, 50),
            "packet_loss_pct": 100,
        },
    },
    {
        "issue_type":   "HIGH_LATENCY",
        "severity":     "HIGH",
        "hosts":        ["core-switch-01", "wan-router-02", "isp-link-primary"],
        "descriptions": [
            "Average RTT exceeded 400 ms — possible ISP congestion",
            "Jitter spike detected on WAN link — VoIP calls affected",
            "Routing loop suspected — TTL exhausted on traceroute",
        ],
        "metrics_fn":   lambda: {
            "avg_latency_ms":  random.randint(350, 1200),
            "baseline_ms":     20,
            "jitter_ms":       random.randint(80, 300),
            "packet_loss_pct": random.randint(5, 30),
        },
    },
    {
        "issue_type":   "CONNECTION_TIMEOUT",
        "severity":     "HIGH",
        "hosts":        ["app-server-01", "db-server-02", "api-gateway-prod"],
        "descriptions": [
            "TCP connection to port 443 timing out after 30 s",
            "SSH connection refused — firewall rule change suspected",
            "HTTP 504 Gateway Timeout — upstream service unreachable",
        ],
        "metrics_fn":   lambda: {
            "timeout_threshold_s": 30,
            "attempts":            random.randint(3, 10),
            "port":                random.choice([22, 80, 443, 3389, 8080]),
            "packet_loss_pct":     random.randint(40, 100),
        },
    },
    {
        "issue_type":   "DNS_RESOLUTION_FAILURE",
        "severity":     "MEDIUM",
        "hosts":        ["dns-primary", "dns-secondary", "ad-dc-01"],
        "descriptions": [
            "DNS queries failing — NXDOMAIN for internal domains",
            "DNS server not responding on UDP 53",
            "DNS zone transfer failed — secondary out of sync",
        ],
        "metrics_fn":   lambda: {
            "response_time_ms":  random.randint(5000, 30000),
            "failed_queries":    random.randint(50, 500),
            "success_rate_pct":  random.randint(0, 20),
            "error_code":        random.choice(["SERVFAIL", "NXDOMAIN", "TIMEOUT"]),
        },
    },
    {
        "issue_type":   "BANDWIDTH_SATURATION",
        "severity":     "MEDIUM",
        "hosts":        ["edge-router-01", "distribution-sw-02", "uplink-port-gi0/1"],
        "descriptions": [
            "Interface utilisation at 97% — broadcast storm suspected",
            "Top talker consuming 80% bandwidth — possible exfiltration",
            "QoS policy not applied — critical traffic being queued",
        ],
        "metrics_fn":   lambda: {
            "utilisation_pct": random.randint(90, 99),
            "capacity_mbps":   1000,
            "current_mbps":    random.randint(900, 990),
            "top_protocol":    random.choice(["BitTorrent", "YouTube", "Unknown UDP"]),
        },
    },
]


# --------------------------------------------------------------------------
# Simulator class
# --------------------------------------------------------------------------

class IssueSimulator:
    """
    Generates realistic network issues.
    In a real NOC, this data would come from SNMP traps, syslog, or
    agent-based monitoring (Zabbix, Datadog, SolarWinds).
    """

    def __init__(self):
        self._counter = 0

    def _next_id(self) -> str:
        self._counter += 1
        return f"ISS-{self._counter:04d}"

    def generate_issue(self, force_type: Optional[str] = None) -> NetworkIssue:
        """Create one random (or specified) network issue."""
        templates = ISSUE_TEMPLATES
        if force_type:
            templates = [t for t in ISSUE_TEMPLATES if t["issue_type"] == force_type]
            if not templates:
                raise ValueError(f"Unknown issue type: {force_type}")

        tpl = random.choice(templates)

        return NetworkIssue(
            issue_id    = self._next_id(),
            issue_type  = tpl["issue_type"],
            host        = random.choice(tpl["hosts"]),
            severity    = tpl["severity"],
            description = random.choice(tpl["descriptions"]),
            detected_at = datetime.now().isoformat(timespec="seconds"),
            metrics     = tpl["metrics_fn"](),
        )

    def generate_batch(self, count: int = 5) -> list[NetworkIssue]:
        """Generate multiple issues — simulates a busy monitoring window."""
        issues = []
        for _ in range(count):
            issues.append(self.generate_issue())
            time.sleep(0.05)   # tiny delay so timestamps differ
        return issues
