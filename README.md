# Weekly Funnel Report Generator

A web application that automates the creation of weekly recruiting funnel reports. Upload your pipeline data as CSV/Excel files and get a formatted report — both as an HTML preview and a downloadable Word document.

## What It Does

- **Parses pipeline slate data** — skill groups, stage-wise candidate counts, demands
- **Computes conversion metrics** — OA pass rate, BPS→Onsite, OS→Incline, Offer acceptance
- **Derives business-wise breakdowns** — auto-groups by business (AWS, DAS, GMAC, Accounting)
- **Generates month-on-month glidepath** — tracks delivery vs targets with gap analysis
- **Includes sourcing insights** — CTC analysis, source mix percentages
- **Outputs formatted reports** — HTML preview + Word document download

## Quick Start

### 1. Install dependencies

```bash
cd funnel-report-generator
pip install -r requirements.txt
```

### 2. Run the application

```bash
uvicorn app.main:app --reload --port 8001
```

### 3. Open in browser

Visit **http://localhost:8001** to see the upload form.

### 4. Upload your data

- **Pipeline Slate** (required): CSV/Excel with skill group rows and stage columns
- **Monthly Delivery** (optional): Month-on-month glidepath data
- **CTC Data** (optional): Capture-the-Conversation candidate analysis
- Fill in source mix percentages and support items as needed

### 5. Get your report

- View the HTML preview in the browser
- Click **Download Word Document** to get the .docx file

## Sample Files

The `samples/` folder contains example CSVs matching the expected format:

- `pipeline_slate.csv` — Full pipeline slate with all stage columns
- `monthly_delivery.csv` — Month-on-month delivery glidepath
- `ctc_data.csv` — CTC candidate analysis reasons

## CSV Column Formats

### Pipeline Slate (Required)

| Column | Description |
|--------|-------------|
| Skill Group | e.g. "NA-AWS, FA-II, L5" |
| Demands | Number of requisitions |
| RR Awaiting / RR Incline / RR Reject | Recruiter Review stage |
| OA Scheduled / OA Incline / OA Reject | Online Assessment stage |
| BPS Awaiting / BPS Scheduled / BPS Incline / BPS Reject | Business Phone Screen |
| OS Awaiting / OS Scheduled / OS Incline / OS Reject | Onsite stage |
| Offer Made / Offer Accept / Offer Renege / Onboard | Offer stage |

### Monthly Delivery (Optional)

| Column | Description |
|--------|-------------|
| Month | e.g. "January", "February" |
| No Of Sourcer | Number of sourcers |
| OS Inclines Actuals | Actual OS inclines |
| Onsite Completed | Total onsites completed |
| Offer Accepts Actuals | Actual offer accepts |
| Offer Accept Target | Target offer accepts |

### CTC Data (Optional)

| Column | Description |
|--------|-------------|
| Reason | e.g. "Better Compensation & Benefits" |
| Count | Number of candidates |
| Total | Total candidates captured |

## API Endpoints

| Method | Endpoint | Description |
|--------|----------|-------------|
| GET | `/` | Upload form UI |
| POST | `/api/report/generate` | Generate report from uploaded files |
| GET | `/api/report/download` | Download latest report as Word doc |
| GET | `/api/health` | Health check |
| GET | `/docs` | Swagger API documentation |
