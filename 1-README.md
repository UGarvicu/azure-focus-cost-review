# Azure FOCUS cost review

A small, **local and read-only** Python tool to group Azure Cost Management FOCUS CSV billed cost by month, service, and an allocation tag. Useful for a cloud lead checking whether teams have tagged their spend. It makes no Azure API calls and does not change resources or send cost data anywhere.

## Try it

Python 3.10 or newer; no runtime dependencies.

```bash
python -m pip install -e .
focus-cost-review examples/sample-focus.csv --tag costCenter --output report.json
python -m unittest discover -s tests -v
```

`report.json` includes the source row count and sorted groups with `currency`, `month`, `allocation`, `service`, `billed_cost`, and `rows`. The sample is synthetic. For your own data, export **Cost and usage details (FOCUS)** as CSV from Azure Cost Management, then pass its downloaded CSV path. Keep actual exports out of version control: they can contain sensitive account, resource, and tag values.

## Design choices

- Use `Decimal`, not binary floating-point, for billed costs. Preserve negative amounts, including refunds or adjustments.
- Keep currencies in separate groups; adding EUR to USD without an exchange rate is misleading.
- Missing or blank allocation tags become `(unallocated)`; `--tag` is case-sensitive. Missing service names become `(unspecified)`.
- Treat input files as independent data. Azure scheduled exports can repeat month-to-date costs across runs; **do not pass overlapping snapshots**, or the tool will double-count. It does not deduplicate charge IDs.
- Fail on malformed dates, costs, or tag JSON instead of quietly dropping records. For a large export, memory grows with the number of distinct groups, not rows; input is streamed.
- `BilledCost` is invoice-oriented, not amortized/effective cost. This is a reporting sample, not a substitute for reconciliation to an Azure invoice.

## Limitations

The tool expects the FOCUS CSV fields `BilledCost`, `BillingCurrency`, `ChargePeriodStart`, `ServiceName`, `Tags`; it does not parse Parquet, gzip, manifests, other Azure cost-export schemas, or normalize tag casing. It groups by the charge period's month, not the billing period. It does not convert currencies or claim to detect optimization opportunities. No live Azure deployment or real customer data was used in this sample.

## References

- [Microsoft FOCUS cost and usage details schema](https://learn.microsoft.com/en-us/azure/cost-management-billing/dataset-schema/cost-usage-details-focus)
- [Microsoft Cost Management exports](https://learn.microsoft.com/en-us/azure/cost-management-billing/costs/tutorial-export-acm-data)
