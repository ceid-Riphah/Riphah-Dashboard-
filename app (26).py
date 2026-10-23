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
   Survey (2026) analytics, unchanged.

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

try:
    import gspread
    from google.oauth2.service_account import Credentials as GCredentials
    _GSPREAD_AVAILABLE = True
except ImportError:
    _GSPREAD_AVAILABLE = False

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
# SECTION 1 — SURVEY DASHBOARD DATA (6 faculty survey sheets, combined)
# ========================================================================
# Each faculty has its own "Career Aspirations & Pathways Survey (2026)" response
# sheet (all share the same columns). They are loaded and stacked into one table.
# Sheets must be shared as "Anyone with the link -> Viewer".
SURVEY_SHEETS = {
    "RSCI": "https://docs.google.com/spreadsheets/d/1aV6lIA9uCdfEl0HVlmUvqqjfPLbJJS-3Q-WndpEW_v8/edit",
    "RCST": "https://docs.google.com/spreadsheets/d/1ctPCP_fWt1LQf1V9f0PnDSERvgPWhHuvdYgyu9GReGQ/edit",
    "RSBM": "https://docs.google.com/spreadsheets/d/1HYDrFP_ahtDiudPkZhtOUG_d66ozPyS7uWVWPLWNbh4/edit",
    "RIPS": "https://docs.google.com/spreadsheets/d/1lzgWotptggnLO0MLhvxk_Y6v_S1IdAZrHn1goR2HSDs/edit",
    "RICPP": "https://docs.google.com/spreadsheets/d/1tl_RRvTA_8qgKXzM4fibeqy9HZGe0pLMsY9hdjjijX0/edit",
    "AHS": "https://docs.google.com/spreadsheets/d/1cBXdafJ9t5CNAY7tLPcEDSPUhUZXkcwC-fIdqer97bo/edit",
}
# Older (2025) combined survey, kept alongside the 2026 sheets.
OLD_SURVEY_ID = "16eFMceIi7pgMUgxe_7Hn0ye94RuidGLtrrITNit1liE"
OLD_SURVEY_LABEL = "2025 survey"
SURVEY_TAB_NAMES = ["Form Responses 1", "Form_Responses"]
CAREER_COL = "Which career path best describes your ambition?"


SURVEY_GIDS = {"1aV6lIA9uCdfEl0HVlmUvqqjfPLbJJS-3Q-WndpEW_v8": "1057155562"}


@st.cache_data(ttl=600, show_spinner=False)
def load_one_survey(sheet_id: str):
    """Reads one response sheet by several methods and keeps whichever returns
    the MOST rows. Returns (dataframe, log) where log lists what each method gave."""
    base = f"https://docs.google.com/spreadsheets/d/{sheet_id}"
    attempts = []
    gid = SURVEY_GIDS.get(sheet_id)
    if gid:
        attempts.append(("export gid", f"{base}/export?format=csv&gid={gid}"))
        attempts.append(("gviz gid", _sheet_csv_url(sheet_id, gid=gid)))
    attempts.append(("export first tab", f"{base}/export?format=csv"))
    for t in SURVEY_TAB_NAMES:
        attempts.append((f"gviz tab '{t}'", _sheet_csv_url(sheet_id, sheet_name=t)))
    attempts.append(("gviz gid 0", _sheet_csv_url(sheet_id, gid="0")))
    best, best_name, log = None, None, []
    for name, u in attempts:
        try:
            d = pd.read_csv(u)
            d.columns = [c.strip() for c in d.columns]
            d = d.dropna(axis=1, how="all")
            if CAREER_COL not in d.columns:
                log.append((name, 0, "no survey columns (sheet not readable/shared?)"))
                continue
            d = d[d[CAREER_COL].notna()]
            log.append((name, len(d), "ok"))
            if best is None or len(d) > len(best):
                best, best_name = d, name
        except Exception as e:
            log.append((name, 0, str(e)[:80]))
    if best is None:
        raise ValueError("; ".join(f"{n}: {m}" for n, _, m in log))
    log.append(("USED", len(best), best_name))
    return best, log


