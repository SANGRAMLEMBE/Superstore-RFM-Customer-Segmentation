"""
Superstore Sales & RFM Customer Segmentation dashboard
======================================================
Run from the project root:   python -m streamlit run dashboard/app.py
or double-click run_dashboard.bat                ->  http://localhost:8501

Pages
  Overview            KPIs, sales by category / region / customer type, monthly trend, data
  Sales & Products    trend explorer, year-on-year, sub-category sales and profit, discounts, top products
  RFM Segmentation    method, segment sizes and revenue, R x F grid, customer scatter, customer list
  Data Quality        cleaning log, column profile, check against the original file
  Insights & Actions  findings with evidence, marketing action per segment
"""

import html
import re
from pathlib import Path

import pandas as pd
import streamlit as st

import charts as ch
import rfm as rf
from preprocessing import clean, compare_with_reference, read_raw

ROOT = Path(__file__).resolve().parent.parent
DATA = ROOT / "Superstore_raw.csv"            # raw file with duplicates, blanks and text errors
REFERENCE = ROOT / "Sample - Superstore.csv"  # original file, used to verify the cleaning

st.set_page_config(page_title="Superstore RFM Dashboard", page_icon=":material/insights:",
                   layout="wide", initial_sidebar_state="expanded")

st.markdown("""
<style>
.block-container {padding-top: 4.2rem; padding-bottom: 2rem; max-width: 1500px;}
div[class*="st-key-card-"] {background: #FFFFFF; border-radius: 0.6rem; box-shadow: 0 1px 2px rgba(16,24,40,.05);}
[data-testid="stMetric"] {background: #FFFFFF; box-shadow: 0 1px 2px rgba(16,24,40,.05);}
[data-testid="stMetricValue"] {color: #0B3C49;}
.page-title {font-size: 1.75rem; font-weight: 700; color: #0B3C49; line-height: 1.2;}
.page-sub {color: #6B7780; margin: 0.15rem 0 0.4rem;}
.card-title {font-weight: 650; font-size: 1.02rem; color: #0B3C49;}
.card-note {font-size: 0.85rem; color: #6B7780; margin-top: 0.05rem;}
.brand {font-size: 1.25rem; font-weight: 700; color: #0B3C49;}
.brand-sub {color: #6B7780; font-size: 0.85rem; margin-bottom: 0.4rem;}
.big {font-size: 2.1rem; font-weight: 700; color: #0B3C49; line-height: 1.1;}
.big-sub {color: #6B7780; font-size: 0.85rem; margin-bottom: 0.5rem;}
table.nice {width: 100%; border-collapse: collapse; font-size: 0.9rem;}
table.nice th {text-align: left; color: #6B7780; font-weight: 600; border-bottom: 1px solid #DDE3E6; padding: 6px 8px;}
table.nice td {border-bottom: 1px solid #EEF2F4; padding: 7px 8px; vertical-align: top; color: #1F2933;}
.pill {display: inline-block; padding: 1px 9px; border-radius: 999px; font-size: 0.8rem; font-weight: 600; white-space: nowrap;}
.pill-Pass {background: #E2F2EC; color: #1C6B4F;}
.pill-Fixed {background: #E3EEF7; color: #1D5A82;}
.pill-Flagged {background: #FBEFD9; color: #8A5A10;}
.pill-Added {background: #ECEFF1; color: #4A5560;}
.dot {display: inline-block; width: 10px; height: 10px; border-radius: 50%; margin-right: 6px; vertical-align: baseline;}
.step {border-left: 3px solid #0E6E78; padding: 0.2rem 0 0.2rem 0.7rem; height: 100%;}
.step-n {color: #0E6E78; font-weight: 700; font-size: 0.8rem; letter-spacing: 0.04em;}
.step-t {font-weight: 650; color: #0B3C49; margin: 0.1rem 0 0.2rem;}
.step-d {font-size: 0.88rem; color: #1F2933;}
</style>
""", unsafe_allow_html=True)


# ---------------------------------------------------------------------------
# Data
# ---------------------------------------------------------------------------
@st.cache_data
def load(mtime):   # mtime in the cache key -> reloads when the CSV changes
    raw = read_raw(DATA)
    res = clean(raw)
    customers, snapshot = rf.compute(res.df)
    return raw, res, customers, snapshot


raw, res, customers, SNAPSHOT = load(DATA.stat().st_mtime)
base = res.df
SEG_SUMMARY = rf.summary(customers)

