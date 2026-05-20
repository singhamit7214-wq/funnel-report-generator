# Weekly Funnel Report Generator

Upload your weekly tracker Excel and auto-generate the full recruiting funnel report.

## Features

- **Auto-parses** raw candidate data from your Base Sheet
- **Computes** all stage counts, conversion metrics, business breakdowns
- **Monthly glidepath** from OS Incline Date / Offer Accept Date columns
- **Source mix** from Channel Mix column
- **Downloads** formatted Word document
- **Always online** via Streamlit Cloud

## How to Use

1. Open the app link
2. Upload your weekly tracker Excel (.xlsx) in the sidebar
3. View the full report with metrics, tables, and charts
4. Click "Download Word Report" to get the .docx file

## Deployment (Streamlit Cloud)

This app is deployed on Streamlit Cloud for free.

## Local Development

```bash
pip install -r requirements.txt
streamlit run streamlit_app.py
```
