"""
RICA decision-support rules, grounded in Zambian copper benchmarks.

Conventions
  * Price is always interpreted as USD per tonne.
  * Grade is a PERCENTAGE of copper (0.56 means 0.56% Cu, 25 means 25% Cu).
  * Recovery is a fraction (0.90 means 90%), as in ScenarioUpdate.

evaluate_scenario(scenario, result, context=None, benchmarks=None, stage_name=None,
                  baseline=None, batch=None, history=None, today=None)

  scenario  : assumed_quantity, assumed_grade, assumed_recovery, assumed_price (USD per tonne)
  result    : simulated_value, baseline_value, value_difference
  context   : existing AssessmentContext fields only (all optional):
              ore_type, mining_method (sharpen the benchmarks),
              technical_recovery_min/_max, required_capacity_tonnes, available_capacity_tonnes,
              regulatory_status, infrastructure_status, operation_specific_technical_evidence,
              cost_data_complete, downside_price
  stage_name: name of the scenario's assumed stage (Extraction, Processing, Smelting, Refining)
  baseline  : optional baseline calculation (quantity, grade, recovery, reference_price, price_date, stage_id)
  batch     : optional mineral batch (source_type, assay_original_filename)
  history   : optional list of batch-history entries (recovery, occurred_at)
  today     : optional date, for deterministic price-age checks in tests

Outcome
  any FAIL                                   -> NOT_VIABLE
  core checks could not be assessed          -> INSUFFICIENT_INFORMATION
  any WARNING                                -> CONDITIONALLY_VIABLE
  otherwise                                  -> VIABLE
  Missing optional operational fields are treated as ideal assumptions and do not lower the
  outcome, but each one is listed in `not_verified`, recorded as a NOT_ASSESSED finding, caps
  reliability at MEDIUM and turns PROCEED into PROCEED_AFTER_VALIDATION. Unknown stages are not
  compared against an unrelated stage benchmark.
"""

import re
from datetime import date, datetime
from decimal import Decimal, InvalidOperation

# Stored on every decision so a result can be traced to the rule set that produced it.
# Bump when rules or benchmarks change in a way that can change outcomes.
ASSESSMENT_METHOD = "RULE_BASED_V1"

PASS, WARN, FAIL, NA = "PASS", "WARNING", "FAIL", "NOT_ASSESSED"
ZERO, ONE, HUNDRED = Decimal("0"), Decimal("1"), Decimal("100")
RECONCILIATION_TOLERANCE = Decimal(
    "0.01"
)  # policy: result vs quantity x grade x recovery x price
CAPACITY_HEADROOM_WARN = Decimal("0.10")


BENCHMARKS = {
    "meta": {"as_of": "2026-10-20"},
    # Regular expressions matched against the lower-cased stage name, in priority order.
    # Word-boundary anchors stop e.g. "mineral" from matching "mine".
    "stage_keywords": [
        ["SMELTING", [r"\bsmelt"]],
        ["REFINING", [r"\brefin", r"\bcathode", r"\belectrowin", r"\bsx-?ew\b"]],
        ["EXTRACTION", [r"\bextract", r"\bmining\b", r"\bmine\b"]],
        [
            "PROCESSING",
            [
                r"\bprocess",
                r"\bcrush",
                r"\bgrind",
                r"\bmill\b",
                r"\bmilling\b",
                r"\bflotation",
                r"\bleach",
                r"\bconcentrat",
            ],
        ],
    ],
    "grade_pct": {
        "ORE": {
            "OPEN_PIT": {"min": 0.32, "max": 0.88, "hard_min": 0.12, "hard_max": 2.0},
            "UNDERGROUND": {"min": 2.0, "max": 3.98, "hard_min": 1.99, "hard_max": 6.0},
            "ANY": {"min": 0.32, "max": 3.98, "hard_min": 0.12, "hard_max": 6.0},
        },
        "CONCENTRATE": {
            "ANY": {"min": 18.0, "max": 33.25, "hard_min": 10.0, "hard_max": 45.0}
        },
        "CATHODE": {
            "ANY": {"min": 99.9, "max": 100.0, "hard_min": 99.0, "hard_max": 100.0}
        },
    },
    "recovery": {
        "ORE": {
            "SULPHIDE": {"min": 0.82, "max": 0.964, "hard_min": 0.70, "hard_max": 0.98},
            "MIXED": {"min": 0.50, "max": 0.90, "hard_min": 0.30, "hard_max": 0.95},
            "OXIDE": {"min": 0.0, "max": 0.55, "hard_min": 0.0, "hard_max": 0.70},
            "NON_PRIMARY_SULPHIDE": {
                "min": 0.57,
                "max": 0.73,
                "hard_min": 0.40,
                "hard_max": 0.85,
            },
            "UNDERGROUND_SULPHIDE": {
                "min": 0.60,
                "max": 0.86,
                "hard_min": 0.45,
                "hard_max": 0.95,
            },
            "ANY": {"min": 0.60, "max": 0.97, "hard_min": 0.30, "hard_max": 0.98},
        },
        "CONCENTRATE": {
            "ANY": {"min": 0.95, "max": 1.0, "hard_min": 0.90, "hard_max": 1.0}
        },
    },
    "price_usd_per_t": {"min": 8885, "max": 14850, "hard_min": 6664, "hard_max": 18563},
    "cost": {"lowest_c1_usd_per_t": 3594, "aisc_guidance_2026_max_usd_per_t": 7826},
    "royalty_bands": [  # marginal bands on the copper price, USD per tonne
        {"up_to": 3999, "rate": 0.04},
        {"up_to": 4999, "rate": 0.065},
        {"up_to": 6999, "rate": 0.085},
        {"up_to": None, "rate": 0.10},
    ],
    "corporate_income_tax": 0.30,
    "concentrate_export_duty": 0.10,
    "scale": {
        "national_output_2025_t": 890346,
        "largest_mine_annual_cu_t": 240000,
        "largest_concentrator_t_per_year": 52000000,
    },
    "uplift": {"max": 1.0, "hard_max": 3.0},
    "baseline_checks": {
        "recovery_gain_soft": 0.09,
        "recovery_gain_hard": 0.20,  # lab-to-plant gap ~9 points
        "quantity_growth_soft": 1.0,
        "quantity_growth_hard": 3.0,  # largest Zambian expansion = doubling
        "price_move_soft": 0.34,
        "price_move_hard": 0.60,  # observed 2025-26 range ~ +34%
        "price_age_days": 90,
    },
}

_SEVERITY = {PASS: "INFO", WARN: "WARNING", NA: "WARNING", FAIL: "BLOCKER"}
_RANK = {PASS: 0, NA: 1, WARN: 2, FAIL: 3}


def load_benchmarks(path=None):
    return BENCHMARKS


def to_decimal(value):
    if value is None or isinstance(value, bool):
        return None
    try:
        return Decimal(str(value))
    except (InvalidOperation, TypeError, ValueError):
        return None


def fmt(value, places=2):
    d = to_decimal(value)
    return None if d is None else f"{d:,.{places}f}"