DESCRIPTIONS = {
    "Row ID": "Line-item key (one row per product in an order)",
    "Order ID": "Order number; one order can have several lines",
    "Order Date": "Date the order was placed",
    "Ship Date": "Date the order was shipped",
    "Ship Mode": "Standard / Second / First Class, Same Day",
    "Customer ID": "Customer key, used for RFM",
    "Customer Name": "Customer name",
    "Segment": "Customer type: Consumer, Corporate, Home Office",
    "Country": "Always United States",
    "City": "Delivery city",
    "State": "Delivery state",
    "Postal Code": "Delivery postal code",
    "Region": "West, East, Central, South",
    "Product ID": "Product key",
    "Category": "Furniture, Office Supplies, Technology",
    "Sub-Category": "17 product groups (Phones, Chairs, Binders, …)",
    "Product Name": "Product description",
    "Sales": "Revenue of the line ($)",
    "Quantity": "Units sold",
    "Discount": "Discount given (0.2 = 20%)",
    "Profit": "Profit of the line ($, can be negative)",
    "Year": "Derived: year of Order Date",
    "Month": "Derived: month of Order Date",
    "Ship Days": "Derived: Ship Date − Order Date",
    "Profit Margin": "Derived: Profit ÷ Sales",
    "Discount Band": "Derived: No discount, 1–20%, 21–40%, over 40%",
}


# ---------------------------------------------------------------------------
# UI helpers
# ---------------------------------------------------------------------------
def card(title, note=None, key=None):
    box = st.container(border=True, key=key or "card-" + re.sub(r"[^a-z0-9]+", "-", title.lower()).strip("-"))
    head = f"<div class='card-title'>{title}</div>"
    if note:
        head += f"<div class='card-note'>{note}</div>"
    box.markdown(head, unsafe_allow_html=True)
    return box


def show(fig, key=None, **kw):
    fig.update_layout(paper_bgcolor="white", plot_bgcolor="white")   # Streamlit otherwise paints the app background
    return st.plotly_chart(fig, theme=None, config=ch.PLOT_CONFIG, key=key, **kw)


def seg_html(s):
    return f"<span class='dot' style='background:{ch.SEG_COLOR[s]}'></span>{s}"


def html_table(df, pills=(), raw_html=()):
    head = "".join(f"<th>{html.escape(str(c))}</th>" for c in df.columns)
    body = []
    for _, r in df.iterrows():
        cells = []
        for c in df.columns:
            v = r[c]
            if c in pills:
                v = f"<span class='pill pill-{v}'>{html.escape(str(v))}</span>"
            elif c not in raw_html:
                v = html.escape(str(v))
            cells.append(f"<td>{v}</td>")
        body.append("<tr>" + "".join(cells) + "</tr>")
    st.markdown(f"<table class='nice'><thead><tr>{head}</tr></thead><tbody>{''.join(body)}</tbody></table>",
                unsafe_allow_html=True)


def big(number, sub):
    st.markdown(f"<div class='big'>{number}</div><div class='big-sub'>{sub}</div>", unsafe_allow_html=True)


def text(s):
    """Markdown with literal dollar signs (two $ in one line would otherwise render as LaTeX)."""
    st.markdown(s.replace("$", r"\$"))


def pct(v):
    return f"{v:.0%}"


# ---------------------------------------------------------------------------
# Sidebar filters
# ---------------------------------------------------------------------------
FILTER_KEYS = ["f_year", "f_region", "f_cat", "f_type"]
YEARS = sorted(base["Year"].unique().tolist())


def reset_filters():
    for k in FILTER_KEYS:
        st.session_state.pop(k, None)


def sidebar(d):
    sb = st.sidebar
    sb.markdown("<div class='brand'>Superstore Analytics</div>"
                "<div class='brand-sub'>Sales &amp; RFM customer segmentation</div>", unsafe_allow_html=True)
    years = sb.pills("Year", YEARS, selection_mode="multi", default=YEARS, key="f_year")
    regions = sb.multiselect("Region", sorted(d["Region"].unique()), key="f_region", placeholder="All regions")
    cats = sb.multiselect("Category", sorted(d["Category"].unique()), key="f_cat", placeholder="All categories")
    types = sb.multiselect("Customer type", sorted(d["Segment"].unique()), key="f_type", placeholder="All types")
    sb.button("Reset filters", icon=":material/restart_alt:", on_click=reset_filters, width="stretch")

    years = years or YEARS
    m = d["Year"].isin(years)
    active = []
    if set(years) != set(YEARS):
        active.append("Year: " + ", ".join(str(y) for y in sorted(years)))
    for col, sel, name in [("Region", regions, "Region"), ("Category", cats, "Category"),
                           ("Segment", types, "Customer type")]:
        if sel:
            m &= d[col].isin(sel)
            active.append(f"{name}: " + ", ".join(sel))

    sb.divider()
    sb.markdown(f"**{int(m.sum()):,}** of {len(d):,} order lines selected")
    sb.caption("Filters apply to Overview and Sales & Products. RFM scores are always computed on all "
               f"{len(customers)} customers, so the segments stay the same as in the report.")
    return d[m].reset_index(drop=True), active


