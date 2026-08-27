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

import pandas as pd
import plotly.express as px
import streamlit as st

# ----------------------------------------------------------------------
# CONFIG
# ----------------------------------------------------------------------
SHEET_ID = "16eFMceIi7pgMUgxe_7Hn0ye94RuidGLtrrITNit1liE"
# gid=0 is the first tab. If your data lives on another tab, change gid.
CSV_URL = f"https://docs.google.com/spreadsheets/d/{SHEET_ID}/export?format=csv&gid=0"

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


with st.spinner("Loading survey responses..."):
    try:
        df = load_data(CSV_URL)
    except Exception as e:
        st.error(
            "Couldn't load the Google Sheet. Make sure it's shared as "
            "'Anyone with the link can view'. Error: " + str(e)
        )
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
