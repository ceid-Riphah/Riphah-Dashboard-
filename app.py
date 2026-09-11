"""
Riphah CEID – Career Survey Dashboard + CEID KPI Portal
------------------------------------------------------------------
Three tabs at the top:

1. CEID Portal — department -> vertical drill-down showing actual-vs-
   target KPI progress. Each faculty has its OWN Google Sheet (one tab
   per vertical) containing both the checkpoint targets and an
   "Actual (latest)" column coordinators update directly — no targets
   are hardcoded in this file.
2. CEO Overview — a Faculty x Vertical heat map (simplified KPI
   attainment %, not the full weighted CEO score).
3. Survey Dashboard — the original Career Aspirations & Pathways
   Survey (2025) analytics, unchanged.

Run locally:
    pip install -r requirements.txt
    streamlit run app.py
"""

import re
from datetime import date
from urllib.parse import quote

import pandas as pd
import plotly.express as px
import streamlit as st

st.set_page_config(page_title="Riphah CEID – Dashboard", page_icon="🎓", layout="wide")

_SHEET_ID_RE = re.compile(r"/spreadsheets/d/([a-zA-Z0-9-_]+)")


def _extract_sheet_id(link_or_id: str) -> str:
    match = _SHEET_ID_RE.search(link_or_id)
    return match.group(1) if match else link_or_id.strip()


def _sheet_csv_url(sheet_id: str, sheet_name: str = None, gid: str = "0") -> str:
    if sheet_name:
        return f"https://docs.google.com/spreadsheets/d/{sheet_id}/gviz/tq?tqx=out:csv&sheet={quote(sheet_name)}"
    return f"https://docs.google.com/spreadsheets/d/{sheet_id}/gviz/tq?tqx=out:csv&gid={gid}"


# ========================================================================
# SECTION 1 — SURVEY DASHBOARD DATA (unchanged)
# ========================================================================
SURVEY_SHEET_ID = "16eFMceIi7pgMUgxe_7Hn0ye94RuidGLtrrITNit1liE"
SURVEY_TAB_NAME = "Form_Responses"
SURVEY_CANDIDATE_URLS = [
    _sheet_csv_url(SURVEY_SHEET_ID, sheet_name=SURVEY_TAB_NAME),
    _sheet_csv_url(SURVEY_SHEET_ID, gid="0"),
    f"https://docs.google.com/spreadsheets/d/{SURVEY_SHEET_ID}/export?format=csv&gid=0",
]


@st.cache_data(ttl=600)
def load_survey_data(url: str) -> pd.DataFrame:
    d = pd.read_csv(url)
    d.columns = [c.strip() for c in d.columns]
    d = d.dropna(axis=1, how="all")
    key_col = "Which career path best describes your ambition?"
    if key_col in d.columns:
        d = d[d[key_col].notna()]
    return d


df = None
load_error = None
with st.spinner("Loading survey responses..."):
    for url in SURVEY_CANDIDATE_URLS:
        try:
            df = load_survey_data(url)
            break
        except Exception as e:
            load_error = e

if df is None:
    st.error(
        "Couldn't load the survey Google Sheet automatically. Make sure it's "
        "shared as 'Anyone with the link -> Viewer'.\n\n"
        f"Technical detail: {load_error}"
    )
    st.info("In the meantime, you can upload a CSV export manually below.")
    uploaded = st.file_uploader("Upload survey CSV", type=["csv"])
    if uploaded is not None:
        df = pd.read_csv(uploaded)
        df.columns = [c.strip() for c in df.columns]
        df = df.dropna(axis=1, how="all")
    else:
        df = pd.DataFrame()

CAREER_COL = "Which career path best describes your ambition?"
MOTIVATION_COL = "What motivates you most to choose this path?"
CONFIDENCE_COL = "How confident are you about achieving this goal?"
FACULTY_COL = "Please select your Faculty"
DEPT_COL = "Department"
PROGRAM_COL = "Degree Program"
SEMESTER_COL = "Semester"
GENDER_COL = "Your Gender"
BIZ_TYPE_COL = "What type of business or venture are you interested in starting?"
FREELANCE_SKILL_COL = "What freelancing skill are you most interested in learning?"
EDU_LEVEL_COL = "What level of higher education are you considering?"
INDUSTRY_COL = "What industry or field would you like to work in?"

