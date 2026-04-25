# Network Monitoring & Ticketing Simulator

A fully self-contained Python project that simulates what a Network Operations
Centre (NOC) engineer does every day: detect issues, create tickets, execute
runbooks, and resolve problems — all automated.

---

## What This Simulates

| Real-World Tool | This Project's Equivalent |
|-----------------|---------------------------|
| Zabbix / PRTG   | `monitor.py` — polling & alerting |
| JIRA / ServiceNow | `ticketing.py` — ticket lifecycle |
| Confluence Runbooks | `troubleshooter.py` — step-by-step playbooks |
| Syslog / Splunk | `logs/monitor.log` — structured audit log |
| CMDB / Network devices | `issue_simulator.py` — realistic issue generator |

---

## Folder Structure

```
netmon/
├── main.py                  # Entry point — runs the full pipeline
├── README.md                # This file
│
├── core/
│   ├── issue_simulator.py   # Stage 3: Generates realistic network issues
│   ├── monitor.py           # Stage 4: Monitoring engine + alert logic
│   ├── ticketing.py         # Stage 5: Ticket lifecycle management
│   └── troubleshooter.py    # Stage 6: Step-by-step resolution runbooks
│
├── logs/
│   └── monitor.log          # Auto-generated — full audit trail
│
├── tickets/
│   └── tickets.json         # Auto-generated — persistent ticket store
│
└── data/
    └── last_run.json        # Auto-generated — full JSON export of last run
```

---

## Requirements

- **Python 3.10+** (uses dataclasses, match statements)
- **No external libraries** — 100% Python standard library

---

## How to Run

```bash
# Navigate into the project folder
cd netmon

# Full run — 3 monitoring cycles, ~12 issues, all auto-resolved
python main.py

# Demo run — shorter, 2 cycles, 4 issues (good for first look)
python main.py --mode demo

# Report only — shows tickets from previous run (no new monitoring)
python main.py --mode report
```

---

## The Eight Stages Explained

### Stage 1 — What This System Does

A **NOC (Network Operations Centre)** monitors infrastructure 24/7. When
something goes wrong, the workflow is:

```
Network anomaly detected
        ↓
Alert fired by monitoring system
        ↓
Ticket created (OPEN)
        ↓
Engineer assigned (IN_PROGRESS)
        ↓
Runbook executed step by step
        ↓
Issue resolved → Ticket closed (RESOLVED)
```

This project simulates all of that — no real network needed.

---

### Stage 2 — System Components

| Component | File | Why It Exists |
|-----------|------|---------------|
| Issue Simulator | `issue_simulator.py` | Generates realistic network problems |
| Monitor Engine | `monitor.py` | Evaluates issues against alert thresholds |
| Ticket Manager | `ticketing.py` | Tracks every issue from open to close |
| Troubleshooter | `troubleshooter.py` | Executes resolution runbooks |
| Logger | inside `monitor.py` | Creates permanent audit trail |

---

### Stage 3 — Issue Types Simulated

| Issue | Severity | Real-World Cause |
|-------|----------|-----------------|
| `VPN_FAILURE` | CRITICAL | IKE negotiation failure, RADIUS timeout |
| `HIGH_LATENCY` | HIGH | ISP congestion, routing loop, QoS misconfiguration |
| `CONNECTION_TIMEOUT` | HIGH | Firewall block, service down, port unreachable |
| `DNS_RESOLUTION_FAILURE` | MEDIUM | Zone file corruption, DNS service crash |
| `BANDWIDTH_SATURATION` | MEDIUM | Broadcast storm, unauthorized P2P, backup job |

Each issue comes with:
- Affected host name (e.g., `vpn-gateway-01`)
- Realistic description
- Raw metrics (latency ms, packet loss %, utilisation %)

---

### Stage 4 — Monitoring Logic

The monitor runs in polling cycles (like Zabbix every 60 seconds).

Each issue is evaluated against **threshold rules**:

```python
ALERT_RULES = {
    "VPN_FAILURE":    {"min_severity": "HIGH",   "auto_ticket": True},
    "HIGH_LATENCY":   {"min_severity": "MEDIUM", "auto_ticket": True},
    ...
}
```

If `issue_severity >= min_severity` → alert fires → ticket is created automatically.

---

### Stage 5 — Ticket Lifecycle

Tickets follow this state machine:

```
OPEN → IN_PROGRESS → RESOLVED
          ↓
       ESCALATED (optional)
```

Priority mapping mirrors PagerDuty / JIRA:

| Severity | Priority | SLA |
|----------|----------|-----|
| CRITICAL | P1 | 1 hour |
| HIGH | P2 | 4 hours |
| MEDIUM | P3 | 8 hours |
| LOW | P4 | 24 hours |

Every state change is appended to the ticket's **history** — a full audit trail.

---

### Stage 6 — Troubleshooting Runbooks

Each issue type has a specific runbook — a checklist of diagnostic steps.

Example — VPN_FAILURE runbook:
1. Verify VPN service status (`systemctl status`)
2. Check auth server (RADIUS ping)
3. Review VPN daemon logs
4. Restart VPN daemon
5. Validate tunnel and connectivity

This mirrors how real NOC engineers follow documented procedures rather than guessing.

---

### Stage 7 — Automation

The key automation hook is the `on_alert` callback:

```python
def on_alert(issue):
    ticket = tm.create_ticket(issue)   # Auto ticket creation
    ...

monitor = NetworkMonitor(on_alert=on_alert)
```

And after monitoring, all open tickets are resolved automatically:

```python
for ticket in open_tickets:
    troubleshooter.resolve(ticket.ticket_id)
```

**Efficiency gain:** In manual operations, a monitoring alert → engineer reads it
→ manually creates ticket → assigns it. This takes 5–15 minutes per issue.
Automation reduces that to milliseconds, and nothing falls through the cracks.

---

### Stage 8 — Output Files

After each run you get:

| File | Contents |
|------|----------|
| `logs/monitor.log` | Full timestamped audit log — every check, alert, step |
| `tickets/tickets.json` | Persistent ticket store — survives restarts |
| `data/last_run.json` | Complete JSON export — stats + all ticket details |

---

## How to Talk About This in an Interview

**"What does this project do?"**
> "It simulates a NOC monitoring pipeline. A monitor detects network issues like
> VPN failures or DNS outages, automatically creates a ticket with priority and
> SLA, then executes a step-by-step runbook to resolve it. Everything is logged
> for audit purposes — just like Zabbix feeding into ServiceNow."

**"How does ticketing work?"**
> "Tickets have a lifecycle: OPEN → IN_PROGRESS → RESOLVED. Every state change
> is recorded in the ticket history with a timestamp and actor — L1-Support or
> L2-Network depending on the issue type. P1 critical issues get a 1-hour SLA."

**"What automation did you add?"**
> "The monitoring engine has an alert callback that automatically creates tickets
> the moment an issue crosses the severity threshold. Then after the monitoring
> phase, all open tickets get routed to the troubleshooter which runs the
> appropriate runbook automatically. No human needs to read an alert and manually
> open a ticket."

---

## Extending This Project

Ideas to make it more advanced:
- Add a REST API (`flask`) so a web dashboard can read tickets
- Add email/Slack notification on CRITICAL alerts
- Add SLA breach detection (flag tickets that exceed SLA time)
- Persist with SQLite instead of JSON for faster querying
- Add real `ping` checks using Python's `subprocess` module
