"""Aggregate Azure FOCUS CSV billed cost by month, service and allocation tag."""
import argparse
import csv
import json
import sys
from collections import defaultdict
from datetime import datetime
from decimal import Decimal, InvalidOperation
from pathlib import Path

REQUIRED = {"BilledCost", "BillingCurrency", "ChargePeriodStart", "ServiceName", "Tags"}


class ExportError(ValueError):
    """An input export cannot be interpreted safely."""


def parse_date(value: str, row: int) -> str:
    try:
        # FOCUS timestamps are ISO 8601; reject dates without a time component.
        if "T" not in value:
            raise ValueError("missing time")
        return datetime.fromisoformat(value.replace("Z", "+00:00")).strftime("%Y-%m")
    except ValueError as exc:
        raise ExportError(f"row {row}: invalid ChargePeriodStart: {value!r}") from exc


def parse_tags(value: str, row: int) -> dict:
    if not value.strip():
        return {}
    try:
        tags = json.loads(value)
    except json.JSONDecodeError as exc:
        raise ExportError(f"row {row}: Tags is not valid JSON") from exc
    if not isinstance(tags, dict):
        raise ExportError(f"row {row}: Tags must be a JSON object")
    return tags


def analyze(paths: list[Path], tag: str) -> dict:
    if not paths:
        raise ExportError("at least one CSV file is required")
    totals = defaultdict(Decimal)
    currencies = set()
    counts = defaultdict(int)
    for path in paths:
        try:
            with path.open(newline="", encoding="utf-8-sig") as stream:
                reader = csv.DictReader(stream)
                if not reader.fieldnames:
                    raise ExportError(f"{path}: empty CSV or missing header")
                missing = REQUIRED - set(reader.fieldnames)
                if missing:
                    raise ExportError(f"{path}: missing columns: {', '.join(sorted(missing))}")
                for number, row in enumerate(reader, start=2):
                    label = f"{path}: row {number}"
                    try:
                        amount = Decimal(row["BilledCost"].strip())
                    except (InvalidOperation, AttributeError) as exc:
                        raise ExportError(f"{label}: invalid BilledCost") from exc
                    if not amount.is_finite():
                        raise ExportError(f"{label}: non-finite BilledCost")
                    currency = (row["BillingCurrency"] or "").strip().upper()
                    if not currency:
                        raise ExportError(f"{label}: empty BillingCurrency")
                    currencies.add(currency)
                    month = parse_date(row["ChargePeriodStart"] or "", number)
                    tags = parse_tags(row["Tags"] or "", number)
                    owner = tags.get(tag)
                    if not isinstance(owner, str) or not owner.strip():
                        owner = "(unallocated)"
                    service = (row["ServiceName"] or "").strip() or "(unspecified)"
                    totals[(currency, month, owner, service)] += amount
                    counts[(currency, month, owner, service)] += 1
        except OSError as exc:
            raise ExportError(f"cannot read {path}: {exc.strerror}") from exc
    return {
        "allocation_tag": tag,
        "currencies": sorted(currencies),
        "rows": sum(counts.values()),
        "groups": [
            {"currency": currency, "month": month, "allocation": owner,
             "service": service, "billed_cost": str(totals[key]), "rows": counts[key]}
            for key in sorted(totals)
            for currency, month, owner, service in [key]
        ],
    }


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("csv", nargs="+", type=Path, help="FOCUS CSV export files")
    parser.add_argument("--tag", default="costCenter", help="allocation tag (case-sensitive)")
    parser.add_argument("--output", type=Path, help="write JSON report here (otherwise stdout)")
    args = parser.parse_args(argv)
    try:
        report = analyze(args.csv, args.tag)
        data = json.dumps(report, indent=2, ensure_ascii=False) + "\n"
        if args.output:
            args.output.write_text(data, encoding="utf-8")
        else:
            sys.stdout.write(data)
    except (ExportError, OSError) as exc:
        parser.exit(2, f"error: {exc}\n")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
