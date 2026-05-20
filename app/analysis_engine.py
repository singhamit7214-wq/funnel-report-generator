"""Analysis engine: processes raw candidate-level data into funnel report metrics.

Accepts the Excel/CSV format from the weekly tracker (Base Sheet) with columns like:
  Skill Group, Final Status, Channel Mix, OS Incline Date, Offer Accept Date, etc.
and auto-computes all aggregations, conversions, and monthly breakdowns.
"""

import logging
from collections import defaultdict
from io import BytesIO
from pathlib import Path
from typing import Optional, Union

import pandas as pd

from app.models import (
    BusinessUpdate,
    CTCInsight,
    FunnelReport,
    MonthlyDelivery,
    SkillGroup,
)

logger = logging.getLogger(__name__)


# ── Status mapping: raw "Final Status" values → stage buckets ──────────

STATUS_MAP = {
    # Recruiter RR
    "awaiting hm rr": ("rr", "awaiting"),
    "awaiting recruiter rr": ("rr", "awaiting"),
    "scheduled rps": ("rr", "awaiting"),
    "awaiting rps": ("rr", "awaiting"),
    "rejected at recruiter rr": ("rr", "reject"),
    "rejected at hm rr": ("rr", "reject"),
    "rejected at rps": ("rr", "reject"),
    # Online Assessment
    "awaiting oa": ("oa", "scheduled"),
    "scheduled oa": ("oa", "scheduled"),
    "rejected at oa": ("oa", "reject"),
    # BPS
    "awaiting bps": ("bps", "awaiting"),
    "scheduled bps": ("bps", "scheduled"),
    "rejected at bps": ("bps", "reject"),
    "position filled - sch bps stage": ("bps", "reject"),
    # Onsite
    "awaiting os": ("os", "awaiting"),
    "scheduled os": ("os", "scheduled"),
    "awaiting debreif": ("os", "awaiting"),
    "scheduled debreif": ("os", "scheduled"),
    "os incline": ("os", "incline"),
    "rejected at os": ("os", "reject"),
    "offer cancelled": ("os", "incline"),
    # Offer
    "offer-in-process": ("offer", "made"),
    "offer made": ("offer", "made"),
    "offer accept": ("offer", "accept"),
    "offer decline": ("offer", "renege"),
    "offer renege": ("offer", "renege"),
    "onboard": ("offer", "onboard"),
    # Terminal / not counted in active pipeline
    "candidature withdrawn": ("withdrawn", ""),
    "dispositioned as req. filled": ("withdrawn", ""),
}

MONTH_ORDER = [
    "January", "February", "March", "April", "May", "June",
    "July", "August", "September", "October", "November", "December",
]


def _read_file(
    content: bytes = None, filename: str = "", file_path: Union[str, Path] = None,
    sheet_name=0,
) -> pd.DataFrame:
    """Read CSV or Excel into a DataFrame."""
    if content:
        ext = Path(filename).suffix.lower() if filename else ".csv"
        buf = BytesIO(content)
        if ext in (".xlsx", ".xls"):
            return pd.read_excel(buf, sheet_name=sheet_name)
        return pd.read_csv(buf)
    if file_path:
        p = Path(file_path)
        if p.suffix.lower() in (".xlsx", ".xls"):
            return pd.read_excel(p, sheet_name=sheet_name)
        return pd.read_csv(p)
    raise ValueError("Provide either content bytes or file_path")


def _safe_int(val, default: int = 0) -> int:
    try:
        if pd.isna(val):
            return default
        return int(float(val))
    except (ValueError, TypeError):
        return default


def _find_col(df: pd.DataFrame, candidates: list[str]) -> Optional[str]:
    """Find the first matching column (case-insensitive, stripped)."""
    cols_lower = {c.strip().lower(): c for c in df.columns}
    for name in candidates:
        if name.strip().lower() in cols_lower:
            return cols_lower[name.strip().lower()]
    return None


# ── Detect which sheet has the base data ───────────────────────────────

