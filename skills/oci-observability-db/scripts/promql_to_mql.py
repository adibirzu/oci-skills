#!/usr/bin/env python3
"""Convert a safe PromQL subset to OCI MQL and render host dashboards.

This is deliberately not a general PromQL parser. Unsupported expressions fail
closed so operators can validate semantics instead of receiving guessed MQL.
"""
from __future__ import annotations

import argparse
import json
import re
import sys
from pathlib import Path
from typing import Any, NamedTuple


CATALOG_PATH = Path(__file__).resolve().parent.parent / "assets" / "host-dashboard-profiles.json"
VALID_GAUGE_STATISTICS = {"last", "mean"}


class UnsupportedPromQL(ValueError):
    """Raised when an expression is outside the deterministic conversion subset."""


class ConversionResult(NamedTuple):
    promql: str
    mql: str
    namespace: str
    validation_required: bool
    notes: tuple[str, ...]


_METRIC = r"[A-Za-z_:][A-Za-z0-9_:]*"
_WINDOW = r"[1-9][0-9]*(?:m|h|d)"
_SELECTOR_RE = re.compile(
    rf"^(?P<metric>{_METRIC})(?:\{{(?P<labels>[^{{}}]*)\}})?$"
)
_LABEL_RE = re.compile(
    r'^\s*(?P<name>[A-Za-z_][A-Za-z0-9_]*)\s*'
    r'(?P<operator>=|!=|=~)\s*"(?P<value>[^"]*)"\s*$'
)


def _normalized(expression: str) -> str:
    return " ".join(expression.strip().split())


def _mql_selector(selector: str, window: str) -> str:
    match = _SELECTOR_RE.fullmatch(selector.strip())
    if not match:
        raise UnsupportedPromQL(
            "unsupported metric selector; supported labels use =, !=, or =~ with quoted values"
        )
    rendered = f"{match.group('metric')}[{window}]"
    labels = match.group("labels")
    if not labels:
        return rendered
    converted: list[str] = []
    for label in labels.split(","):
        item = _LABEL_RE.fullmatch(label)
        if not item:
            raise UnsupportedPromQL(
                "unsupported label matcher; negative regex (!~) and unquoted values are not converted"
            )
        converted.append(
            f'{item.group("name")} {item.group("operator")} "{item.group("value")}"'
        )
    return f"{rendered}{{{', '.join(converted)}}}"


def _gauge(metric: str, window: str, statistic: str) -> str:
    return f"{metric}[{window}].{statistic}()"


def convert_promql(
    expression: str,
    *,
    namespace: str = "<NAMESPACE>",
    gauge_statistic: str = "last",
) -> ConversionResult:
    """Convert supported PromQL shapes to an OCI MQL candidate."""
    if gauge_statistic not in VALID_GAUGE_STATISTICS:
        raise ValueError("gauge_statistic must be 'last' or 'mean'")
    promql = _normalized(expression)

    cpu = re.fullmatch(
        rf"100\s*-\s*avg\s+by\s*\(\s*(?P<dimension>[A-Za-z_][A-Za-z0-9_]*)\s*\)"
        rf"\s*\(\s*rate\(\s*(?P<selector>{_METRIC}(?:\{{[^{{}}]*\}})?)"
        rf"\[(?P<window>{_WINDOW})\]\s*\)\s*\)\s*\*\s*100",
        promql,
    )
    if cpu:
        base = _mql_selector(cpu.group("selector"), cpu.group("window"))
        mql = (
            f"100 - ({base}.rate()).groupBy({cpu.group('dimension')}).mean() * 100"
        )
        return ConversionResult(
            promql,
            mql,
            namespace,
            True,
            (
                "Nested rate-to-mean conversion preserves the PromQL per-dimension intent.",
                "Confirm the grouping dimension exists on the OCI metric streams.",
            ),
        )

    gauge_ratio = re.fullmatch(
        rf"\(\s*(?P<total>{_METRIC})\s*-\s*(?P<available>{_METRIC})\s*\)"
        rf"\s*/\s*(?P=total)\s*\*\s*100",
        promql,
    )
    if gauge_ratio:
        total = _gauge(gauge_ratio.group("total"), "1m", gauge_statistic)
        available = _gauge(gauge_ratio.group("available"), "1m", gauge_statistic)
        return ConversionResult(
            promql,
            f"({total} - {available}) / {total} * 100",
            namespace,
            True,
            (
                f"Gauge samples use {gauge_statistic}() in each one-minute interval.",
                "Both metrics must have matching dimensions for stream-wise arithmetic.",
            ),
        )

    rate = re.fullmatch(
        rf"rate\(\s*(?P<selector>{_METRIC}(?:\{{[^{{}}]*\}})?)"
        rf"\[(?P<window>{_WINDOW})\]\s*\)"
        rf"(?:\s*\*\s*(?P<scalar>[0-9]+(?:\.[0-9]+)?))?",
        promql,
    )
    if rate:
        mql = f"{_mql_selector(rate.group('selector'), rate.group('window'))}.rate()"
        if rate.group("scalar"):
            mql += f" * {rate.group('scalar')}"
        return ConversionResult(
            promql,
            mql,
            namespace,
            True,
            (
                "OCI rate() returns the per-second average rate of change.",
                "Confirm counter monotonicity and the emitted metric dimensions.",
            ),
        )

    raise UnsupportedPromQL(
        "unsupported PromQL shape; supported conversions are avg-by rate CPU, "
        "used/total gauge percentage, and rate(selector[window]) with an optional scalar"
    )


