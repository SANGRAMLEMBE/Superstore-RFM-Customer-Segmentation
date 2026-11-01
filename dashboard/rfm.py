"""
RFM customer segmentation
=========================
R - Recency    days from the customer's last order to the snapshot date
F - Frequency  number of unique orders
M - Monetary   total sales

Each measure is scored 1-5 by quintile (20% of customers per score). Customers
are ranked first (method="first") so ties are split evenly and every score has
the same number of customers. Recency is reversed: fewer days = score 5.

RFM_Score = R + F + M (3-15) is then mapped to five segments.
"""

import numpy as np
import pandas as pd

SEGMENTS = ["Champions", "Loyal Customers", "Potential Loyalists", "At Risk", "Low Value"]
SEGMENT_RULES = {"Champions": "13–15", "Loyal Customers": "10–12", "Potential Loyalists": "8–9",
                 "At Risk": "6–7", "Low Value": "3–5"}

SEGMENT_GOAL = {"Champions": "Retain", "Loyal Customers": "Grow value", "Potential Loyalists": "Build habit",
                "At Risk": "Win back", "Low Value": "Low-cost reach"}
SEGMENT_ACTION = {
    "Champions": "VIP / loyalty tier, early access to new products, referral rewards.",
    "Loyal Customers": "Up-sell and cross-sell Technology and Furniture; membership offers.",
    "Potential Loyalists": "Follow-up offer after each order, bundles, free shipping on the next order.",
    "At Risk": "Personalised reminders and a time-limited offer (discount of 20% or less).",
    "Low Value": "Newsletters and seasonal campaigns only; keep spend low.",
}


def quintile(s, reverse=False):
    labels = [5, 4, 3, 2, 1] if reverse else [1, 2, 3, 4, 5]
    return pd.qcut(s.rank(method="first"), 5, labels=labels).astype(int)


def segment(score):
    return np.select([score >= 13, score >= 10, score >= 8, score >= 6], SEGMENTS[:4], SEGMENTS[4])


def compute(df):
    """One row per customer with R, F, M values, 1-5 scores and segment."""
    snapshot = df["Order Date"].max() + pd.Timedelta(days=1)
    r = (df.groupby("Customer ID")
           .agg(**{"Customer Name": ("Customer Name", "first"), "Customer Type": ("Segment", "first"),
                   "Region": ("Region", lambda s: s.mode().iloc[0]),
                   "Last Order": ("Order Date", "max"), "First Order": ("Order Date", "min"),
                   "Frequency": ("Order ID", "nunique"), "Monetary": ("Sales", "sum"),
                   "Profit": ("Profit", "sum")})
           .reset_index())
    r["Recency"] = (snapshot - r["Last Order"]).dt.days
    r["R"] = quintile(r["Recency"], reverse=True)
    r["F"] = quintile(r["Frequency"])
    r["M"] = quintile(r["Monetary"])
    r["RFM_Score"] = r["R"] + r["F"] + r["M"]
    r["RFM_Code"] = r["R"].astype(str) + r["F"].astype(str) + r["M"].astype(str)
    r["RFM_Segment"] = pd.Categorical(segment(r["RFM_Score"]), categories=SEGMENTS, ordered=True)
    cols = ["Customer ID", "Customer Name", "Customer Type", "Region", "Recency", "Frequency", "Monetary",
            "Profit", "R", "F", "M", "RFM_Code", "RFM_Score", "RFM_Segment", "First Order", "Last Order"]
    return r[cols].sort_values(["RFM_Score", "Monetary"], ascending=False).reset_index(drop=True), snapshot


def summary(rfm):
    """Segment profile: size, averages and share of revenue."""
    g = (rfm.groupby("RFM_Segment", observed=True)
            .agg(Customers=("Customer ID", "size"), Recency=("Recency", "mean"),
                 Frequency=("Frequency", "mean"), Monetary=("Monetary", "mean"),
                 Sales=("Monetary", "sum"), Profit=("Profit", "sum"))
            .reindex(SEGMENTS))
    g["Customer_Share"] = g["Customers"] / g["Customers"].sum()
    g["Sales_Share"] = g["Sales"] / g["Sales"].sum()
    return g


def quintile_edges(rfm):
    """Value range behind each 1-5 score, for the method table."""
    rows = []
    for col, score in [("Recency", "R"), ("Frequency", "F"), ("Monetary", "M")]:
        g = rfm.groupby(score)[col].agg(["min", "max"])
        for s in range(5, 0, -1):
            rows.append({"Measure": col, "Score": s, "Min": g.at[s, "min"], "Max": g.at[s, "max"]})
    return pd.DataFrame(rows)