def _find_base_sheet(content: bytes, filename: str) -> tuple[pd.DataFrame, Optional[str]]:
    """Try to find the sheet with raw candidate rows (Base Sheet)."""
    ext = Path(filename).suffix.lower() if filename else ".csv"
    if ext not in (".xlsx", ".xls"):
        df = pd.read_csv(BytesIO(content))
        return df, None

    xls = pd.ExcelFile(BytesIO(content))
    sheet_names = xls.sheet_names

    # Prefer sheets named "Base Sheet", "Base", "Raw", "Data"
    for preferred in ["Base Sheet", "base sheet", "Base", "Raw Data", "Raw", "Data"]:
        for sn in sheet_names:
            if sn.strip().lower() == preferred.lower():
                return pd.read_excel(xls, sheet_name=sn), sn

    # Fallback: pick the sheet with the most rows (likely the base data)
    best_sheet = None
    best_rows = 0
    for sn in sheet_names:
        df = pd.read_excel(xls, sheet_name=sn, nrows=5)
        full = pd.read_excel(xls, sheet_name=sn)
        if len(full) > best_rows:
            best_rows = len(full)
            best_sheet = sn

    df = pd.read_excel(xls, sheet_name=best_sheet)
    return df, best_sheet


def _find_summary_sheet(content: bytes, filename: str) -> Optional[pd.DataFrame]:
    """Try to find the Summary sheet for demand counts."""
    ext = Path(filename).suffix.lower() if filename else ".csv"
    if ext not in (".xlsx", ".xls"):
        return None
    xls = pd.ExcelFile(BytesIO(content))
    for sn in xls.sheet_names:
        if "summary" in sn.strip().lower():
            return pd.read_excel(xls, sheet_name=sn)
    return None


def _find_open_demands_sheet(content: bytes, filename: str) -> Optional[pd.DataFrame]:
    """Try to find the Open Demands sheet for requisition counts."""
    ext = Path(filename).suffix.lower() if filename else ".csv"
    if ext not in (".xlsx", ".xls"):
        return None
    xls = pd.ExcelFile(BytesIO(content))
    for sn in xls.sheet_names:
        if "open demand" in sn.strip().lower() or "demand" in sn.strip().lower():
            return pd.read_excel(xls, sheet_name=sn)
    return None


# ── Core: parse raw candidate data into SkillGroup aggregations ────────

