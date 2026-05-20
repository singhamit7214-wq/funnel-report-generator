"""Weekly Funnel Report Generator — Streamlit App."""

import streamlit as st
import pandas as pd
from io import BytesIO

from app.analysis_engine import (
    parse_raw_candidates,
    build_funnel_report,
    compute_funnel_metrics,
)
from app.docx_generator import generate_docx

# ── Page config ──
st.set_page_config(
    page_title="Weekly Funnel Report Generator",
    page_icon="📊",
    layout="wide",
)

st.title("📊 Weekly Funnel Report Generator")
st.markdown("Upload your weekly tracker Excel and the tool will auto-generate the full funnel report.")
st.divider()

# ── Sidebar: Upload & Settings ──
with st.sidebar:
    st.header("⬆️ Upload & Settings")

    uploaded_file = st.file_uploader(
        "Upload Weekly Tracker (.xlsx or .csv)",
        type=["xlsx", "xls", "csv"],
        help="Upload the Excel file with the Base Sheet containing candidate-level data.",
    )

    st.markdown("**Expected columns:**")
    st.markdown("""
    - `Skill Group` — e.g. "NA-AWS, FA-II, L5"
    - `Final Status` — e.g. "Offer Accept", "Rejected at BPS"
    - `Channel Mix` *(optional)* — "LinkedIn", "Hire"
    - `OS Incline Date` *(optional)* — for monthly glidepath
    - `Offer Accept Date` *(optional)* — for monthly glidepath
    - `Req ID` *(optional)* — for demand count
    """)

    st.divider()
    report_year = st.number_input("Report Year", value=2026, min_value=2020, max_value=2030)

    st.divider()
    support_items = st.text_area(
        "Support Required (one per line)",
        placeholder="e.g. DAS: Req ID 3100130 pending HM review...",
    )

# ── Main content ──
if uploaded_file is None:
    st.info("👈 Upload your weekly tracker file in the sidebar to get started.")
    st.stop()


# ── Process the file ──
try:
    content = uploaded_file.read()
    skill_groups, monthly, source_mix = parse_raw_candidates(
        content=content, filename=uploaded_file.name,
    )

    support = [s.strip() for s in support_items.strip().split("\n") if s.strip()] if support_items else []

    report = build_funnel_report(
        skill_groups=skill_groups,
        monthly_delivery=monthly,
        support_items=support,
        source_hire_pct=source_mix.get("hire_pct"),
        source_linkedin_pct=source_mix.get("linkedin_pct"),
        total_sourced=source_mix.get("total_sourced", 0),
        report_year=report_year,
    )

    metrics = compute_funnel_metrics(skill_groups)
    t = metrics["totals"]

except Exception as e:
    st.error(f"❌ Error processing file: {str(e)}")
    st.stop()

# ── Success message ──
st.success(f"✅ Processed {sum(1 for _ in skill_groups)} skill groups from **{uploaded_file.name}**")

# ── Download & Email ──
docx_bytes = generate_docx(report)

col_dl1, col_dl2 = st.columns([1, 1])
with col_dl1:
    st.download_button(
        label="📥 Download Word Report",
        data=docx_bytes,
        file_name="Weekly_Funnel_Report.docx",
        mime="application/vnd.openxmlformats-officedocument.wordprocessingml.document",
    )

