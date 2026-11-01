"""
Cleaning pipeline for the Sample Superstore dataset
===================================================
Every step records what it checked, what it found and what it did, so the
dashboard can show the full cleaning log.

    clean(raw) -> CleanResult(df, log, profile)

Order matters: standardise text -> drop duplicates -> parse types -> recover
missing values -> validate ranges -> check consistency -> flag outliers ->
add derived columns. Duplicates go first so repeated rows don't count twice
anywhere else.

Missing values are not guessed: in this dataset every customer has one name
and one segment, every state one region, every sub-category one category and
every order one date and ship mode, so a blank cell can be read back from the
other rows that share the same key.
"""

from dataclasses import dataclass

import numpy as np
import pandas as pd

TEXT_COLS = ["Order ID", "Ship Mode", "Customer ID", "Customer Name", "Segment", "Country", "City",
             "State", "Region", "Product ID", "Category", "Sub-Category", "Product Name"]
CATEGORICAL = ["Ship Mode", "Segment", "Region", "Category", "Sub-Category"]   # small fixed sets of values
NUMERIC_COLS = ["Sales", "Quantity", "Discount", "Profit"]
DATE_COLS = ["Order Date", "Ship Date"]
DATE_FORMAT = "%m/%d/%Y"

# (column to fill, key column it depends on, reason shown in the log)
RECOVER = [
    ("Customer ID", "Customer Name", "each customer name belongs to one ID"),
    ("Customer Name", "Customer ID", "each customer ID has one name"),
    ("Segment", "Customer ID", "a customer always has the same segment"),
    ("Region", "State", "each state lies in one region"),
    ("Category", "Sub-Category", "each sub-category belongs to one category"),
    ("Order Date", "Order ID", "all lines of an order share the order date"),
    ("Ship Mode", "Order ID", "all lines of an order share the ship mode"),
]


@dataclass
class CleanResult:
    df: pd.DataFrame          # cleaned data + derived columns
    log: pd.DataFrame         # one row per check
    profile: pd.DataFrame     # per-column profile of the raw file


def read_raw(path):
    return pd.read_csv(path, encoding="cp1252")


def profile(raw):
    rows = []
    for c in raw.columns:
        s = raw[c]
        num = pd.api.types.is_numeric_dtype(s)
        rows.append({
            "Column": c,
            "Type": "numeric" if num else "text",
            "Non-null": int(s.notna().sum()),
            "Missing": int(s.isna().sum()),
            "Unique": int(s.nunique()),
            "Min": f"{s.min():,.2f}" if num else "",
            "Max": f"{s.max():,.2f}" if num else "",
            "Example": str(s.dropna().iloc[0]) if s.notna().any() else "",
        })
    return pd.DataFrame(rows)


def iqr_bounds(s):
    q1, q3 = s.quantile([0.25, 0.75])
    iqr = q3 - q1
    return q1 - 1.5 * iqr, q3 + 1.5 * iqr