def parse_raw_candidates(
    content: bytes = None, filename: str = "", file_path: str = None,
) -> tuple[list[SkillGroup], list[MonthlyDelivery], dict]:
    """
    Parse raw candidate-level data (Base Sheet) and compute:
    1. SkillGroup aggregations (pipeline slate)
    2. MonthlyDelivery glidepath (from OS Incline Date / Offer Accept Date)
    3. Source mix stats

    Returns (skill_groups, monthly_delivery, source_mix_dict)
    """
    if content:
        df, sheet = _find_base_sheet(content, filename)
    else:
        df = _read_file(file_path=file_path)
        sheet = None

    df.columns = [str(c).strip() for c in df.columns]
    logger.info(f"Loaded {len(df)} rows from sheet '{sheet}', columns: {list(df.columns)[:15]}...")

    # ── Identify key columns ──
    sg_col = _find_col(df, ["Skill Group", "skill_group"])
    status_col = _find_col(df, ["Final Status", "final_status", "Status"])
    channel_col = _find_col(df, ["Channel Mix", "channel_mix", "Source"])
    os_incline_date_col = _find_col(df, [
        "OS Incline Date", "os_incline_date", "Incline Date",
    ])
    offer_accept_date_col = _find_col(df, [
        "Offer Accept Date", "offer_accept_date",
    ])

    if not sg_col:
        raise ValueError(
            f"Could not find 'Skill Group' column in the data. "
            f"Available columns: {list(df.columns)}"
        )
    if not status_col:
        raise ValueError(
            f"Could not find 'Final Status' column. "
            f"Available columns: {list(df.columns)}"
        )

    # ── Clean data ──
    df = df.dropna(subset=[sg_col], how="all")
    df = df[df[sg_col].astype(str).str.strip() != ""]
    df = df[~df[sg_col].astype(str).str.lower().isin(["nan", "grand total", "total"])]
    df[status_col] = df[status_col].astype(str).str.strip()
    df[sg_col] = df[sg_col].astype(str).str.strip()

    # ── Aggregate by skill group ──
    sg_data: dict[str, dict] = defaultdict(lambda: {
        "demands": 0, "candidates": 0,
        "rr_awaiting": 0, "rr_incline": 0, "rr_reject": 0,
        "oa_scheduled": 0, "oa_incline": 0, "oa_reject": 0,
        "bps_awaiting": 0, "bps_scheduled": 0, "bps_incline": 0, "bps_reject": 0,
        "os_awaiting": 0, "os_scheduled": 0, "os_incline": 0, "os_reject": 0,
        "offer_made": 0, "offer_accept": 0, "offer_renege": 0, "onboard": 0,
    })

    for _, row in df.iterrows():
        sg = str(row[sg_col]).strip()
        status_raw = str(row[status_col]).strip().lower()
        if not sg or sg.lower() == "nan":
            continue

        d = sg_data[sg]
        d["candidates"] += 1

        mapping = STATUS_MAP.get(status_raw)
        if not mapping:
            logger.debug(f"Unknown status '{status_raw}' for {sg}")
            continue

        stage, outcome = mapping

        if stage == "rr":
            if outcome == "awaiting":
                d["rr_awaiting"] += 1
            elif outcome == "reject":
                d["rr_reject"] += 1
            else:
                d["rr_incline"] += 1
        elif stage == "oa":
            if outcome == "scheduled":
                d["oa_scheduled"] += 1
            elif outcome == "reject":
                d["oa_reject"] += 1
            else:
                d["oa_incline"] += 1
        elif stage == "bps":
            if outcome == "awaiting":
                d["bps_awaiting"] += 1
            elif outcome == "scheduled":
                d["bps_scheduled"] += 1
            elif outcome == "reject":
                d["bps_reject"] += 1
            else:
                d["bps_incline"] += 1
        elif stage == "os":
            if outcome == "awaiting":
                d["os_awaiting"] += 1
            elif outcome == "scheduled":
                d["os_scheduled"] += 1
            elif outcome == "incline":
                d["os_incline"] += 1
            elif outcome == "reject":
                d["os_reject"] += 1
        elif stage == "offer":
            if outcome == "made":
                d["offer_made"] += 1
            elif outcome == "accept":
                d["offer_accept"] += 1
            elif outcome == "renege":
                d["offer_renege"] += 1
            elif outcome == "onboard":
                d["onboard"] += 1

        # NOTE: No cascade counting. Each candidate is counted only at
        # their current/final status. The Summary sheet in the Excel
        # already tracks completed stages separately via pivot tables.

    # ── Count demands from Open Demands sheet or unique Req IDs ──
    req_col = _find_col(df, ["Req ID", "req_id", "Requisition ID", "Job ID"])
    if req_col:
        for sg, rows_in_sg in df.groupby(sg_col):
            sg_str = str(sg).strip()
            if sg_str in sg_data:
                unique_reqs = rows_in_sg[req_col].dropna().nunique()
                sg_data[sg_str]["demands"] = unique_reqs

    # ── Build SkillGroup objects ──
    skill_groups = []
    for sg_name, d in sg_data.items():
        skill_groups.append(SkillGroup(
            skill_group=sg_name,
            demands=d["demands"],
            rr_awaiting=d["rr_awaiting"],
            rr_incline=d["rr_incline"],
            rr_reject=d["rr_reject"],
            oa_scheduled=d["oa_scheduled"],
            oa_incline=d["oa_incline"],
            oa_reject=d["oa_reject"],
            bps_awaiting=d["bps_awaiting"],
            bps_scheduled=d["bps_scheduled"],
            bps_incline=d["bps_incline"],
            bps_reject=d["bps_reject"],
            os_awaiting=d["os_awaiting"],
            os_scheduled=d["os_scheduled"],
            os_incline=d["os_incline"],
            os_reject=d["os_reject"],
            offer_made=d["offer_made"],
            offer_accept=d["offer_accept"],
            offer_renege=d["offer_renege"],
            onboard=d["onboard"],
        ))

    # ── Monthly delivery from date columns ──
    monthly = _compute_monthly_delivery(df, os_incline_date_col, offer_accept_date_col)

    # ── Source mix ──
    source_mix = _compute_source_mix(df, channel_col)

    logger.info(f"Parsed {len(skill_groups)} skill groups from {len(df)} candidate rows")
    return skill_groups, monthly, source_mix