st.sidebar.header("🔎 Survey Filters")


def multiselect_filter(label, column_name):
    if df.empty or column_name not in df.columns:
        return None
    options = sorted(df[column_name].dropna().unique().tolist())
    return st.sidebar.multiselect(label, options, default=[])


faculty_sel = multiselect_filter("Faculty", FACULTY_COL)
dept_sel = multiselect_filter("Department", DEPT_COL)
program_sel = multiselect_filter("Degree Program", PROGRAM_COL)
semester_sel = multiselect_filter("Semester", SEMESTER_COL)
gender_sel = multiselect_filter("Gender", GENDER_COL)

filtered = df.copy()
for col_name, sel in [
    (FACULTY_COL, faculty_sel), (DEPT_COL, dept_sel), (PROGRAM_COL, program_sel),
    (SEMESTER_COL, semester_sel), (GENDER_COL, gender_sel),
]:
    if sel:
        filtered = filtered[filtered[col_name].isin(sel)]

st.sidebar.markdown("---")
st.sidebar.caption(f"Showing **{len(filtered)}** of **{len(df)}** survey responses")


def render_survey_dashboard():
    st.title("🎓 Riphah CEID – Career Aspirations & Pathways Survey (2025)")
    st.caption("Live dashboard powered by Google Sheets responses")

    k1, k2, k3, k4 = st.columns(4)
    k1.metric("Total Responses", len(filtered))
    if CONFIDENCE_COL in filtered.columns:
        avg_conf = pd.to_numeric(filtered[CONFIDENCE_COL], errors="coerce").mean()
        k2.metric("Avg. Confidence (1-5)", f"{avg_conf:.1f}" if pd.notna(avg_conf) else "N/A")
    if CAREER_COL in filtered.columns and len(filtered):
        top_path = filtered[CAREER_COL].mode()
        k3.metric("Top Career Path", top_path.iloc[0] if not top_path.empty else "N/A")
    if GENDER_COL in filtered.columns and len(filtered):
        female_pct = (filtered[GENDER_COL] == "Female").mean() * 100
        k4.metric("Female Respondents", f"{female_pct:.0f}%")

    st.markdown("---")
    c1, c2 = st.columns(2)
    with c1:
        if CAREER_COL in filtered.columns:
            st.subheader("Career Path Ambitions")
            counts = filtered[CAREER_COL].value_counts().reset_index()
            counts.columns = ["Career Path", "Count"]
            fig = px.bar(counts, x="Count", y="Career Path", orientation="h", color="Career Path", text="Count")
            fig.update_layout(showlegend=False, yaxis_title=None)
            st.plotly_chart(fig, use_container_width=True, key="sd_career")
    with c2:
        if MOTIVATION_COL in filtered.columns:
            st.subheader("Primary Motivation")
            counts = filtered[MOTIVATION_COL].value_counts().reset_index()
            counts.columns = ["Motivation", "Count"]
            fig = px.pie(counts, names="Motivation", values="Count", hole=0.4)
            st.plotly_chart(fig, use_container_width=True, key="sd_motivation")

    c3, c4 = st.columns(2)
    with c3:
        if CONFIDENCE_COL in filtered.columns:
            st.subheader("Confidence Level Distribution")
            conf_numeric = pd.to_numeric(filtered[CONFIDENCE_COL], errors="coerce").dropna()
            fig = px.histogram(conf_numeric, nbins=5, labels={"value": "Confidence (1-5)"})
            fig.update_layout(showlegend=False, yaxis_title="Responses")
            st.plotly_chart(fig, use_container_width=True, key="sd_confidence")
    with c4:
        if GENDER_COL in filtered.columns:
            st.subheader("Gender Split")
            counts = filtered[GENDER_COL].value_counts().reset_index()
            counts.columns = ["Gender", "Count"]
            fig = px.pie(counts, names="Gender", values="Count", hole=0.4)
            st.plotly_chart(fig, use_container_width=True, key="sd_gender")

    c5, c6 = st.columns(2)
    with c5:
        if SEMESTER_COL in filtered.columns:
            st.subheader("Responses by Semester")
            counts = filtered[SEMESTER_COL].value_counts().reset_index()
            counts.columns = ["Semester", "Count"]
            fig = px.bar(counts, x="Semester", y="Count", text="Count")
            st.plotly_chart(fig, use_container_width=True, key="sd_semester")
    with c6:
        if DEPT_COL in filtered.columns:
            st.subheader("Responses by Department")
            counts = filtered[DEPT_COL].value_counts().reset_index()
            counts.columns = ["Department", "Count"]
            fig = px.bar(counts, x="Count", y="Department", orientation="h", text="Count")
            fig.update_layout(yaxis_title=None)
            st.plotly_chart(fig, use_container_width=True, key="sd_department")

    st.markdown("---")
    st.header("🚀 Entrepreneurship & Freelancing Insights")
    c7, c8 = st.columns(2)
    with c7:
        if BIZ_TYPE_COL in filtered.columns:
            st.subheader("Business/Venture Interests")
            counts = filtered[BIZ_TYPE_COL].dropna().value_counts().reset_index()
            counts.columns = ["Business Type", "Count"]
            if not counts.empty:
                fig = px.bar(counts, x="Count", y="Business Type", orientation="h", text="Count")
                fig.update_layout(yaxis_title=None)
                st.plotly_chart(fig, use_container_width=True, key="sd_biztype")
            else:
                st.info("No data for the current filter selection.")
    with c8:
        if FREELANCE_SKILL_COL in filtered.columns:
            st.subheader("Freelancing Skills of Interest")
            counts = filtered[FREELANCE_SKILL_COL].dropna().value_counts().reset_index()
            counts.columns = ["Skill", "Count"]
            if not counts.empty:
                fig = px.bar(counts, x="Count", y="Skill", orientation="h", text="Count")
                fig.update_layout(yaxis_title=None)
                st.plotly_chart(fig, use_container_width=True, key="sd_freelance")
            else:
                st.info("No data for the current filter selection.")

    st.markdown("---")
    st.header("🌍 Higher Education & Employment Preferences")
    c9, c10 = st.columns(2)
    with c9:
        if EDU_LEVEL_COL in filtered.columns:
            st.subheader("Higher Education Level")
            counts = filtered[EDU_LEVEL_COL].dropna().value_counts().reset_index()
            counts.columns = ["Level", "Count"]
            if not counts.empty:
                fig = px.pie(counts, names="Level", values="Count", hole=0.4)
                st.plotly_chart(fig, use_container_width=True, key="sd_edulevel")
            else:
                st.info("No data for the current filter selection.")
    with c10:
        if INDUSTRY_COL in filtered.columns:
            st.subheader("Target Industry / Field")
            counts = filtered[INDUSTRY_COL].dropna().value_counts().reset_index()
            counts.columns = ["Industry", "Count"]
            if not counts.empty:
                fig = px.bar(counts, x="Count", y="Industry", orientation="h", text="Count")
                fig.update_layout(yaxis_title=None)
                st.plotly_chart(fig, use_container_width=True, key="sd_industry")
            else:
                st.info("No data for the current filter selection.")

    st.markdown("---")
    with st.expander("📄 View filtered raw data"):
        st.dataframe(filtered, use_container_width=True)
        st.download_button(
            "Download filtered data as CSV", filtered.to_csv(index=False).encode("utf-8"),
            "filtered_survey_data.csv", "text/csv", key="sd_download",
        )


