"""
Riphah CEID – Career Survey Dashboard + CEID Portal
------------------------------------------------------------------
Two sections, selectable via tabs at the top (so neither requires
scrolling past the other):

1. CEID Portal (opens by default) — click a department to expand its
   9 verticals, click a vertical to load its data on the right.
2. Survey Dashboard — the original Career Aspirations & Pathways
   Survey (2025) analytics, unchanged.

Run locally:
    pip install -r requirements.txt
    streamlit run app.py

Deploy: push to GitHub, deploy on share.streamlit.io, main file = app.py
"""

import re

import pandas as pd
import plotly.express as px
import streamlit as st

# ----------------------------------------------------------------------
# CONFIG
# ----------------------------------------------------------------------
SHEET_ID = "16eFMceIi7pgMUgxe_7Hn0ye94RuidGLtrrITNit1liE"
SHEET_TAB_NAME = "Form_Responses"
GID = "0"

CANDIDATE_URLS = [
    f"https://docs.google.com/spreadsheets/d/{SHEET_ID}/gviz/tq?tqx=out:csv&sheet={SHEET_TAB_NAME}",
    f"https://docs.google.com/spreadsheets/d/{SHEET_ID}/gviz/tq?tqx=out:csv&gid={GID}",
    f"https://docs.google.com/spreadsheets/d/{SHEET_ID}/export?format=csv&gid={GID}",
]

st.set_page_config(
    page_title="Riphah CEID – Dashboard",
    page_icon="🎓",
    layout="wide",
)

# ----------------------------------------------------------------------
# SURVEY DATA LOADING
# ----------------------------------------------------------------------
@st.cache_data(ttl=600)
def load_data(url: str) -> pd.DataFrame:
    df = pd.read_csv(url)
    df.columns = [c.strip() for c in df.columns]
    df = df.dropna(axis=1, how="all")
    key_col = "Which career path best describes your ambition?"
    if key_col in df.columns:
        df = df[df[key_col].notna()]
    return df


df = None
load_error = None

with st.spinner("Loading survey responses..."):
    for url in CANDIDATE_URLS:
        try:
            df = load_data(url)
            break
        except Exception as e:
            load_error = e

if df is None:
    st.error(
        "Couldn't load the Google Sheet automatically.\n\n"
        "This usually means the sheet isn't fully public yet. In Google Sheets, "
        "go to **Share → General access → Anyone with the link → Viewer**, then "
        "reload this app.\n\n"
        f"Technical detail: {load_error}"
    )
    st.info("In the meantime, you can upload a CSV export of the sheet manually below.")
    uploaded = st.file_uploader("Upload survey CSV", type=["csv"])
    if uploaded is not None:
        df = pd.read_csv(uploaded)
        df.columns = [c.strip() for c in df.columns]
        df = df.dropna(axis=1, how="all")
        key_col = "Which career path best describes your ambition?"
        if key_col in df.columns:
            df = df[df[key_col].notna()]
    else:
        st.stop()

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

# ----------------------------------------------------------------------
# SIDEBAR FILTERS (apply to the Survey Dashboard tab)
# ----------------------------------------------------------------------
st.sidebar.header("🔎 Survey Filters")


def multiselect_filter(label, column_name):
    if column_name not in df.columns:
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
    (FACULTY_COL, faculty_sel),
    (DEPT_COL, dept_sel),
    (PROGRAM_COL, program_sel),
    (SEMESTER_COL, semester_sel),
    (GENDER_COL, gender_sel),
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
            fig = px.bar(counts, x="Count", y="Career Path", orientation="h",
                         color="Career Path", text="Count")
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
            "Download filtered data as CSV",
            filtered.to_csv(index=False).encode("utf-8"),
            "filtered_survey_data.csv",
            "text/csv",
            key="sd_download",
        )


# ========================================================================
# CEID PORTAL — Department (click to expand) x Vertical explorer
# ========================================================================
CEID_DEPARTMENTS = [
    "Riphah College of Science and Technology",
    "Riphah School of Business and Management",
    "Riphah School of Computing and Innovation",
    "Riphah Institute of Pharmaceutical Sciences",
    "Riphah Institute of Clinical & Professional Psychology",
    "Riphah College of Rehabilitation and Allied Health Sciences",
]

CEID_VERTICALS = [
    "Alumni Engagement",
    "Career Services",
    "Eve Venture",
    "Family Owned Businesses",
    "Further Education",
    "FYP Transformation",
    "Industrial Linkages",
    "Innovation Hub",
    "ORIC Commercialization",
]

# Fill these in as sheet links become available. Paste the normal
# Google Sheets "share" link (the ...edit?usp=sharing one) — no need
# to convert it to CSV format yourself.
#
# Example:
# CEID_DATA_SOURCES["Riphah School of Computing and Innovation"]["Career Services"] = \
#     "https://docs.google.com/spreadsheets/d/XXXXXXXXXXXXXXXXXXXX/edit?usp=sharing"
#
# If a sheet has multiple tabs, target one by name with a tuple:
# CEID_DATA_SOURCES["..."]["..."] = ("https://.../edit", "Form_Responses")
CEID_DATA_SOURCES: dict[str, dict[str, object]] = {
    dept: {vertical: None for vertical in CEID_VERTICALS} for dept in CEID_DEPARTMENTS
}

