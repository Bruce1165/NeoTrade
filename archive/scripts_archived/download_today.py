#!/usr/bin/env python3
"""
download_today.py – 今日行情下载（多数据源 fallback）

优先级：mootdx → baostock → akshare
任一成功写入 daily_prices 并退出 0；全部失败退出 1。

复用 backfill_baostock / backfill_mootdx 已有的 fetch + insert 逻辑，
避免重复代码。
"""

from __future__ import annotations

import logging
import sqlite3
import sys
import time
from datetime import datetime, timedelta
from pathlib import Path
from typing import List, Optional

sys.path.insert(0, str(Path(__file__).parent))
from config import DB_PATH, LOGS_DIR

LOGS_DIR.mkdir(parents=True, exist_ok=True)
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(levelname)s - %(message)s",
    handlers=[
        logging.FileHandler(LOGS_DIR / "download_today.log", encoding="utf-8"),
        logging.StreamHandler(),
    ],
)
logger = logging.getLogger(__name__)


# ─────────────────────────────────────────────
# 工具
# ─────────────────────────────────────────────

def _get_trade_date() -> str:
    """返回今日或最近交易日 YYYY-MM-DD（简单按周末处理）"""
    today = datetime.now()
    wd = today.weekday()
    if wd == 5:       # 周六 → 周五
        today -= timedelta(days=1)
    elif wd == 6:     # 周日 → 周五
        today -= timedelta(days=2)
    return today.strftime("%Y-%m-%d")


def _get_conn() -> sqlite3.Connection:
    conn = sqlite3.connect(str(DB_PATH), timeout=30)
    conn.execute("PRAGMA journal_mode=WAL")
    return conn


def _get_stock_list() -> List[dict]:
    with _get_conn() as conn:
        rows = conn.execute(
            "SELECT code, name FROM stocks WHERE COALESCE(is_delisted,0)=0"
        ).fetchall()
    return [{"code": r[0], "name": r[1]} for r in rows]


# ─────────────────────────────────────────────
# 数据源 1：mootdx（复用 backfill_mootdx 逻辑）
# ─────────────────────────────────────────────

def _fetch_mootdx(trade_date: str, stocks: List[dict]) -> int:
    """用 mootdx 下载今日数据，写入 DB，返回插入条数"""
    from backfill_mootdx import _fetch_one_stock_mootdx, _insert_records_mootdx
    from mootdx.quotes import Quotes

    client = Quotes.factory(market="std", bestip=True, timeout=15)
    logger.info("[mootdx] 客户端初始化完成，共 %d 只股票", len(stocks))

    conn = _get_conn()
    total_inserted = 0
    errors = 0
    try:
        for i, stock in enumerate(stocks, 1):
            code = stock["code"]
            try:
                records = _fetch_one_stock_mootdx(client, code, trade_date, trade_date)
                if records:
                    n = _insert_records_mootdx(conn, code, records)
                    total_inserted += n
            except Exception as exc:
                errors += 1
                if errors <= 5:
                    logger.debug("[mootdx] %s 失败: %s", code, exc)
            if i % 500 == 0:
                conn.commit()
                logger.info("[mootdx] 进度 %d/%d 已插入 %d 条", i, len(stocks), total_inserted)
        conn.commit()
    finally:
        conn.close()

    logger.info("[mootdx] 完成，插入 %d 条，失败 %d 只", total_inserted, errors)
    if total_inserted == 0:
        raise ValueError("mootdx 插入 0 条，可能今日非交易日或连接失败")
    return total_inserted


# ─────────────────────────────────────────────
# 数据源 2：baostock（复用 backfill_baostock 逻辑）
# ─────────────────────────────────────────────