# ========================================================================
# SECTION 2 — CEID KPI PORTAL
# ========================================================================
# Each faculty has its OWN Google Sheet (one tab per vertical). Every tab
# has both the checkpoint targets AND an "Actual (latest)" column that
# coordinators update directly — so no targets are hardcoded here.
#
# Add each faculty's sheet link as it becomes available:
FACULTY_SHEETS = {
    "Riphah College of Science and Technology":
        "https://docs.google.com/spreadsheets/d/15Afx3u6P4x-lVEsdHzbAyopCyEumsagcaQ4roE2J4pE/edit",
    "Riphah School of Business and Management":
        "https://docs.google.com/spreadsheets/d/1JDhtbaP2tl3giVEwUWRe0c5m2l3hlORuuvz818YYm90/edit",
    "Riphah School of Computing and Innovation":
        "https://docs.google.com/spreadsheets/d/1c6FP4H5EKqKxAmxO6z9g47KoEz3KwJ9Ob9cU8j1cM-Y/edit",
    "Riphah Institute of Pharmaceutical Sciences":
        "https://docs.google.com/spreadsheets/d/1GefvghkGWx6EyGyzL6xPC6H9zfurtsCvjoFsH166RrM/edit",
    "Riphah Institute of Clinical & Professional Psychology":
        "https://docs.google.com/spreadsheets/d/15AWu05J7DrBEjwOazbtbvcHwXvluEHBraH0ctBQx_w0/edit",
    "Riphah College of Rehabilitation and Allied Health Sciences":
        "https://docs.google.com/spreadsheets/d/137xHUQr-Wb-PLZhwr1xKL2-DePmpjo9UtabpY9JSBoE/edit",
}
# NOTE: every faculty except Computing and Innovation is currently a raw
# duplicate of Computing and Innovation's sheet (same targets, same student
# counts, same coordinator names) — it's a starting template only, not real
# data. Replace each one's numbers with that faculty's actual KPI report
# once available.