def _get(obj, name):
    if obj is None:
        return None
    return obj.get(name) if isinstance(obj, dict) else getattr(obj, name, None)


def make_finding(code, category, outcome, message, actual=None, expected=None):
    return {
        "rule_code": code,
        "category": category,
        "outcome": outcome,
        "severity": _SEVERITY[outcome],
        "message": message,
        "actual_value": str(actual) if actual is not None else None,
        "expected_value": str(expected) if expected is not None else None,
    }


class _Ledger:
    def __init__(self):
        self.findings, self.recommendations = [], []

    def add(self, finding, recommend=None, on=(WARN, FAIL)):
        self.findings.append(finding)
        if recommend and finding["outcome"] in on:
            self.recommendations.append(recommend)
        return finding

    def assessed(self, *codes):
        return any(
            f["rule_code"] in codes and f["outcome"] != NA for f in self.findings
        )


def _range_text(lo, hi, places):
    if lo is not None and hi is not None:
        return f"{fmt(lo, places)} to {fmt(hi, places)}"
    return f">= {fmt(lo, places)}" if lo is not None else f"<= {fmt(hi, places)}"


def _check(ledger, code, cat, label, value, bench, places=2, unit=""):
    """PASS inside min..max, WARNING outside but inside hard limits, FAIL beyond hard limits."""
    if value is None:
        return ledger.add(make_finding(code, cat, NA, f"{label} is missing."))
    bench = bench or {}
    lo, hi = to_decimal(bench.get("min")), to_decimal(bench.get("max"))
    hlo, hhi = to_decimal(bench.get("hard_min")), to_decimal(bench.get("hard_max"))
    if lo is None and hi is None:
        return ledger.add(
            make_finding(
                code,
                cat,
                NA,
                f"No Zambian benchmark is available for the {label.lower()}.",
                f"{fmt(value, places)}{unit}",
            )
        )
    exp = _range_text(lo, hi, places) + unit
    act = f"{fmt(value, places)}{unit}"
    below, above = (lo is not None and value < lo), (hi is not None and value > hi)
    if not below and not above:
        return ledger.add(
            make_finding(
                code,
                cat,
                PASS,
                f"{label} is within the Zambian benchmark range.",
                act,
                exp,
            )
        )
    hard = (hlo is not None and value < hlo) or (hhi is not None and value > hhi)
    if hard:
        return ledger.add(
            make_finding(
                code,
                cat,
                FAIL,
                f"{label} is far outside the Zambian benchmark range and is not realistic.",
                act,
                exp,
            ),
            f"Revise the {label.lower()}; it is beyond what Zambian operations report.",
        )
    return ledger.add(
        make_finding(
            code,
            cat,
            WARN,
            f"{label} is outside the Zambian benchmark range.",
            act,
            exp,
        ),
        f"Validate the {label.lower()} with operation-specific data.",
    )


def _stage(stage_name, context, grade_pct, bm):
    """RICA stage -> (stage_kind, grade_material, recovery_material)."""
    name = (stage_name or "").lower()
    kind = (context.get("stage_kind") or "").upper() or None
    if kind is None:
        for k, patterns in bm["stage_keywords"]:
            if any(re.search(pattern, name) for pattern in patterns):
                kind = k
                break
    if kind in ("EXTRACTION", "PROCESSING"):
        thr = to_decimal(bm["grade_pct"]["CONCENTRATE"]["ANY"]["hard_min"])
        material = (
            "CONCENTRATE" if (grade_pct is not None and grade_pct >= thr) else "ORE"
        )
        return kind, material, "ORE"
    if kind == "SMELTING":
        return kind, "CONCENTRATE", "CONCENTRATE"
    if kind == "REFINING":
        return kind, "CATHODE", None
    return None, None, None


def royalty_rate(price_t, bm):
    """Effective Zambian mineral royalty as a fraction of value at a copper price in USD/t."""
    price_t = to_decimal(price_t)
    if price_t is None or price_t <= 0:
        return ZERO
    total, prev = ZERO, ZERO
    for band in bm["royalty_bands"]:
        top = to_decimal(band["up_to"])
        upper = price_t if top is None else min(price_t, top)
        if upper > prev:
            total += (upper - prev) * to_decimal(band["rate"])
        prev = upper
        if top is None or price_t <= top:
            break
    return total / price_t


def _as_date(v):
    if isinstance(v, datetime):
        return v.date()
    if isinstance(v, date):
        return v
    try:
        return datetime.fromisoformat(str(v)).date()
    except (TypeError, ValueError):
        return None


# For each rule: why a PASS is good news, and (why it is a problem, what to do) when it warns or fails.
_PRO_PRIORITY = [
    "INCREMENTAL_VALUE",
    "GRADE_VS_BENCHMARK",
    "RECOVERY_VS_BENCHMARK",
    "RECOVERY_VS_SITE_RANGE",
    "PRICE_VS_BAND",
    "PRICE_COVERS_INDUSTRY_COST",
    "UPLIFT_PLAUSIBILITY",
    "MARKET_RESILIENCE",
]

_PRO = {
    "INCREMENTAL_VALUE": "The scenario is worth about ${actual} more than the baseline.",
    "GRADE_VS_BENCHMARK": "The assumed grade ({actual}) is inside the range Zambian operations report ({expected}).",
    "ORE_BELOW_CUTOFF": "The grade ({actual}) is above the level Zambian mines treat as ore ({expected}).",
    "RECOVERY_VS_BENCHMARK": "The assumed recovery ({actual}) is in line with what Zambian plants achieve ({expected}).",
    "RECOVERY_VS_SITE_RANGE": "Recovery ({actual}) falls inside the site-specific range you supplied ({expected}).",
    "UPLIFT_PLAUSIBILITY": "The value gain over baseline ({actual}) is within what Zambian operations have delivered (up to +100%).",
    "SCALE_VS_LARGEST_MINE": "The recoverable copper ({actual} t) is within the scale of Zambian operations.",
    "PRICE_VS_BAND": "The assumed price ({actual} USD/t) is inside the recent LME range ({expected} USD/t).",
    "PRICE_COVERS_INDUSTRY_COST": "The price ({actual} USD/t) is above the all-in cost Zambian producers report ({expected_clean} USD/t), so a margin is possible.",
    "MARKET_RESILIENCE": "At the downside price ({actual} USD/t) the scenario still covers reported Zambian all-in costs.",
    "RECOVERY_VS_BASELINE": "The recovery change versus baseline ({actual}) is realistic.",
    "QUANTITY_VS_BASELINE": "The quantity change versus baseline ({actual}) is realistic.",
    "PRICE_VS_BASELINE": "The scenario and baseline prices are comparable, so the gain does not come from a price assumption.",
    "RECOVERY_VS_MEASURED": "The assumed recovery matches measured plant performance for this batch.",
    "ASSAY_EVIDENCE": "An assay document supports the batch grade.",
    "PROCESSING_CAPACITY": "Processing capacity is sufficient ({actual} available for {expected} needed).",
    "INFRASTRUCTURE": "Required infrastructure is available.",
    "REGULATORY_STATUS": "Regulatory requirements are confirmed.",
    "TECHNICAL_EVIDENCE": "Operation-specific technical evidence supports the assumptions.",
    "COST_COMPLETENESS": "Cost data is complete, so the result is not flattered by missing costs.",
}