with col_dl2:
    with st.popover("📧 Send via Email"):
        st.markdown("**Send report to recipients**")
        to_emails = st.text_input("To (comma-separated emails)", placeholder="leader1@company.com, leader2@company.com")
        cc_emails = st.text_input("CC (optional)", placeholder="manager@company.com")
        email_subject = st.text_input("Subject", value=f"Weekly Funnel Report - FGBS {report_year}")
        smtp_host = st.text_input("SMTP Host", value=st.session_state.get("smtp_host", "smtp.office365.com"))
        smtp_port = st.number_input("SMTP Port", value=587, min_value=1, max_value=65535)
        smtp_user = st.text_input("SMTP Username (your email)", value=st.session_state.get("smtp_user", ""))
        smtp_pass = st.text_input("SMTP Password / App Password", type="password")

        if st.button("Send Email", type="primary"):
            if not to_emails.strip():
                st.error("Enter at least one recipient email.")
            elif not smtp_user or not smtp_pass:
                st.error("Enter SMTP credentials.")
            else:
                # Save for reuse in session
                st.session_state["smtp_host"] = smtp_host
                st.session_state["smtp_user"] = smtp_user
                try:
                    from app.email_utils import send_report_email
                    result = send_report_email(
                        to_emails=[e.strip() for e in to_emails.split(",") if e.strip()],
                        cc_emails=[e.strip() for e in cc_emails.split(",") if e.strip()] if cc_emails else [],
                        subject=email_subject,
                        docx_bytes=docx_bytes,
                        smtp_host=smtp_host,
                        smtp_port=smtp_port,
                        smtp_user=smtp_user,
                        smtp_pass=smtp_pass,
                        report=report,
                    )
                    if result["success"]:
                        st.success(f"✅ {result['message']}")
                    else:
                        st.error(f"❌ {result['message']}")
                except Exception as e:
                    st.error(f"❌ Failed: {str(e)}")

st.divider()

# ── Summary Cards ──
st.subheader("Highlight & Demand Updates")

col1, col2, col3, col4 = st.columns(4)
col1.metric("OS Inclines (YTD)", report.ytd_os_inclines)
col2.metric("Offer Accepts (YTD)", report.ytd_offer_accepts)
col3.metric("Active Requisitions", report.total_requisitions)
col4.metric("Active Pipeline", report.total_active_pipeline)

col5, col6, col7 = st.columns(3)
col5.metric("BPS → Onsite", f"{report.bps_to_os_pct:.1f}%" if report.bps_to_os_pct else "N/A")
col6.metric("OS → Incline", f"{report.os_to_incline_pct:.1f}%" if report.os_to_incline_pct else "N/A")
col7.metric("Offer Accept Rate", f"{report.offer_acceptance_pct:.1f}%" if report.offer_acceptance_pct else "N/A")

st.markdown(
    f"In **{report.report_year}**, we've delivered **{report.ytd_os_inclines}** OS inclines "
    f"across L4-L6 roles, leading to **{report.ytd_offer_accepts}** Offer Accepts, "
    f"**{report.ytd_offer_stage}** at Offer Stage and **{report.ytd_offer_declines}** Offer Declines."
)


# ── Business-wise Updates ──
st.divider()
st.subheader("Business-wise Updates")

for biz in report.business_updates:
    with st.expander(f"**{biz.business_name}**", expanded=True):
        bcol1, bcol2, bcol3, bcol4 = st.columns(4)
        bcol1.metric("OS Inclines", biz.os_inclines)
        bcol2.metric("Offer Accepts", biz.offer_accepts)
        bcol3.metric("Incline Conv %", f"{biz.incline_conversion_pct:.0f}%" if biz.incline_conversion_pct else "N/A")
        bcol4.metric("Active Pipeline",
                     biz.pipeline_onsite + biz.pipeline_bps + biz.pipeline_assessment + biz.pipeline_hm_review)

        details = f"GSS delivered **{biz.os_inclines}** OS inclines → **{biz.offer_accepts}** offer accepts"
        if biz.offer_stage:
            details += f" / {biz.offer_stage} at Offer Stage"
        if biz.offer_declines:
            details += f" / {biz.offer_declines} decline(s)"
        st.markdown(details)

        if biz.incline_conversion_pct is not None:
            pipeline_parts = []
            if biz.pipeline_onsite:
                pipeline_parts.append(f"{biz.pipeline_onsite} at Onsite")
            if biz.pipeline_bps:
                pipeline_parts.append(f"{biz.pipeline_bps} BPS")
            if biz.pipeline_assessment:
                pipeline_parts.append(f"{biz.pipeline_assessment} at Assessment")
            if biz.pipeline_hm_review:
                pipeline_parts.append(f"{biz.pipeline_hm_review} at HM Review")
            if pipeline_parts:
                st.markdown(f"Pipeline: {', '.join(pipeline_parts)}")