df, ACTIVE = sidebar(base)


def header(title, subtitle, scoped=True):
    st.markdown(f"<div class='page-title'>{title}</div><div class='page-sub'>{subtitle}</div>",
                unsafe_allow_html=True)
    if not scoped:
        return
    with st.container(horizontal=True, gap="small"):
        if not ACTIVE:
            st.badge(f"All {len(base):,} order lines · 2014–2017", icon=":material/filter_alt_off:", color="gray")
        else:
            st.badge(f"{len(df):,} of {len(base):,} order lines", icon=":material/filter_alt:", color="blue")
            for a in ACTIVE:
                st.badge(a, color="gray")


def guard():
    if df.empty:
        st.warning("No orders match the current filters. Widen them in the sidebar or press **Reset filters**.",
                   icon=":material/filter_alt_off:")
        st.stop()


def kpis(d):
    sales, profit, orders = d["Sales"].sum(), d["Profit"].sum(), d["Order ID"].nunique()
    return sales, profit, orders, d["Customer ID"].nunique(), d["Quantity"].sum()


# ---------------------------------------------------------------------------
# Page 1 - Overview
# ---------------------------------------------------------------------------
def overview():
    header("Sales Overview",
           f"{len(base):,} order lines · {base['Order ID'].nunique():,} orders · "
           f"{base['Customer ID'].nunique()} customers · source: {DATA.name} (cleaned)")
    guard()
    filtered = len(df) < len(base)
    sales, profit, orders, custs, qty = kpis(df)
    all_sales = base["Sales"].sum()
    items = [
        ("Total sales", ch.money(sales), f"{sales / all_sales:.0%} of all" if filtered else None, "Sum of Sales"),
        ("Total profit", ch.money(profit), None, "Sum of Profit"),
        ("Profit margin", pct(profit / sales), None, "Profit ÷ Sales"),
        ("Orders", f"{orders:,}", None, "Unique Order IDs"),
        ("Customers", f"{custs:,}", None, "Unique Customer IDs"),
        ("Avg order value", ch.money(sales / orders), None, "Sales ÷ orders"),
    ]
    for c, (lab, val, delta, hlp) in zip(st.columns(6), items):
        c.metric(lab, val, delta, delta_color="off", border=True, help=hlp, delta_arrow="off")

    left, right = st.columns(2)
    with left:
        with card("Sales by category", "Label = sales · share of the selection"):
            g = df.groupby("Category")["Sales"].sum().sort_values(ascending=False)
            show(ch.hbar(g.index, g.values, ch.NEUTRAL, [f"{ch.money(v)}  ·  {v / g.sum():.0%}" for v in g],
                         height=200, hover="%{y}: $%{x:,.0f}<extra></extra>"), key="ov_cat")
        with card("Sales by customer type", "Consumer, Corporate and Home Office buyers"):
            g = df.groupby("Segment")["Sales"].sum().sort_values(ascending=False)
            show(ch.hbar(g.index, g.values, ch.NEUTRAL, [f"{ch.money(v)}  ·  {v / g.sum():.0%}" for v in g],
                         height=200, hover="%{y}: $%{x:,.0f}<extra></extra>"), key="ov_type")
    with right:
        with card("Sales by region", "Label = sales (profit margin)"):
            g = df.groupby("Region")[["Sales", "Profit"]].sum().sort_values("Sales", ascending=False)
            show(ch.hbar(g.index, g["Sales"], ch.NEUTRAL,
                         [f"{ch.money(s)}  ({p / s:.0%} margin)" for s, p in zip(g["Sales"], g["Profit"])],
                         height=250, hover="%{y}: $%{x:,.0f}<extra></extra>"), key="ov_region")
        with card("Sales by year", "Label = sales · growth vs the previous year"):
            g = df.groupby("Year")["Sales"].sum()
            growth = g.pct_change()
            text = [ch.money(v) + ("" if pd.isna(gr) else f"  ({gr:+.0%})") for v, gr in zip(g, growth)]
            show(ch.vbar(g.index, g.values, text, height=180, hover="%{x}: $%{y:,.0f}<extra></extra>"),
                 key="ov_year")

    with card("Monthly sales trend", "Total sales per month · hover for values"):
        m = df.groupby("Month")["Sales"].sum()
        show(ch.trend(m, "Sales ($)", ch.money, height=320), key="ov_trend")

    with card("Dataset", "Cleaned order lines for the current selection"):
        t1, t2 = st.tabs(["Data preview", "Data dictionary"])
        with t1:
            st.dataframe(df.drop(columns=["Month"]), hide_index=True, height=340,
                         column_config={"Order Date": st.column_config.DateColumn(format="YYYY-MM-DD"),
                                        "Ship Date": st.column_config.DateColumn(format="YYYY-MM-DD"),
                                        "Sales": st.column_config.NumberColumn(format="$%.2f"),
                                        "Profit": st.column_config.NumberColumn(format="$%.2f"),
                                        "Profit Margin": st.column_config.NumberColumn(format="percent"),
                                        "Discount": st.column_config.NumberColumn(format="percent")})
            st.download_button("Download filtered data (CSV)", df.to_csv(index=False).encode("utf-8"),
                               "superstore_filtered.csv", "text/csv", icon=":material/download:")
        with t2:
            dd = pd.DataFrame({"Column": base.columns,
                               "Type": ["date" if pd.api.types.is_datetime64_any_dtype(base[c]) else
                                        "numeric" if pd.api.types.is_numeric_dtype(base[c]) else "text"
                                        for c in base.columns],
                               "Meaning": [DESCRIPTIONS.get(c, "") for c in base.columns]})
            html_table(dd)