def _clean_survey(d: pd.DataFrame) -> pd.DataFrame:
    d = d.copy()
    if "Degree Program" in d.columns:
        d["Degree Program"] = d["Degree Program"].astype(str).str.strip().str.lstrip("-").str.strip()
    # Unique-student key: student ID if it looks numeric, otherwise the email.
    sid = d.get("Your Student ID.", pd.Series("", index=d.index)).astype(str).str.strip()
    email = d.get("Email Address", pd.Series("", index=d.index)).astype(str).str.strip().str.lower()
    d["_student_key"] = sid.where(sid.str.fullmatch(r"\d{4,6}"), "email:" + email)
    return d


@st.cache_data(ttl=600, show_spinner=False)
def load_all_surveys():
    frames, errors, logs = [], {}, {}
    for name, link in SURVEY_SHEETS.items():
        try:
            f, lg = load_one_survey(_extract_sheet_id(link))
            logs[name] = lg
            f.insert(0, "Survey", name)
            frames.append(f)
        except Exception as e:
            errors[name] = str(e)
    try:
        f, lg = load_one_survey(OLD_SURVEY_ID)
        logs[OLD_SURVEY_LABEL] = lg
        f.insert(0, "Survey", OLD_SURVEY_LABEL)
        frames.append(f)
    except Exception as e:
        errors[OLD_SURVEY_LABEL] = str(e)
    if not frames:
        return pd.DataFrame(), errors, logs
    out = _clean_survey(pd.concat(frames, ignore_index=True))
    out["Year"] = out["Survey"].map(lambda x: "2025" if x == OLD_SURVEY_LABEL else "2026")
    return out, errors, logs


with st.spinner("Loading survey responses..."):
    df_all, _survey_errors, _survey_logs = load_all_surveys()

# Responses table (every submission) and de-duplicated table (latest per student).
df = df_all.drop_duplicates(["Year", "_student_key"], keep="last") if not df_all.empty else df_all

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

def _cascade_filter(frame, label, column_name):
    """Multiselect whose options come from the already-filtered frame, so each
    filter only offers values that exist under the selections above it."""
    if frame.empty or column_name not in frame.columns:
        return frame
    options = sorted(frame[column_name].dropna().astype(str).unique().tolist())
    sel = st.sidebar.multiselect(label, options, default=[])
    return frame[frame[column_name].astype(str).isin(sel)] if sel else frame


def apply_survey_sidebar_filters():
    """Left-sidebar filters (shown only on the Survey Dashboard view). They
    cascade: Year -> Faculty -> Department -> Degree Program -> Semester -> Gender."""
    st.sidebar.header("🔎 Survey Filters")
    out = df.copy()
    for label, col in [
        ("Survey year", "Year"),
        ("Faculty", FACULTY_COL),
        ("Department", DEPT_COL),
        ("Degree Program", PROGRAM_COL),
        ("Semester", SEMESTER_COL),
        ("Gender", GENDER_COL),
    ]:
        out = _cascade_filter(out, label, col)
    st.sidebar.markdown("---")
    st.sidebar.caption(f"Showing **{len(out)}** of **{len(df)}** unique students")
    return out


