"""
ticketing.py
------------
Stage 5: Ticketing System

PURPOSE: Tracks every detected issue through its lifecycle — from
first detection to resolution. Think JIRA, ServiceNow, or Freshservice
but stripped to what matters for learning.

TICKET LIFECYCLE:
  OPEN → IN_PROGRESS → RESOLVED (or ESCALATED)

WHY IT EXISTS:
  - Accountability: every issue has an owner and a timeline
  - Auditability: you can prove what was done and when
  - SLA tracking: how long from open to resolve?
  - Knowledge base: repeat issues get faster resolution

REAL-WORLD PARALLEL:
  This mirrors how L1/L2 support teams operate in a helpdesk or NOC.
  A ticket is never "lost" — it's always in a known state.
"""

import json
import os
from datetime import datetime
from dataclasses import dataclass, field, asdict
from typing import Optional
from enum import Enum


# --------------------------------------------------------------------------
# Ticket states — mirrors JIRA workflow
# --------------------------------------------------------------------------

class TicketStatus(str, Enum):
    OPEN        = "OPEN"
    IN_PROGRESS = "IN_PROGRESS"
    ESCALATED   = "ESCALATED"
    RESOLVED    = "RESOLVED"
    CLOSED      = "CLOSED"


PRIORITY_MAP = {
    "CRITICAL": "P1",
    "HIGH":     "P2",
    "MEDIUM":   "P3",
    "LOW":      "P4",
}

SLA_HOURS = {
    "P1": 1,   # Critical — 1 hour response
    "P2": 4,   # High — 4 hours
    "P3": 8,   # Medium — same business day
    "P4": 24,  # Low — next business day
}


# --------------------------------------------------------------------------
# Ticket data model
# --------------------------------------------------------------------------

@dataclass
class Ticket:
    ticket_id:    str
    issue_id:     str
    issue_type:   str
    host:         str
    priority:     str             # P1–P4
    status:       TicketStatus
    title:        str
    description:  str
    created_at:   str
    updated_at:   str
    assigned_to:  str = "Unassigned"
    resolution:   Optional[str] = None
    resolved_at:  Optional[str] = None
    history:      list = field(default_factory=list)  # audit trail

    def to_dict(self) -> dict:
        d = asdict(self)
        d["status"] = self.status.value
        return d

    def summary_line(self) -> str:
        return (
            f"[{self.ticket_id}] {self.priority} | {self.status.value:<12} | "
            f"{self.issue_type:<25} | Host: {self.host}"
        )


# --------------------------------------------------------------------------
# Ticket Manager — the central registry
# --------------------------------------------------------------------------

class TicketManager:
    """
    Creates, updates, and persists tickets.
    Tickets are saved to a JSON file — in production this would be
    a database (PostgreSQL, MySQL) or ITSM API (ServiceNow REST).
    """

    STORE_PATH = "tickets/tickets.json"

    def __init__(self):
        self._tickets: dict[str, Ticket] = {}
        self._counter = 0
        os.makedirs("tickets", exist_ok=True)
        self._load()

    # ------------------------------------------------------------------
    # Persistence
    # ------------------------------------------------------------------

    def _load(self):
        if os.path.exists(self.STORE_PATH):
            with open(self.STORE_PATH) as f:
                data = json.load(f)
            for raw in data.values():
                raw["status"] = TicketStatus(raw["status"])
                t = Ticket(**raw)
                self._tickets[t.ticket_id] = t
                # keep counter in sync
                num = int(t.ticket_id.split("-")[1])
                self._counter = max(self._counter, num)

    def _save(self):
        with open(self.STORE_PATH, "w") as f:
            json.dump(
                {tid: t.to_dict() for tid, t in self._tickets.items()},
                f, indent=2,
            )

    def _next_ticket_id(self) -> str:
        self._counter += 1
        return f"TKT-{self._counter:04d}"

    # ------------------------------------------------------------------
    # CRUD operations
    # ------------------------------------------------------------------

    def create_ticket(self, issue) -> Ticket:
        """
        Open a new ticket from a NetworkIssue.
        Called automatically by the monitor (Stage 7 automation).
        """
        priority = PRIORITY_MAP.get(issue.severity, "P4")
        now      = datetime.now().isoformat(timespec="seconds")

        ticket = Ticket(
            ticket_id   = self._next_ticket_id(),
            issue_id    = issue.issue_id,
            issue_type  = issue.issue_type,
            host        = issue.host,
            priority    = priority,
            status      = TicketStatus.OPEN,
            title       = f"{issue.issue_type.replace('_', ' ').title()} — {issue.host}",
            description = issue.description,
            created_at  = now,
            updated_at  = now,
            history     = [{"at": now, "event": "Ticket created", "by": "AutoMonitor"}],
        )

        self._tickets[ticket.ticket_id] = ticket
        self._save()
        return ticket

    def update_status(
        self,
        ticket_id: str,
        new_status: TicketStatus,
        by: str = "Engineer",
        note: str = "",
    ) -> Ticket:
        """Move a ticket to a new state and append to its history."""
        ticket = self._tickets[ticket_id]
        now    = datetime.now().isoformat(timespec="seconds")

        old_status    = ticket.status
        ticket.status = new_status
        ticket.updated_at = now

        event = f"Status changed {old_status.value} → {new_status.value}"
        if note:
            event += f" | Note: {note}"

        ticket.history.append({"at": now, "event": event, "by": by})

        if new_status == TicketStatus.RESOLVED:
            ticket.resolved_at = now
            ticket.resolution  = note or "Issue resolved"

        self._save()
        return ticket

    def assign_ticket(self, ticket_id: str, engineer: str) -> Ticket:
        """Assign a ticket to an engineer (L1/L2/L3)."""
        ticket = self._tickets[ticket_id]
        now    = datetime.now().isoformat(timespec="seconds")
        ticket.assigned_to = engineer
        ticket.updated_at  = now
        ticket.history.append(
            {"at": now, "event": f"Assigned to {engineer}", "by": "TicketSystem"}
        )
        self._save()
        return ticket

    def get_ticket(self, ticket_id: str) -> Optional[Ticket]:
        return self._tickets.get(ticket_id)

    def list_tickets(self, status: Optional[TicketStatus] = None) -> list[Ticket]:
        tickets = list(self._tickets.values())
        if status:
            tickets = [t for t in tickets if t.status == status]
        return sorted(tickets, key=lambda t: t.created_at, reverse=True)

    def stats(self) -> dict:
        all_t = list(self._tickets.values())
        return {
            "total":       len(all_t),
            "open":        sum(1 for t in all_t if t.status == TicketStatus.OPEN),
            "in_progress": sum(1 for t in all_t if t.status == TicketStatus.IN_PROGRESS),
            "resolved":    sum(1 for t in all_t if t.status == TicketStatus.RESOLVED),
            "critical_p1": sum(1 for t in all_t if t.priority == "P1"),
        }
