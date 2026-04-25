"""
troubleshooter.py
-----------------
Stage 6: Troubleshooting Flow

PURPOSE: Defines and executes the step-by-step resolution playbook for
each issue type. This is the "runbook" — documented procedures that L1
support follows to diagnose and fix network problems.

WHY RUNBOOKS MATTER:
  - Consistency: every engineer follows the same steps
  - Speed: no guesswork — trained responses for known issue patterns
  - Escalation criteria: clear rules for when to escalate to L2/L3
  - Post-mortem material: logged steps feed incident reviews

REAL-WORLD PARALLEL:
  Tools like PagerDuty, OpsGenie, and Confluence store runbooks
  that auto-attach to incidents. This simulates that behaviour.
"""

import time
import logging
from datetime import datetime
from typing import Optional

from core.ticketing import TicketManager, TicketStatus


# --------------------------------------------------------------------------
# Resolution playbooks — one per issue type
# --------------------------------------------------------------------------
# Each step has:
#   name:    short label (shown in logs)
#   action:  what the engineer does
#   check:   what success looks like
#   delay_s: realistic time this step would take (simulated)

PLAYBOOKS = {

    "VPN_FAILURE": {
        "assigned_to": "L2-Network",
        "steps": [
            {
                "name":    "Verify VPN service status",
                "action":  "Check VPN gateway service (strongSwan/OpenVPN) is running",
                "check":   "systemctl status vpn-gateway returns Active",
                "delay_s": 0.3,
            },
            {
                "name":    "Check authentication server",
                "action":  "Ping RADIUS/LDAP server, verify port 1812/389 responsive",
                "check":   "Auth server responds within 200 ms",
                "delay_s": 0.3,
            },
            {
                "name":    "Review VPN gateway logs",
                "action":  "tail -f /var/log/vpn/daemon.log | grep ERROR",
                "check":   "Identify error code (IKE timeout, cert expired, etc.)",
                "delay_s": 0.4,
            },
            {
                "name":    "Restart VPN daemon",
                "action":  "systemctl restart vpn-gateway && monitor tunnel re-establishment",
                "check":   "Tunnel status changes to ESTABLISHED",
                "delay_s": 0.5,
            },
            {
                "name":    "Validate connectivity",
                "action":  "Ping internal resources through VPN tunnel",
                "check":   "RTT < 50 ms, 0% packet loss",
                "delay_s": 0.2,
            },
        ],
    },

    "HIGH_LATENCY": {
        "assigned_to": "L2-Network",
        "steps": [
            {
                "name":    "Baseline latency measurement",
                "action":  "Run continuous ping to gateway and remote site (100 packets)",
                "check":   "Establish current avg/min/max RTT",
                "delay_s": 0.4,
            },
            {
                "name":    "Traceroute analysis",
                "action":  "traceroute -n <destination> — identify high-latency hop",
                "check":   "Pinpoint the network segment causing delay",
                "delay_s": 0.4,
            },
            {
                "name":    "Check interface utilisation",
                "action":  "SNMP poll: ifInOctets / ifOutOctets on WAN interface",
                "check":   "Utilisation < 80% threshold",
                "delay_s": 0.3,
            },
            {
                "name":    "Review QoS policy",
                "action":  "show policy-map interface — verify priority queues active",
                "check":   "Critical traffic in priority queue, not best-effort",
                "delay_s": 0.3,
            },
            {
                "name":    "Contact ISP if external",
                "action":  "Open ISP ticket with traceroute data if latency is beyond edge router",
                "check":   "ISP acknowledges and begins investigation",
                "delay_s": 0.2,
            },
        ],
    },

    "CONNECTION_TIMEOUT": {
        "assigned_to": "L1-Support",
        "steps": [
            {
                "name":    "Port reachability check",
                "action":  "telnet <host> <port> or Test-NetConnection -Port <port>",
                "check":   "Connection accepted or refused (refused = service down, timeout = firewall)",
                "delay_s": 0.3,
            },
            {
                "name":    "Firewall rule audit",
                "action":  "Review ACL/security group rules for the affected port/host pair",
                "check":   "Confirm allow rule exists and is not shadowed by deny",
                "delay_s": 0.4,
            },
            {
                "name":    "Check service health",
                "action":  "SSH to target server — verify service (nginx, sshd, RDP) is running",
                "check":   "ps aux | grep <service> shows running process",
                "delay_s": 0.3,
            },
            {
                "name":    "Review recent change log",
                "action":  "Check change management system for firewall or config changes in last 24 h",
                "check":   "Identify if change caused the timeout",
                "delay_s": 0.3,
            },
            {
                "name":    "Restore or rollback",
                "action":  "Revert firewall rule change or restart service as needed",
                "check":   "Connection established successfully",
                "delay_s": 0.3,
            },
        ],
    },

    "DNS_RESOLUTION_FAILURE": {
        "assigned_to": "L2-Network",
        "steps": [
            {
                "name":    "DNS query test",
                "action":  "nslookup <internal-domain> <dns-server-ip>",
                "check":   "Returns valid IP — if not, DNS server is the issue",
                "delay_s": 0.3,
            },
            {
                "name":    "DNS service status",
                "action":  "Check named/unbound/AD DNS service on primary DNS server",
                "check":   "Service running, listening on UDP/TCP 53",
                "delay_s": 0.3,
            },
            {
                "name":    "Zone data integrity",
                "action":  "named-checkzone <zone> <zonefile> to validate zone file",
                "check":   "No syntax errors, SOA record valid",
                "delay_s": 0.4,
            },
            {
                "name":    "Failover to secondary DNS",
                "action":  "Update DHCP scope to point to secondary DNS while primary is investigated",
                "check":   "Client resolution works via secondary",
                "delay_s": 0.3,
            },
            {
                "name":    "Restore primary DNS",
                "action":  "Fix zone file / restart service / force zone transfer",
                "check":   "dig @primary <domain> returns correct A record",
                "delay_s": 0.3,
            },
        ],
    },

    "BANDWIDTH_SATURATION": {
        "assigned_to": "L2-Network",
        "steps": [
            {
                "name":    "Identify top talkers",
                "action":  "Use ntopng / NetFlow / show interface counters to find heavy hitters",
                "check":   "IP addresses consuming > 20% bandwidth identified",
                "delay_s": 0.4,
            },
            {
                "name":    "Protocol analysis",
                "action":  "Capture 60 s of traffic with tcpdump / Wireshark on saturated interface",
                "check":   "Identify protocol mix (P2P, streaming, backup job, etc.)",
                "delay_s": 0.4,
            },
            {
                "name":    "Apply rate limiting",
                "action":  "Configure traffic shaping / QoS policy to throttle non-critical traffic",
                "check":   "Interface utilisation drops below 80%",
                "delay_s": 0.3,
            },
            {
                "name":    "Notify stakeholders",
                "action":  "Alert affected teams; document bandwidth policy if violation",
                "check":   "Users acknowledged; HR/security looped in if policy breach",
                "delay_s": 0.2,
            },
        ],
    },
}