def render_survey_dashboard():
    filtered = apply_survey_sidebar_filters()
    if df_all.empty:
        st.error("Couldn't load any survey sheet. Make sure each is shared as 'Anyone with the link -> Viewer'.")
        for k, v in _survey_errors.items():
            st.caption(f"{k}: {v}")
        return
    for k, v in _survey_errors.items():
        st.warning(f"Couldn't load the {k} survey sheet: {v}")

    with st.expander("📋 Students who filled the survey, by degree program", expanded=True):
        resp = df_all.groupby(["Year", "Survey", PROGRAM_COL]).size().rename("Responses")
        uniq = df.groupby(["Year", "Survey", PROGRAM_COL]).size().rename("Unique students")
        tbl = pd.concat([resp, uniq], axis=1).fillna(0).astype(int).reset_index()
        tbl = tbl.rename(columns={"Survey": "School"}).sort_values(["Year", "School", "Unique students"], ascending=[False, True, False])
        c1, c2 = st.columns(2)
        c1.metric("Total unique students", int(df.shape[0]))
        c2.metric("Total responses (incl. repeats)", int(df_all.shape[0]))
        st.dataframe(tbl, hide_index=True, use_container_width=True)
        by_school = df.groupby("Survey", sort=False).size().rename("Unique students").reset_index()
        src = df_all.groupby("Survey", sort=False).size()
        with st.expander("🔧 Data check (rows read from each Google Sheet)"):
            rows = [(k, m, n, note) for k, lg in _survey_logs.items() for m, n, note in lg]
            st.dataframe(pd.DataFrame(rows, columns=["Sheet", "Method", "Rows", "Note"]), hide_index=True, use_container_width=True)
        st.caption("Rows loaded from each sheet: " + " · ".join(f"{k} {v}" for k, v in src.items()))
        st.caption("By school: " + " · ".join(f"{a} {b}" for a, b in zip(by_school["Survey"], by_school["Unique students"])))
        st.download_button("Download this table (CSV)", tbl.to_csv(index=False), "students_by_degree_program.csv")
    st.title("🎓 Riphah CEID – Career Aspirations & Pathways Survey (2026)")
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
    return d


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


# ========================================================================
# SECTION 3 — UPDATE DATA PORTAL (login + write-back to Google Sheets)
# ========================================================================
# Credentials live in Streamlit's secrets manager, NOT in this file, so they
# never end up in the GitHub repo. In Streamlit Cloud: App settings -> Secrets
# -> paste something like:
#
#   [ceid_logins."Riphah School of Computing and Innovation"]
#   username = "rsci_coordinator"
#   password = "put-a-real-password-here"
#
#   [ceid_logins."Riphah College of Science and Technology"]
#   username = "..."
#   password = "..."
#   # ...one block per faculty...
#
# If no secrets are configured yet, a clearly-labelled demo login is used
# instead so the portal is testable immediately — replace it before real use.
_DEMO_LOGINS = {
    dept: {"username": "demo", "password": "demo"} for dept in CEID_DEPARTMENTS
}


def _get_logins() -> dict:
    if "ceid_logins" in st.secrets:
        return {dept: dict(creds) for dept, creds in st.secrets["ceid_logins"].items()}
    return _DEMO_LOGINS


def _check_login(department: str, username: str, password: str) -> bool:
    logins = _get_logins()
    record = logins.get(department)
    if not record:
        return False
    return username == record.get("username") and password == record.get("password")


_DEMO_ADMIN = {"username": "admin", "password": "admin"}


_DEMO_CEO = {"username": "ceo", "password": "ceo"}


def _get_ceo_login() -> dict:
    if "ceid_ceo" in st.secrets:
        return dict(st.secrets["ceid_ceo"])
    return _DEMO_CEO


def _check_ceo_login(username: str, password: str) -> bool:
    record = _get_ceo_login()
    return username == record.get("username") and password == record.get("password")


def _targets_cumulative_error(df_in):
    """Returns a message if any KPI's targets decrease from one checkpoint to the next."""
    cols = ["Target 30 Sep", "Target 31 Oct", "Target 30 Nov", "Target 31 Dec"]
    for _, row in df_in.iterrows():
        vals = [_parse_num(row.get(c)) for c in cols]
        prev = None
        for c, v in zip(cols, vals):
            if v is None or pd.isna(v):
                continue
            if prev is not None and v < prev:
                return f"Targets must be cumulative (never decrease). Check '{row.get('KPI')}': {c} ({v:g}) is lower than the previous checkpoint ({prev:g})."
            prev = v
    return None


def _get_admin_login() -> dict:
    if "ceid_admin" in st.secrets:
        return dict(st.secrets["ceid_admin"])
    return _DEMO_ADMIN


def _check_admin_login(username: str, password: str) -> bool:
    record = _get_admin_login()
    return username == record.get("username") and password == record.get("password")