_CON = {
    "INCREMENTAL_VALUE": (
        "The scenario is worth about ${gap} less than the baseline, so choosing it would lose value.",
        "Do not choose this scenario over the baseline unless the assumptions behind the lower value change.",
    ),
    "GRADE_VS_BENCHMARK": (
        "The assumed grade ({actual}) is outside what Zambian operations report ({expected}), so the copper may not exist at that concentration.",
        "Check the grade against an assay or the deposit's reserve statement, and confirm it is entered as a percentage.",
    ),
    "ORE_BELOW_CUTOFF": (
        "The grade ({actual}) is below the cut-off Zambian mines use ({expected}), so this material would be treated as waste.",
        "Raise the grade assumption or confirm the cut-off for this deposit.",
    ),
    "RECOVERY_VS_BENCHMARK": (
        "The assumed recovery ({actual}) is outside what Zambian plants achieve ({expected}), so the recoverable copper and the value may be overstated.",
        "Support the recovery with test work or plant data, or use a figure inside the Zambian range.",
    ),
    "RECOVERY_VS_SITE_RANGE": (
        "Recovery ({actual}) is outside the site-specific range supplied ({expected}).",
        "Use a recovery inside the site range, or explain what changes at this site.",
    ),
    "UPLIFT_PLAUSIBILITY": (
        "The value uplift over baseline ({actual}) exceeds the configured plausibility limit.",
        "Look for an input or unit error in the scenario, or phase the plan into realistic steps.",
    ),
    "SCALE_VS_NATIONAL_OUTPUT": (
        "The recoverable copper ({actual} t) is more than Zambia produced in all of 2025 ({expected} t).",
        "Check the quantity and its units.",
    ),
    "SCALE_VS_LARGEST_MINE": (
        "If annual, the recoverable copper ({actual} t) is bigger than any single Zambian mine plans to produce ({expected} t).",
        "Confirm the time basis, or split the volume across operations.",
    ),
    "THROUGHPUT_VS_LARGEST_PLANT": (
        "The ore quantity ({actual} t) is above the largest concentrator throughput in Zambia ({expected} t a year), if annual.",
        "Confirm the time basis for the ore quantity.",
    ),
    "PRICE_VS_BAND": (
        "The assumed price ({actual} USD/t) is outside the recent LME range ({expected} USD/t), so the value depends on a price the market has not recently paid.",
        "Use a price inside the recent range, or justify the assumption.",
    ),
    "PRICE_COVERS_INDUSTRY_COST": (
        "At {actual} USD/t the price is below what Zambian producers need to cover their costs ({expected_clean} USD/t), so the operation could lose money even if the numbers add up.",
        "Re-run with full costs and a realistic price before going ahead.",
    ),
    "MARKET_RESILIENCE": (
        "If the price falls to the downside case, the scenario no longer covers Zambian costs ({actual} against {expected_clean} USD/t).",
        "Consider hedging, offtake terms or a larger margin of safety.",
    ),
    "RECOVERY_VS_BASELINE": (
        "Recovery rises {actual} over baseline, more than the usual lab-to-plant gap of about 9 points, so part of the gain depends on an improvement that is not yet proven.",
        "Back the improvement with pilot or plant data.",
    ),
    "QUANTITY_VS_BASELINE": (
        "Quantity grows {actual} over baseline; the largest expansion seen in Zambia was a doubling (+100%).",
        "Confirm capacity and capital for this scale-up, or phase it.",
    ),
    "PRICE_VS_BASELINE": (
        "The scenario price differs from the baseline price by {actual}, so part of the gain comes from the price assumption and not from the operation.",
        "Compare scenario and baseline at the same price.",
    ),
    "BASELINE_PRICE_AGE": (
        "The baseline price is {actual} old, and copper moved sharply in 2025-26, so the baseline may be out of date.",
        "Recalculate the baseline with a current price.",
    ),
    "STAGE_VS_BASELINE": (
        "The scenario and the baseline are at different processing stages, so the gain is not like-for-like.",
        "Compare scenario and baseline at the same stage.",
    ),
    "CALC_RECONCILIATION": (
        "The scenario value does not match quantity x grade x recovery x price ({actual} against {expected}), so the result may include deductions or the inputs may be in the wrong units.",
        "Confirm the grade units (percent) and what the result includes.",
    ),
    "RECOVERY_VS_MEASURED": (
        "Assumed recovery ({actual}) is well above measured plant performance ({expected}).",
        "Align the assumption with measured results or justify the improvement.",
    ),
    "ASSAY_EVIDENCE": (
        "No assay document backs the batch grade, so the grade is an assumption, not a measurement.",
        "Upload an assay document for the batch.",
    ),
    "PROCESSING_CAPACITY": (
        "Available capacity ({actual}) does not comfortably cover the requirement ({expected}), so the volume may not be processed as planned.",
        "Confirm extra capacity, or reduce the throughput assumption.",
    ),
    "INFRASTRUCTURE": (
        "Infrastructure is limited or unavailable; in Zambia power is the usual constraint, and it raises costs and interrupts production.",
        "Secure power and other infrastructure before relying on this scenario.",
    ),
    "REGULATORY_STATUS": (
        "A licence, environmental approval or processing, trading or export right is not confirmed, so the activity may not be allowed to proceed.",
        "Confirm the approvals with the Minerals Regulation Commission and the environmental authority.",
    ),
    "TECHNICAL_EVIDENCE": (
        "There is no operation-specific technical evidence, so grade and recovery are not proven for this site.",
        "Validate the assumptions with test work or operating data.",
    ),
    "COST_COMPLETENESS": (
        "Cost data is incomplete, so the gain may be overstated.",
        "Complete the cost estimate before relying on the result.",
    ),
}


def _fill(template, f, gap=""):
    exp = f.get("expected_value") or ""
    values = {
        "actual": f.get("actual_value") or "",
        "expected": exp,
        "expected_clean": exp.replace(">= ", "").replace("<= ", ""),
        "gap": gap,
    }
    return template.format(**values)