# ---------------------------------------------------------------------------
# Page 2 - Sales and products
# ---------------------------------------------------------------------------
METRICS = {"Sales": ("Sales", "sum", ch.money), "Profit": ("Profit", "sum", ch.money),
           "Orders": ("Order ID", "nunique", lambda v: f"{v:,.0f}"),
           "Quantity": ("Quantity", "sum", lambda v: f"{v:,.0f}")}
FREQ = {"Month": "MS", "Quarter": "QS", "Year": "YS"}


def sales_products():
    header("Sales & Products", "How sales and profit move over time and across products, regions and discounts.")
    guard()

    left, right = st.columns([1.7, 1])
    with left:
        with card("Trend explorer", "Pick a measure and a time grain"):
            c1, c2 = st.columns(2)
            metric = c1.segmented_control("Measure", list(METRICS), default="Sales", required=True, key="sp_metric")
            grain = c2.segmented_control("Time grain", list(FREQ), default="Month", required=True, key="sp_grain")
            col, agg, fmt = METRICS[metric]
            s = df.set_index("Order Date").resample(FREQ[grain])[col].agg(agg)
            show(ch.trend(s, metric, fmt, height=330, prefix="$" if metric in ("Sales", "Profit") else ""),
                 key="sp_trend")
    with right:
        with card("Year on year", "Growth is vs the previous year"):
            y = df.groupby("Year").agg(Sales=("Sales", "sum"), Profit=("Profit", "sum"),
                                       Orders=("Order ID", "nunique"))
            g = y["Sales"].pct_change()
            html_table(pd.DataFrame({
                "Year": y.index.astype(str), "Sales": y["Sales"].map(ch.money),
                "Growth": ["–" if pd.isna(v) else f"{v:+.0%}" for v in g],
                "Profit": y["Profit"].map(ch.money), "Margin": (y["Profit"] / y["Sales"]).map(pct),
                "Orders": y["Orders"].map("{:,}".format)}))
            q = df.assign(Q=df["Order Date"].dt.quarter).groupby("Q")["Sales"].sum()
            st.markdown(f"**Seasonality:** Q4 (Oct–Dec) brings **{q.get(4, 0) / q.sum():.0%}** of sales in the "
                        f"selection; Q1 only {q.get(1, 0) / q.sum():.0%}.")

    left, right = st.columns(2)
    sub = df.groupby("Sub-Category")[["Sales", "Profit"]].sum()
    with left:
        with card("Sales by sub-category", "All 17 sub-categories, largest first"):
            g = sub["Sales"].sort_values(ascending=False)
            show(ch.hbar(g.index, g.values, ch.NEUTRAL, [ch.money(v) for v in g], height=26 * len(g) + 40,
                         hover="%{y}: $%{x:,.0f}<extra></extra>"), key="sp_sub_sales")
    with right:
        with card("Profit by sub-category", "Blue = profit, red = loss"):
            show(ch.profit_bars(sub["Profit"], height=26 * len(sub) + 40), key="sp_sub_profit")

    left, right = st.columns([1.1, 1])
    with left:
        with card("Sales by region and category", "Darker = more sales"):
            t = df.pivot_table(index="Region", columns="Category", values="Sales", aggfunc="sum", fill_value=0)
            t = t.loc[t.sum(axis=1).sort_values(ascending=False).index]
            show(ch.heatmap(t, ch.money, height=260), key="sp_heat")
    with right:
        with card("Profit margin by discount level", "Profit ÷ sales for each discount band"):
            order = ["No discount", "1–20%", "21–40%", "Over 40%"]
            b = df.groupby("Discount Band")[["Sales", "Profit"]].sum().reindex(order).dropna()
            mg = b["Profit"] / b["Sales"]
            show(ch.hbar(mg.index, mg.values * 100, [ch.NEUTRAL if v >= 0 else ch.LOSS for v in mg],
                         [f"{v:.0%}  ({ch.money(s)} sales)" for v, s in zip(mg, b["Sales"])], height=220,
                         hover="%{y}: %{x:.1f}%<extra></extra>"), key="sp_disc")

    with card("Top 10 products by sales"):
        p = (df.groupby(["Product Name", "Category", "Sub-Category"])
               .agg(Sales=("Sales", "sum"), Profit=("Profit", "sum"), Units=("Quantity", "sum"))
               .nlargest(10, "Sales").reset_index())
        html_table(pd.DataFrame({"#": range(1, len(p) + 1), "Product": p["Product Name"],
                                 "Sub-category": p["Sub-Category"], "Sales": p["Sales"].map(ch.money),
                                 "Profit": p["Profit"].map(ch.money), "Units": p["Units"]}))


