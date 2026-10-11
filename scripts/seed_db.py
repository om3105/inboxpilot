#!/usr/bin/env python3
"""
Seed script: loads ~30 realistic MOCK records into MongoDB Atlas.

Collections seeded:
  - employees    (10 records)  — name, email, department, leave balances
  - invoices     (10 records)  — vendor, amount, status, due date
  - tickets      (10 records)  — support tickets with status & priority

Usage:
    python -m scripts.seed_db          # uses .env for MONGODB_URI
    MONGODB_URI=... python -m scripts.seed_db  # explicit URI

Design decisions:
- Uses pymongo (sync) because this is a one-shot script, not a server.
- Drops existing collections first so re-running is idempotent.
- All data is MOCK — names, emails, and amounts are fictional.
"""

import os
import sys
from datetime import datetime, timedelta

from dotenv import load_dotenv
from pymongo import MongoClient


def get_mock_employees() -> list[dict]:
    """10 fictional employees with leave balances."""
    return [
        {
            "employee_id": "EMP001",
            "name": "Aarav Sharma",
            "email": "aarav.sharma@acme.dev",
            "department": "Engineering",
            "leave_balance": {"casual": 10, "sick": 7, "earned": 15},
            "manager": "Priya Patel",
        },
        {
            "employee_id": "EMP002",
            "name": "Priya Patel",
            "email": "priya.patel@acme.dev",
            "department": "Engineering",
            "leave_balance": {"casual": 8, "sick": 7, "earned": 12},
            "manager": "Vikram Rao",
        },
        {
            "employee_id": "EMP003",
            "name": "Rohan Mehta",
            "email": "rohan.mehta@acme.dev",
            "department": "Finance",
            "leave_balance": {"casual": 5, "sick": 7, "earned": 20},
            "manager": "Anita Desai",
        },
        {
            "employee_id": "EMP004",
            "name": "Sneha Nair",
            "email": "sneha.nair@acme.dev",
            "department": "HR",
            "leave_balance": {"casual": 12, "sick": 6, "earned": 10},
            "manager": "Anita Desai",
        },
        {
            "employee_id": "EMP005",
            "name": "Karan Singh",
            "email": "karan.singh@acme.dev",
            "department": "Marketing",
            "leave_balance": {"casual": 3, "sick": 7, "earned": 18},
            "manager": "Priya Patel",
        },
        {
            "employee_id": "EMP006",
            "name": "Anita Desai",
            "email": "anita.desai@acme.dev",
            "department": "HR",
            "leave_balance": {"casual": 9, "sick": 5, "earned": 14},
            "manager": "Vikram Rao",
        },
        {
            "employee_id": "EMP007",
            "name": "Vikram Rao",
            "email": "vikram.rao@acme.dev",
            "department": "Engineering",
            "leave_balance": {"casual": 6, "sick": 7, "earned": 22},
            "manager": None,  # CEO / top-level
        },
        {
            "employee_id": "EMP008",
            "name": "Meera Joshi",
            "email": "meera.joshi@acme.dev",
            "department": "Support",
            "leave_balance": {"casual": 10, "sick": 4, "earned": 11},
            "manager": "Sneha Nair",
        },
        {
            "employee_id": "EMP009",
            "name": "Arjun Kapoor",
            "email": "arjun.kapoor@acme.dev",
            "department": "Engineering",
            "leave_balance": {"casual": 0, "sick": 2, "earned": 5},
            "manager": "Aarav Sharma",
        },
        {
            "employee_id": "EMP010",
            "name": "Divya Reddy",
            "email": "divya.reddy@acme.dev",
            "department": "Finance",
            "leave_balance": {"casual": 7, "sick": 7, "earned": 16},
            "manager": "Rohan Mehta",
        },
    ]


