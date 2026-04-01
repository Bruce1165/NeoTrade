#!/usr/bin/env python3
"""
verify_and_fix.py — NeoTrade Screener 架构最终验证

检查项：
  1. 语法编译通过
  2. 继承 BaseScreener
  3. 实现 screen_stock 和 run_screening
  4. super().__init__ 传入 screener_name=
  5. 无 self.db_path（代码层，注释/文档字符串除外）
  6. 无硬编码 /Users/mac（代码层）
  7. 无硬编码端口 5003（代码层）
  8. 无死代码 SQLAlchemy 导入
  9. 无 STATUS 哨兵（代码层）
"""

import ast
import re
import sys
import os
import tokenize
import io

SCRIPTS_DIR = os.path.dirname(os.path.abspath(__file__))

SCREENER_FILES = [
    "ascending_triangle_screener.py",
    "ashare_21_screener.py",
    "breakout_20day_screener.py",
    "breakout_main_screener.py",
    "coffee_cup_screener.py",
    "daily_hot_cold_screener.py",
    "double_bottom_screener.py",
    "er_ban_hui_tiao_screener.py",
    "flat_base_screener.py",
    "high_tight_flag_screener.py",
    "jin_feng_huang_screener.py",
    "shi_pan_xian_screener.py",
    "shuang_shou_ban_screener.py",
    "yin_feng_huang_screener.py",
    "zhang_ting_bei_liang_yin_screener.py",
]

PASS  = "✅"
FAIL  = "❌"
WARN  = "⚠️ "


def get_code_only_lines(source: str):
    """
    使用 tokenize 模块提取纯代码行（排除注释行和多行字符串内容）。
    返回 set of line numbers that are "real code".
    """
    code_line_numbers = set()
    try:
        tokens = tokenize.generate_tokens(io.StringIO(source).readline)
        for tok_type, tok_str, tok_start, tok_end, _ in tokens:
            if tok_type in (tokenize.COMMENT, tokenize.STRING, tokenize.NEWLINE,
                            tokenize.NL, tokenize.INDENT, tokenize.DEDENT,
                            tokenize.ENCODING):
                continue
            # 这是真实代码 token，标记其所在行
            for ln in range(tok_start[0], tok_end[0] + 1):
                code_line_numbers.add(ln)
    except tokenize.TokenError:
        # 解析失败时退化为全行扫描
        code_line_numbers = set(range(1, len(source.splitlines()) + 1))
    return code_line_numbers


def check_file(fname):
    fpath = os.path.join(SCRIPTS_DIR, fname)
    issues = []
    warnings = []

    if not os.path.exists(fpath):
        return [f"{FAIL} 文件不存在: {fpath}"], []

    with open(fpath, "r", encoding="utf-8") as f:
        source = f.read()

    lines = source.splitlines()

    # ── 1. 语法编译 ──────────────────────────────────────────
    try:
        tree = ast.parse(source)
    except SyntaxError as e:
        issues.append(f"{FAIL} 语法错误: {e}")
        return issues, warnings

    # 获取纯代码行号集合
    code_line_nos = get_code_only_lines(source)

    def code_lines():
        """yield (lineno, line_text) for real code lines only"""
        for ln in sorted(code_line_nos):
            if 1 <= ln <= len(lines):
                yield ln, lines[ln - 1]

    # ── 2. 继承 BaseScreener ─────────────────────────────────
    class_defs = [n for n in ast.walk(tree) if isinstance(n, ast.ClassDef)]
    inherits_base = any(
        any(
            (isinstance(b, ast.Name) and b.id == "BaseScreener") or
            (isinstance(b, ast.Attribute) and b.attr == "BaseScreener")
            for b in cls.bases
        )
        for cls in class_defs
    )
    if not inherits_base:
        issues.append(f"{FAIL} 未继承 BaseScreener")

    # ── 3. 实现 screen_stock & run_screening ─────────────────
    func_names = {n.name for n in ast.walk(tree) if isinstance(n, ast.FunctionDef)}
    for method in ("screen_stock", "run_screening"):
        if method not in func_names:
            issues.append(f"{FAIL} 缺少方法: {method}()")

    # ── 4. super().__init__ 传入 screener_name= ───────────────
    if "super().__init__" in source:
        if "screener_name=" not in source:
            issues.append(f"{FAIL} super().__init__ 未传 screener_name=")
    else:
        issues.append(f"{FAIL} 未调用 super().__init__")

    # ── 5-9. 逐行检查（仅代码行）────────────────────────────
    for lineno, raw in code_lines():
        # 5. self.db_path（应为 self._db_path）
        if re.search(r'\bself\.db_path\b', raw) and "self._db_path" not in raw:
            issues.append(f"{FAIL} line {lineno}: 使用了 self.db_path（应为 self._db_path）")

        # 6. 硬编码 /Users/mac
        if "/Users/mac" in raw:
            issues.append(f"{FAIL} line {lineno}: 硬编码路径 /Users/mac")

        # 7. 硬编码端口 5003
        if re.search(r'["\'].*5003.*["\']|localhost:5003', raw):
            issues.append(f"{FAIL} line {lineno}: 硬编码端口 5003")

        # 9. STATUS 哨兵
        if re.search(r"'code'\s*:\s*'STATUS'", raw):
            issues.append(f"{FAIL} line {lineno}: 存在 STATUS 哨兵记录")
        if re.search(r'\.get\(["\']code["\']\)\s*!=\s*["\']STATUS["\']', raw):
            warnings.append(f"{WARN} line {lineno}: 存在 STATUS 过滤器（死代码）")

    # ── 8. 死代码 SQLAlchemy 导入（import 语句本身就是代码行）
    if re.search(r'^from database import', source, re.MULTILINE):
        issues.append(f"{FAIL} 存在死代码 SQLAlchemy 导入（from database import ...）")

    return issues, warnings


# ── 运行检查 ──────────────────────────────────────────────────
print("=" * 65)
print("  NeoTrade Screener 架构验证")
print("=" * 65)

total_issues = 0
total_warnings = 0

for fname in SCREENER_FILES:
    issues, warnings = check_file(fname)
    total_issues += len(issues)
    total_warnings += len(warnings)

    if not issues and not warnings:
        print(f"{PASS} {fname}")
    else:
        print(f"\n{'─'*65}")
        status = FAIL if issues else WARN
        print(f"{status} {fname}")
        for msg in issues:
            print(f"      {msg}")
        for msg in warnings:
            print(f"      {msg}")
        print()

print("\n" + "=" * 65)
if total_issues == 0 and total_warnings == 0:
    print(f"🎉 全部通过！所有 {len(SCREENER_FILES)} 个 screener 架构干净。")
elif total_issues == 0:
    print(f"✅ 无严重问题，{total_warnings} 个警告。")
else:
    print(f"❌ 发现 {total_issues} 个问题，{total_warnings} 个警告，需要修复。")
print("=" * 65)

sys.exit(0 if total_issues == 0 else 1)