# ---------------------------------------------------------------------------
# Page 3 - RFM segmentation
# ---------------------------------------------------------------------------
def rfm_page():
    header("RFM Customer Segmentation",
           f"Recency, Frequency and Monetary value for all {len(customers)} customers · snapshot date "
           f"{SNAPSHOT:%d %b %Y} (day after the last order) · sidebar filters don't apply here.", scoped=False)
    s = SEG_SUMMARY
    risk = s.loc[["At Risk", "Low Value"]]
    k = st.columns(5)
    k[0].metric("Customers scored", f"{len(customers)}", border=True)
    k[1].metric("Champions", f"{s.at['Champions', 'Customers']}", f"{s.at['Champions', 'Customer_Share']:.0%} of customers",
                delta_color="off", delta_arrow="off", border=True)
    k[2].metric("Sales from Champions + Loyal", pct(s.loc[["Champions", "Loyal Customers"], "Sales_Share"].sum()),
                f"from {s.loc[['Champions', 'Loyal Customers'], 'Customer_Share'].sum():.0%} of customers",
                delta_color="off", delta_arrow="off", border=True)
    k[3].metric("At Risk + Low Value", f"{int(risk['Customers'].sum())}",
                f"{risk['Sales_Share'].sum():.0%} of sales", delta_color="off", delta_arrow="off", border=True)
    k[4].metric("Median recency", f"{customers['Recency'].median():.0f} days", border=True,
                help="Half of all customers ordered within this many days of the snapshot")

    with card("How the RFM score is built"):
        steps = [("R · RECENCY", "Days since last order", "Snapshot date − last order date. Fewer days = higher score."),
                 ("F · FREQUENCY", "Number of orders", "Unique Order IDs per customer. More orders = higher score."),
                 ("M · MONETARY", "Total sales", "Sum of Sales per customer. More spend = higher score."),
                 ("SCORE", "Quintiles 1–5", "Customers ranked and split into five equal groups of ~159 for each "
                                           "measure."),
                 ("SEGMENT", "R + F + M = 3–15", "13–15 Champions · 10–12 Loyal · 8–9 Potential Loyalists · "
                                                "6–7 At Risk · 3–5 Low Value")]
        for c, (n, t, d) in zip(st.columns(5), steps):
            c.markdown(f"<div class='step'><div class='step-n'>{n}</div><div class='step-t'>{t}</div>"
                       f"<div class='step-d'>{d}</div></div>", unsafe_allow_html=True)
        with st.expander("Value range behind each score"):
            e = rf.quintile_edges(customers)
            e["Range"] = [f"{a:,.0f} – {b:,.0f}" if m != "Monetary" else f"${a:,.0f} – ${b:,.0f}"
                          for a, b, m in zip(e["Min"], e["Max"], e["Measure"])]
            t = e.pivot(index="Score", columns="Measure", values="Range").sort_index(ascending=False)
            t.columns = ["Frequency (orders)", "Monetary (sales)", "Recency (days)"]
            st.dataframe(t[["Recency (days)", "Frequency (orders)", "Monetary (sales)"]])

    left, right = st.columns(2)
    with left:
        with card("Customers by segment", "Number of customers · share of all customers"):
            show(ch.segment_bars(s, "Customers", lambda v: f"{v:.0f}", "Customer_Share"), key="rfm_n")
    with right:
        with card("Sales by segment", "Total sales 2014–2017 · share of all sales"):
            show(ch.segment_bars(s, "Sales", ch.money, "Sales_Share"), key="rfm_sales")

    left, right = st.columns(2)
    with left:
        with card("Distribution of RFM scores", "Colour = segment the score falls in"):
            show(ch.score_distribution(customers), key="rfm_dist")
    with right:
        with card("Recency × Frequency grid", "Customers in each R/F score cell · top right = best customers"):
            show(ch.rf_grid(customers), key="rfm_grid")

    with card("Customer map: recency vs spend", "Each dot is a customer · pick a segment to highlight it"):
        pick = st.segmented_control("Highlight", ["All"] + rf.SEGMENTS, default="All", required=True,
                                    key="rfm_pick")
        show(ch.rfm_scatter(customers, None if pick == "All" else pick), key="rfm_scatter")

    with card("Segment profile and marketing action"):
        html_table(pd.DataFrame({
            "Segment": [seg_html(x) for x in s.index],
            "Score": [rf.SEGMENT_RULES[x] for x in s.index],
            "Customers": [f"{n} ({p:.0%})" for n, p in zip(s["Customers"], s["Customer_Share"])],
            "Avg recency": s["Recency"].map(lambda v: f"{v:.0f} days"),
            "Avg orders": s["Frequency"].map(lambda v: f"{v:.1f}"),
            "Avg sales": s["Monetary"].map(ch.money),
            "Share of sales": s["Sales_Share"].map(pct),
            "Recommended action": [f"{rf.SEGMENT_GOAL[x]}: {rf.SEGMENT_ACTION[x]}" for x in s.index],
        }), raw_html=("Segment",))

    with card("Customer list", "Search and download the scored customers"):
        c1, c2 = st.columns([2, 1])
        segs = c1.multiselect("Segment", rf.SEGMENTS, key="rfm_list_seg", placeholder="All segments")
        name = c2.text_input("Search customer name", key="rfm_list_name")
        t = customers
        if segs:
            t = t[t["RFM_Segment"].isin(segs)]
        if name:
            t = t[t["Customer Name"].str.contains(name, case=False, regex=False)]
        st.dataframe(t, hide_index=True, height=360,
                     column_config={"Monetary": st.column_config.NumberColumn("Monetary ($)", format="$%.0f"),
                                    "Profit": st.column_config.NumberColumn(format="$%.0f"),
                                    "Recency": st.column_config.NumberColumn("Recency (days)"),
                                    "Frequency": st.column_config.NumberColumn("Frequency (orders)"),
                                    "First Order": st.column_config.DateColumn(format="YYYY-MM-DD"),
                                    "Last Order": st.column_config.DateColumn(format="YYYY-MM-DD")})
        st.caption(f"{len(t)} customers shown")
        st.download_button("Download customer RFM table (CSV)", t.to_csv(index=False).encode("utf-8"),
                           "customer_rfm.csv", "text/csv", icon=":material/download:")