@st.cache_resource(show_spinner=False)
def get_gspread_client():
    """Authenticated write client, built from a GCP service account stored
    in Streamlit secrets under [gcp_service_account]. Returns None if not
    configured yet, so the caller can show setup instructions instead of a
    raw crash."""
    if not _GSPREAD_AVAILABLE or "gcp_service_account" not in st.secrets:
        return None
    scopes = ["https://www.googleapis.com/auth/spreadsheets"]
    creds = GCredentials.from_service_account_info(dict(st.secrets["gcp_service_account"]), scopes=scopes)
    return gspread.authorize(creds)


def write_row_data_to_sheet(sheet_id: str, vertical_tab: str, edited_df: pd.DataFrame, include_targets: bool) -> tuple[bool, str]:
    client = get_gspread_client()
    if client is None:
        return False, (
            "Write access isn't configured yet. A Google service account with edit "
            "rights on this spreadsheet needs to be added to Streamlit's secrets as "
            "[gcp_service_account] — see the setup note below."
        )
    try:
        sh = client.open_by_key(sheet_id)
        ws = sh.worksheet(vertical_tab)

        def _clean(v):
            if v is None:
                return ""
            if isinstance(v, float) and pd.isna(v):
                return ""
            return v

        # Columns are always: A=KPI, B-E=Target x4, F=Actual (latest), G=Delivery note.
        # Coordinators only get F:G; admins get the whole row B:G including targets.
        if include_targets:
            cols = ["Target 30 Sep", "Target 31 Oct", "Target 30 Nov", "Target 31 Dec",
                    "Actual (latest)", "Delivery note"]
            start_col = "B"
        else:
            cols = ["Actual (latest)", "Delivery note"]
            start_col = "F"

        values = [[_clean(row.get(c, "")) for c in cols] for _, row in edited_df.iterrows()]
        end_col = chr(ord(start_col) + len(cols) - 1)
        ws.update(range_name=f"{start_col}2:{end_col}{len(values) + 1}", values=values)
        return True, "Saved."
    except Exception as e:
        return False, f"Couldn't save: {e}"


def render_login_panel():
    """Role picker + login forms (coordinator / admin / CEO). Sets session_state."""
    role_choice = st.radio(
        "I am logging in as a...", ["Department Coordinator", "CEID Admin", "CEO"], horizontal=True,
    )

    if role_choice == "Department Coordinator":
        st.caption("Log in with your department, username, and password to update your faculty's actuals.")
        with st.form("update_login_form"):
            dept = st.selectbox("Department", CEID_DEPARTMENTS)
            username = st.text_input("Username")
            password = st.text_input("Password", type="password")
            submitted = st.form_submit_button("Log in")
        if submitted:
            if _check_login(dept, username, password):
                st.session_state["update_portal_role"] = "coordinator"
                st.session_state["update_portal_dept"] = dept
                st.rerun()
            else:
                st.error("Username, password, or department didn't match.")
        if "ceid_logins" not in st.secrets:
            st.info(
                "No real logins configured yet — using a demo login for testing: "
                "**username: demo, password: demo** (works for any department). "
                "Set up real credentials in Streamlit secrets before giving this "
                "to actual coordinators — see the note near the top of `app.py`."
            )
    elif role_choice == "CEO":
        st.caption("The CEO can pick any department and set cumulative targets as well as actuals.")
        with st.form("update_ceo_login_form"):
            username = st.text_input("CEO username")
            password = st.text_input("CEO password", type="password")
            submitted = st.form_submit_button("Log in")
        if submitted:
            if _check_ceo_login(username, password):
                st.session_state["update_portal_role"] = "ceo"
                st.rerun()
            else:
                st.error("Username or password didn't match.")
        if "ceid_ceo" not in st.secrets:
            st.info("No real CEO login configured yet — demo login: **username: ceo, password: ceo**. Add a [ceid_ceo] block to Streamlit secrets.")
    else:
        st.caption("Admins can pick any department and edit both targets and actuals.")
        with st.form("update_admin_login_form"):
            username = st.text_input("Admin username")
            password = st.text_input("Admin password", type="password")
            submitted = st.form_submit_button("Log in")
        if submitted:
            if _check_admin_login(username, password):
                st.session_state["update_portal_role"] = "admin"
                st.rerun()
            else:
                st.error("Username or password didn't match.")
        if "ceid_admin" not in st.secrets:
            st.info(
                "No real admin login configured yet — using a demo login for testing: "
                "**username: admin, password: admin**. Set up a real [ceid_admin] "
                "block in Streamlit secrets before giving this to a real admin."
            )


