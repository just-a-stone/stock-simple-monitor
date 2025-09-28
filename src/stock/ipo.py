import os
import sys
from datetime import date, datetime, timedelta
from typing import Optional, Tuple

import pandas as pd


def _resolve_dates(
    start: Optional[str] = None,
    end: Optional[str] = None,
    today: Optional[date] = None,
) -> Tuple[str, str]:
    t = today or date.today()
    if end is None:
        end = t.strftime("%Y%m%d")
    if start is None:
        # Avoid date.replace() leap-day pitfalls by subtracting ~5 years in days
        five_years_ago = t - timedelta(days=1827)
        start = five_years_ago.strftime("%Y%m%d")
    return start, end


def _build_event_date(df: pd.DataFrame) -> pd.Series:
    """Row-wise choose the best available date among issue_date, ipo_date, list_date."""
    cols = [c for c in ("issue_date", "ipo_date", "list_date") if c in df.columns]
    if not cols:
        return pd.Series(pd.NaT, index=df.index)
    ser = None
    for c in cols:
        col = df[c].astype(str).str.replace("-", "", regex=False)
        col = pd.to_datetime(col, format="%Y%m%d", errors="coerce")
        ser = col if ser is None else ser.combine_first(col)
    return ser


def _iter_ranges(start: date, end: date, days: int = 93):
    cur = start
    while cur <= end:
        nxt = min(cur + timedelta(days=days), end)
        yield cur.strftime("%Y%m%d"), nxt.strftime("%Y%m%d")
        cur = nxt + timedelta(days=1)


def fetch_new_shares(token: str, start: Optional[str] = None, end: Optional[str] = None) -> pd.DataFrame:
    """Fetch new share (IPO) data from TuShare within [start, end].

    - Dates are strings in YYYYMMDD
    - Requires a valid TuShare Pro `token`
    """
    # Import here to avoid import cost if not used
    try:
        import tushare as ts  # type: ignore
    except Exception as exc:  # pragma: no cover
        raise RuntimeError(
            "Failed to import tushare. Ensure dependency is installed."
        ) from exc

    
    pro = ts.pro_api(token)
    # First attempt: single window
    try:    
        df = pro.new_share()
        return df
    except Exception as exc:  # pragma: no cover
        print(f"[stock] TuShare API error: {exc}")
        return pd.DataFrame()


def aggregate_monthly(df: pd.DataFrame) -> pd.DataFrame:
    """Aggregate IPO count and funds by month.

    Columns expected from TuShare new_share:
    - date column: one of ['issue_date', 'ipo_date'] as YYYYMMDD
    - 'funds' (募集资金, 亿元) if available
    - 'amount' (发行数量, 万股) optional fallback
    """
    if df.empty:
        return pd.DataFrame(columns=["month", "ipo_count", "issue_amount_sum", "funds_sum"]) 

    # Determine event date from available columns and build month
    df = df.copy()
    df["event_date"] = _build_event_date(df)
    df = df.dropna(subset=["event_date"]).reset_index(drop=True)
    df["month"] = df["event_date"].dt.to_period("M").astype(str)
    

    # Prepare metrics
    has_funds = "funds" in df.columns
    has_amount = "amount" in df.columns

    if has_amount:
        df["amount"] = pd.to_numeric(df["amount"], errors="coerce")
    if has_funds:
        df["funds"] = pd.to_numeric(df["funds"], errors="coerce")

    agg_kwargs = {"ipo_count": ("month", "size")}
    if has_amount:
        agg_kwargs["issue_amount_sum"] = ("amount", "sum")
    if has_funds:
        agg_kwargs["funds_sum"] = ("funds", "sum")

    grouped = df.groupby("month").agg(**agg_kwargs).reset_index()
    if "issue_amount_sum" not in grouped.columns:
        grouped["issue_amount_sum"] = pd.NA
    if "funds_sum" not in grouped.columns:
        grouped["funds_sum"] = pd.NA

    grouped = grouped.sort_values("month").reset_index(drop=True)
    return grouped


def save_csv(df: pd.DataFrame, path: str) -> None:
    dirpath = os.path.dirname(path)
    if dirpath:
        os.makedirs(dirpath, exist_ok=True)
    df.to_csv(path, index=False)


def run_once(
    token: str,
    start: Optional[str],
    end: Optional[str],
    raw_out: str,
    monthly_out: str,
) -> pd.DataFrame:
    df = fetch_new_shares(token, start, end)
    if df.empty:
        print("[stock] No IPO data returned for the given range.")
        # still write empty files for consistency
        save_csv(df, raw_out)
        monthly = aggregate_monthly(df)
        save_csv(monthly, monthly_out)
        return monthly
    # Normalize dates and apply explicit start/end filter to ensure range accuracy
    df_norm = df.copy()
    df_norm["event_date"] = _build_event_date(df_norm)
    df_norm = df_norm.dropna(subset=["event_date"]).reset_index(drop=True)
    if start:
        s = pd.to_datetime(str(start).replace("-", ""), format="%Y%m%d", errors="coerce")
        if not pd.isna(s):
            df_norm = df_norm[df_norm["event_date"] >= s]
    if end:
        e = pd.to_datetime(str(end).replace("-", ""), format="%Y%m%d", errors="coerce")
        if not pd.isna(e):
            df_norm = df_norm[df_norm["event_date"] <= e]

    save_csv(df_norm, raw_out)
    monthly = aggregate_monthly(df_norm)
    save_csv(monthly, monthly_out)
    # Range diagnostics
    if not df_norm.empty:
        min_dt = df_norm["event_date"].min()
        max_dt = df_norm["event_date"].max()
        print(f"[stock] Data window: {min_dt.date()} -> {max_dt.date()} (rows={len(df_norm)})")
        # If requested window is much wider than returned, hint about API limits
        try:
            s_req, e_req = _resolve_dates(start, end)
            s_req_dt = datetime.strptime(s_req, "%Y%m%d").date()
            e_req_dt = datetime.strptime(e_req, "%Y%m%d").date()
            if (e_req_dt - s_req_dt).days - (max_dt.date() - min_dt.date()).days > 365:
                print("[stock] Warning: Returned range is narrower than requested; this may be due to TuShare API window or token permission limits.")
        except Exception:
            pass
    return monthly