CEID_DEPARTMENTS = list(FACULTY_SHEETS.keys())

# Display label -> tab name in each faculty's spreadsheet.
VERTICAL_DISPLAY_TO_KEY = {
    "Alumni Engagement": "Alumni Engagement",
    "Career Services": "Career Services",
    "Eve Venture": "EVE Ventures",
    "Family Owned Businesses": "Family-Owned Businesses",
    "Further Education": "Further Education",
    "FYP Transformation": "Final Year Projects",
    "Industrial Linkages": "Industry Linkages",
    "Innovation Hub": "Innovation Hub",
    "ORIC Commercialization": "ORIC Commercialisation",
}
CEID_VERTICALS = list(VERTICAL_DISPLAY_TO_KEY.keys())

CHECKPOINT_COLUMNS = [
    (date(2026, 9, 30), "Target 30 Sep"),
    (date(2026, 10, 31), "Target 31 Oct"),
    (date(2026, 11, 30), "Target 30 Nov"),
    (date(2026, 12, 31), "Target 31 Dec"),
]


def current_checkpoint():
    today = date.today()
    for d, col in CHECKPOINT_COLUMNS:
        if today <= d:
            return col, col.replace("Target ", "")
    return CHECKPOINT_COLUMNS[-1][1], CHECKPOINT_COLUMNS[-1][1].replace("Target ", "")


def _parse_num(v):
    if v is None or (isinstance(v, float) and pd.isna(v)):
        return None
    s = str(v).strip().replace("%", "").replace(",", "")
    if s == "" or s.lower() == "nan":
        return None
    try:
        return float(s)
    except ValueError:
        return None


@st.cache_data(ttl=600, show_spinner=False)
def load_faculty_vertical_sheet(sheet_id: str, vertical_key: str) -> pd.DataFrame:
    url = _sheet_csv_url(sheet_id, sheet_name=vertical_key)
    d = pd.read_csv(url)
    d.columns = [c.strip() for c in d.columns]
    return d.dropna(axis=1, how="all")


def load_vertical_sheet_with_fallback(sheet_id: str, vertical_key: str, vertical_display: str):
    """Try the canonical tab name first, then the sidebar display label, in
    case the tab was renamed to match what's shown on screen. A missing tab
    doesn't raise an error from Google's endpoint, it just comes back empty,
    so we check for real data rather than relying on exceptions alone."""
    candidate_names = [vertical_key]
    if vertical_display not in candidate_names:
        candidate_names.append(vertical_display)

    last_error = None
    for name in candidate_names:
        try:
            candidate_df = load_faculty_vertical_sheet(sheet_id, name)
            if "KPI" in candidate_df.columns and candidate_df["KPI"].notna().any():
                return candidate_df, None
        except Exception as e:
            last_error = e
    return None, last_error


def kpi_rows_with_pct(sheet_df: pd.DataFrame, checkpoint_col: str):
    """Yield (kpi, target, actual, pct, note) for each row in the tab."""
    results = []
    for _, row in sheet_df.iterrows():
        kpi = row.get("KPI")
        if pd.isna(kpi) or not str(kpi).strip():
            continue
        target = _parse_num(row.get(checkpoint_col))
        actual = _parse_num(row.get("Actual (latest)"))
        note = row.get("Delivery note")
        note = "" if pd.isna(note) else str(note)
        pct = None
        if actual is not None and target:
            pct = actual / target * 100
        elif actual is not None and target == 0:
            pct = 100.0 if actual >= 0 else 0.0
        results.append((str(kpi), target, actual, pct, note))
    return results