def evaluate_scenario(
    scenario,
    result,
    context=None,
    benchmarks=None,
    stage_name=None,
    baseline=None,
    batch=None,
    history=None,
    today=None,
):
    ctx = context or {}
    bm = benchmarks or BENCHMARKS
    bc = bm["baseline_checks"]
    L = _Ledger()

    q = to_decimal(_get(scenario, "assumed_quantity"))
    g = to_decimal(_get(scenario, "assumed_grade"))  # percent
    r = to_decimal(_get(scenario, "assumed_recovery"))  # fraction
    p = to_decimal(_get(scenario, "assumed_price"))
    sim = to_decimal(_get(result, "simulated_value"))
    base = to_decimal(_get(result, "baseline_value"))
    diff = to_decimal(_get(result, "value_difference"))
    delta = (
        (diff if diff is not None else sim - base)
        if (sim is not None and base is not None)
        else None
    )

    price_t = p

    stage_kind, material, rec_material = _stage(stage_name, ctx, g, bm)
    ore_type = (ctx.get("ore_type") or "ANY").upper()
    method = (ctx.get("mining_method") or "ANY").upper()
    contained = q * g / HUNDRED if (q is not None and g is not None) else None
    recoverable = contained * r if (contained is not None and r is not None) else None

    # INPUT
    if g is None:
        L.add(
            make_finding("GRADE_RANGE", "INPUT", NA, "Grade is missing or not numeric.")
        )
    elif not ZERO <= g <= HUNDRED:
        L.add(
            make_finding(
                "GRADE_RANGE",
                "INPUT",
                FAIL,
                "Grade must be a percentage between 0 and 100.",
                fmt(g),
                "0 to 100",
            )
        )
    else:
        L.add(
            make_finding(
                "GRADE_RANGE",
                "INPUT",
                PASS,
                "Grade is a valid percentage.",
                f"{fmt(g)}%",
                "0 to 100%",
            )
        )
    if r is None:
        L.add(
            make_finding(
                "RECOVERY_RANGE", "INPUT", NA, "Recovery is missing or not numeric."
            )
        )
    elif not ZERO <= r <= ONE:
        L.add(
            make_finding(
                "RECOVERY_RANGE",
                "INPUT",
                FAIL,
                "Recovery must be a fraction between 0 and 1.",
                fmt(r, 4),
                "0 to 1",
            )
        )
    else:
        L.add(
            make_finding(
                "RECOVERY_RANGE",
                "INPUT",
                PASS,
                "Recovery is a valid fraction.",
                fmt(r, 4),
                "0 to 1",
            )
        )
    if q is None or q < 0:
        L.add(
            make_finding(
                "QUANTITY_VALID",
                "INPUT",
                FAIL,
                "Quantity must be numeric and non-negative.",
                fmt(q),
                ">= 0",
            )
        )
    else:
        L.add(
            make_finding(
                "QUANTITY_VALID", "INPUT", PASS, "Quantity is valid.", fmt(q), ">= 0"
            )
        )
    if p is None or p <= 0:
        L.add(
            make_finding(
                "PRICE_VALID",
                "INPUT",
                FAIL,
                "Price must be numeric and greater than zero.",
                fmt(p),
                "> 0",
            )
        )
    else:
        L.add(
            make_finding(
                "PRICE_VALID",
                "INPUT",
                PASS,
                "Price is valid (USD per tonne).",
                f"USD {fmt(p)}",
                "> 0",
            )
        )

    if stage_kind is None:
        L.add(
            make_finding(
                "STAGE_MAPPING",
                "INPUT",
                NA,
                "No stage-specific benchmark was applied; stage-independent checks were used.",
            )
        )
    else:
        L.add(
            make_finding(
                "STAGE_MAPPING",
                "INPUT",
                PASS,
                f"Stage treated as {stage_kind.lower()}; grade judged as {material.lower()}.",
                material,
            )
        )

    if None not in (q, g, r, price_t, sim):
        expected = contained * r * price_t
        if expected > 0:
            gap = abs(sim - expected) / expected
            if gap <= RECONCILIATION_TOLERANCE:
                L.add(
                    make_finding(
                        "CALC_RECONCILIATION",
                        "INPUT",
                        PASS,
                        "Scenario value reconciles with quantity x grade% x recovery x price.",
                        fmt(sim, 0),
                        fmt(expected, 0),
                    )
                )
            else:
                L.add(
                    make_finding(
                        "CALC_RECONCILIATION",
                        "INPUT",
                        WARN,
                        f"Scenario value differs from quantity x grade% x recovery x price by {gap * 100:.1f}%. "
                        "Check the grade units and whether the result includes deductions.",
                        fmt(sim, 0),
                        fmt(expected, 0),
                    ),
                    "Confirm the grade units (percent) and what the result table includes.",
                )

    # ECONOMIC
    if delta is None:
        L.add(
            make_finding(
                "RESULTS_PRESENT",
                "ECONOMIC",
                NA,
                "Scenario value or baseline value is missing.",
            )
        )
    else:
        L.add(
            make_finding(
                "RESULTS_PRESENT",
                "ECONOMIC",
                PASS,
                "Scenario and baseline values are available.",
            )
        )
        if delta > 0:
            L.add(
                make_finding(
                    "INCREMENTAL_VALUE",
                    "ECONOMIC",
                    PASS,
                    "Scenario value exceeds baseline.",
                    fmt(delta),
                    "> 0",
                )
            )
        elif delta == 0:
            L.add(
                make_finding(
                    "INCREMENTAL_VALUE",
                    "ECONOMIC",
                    WARN,
                    "Scenario value equals baseline.",
                    fmt(delta),
                    "> 0",
                ),
                "Review whether the scenario changes anything of value.",
            )
        else:
            L.add(
                make_finding(
                    "INCREMENTAL_VALUE",
                    "ECONOMIC",
                    FAIL,
                    "Scenario value is below baseline.",
                    fmt(delta),
                    "> 0",
                ),
                "Review scenario assumptions and why the value is below baseline.",
            )

    roy = royalty_rate(price_t, bm) if price_t is not None else None
    if roy is not None and delta is not None and delta > 0:
        tax = to_decimal(bm["corporate_income_tax"])
        after_roy = delta * (ONE - roy)
        L.add(
            make_finding(
                "ROYALTY_BURDEN",
                "ECONOMIC",
                PASS,
                f"Zambian mineral royalty is about {roy * 100:.1f}% of value at this price. Gain after royalty ~ {fmt(after_roy, 0)}; "
                f"after {tax * 100:.0f}% income tax ~ {fmt(after_roy * (ONE - tax), 0)} (before operating costs).",
                f"{roy * 100:.2f}%",
                "informational",
            )
        )
    if stage_kind == "SMELTING":
        L.add(
            make_finding(
                "CONCENTRATE_EXPORT_DUTY",
                "ECONOMIC",
                PASS,
                f"If concentrate is exported instead of smelted in Zambia, a {to_decimal(bm['concentrate_export_duty']) * 100:.0f}% export duty applies unless waived.",
                None,
                "informational",
            )
        )

    # PHYSICAL
    grade_bm = None
    if material == "ORE":
        grade_bm = bm["grade_pct"]["ORE"].get(method) or bm["grade_pct"]["ORE"]["ANY"]
    elif material in ("CONCENTRATE", "CATHODE"):
        grade_bm = bm["grade_pct"][material]["ANY"]
    if stage_kind is not None:
        _check(
            L,
            "GRADE_VS_BENCHMARK",
            "PHYSICAL",
            "Assumed grade",
            g,
            grade_bm,
            places=2,
            unit="%",
        )
        if material == "ORE" and g is not None and grade_bm:
            cut = to_decimal(grade_bm.get("hard_min"))
            if g < cut:
                L.add(
                    make_finding(
                        "ORE_BELOW_CUTOFF",
                        "PHYSICAL",
                        FAIL,
                        "Grade is below the lowest economic cut-off modelled for Zambian operations; the material would be waste.",
                        f"{fmt(g)}%",
                        f">= {fmt(cut)}%",
                    ),
                    "Raise the grade assumption or re-check the cut-off for this deposit.",
                )
            else:
                L.add(
                    make_finding(
                        "ORE_BELOW_CUTOFF",
                        "PHYSICAL",
                        PASS,
                        "Grade is above the modelled economic cut-off.",
                        f"{fmt(g)}%",
                        f">= {fmt(cut)}%",
                    )
                )

    rec_bm = None
    if rec_material in ("ORE", "CONCENTRATE"):
        table = bm["recovery"][rec_material]
        rec_bm = table.get(ore_type) or table["ANY"]
    rmin, rmax = (
        to_decimal(ctx.get("technical_recovery_min")),
        to_decimal(ctx.get("technical_recovery_max")),
    )
    has_site = rmin is not None and rmax is not None
    if has_site and r is not None:
        exp = f"{fmt(rmin * 100, 1)}% to {fmt(rmax * 100, 1)}%"
        act = f"{fmt(r * 100, 1)}%"
        if rmin > rmax:
            L.add(
                make_finding(
                    "RECOVERY_VS_SITE_RANGE",
                    "PHYSICAL",
                    FAIL,
                    "The site-specific recovery range is invalid (min > max).",
                    act,
                    exp,
                ),
                "Correct the site-specific recovery range.",
            )
        elif rmin <= r <= rmax:
            L.add(
                make_finding(
                    "RECOVERY_VS_SITE_RANGE",
                    "PHYSICAL",
                    PASS,
                    "Recovery falls within the site-specific range.",
                    act,
                    exp,
                )
            )
        else:
            L.add(
                make_finding(
                    "RECOVERY_VS_SITE_RANGE",
                    "PHYSICAL",
                    WARN,
                    "Recovery is outside the site-specific range.",
                    act,
                    exp,
                ),
                "Validate recovery for the ore type and processing route.",
            )
    if stage_kind is not None and stage_kind != "REFINING":
        _scaled = {k: v * 100 for k, v in rec_bm.items()} if rec_bm else None
        _check(
            L,
            "RECOVERY_VS_BENCHMARK",
            "PHYSICAL",
            "Assumed recovery",
            r * 100 if r is not None else None,
            _scaled,
            places=1,
            unit="%",
        )

    uplift = (
        (delta / base)
        if (delta is not None and base is not None and base > 0)
        else None
    )
    if uplift is None:
        L.add(
            make_finding(
                "UPLIFT_PLAUSIBILITY",
                "PHYSICAL",
                NA,
                "Uplift cannot be calculated (baseline is zero or missing).",
            )
        )
    elif uplift <= 0:
        L.add(
            make_finding(
                "UPLIFT_PLAUSIBILITY",
                "PHYSICAL",
                PASS,
                "No uplift over baseline to test.",
                fmt(uplift * 100, 1) + "%",
            )
        )
    else:
        _check(
            L,
            "UPLIFT_PLAUSIBILITY",
            "PHYSICAL",
            "Value uplift over baseline",
            uplift * 100,
            {
                "max": bm["uplift"]["max"] * 100,
                "hard_max": bm["uplift"]["hard_max"] * 100,
            },
            places=1,
            unit="%",
        )

    if recoverable is not None:
        nat = to_decimal(bm["scale"]["national_output_2025_t"])
        big = to_decimal(bm["scale"]["largest_mine_annual_cu_t"])
        if recoverable > nat:
            L.add(
                make_finding(
                    "SCALE_VS_NATIONAL_OUTPUT",
                    "PHYSICAL",
                    FAIL,
                    "Recoverable copper exceeds Zambia's entire 2025 output.",
                    fmt(recoverable, 0),
                    f"<= {fmt(nat, 0)}",
                ),
                "Check the quantity and units.",
            )
        elif recoverable > big:
            L.add(
                make_finding(
                    "SCALE_VS_LARGEST_MINE",
                    "PHYSICAL",
                    WARN,
                    "If this quantity is annual, it exceeds the largest planned single-mine output in Zambia.",
                    fmt(recoverable, 0),
                    f"<= {fmt(big, 0)}",
                ),
                "Confirm the time basis and that one operation can deliver this volume.",
            )
        else:
            L.add(
                make_finding(
                    "SCALE_VS_LARGEST_MINE",
                    "PHYSICAL",
                    PASS,
                    "Recoverable copper is within the scale of Zambian operations.",
                    fmt(recoverable, 0),
                    f"<= {fmt(big, 0)}",
                )
            )
    if (
        stage_kind in ("EXTRACTION", "PROCESSING")
        and material == "ORE"
        and q is not None
    ):
        mx = to_decimal(bm["scale"]["largest_concentrator_t_per_year"])
        if q > mx:
            L.add(
                make_finding(
                    "THROUGHPUT_VS_LARGEST_PLANT",
                    "PHYSICAL",
                    WARN,
                    "Ore quantity exceeds the largest concentrator throughput in Zambia (if annual).",
                    fmt(q, 0),
                    f"<= {fmt(mx, 0)}",
                ),
                "Confirm the time basis for the ore quantity.",
            )

    if price_t is not None:
        _check(
            L,
            "PRICE_VS_BAND",
            "MARKET",
            "Assumed price (USD/t)",
            price_t,
            bm["price_usd_per_t"],
            places=0,
        )
        if stage_kind in ("EXTRACTION", "PROCESSING"):
            c1_low = to_decimal(bm["cost"]["lowest_c1_usd_per_t"])
            aisc = to_decimal(bm["cost"]["aisc_guidance_2026_max_usd_per_t"])
            if price_t < c1_low:
                L.add(
                    make_finding(
                        "PRICE_COVERS_INDUSTRY_COST",
                        "MARKET",
                        FAIL,
                        "Assumed price is below the lowest cash cost reported by Zambian producers.",
                        fmt(price_t, 0),
                        f">= {fmt(c1_low, 0)}",
                    )
                )
            elif price_t < aisc:
                L.add(
                    make_finding(
                        "PRICE_COVERS_INDUSTRY_COST",
                        "MARKET",
                        WARN,
                        "Assumed price is below First Quantum's 2026 all-in sustaining cost guidance; margins would be thin.",
                        fmt(price_t, 0),
                        f">= {fmt(aisc, 0)}",
                    ),
                    "Test the scenario at a lower price and with full costs.",
                )
            else:
                L.add(
                    make_finding(
                        "PRICE_COVERS_INDUSTRY_COST",
                        "MARKET",
                        PASS,
                        "Assumed price covers reported Zambian all-in sustaining costs.",
                        fmt(price_t, 0),
                        f">= {fmt(aisc, 0)}",
                    )
                )

    down = to_decimal(ctx.get("downside_price"))
    if down is not None and stage_kind in ("EXTRACTION", "PROCESSING"):
        down_t = down
        net_down = down_t * (ONE - royalty_rate(down_t, bm))
        c1_low = to_decimal(bm["cost"]["lowest_c1_usd_per_t"])
        aisc = to_decimal(bm["cost"]["aisc_guidance_2026_max_usd_per_t"])
        if price_t is not None and down_t >= price_t:
            L.add(
                make_finding(
                    "MARKET_RESILIENCE",
                    "MARKET",
                    NA,
                    "The downside price is not below the assumed price.",
                    fmt(down_t, 0),
                    f"< {fmt(price_t, 0)}",
                )
            )
        elif net_down < c1_low:
            L.add(
                make_finding(
                    "MARKET_RESILIENCE",
                    "MARKET",
                    FAIL,
                    "At the downside price, revenue after royalty is below the lowest cash cost reported in Zambia.",
                    fmt(net_down, 0),
                    f">= {fmt(c1_low, 0)}",
                ),
                "The scenario does not survive a price fall of this size.",
            )
        elif down_t < aisc:
            L.add(
                make_finding(
                    "MARKET_RESILIENCE",
                    "MARKET",
                    WARN,
                    "At the downside price, the price is below Zambian all-in sustaining costs; margins would be thin or negative.",
                    fmt(down_t, 0),
                    f">= {fmt(aisc, 0)}",
                ),
                "Consider hedging or offtake terms, or a larger margin of safety.",
            )
        else:
            L.add(
                make_finding(
                    "MARKET_RESILIENCE",
                    "MARKET",
                    PASS,
                    "At the downside price, the scenario still covers reported Zambian all-in costs.",
                    fmt(down_t, 0),
                    f">= {fmt(aisc, 0)}",
                )
            )

    # BASELINE COMPARISON
    if baseline is not None:
        bq, _bg = (
            to_decimal(_get(baseline, "quantity")),
            to_decimal(_get(baseline, "grade")),
        )
        br, bp = (
            to_decimal(_get(baseline, "recovery")),
            to_decimal(_get(baseline, "reference_price")),
        )
        bstage, pdate = (
            _get(baseline, "stage_id"),
            _as_date(_get(baseline, "price_date")),
        )
        sid = _get(scenario, "assumed_stage_id")

        if br is not None and r is not None:
            gain = r - br
            soft, hard = (
                to_decimal(bc["recovery_gain_soft"]),
                to_decimal(bc["recovery_gain_hard"]),
            )
            if gain > hard:
                L.add(
                    make_finding(
                        "RECOVERY_VS_BASELINE",
                        "PHYSICAL",
                        FAIL,
                        "Recovery improves far more than Zambian plants show between good and poor performance.",
                        f"+{gain * 100:.1f} points",
                        f"<= +{soft * 100:.0f} points",
                    ),
                    "Revise the recovery assumption.",
                )
            elif gain > soft:
                L.add(
                    make_finding(
                        "RECOVERY_VS_BASELINE",
                        "PHYSICAL",
                        WARN,
                        "Recovery improves by more than the typical lab-to-plant gap (about 9 points).",
                        f"+{gain * 100:.1f} points",
                        f"<= +{soft * 100:.0f} points",
                    ),
                    "Support the recovery improvement with test work or plant data.",
                )
            else:
                L.add(
                    make_finding(
                        "RECOVERY_VS_BASELINE",
                        "PHYSICAL",
                        PASS,
                        "Recovery change versus baseline is realistic.",
                        f"{gain * 100:+.1f} points",
                        f"<= +{soft * 100:.0f} points",
                    )
                )
        if bq is not None and bq > 0 and q is not None:
            growth = q / bq - ONE
            soft, hard = (
                to_decimal(bc["quantity_growth_soft"]),
                to_decimal(bc["quantity_growth_hard"]),
            )
            if growth > hard:
                L.add(
                    make_finding(
                        "QUANTITY_VS_BASELINE",
                        "PHYSICAL",
                        FAIL,
                        "Quantity grows far beyond the largest expansion seen in Zambia (a doubling).",
                        f"+{growth * 100:.0f}%",
                        f"<= +{soft * 100:.0f}%",
                    ),
                    "Revise the quantity or phase it.",
                )
            elif growth > soft:
                L.add(
                    make_finding(
                        "QUANTITY_VS_BASELINE",
                        "PHYSICAL",
                        WARN,
                        "Quantity more than doubles versus baseline, the largest Zambian expansion step.",
                        f"+{growth * 100:.0f}%",
                        f"<= +{soft * 100:.0f}%",
                    ),
                    "Confirm capacity and capital for this scale-up.",
                )
            else:
                L.add(
                    make_finding(
                        "QUANTITY_VS_BASELINE",
                        "PHYSICAL",
                        PASS,
                        "Quantity change versus baseline is realistic.",
                        f"{growth * 100:+.0f}%",
                        f"<= +{soft * 100:.0f}%",
                    )
                )
        if bp is not None and bp > 0 and p is not None:
            move = abs(p / bp - ONE)
            soft, hard = (
                to_decimal(bc["price_move_soft"]),
                to_decimal(bc["price_move_hard"]),
            )
            if move > hard:
                L.add(
                    make_finding(
                        "PRICE_VS_BASELINE",
                        "MARKET",
                        FAIL,
                        "Scenario price differs from the baseline price by more than any recent Zambian-era price swing.",
                        f"{move * 100:.0f}%",
                        f"<= {soft * 100:.0f}%",
                    ),
                    "Use a price consistent with the baseline or justify the difference.",
                )
            elif move > soft:
                L.add(
                    make_finding(
                        "PRICE_VS_BASELINE",
                        "MARKET",
                        WARN,
                        "Scenario price differs from the baseline price by more than the 2025-26 observed range.",
                        f"{move * 100:.0f}%",
                        f"<= {soft * 100:.0f}%",
                    ),
                    "Check that scenario and baseline use comparable prices.",
                )
            else:
                L.add(
                    make_finding(
                        "PRICE_VS_BASELINE",
                        "MARKET",
                        PASS,
                        "Scenario and baseline prices are comparable.",
                        f"{move * 100:.0f}%",
                        f"<= {soft * 100:.0f}%",
                    )
                )
        if pdate is not None:
            age = ((today or date.today()) - pdate).days
            lim = int(bc["price_age_days"])
            if age > lim:
                L.add(
                    make_finding(
                        "BASELINE_PRICE_AGE",
                        "MARKET",
                        WARN,
                        "The baseline price is old; copper moved sharply in 2025-26.",
                        f"{age} days",
                        f"<= {lim} days",
                    ),
                    "Recalculate the baseline with a current price.",
                )
            else:
                L.add(
                    make_finding(
                        "BASELINE_PRICE_AGE",
                        "MARKET",
                        PASS,
                        "The baseline price is recent.",
                        f"{age} days",
                        f"<= {lim} days",
                    )
                )
        if bstage is not None and sid is not None and bstage != sid:
            L.add(
                make_finding(
                    "STAGE_VS_BASELINE",
                    "PHYSICAL",
                    WARN,
                    "Scenario and baseline are at different processing stages; their values are not like-for-like.",
                ),
                "Compare scenario and baseline at the same stage.",
            )

    #  BATCH EVIDENCE (optional)
    if batch is not None:
        assay = _get(batch, "assay_original_filename")
        if assay:
            L.add(
                make_finding(
                    "ASSAY_EVIDENCE",
                    "EVIDENCE",
                    PASS,
                    "An assay document supports the batch grade.",
                )
            )
        else:
            L.add(
                make_finding(
                    "ASSAY_EVIDENCE",
                    "EVIDENCE",
                    WARN,
                    "No assay document is attached to the batch, so the grade is not backed by a measurement.",
                ),
                "Upload an assay document for the batch.",
            )
    if history:
        rows = [h for h in history if to_decimal(_get(h, "recovery")) is not None]
        if rows and r is not None:
            rows.sort(key=lambda h: str(_get(h, "occurred_at") or ""))
            measured = to_decimal(_get(rows[-1], "recovery"))
            over = r - measured
            soft, hard = (
                to_decimal(bc["recovery_gain_soft"]),
                to_decimal(bc["recovery_gain_hard"]),
            )
            if over > hard:
                L.add(
                    make_finding(
                        "RECOVERY_VS_MEASURED",
                        "EVIDENCE",
                        FAIL,
                        "Assumed recovery is far above the latest measured recovery for this batch.",
                        f"{fmt(r * 100, 1)}%",
                        f"{fmt(measured * 100, 1)}% measured",
                    ),
                    "Align the assumption with measured performance.",
                )
            elif over > soft:
                L.add(
                    make_finding(
                        "RECOVERY_VS_MEASURED",
                        "EVIDENCE",
                        WARN,
                        "Assumed recovery is more than about 9 points above the latest measured recovery.",
                        f"{fmt(r * 100, 1)}%",
                        f"{fmt(measured * 100, 1)}% measured",
                    ),
                    "Justify the improvement over measured performance.",
                )
            else:
                L.add(
                    make_finding(
                        "RECOVERY_VS_MEASURED",
                        "EVIDENCE",
                        PASS,
                        "Assumed recovery is consistent with the latest measured recovery.",
                        f"{fmt(r * 100, 1)}%",
                        f"{fmt(measured * 100, 1)}% measured",
                    )
                )

    # ============================ OPERATIONAL CONTEXT (optional) ============================
    not_verified = []
    required, available = (
        to_decimal(ctx.get("required_capacity_tonnes")),
        to_decimal(ctx.get("available_capacity_tonnes")),
    )
    note = ""
    if required is None and q is not None and available is not None:
        required, note = q, " (requirement taken from the scenario quantity)"
    if required is None or available is None:
        pass  # Disclosed below as an unverified, ideal assumption.
    elif available < required:
        L.add(
            make_finding(
                "PROCESSING_CAPACITY",
                "CAPACITY",
                FAIL,
                "Available capacity is below the requirement" + note + ".",
                fmt(available, 0),
                fmt(required, 0),
            ),
            "Confirm additional capacity or revise the throughput assumption.",
        )
    elif required > 0 and (available - required) / required < CAPACITY_HEADROOM_WARN:
        L.add(
            make_finding(
                "PROCESSING_CAPACITY",
                "CAPACITY",
                WARN,
                "Capacity meets the requirement with very little headroom" + note + ".",
                fmt(available, 0),
                fmt(required, 0),
            ),
            "Check that capacity is firm and not shared.",
        )
    else:
        L.add(
            make_finding(
                "PROCESSING_CAPACITY",
                "CAPACITY",
                PASS,
                "Available capacity meets the requirement" + note + ".",
                fmt(available, 0),
                fmt(required, 0),
            )
        )

    infra = ctx.get("infrastructure_status")
    if infra == "AVAILABLE":
        L.add(
            make_finding(
                "INFRASTRUCTURE",
                "INFRASTRUCTURE",
                PASS,
                "Infrastructure is reported as available.",
            )
        )
    elif infra == "LIMITED":
        L.add(
            make_finding(
                "INFRASTRUCTURE",
                "INFRASTRUCTURE",
                WARN,
                "Infrastructure is reported as limited. In Zambia, power supply is the usual constraint.",
            ),
            "Assess infrastructure and power limits on cost, throughput and schedule.",
        )
    elif infra == "UNAVAILABLE":
        L.add(
            make_finding(
                "INFRASTRUCTURE",
                "INFRASTRUCTURE",
                FAIL,
                "Required infrastructure is reported as unavailable.",
            ),
            "Secure the infrastructure or revise the scenario.",
        )

    reg = ctx.get("regulatory_status")
    if reg in ("CONFIRMED", "NOT_APPLICABLE"):
        L.add(
            make_finding(
                "REGULATORY_STATUS",
                "REGULATORY",
                PASS,
                f"Regulatory status was supplied as {reg}.",
            )
        )
    elif reg == "NOT_CONFIRMED":
        L.add(
            make_finding(
                "REGULATORY_STATUS",
                "REGULATORY",
                WARN,
                "Mining or processing rights, or environmental approval, are not confirmed (now overseen by the Minerals Regulation Commission).",
            ),
            "Confirm the licence, environmental approval and any processing, trading or export rights.",
        )

    ev = ctx.get("operation_specific_technical_evidence")
    if ev is True:
        L.add(
            make_finding(
                "TECHNICAL_EVIDENCE",
                "EVIDENCE",
                PASS,
                "Operation-specific technical evidence is reported as available.",
            )
        )
    elif ev is False:
        L.add(
            make_finding(
                "TECHNICAL_EVIDENCE",
                "EVIDENCE",
                WARN,
                "Operation-specific technical evidence is not confirmed.",
            ),
            "Validate grade, recovery and processing assumptions against operation-specific evidence.",
        )

    cc = ctx.get("cost_data_complete")
    if cc is True:
        L.add(
            make_finding(
                "COST_COMPLETENESS",
                "EVIDENCE",
                PASS,
                "Cost data is reported as complete.",
            )
        )
    elif cc is False:
        L.add(
            make_finding(
                "COST_COMPLETENESS",
                "EVIDENCE",
                WARN,
                "Cost data is incomplete, so value may be overstated.",
            ),
            "Complete relevant costs before relying on the result.",
        )

    # Disclose every operational input that was not supplied: it is assumed ideal, never verified.
    for code, category, label, absent in (
        (
            "PROCESSING_CAPACITY",
            "CAPACITY",
            "processing capacity",
            required is None or available is None,
        ),
        (
            "INFRASTRUCTURE",
            "INFRASTRUCTURE",
            "infrastructure availability",
            infra not in ("AVAILABLE", "LIMITED", "UNAVAILABLE"),
        ),
        (
            "REGULATORY_STATUS",
            "REGULATORY",
            "regulatory status",
            reg not in ("CONFIRMED", "NOT_APPLICABLE", "NOT_CONFIRMED"),
        ),
        (
            "TECHNICAL_EVIDENCE",
            "EVIDENCE",
            "operation-specific technical evidence",
            ev is None,
        ),
        ("COST_COMPLETENESS", "EVIDENCE", "cost data completeness", cc is None),
    ):
        if absent:
            not_verified.append(label)
            L.add(
                make_finding(
                    code,
                    category,
                    NA,
                    f"The {label} was not provided and is assumed ideal, not verified.",
                )
            )

    F = L.findings
    failed = any(f["outcome"] == FAIL for f in F)
    warned = any(f["outcome"] == WARN for f in F)
    core_ok = (
        L.assessed("GRADE_VS_BENCHMARK")
        and L.assessed("INCREMENTAL_VALUE")
        and (
            stage_kind in (None, "REFINING")
            or L.assessed("RECOVERY_VS_BENCHMARK", "RECOVERY_VS_SITE_RANGE")
        )
    )
    area = {}
    for f in F:
        area[f["category"]] = max(
            area.get(f["category"], PASS), f["outcome"], key=_RANK.get
        )

    if failed:
        outcome, rec = "NOT_VIABLE", "REVISE_SCENARIO"
    elif not core_ok:
        outcome, rec = "INSUFFICIENT_INFORMATION", "REVIEW_REQUIRED"
    elif warned:
        outcome, rec = "CONDITIONALLY_VIABLE", "PROCEED_AFTER_VALIDATION"
    else:
        outcome = "VIABLE"
        rec = "PROCEED_AFTER_VALIDATION" if not_verified else "PROCEED"

    gap = fmt(abs(delta), 0) if delta is not None else ""
    pct = (
        (delta / base * 100)
        if (delta is not None and base is not None and base > 0)
        else None
    )
    tax = to_decimal(bm["corporate_income_tax"])
    reliability = (
        "LOW"
        if failed or not core_ok
        else ("MEDIUM" if warned else "MEDIUM" if not_verified else "HIGH")
    )

    against, actions = [], []
    for f in [x for x in F if x["outcome"] == FAIL] + [
        x for x in F if x["outcome"] == WARN
    ]:
        text = _CON.get(f["rule_code"])
        if text:
            against.append(_fill(text[0], f, gap))
            if not (
                f["rule_code"] == "INCREMENTAL_VALUE"
                and delta is not None
                and delta < 0
            ):
                actions.append(_fill(text[1], f, gap))
        else:
            against.append(f["message"])
    pros = [f for f in F if f["outcome"] == PASS and f["rule_code"] in _PRO]
    pros.sort(
        key=lambda f: (
            _PRO_PRIORITY.index(f["rule_code"])
            if f["rule_code"] in _PRO_PRIORITY
            else 99
        )
    )
    reasons_for = [_fill(_PRO[f["rule_code"]], f, gap) for f in pros]

    after_roy = after_tax = None
    if delta is None:
        gain_text = "The gain or loss cannot be calculated because the scenario or baseline value is missing."
        direction = "UNKNOWN"
    elif delta > 0:
        direction = "GAIN"
        gain_text = (
            f"On paper the scenario gains about ${fmt(delta, 0)}"
            + (f" (+{pct:,.1f}%)" if pct is not None else "")
            + " over the baseline."
        )
        if roy is not None:
            after_roy = delta * (ONE - roy)
            after_tax = after_roy * (ONE - tax)
            gain_text += (
                f" After Zambian mineral royalty (about {roy * 100:.1f}%) and {tax * 100:.0f}% income tax, roughly "
                f"${fmt(after_tax, 0)} would remain, before operating costs."
            )
        if failed:
            gain_text += " However, one or more checks failed (see below), so you should not count on this gain."
        elif reliability == "LOW":
            gain_text += " However, core inputs could not be assessed, so you should not count on this gain."
        elif reliability == "MEDIUM":
            gain_text += " Treat it as an upper estimate until the flagged assumptions are validated."
        else:
            gain_text += " The assumptions behind it are realistic for Zambia."
    elif delta < 0:
        direction = "LOSS"
        gain_text = (
            f"The scenario would lose about ${gap}"
            + (f" ({pct:,.1f}%)" if pct is not None else "")
            + " compared with the baseline, so you would be worse off choosing it."
        )
    else:
        direction = "NO_CHANGE"
        gain_text = (
            "The scenario is worth the same as the baseline, so there is no gain."
        )

    if outcome == "NOT_VIABLE":
        headline = "Not recommended as it stands."
        first_rec = (
            "Do not choose this scenario because it is worth less than the baseline."
            if direction == "LOSS"
            else "Verify the failed checks before relying on this scenario."
        )
    elif outcome == "INSUFFICIENT_INFORMATION":
        headline = "Not enough information to assess this scenario."
        first_rec = "Provide the missing core inputs (stage, grade, recovery or baseline value) and reassess."
    elif outcome == "CONDITIONALLY_VIABLE":
        headline = "Potentially viable, subject to validation."
        first_rec = "Validate the flagged assumptions before proceeding."
    else:
        headline = "The scenario passes the configured checks."
        first_rec = (
            "Confirm these assumptions before proceeding: "
            + ", ".join(not_verified)
            + "."
            if not_verified
            else "Proceed, subject to normal operational review."
        )

    if delta is None:
        summary = f"{headline} Scenario and baseline values are needed to assess the financial impact."
    elif pct is not None:
        summary = f"{headline} Projected value change is {pct:+,.1f}% versus baseline."
    else:
        summary = (
            f"{headline} Projected value change is ${fmt(delta, 0)} versus baseline."
        )

    blockers = [f["message"] for f in F if f["outcome"] == FAIL]
    if blockers:
        summary += " " + blockers[0]
    elif warned:
        summary += " Validate the warnings before relying on the result."

    if not_verified:
        summary += " Not provided and assumed ideal: " + ", ".join(not_verified) + "."
    if outcome == "VIABLE":
        summary += " This assessment is not a guarantee of commercial success."
    recommendations = list(dict.fromkeys([first_rec] + actions))

    return {
        "assessment_outcome": outcome,
        "recommendation": rec,
        "assessment_summary": summary,
        "findings": F,
        "recommendations": recommendations,
        "reasons_for": reasons_for,
        "reasons_against": against,
        "financial_view": {
            "direction": direction,
            "value_difference": str(delta) if delta is not None else None,
            "percentage_difference": f"{pct:.1f}" if pct is not None else None,
            "after_royalty": fmt(after_roy, 0),
            "after_royalty_and_tax": fmt(after_tax, 0),
            "reliability": reliability,
            "gain_text": gain_text,
            "note": "Gain figures are before operating costs.",
        },
        "has_hard_blocker": failed,
        "area_summary": area,
        "not_verified": not_verified,
        "coverage": {
            "rules_run": len(F),
            "rules_assessed": sum(1 for f in F if f["outcome"] != NA),
            "benchmark_as_of": bm["meta"]["as_of"],
        },
    }