def clean(raw: pd.DataFrame) -> CleanResult:
    df = raw.copy()
    log = []

    def step(stage, check, found, action, status):
        log.append({"Stage": stage, "Check": check, "Finding": found, "Action": action, "Status": status})

    # 1 - text standardisation ------------------------------------------------
    changed = 0
    for c in TEXT_COLS:
        cleaned = df[c].astype("string").str.strip()
        changed += int((cleaned != df[c].astype("string")).fillna(False).sum())
        df[c] = cleaned
    step("Standardise", "Leading/trailing spaces in text columns",
         f"{changed} cells with extra spaces", "Trimmed", "Fixed" if changed else "Pass")

    n_case = 0
    examples = []
    for c in CATEGORICAL:
        key = df[c].str.lower()
        canonical = df[c].groupby(key).agg(lambda s: s.mode().iloc[0])   # most common spelling wins
        fixed = df[c].ne(key.map(canonical)) & df[c].notna()
        n_case += int(fixed.sum())
        examples += [f"'{v}' → '{canonical[v.lower()]}'" for v in df.loc[fixed, c].unique()]
        df[c] = key.map(canonical)
    step("Standardise", "Upper/lower-case variants in " + ", ".join(CATEGORICAL),
         f"{n_case} cells" + (": " + ", ".join(examples) if examples else ""),
         "Replaced with the standard spelling" if n_case else "No change needed",
         "Fixed" if n_case else "Pass")

    # 2 - duplicates (checked after trimming, so ' West' and 'West' match) --------
    dup_rows = int(df.duplicated().sum())
    df = df.drop_duplicates().reset_index(drop=True)
    step("Duplicates", "Exact duplicate rows", f"{dup_rows} duplicate rows",
         "Dropped, first copy kept" if dup_rows else "No change needed", "Fixed" if dup_rows else "Pass")
    dup_ids = int(df["Row ID"].duplicated().sum())
    step("Duplicates", "Row ID is unique (primary key)", f"{dup_ids} repeated IDs",
         "Kept first occurrence" if dup_ids else "No change needed", "Fixed" if dup_ids else "Pass")
    df = df.drop_duplicates("Row ID").reset_index(drop=True)
    same_line = int(df.drop(columns="Row ID").duplicated().sum())
    step("Duplicates", "Identical line items with different Row IDs",
         f"{same_line} line(s) repeat another line of the same order",
         "Kept: separate Row ID, so treated as a real second line" if same_line else "No change needed",
         "Flagged" if same_line else "Pass")

    # 3 - data types ------------------------------------------------------------
    bad_num = 0
    for c in NUMERIC_COLS:
        coerced = pd.to_numeric(df[c], errors="coerce")
        bad_num += int((coerced.isna() & df[c].notna()).sum())
        df[c] = coerced
    bad_date = 0
    for c in DATE_COLS:
        parsed = pd.to_datetime(df[c], format=DATE_FORMAT, errors="coerce")
        bad_date += int((parsed.isna() & df[c].notna()).sum())
        df[c] = parsed
    step("Data types", "Sales, Quantity, Discount, Profit are numbers; dates parse as month/day/year",
         f"{bad_num} non-numeric values, {bad_date} unreadable dates",
         "Converted (bad values become missing)" if bad_num or bad_date else "Converted to number / date types",
         "Fixed" if bad_num or bad_date else "Pass")

    # 4 - missing values --------------------------------------------------------
    miss = df.isna().sum()
    total_miss = int(miss.sum())
    step("Missing values", f"Empty cells across {df.shape[1]} columns",
         f"{total_miss} missing cells: " + (", ".join(f"{c} {n}" for c, n in miss.items() if n) or "none"),
         "Recovered column by column (next rows)" if total_miss else "Nothing to fill",
         "Fixed" if total_miss else "Pass")

    for col, key, why in RECOVER:
        gaps = df[col].isna()
        if not gaps.any():
            continue
        lookup = df.dropna(subset=[col, key]).groupby(key)[col].first()
        df.loc[gaps, col] = df.loc[gaps, key].map(lookup)
        left = int(df[col].isna().sum())
        step("Missing values", f"Missing {col}", f"{int(gaps.sum())} cells",
             f"Read from other rows with the same {key} ({why})"
             + (f"; {left} could not be recovered" if left else ""), "Fixed")

    # fallbacks, only used if a key had no other rows
    if df["Order Date"].isna().any():
        days = (df["Ship Date"] - df["Order Date"]).dt.days
        med = days.groupby(df["Ship Mode"]).transform("median")
        n = int(df["Order Date"].isna().sum())
        df["Order Date"] = df["Order Date"].fillna(df["Ship Date"] - pd.to_timedelta(med, unit="D"))
        step("Missing values", "Order Date with no other line in the order", f"{n} cells",
             "Ship Date minus the median shipping days for that ship mode", "Fixed")
    left = df.isna().sum()
    left = left[left > 0]
    if len(left):
        n = int(left.sum())
        df = df.dropna().reset_index(drop=True)
        step("Missing values", "Cells that could not be recovered", f"{n} cells", "Rows dropped", "Fixed")

    # 5 - valid ranges ----------------------------------------------------------
    rules = [("Sales > 0", df["Sales"] <= 0),
             ("Quantity ≥ 1", df["Quantity"] < 1),
             ("Discount between 0 and 1", ~df["Discount"].between(0, 1)),
             ("Ship Date on or after Order Date", df["Ship Date"] < df["Order Date"])]
    bad = {name: int(m.sum()) for name, m in rules}
    n_bad = sum(bad.values())
    step("Validity", "; ".join(bad), f"{n_bad} rows break a rule",
         "No change needed" if not n_bad else "Rows removed", "Pass" if not n_bad else "Fixed")
    if n_bad:
        keep = ~np.logical_or.reduce([m.to_numpy() for _, m in rules])
        df = df[keep].reset_index(drop=True)
    loss = int((df["Profit"] < 0).sum())
    step("Validity", "Negative profit", f"{loss} lines ({loss / len(df):.0%}) sold at a loss",
         "Kept: losses are real (mostly heavy discounts)", "Flagged")

    # 6 - internal consistency ------------------------------------------------
    for key, cols in [("Order ID", ["Order Date", "Customer ID", "Ship Mode"]),
                      ("Customer ID", ["Customer Name", "Segment"]),
                      ("State", ["Region"])]:
        n = int((df.groupby(key)[cols].nunique() > 1).any(axis=1).sum())
        step("Consistency", f"Each {key} has one {', '.join(cols)}", f"{n} conflicts",
             "Confirmed" if not n else "Review manually", "Pass" if not n else "Flagged")
    other = df["Country"].unique().tolist()
    step("Consistency", "Single country", f"Country = {', '.join(other)}",
         "Column kept for completeness; not used in analysis", "Pass")

    # 7 - outliers (IQR rule) ----------------------------------------------------
    parts = []
    for c in ["Sales", "Profit"]:
        lo, hi = iqr_bounds(df[c])
        n = int(((df[c] < lo) | (df[c] > hi)).sum())
        parts.append(f"{c} {n} ({n / len(df):.0%})")
    step("Outliers", "IQR rule (outside Q1 − 1.5·IQR … Q3 + 1.5·IQR) on Sales and Profit",
         "Lines outside the fences: " + ", ".join(parts),
         "Kept and flagged: big orders are real and matter for Monetary value; medians shown alongside means",
         "Flagged")

    # 8 - derived columns -------------------------------------------------------
    df["Year"] = df["Order Date"].dt.year
    df["Month"] = df["Order Date"].dt.to_period("M").dt.to_timestamp()
    df["Ship Days"] = (df["Ship Date"] - df["Order Date"]).dt.days
    df["Profit Margin"] = df["Profit"] / df["Sales"]
    df["Discount Band"] = pd.cut(df["Discount"], [-0.01, 0, 0.2, 0.4, 1],
                                 labels=["No discount", "1–20%", "21–40%", "Over 40%"]).astype(str)
    df["Quantity"] = df["Quantity"].astype(int)
    step("Feature engineering", "Add analysis columns",
         "Year, Month, Ship Days, Profit Margin, Discount Band", "Added", "Added")

    df = df.sort_values("Row ID").reset_index(drop=True)
    return CleanResult(df, pd.DataFrame(log), profile(raw))


def compare_with_reference(clean_df, ref):
    """Count cells that differ from the original Sample Superstore file (same Row IDs).

    Text is compared after trimming: the original itself has trailing spaces in
    16 product names, which the pipeline removes on purpose."""
    ref = ref.set_index("Row ID")
    c = clean_df.set_index("Row ID").reindex(ref.index)
    diff = 0
    for col in ref.columns:
        a, b = ref[col], c[col]
        if col in DATE_COLS:
            a = pd.to_datetime(a, format=DATE_FORMAT)
        if pd.api.types.is_numeric_dtype(a) and not pd.api.types.is_datetime64_any_dtype(a):
            diff += int((~np.isclose(a.to_numpy(float), b.to_numpy(float))).sum())
        else:
            diff += int((a.astype(str).str.strip() != b.astype(str)).sum())
    missing_rows = int(c.isna().all(axis=1).sum())
    return diff, missing_rows