def render_update_portal():
    st.title("✏️ Update KPI Data")

    if "update_portal_role" not in st.session_state:
        render_login_panel()
        return

    role = st.session_state["update_portal_role"]
    is_admin = role in ("admin", "ceo")

    top_col, logout_col = st.columns([5, 1])
    with top_col:
        if is_admin:
            st.subheader("Logged in as: CEO" if role == "ceo" else "Logged in as: CEID Admin")
        else:
            st.subheader(f"Logged in as: {st.session_state['update_portal_dept']}")
    with logout_col:
        st.write("")
        if st.button("Log out"):
            st.session_state.pop("update_portal_role", None)
            st.session_state.pop("update_portal_dept", None)
            st.rerun()

    if is_admin:
        department = st.selectbox("Department", CEID_DEPARTMENTS, key="admin_dept_select")
    else:
        department = st.session_state["update_portal_dept"]

    sheet_link = FACULTY_SHEETS.get(department)
    if not sheet_link:
        st.warning(f"No KPI sheet connected yet for {department}. Nothing to update.")
        return

    sheet_id = _extract_sheet_id(sheet_link)
    vertical_display = st.selectbox("Vertical", CEID_VERTICALS, key="update_vertical")
    vertical_key = VERTICAL_DISPLAY_TO_KEY[vertical_display]

    sheet_df, load_error = load_vertical_sheet_with_fallback(sheet_id, vertical_key, vertical_display)
    if sheet_df is None:
        st.error(f"Couldn't load this vertical's data. Details: {load_error}")
        return

    if is_admin:
        st.caption("Edit targets, actuals, and delivery notes below, then save. Targets are cumulative: each checkpoint must be equal to or higher than the one before.")
        locked_cols = ["KPI"]
    else:
        st.caption("Edit the 'Actual (latest)' and 'Delivery note' columns below, then save.")
        locked_cols = ["KPI", "Target 30 Sep", "Target 31 Oct", "Target 30 Nov", "Target 31 Dec"]

    editable_cols = ["KPI", "Target 30 Sep", "Target 31 Oct", "Target 30 Nov", "Target 31 Dec",
                      "Actual (latest)", "Delivery note"]
    display_cols = [c for c in editable_cols if c in sheet_df.columns]
    edited = st.data_editor(
        sheet_df[display_cols],
        disabled=[c for c in display_cols if c in locked_cols],
        use_container_width=True,
        hide_index=True,
        key=f"editor_{department}_{vertical_key}_{role}",
    )

    if st.button("💾 Save changes", type="primary"):
        if is_admin:
            err = _targets_cumulative_error(edited)
            if err:
                st.error(err)
                return
        ok, message = write_row_data_to_sheet(sheet_id, vertical_key, edited, include_targets=is_admin)
        if ok:
            st.cache_data.clear()
            st.success(message)
        else:
            st.error(message)


# ----------------------------------------------------------------------
# CALENDAR MODULE — coordinators add events per vertical; everyone can view
# ----------------------------------------------------------------------
import calendar as _calendar
import uuid
from datetime import datetime as _dt, timedelta
from html import escape as _esc

# One shared Google Sheet ("CEID Events Calendar"). The service account needs Editor access.
EVENTS_SHEET_ID = "1_7OBpshh5qKU8d4Gw_rcrd_IuxS7ihzg0xlbhsrTEZ8"
EVENT_COLS = ["Event ID", "Start date", "End date", "Faculty", "Vertical", "Event title",
              "Type", "Venue", "Description", "Status", "Added by", "Added at"]
EVENT_TYPES = ["Session / Workshop", "Seminar / Expert talk", "Industry visit", "Meeting",
               "Competition / Event", "Deadline", "Other"]
EVENT_STATUSES = ["Planned", "Done", "Cancelled"]
_FAC_COLORS = ["#2563eb", "#16a34a", "#d97706", "#9333ea", "#dc2626", "#0891b2"]


