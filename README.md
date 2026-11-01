# Customer Segmentation and Sales Analysis Using RFM Analytics

Marketing Analytics project · Module 1: data cleaning, sales analysis, RFM customer segmentation and an
interactive dashboard.

**Team:** Sangram Lembe · Surya S · Manavendra A · Manne Subhash

We analyse the **Sample Superstore** dataset (9,994 order lines, 5,009 orders, 793 customers, 2014–2017),
find where sales and profit come from, score every customer on **Recency, Frequency and Monetary value**,
group them into five segments (Champions, Loyal Customers, Potential Loyalists, At Risk, Low Value) and
recommend a marketing action for each segment.

## Run the dashboard

```bash
pip install -r requirements.txt
python -m streamlit run dashboard/app.py
```

Run it from the project root so the theme in `.streamlit/config.toml` is used, then open
**http://localhost:8501**. On Windows you can also double-click `run_dashboard.bat`.

### Deploy on Streamlit Community Cloud

1. Push this repo to GitHub.
2. Go to **share.streamlit.io**, sign in with GitHub and click **Create app → Deploy a public app from GitHub**.
3. Pick this repository, branch `main`, main file path **`dashboard/app.py`**, then **Deploy**.

The app installs `requirements.txt` and reads the data files from the repo, so no other setup is needed.

## What's in this repo

| Path | What it is |
|---|---|
| `dashboard/app.py` | The dashboard: sidebar filters and 5 pages |
| `dashboard/preprocessing.py` | Cleaning pipeline (duplicates, missing values, text fixes, checks, outliers) |
| `dashboard/rfm.py` | RFM calculation, quintile scoring and segment rules |
| `dashboard/charts.py` | All Plotly charts and the colour theme |
| `Superstore_raw.csv` | Raw data the dashboard loads (10,004 rows, with duplicates, blanks and text errors) |
| `Sample - Superstore.csv` | Original dataset, used to verify the cleaned data (0 differences) |
| `Superstore_RFM_Customer_Segmentation.pptx` | Presentation deck |

## Dashboard pages

1. **Overview**: KPIs, sales by category / region / customer type / year, monthly trend, data preview
2. **Sales & Products**: trend explorer, year-on-year table, sub-category sales and profit, discount impact, top products
3. **RFM Segmentation**: method, segment sizes and sales, R × F grid, customer map, segment actions, customer list
4. **Data Quality**: cleaning log, column profile, check against the original file
5. **Insights & Actions**: six findings with evidence, marketing plan per segment, next steps

## RFM method

| Measure | Definition | Score |
|---|---|---|
| Recency | Days from the last order to 31 Dec 2017 (day after the last order) | 5 = most recent 20% |
| Frequency | Number of unique orders | 5 = top 20% |
| Monetary | Total sales | 5 = top 20% |

RFM score = R + F + M (3–15): Champions 13–15 · Loyal Customers 10–12 · Potential Loyalists 8–9 ·
At Risk 6–7 · Low Value 3–5.
