# Riphah CEID Career Survey Dashboard

A Streamlit dashboard for the "Riphah CEID – Career Aspirations & Pathways
Survey (2025)" Google Sheet responses.

## 1. Run it locally (optional, to preview)
```bash
pip install -r requirements.txt
streamlit run app.py
```

## 2. Put it on GitHub
1. Go to https://github.com/new and create a new repository (e.g. `ceid-career-dashboard`).
2. Upload `app.py`, `requirements.txt`, and this `README.md` to the repo
   (use the "Add file → Upload files" button on GitHub, or `git push` if you use Git locally).

## 3. Deploy for free on Streamlit Community Cloud
1. Go to https://share.streamlit.io and sign in with your GitHub account.
2. Click **"New app"**.
3. Select your repository, branch (`main`), and set the main file path to `app.py`.
4. Click **Deploy**. Streamlit will install `requirements.txt` and launch the app.
5. You'll get a public URL like `https://your-app-name.streamlit.app` to share.

## Notes
- The app reads live data straight from the Google Sheet's public CSV export link,
  so it always reflects the latest survey responses — no manual re-upload needed.
- The sheet must stay shared as **"Anyone with the link can view"** for the CSV
  export URL to work. If you switch tabs in the sheet, update `gid=0` in `CSV_URL`
  inside `app.py` to match the tab you want (visible in the sheet's URL when that
  tab is open).