def _fac_short(name: str) -> str:
    return "".join(w[0] for w in name.split() if w[0].isupper()) or name[:4]


def _fac_color(name: str) -> str:
    try:
        return _FAC_COLORS[CEID_DEPARTMENTS.index(name) % len(_FAC_COLORS)]
    except ValueError:
        return "#64748b"


@st.cache_data(ttl=60, show_spinner=False)
def load_events() -> pd.DataFrame:
    df_ev = None
    client = get_gspread_client()
    if client is not None:
        try:
            rows = client.open_by_key(EVENTS_SHEET_ID).sheet1.get_all_records()
            df_ev = pd.DataFrame(rows)
        except Exception:
            df_ev = None
    if df_ev is None:
        try:
            df_ev = pd.read_csv(f"https://docs.google.com/spreadsheets/d/{EVENTS_SHEET_ID}/export?format=csv")
        except Exception:
            df_ev = pd.DataFrame()
    for c in EVENT_COLS:
        if c not in df_ev.columns:
            df_ev[c] = ""
    df_ev = df_ev[EVENT_COLS].fillna("")
    df_ev["_start"] = pd.to_datetime(df_ev["Start date"], errors="coerce").dt.date
    df_ev["_end"] = pd.to_datetime(df_ev["End date"], errors="coerce").dt.date
    df_ev["_end"] = df_ev["_end"].where(df_ev["_end"].notna(), df_ev["_start"])
    return df_ev[df_ev["_start"].notna()].reset_index(drop=True)


def _events_ws():
    client = get_gspread_client()
    if client is None:
        raise RuntimeError("Write access isn't configured (service account missing in secrets).")
    return client.open_by_key(EVENTS_SHEET_ID).sheet1


def add_event(rec: dict) -> tuple[bool, str]:
    try:
        ws = _events_ws()
        if not ws.row_values(1):
            ws.update(range_name="A1", values=[EVENT_COLS])
        ws.append_row([rec.get(c, "") for c in EVENT_COLS], value_input_option="RAW")
        st.cache_data.clear()
        return True, "Event saved."
    except Exception as e:
        return False, f"Couldn't save: {e}"


def update_event_status(event_id: str, status: str) -> tuple[bool, str]:
    try:
        ws = _events_ws()
        cell = ws.find(event_id, in_column=1)
        if cell is None:
            return False, "Event not found."
        ws.update_cell(cell.row, EVENT_COLS.index("Status") + 1, status)
        st.cache_data.clear()
        return True, "Status updated."
    except Exception as e:
        return False, f"Couldn't update: {e}"


def delete_event(event_id: str) -> tuple[bool, str]:
    try:
        ws = _events_ws()
        cell = ws.find(event_id, in_column=1)
        if cell is None:
            return False, "Event not found."
        ws.delete_rows(cell.row)
        st.cache_data.clear()
        return True, "Event deleted."
    except Exception as e:
        return False, f"Couldn't delete: {e}"