# ---------------------------------------------------------------------------
# Page 4 - Data quality
# ---------------------------------------------------------------------------
def data_quality():
    header("Data Preparation & Cleaning",
           f"Every check runs on the raw file ({DATA.name}) before any analysis. "
           "Sidebar filters don't apply on this page.", scoped=False)
    log = res.log
    checks = log[log["Status"] != "Added"]
    n = checks["Status"].value_counts()
    k = st.columns(6)
    k[0].metric("Clean rows", f"{len(base):,}", f"from {len(raw):,} raw", delta_color="off", delta_arrow="off",
                border=True)
    k[1].metric("Duplicates removed", f"{int(raw.duplicated().sum())}", border=True)
    k[2].metric("Blanks recovered", f"{int(raw.isna().sum().sum())}", border=True,
                help="Read back from other rows with the same customer, state, sub-category or order")
    k[3].metric("Text fixes", f"{int(log[log['Stage'] == 'Standardise']['Finding'].str.extract(r'(\d+)')[0].astype(int).sum())}",
                border=True, help="Extra spaces and upper/lower-case variants")
    k[4].metric("Checks run", f"{len(checks)}",
                f"{n.get('Pass', 0)} pass · {n.get('Fixed', 0)} fixed · {n.get('Flagged', 0)} flagged",
                delta_color="off", delta_arrow="off", border=True,
                help="Fixed = problem found and corrected · Flagged = kept on purpose with a reason")
    if REFERENCE.exists():
        diff, missing = compare_with_reference(base, read_raw(REFERENCE))
        k[5].metric("Diff vs original", f"{diff + missing} cells", border=True,
                    help=f"Cleaned data compared cell by cell with {REFERENCE.name}")

    with card("Cleaning log", "What was checked, what was found and what was done, in pipeline order"):
        html_table(log, pills=("Status",))

    left, right = st.columns([1.35, 1])
    with left:
        with card("Column profile (raw file)", f"Types, completeness and ranges for all {raw.shape[1]} columns"):
            st.dataframe(res.profile, hide_index=True, height=420)
    with right:
        with card("Derived columns", "Added for the analysis"):
            html_table(pd.DataFrame([
                ("Year, Month", "From Order Date", "Trends, year-on-year"),
                ("Ship Days", "Ship Date − Order Date", "Delivery check"),
                ("Profit Margin", "Profit ÷ Sales", "Profitability"),
                ("Discount Band", "No discount / 1–20% / 21–40% / over 40%", "Discount impact"),
                ("Recency, Frequency, Monetary", "Per customer (RFM page)", "Segmentation"),
            ], columns=["Column", "How", "Used for"]))
            st.download_button("Download cleaned dataset (CSV)", base.to_csv(index=False).encode("utf-8"),
                               "Superstore_cleaned.csv", "text/csv", icon=":material/download:")