def render_kpi_section(department: str, vertical_display: str):
    sheet_link = FACULTY_SHEETS.get(department)
    if not sheet_link:
        st.info(
            f"No KPI sheet connected yet for **{department}**. Add its sheet link to "
            f"`FACULTY_SHEETS[\"{department}\"]` in `app.py` once it's available."
        )
        return

    if department != "Riphah School of Computing and Innovation":
        st.warning(
            f"⚠️ **{department}**'s sheet is currently a duplicated template from "
            "Riphah School of Computing and Innovation — these targets, counts, and "
            "coordinator names are placeholders, not this faculty's real data. "
            "Replace them once this faculty's actual KPI report is available."
        )

    sheet_id = _extract_sheet_id(sheet_link)
    vertical_key = VERTICAL_DISPLAY_TO_KEY[vertical_display]
    with st.spinner("Loading KPI data..."):
        sheet_df, load_error = load_vertical_sheet_with_fallback(sheet_id, vertical_key, vertical_display)

    if sheet_df is None:
        st.error(
            "Couldn't find a matching tab for this vertical. Make sure the "
            f"spreadsheet is shared as 'Anyone with the link -> Viewer' and has "
            f"a tab named either '{vertical_key}' or '{vertical_display}' with "
            f"data in a 'KPI' column."
            + (f" Details: {load_error}" if load_error else "")
        )
        return

    checkpoint_col, ckpt_label = current_checkpoint()
    st.caption(f"Current checkpoint: **{ckpt_label} 2026**")

    rows = kpi_rows_with_pct(sheet_df, checkpoint_col)
    if not rows:
        st.info("No KPI rows found in this tab yet.")
        return

    chart_records = []
    for kpi, target, actual, pct, note in rows:
        if target is not None:
            chart_records.append({"KPI": kpi, "Series": f"Target ({ckpt_label})", "Value": target})
        if actual is not None:
            chart_records.append({"KPI": kpi, "Series": "Actual", "Value": actual})
    if chart_records:
        chart_df = pd.DataFrame(chart_records)
        fig = px.bar(
            chart_df, x="Value", y="KPI", color="Series", orientation="h", barmode="group",
            color_discrete_map={f"Target ({ckpt_label})": "#4C78A8", "Actual": "#F58518"},
        )
        fig.update_layout(yaxis_title=None, legend_title=None, height=max(320, 60 * len(rows)))
        st.plotly_chart(fig, use_container_width=True, key=f"chart_{department}_{vertical_display}")

    cols = st.columns(2)
    valid_pcts = []
    for i, (kpi, target, actual, pct, note) in enumerate(rows):
        with cols[i % 2]:
            if actual is None:
                st.metric(kpi, "No data yet", f"Target: {target} by {ckpt_label}")
            else:
                st.metric(kpi, f"{actual:g} / {target:g}" if target is not None else f"{actual:g}",
                          f"{pct:.0f}% of target" if pct is not None else None)
                if pct is not None:
                    st.progress(min(1.0, pct / 100))
                    valid_pcts.append(min(pct, 150))
            if note:
                st.caption(note)

    st.markdown("---")
    if valid_pcts:
        avg = sum(valid_pcts) / len(valid_pcts)
        rag = "🟢 On track" if avg >= 85 else ("🟡 Attention needed" if avg >= 65 else "🔴 Intervention needed")
        st.markdown(f"### Overall KPI attainment: {avg:.0f}% — {rag}")
        st.caption(
            "Automatic KPI-only estimate based on the 'Actual (latest)' column. "
            "Does not include evidence quality, conversion/impact, reporting "
            "discipline, or cross-vertical collaboration."
        )
    else:
        st.info("No actuals recorded yet for this vertical — coordinators should fill in the 'Actual (latest)' column.")

    with st.expander("📄 Raw sheet data"):
        st.dataframe(sheet_df, use_container_width=True)
        st.download_button(
            "Download as CSV", sheet_df.to_csv(index=False).encode("utf-8"),
            f"{vertical_key}_{department}.csv", "text/csv", key=f"dl_{vertical_key}_{department}",
        )


