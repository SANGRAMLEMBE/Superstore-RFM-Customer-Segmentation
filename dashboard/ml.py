"""
Machine-learning models
=======================
1. K-Means clustering (unsupervised)
   Groups customers on log-scaled, standardised Recency, Frequency and
   Monetary value. k = 4 is chosen with the elbow (inertia) and silhouette
   score, and the clusters are compared with the rule-based RFM segments
   (Adjusted Rand Index + cross-table).

2. Loss-making order prediction (supervised classification)
   Predicts whether an order line will make a loss (Profit < 0) from what is
   known when the order is placed: discount, sales, quantity, product
   category / sub-category, region, customer type and ship mode. Logistic
   Regression, a Decision Tree and a Random Forest are trained on 70% of the
   lines and tested on the other 30%, against a simple "discount > 20%" rule.

3. Churn check
   Predicting "no order in the next 6 months" from RFM-style features was
   tested too. Cross-validated ROC-AUC is about 0.5 (no better than chance),
   so the dashboard reports the result instead of using the model.
"""

import numpy as np
import pandas as pd
from sklearn.cluster import KMeans
from sklearn.compose import ColumnTransformer
from sklearn.ensemble import RandomForestClassifier
from sklearn.inspection import permutation_importance
from sklearn.linear_model import LogisticRegression
from sklearn.metrics import (accuracy_score, adjusted_rand_score, confusion_matrix, f1_score, precision_score,
                             recall_score, roc_auc_score, roc_curve, silhouette_score)
from sklearn.model_selection import StratifiedKFold, cross_val_score, train_test_split
from sklearn.pipeline import make_pipeline
from sklearn.preprocessing import OneHotEncoder, StandardScaler
from sklearn.tree import DecisionTreeClassifier

SEED = 42

# ---------------------------------------------------------------------------
# 1. K-Means
# ---------------------------------------------------------------------------
K_RANGE = range(2, 9)
K = 4
CLUSTER_NAMES = ["Top Spenders", "Recent Buyers", "Slipping Away", "Lost / Low Value"]


def rfm_matrix(rfm):
    """log1p tames the long right tail of Frequency and Monetary; scaling puts R, F, M on equal footing."""
    x = np.log1p(rfm[["Recency", "Frequency", "Monetary"]].to_numpy(float))
    return StandardScaler().fit_transform(x)


def kmeans_scan(rfm):
    x = rfm_matrix(rfm)
    rows = []
    for k in K_RANGE:
        km = KMeans(n_clusters=k, n_init=10, random_state=SEED).fit(x)
        rows.append({"k": k, "Inertia": km.inertia_, "Silhouette": silhouette_score(x, km.labels_)})
    return pd.DataFrame(rows)


def kmeans_fit(rfm, k=K):
    """Cluster per customer, a profile per cluster and agreement with the RFM segments.

    Names follow the cluster averages: highest spend -> Top Spenders; of the rest,
    most recent -> Recent Buyers, least recent -> Lost / Low Value, the remaining
    one -> Slipping Away."""
    km = KMeans(n_clusters=k, n_init=10, random_state=SEED).fit(rfm_matrix(rfm))
    out = rfm.assign(Cluster=km.labels_)
    prof = out.groupby("Cluster").agg(Customers=("Customer ID", "size"), Recency=("Recency", "mean"),
                                      Frequency=("Frequency", "mean"), Monetary=("Monetary", "mean"),
                                      Sales=("Monetary", "sum"))
    top = prof["Monetary"].idxmax()
    rest = prof.drop(index=top)
    recent, lost = rest["Recency"].idxmin(), rest["Recency"].idxmax()
    names = {top: CLUSTER_NAMES[0], recent: CLUSTER_NAMES[1], lost: CLUSTER_NAMES[3]}
    names.update({c: CLUSTER_NAMES[2] for c in prof.index if c not in names})
    out["Cluster"] = pd.Categorical(out["Cluster"].map(names), categories=CLUSTER_NAMES, ordered=True)
    prof = prof.rename(index=names).reindex(CLUSTER_NAMES)
    prof["Sales_Share"] = prof["Sales"] / prof["Sales"].sum()
    ari = adjusted_rand_score(out["RFM_Segment"].astype(str), out["Cluster"].astype(str))
    return out, prof, ari


# ---------------------------------------------------------------------------
# 2. Loss-making order prediction
# ---------------------------------------------------------------------------
NUMERIC = ["Discount", "Sales", "Quantity"]
CATEGORICAL = ["Category", "Sub-Category", "Region", "Segment", "Ship Mode"]
FEATURE_LABEL = {"Discount": "Discount", "Sales": "Sales value", "Quantity": "Quantity",
                 "Category": "Category", "Sub-Category": "Sub-category", "Region": "Region",
                 "Segment": "Customer type", "Ship Mode": "Ship mode"}