def _compute_monthly_delivery(
    df: pd.DataFrame,
    os_incline_date_col: Optional[str],
    offer_accept_date_col: Optional[str],
) -> list[MonthlyDelivery]:
    """Compute month-on-month OS inclines and offer accepts from date columns."""
    if not os_incline_date_col and not offer_accept_date_col:
        return []

    monthly_data: dict[str, dict] = {}

    # OS Inclines by month
    if os_incline_date_col:
        dates = pd.to_datetime(df[os_incline_date_col], errors="coerce")
        for dt in dates.dropna():
            month_name = dt.strftime("%B")
            if month_name not in monthly_data:
                monthly_data[month_name] = {"os_inclines": 0, "offer_accepts": 0}
            monthly_data[month_name]["os_inclines"] += 1

    # Offer Accepts by month
    if offer_accept_date_col:
        dates = pd.to_datetime(df[offer_accept_date_col], errors="coerce")
        for dt in dates.dropna():
            month_name = dt.strftime("%B")
            if month_name not in monthly_data:
                monthly_data[month_name] = {"os_inclines": 0, "offer_accepts": 0}
            monthly_data[month_name]["offer_accepts"] += 1

    # Build sorted list
    result = []
    for month_name in MONTH_ORDER:
        if month_name in monthly_data:
            d = monthly_data[month_name]
            result.append(MonthlyDelivery(
                month=month_name,
                os_inclines_actual=d["os_inclines"],
                offer_accepts_actual=d["offer_accepts"],
            ))

    return result


def _compute_source_mix(df: pd.DataFrame, channel_col: Optional[str]) -> dict:
    """Compute source mix percentages."""
    if not channel_col:
        return {}

    total = len(df)
    if total == 0:
        return {}

    counts = df[channel_col].astype(str).str.strip().str.lower().value_counts()
    hire_count = sum(v for k, v in counts.items() if "hire" in k)
    linkedin_count = sum(v for k, v in counts.items() if "linkedin" in k)
    direct_count = sum(v for k, v in counts.items() if "direct" in k)

    return {
        "total_sourced": total,
        "hire_pct": round(hire_count / total * 100, 1) if total else 0,
        "linkedin_pct": round(linkedin_count / total * 100, 1) if total else 0,
        "direct_pct": round(direct_count / total * 100, 1) if total else 0,
        "hire_count": hire_count,
        "linkedin_count": linkedin_count,
        "direct_count": direct_count,
    }


# ── Metrics and report building (unchanged) ────────────────────────────

def compute_funnel_metrics(groups: list[SkillGroup]) -> dict:
    """Compute aggregate conversion metrics from skill group data."""
    totals = {
        "demands": 0,
        "rr_awaiting": 0, "rr_incline": 0, "rr_reject": 0,
        "oa_scheduled": 0, "oa_incline": 0, "oa_reject": 0,
        "bps_awaiting": 0, "bps_scheduled": 0, "bps_incline": 0, "bps_reject": 0,
        "os_awaiting": 0, "os_scheduled": 0, "os_incline": 0, "os_reject": 0,
        "offer_made": 0, "offer_accept": 0, "offer_renege": 0, "onboard": 0,
    }
    for g in groups:
        for key in totals:
            totals[key] += getattr(g, key, 0)

    # OA completed = candidates who got OA result (passed to BPS or rejected at OA)
    # Since no cascade: OA incline = those explicitly at OA incline stage
    # But candidates at BPS/OS/Offer all passed OA, so:
    oa_passed = (totals["bps_awaiting"] + totals["bps_scheduled"] + totals["bps_incline"]
                 + totals["bps_reject"] + totals["os_awaiting"] + totals["os_scheduled"]
                 + totals["os_incline"] + totals["os_reject"]
                 + totals["offer_made"] + totals["offer_accept"] + totals["offer_renege"]
                 + totals["onboard"] + totals["oa_incline"])
    oa_completed = oa_passed + totals["oa_reject"]

    # BPS completed = candidates who got BPS result
    bps_passed = (totals["os_awaiting"] + totals["os_scheduled"]
                  + totals["os_incline"] + totals["os_reject"]
                  + totals["offer_made"] + totals["offer_accept"] + totals["offer_renege"]
                  + totals["onboard"] + totals["bps_incline"])
    bps_completed = bps_passed + totals["bps_reject"]

    # OS completed = candidates who got OS result
    os_passed = (totals["os_incline"] + totals["offer_made"] + totals["offer_accept"]
                 + totals["offer_renege"] + totals["onboard"])
    os_completed = os_passed + totals["os_reject"]

    # Offers released
    offers_released = totals["offer_made"] + totals["offer_accept"] + totals["offer_renege"]

    return {
        "totals": totals,
        "oa_completed": oa_completed,
        "bps_completed": bps_completed,
        "os_completed": os_completed,
        "offers_released": offers_released,
        "oa_pass_pct": round(oa_passed / oa_completed * 100, 1) if oa_completed else None,
        "oa_reject_pct": round(totals["oa_reject"] / oa_completed * 100, 1) if oa_completed else None,
        "bps_to_os_pct": round(bps_passed / bps_completed * 100, 1) if bps_completed else None,
        "os_to_incline_pct": round(os_passed / os_completed * 100, 1) if os_completed else None,
        "offer_accept_pct": round(totals["offer_accept"] / offers_released * 100, 1) if offers_released else None,
        "offer_renege_pct": round(totals["offer_renege"] / offers_released * 100, 1) if offers_released else None,
    }