# ---------------------------------------------------------------------------
# Page 5 - Insights and actions
# ---------------------------------------------------------------------------
def insights():
    header("Key Insights & Marketing Actions",
           "Findings from the full dataset (2014–2017, all customers), with the evidence for each.", scoped=False)
    d = base
    s = SEG_SUMMARY
    year = d.groupby("Year")["Sales"].sum()
    cat = d.groupby("Category")["Sales"].sum().sort_values(ascending=False)
    reg = d.groupby("Region")["Sales"].sum().sort_values(ascending=False)
    sub = d.groupby("Sub-Category")["Profit"].sum().sort_values()
    losers = sub[sub < 0]
    band = d.groupby("Discount Band")[["Sales", "Profit"]].sum()
    heavy = band.loc[["21–40%", "Over 40%"]]
    top = ["Champions", "Loyal Customers"]
    risk = ["At Risk", "Low Value"]
    q = d.assign(Q=d["Order Date"].dt.quarter).groupby("Q")["Sales"].sum()

    items = [
        (pct(s.loc[top, "Sales_Share"].sum()), f"of sales from {s.loc[top, 'Customer_Share'].sum():.0%} of customers",
         "A small group of customers drives revenue",
         f"Champions and Loyal Customers ({int(s.loc[top, 'Customers'].sum())} people) bring "
         f"{ch.money(s.loc[top, 'Sales'].sum())}. A Champion spends {ch.money(s.at['Champions', 'Monetary'])} on "
         f"average, {s.at['Champions', 'Monetary'] / s.at['Low Value', 'Monetary']:.0f}× a Low Value customer.",
         ch.segment_bars(s, "Sales", ch.money, "Sales_Share", height=230)),
        (f"{year.iloc[-1] / year.iloc[0] - 1:+.0%}", f"sales growth {year.index[0]} → {year.index[-1]}",
         "Sales are growing, with a strong Q4",
         f"Sales rose from {ch.money(year.iloc[0])} to {ch.money(year.iloc[-1])}. Q4 (Oct–Dec) brings "
         f"{q[4] / q.sum():.0%} of yearly sales, so campaigns should be ready before the holiday season.",
         ch.vbar(year.index, year.values, [ch.money(v) for v in year], height=230,
                 hover="%{x}: $%{y:,.0f}<extra></extra>")),
        (ch.money(cat.iloc[0]), f"{cat.index[0]} sales ({cat.iloc[0] / cat.sum():.0%} of total)",
         f"{cat.index[0]} and the {reg.index[0]} lead",
         f"{cat.index[0]} is the largest category; the {reg.index[0]} ({ch.money(reg.iloc[0])}) and "
         f"{reg.index[1]} ({ch.money(reg.iloc[1])}) are the largest regions, while the {reg.index[-1]} "
         f"is the smallest ({ch.money(reg.iloc[-1])}).",
         ch.hbar(reg.index, reg.values, ch.NEUTRAL, [ch.money(v) for v in reg], height=230,
                 hover="%{y}: $%{x:,.0f}<extra></extra>")),
        (ch.money(heavy["Profit"].sum()), "profit on lines with more than 20% discount",
         "Heavy discounts lose money",
         f"Lines with 21–40% discount run at a {band.at['21–40%', 'Profit'] / band.at['21–40%', 'Sales']:.0%} margin "
         f"and over 40% at {band.at['Over 40%', 'Profit'] / band.at['Over 40%', 'Sales']:.0%}. Retention offers "
         "should stay at 20% or less.",
         ch.hbar(["No discount", "1–20%", "21–40%", "Over 40%"],
                 [(band.at[b, 'Profit'] / band.at[b, 'Sales']) * 100 for b in ["No discount", "1–20%", "21–40%", "Over 40%"]],
                 [ch.NEUTRAL if band.at[b, 'Profit'] >= 0 else ch.LOSS for b in ["No discount", "1–20%", "21–40%", "Over 40%"]],
                 [f"{band.at[b, 'Profit'] / band.at[b, 'Sales']:.0%}" for b in ["No discount", "1–20%", "21–40%", "Over 40%"]],
                 height=230, hover="%{y}: %{x:.1f}%<extra></extra>")),
        (f"{len(losers)}", "sub-categories make a loss: " + ", ".join(losers.index),
         "Some big sellers are unprofitable",
         f"{losers.index[0]} lose {ch.money(-losers.iloc[0])} despite strong sales. Their pricing and discounting "
         "need review before they are pushed in campaigns.",
         ch.profit_bars(pd.concat([sub.head(4), sub.tail(3)]), height=230)),
        (f"{int(s.loc[risk, 'Customers'].sum())}", f"customers At Risk or Low Value ({s.loc[risk, 'Customer_Share'].sum():.0%})",
         "A third of customers are drifting away",
         f"At Risk customers last ordered {s.at['At Risk', 'Recency']:.0f} days ago on average, Low Value "
         f"{s.at['Low Value', 'Recency']:.0f} days. Together they bring only {s.loc[risk, 'Sales_Share'].sum():.0%} of "
         "sales: win back At Risk first, keep Low Value on low-cost channels.",
         ch.segment_bars(s, "Recency", lambda v: f"{v:.0f} days", height=230)),
    ]
    for row in range(0, len(items), 3):
        for c, (i, (num, sub_, title, body, fig)) in zip(st.columns(3), enumerate(items[row:row + 3], start=row + 1)):
            with c:
                with card(f"{i}. {title}", key=f"card-insight-{i}"):
                    big(num, sub_)
                    text(body)
                    show(fig, key=f"ins_{i}")

    with card("Marketing action plan by segment"):
        html_table(pd.DataFrame({
            "Segment": [seg_html(x) for x in s.index],
            "Customers": s["Customers"],
            "Share of sales": s["Sales_Share"].map(pct),
            "Goal": [rf.SEGMENT_GOAL[x] for x in s.index],
            "Action": [rf.SEGMENT_ACTION[x] for x in s.index],
        }), raw_html=("Segment",))

    with card("Next steps"):
        st.markdown(
            "1. **Validate the segments with K-Means clustering** on standardised R, F and M, and compare with the "
            "rule-based segments.\n"
            "2. **Customer lifetime value (CLV)** per segment to size the marketing budget.\n"
            "3. **Track segment movement** each quarter (e.g. Loyal → At Risk) to trigger campaigns early.\n"
            "4. **Add profit to the scoring** so heavily discounted, low-profit customers are not over-rewarded.")


# ---------------------------------------------------------------------------
# Navigation
# ---------------------------------------------------------------------------
pages = [
    st.Page(overview, title="Overview", icon=":material/dashboard:", url_path="overview", default=True),
    st.Page(sales_products, title="Sales & Products", icon=":material/shopping_cart:", url_path="sales"),
    st.Page(rfm_page, title="RFM Segmentation", icon=":material/groups:", url_path="rfm"),
    st.Page(data_quality, title="Data Quality", icon=":material/cleaning_services:", url_path="data-quality"),
    st.Page(insights, title="Insights & Actions", icon=":material/lightbulb:", url_path="insights"),
]
st.navigation(pages, position="top").run()
