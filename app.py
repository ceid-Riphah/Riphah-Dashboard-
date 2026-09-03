"""
Riphah CEID – Career Survey Dashboard + CEID KPI Portal
------------------------------------------------------------------
Three tabs at the top (no scrolling needed to reach any of them):

1. CEID Portal — department -> vertical drill-down showing actual-vs-
   target KPI progress (targets sourced from the Sep-Dec 2026
   Implementation Plan), fed by Google Forms responses.
2. CEO Overview — a Faculty x Vertical heat map (simplified KPI
   attainment %, not the full weighted CEO score).
3. Survey Dashboard — the original Career Aspirations & Pathways
   Survey (2025) analytics, unchanged.

Run locally:
    pip install -r requirements.txt
    streamlit run app.py

Deploy: push to GitHub, deploy on share.streamlit.io, main file = app.py
"""

import re
from datetime import date

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
        return f"https://docs.google.com/spreadsheets/d/{sheet_id}/gviz/tq?tqx=out:csv&sheet={sheet_name}"
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
# Paste the CEID KPI Tracker spreadsheet link (from running
# create_ceid_forms.gs) here once it exists. Full share link or bare
# ID both work.
CEID_KPI_SHEET_LINK = ""  # <-- fill this in

CEID_DEPARTMENTS = [
    "Riphah College of Science and Technology",
    "Riphah School of Business and Management",
    "Riphah School of Computing and Innovation",
    "Riphah Institute of Pharmaceutical Sciences",
    "Riphah Institute of Clinical & Professional Psychology",
    "Riphah College of Rehabilitation and Allied Health Sciences",
]

# Display label -> official vertical key (must match the Google Form /
# spreadsheet tab names created by create_ceid_forms.gs).
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

# Cumulative KPI targets at each checkpoint: [30 Sep, 31 Oct, 30 Nov, 31 Dec]
# Sourced from the Sep-Dec 2026 Implementation Plan.
KPI_TARGETS = {
    "Career Services": {
        "Students profiled": [60, 120, 180, 220],
        "Career sessions/bootcamps": [1, 2, 3, 4],
        "Employers meaningfully engaged": [5, 12, 20, 25],
        "CV/LinkedIn reviews": [20, 50, 80, 100],
        "Mock interviews": [0, 20, 50, 60],
        "Verified internships generated": [0, 8, 20, 25],
        "Verified job opportunities": [0, 3, 8, 10],
    },
    "Innovation Hub": {
        "Students engaged": [50, 100, 150, 190],
        "Innovators identified": [15, 30, 50, 60],
        "Ideas/projects logged": [10, 25, 40, 50],
        "Startup teams formed": [0, 5, 10, 12],
        "Teams completing validation": [0, 3, 8, 10],
        "MVPs/prototypes evidenced": [0, 1, 4, 5],
        "Teams nominated to CEID": [0, 2, 5, 6],
    },
    "Final Year Projects": {
        "Active FYPs mapped (%)": [100, 100, 100, 100],
        "Industry challenges logged": [5, 15, 25, 30],
        "FYPs assessed with rubric": [10, 30, 50, 60],
        "Mentoring/innovation clinics": [1, 2, 3, 4],
        "External validation trials": [0, 3, 8, 10],
        "Prototype projects advanced": [0, 3, 8, 10],
        "Startup/IP referrals": [0, 2, 5, 6],
    },
    "Industry Linkages": {
        "Verified industry contacts": [10, 25, 40, 50],
        "Meaningful partner meetings": [3, 8, 15, 19],
        "Advisory members confirmed": [0, 4, 6, 8],
        "Industry visits/expert sessions": [1, 3, 6, 8],
        "Industry challenges captured": [3, 10, 20, 25],
        "Industry mentors recruited": [0, 3, 8, 10],
        "Documented collaborations": [0, 2, 5, 6],
    },
    "Alumni Engagement": {
        "Alumni records consolidated": [100, 250, 400, 500],
        "Profiles verified/updated": [40, 120, 200, 250],
        "Active alumni volunteers": [5, 12, 20, 25],
        "Chapter established (0 or 1)": [0, 1, 1, 1],
        "Alumni events/sessions": [0, 1, 2, 2],
        "Mentoring interactions": [0, 15, 40, 50],
        "Verified opportunity leads": [0, 5, 12, 15],
    },
    "EVE Ventures": {
        "Female students profiled": [50, 120, 200, 250],
        "Leadership/enterprise sessions": [1, 2, 3, 4],
        "Participants trained": [25, 60, 100, 120],
        "Female mentors engaged": [2, 5, 8, 10],
        "Mentoring interactions": [0, 15, 40, 50],
        "Women-led ideas/teams": [5, 10, 15, 19],
        "Teams/projects advanced": [0, 2, 5, 6],
    },
    "Family-Owned Businesses": {
        "Family businesses identified": [8, 18, 30, 40],
        "Student consultants engaged": [10, 25, 40, 50],
        "Diagnostics completed": [0, 5, 12, 15],
        "Consultancy projects active": [0, 4, 8, 10],
        "Owner workshops/clinics": [0, 1, 2, 2],
        "Improvement plans delivered": [0, 3, 8, 10],
        "Adopted actions/evidenced outcomes": [0, 1, 4, 5],
    },
    "Further Education": {
        "Students profiled": [60, 140, 220, 280],
        "Awareness/application sessions": [1, 2, 3, 4],
        "Students receiving guidance": [20, 60, 100, 120],
        "Scholarship applications supported": [0, 10, 25, 30],
        "Postgraduate applications supported": [0, 8, 20, 25],
        "Certification pathways supported": [0, 5, 15, 19],
        "Mentoring interactions": [0, 10, 25, 30],
    },
    "ORIC Commercialisation": {
        "Research outputs mapped": [10, 25, 40, 50],
        "Commercial assessments": [5, 15, 30, 40],
        "Researchers engaged": [10, 25, 40, 50],
        "Commercial opportunities identified": [0, 4, 8, 10],
        "IP/patent candidates": [0, 2, 4, 5],
        "Proof-of-concept cases": [0, 1, 3, 4],
        "Industry validation discussions": [0, 2, 5, 6],
    },
}

