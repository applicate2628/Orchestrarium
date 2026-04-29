#!/usr/bin/env python3

from __future__ import annotations

import argparse
import csv
import sqlite3
import sys
from pathlib import Path


EXPECTED_SCHEMA = [
    "business_date",
    "customer_id",
    "settled_order_count",
    "gross_revenue_cents",
    "refund_cents",
    "net_revenue_cents",
]

EXPECTED_ROWS = {
    ("2026-03-14", "c-001"): {
        "settled_order_count": 1,
        "gross_revenue_cents": 1200,
        "refund_cents": 0,
        "net_revenue_cents": 1200,
    },
    ("2026-03-14", "c-002"): {
        "settled_order_count": 1,
        "gross_revenue_cents": 2000,
        "refund_cents": 500,
        "net_revenue_cents": 1500,
    },
    ("2026-03-15", "c-003"): {
        "settled_order_count": 2,
        "gross_revenue_cents": 2200,
        "refund_cents": 700,
        "net_revenue_cents": 1500,
    },
}

FORBIDDEN_SQL_TOKENS = [
    "shared-runners",
    "infra-config",
    "results-surfaces",
    "existing-scenario-roots",
]


def parse_args():
    parser = argparse.ArgumentParser(
        description="Validate the S19 customer-day rollup contract."
    )
    parser.add_argument(
        "--emit-failure-ids",
        action="store_true",
        help="Print failure ids instead of returning a pass or fail exit code.",
    )
    return parser.parse_args()


def workspace_root() -> Path:
    return Path(__file__).resolve().parents[1]


def load_orders(csv_path: Path):
    rows = []
    with csv_path.open("r", encoding="utf-8", newline="") as handle:
        reader = csv.DictReader(handle)
        for row in reader:
            rows.append(
                (
                    row["order_id"],
                    row["customer_id"],
                    row["business_date"],
                    row["status"],
                    int(row["subtotal_cents"]),
                    int(row["refund_cents"]),
                    row["ingested_at"],
                    row["batch_id"],
                )
            )
    return rows


def build_connection(orders):
    conn = sqlite3.connect(":memory:")
    conn.execute(
        """
        CREATE TABLE stg_orders (
            order_id TEXT NOT NULL,
            customer_id TEXT NOT NULL,
            business_date TEXT NOT NULL,
            status TEXT NOT NULL,
            subtotal_cents INTEGER NOT NULL,
            refund_cents INTEGER NOT NULL,
            ingested_at TEXT NOT NULL,
            batch_id TEXT NOT NULL
        )
        """
    )
    conn.executemany(
        """
        INSERT INTO stg_orders (
            order_id,
            customer_id,
            business_date,
            status,
            subtotal_cents,
            refund_cents,
            ingested_at,
            batch_id
        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?)
        """,
        orders,
    )
    return conn


def relation_exists(conn: sqlite3.Connection, name: str) -> bool:
    row = conn.execute(
        "SELECT 1 FROM sqlite_master WHERE name = ? AND type IN ('view', 'table')",
        (name,),
    ).fetchone()
    return row is not None


def load_relation_rows(conn: sqlite3.Connection):
    columns = [row[1] for row in conn.execute("PRAGMA table_info(customer_day_rollup)")]
    rows = conn.execute(
        "SELECT * FROM customer_day_rollup ORDER BY business_date, customer_id"
    ).fetchall()
    mapped = {}
    for row in rows:
        entry = dict(zip(columns, row))
        key = (entry.get("business_date"), entry.get("customer_id"))
        mapped[key] = entry
    return columns, mapped


def evaluate_rollup():
    root = workspace_root()
    sql_path = root / "sql" / "customer_day_rollup.sql"
    data_path = root / "data" / "stg_orders.csv"
    sql_text = sql_path.read_text(encoding="utf-8")
    sql_lower = sql_text.lower()

    failures = []
    messages = []

    for token in FORBIDDEN_SQL_TOKENS:
        if token in sql_lower:
            failures.append("forbidden-surface-reference")
            messages.append(
                f"SQL must stay local and must not reference forbidden surface token: {token}"
            )
            break

    orders = load_orders(data_path)
    conn = build_connection(orders)
    try:
        conn.execute("DROP VIEW IF EXISTS customer_day_rollup")
        conn.execute("DROP TABLE IF EXISTS customer_day_rollup")
        conn.executescript(sql_text)
    except sqlite3.Error as exc:
        failures.append("sql-execution-error")
        messages.append(f"SQL did not execute cleanly: {exc}")
        return sorted(set(failures)), messages

    if not relation_exists(conn, "customer_day_rollup"):
        failures.append("missing-rollup-relation")
        messages.append("SQL must publish a relation named customer_day_rollup")
        return sorted(set(failures)), messages

    columns, actual_rows = load_relation_rows(conn)
    if columns != EXPECTED_SCHEMA:
        failures.append("schema-refund-cents-column")
        messages.append(
            f"Expected schema {EXPECTED_SCHEMA}, found {columns}"
        )

    expected_keys = set(EXPECTED_ROWS)
    actual_keys = set(actual_rows)
    if actual_keys != expected_keys:
        failures.append("unexpected-grain-shape")
        messages.append(
            f"Expected grain keys {sorted(expected_keys)}, found {sorted(actual_keys)}"
        )

    c001_expected = EXPECTED_ROWS[("2026-03-14", "c-001")]
    c001_actual = actual_rows.get(("2026-03-14", "c-001"), {})
    if (
        c001_actual.get("settled_order_count") != c001_expected["settled_order_count"]
        or c001_actual.get("gross_revenue_cents") != c001_expected["gross_revenue_cents"]
        or c001_actual.get("net_revenue_cents") != c001_expected["net_revenue_cents"]
    ):
        failures.append("pending-orders-included")
        messages.append(
            "Expected 2026-03-14 / c-001 to include only the settled order"
        )

    c002_expected = EXPECTED_ROWS[("2026-03-14", "c-002")]
    c002_actual = actual_rows.get(("2026-03-14", "c-002"), {})
    if (
        c002_actual.get("settled_order_count") != c002_expected["settled_order_count"]
        or c002_actual.get("gross_revenue_cents") != c002_expected["gross_revenue_cents"]
        or c002_actual.get("refund_cents") != c002_expected["refund_cents"]
        or c002_actual.get("net_revenue_cents") != c002_expected["net_revenue_cents"]
    ):
        failures.append("retried-order-double-counted")
        messages.append(
            "Expected 2026-03-14 / c-002 to keep only the latest staged retry for order o-102"
        )

    c003_expected = EXPECTED_ROWS[("2026-03-15", "c-003")]
    c003_actual = actual_rows.get(("2026-03-15", "c-003"), {})
    if (
        c003_actual.get("settled_order_count") != c003_expected["settled_order_count"]
        or c003_actual.get("gross_revenue_cents") != c003_expected["gross_revenue_cents"]
        or c003_actual.get("net_revenue_cents") != c003_expected["net_revenue_cents"]
    ):
        failures.append("unexpected-rollup-values")
        messages.append(
            "Expected 2026-03-15 / c-003 to preserve the known-good settled totals"
        )

    return sorted(set(failures)), messages


def main():
    args = parse_args()
    failures, messages = evaluate_rollup()

    if args.emit_failure_ids:
        for failure in failures:
            print(failure)
        return 0

    if failures:
        print("S19 validation failed:", file=sys.stderr)
        for message in messages:
            print(f"- {message}", file=sys.stderr)
        return 1

    print("S19 validation PASS")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