def get_mock_invoices() -> list[dict]:
    """10 fictional invoices."""
    today = datetime.utcnow()
    return [
        {
            "invoice_number": "INV-2024-001",
            "vendor_name": "CloudStack Solutions",
            "amount": 4500.00,
            "currency": "USD",
            "status": "pending",
            "issued_date": (today - timedelta(days=30)).isoformat(),
            "due_date": (today + timedelta(days=15)).isoformat(),
            "description": "AWS hosting — October 2024",
        },
        {
            "invoice_number": "INV-2024-002",
            "vendor_name": "DesignCraft Agency",
            "amount": 12000.00,
            "currency": "USD",
            "status": "pending",
            "issued_date": (today - timedelta(days=20)).isoformat(),
            "due_date": (today + timedelta(days=10)).isoformat(),
            "description": "Brand refresh project — Phase 2",
        },
        {
            "invoice_number": "INV-2024-003",
            "vendor_name": "Secure Networks Ltd",
            "amount": 2800.00,
            "currency": "USD",
            "status": "paid",
            "issued_date": (today - timedelta(days=60)).isoformat(),
            "due_date": (today - timedelta(days=30)).isoformat(),
            "description": "Penetration testing — Q3",
        },
        {
            "invoice_number": "INV-2024-004",
            "vendor_name": "Office Supplies Co",
            "amount": 340.50,
            "currency": "USD",
            "status": "pending",
            "issued_date": (today - timedelta(days=10)).isoformat(),
            "due_date": (today + timedelta(days=20)).isoformat(),
            "description": "Stationery and printer cartridges",
        },
        {
            "invoice_number": "INV-2024-005",
            "vendor_name": "Legal Eagles LLP",
            "amount": 7500.00,
            "currency": "USD",
            "status": "overdue",
            "issued_date": (today - timedelta(days=90)).isoformat(),
            "due_date": (today - timedelta(days=10)).isoformat(),
            "description": "Contract review — vendor agreements",
        },
        {
            "invoice_number": "INV-2024-006",
            "vendor_name": "CloudStack Solutions",
            "amount": 4500.00,
            "currency": "USD",
            "status": "pending",
            "issued_date": (today - timedelta(days=5)).isoformat(),
            "due_date": (today + timedelta(days=25)).isoformat(),
            "description": "AWS hosting — November 2024",
        },
        {
            "invoice_number": "INV-2024-007",
            "vendor_name": "TalentForge Recruiting",
            "amount": 15000.00,
            "currency": "USD",
            "status": "pending",
            "issued_date": (today - timedelta(days=15)).isoformat(),
            "due_date": (today + timedelta(days=5)).isoformat(),
            "description": "Senior engineer placement fee",
        },
        {
            "invoice_number": "INV-2024-008",
            "vendor_name": "GreenClean Services",
            "amount": 600.00,
            "currency": "USD",
            "status": "paid",
            "issued_date": (today - timedelta(days=45)).isoformat(),
            "due_date": (today - timedelta(days=15)).isoformat(),
            "description": "Monthly office cleaning — September",
        },
        {
            "invoice_number": "INV-2024-009",
            "vendor_name": "DataVault Backups",
            "amount": 1200.00,
            "currency": "USD",
            "status": "pending",
            "issued_date": (today - timedelta(days=7)).isoformat(),
            "due_date": (today + timedelta(days=23)).isoformat(),
            "description": "Off-site backup storage — annual",
        },
        {
            "invoice_number": "INV-2024-010",
            "vendor_name": "CaterPro Events",
            "amount": 950.00,
            "currency": "USD",
            "status": "paid",
            "issued_date": (today - timedelta(days=40)).isoformat(),
            "due_date": (today - timedelta(days=25)).isoformat(),
            "description": "Team lunch catering — Q3 offsite",
        },
    ]