def _month_grid_html(year: int, month: int, ev: pd.DataFrame) -> str:
    today = date.today()
    by_day = {}
    first, last = date(year, month, 1), date(year, month, _calendar.monthrange(year, month)[1])
    for _, r in ev.iterrows():
        d = max(r["_start"], first)
        while d <= min(r["_end"], last):
            by_day.setdefault(d, []).append(r)
            d += timedelta(days=1)
    head = "".join(f"<th style='padding:6px;text-align:left;opacity:.7'>{d}</th>"
                   for d in ["Mon", "Tue", "Wed", "Thu", "Fri", "Sat", "Sun"])
    rows_html = ""
    for week in _calendar.Calendar(firstweekday=0).monthdayscalendar(year, month):
        tds = ""
        for day in week:
            if day == 0:
                tds += "<td style='border:1px solid rgba(128,128,128,.25);height:96px;background:rgba(128,128,128,.06)'></td>"
                continue
            d = date(year, month, day)
            items = by_day.get(d, [])
            chips = ""
            for r in items[:3]:
                col = _fac_color(r["Faculty"])
                dim = "text-decoration:line-through;opacity:.5;" if r["Status"] == "Cancelled" else ""
                tick = "✓ " if r["Status"] == "Done" else ""
                chips += (f"<div title='{_esc(str(r['Faculty']))} · {_esc(str(r['Vertical']))} · {_esc(str(r['Event title']))}' "
                          f"style='border-left:3px solid {col};background:{col}22;border-radius:3px;margin-top:2px;"
                          f"padding:1px 4px;font-size:11px;line-height:1.25;overflow:hidden;white-space:nowrap;text-overflow:ellipsis;{dim}'>"
                          f"{tick}<b>{_esc(_fac_short(str(r['Faculty'])))}</b> {_esc(str(r['Event title']))}</div>")
            if len(items) > 3:
                chips += f"<div style='font-size:11px;opacity:.7;margin-top:2px'>+{len(items) - 3} more</div>"
            num_style = "font-weight:700;color:#2563eb;" if d == today else "opacity:.8;"
            tds += (f"<td style='border:1px solid rgba(128,128,128,.25);vertical-align:top;height:96px;padding:4px;width:14.28%'>"
                    f"<div style='font-size:12px;{num_style}'>{day}</div>{chips}</td>")
        rows_html += f"<tr>{tds}</tr>"
    return (f"<table style='width:100%;border-collapse:collapse;table-layout:fixed'><thead><tr>{head}</tr></thead>"
            f"<tbody>{rows_html}</tbody></table>")