def derive_business_updates(groups: list[SkillGroup]) -> list[BusinessUpdate]:
    """Derive business-wise updates by grouping skill groups by business."""
    biz_map: dict[str, list[SkillGroup]] = {}
    for g in groups:
        parts = g.skill_group.split(",")
        biz_raw = parts[0].strip() if parts else g.skill_group
        biz_name = biz_raw.replace("NA-", "").strip()
        biz_map.setdefault(biz_name, []).append(g)

    updates = []
    for biz_name, biz_groups in biz_map.items():
        total_os_incline = sum(g.os_incline for g in biz_groups)
        total_os_reject = sum(g.os_reject for g in biz_groups)
        # OS passed includes os_incline + offer candidates (they passed OS)
        total_offer = sum(g.offer_made + g.offer_accept + g.offer_renege + g.onboard for g in biz_groups)
        os_passed = total_os_incline + total_offer
        os_completed = os_passed + total_os_reject
        conv_pct = round(os_passed / os_completed * 100, 1) if os_completed else None

        updates.append(BusinessUpdate(
            business_name=biz_name,
            os_inclines=os_passed,
            offer_accepts=sum(g.offer_accept for g in biz_groups),
            offer_declines=sum(g.offer_renege for g in biz_groups),
            offer_stage=sum(g.offer_made for g in biz_groups),
            os_completed=os_completed,
            incline_conversion_pct=conv_pct,
            pipeline_onsite=sum(g.os_awaiting + g.os_scheduled for g in biz_groups),
            pipeline_bps=sum(g.bps_awaiting + g.bps_scheduled for g in biz_groups),
            pipeline_assessment=sum(g.oa_scheduled for g in biz_groups),
            pipeline_hm_review=sum(g.rr_awaiting for g in biz_groups),
        ))

    return updates


def build_funnel_report(
    skill_groups: list[SkillGroup],
    monthly_delivery: list[MonthlyDelivery] = None,
    ctc_insights: list[CTCInsight] = None,
    support_items: list[str] = None,
    source_hire_pct: float = None,
    source_linkedin_pct: float = None,
    total_sourced: int = 0,
    report_year: int = 2026,
) -> FunnelReport:
    """Build the complete funnel report from parsed data."""
    metrics = compute_funnel_metrics(skill_groups)
    t = metrics["totals"]
    biz_updates = derive_business_updates(skill_groups)

    active_pipeline = (
        t["offer_made"]
        + t["os_awaiting"] + t["os_scheduled"]
        + t["bps_awaiting"] + t["bps_scheduled"]
        + t["oa_scheduled"]
        + t["rr_awaiting"]
    )

    return FunnelReport(
        report_year=report_year,
        ytd_os_inclines=metrics["os_completed"] - (t["os_reject"]),  # OS passed = inclines
        ytd_offer_accepts=t["offer_accept"],
        ytd_offer_stage=t["offer_made"],
        ytd_offer_declines=t["offer_renege"],
        total_requisitions=t["demands"],
        total_active_pipeline=active_pipeline,
        bps_to_os_pct=metrics["bps_to_os_pct"],
        os_to_incline_pct=metrics["os_to_incline_pct"],
        offer_acceptance_pct=metrics["offer_accept_pct"],
        skill_groups=skill_groups,
        monthly_delivery=monthly_delivery or [],
        business_updates=biz_updates,
        ctc_insights=ctc_insights or [],
        source_hire_pct=source_hire_pct,
        source_linkedin_pct=source_linkedin_pct,
        total_sourced=total_sourced,
        support_items=support_items or [],
    )
