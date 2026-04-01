"""
backfill_mootdx.py – mootdx 历史数据回填（Level-3）

修复记录
--------
* [BUG-FIX] 换手率字段写入 DB 列名 turnover（原为 turn）
"""

from __future__ import annotations

import argparse
import logging
import sqlite3
import sys
import time
from datetime import date, datetime
from pathlib import Path
from typing import List, Optional

sys.path.insert(0, str(Path(__file__).parent))
from config import (
    DB_PATH,
    DOWNLOAD_START_DATE,
    RATE_LIMIT_DEFAULT,
    get_end_date,
)
from backfill_baostock import (
    AdaptiveRateLimiter,
    Checkpoint,
    _get_conn,
    _safe_float,
    backup_database,
    get_stocks_to_fill,
    with_retry,
)

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S",
)
logger = logging.getLogger("backfill_mootdx")


# ────────────────────────────────────────────────────────────────────────────
# mootdx 工具
# ────────────────────────────────────────────────────────────────────────────
def _market(code: str) -> int:
    """0=深交所，1=上交所"""
    return 1 if code.startswith(("6", "9")) else 0


def _date_to_bars(start_date: str, end_date: str) -> int:
    try:
        d0 = datetime.strptime(start_date, "%Y-%m-%d").date()
        d1 = datetime.strptime(end_date, "%Y-%m-%d").date()
        return min(int((d1 - d0).days * 5 / 7) + 10, 800)
    except Exception:
        return 500


@with_retry()
def _fetch_one_stock_mootdx(client, code: str, start_date: str, end_date: str) -> List[dict]:
    bars = _date_to_bars(start_date, end_date)
    df = client.bars(symbol=code, frequency=9, market=_market(code), offset=0, count=bars)
    if df is None or df.empty:
        return []

    df = df.reset_index(drop=True)
    rename = {"datetime": "trade_date", "date": "trade_date", "vol": "volume"}
    df = df.rename(columns={c: rename.get(c, c) for c in df.columns})

    if "trade_date" in df.columns:
        df["trade_date"] = df["trade_date"].astype(str).str[:10]

    df = df[(df["trade_date"] >= start_date) & (df["trade_date"] <= end_date)]

    # 计算涨跌幅和换手率（mootdx 不提供）
    df = df.sort_values("trade_date")
    if "pct_change" not in df.columns:
        df["preclose"] = df["close"].shift(1)
        df["pct_change"] = (
            (df["close"] - df["preclose"]) /
            df["preclose"].replace(0, float("nan")) * 100
        ).round(4).fillna(0)

    # turnover 字段（mootdx 无此数据，写 None）
    if "turnover" not in df.columns:
        df["turnover"] = None

    return df.to_dict(orient="records")


def _insert_records_mootdx(conn: sqlite3.Connection, code: str, records: List[dict]) -> int:
    inserted = 0
    for rec in records:
        try:
            conn.execute(
                """
                INSERT OR IGNORE INTO daily_prices
                    (code, trade_date, open, high, low, close, preclose,
                     volume, amount, turnover, pct_change)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    code,
                    str(rec.get("trade_date", ""))[:10],
                    _safe_float(rec.get("open")),
                    _safe_float(rec.get("high")),
                    _safe_float(rec.get("low")),
                    _safe_float(rec.get("close")),
                    _safe_float(rec.get("preclose")),
                    _safe_float(rec.get("volume")),
                    _safe_float(rec.get("amount")),
                    _safe_float(rec.get("turnover")),   # mootdx 无换手率，写 NULL
                    _safe_float(rec.get("pct_change")),
                ),
            )
            inserted += conn.execute("SELECT changes()").fetchone()[0]
        except Exception as exc:
            logger.debug("插入 %s %s 失败: %s", code, rec.get("trade_date"), exc)
    return inserted


def run_backfill(
    start_date: str = DOWNLOAD_START_DATE,
    end_date: Optional[str] = None,
    full: bool = False,
    resume: bool = True,
    code_list: Optional[List[str]] = None,
    dry_run: bool = False,
) -> dict:
    if end_date is None:
        end_date = get_end_date()

    logger.info("=== mootdx 回填开始 start=%s end=%s ===", start_date, end_date)

    try:
        from mootdx.quotes import Quotes
    except ImportError:
        logger.error("mootdx 未安装")
        return {"source": "mootdx", "success": 0, "total": 0, "inserted": 0, "errors": 1}

    if not dry_run:
        backup_database()

    stocks = get_stocks_to_fill(full=full, code_list=code_list)
    logger.info("待处理股票数: %d", len(stocks))
    if not stocks:
        return {"source": "mootdx", "success": 0, "total": 0, "inserted": 0, "errors": 0}

    ckpt = Checkpoint("mootdx")
    if not resume:
        ckpt.clear()

    try:
        client = Quotes.factory(market="std", bestip=True, timeout=15)
    except Exception as exc:
        logger.error("mootdx 初始化失败: %s", exc)
        return {"source": "mootdx", "success": 0, "total": len(stocks), "inserted": 0, "errors": len(stocks)}

    limiter = AdaptiveRateLimiter(RATE_LIMIT_DEFAULT)
    total_inserted = success_count = error_count = 0

    conn = _get_conn()
    try:
        for idx, stock in enumerate(stocks, 1):
            code, name = stock["code"], stock["name"]
            if ckpt.is_done(code):
                continue
            limiter.wait()
            try:
                records = _fetch_one_stock_mootdx(client, code, start_date, end_date)
                if not dry_run and records:
                    n = _insert_records_mootdx(conn, code, records)
                    conn.commit()
                    total_inserted += n
                    logger.info("[%d/%d] %s %s: 拉取=%d 插入=%d 延迟=%.2fs",
                                idx, len(stocks), code, name, len(records), n, limiter.current_delay)
                else:
                    logger.info("[%d/%d] %s %s: 拉取=%d (dry-run/空)",
                                idx, len(stocks), code, name, len(records))
                ckpt.save(code)
                success_count += 1
                limiter.success()
            except Exception as exc:
                logger.warning("[%d/%d] %s %s 失败: %s", idx, len(stocks), code, name, exc)
                error_count += 1
                limiter.failure()
    finally:
        conn.close()

    summary = {
        "source": "mootdx",
        "start": start_date, "end": end_date,
        "total": len(stocks), "success": success_count,
        "inserted": total_inserted, "errors": error_count,
    }
    logger.info("=== mootdx 回填完成: %s ===", summary)
    return summary


if __name__ == "__main__":
    p = argparse.ArgumentParser(description="mootdx 历史数据回填")
    p.add_argument("--start", default=DOWNLOAD_START_DATE)
    p.add_argument("--end", default=None)
    p.add_argument("--full", action="store_true")
    p.add_argument("--no-resume", action="store_true")
    p.add_argument("--stocks", nargs="+", default=None)
    p.add_argument("--dry-run", action="store_true")
    args = p.parse_args()
    result = run_backfill(
        start_date=args.start, end_date=args.end, full=args.full,
        resume=not args.no_resume, code_list=args.stocks, dry_run=args.dry_run,
    )
    sys.exit(0 if result.get("errors", 0) == 0 else 4)