def render_ceid_portal():
    header_col, refresh_col = st.columns([5, 1])
    with header_col:
        st.title("🏫 Riphah CEID Portal")
        st.caption("Click a department to expand its verticals, then click a vertical to see KPI progress")
    with refresh_col:
        st.write("")
        if st.button("🔄 Refresh data now", key="refresh_portal"):
            st.cache_data.clear()
            st.rerun()

    st.session_state.setdefault("ceid_department", CEID_DEPARTMENTS[0])
    st.session_state.setdefault("ceid_vertical", CEID_VERTICALS[0])

    nav_col, content_col = st.columns([1, 2], gap="large")
    with nav_col:
        st.markdown("### Departments")
        for dept in CEID_DEPARTMENTS:
            is_active_dept = dept == st.session_state["ceid_department"]
            if dept == "Riphah School of Computing and Innovation":
                label = dept + " ✅"
            elif FACULTY_SHEETS.get(dept):
                label = dept + " 🟡"
            else:
                label = dept
            with st.expander(label, expanded=is_active_dept):
                for vertical in CEID_VERTICALS:
                    is_active = is_active_dept and vertical == st.session_state["ceid_vertical"]
                    if st.button(
                        ("• " if is_active else "") + vertical,
                        key=f"btn_{dept}_{vertical}", use_container_width=True,
                        type="primary" if is_active else "secondary",
                    ):
                        st.session_state["ceid_department"] = dept
                        st.session_state["ceid_vertical"] = vertical
                        st.rerun()

    with content_col:
        active_dept = st.session_state["ceid_department"]
        active_vertical = st.session_state["ceid_vertical"]
        st.markdown(f"## {active_vertical}")
        st.caption(active_dept)
        render_kpi_section(active_dept, active_vertical)


def render_ceo_overview():
    header_col, refresh_col = st.columns([5, 1])
    with header_col:
        st.title("📊 CEO Overview")
        st.caption("Faculty x Vertical simplified KPI attainment heat map")
    with refresh_col:
        st.write("")
        if st.button("🔄 Refresh data now", key="refresh_ceo"):
            st.cache_data.clear()
            st.rerun()

    checkpoint_col, ckpt_label = current_checkpoint()
    st.caption(f"Current checkpoint: **{ckpt_label} 2026**")

    rows = []
    for dept in CEID_DEPARTMENTS:
        row = {"Faculty": dept}
        sheet_link = FACULTY_SHEETS.get(dept)
        for display_name, key in VERTICAL_DISPLAY_TO_KEY.items():
            if not sheet_link:
                row[display_name] = None
                continue
            try:
                sheet_id = _extract_sheet_id(sheet_link)
                sheet_df, _ = load_vertical_sheet_with_fallback(sheet_id, key, display_name)
                if sheet_df is None:
                    row[display_name] = None
                    continue
                kpi_rows = kpi_rows_with_pct(sheet_df, checkpoint_col)
                pcts = [pct for _, _, _, pct, _ in kpi_rows if pct is not None]
                row[display_name] = round(sum(min(p, 150) for p in pcts) / len(pcts)) if pcts else None
            except Exception:
                row[display_name] = None
        rows.append(row)

    overview_df = pd.DataFrame(rows).set_index("Faculty")

    def fmt(v):
        if v is None or pd.isna(v):
            return "—"
        icon = "🟢" if v >= 85 else ("🟡" if v >= 65 else "🔴")
        return f"{icon} {v:.0f}%"

    display_df = overview_df.apply(lambda col: col.map(fmt))
    st.dataframe(display_df, use_container_width=True)
    st.caption(
        "🟢 ≥85% of checkpoint target (On track) · 🟡 65–84% (Attention needed) · "
        "🔴 <65% (Intervention needed) · — No sheet connected or no actuals yet. "
        "Simplified KPI-only estimate, not the full weighted CEO score."
    )


# ----------------------------------------------------------------------
# TOP-LEVEL TABS
# ----------------------------------------------------------------------
tab_portal, tab_ceo, tab_survey = st.tabs(["🏫 CEID Portal", "📊 CEO Overview", "🎓 Survey Dashboard"])

with tab_portal:
    render_ceid_portal()

with tab_ceo:
    render_ceo_overview()

with tab_survey:
    render_survey_dashboard()