# ── Monthly Delivery Glidepath ──
if report.monthly_delivery:
    st.divider()
    st.subheader("YTD Month-on-Month Delivery Glidepath")

    monthly_df = pd.DataFrame([
        {
            "Month": m.month,
            "OS Inclines": m.os_inclines_actual,
            "Offer Accepts": m.offer_accepts_actual,
            "Target": m.offer_accept_target,
            "GAP": m.offer_accept_target - m.offer_accepts_actual,
        }
        for m in report.monthly_delivery
    ])
    st.dataframe(monthly_df, use_container_width=True, hide_index=True)


# ── Pipeline Slate Table ──
st.divider()
st.subheader("Active Pipeline — YTD Slate")

slate_data = []
for sg in report.skill_groups:
    slate_data.append({
        "Skill Group": sg.skill_group,
        "Demands": sg.demands,
        "RR Await": sg.rr_awaiting,
        "RR Incl": sg.rr_incline,
        "RR Rej": sg.rr_reject,
        "OA Sched": sg.oa_scheduled,
        "OA Incl": sg.oa_incline,
        "OA Rej": sg.oa_reject,
        "BPS Await": sg.bps_awaiting,
        "BPS Sched": sg.bps_scheduled,
        "BPS Incl": sg.bps_incline,
        "BPS Rej": sg.bps_reject,
        "OS Await": sg.os_awaiting,
        "OS Sched": sg.os_scheduled,
        "OS Incl": sg.os_incline,
        "OS Rej": sg.os_reject,
        "Offer Made": sg.offer_made,
        "Offer Accept": sg.offer_accept,
        "Offer Decline": sg.offer_renege,
        "Onboard": sg.onboard,
    })

# Add grand total row
slate_data.append({
    "Skill Group": "Grand Total",
    "Demands": t["demands"],
    "RR Await": t["rr_awaiting"],
    "RR Incl": t["rr_incline"],
    "RR Rej": t["rr_reject"],
    "OA Sched": t["oa_scheduled"],
    "OA Incl": t["oa_incline"],
    "OA Rej": t["oa_reject"],
    "BPS Await": t["bps_awaiting"],
    "BPS Sched": t["bps_scheduled"],
    "BPS Incl": t["bps_incline"],
    "BPS Rej": t["bps_reject"],
    "OS Await": t["os_awaiting"],
    "OS Sched": t["os_scheduled"],
    "OS Incl": t["os_incline"],
    "OS Rej": t["os_reject"],
    "Offer Made": t["offer_made"],
    "Offer Accept": t["offer_accept"],
    "Offer Decline": t["offer_renege"],
    "Onboard": t["onboard"],
})

slate_df = pd.DataFrame(slate_data)
st.dataframe(slate_df, use_container_width=True, hide_index=True)

# Conversion metrics
mcol1, mcol2, mcol3, mcol4 = st.columns(4)
mcol1.metric("OA Completed", metrics["oa_completed"])
mcol2.metric("BPS Completed", metrics["bps_completed"])
mcol3.metric("OS Completed", metrics["os_completed"])
mcol4.metric("Offers Released", metrics["offers_released"])

# ── Source Mix ──
if source_mix:
    st.divider()
    st.subheader("Source Mix")
    scol1, scol2, scol3 = st.columns(3)
    scol1.metric("Hire", f"{source_mix.get('hire_pct', 0):.1f}%")
    scol2.metric("LinkedIn", f"{source_mix.get('linkedin_pct', 0):.1f}%")
    scol3.metric("Direct Applicant", f"{source_mix.get('direct_pct', 0):.1f}%")
    st.caption(f"Total candidates sourced: {source_mix.get('total_sourced', 0)}")

# ── Support Required ──
if report.support_items:
    st.divider()
    st.subheader("Support Required")
    for item in report.support_items:
        st.markdown(f"- {item}")