CHECKPOINTS = [
    (date(2026, 9, 30), "30 Sep"),
    (date(2026, 10, 31), "31 Oct"),
    (date(2026, 11, 30), "30 Nov"),
    (date(2026, 12, 31), "31 Dec"),
]


def current_checkpoint():
    today = date.today()
    for i, (d, label) in enumerate(CHECKPOINTS):
        if today <= d:
            return i, label
    return len(CHECKPOINTS) - 1, CHECKPOINTS[-1][1]


@st.cache_data(ttl=600, show_spinner=False)
def load_kpi_vertical_sheet(sheet_id: str, vertical_key: str) -> pd.DataFrame:
    url = _sheet_csv_url(sheet_id, sheet_name=vertical_key)
    d = pd.read_csv(url)
    d.columns = [c.strip() for c in d.columns]
    return d.dropna(axis=1, how="all")


def kpi_attainment_pcts(sub_df: pd.DataFrame, vertical_key: str, ckpt_idx: int):
    """Return list of (kpi_name, actual, target, pct) for the given faculty's rows."""
    results = []
    for kpi, targets in KPI_TARGETS[vertical_key].items():
        target = targets[ckpt_idx]
        actual = None
        if kpi in sub_df.columns:
            numeric = pd.to_numeric(sub_df[kpi], errors="coerce")
            if numeric.notna().any():
                actual = numeric.max()
        pct = None
        if actual is not None and target:
            pct = actual / target * 100
        elif actual is not None and target == 0:
            pct = 100.0 if actual >= 0 else 0.0
        results.append((kpi, actual, target, pct))
    return results


