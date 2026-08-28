"""
Riphah CEID – Career Aspirations & Pathways Survey (2025) Dashboard
--------------------------------------------------------------------
A Streamlit dashboard that reads responses directly from the public
Google Sheet (CSV export) and visualizes career-path trends,
entrepreneurship interest, freelancing skills, higher-education
plans, and more.

Run locally:
    pip install -r requirements.txt
    streamlit run app.py

Deploy for free on Streamlit Community Cloud:
    1. Push this repo to GitHub (app.py + requirements.txt)
    2. Go to https://share.streamlit.io -> "New app"
    3. Pick your repo/branch, set main file = app.py -> Deploy
"""

import re

import pandas as pd
import plotly.express as px
import streamlit as st

# ----------------------------------------------------------------------
# CONFIG
# ----------------------------------------------------------------------
SHEET_ID = "16eFMceIi7pgMUgxe_7Hn0ye94RuidGLtrrITNit1liE"
SHEET_TAB_NAME = "Form_Responses"  # exact tab name, as seen at the bottom of your sheet
# gid=0 fallback in case the tab-name query doesn't work in your environment.
GID = "0"

# Try (in order): named-tab gviz query -> gid-based gviz query -> gid-based export.
CANDIDATE_URLS = [
    f"https://docs.google.com/spreadsheets/d/{SHEET_ID}/gviz/tq?tqx=out:csv&sheet={SHEET_TAB_NAME}",
    f"https://docs.google.com/spreadsheets/d/{SHEET_ID}/gviz/tq?tqx=out:csv&gid={GID}",
    f"https://docs.google.com/spreadsheets/d/{SHEET_ID}/export?format=csv&gid={GID}",
]

st.set_page_config(
    page_title="Riphah CEID – Career Survey Dashboard",
    page_icon="🎓",
    layout="wide",
)

# ----------------------------------------------------------------------
# DATA LOADING
# ----------------------------------------------------------------------
@st.cache_data(ttl=600)
def load_data(url: str) -> pd.DataFrame:
    df = pd.read_csv(url)
    df.columns = [c.strip() for c in df.columns]
    # Drop fully-empty helper/duplicate columns (K, L, M in the raw sheet)
    df = df.dropna(axis=1, how="all")
    # Drop rows with no real response (blank career-path answer)
    key_col = "Which career path best describes your ambition?"
    if key_col in df.columns:
        df = df[df[key_col].notna()]
    return df


def col(df: pd.DataFrame, name: str):
    """Return a column if it exists, else None (keeps app crash-proof)."""
    return df[name] if name in df.columns else None


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

# ----------------------------------------------------------------------
# SIDEBAR FILTERS
# ----------------------------------------------------------------------
st.sidebar.header("🔎 Filters")


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
st.sidebar.caption(f"Showing **{len(filtered)}** of **{len(df)}** responses")

# ----------------------------------------------------------------------
# HEADER + KPIs
# ----------------------------------------------------------------------
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

# ----------------------------------------------------------------------
# ROW 1: Career Path + Motivation
# ----------------------------------------------------------------------
c1, c2 = st.columns(2)

with c1:
    if CAREER_COL in filtered.columns:
        st.subheader("Career Path Ambitions")
        counts = filtered[CAREER_COL].value_counts().reset_index()
        counts.columns = ["Career Path", "Count"]
        fig = px.bar(
            counts, x="Count", y="Career Path", orientation="h",
            color="Career Path", text="Count",
        )
        fig.update_layout(showlegend=False, yaxis_title=None)
        st.plotly_chart(fig, use_container_width=True)

with c2:
    if MOTIVATION_COL in filtered.columns:
        st.subheader("Primary Motivation")
        counts = filtered[MOTIVATION_COL].value_counts().reset_index()
        counts.columns = ["Motivation", "Count"]
        fig = px.pie(counts, names="Motivation", values="Count", hole=0.4)
        st.plotly_chart(fig, use_container_width=True)

# ----------------------------------------------------------------------
# ROW 2: Confidence distribution + Gender split
# ----------------------------------------------------------------------
c3, c4 = st.columns(2)

with c3:
    if CONFIDENCE_COL in filtered.columns:
        st.subheader("Confidence Level Distribution")
        conf_numeric = pd.to_numeric(filtered[CONFIDENCE_COL], errors="coerce").dropna()
        fig = px.histogram(conf_numeric, nbins=5, labels={"value": "Confidence (1-5)"})
        fig.update_layout(showlegend=False, yaxis_title="Responses")
        st.plotly_chart(fig, use_container_width=True)

with c4:
    if GENDER_COL in filtered.columns:
        st.subheader("Gender Split")
        counts = filtered[GENDER_COL].value_counts().reset_index()
        counts.columns = ["Gender", "Count"]
        fig = px.pie(counts, names="Gender", values="Count", hole=0.4)
        st.plotly_chart(fig, use_container_width=True)

# ----------------------------------------------------------------------
# ROW 3: Semester distribution + Department breakdown
# ----------------------------------------------------------------------
c5, c6 = st.columns(2)

with c5:
    if SEMESTER_COL in filtered.columns:
        st.subheader("Responses by Semester")
        counts = filtered[SEMESTER_COL].value_counts().reset_index()
        counts.columns = ["Semester", "Count"]
        fig = px.bar(counts, x="Semester", y="Count", text="Count")
        st.plotly_chart(fig, use_container_width=True)