def _fetch_baostock(trade_date: str, stocks: List[dict]) -> int:
    """用 baostock 下载今日数据，写入 DB，返回插入条数"""
    import baostock as bs
    from backfill_baostock import _fetch_one_stock, _insert_records

    lg = bs.login()
    if lg.error_code != "0":
        raise RuntimeError(f"baostock 登录失败: {lg.error_msg}")
    logger.info("[baostock] 登录成功，共 %d 只股票", len(stocks))

    conn = _get_conn()
    total_inserted = 0
    errors = 0
    try:
        for i, stock in enumerate(stocks, 1):
            code = stock["code"]
            try:
                records = _fetch_one_stock(bs, code, trade_date, trade_date)
                if records:
                    n = _insert_records(conn, code, records)
                    total_inserted += n
            except Exception as exc:
                errors += 1
                if errors <= 5:
                    logger.debug("[baostock] %s 失败: %s", code, exc)
            if i % 500 == 0:
                conn.commit()
                logger.info("[baostock] 进度 %d/%d 已插入 %d 条", i, len(stocks), total_inserted)
            time.sleep(0.05)   # 温和限速
        conn.commit()
    finally:
        conn.close()
        bs.logout()
        logger.info("[baostock] 已登出")

    logger.info("[baostock] 完成，插入 %d 条，失败 %d 只", total_inserted, errors)
    if total_inserted == 0:
        raise ValueError("baostock 插入 0 条，可能今日非交易日或无新数据")
    return total_inserted


# ─────────────────────────────────────────────
# 数据源 3：akshare（批量接口，速度快）
# ─────────────────────────────────────────────

def _safe_float(v) -> Optional[float]:
    try:
        f = float(v)
        return None if (f != f) else f
    except Exception:
        return None


def _fetch_akshare(trade_date: str, stocks: List[dict]) -> int:
    """用 akshare stock_zh_a_hist 逐股下载今日数据，写入 DB"""
    import akshare as ak

    stock_set = {s["code"] for s in stocks}
    conn = _get_conn()
    total_inserted = 0
    errors = 0
    try:
        for i, stock in enumerate(stocks, 1):
            code = stock["code"]
            try:
                df = ak.stock_zh_a_hist(
                    symbol=code,
                    period="daily",
                    start_date=trade_date.replace("-", ""),
                    end_date=trade_date.replace("-", ""),
                    adjust="hfq",
                )
                if df is None or df.empty:
                    continue
                row = df.iloc[-1]
                conn.execute(
                    """
                    INSERT OR IGNORE INTO daily_prices
                        (code, trade_date, open, high, low, close, preclose,
                         volume, amount, turnover, pct_change)
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                    """,
                    (
                        code, trade_date,
                        _safe_float(row.get("开盘")),
                        _safe_float(row.get("最高")),
                        _safe_float(row.get("最低")),
                        _safe_float(row.get("收盘")),
                        None,   # akshare hist 无 preclose
                        _safe_float(row.get("成交量")),
                        _safe_float(row.get("成交额")),
                        _safe_float(row.get("换手率")),
                        _safe_float(row.get("涨跌幅")),
                    ),
                )
                total_inserted += conn.execute("SELECT changes()").fetchone()[0]
            except Exception as exc:
                errors += 1
                if errors <= 5:
                    logger.debug("[akshare] %s 失败: %s", code, exc)
            if i % 200 == 0:
                conn.commit()
                logger.info("[akshare] 进度 %d/%d 已插入 %d 条", i, len(stocks), total_inserted)
            time.sleep(0.1)
        conn.commit()
    finally:
        conn.close()

    logger.info("[akshare] 完成，插入 %d 条，失败 %d 只", total_inserted, errors)
    if total_inserted == 0:
        raise ValueError("akshare 插入 0 条，可能今日非交易日或接口失败")
    return total_inserted


# ─────────────────────────────────────────────
# 主流程
# ─────────────────────────────────────────────

def main() -> int:
    trade_date = _get_trade_date()
    logger.info("=== download_today 开始，交易日: %s ===", trade_date)

    try:
        stocks = _get_stock_list()
    except Exception as exc:
        logger.error("无法读取 stocks 表: %s", exc)
        return 1

    if not stocks:
        logger.error("stocks 表为空，请先运行数据初始化")
        return 1

    logger.info("共 %d 只股票待下载", len(stocks))

    sources = [
        ("mootdx",   _fetch_mootdx),
        ("baostock", _fetch_baostock),
        ("akshare",  _fetch_akshare),
    ]

    for name, fetch_fn in sources:
        logger.info("── 尝试数据源: %s ──", name)
        try:
            inserted = fetch_fn(trade_date, stocks)
            logger.info("✅ %s 成功，共写入 %d 条", name, inserted)
            return 0
        except ImportError as exc:
            logger.warning("❌ %s 未安装，跳过: %s", name, exc)
        except Exception as exc:
            logger.warning("❌ %s 失败: %s，尝试下一个数据源", name, exc)
        time.sleep(2)

    logger.error("所有数据源均失败，今日数据未写入")
    return 1


if __name__ == "__main__":
    sys.exit(main())