def get_mock_tickets() -> list[dict]:
    """10 fictional support tickets."""
    today = datetime.utcnow()
    return [
        {
            "ticket_id": "TKT-301",
            "requester": "aarav.sharma@acme.dev",
            "subject": "VPN disconnects every 30 minutes",
            "priority": "high",
            "status": "open",
            "created_at": (today - timedelta(days=2)).isoformat(),
            "assigned_to": "Meera Joshi",
            "description": "VPN drops on the office Wi-Fi. Have tried reinstalling the client.",
        },
        {
            "ticket_id": "TKT-302",
            "requester": "rohan.mehta@acme.dev",
            "subject": "Cannot access finance dashboard",
            "priority": "critical",
            "status": "open",
            "created_at": (today - timedelta(days=1)).isoformat(),
            "assigned_to": "Meera Joshi",
            "description": "Getting 403 Forbidden since the last deployment.",
        },
        {
            "ticket_id": "TKT-303",
            "requester": "karan.singh@acme.dev",
            "subject": "Request new marketing analytics tool",
            "priority": "low",
            "status": "open",
            "created_at": (today - timedelta(days=5)).isoformat(),
            "assigned_to": None,
            "description": "Need access to BrandWatch for social listening.",
        },
        {
            "ticket_id": "TKT-304",
            "requester": "sneha.nair@acme.dev",
            "subject": "Printer on 3rd floor is jammed",
            "priority": "medium",
            "status": "in_progress",
            "created_at": (today - timedelta(days=3)).isoformat(),
            "assigned_to": "Meera Joshi",
            "description": "HP LaserJet on 3rd floor shows paper-jam error, no paper visible.",
        },
        {
            "ticket_id": "TKT-305",
            "requester": "divya.reddy@acme.dev",
            "subject": "Expense report software crashes on submit",
            "priority": "high",
            "status": "open",
            "created_at": (today - timedelta(days=1)).isoformat(),
            "assigned_to": None,
            "description": "Chrome shows 'Aw, Snap!' when clicking Submit on expense reports.",
        },
        {
            "ticket_id": "TKT-306",
            "requester": "arjun.kapoor@acme.dev",
            "subject": "GitHub SSO login loop",
            "priority": "critical",
            "status": "open",
            "created_at": today.isoformat(),
            "assigned_to": "Meera Joshi",
            "description": "Okta SSO redirects back to login page infinitely for GitHub Enterprise.",
        },
        {
            "ticket_id": "TKT-307",
            "requester": "priya.patel@acme.dev",
            "subject": "Slack notifications not appearing on mobile",
            "priority": "low",
            "status": "resolved",
            "created_at": (today - timedelta(days=10)).isoformat(),
            "assigned_to": "Meera Joshi",
            "description": "Resolved by re-enabling notification permissions in iOS settings.",
        },
        {
            "ticket_id": "TKT-308",
            "requester": "meera.joshi@acme.dev",
            "subject": "Monitor flickering on standing desk",
            "priority": "medium",
            "status": "open",
            "created_at": (today - timedelta(days=4)).isoformat(),
            "assigned_to": None,
            "description": "Dell U2723 flickers when desk is raised. Possibly a cable issue.",
        },
        {
            "ticket_id": "TKT-309",
            "requester": "vikram.rao@acme.dev",
            "subject": "Need admin access to Confluence",
            "priority": "medium",
            "status": "open",
            "created_at": (today - timedelta(days=2)).isoformat(),
            "assigned_to": "Sneha Nair",
            "description": "Need space-admin permissions to create the 2025 planning space.",
        },
        {
            "ticket_id": "TKT-310",
            "requester": "anita.desai@acme.dev",
            "subject": "Onboarding laptop setup for new hire",
            "priority": "high",
            "status": "in_progress",
            "created_at": (today - timedelta(days=1)).isoformat(),
            "assigned_to": "Meera Joshi",
            "description": "New hire starts Monday. Need MacBook Pro with standard dev tooling.",
        },
    ]


def seed(uri: str, db_name: str) -> None:
    """Drop existing collections and insert fresh mock data."""
    client = MongoClient(uri)
    db = client[db_name]

    collections = {
        "employees": get_mock_employees(),
        "invoices": get_mock_invoices(),
        "tickets": get_mock_tickets(),
    }

    for name, docs in collections.items():
        db[name].drop()
        result = db[name].insert_many(docs)
        print(f"  ✓ {name}: inserted {len(result.inserted_ids)} documents")

    # Create useful indexes
    db["employees"].create_index("employee_id", unique=True)
    db["employees"].create_index("name")
    db["employees"].create_index("email", unique=True)
    db["invoices"].create_index("invoice_number", unique=True)
    db["tickets"].create_index("ticket_id", unique=True)
    print("  ✓ Indexes created")

    client.close()
    print("\n✅ Seed complete.")


if __name__ == "__main__":
    load_dotenv()
    uri = os.getenv("MONGODB_URI")
    db_name = os.getenv("MONGODB_DB_NAME", "inboxpilot")

    if not uri:
        print("❌ MONGODB_URI not set. Copy .env.example → .env and fill it in.")
        sys.exit(1)

    print(f"🌱 Seeding database '{db_name}' …")
    seed(uri, db_name)