def render_kpi_section(vertical_key: str, department: str):
    if not CEID_KPI_SHEET_LINK:
        st.info(
            "The CEID KPI Tracker spreadsheet isn't connected yet. Run "
            "`create_ceid_forms.gs` in Google Apps Script to generate the 9 "
            "forms, then paste the resulting spreadsheet link into "
            "`CEID_KPI_SHEET_LINK` near the top of `app.py`."
        )
        return

    sheet_id = _extract_sheet_id(CEID_KPI_SHEET_LINK)
    try:
        with st.spinner("Loading KPI data..."):
            sheet_df = load_kpi_vertical_sheet(sheet_id, vertical_key)
    except Exception as e:
        st.error(
            "Couldn't load this vertical's sheet. Make sure the spreadsheet is "
            f"shared as 'Anyone with the link -> Viewer'. Details: {e}"
        )
        return

    if "Faculty" not in sheet_df.columns:
        st.warning("This sheet doesn't have a 'Faculty' column yet — no submissions recorded.")
        return

    sub = sheet_df[sheet_df["Faculty"] == department]
    ckpt_idx, ckpt_label = current_checkpoint()

    if sub.empty:
        st.info(f"No submissions yet from {department} for this vertical.")
        st.caption(f"Current checkpoint: {ckpt_label} 2026")
        return

    st.caption(f"Current checkpoint: **{ckpt_label} 2026** · {len(sub)} submission(s) on file")

    rows = kpi_attainment_pcts(sub, vertical_key, ckpt_idx)
    cols = st.columns(2)
    valid_pcts = []
    for i, (kpi, actual, target, pct) in enumerate(rows):
        with cols[i % 2]:
            if actual is None:
                st.metric(kpi, "No data", f"Target: {target} by {ckpt_label}")
            else:
                st.metric(kpi, f"{actual:.0f} / {target}", f"{pct:.0f}% of target")
                st.progress(min(1.0, pct / 100) if pct is not None else 0)
                valid_pcts.append(min(pct, 150))

    st.markdown("---")
    if valid_pcts:
        avg = sum(valid_pcts) / len(valid_pcts)
        rag = "🟢 On track" if avg >= 85 else ("🟡 Attention needed" if avg >= 65 else "🔴 Intervention needed")
        st.markdown(f"### Overall KPI attainment: {avg:.0f}% — {rag}")
        st.caption(
            "This is an automatic KPI-only estimate based on submitted numbers. "
            "The official CEO score also weighs evidence quality, conversion/impact, "
            "reporting discipline and cross-vertical collaboration."
        )

    with st.expander("📄 Raw submissions for this faculty"):
        st.dataframe(sub, use_container_width=True)
        st.download_button(
            "Download as CSV", sub.to_csv(index=False).encode("utf-8"),
            f"{vertical_key}_{department}.csv", "text/csv", key=f"dl_{vertical_key}_{department}",
        )


def render_ceid_portal():
    st.title("🏫 Riphah CEID Portal")
    st.caption("Click a department to expand its verticals, then click a vertical to see KPI progress")

    st.session_state.setdefault("ceid_department", CEID_DEPARTMENTS[0])
    st.session_state.setdefault("ceid_vertical", CEID_VERTICALS[0])

    nav_col, content_col = st.columns([1, 2], gap="large")
    with nav_col:
        st.markdown("### Departments")
        for dept in CEID_DEPARTMENTS:
            is_active_dept = dept == st.session_state["ceid_department"]
            with st.expander(dept, expanded=is_active_dept):
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
        render_kpi_section(VERTICAL_DISPLAY_TO_KEY[active_vertical], active_dept)


def render_ceo_overview():
    st.title("📊 CEO Overview")
    st.caption("Faculty x Vertical simplified KPI attainment heat map")

    if not CEID_KPI_SHEET_LINK:
        st.info(
            "Connect `CEID_KPI_SHEET_LINK` (see the CEID Portal tab for instructions) "
            "to populate this heat map."
        )
        return

    sheet_id = _extract_sheet_id(CEID_KPI_SHEET_LINK)
    ckpt_idx, ckpt_label = current_checkpoint()
    st.caption(f"Current checkpoint: **{ckpt_label} 2026**")

    rows = []
    for dept in CEID_DEPARTMENTS:
        row = {"Faculty": dept}
        for display_name, key in VERTICAL_DISPLAY_TO_KEY.items():
            try:
                sheet_df = load_kpi_vertical_sheet(sheet_id, key)
                sub = sheet_df[sheet_df["Faculty"] == dept] if "Faculty" in sheet_df.columns else sheet_df.iloc[0:0]
            except Exception:
                sub = pd.DataFrame()
            if sub.empty:
                row[display_name] = None
            else:
                pcts = [pct for _, _, _, pct in kpi_attainment_pcts(sub, key, ckpt_idx) if pct is not None]
                row[display_name] = round(sum(min(p, 150) for p in pcts) / len(pcts)) if pcts else None
        rows.append(row)

    overview_df = pd.DataFrame(rows).set_index("Faculty")

    def fmt(v):
        if v is None or pd.isna(v):
            return "—"
        icon = "🟢" if v >= 85 else ("🟡" if v >= 65 else "🔴")
        return f"{icon} {v:.0f}%"

    display_df = overview_df.applymap(fmt)
    st.dataframe(display_df, use_container_width=True)
    st.caption(
        "🟢 ≥85% of checkpoint target (On track) · 🟡 65–84% (Attention needed) · "
        "🔴 <65% (Intervention needed) · — No submissions yet. "
        "This is a simplified KPI-only estimate, not the full weighted CEO score."
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
