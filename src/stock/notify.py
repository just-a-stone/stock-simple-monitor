from __future__ import annotations

import json
import os
import sys
import urllib.parse
import urllib.request
from datetime import datetime
from typing import Any, Dict, Optional


MAX_TITLE_LEN = 32
MAX_DESP_BYTES = 32 * 1024  # 32KB in bytes


def _get_sendkey(explicit: Optional[str] = None) -> Optional[str]:
    """Resolve Server酱 Turbo SendKey.

    Precedence: explicit arg -> env `SCT_SENDKEY` -> env `SERVERCHAN_SENDKEY`.
    """
    if explicit:
        return explicit.strip()
    return os.getenv("SCT_SENDKEY") or os.getenv("SERVERCHAN_SENDKEY")


def _truncate_title(title: str) -> str:
    t = (title or "").replace("\n", " ").strip()
    return t if len(t) <= MAX_TITLE_LEN else (t[: MAX_TITLE_LEN - 1] + "…")


def _truncate_desp(desp: Optional[str]) -> str:
    if not desp:
        return ""
    # Server酱按字节计，保守用 UTF-8 编码长度截断
    raw = desp.strip()
    b = raw.encode("utf-8")
    if len(b) <= MAX_DESP_BYTES:
        return raw
    # Truncate to MAX_DESP_BYTES without breaking multi-byte chars
    cut = b[:MAX_DESP_BYTES]
    while True:
        try:
            return cut.decode("utf-8")
        except UnicodeDecodeError:
            cut = cut[:-1]


def send_wechat(
    title: str,
    desp: Optional[str] = None,
    *,
    sendkey: Optional[str] = None,
    timeout: int = 10,
) -> Dict[str, Any]:
    """Send a message via Server酱 Turbo API.

    Returns a dict with keys: ok(bool), status(int|None), body(dict|str|None), error(str|None).
    Does not raise on HTTP errors; surfaces error in return payload.
    """
    key = _get_sendkey(sendkey)
    if not key:
        return {"ok": False, "status": None, "body": None, "error": "Missing SCT_SENDKEY"}

    safe_title = _truncate_title(title)
    safe_desp = _truncate_desp(desp)

    base = f"https://sctapi.ftqq.com/{key}.send"
    params = {"title": safe_title, "desp": safe_desp}
    url = base + "?" + urllib.parse.urlencode(params)

    req = urllib.request.Request(url, method="GET")
    try:
        with urllib.request.urlopen(req, timeout=timeout) as resp:  # nosec B310
            status = getattr(resp, "status", None) or resp.getcode()
            body_bytes = resp.read()
            body_text = body_bytes.decode("utf-8", errors="replace")
            try:
                body_json = json.loads(body_text)
            except Exception:
                body_json = body_text
            ok = bool(status and 200 <= status < 300)
            return {"ok": ok, "status": status, "body": body_json, "error": None}
    except Exception as exc:  # pragma: no cover
        return {"ok": False, "status": None, "body": None, "error": str(exc)}


def notify_monthly_thresholds(
    monthly_df,
    *,
    sendkey: Optional[str] = None,
    threshold_ipo: int = 10,
    threshold_funds: float = 100.0,
) -> Optional[Dict[str, Any]]:
    """If current month exceeds thresholds, push a notification.

    Expects DataFrame with columns: month (YYYY-MM), ipo_count, funds_sum.
    Returns the send_wechat result if sent; otherwise None.
    """
    if monthly_df is None or getattr(monthly_df, "empty", True):
        return None

    now_month = datetime.now().strftime("%Y-%m")
    cur = monthly_df[monthly_df["month"] == now_month]
    if cur.empty:
        return None

    row = cur.iloc[0]
    ipo_count = int(row.get("ipo_count") or 0)
    funds_val = row.get("funds_sum")
    try:
        funds_sum = float(funds_val) if funds_val is not None else 0.0
    except Exception:
        funds_sum = 0.0

    trigger_ipo = ipo_count > threshold_ipo
    trigger_funds = funds_sum > threshold_funds
    if not (trigger_ipo or trigger_funds):
        return None

    title = f"{now_month} IPO提示"
    reasons = []
    if trigger_ipo:
        reasons.append(f"数量>{threshold_ipo}")
    if trigger_funds:
        reasons.append(f"募资>{threshold_funds}")
    reason_str = ", ".join(reasons)

    desp_lines = [
        f"- 月份: {now_month}",
        f"- 上市家数: {ipo_count}",
        f"- 募集资金合计(亿元): {funds_sum:.2f}",
        f"- 触发条件: {reason_str}",
    ]
    desp = "\n".join(desp_lines)

    return send_wechat(title=title, desp=desp, sendkey=sendkey)

