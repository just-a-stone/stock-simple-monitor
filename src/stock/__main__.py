import os
import sys
import time
import argparse
from typing import List, Optional, Tuple

from .ipo import run_once
from .notify import notify_monthly_thresholds
from .config import get_env


def _default_paths() -> Tuple[str, str]:
    data_dir = os.path.join(os.getcwd(), "data")
    raw = os.path.join(data_dir, "ipo_raw.csv")
    monthly = os.path.join(data_dir, "ipo_monthly.csv")
    return raw, monthly


def _parse_args(argv: List[str]) -> argparse.Namespace:
    parser = argparse.ArgumentParser(prog="stock", description="Stock utilities")
    sub = parser.add_subparsers(dest="cmd", required=False)

    # ipo command
    ipo = sub.add_parser("ipo", help="Fetch and analyze IPO data")
    ipo.add_argument("mode", choices=["once", "schedule"], nargs="?", default="once")
    # Token will be read from project .env if not provided explicitly
    ipo.add_argument("--token", dest="token", default=None)
    ipo.add_argument("--start", dest="start", default=None, help="YYYYMMDD (default: 5 years ago)")
    ipo.add_argument("--end", dest="end", default=None, help="YYYYMMDD (default: today)")
    raw, monthly = _default_paths()
    ipo.add_argument("--raw-out", dest="raw_out", default=raw)
    ipo.add_argument("--monthly-out", dest="monthly_out", default=monthly)
    ipo.add_argument("--interval-hours", type=int, default=24, help="Schedule interval in hours")
    ipo.add_argument("--at", dest="at", default=None, help="Daily time HH:MM (local) if provided")

    return parser.parse_args(argv)


def _run_schedule(token: str, start: Optional[str], end: Optional[str], raw: str, monthly: str, interval_hours: int, at: Optional[str]) -> int:
    try:
        import schedule
    except Exception as exc:
        print("[stock] Missing 'schedule' dependency:", exc)
        return 2

    def job() -> None:
        print("[stock] Running scheduled IPO fetch/aggregate...")
        try:
            result = run_once(token, start, end, raw, monthly)
            if not result.empty:
                # Show last 3 months quick view
                tail = result.tail(3)
                print(tail.to_string(index=False))
            print("[stock] Done.")
        except Exception as e:
            print("[stock] Error during scheduled run:", e)

    if at:
        schedule.every().day.at(at).do(job)
        print(f"[stock] Scheduled daily at {at} (local time). Press Ctrl+C to stop.")
    else:
        schedule.every(interval_hours).hours.do(job)
        print(f"[stock] Scheduled every {interval_hours} hour(s). Press Ctrl+C to stop.")

    job()  # run once immediately
    try:
        while True:
            schedule.run_pending()
            time.sleep(1)
    except KeyboardInterrupt:
        print("[stock] Stopped.")
        return 0


def main(argv: Optional[List[str]] = None) -> int:
    args = _parse_args(list(sys.argv[1:] if argv is None else argv))
    if args.cmd == "ipo" or args.cmd is None:
        token = args.token or get_env("TUSHARE_TOKEN")
        if not token:
            print("[stock] Please set TUSHARE_TOKEN in project .env or pass --token.")
            return 2
        raw_out = args.raw_out
        monthly_out = args.monthly_out
        if args.mode == "once":
            res = run_once(token, args.start, args.end, raw_out, monthly_out)
            if res.empty:
                print("[stock] No data.")
            else:
                # Print quick monthly summary tail
                print(res.tail(60).to_string(index=False))
                # Push notification if thresholds are exceeded for current month
                notify_result = notify_monthly_thresholds(res)
                if notify_result is None:
                    pass  # No trigger or no data for current month
                else:
                    ok = notify_result.get("ok")
                    status = notify_result.get("status")
                    if ok:
                        print(f"[stock] Notified via Server酱 (status={status}).")
                    else:
                        err = notify_result.get("error")
                        print(f"[stock] Notification failed: status={status}, error={err}")
            return 0
        else:
            return _run_schedule(token, args.start, args.end, raw_out, monthly_out, args.interval_hours, args.at)

    # Default info
    print("stock-simple-monitor is set up. Try 'python -m stock ipo once' or 'stock-simple-monitor ipo once' after installation.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