def _load_catalog() -> dict[str, Any]:
    return json.loads(CATALOG_PATH.read_text(encoding="utf-8"))


def render_dashboard(
    *,
    profile: str,
    namespace: str,
    datasource_uid: str,
) -> dict[str, Any]:
    """Render an OCI Metrics datasource dashboard from a host profile."""
    catalog = _load_catalog()
    try:
        definition = catalog["profiles"][profile]
    except KeyError as exc:
        raise ValueError(f"unknown profile: {profile!r}; choose linux or windows") from exc

    variables = [
        {
            "name": "region",
            "label": "OCI region",
            "type": "custom",
            "query": "<REGION>",
            "current": {"text": "<REGION>", "value": "<REGION>"},
        },
        {
            "name": "compartment",
            "label": "Compartment",
            "type": "custom",
            "query": "<COMPARTMENT_NAME>",
            "current": {"text": "<COMPARTMENT_NAME>", "value": "<COMPARTMENT_NAME>"},
        },
        {
            "name": "instance",
            "label": "Host instance",
            "type": "custom",
            "query": "<INSTANCE>",
            "current": {"text": "<INSTANCE>", "value": "<INSTANCE>"},
        },
    ]
    for variable in definition["variables"]:
        placeholder = f"<{variable.upper()}>"
        variables.append(
            {
                "name": variable,
                "label": variable.replace("_", " ").title(),
                "type": "custom",
                "query": placeholder,
                "current": {"text": placeholder, "value": placeholder},
            }
        )

    panels: list[dict[str, Any]] = []
    for index, source in enumerate(definition["panels"]):
        panels.append(
            {
                "id": index + 1,
                "title": source["title"],
                "description": source["description"],
                "type": source.get("visualization", "timeseries"),
                "datasource": {
                    "type": "oci-metrics-datasource",
                    "uid": datasource_uid,
                },
                "fieldConfig": {
                    "defaults": {"unit": source["unit"]},
                    "overrides": [],
                },
                "gridPos": {
                    "h": 8,
                    "w": 12,
                    "x": 0 if index % 2 == 0 else 12,
                    "y": (index // 2) * 8,
                },
                "targets": [
                    {
                        "refId": "A",
                        "datasource": {
                            "type": "oci-metrics-datasource",
                            "uid": datasource_uid,
                        },
                        "compartment": "$compartment",
                        "region": "$region",
                        "namespace": namespace,
                        "metric": source["metric"],
                        "queryText": source["mql"],
                        "rawQuery": True,
                        "legendFormat": source["legend"],
                    }
                ],
            }
        )

    return {
        "title": f"OCI {definition['title']}",
        "uid": f"oci-{profile}-host",
        "description": (
            "Generated OCI Monitoring MQL dashboard. Validate every query against "
            "the selected namespace and live metric dimensions before provisioning."
        ),
        "tags": ["oci", "monitoring", "mql", profile],
        "schemaVersion": 39,
        "version": 1,
        "refresh": "1m",
        "time": {"from": "now-6h", "to": "now"},
        "templating": {"list": variables},
        "panels": panels,
    }


def _result_json(result: ConversionResult) -> dict[str, Any]:
    return {
        "promql": result.promql,
        "mql": result.mql,
        "namespace": result.namespace,
        "validation_required": result.validation_required,
        "notes": list(result.notes),
    }


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Convert a safe PromQL subset to OCI MQL or render a host dashboard."
    )
    subparsers = parser.add_subparsers(dest="command", required=True)

    convert = subparsers.add_parser("convert", help="convert one PromQL expression")
    convert.add_argument("expression")
    convert.add_argument("--namespace", default="<NAMESPACE>")
    convert.add_argument(
        "--gauge-statistic",
        choices=sorted(VALID_GAUGE_STATISTICS),
        default="last",
    )
    convert.add_argument("--json", action="store_true", dest="as_json")

    dashboard = subparsers.add_parser(
        "dashboard", help="render an OCI Metrics Linux or Windows dashboard"
    )
    dashboard.add_argument("--profile", choices=("linux", "windows"), required=True)
    dashboard.add_argument("--namespace", required=True)
    dashboard.add_argument("--datasource-uid", default="<OCI_METRICS_UID>")
    dashboard.add_argument("--output", type=Path)
    dashboard.add_argument("--force", action="store_true")
    return parser


def main(argv: list[str] | None = None) -> int:
    args = _build_parser().parse_args(argv)
    try:
        if args.command == "convert":
            result = convert_promql(
                args.expression,
                namespace=args.namespace,
                gauge_statistic=args.gauge_statistic,
            )
            if args.as_json:
                print(json.dumps(_result_json(result), indent=2))
            else:
                print(result.mql)
                print("Validation required: confirm namespace, dimensions, and live datapoints.")
            return 0

        rendered = render_dashboard(
            profile=args.profile,
            namespace=args.namespace,
            datasource_uid=args.datasource_uid,
        )
        payload = json.dumps(rendered, indent=2) + "\n"
        if args.output is None:
            print(payload, end="")
            return 0
        if args.output.exists() and not args.force:
            raise FileExistsError(
                f"refusing to overwrite {args.output}; pass --force after review"
            )
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(payload, encoding="utf-8")
        print(f"rendered {args.profile} dashboard: {args.output}")
        return 0
    except (UnsupportedPromQL, ValueError, FileExistsError) as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