def render_calendar():
    st.title("📅 CEID Events Calendar")
    st.caption("Coordinators add the events planned for their verticals; the CEO and everyone else can see all "
               "departments in one calendar. Log in below to add or manage events.")

    events = load_events()

    # --- month + filters -------------------------------------------------
    today = date.today()
    c1, c2, c3, c4 = st.columns([1, 1, 2, 2])
    year = c1.selectbox("Year", [2026, 2027], index=0 if today.year <= 2026 else 1)
    month = c2.selectbox("Month", list(range(1, 13)), index=today.month - 1,
                         format_func=lambda m: _calendar.month_name[m])
    fac_sel = c3.multiselect("Department", CEID_DEPARTMENTS, default=[], placeholder="All departments")
    vert_sel = c4.multiselect("Vertical", CEID_VERTICALS, default=[], placeholder="All verticals")

    first, last = date(year, month, 1), date(year, month, _calendar.monthrange(year, month)[1])
    view_ev = events[(events["_start"] <= last) & (events["_end"] >= first)] if not events.empty else events
    if fac_sel:
        view_ev = view_ev[view_ev["Faculty"].isin(fac_sel)]
    if vert_sel:
        view_ev = view_ev[view_ev["Vertical"].isin(vert_sel)]

    m1, m2, m3, m4 = st.columns(4)
    m1.metric("Events this month", len(view_ev))
    m2.metric("Planned", int((view_ev["Status"] == "Planned").sum()) if len(view_ev) else 0)
    m3.metric("Done", int((view_ev["Status"] == "Done").sum()) if len(view_ev) else 0)
    m4.metric("Departments with events", view_ev["Faculty"].nunique() if len(view_ev) else 0)

    st.markdown(_month_grid_html(year, month, view_ev), unsafe_allow_html=True)
    legend = " &nbsp; ".join(
        f"<span style='border-left:3px solid {_fac_color(f)};padding-left:4px;font-size:12px'>"
        f"<b>{_esc(_fac_short(f))}</b> {_esc(f)}</span>" for f in CEID_DEPARTMENTS)
    st.markdown(legend, unsafe_allow_html=True)

    # --- agenda ------------------------------------------------------------
    st.subheader("Agenda")
    if view_ev.empty:
        st.info("No events for this month and filters yet.")
    else:
        agenda = view_ev.sort_values("_start")[
            ["Start date", "End date", "Faculty", "Vertical", "Event title", "Type", "Venue", "Status", "Description", "Added by"]]
        st.dataframe(agenda, hide_index=True, use_container_width=True)
        st.download_button("Download agenda (CSV)", agenda.to_csv(index=False),
                           f"ceid_events_{year}_{month:02d}.csv")

    # --- add / manage ------------------------------------------------------
    st.divider()
    st.subheader("➕ Add or manage events")
    if "update_portal_role" not in st.session_state:
        st.caption("Log in as a coordinator (your department only), or as Admin / CEO (any department).")
        render_login_panel()
        return

    role = st.session_state["update_portal_role"]
    who = {"admin": "CEID Admin", "ceo": "CEO"}.get(role, st.session_state.get("update_portal_dept", ""))
    lc, rc = st.columns([5, 1])
    lc.markdown(f"Logged in as **{who}**")
    if rc.button("Log out", key="cal_logout"):
        st.session_state.pop("update_portal_role", None)
        st.session_state.pop("update_portal_dept", None)
        st.rerun()

    can_any = role in ("admin", "ceo")
    if can_any:
        faculty = st.selectbox("Department", CEID_DEPARTMENTS, key="cal_fac")
    else:
        faculty = st.session_state["update_portal_dept"]
        st.write(f"Department: **{faculty}**")

    with st.form("add_event_form", clear_on_submit=True):
        f1, f2 = st.columns(2)
        vertical = f1.selectbox("Vertical", CEID_VERTICALS)
        etype = f2.selectbox("Type", EVENT_TYPES)
        title = st.text_input("Event title")
        d1, d2, d3 = st.columns(3)
        start = d1.date_input("Start date", value=max(today, first) if today <= last else first)
        end = d2.date_input("End date (same as start for a one-day event)", value=max(today, first) if today <= last else first)
        status = d3.selectbox("Status", EVENT_STATUSES)
        venue = st.text_input("Venue / link (optional)")
        desc = st.text_area("Description (optional)", height=80)
        submitted = st.form_submit_button("Add event", type="primary")
    if submitted:
        if not title.strip():
            st.error("Please enter an event title.")
        elif end < start:
            st.error("End date can't be before the start date.")
        else:
            ok, msg = add_event({
                "Event ID": uuid.uuid4().hex[:8], "Start date": start.isoformat(), "End date": end.isoformat(),
                "Faculty": faculty, "Vertical": vertical, "Event title": title.strip(), "Type": etype,
                "Venue": venue.strip(), "Description": desc.strip(), "Status": status, "Added by": who,
                "Added at": _dt.now().strftime("%Y-%m-%d %H:%M"),
            })
            (st.success if ok else st.error)(msg)
            if ok:
                st.rerun()

    mine = events if can_any else events[events["Faculty"] == faculty]
    if can_any:
        mine = mine[mine["Faculty"] == faculty]
    if not mine.empty:
        with st.expander(f"Manage existing events — {faculty}", expanded=False):
            mine = mine.sort_values("_start")
            labels = {r["Event ID"]: f"{r['Start date']} · {r['Vertical']} · {r['Event title']} [{r['Status']}]"
                      for _, r in mine.iterrows()}
            pick = st.selectbox("Event", list(labels.keys()), format_func=lambda k: labels[k], key="cal_pick")
            b1, b2, b3 = st.columns([2, 1, 1])
            new_status = b1.selectbox("Set status", EVENT_STATUSES, key="cal_newstatus")
            if b2.button("Update status"):
                ok, msg = update_event_status(pick, new_status)
                (st.success if ok else st.error)(msg)
                if ok:
                    st.rerun()
            if b3.button("Delete event"):
                ok, msg = delete_event(pick)
                (st.success if ok else st.error)(msg)
                if ok:
                    st.rerun()


# ----------------------------------------------------------------------
# TOP-LEVEL TABS
# ----------------------------------------------------------------------
VIEWS = ["🏫 CEID Portal", "📊 CEO Overview", "✏️ Update Data", "📅 Calendar", "🎓 Survey Dashboard"]
view = st.radio("View", VIEWS, horizontal=True, label_visibility="collapsed", key="main_view")
st.divider()

if view == VIEWS[0]:
    render_ceid_portal()
elif view == VIEWS[1]:
    render_ceo_overview()
elif view == VIEWS[2]:
    render_update_portal()
elif view == VIEWS[3]:
    render_calendar()
else:
    render_survey_dashboard()