def _prep(scale):
    num = StandardScaler() if scale else "passthrough"
    return ColumnTransformer([("num", num, NUMERIC),
                              ("cat", OneHotEncoder(handle_unknown="ignore"), CATEGORICAL)])


MODELS = {
    "Logistic Regression": lambda: make_pipeline(_prep(True), LogisticRegression(max_iter=2000)),
    "Decision Tree": lambda: make_pipeline(_prep(False), DecisionTreeClassifier(
        max_depth=10, min_samples_leaf=10, random_state=SEED)),
    "Random Forest": lambda: make_pipeline(_prep(False), RandomForestClassifier(
        n_estimators=150, max_depth=8, min_samples_leaf=5, random_state=SEED, n_jobs=-1)),
}
RULE = "Rule: discount > 20%"


def loss_dataset(orders):
    return orders[NUMERIC + CATEGORICAL].copy(), (orders["Profit"] < 0).astype(int).rename("Loss")


def _scores(y, pred, prob):
    return {"Accuracy": accuracy_score(y, pred), "Precision": precision_score(y, pred),
            "Recall": recall_score(y, pred), "F1": f1_score(y, pred),
            "ROC_AUC": roc_auc_score(y, prob) if prob is not None else np.nan}


def train_loss_models(x, y):
    """Fit every model on a stratified 70/30 split; return test metrics, ROC curves,
    confusion matrices, fitted models and the split sizes."""
    x_tr, x_te, y_tr, y_te = train_test_split(x, y, test_size=0.3, stratify=y, random_state=SEED)
    rows, curves, cms, fitted = {}, {}, {}, {}
    rule = (x_te["Discount"] > 0.2).astype(int)
    rows[RULE] = _scores(y_te, rule, None)
    cms[RULE] = confusion_matrix(y_te, rule)
    for name, make in MODELS.items():
        m = make().fit(x_tr, y_tr)
        prob = m.predict_proba(x_te)[:, 1]
        pred = (prob >= 0.5).astype(int)
        rows[name] = _scores(y_te, pred, prob)
        curves[name] = roc_curve(y_te, prob)[:2]
        cms[name] = confusion_matrix(y_te, pred)
        fitted[name] = m
    metrics = pd.DataFrame.from_dict(rows, orient="index")
    return metrics, curves, cms, fitted, {"train": len(x_tr), "test": len(x_te), "x_test": x_te, "y_test": y_te}


def feature_importance(model, x_test, y_test):
    """Permutation importance on the test set: drop in ROC-AUC when one input column is shuffled."""
    r = permutation_importance(model, x_test, y_test, scoring="roc_auc", n_repeats=5, random_state=SEED, n_jobs=-1)
    return pd.Series(r.importances_mean, index=x_test.columns).sort_values(ascending=False)


# ---------------------------------------------------------------------------
# 3. Churn check
# ---------------------------------------------------------------------------
CHURN_CUTOFF = pd.Timestamp("2017-06-30")
CHURN_HORIZON_DAYS = 183


def churn_check(orders):
    """5-fold cross-validated ROC-AUC for predicting 'no order in the next 6 months'."""
    d = orders[orders["Order Date"] <= CHURN_CUTOFF]
    g = d.groupby("Customer ID")
    x = pd.DataFrame({"Recency": (CHURN_CUTOFF - g["Order Date"].max()).dt.days,
                      "Frequency": g["Order ID"].nunique(), "Monetary": g["Sales"].sum(),
                      "Tenure": (CHURN_CUTOFF - g["Order Date"].min()).dt.days,
                      "Avg_Discount": g["Discount"].mean(), "Profit": g["Profit"].sum()})
    end = CHURN_CUTOFF + pd.Timedelta(days=CHURN_HORIZON_DAYS)
    future = orders[(orders["Order Date"] > CHURN_CUTOFF) & (orders["Order Date"] <= end)]["Customer ID"].unique()
    y = (~x.index.isin(future)).astype(int)
    rf = RandomForestClassifier(n_estimators=150, max_depth=4, min_samples_leaf=5, class_weight="balanced",
                                random_state=SEED, n_jobs=-1)
    auc = cross_val_score(rf, x, y, cv=StratifiedKFold(5, shuffle=True, random_state=SEED), scoring="roc_auc")
    return {"customers": len(y), "churn_rate": float(y.mean()), "auc": float(auc.mean())}
