# Customer Segmentation and Sales Analysis Using RFM Analytics

Marketing Analytics project · Module 1: data cleaning, sales analysis, RFM customer segmentation and an
interactive dashboard.

**Team:** Sangram Lembe · Surya S · Manavendra A · Manne Subhash

We analyse the **Sample Superstore** dataset (9,994 order lines, 5,009 orders, 793 customers, 2014–2017),
find where sales and profit come from, score every customer on **Recency, Frequency and Monetary value**,
group them into five segments (Champions, Loyal Customers, Potential Loyalists, At Risk, Low Value) and
recommend a marketing action for each segment. Machine learning checks the segments (K-Means clustering)
and predicts loss-making orders (Logistic Regression, Decision Tree, Random Forest).

## Run the dashboard


```bash
pip install -r requirements.txt
python -m streamlit run dashboard/app.py
```

Run it from the project root so the theme in `.streamlit/config.toml` is used, then open
**http://localhost:8501**. On Windows you can also double-click `run_dashboard.bat`.

### Deploy online (free, on Render)

1. Sign in at **render.com** with GitHub.
2. Click **New → Blueprint**, pick this repository and click **Apply**. Render reads `render.yaml`,
   installs `requirements.txt` and starts the app.
3. After the first build (a few minutes) the app is live at `https://<service-name>.onrender.com`.

The free plan sleeps after 15 minutes without visitors; the first visit after that takes about a minute.
The same start command is in `Procfile` (Heroku, Koyeb) and the Python version in `.python-version`.
On Streamlit Community Cloud, use main file path `dashboard/app.py`.

## What's in this repo

| Path | What it is |
|---|---|
| `dashboard/app.py` | The dashboard: sidebar filters and 6 pages |
| `dashboard/preprocessing.py` | Cleaning pipeline (duplicates, missing values, text fixes, checks, outliers) |
| `dashboard/rfm.py` | RFM calculation, quintile scoring and segment rules |
| `dashboard/ml.py` | K-Means clustering, loss-making order prediction, churn check (scikit-learn) |
| `dashboard/charts.py` | All Plotly charts and the colour theme |
| `Superstore_raw.csv` | Raw data the dashboard loads (10,004 rows, with duplicates, blanks and text errors) |
| `Sample - Superstore.csv` | Original dataset, used to verify the cleaned data (0 differences) |
| `Superstore_RFM_Customer_Segmentation.pptx` | Presentation deck |

## Dashboard pages

1. **Overview**: KPIs, sales by category / region / customer type / year, monthly trend, data preview
2. **Sales & Products**: trend explorer, year-on-year table, sub-category sales and profit, discount impact, top products
3. **RFM Segmentation**: method, segment sizes and sales, R × F grid, customer map, segment actions, customer list
4. **ML Models**: K-Means clusters vs RFM segments, loss-prediction model comparison, what-if predictor, churn check
5. **Data Quality**: cleaning log, column profile, check against the original file
6. **Insights & Actions**: six findings with evidence, marketing plan per segment, next steps

## Machine learning

| Model | Type | Result |
|---|---|---|
| K-Means (k = 4) on log-scaled, standardised R, F, M | Unsupervised clustering | 4 clusters that line up with the RFM segments (silhouette 0.26, ARI 0.26) |
| Logistic Regression, Decision Tree, Random Forest | Supervised classification: will an order line make a loss? | Decision Tree catches 82% of loss lines vs 71% for a "discount > 20%" rule (F1 0.85); discount is the main driver |
| Random Forest churn check | Supervised classification: no order in the next 6 months? | ROC-AUC 0.52 (no better than chance), so not used |

## RFM method

| Measure | Definition | Score |
|---|---|---|
| Recency | Days from the last order to 31 Dec 2017 (day after the last order) | 5 = most recent 20% |
| Frequency | Number of unique orders | 5 = top 20% |
| Monetary | Total sales | 5 = top 20% |

RFM score = R + F + M (3–15): Champions 13–15 · Loyal Customers 10–12 · Potential Loyalists 8–9 ·
At Risk 6–7 · Low Value 3–5.