_SHEET_ID_RE = re.compile(r"/spreadsheets/d/([a-zA-Z0-9-_]+)")


def _ceid_to_csv_url(share_link: str, sheet_name: str | None = None, gid: str = "0") -> str:
    match = _SHEET_ID_RE.search(share_link)
    if not match:
        raise ValueError("Doesn't look like a Google Sheets link.")
    sheet_id = match.group(1)
    if sheet_name:
        return f"https://docs.google.com/spreadsheets/d/{sheet_id}/gviz/tq?tqx=out:csv&sheet={sheet_name}"
    return f"https://docs.google.com/spreadsheets/d/{sheet_id}/gviz/tq?tqx=out:csv&gid={gid}"


@st.cache_data(ttl=600, show_spinner=False)
def _ceid_load_sheet(csv_url: str) -> pd.DataFrame:
    sheet_df = pd.read_csv(csv_url)
    sheet_df.columns = [c.strip() for c in sheet_df.columns]
    return sheet_df.dropna(axis=1, how="all")


def _ceid_resolve_source(source):
    if source is None:
        return None
    if isinstance(source, tuple):
        link, sheet_name = source
        return _ceid_to_csv_url(link, sheet_name=sheet_name)
    return _ceid_to_csv_url(source)


def _ceid_render_generic_dashboard(sheet_df: pd.DataFrame, title: str):
    st.subheader(title)
    st.caption(f"{len(sheet_df)} rows · {len(sheet_df.columns)} columns")

    with st.expander("📄 Raw data", expanded=False):
        st.dataframe(sheet_df, use_container_width=True)
        st.download_button(
            "Download as CSV",
            sheet_df.to_csv(index=False).encode("utf-8"),
            f"{title.replace(' ', '_')}.csv",
            "text/csv",
            key=f"dl_{title}",
        )

    categorical_cols, numeric_cols = [], []
    for c in sheet_df.columns:
        if pd.api.types.is_numeric_dtype(sheet_df[c]):
            numeric_cols.append(c)
        else:
            nunique = sheet_df[c].nunique(dropna=True)
            if 1 < nunique <= 30 and nunique < 0.6 * len(sheet_df):
                categorical_cols.append(c)

    if not categorical_cols and not numeric_cols:
        st.info("No chartable columns detected yet — showing raw data only.")
        return

    if numeric_cols:
        st.markdown("#### Numeric fields")
        cols = st.columns(min(2, len(numeric_cols)))
        for i, c in enumerate(numeric_cols):
            with cols[i % len(cols)]:
                fig = px.histogram(sheet_df, x=c, title=c)
                fig.update_layout(showlegend=False)
                st.plotly_chart(fig, use_container_width=True, key=f"num_{title}_{c}")

    if categorical_cols:
        st.markdown("#### Category breakdowns")
        cols = st.columns(2)
        for i, c in enumerate(categorical_cols):
            counts = sheet_df[c].dropna().value_counts().reset_index()
            counts.columns = [c, "Count"]
            with cols[i % 2]:
                fig = px.bar(counts, x="Count", y=c, orientation="h", text="Count", title=c)
                fig.update_layout(yaxis_title=None, showlegend=False)
                st.plotly_chart(fig, use_container_width=True, key=f"cat_{title}_{c}")


def render_ceid_portal():
    st.title("🏫 Riphah CEID Portal")
    st.caption("Click a department to expand its verticals, then click a vertical to load its data")

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
                        key=f"btn_{dept}_{vertical}",
                        use_container_width=True,
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

        source = CEID_DATA_SOURCES.get(active_dept, {}).get(active_vertical)

        if source is None:
            st.info(
                "No data connected yet for this department/vertical. Once you share "
                "the sheet link for it, add it to "
                f"`CEID_DATA_SOURCES[\"{active_dept}\"][\"{active_vertical}\"]` in `app.py`."
            )
        else:
            try:
                csv_url = _ceid_resolve_source(source)
                with st.spinner("Loading data..."):
                    sheet_df = _ceid_load_sheet(csv_url)
                _ceid_render_generic_dashboard(sheet_df, f"{active_vertical} — {active_dept}")
            except Exception as e:
                st.error(
                    "Couldn't load this sheet. Make sure it's shared as "
                    f"'Anyone with the link can view'. Details: {e}"
                )


# ----------------------------------------------------------------------
# TOP-LEVEL TABS — CEID Portal opens first (no scrolling needed)
# ----------------------------------------------------------------------
tab_portal, tab_survey = st.tabs(["🏫 CEID Portal", "🎓 Survey Dashboard"])

with tab_portal:
    render_ceid_portal()

with tab_survey:
    render_survey_dashboard()