# Fallback for unknown issue types
DEFAULT_PLAYBOOK = {
    "assigned_to": "L1-Support",
    "steps": [
        {"name": "Gather information", "action": "Collect logs and reproduce the issue", "check": "Issue documented", "delay_s": 0.3},
        {"name": "Escalate to L2",     "action": "Create L2 ticket with all gathered data",  "check": "L2 assigned",     "delay_s": 0.2},
    ],
}


# --------------------------------------------------------------------------
# Troubleshooter class
# --------------------------------------------------------------------------

class Troubleshooter:
    """
    Executes the resolution runbook for a given ticket.
    Logs every step to both console and audit trail.
    """

    def __init__(self, ticket_manager: TicketManager, logger: Optional[logging.Logger] = None):
        self.tm     = ticket_manager
        self.logger = logger or logging.getLogger("Troubleshooter")

    def resolve(self, ticket_id: str, simulate_delay: bool = True) -> bool:
        """
        Run the full troubleshooting playbook for a ticket.
        Returns True when resolved successfully.
        """
        ticket = self.tm.get_ticket(ticket_id)
        if not ticket:
            self.logger.error(f"Ticket {ticket_id} not found")
            return False

        playbook = PLAYBOOKS.get(ticket.issue_type, DEFAULT_PLAYBOOK)

        self.logger.info(f"\n{'─'*60}")
        self.logger.info(f"🔧 TROUBLESHOOTING START: {ticket_id}")
        self.logger.info(f"   Issue   : {ticket.issue_type}")
        self.logger.info(f"   Host    : {ticket.host}")
        self.logger.info(f"   Priority: {ticket.priority}")
        self.logger.info(f"{'─'*60}")

        # Stage 7: Auto-assign + move to IN_PROGRESS
        self.tm.assign_ticket(ticket_id, playbook["assigned_to"])
        self.tm.update_status(
            ticket_id, TicketStatus.IN_PROGRESS,
            by=playbook["assigned_to"],
            note="Runbook started",
        )

        # Execute each step
        total_steps = len(playbook["steps"])
        for i, step in enumerate(playbook["steps"], 1):
            self.logger.info(
                f"\n  Step {i}/{total_steps}: {step['name']}"
            )
            self.logger.info(f"  → Action : {step['action']}")
            self.logger.info(f"  → Success: {step['check']}")

            if simulate_delay:
                time.sleep(step.get("delay_s", 0.2))

            # Append step to ticket history
            ticket.history.append({
                "at":    datetime.now().isoformat(timespec="seconds"),
                "event": f"Step {i}: {step['name']} — COMPLETED",
                "by":    playbook["assigned_to"],
            })

        # Stage 7: Auto-resolve
        resolution_note = (
            f"All {total_steps} runbook steps completed. "
            f"Issue confirmed resolved by {playbook['assigned_to']}."
        )
        self.tm.update_status(
            ticket_id, TicketStatus.RESOLVED,
            by=playbook["assigned_to"],
            note=resolution_note,
        )
        self.tm._save()

        self.logger.info(f"\n  ✅ RESOLVED: {ticket_id} | {resolution_note}")
        self.logger.info(f"{'─'*60}\n")
        return True
