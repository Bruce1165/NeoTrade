"""
backfill_akshare.py – AKShare 历史数据回填（Level-2）

修复记录
--------
* [BUG-FIX] 换手率字段统一写入 DB 列名 turnover（原为 turn）
* 列名映射更新：turn / turnover_rate → turnover
"""

from __future__ import annotations

import argparse
import logging
import sqlite3
import sys
import time
from pathlib import Path
from typing import List, Optional

sys.path.insert(0, str(Path(__file__).parent))
from config import (
    AKSHARE_ADJUST,
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
    RETRY_MAX_ATTEMPTS,
)

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S",
)
logger = logging.getLogger("backfill_akshare")


# ────────────────────────────────────────────────────────────────────────────
# 日期格式工具
# ────────────────────────────────────────────────────────────────────────────
def _to_compact(d: str) -> str:
    return d.replace("-", "")


def _to_dash(d: str) -> str:
    if "-" in d:
        return d
    return f"{d[:4]}-{d[4:6]}-{d[6:]}"


# ────────────────────────────────────────────────────────────────────────────
# AKShare 列名 → daily_prices 字段名映射
# 换手率统一写入 turnover（与 schema 一致）
# ────────────────────────────────────────────────────────────────────────────
_COLUMN_MAP = {
    # 中文列名
    "日期":    "trade_date",
    "开盘":    "open",
    "最高":    "high",
    "最低":    "low",
    "收盘":    "close",
    "昨收":    "preclose",
    "成交量":  "volume",
    "成交额":  "amount",
    "涨跌幅":  "pct_change",
    "换手率":  "turnover",
    # 英文列名
    "date":          "trade_date",
    "open":          "open",
    "high":          "high",
    "low":           "low",
    "close":         "close",
    "volume":        "volume",
    "amount":        "amount",
    "pct_chg":       "pct_change",
    "turn":          "turnover",
    "turnover_rate": "turnover",
}


@with_retry(max_attempts=RETRY_MAX_ATTEMPTS)
def _fetch_one_stock_ak(code: str, start_date: str, end_date: str) -> List[dict]:
    import akshare as ak
    df = ak.stock_zh_a_hist(
        symbol=code,
        period="daily",
        start_date=_to_compact(start_date),
        end_date=_to_compact(end_date),
        adjust=AKSHARE_ADJUST,
    )
    if df is None or df.empty:
        return []

    df = df.rename(columns={c: _COLUMN_MAP.get(c, c) for c in df.columns})

    if "trade_date" in df.columns:
        df["trade_date"] = df["trade_date"].astype(str).apply(_to_dash)

    return df.to_dict(orient="records")


def _insert_records_ak(conn: sqlite3.Connection, code: str, records: List[dict]) -> int:
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
                    rec.get("trade_date"),
                    _safe_float(rec.get("open")),
                    _safe_float(rec.get("high")),
                    _safe_float(rec.get("low")),
                    _safe_float(rec.get("close")),
                    _safe_float(rec.get("preclose")),
                    _safe_float(rec.get("volume")),
                    _safe_float(rec.get("amount")),
                    _safe_float(rec.get("turnover")),
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

    logger.info("=== AKShare 回填开始 start=%s end=%s ===", start_date, end_date)

    try:
        import akshare  # noqa
    except ImportError:
        logger.error("akshare 未安装")
        return {"source": "akshare", "success": 0, "total": 0, "inserted": 0, "errors": 1}

    if not dry_run:
        backup_database()

    stocks = get_stocks_to_fill(full=full, code_list=code_list)
    logger.info("待处理股票数: %d", len(stocks))
    if not stocks:
        return {"source": "akshare", "success": 0, "total": 0, "inserted": 0, "errors": 0}

    ckpt = Checkpoint("akshare")
    if not resume:
        ckpt.clear()
    logger.info("Checkpoint 已跳过: %d 只", len(ckpt))

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
                records = _fetch_one_stock_ak(code, start_date, end_date)
                if not dry_run and records:
                    n = _insert_records_ak(conn, code, records)
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
        "source": "akshare",
        "start": start_date, "end": end_date,
        "total": len(stocks), "success": success_count,
        "inserted": total_inserted, "errors": error_count,
    }
    logger.info("=== AKShare 回填完成: %s ===", summary)
    return summary


if __name__ == "__main__":
    p = argparse.ArgumentParser(description="AKShare 历史数据回填")
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