with c6:
    if DEPT_COL in filtered.columns:
        st.subheader("Responses by Department")
        counts = filtered[DEPT_COL].value_counts().reset_index()
        counts.columns = ["Department", "Count"]
        fig = px.bar(counts, x="Count", y="Department", orientation="h", text="Count")
        fig.update_layout(yaxis_title=None)
        st.plotly_chart(fig, use_container_width=True)

# ----------------------------------------------------------------------
# ROW 4: Entrepreneurship + Freelancing deep dive (conditional columns)
# ----------------------------------------------------------------------
st.markdown("---")
st.header("🚀 Entrepreneurship & Freelancing Insights")

c7, c8 = st.columns(2)

BIZ_TYPE_COL = "What type of business or venture are you interested in starting?"
with c7:
    if BIZ_TYPE_COL in filtered.columns:
        st.subheader("Business/Venture Interests")
        counts = filtered[BIZ_TYPE_COL].dropna().value_counts().reset_index()
        counts.columns = ["Business Type", "Count"]
        if not counts.empty:
            fig = px.bar(counts, x="Count", y="Business Type", orientation="h", text="Count")
            fig.update_layout(yaxis_title=None)
            st.plotly_chart(fig, use_container_width=True)
        else:
            st.info("No data for the current filter selection.")

FREELANCE_SKILL_COL = "What freelancing skill are you most interested in learning?"
with c8:
    if FREELANCE_SKILL_COL in filtered.columns:
        st.subheader("Freelancing Skills of Interest")
        counts = filtered[FREELANCE_SKILL_COL].dropna().value_counts().reset_index()
        counts.columns = ["Skill", "Count"]
        if not counts.empty:
            fig = px.bar(counts, x="Count", y="Skill", orientation="h", text="Count")
            fig.update_layout(yaxis_title=None)
            st.plotly_chart(fig, use_container_width=True)
        else:
            st.info("No data for the current filter selection.")

# ----------------------------------------------------------------------
# ROW 5: Higher education + Industry/Employment
# ----------------------------------------------------------------------
st.markdown("---")
st.header("🌍 Higher Education & Employment Preferences")

c9, c10 = st.columns(2)

EDU_LEVEL_COL = "What level of higher education are you considering?"
with c9:
    if EDU_LEVEL_COL in filtered.columns:
        st.subheader("Higher Education Level")
        counts = filtered[EDU_LEVEL_COL].dropna().value_counts().reset_index()
        counts.columns = ["Level", "Count"]
        if not counts.empty:
            fig = px.pie(counts, names="Level", values="Count", hole=0.4)
            st.plotly_chart(fig, use_container_width=True)
        else:
            st.info("No data for the current filter selection.")

INDUSTRY_COL = "What industry or field would you like to work in?"
with c10:
    if INDUSTRY_COL in filtered.columns:
        st.subheader("Target Industry / Field")
        counts = filtered[INDUSTRY_COL].dropna().value_counts().reset_index()
        counts.columns = ["Industry", "Count"]
        if not counts.empty:
            fig = px.bar(counts, x="Count", y="Industry", orientation="h", text="Count")
            fig.update_layout(yaxis_title=None)
            st.plotly_chart(fig, use_container_width=True)
        else:
            st.info("No data for the current filter selection.")

# ----------------------------------------------------------------------
# RAW DATA
# ----------------------------------------------------------------------
st.markdown("---")
with st.expander("📄 View filtered raw data"):
    st.dataframe(filtered, use_container_width=True)
    st.download_button(
        "Download filtered data as CSV",
        filtered.to_csv(index=False).encode("utf-8"),
        "filtered_survey_data.csv",
        "text/csv",
    )

# ========================================================================
# CEID PORTAL — Department x Vertical explorer (separate from the survey
# dashboard above). Pick a department on the left, then a vertical; its
# data loads on the right. Wire up sheet links in DATA_SOURCES below.
# ========================================================================
st.markdown("---")
st.markdown("---")
st.title("🏫 Riphah CEID Portal")
st.caption("Browse data by department and vertical")

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
    """Convert any Google Sheets share link into a CSV export URL."""
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


ceid_nav_col, ceid_content_col = st.columns([1, 3], gap="large")

with ceid_nav_col:
    st.markdown("### Department")
    ceid_department = st.radio(
        "Select a department", CEID_DEPARTMENTS, label_visibility="collapsed", key="ceid_dept",
    )
    st.markdown("### Vertical")
    ceid_vertical = st.radio(
        "Select a vertical", CEID_VERTICALS, label_visibility="collapsed", key="ceid_vertical",
    )

with ceid_content_col:
    st.markdown(f"## {ceid_vertical}")
    st.caption(ceid_department)

    ceid_source = CEID_DATA_SOURCES.get(ceid_department, {}).get(ceid_vertical)

    if ceid_source is None:
        st.info(
            "No data connected yet for this department/vertical. Once you share "
            "the sheet link for it, add it to "
            f"`CEID_DATA_SOURCES[\"{ceid_department}\"][\"{ceid_vertical}\"]` in `app.py`."
        )
    else:
        try:
            ceid_csv_url = _ceid_resolve_source(ceid_source)
            with st.spinner("Loading data..."):
                ceid_df = _ceid_load_sheet(ceid_csv_url)
            _ceid_render_generic_dashboard(ceid_df, f"{ceid_vertical} — {ceid_department}")
        except Exception as e:
            st.error(
                "Couldn't load this sheet. Make sure it's shared as "
                f"'Anyone with the link can view'. Details: {e}"
            )
