#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""check_rule_tags.py —— 机验 SKILL.md 无「裸铁律」。

背景（P2 方法论去过拟合）：SKILL.md 里多数规则只被 1 战验证过，
个案被写成铁律会误导后续使用者。因此规定：

    每条规则条目必须带溯源标记 ——
        [战N]      ≥2 战独立验证，铁律
        [战N·待复现]  仅 1 战证据，是假设不是规律
        [环境]     操作系统/工具行为，一次踩到即记录
        [设计]     结构性设计，非经验归纳

判据：
    1. 核心定位「三件套」三条必须带标记；
    2. 从 `## 实施注意` 到文件末尾，所有一级 bullet（`- ` 开头，非缩进）必须带标记；
    3. 「待复现观察」章节里的条目必须带 `待复现` 或 `单样本` 字样 —— 防止降级条目伪装成铁律。

退出码：0 = 通过；1 = 发现裸铁律 / 伪装条目。

用法：
    python scripts/check_rule_tags.py                  # 检查仓库 SKILL.md
    python scripts/check_rule_tags.py --file <path>    # 检查任意文件
    python scripts/check_rule_tags.py --self-test      # 变异验证（判据本身是否有效）
"""

import argparse
import re
import sys
import tempfile
from pathlib import Path


def utf8_stdout():
    """stdout/stderr 切 UTF-8：Windows 控制台可能是 cp1252，print 中文会
    UnicodeEncodeError（实测 GitHub windows runner 因此整步失败）。"""
    for stream in (sys.stdout, sys.stderr):
        try:
            stream.reconfigure(encoding="utf-8", errors="replace")
        except Exception:
            pass


TAG_RE = re.compile(r"\[(?:战[0-9]+(?:·[^\[\]]*)?|环境|设计)\]")
NUM_RE = re.compile(r"^\d+\.\s+\*\*")
# 只有三件套锚点之后的 numbered list 才是「规则」；
# 「输入」的三种进入方式、「6 步流水线」是流程说明，不是经验规则，不纳入。
TRIPLET_ANCHOR = "三件套护城河"
WEAK_MARKERS = ("待复现", "单样本")

SECTION_START = "## 实施注意"
PENDING_SECTION = "## 待复现观察"


def check(path: Path, collect_spans: bool = False):
    """返回 (errors, checked_count, tagged_count, spans)。

    spans 供变异验证使用：记录**被检查条目**上的标记 (kind, tag, index)，
    避免变异误打在说明行/表格行上——那些不在检查范围内，删了本来也不会报错。
    """
    text = path.read_text(encoding="utf-8")
    lines = text.splitlines()
    errors = []
    checked = 0
    tagged = 0
    spans = []

    in_rules = False
    in_pending = False
    in_triplet = False

    for lineno, line in enumerate(lines, 1):
        stripped = line.strip()

        if stripped.startswith(PENDING_SECTION):
            # 待复现章节本身也要检查（它可能是文件里唯一的规则区）
            in_rules = True
            in_pending = True
            in_triplet = False
            continue
        if stripped.startswith(SECTION_START):
            in_rules = True
            in_pending = False
            in_triplet = False
            continue
        if TRIPLET_ANCHOR in stripped:
            in_triplet = True
            continue
        if stripped.startswith("## "):
            # 任何二级标题都结束三件套 / 待复现区段，
            # 避免误伤「输入」「流水线」的编号条目、以及章节外的内容
            in_triplet = False
            in_pending = False

        # 三件套（numbered list，紧跟锚点之后）
        if in_triplet and NUM_RE.match(stripped):
            checked += 1
            m = TAG_RE.search(line)
            if m:
                tagged += 1
                if collect_spans:
                    spans.append(("triplet", m.group(0), lineno, m.start()))
            else:
                errors.append(f"L{lineno}: 三件套条目缺溯源标记 -> {stripped[:60]}")
            continue

        if not in_rules:
            continue

        # 一级 bullet：`- ` 开头且无缩进
        is_top_bullet = line.startswith("- ") and not line.startswith("  ")
        if not is_top_bullet:
            continue

        checked += 1
        if not TAG_RE.search(line):
            errors.append(f"L{lineno}: 裸铁律（缺 [战N]/[环境]/[设计] 标记）-> {stripped[:70]}")
            continue

        tagged += 1
        m = TAG_RE.search(line)
        if collect_spans:
            spans.append(("pending" if in_pending else "rule", m.group(0), lineno, m.start()))
        # 待复现章节内的条目必须真的是降级条目
        if in_pending:
            tag = m.group(0)
            if not any(w in tag for w in WEAK_MARKERS):
                errors.append(
                    f"L{lineno}: 位于「待复现观察」却用铁律标记 {tag} -> {stripped[:60]}"
                )

    return errors, checked, tagged, spans


def main():
    utf8_stdout()
    ap = argparse.ArgumentParser(description="机验 SKILL.md 规则条目均带溯源标记")
    ap.add_argument("--file", default=None, help="待检查文件（默认仓库根 SKILL.md）")
    ap.add_argument("--self-test", action="store_true", help="变异验证：删标记后必须 FAIL")
    args = ap.parse_args()

    root = Path(__file__).resolve().parent.parent
    target = Path(args.file) if args.file else root / "SKILL.md"

    if args.self_test:
        return self_test(target)

    if not target.exists():
        print(f"[FAIL] 文件不存在: {target}")
        return 1

    errors, checked, tagged, _ = check(target)
    print(f"检查文件: {target}")
    print(f"条目总数: {checked}   带标记: {tagged}   裸铁律: {len(errors)}")

    if errors:
        print("\n[FAIL] 发现裸铁律 / 伪装条目：")
        for e in errors:
            print("  - " + e)
        print("\n修法：给条目加 [战N] / [战N·待复现] / [环境] / [设计] 标记；")
        print("      单战证据的观察必须放进「待复现观察」章节并用待复现标记。")
        return 1

    print("[OK] 无裸铁律 —— 全部规则条目均带溯源标记。")
    return 0


def self_test(target: Path):
    """变异验证：故意破坏标记，判据必须报错。否则判据本身无效。

    关键两点：
    1. 变异必须打在**被检查条目**的标记上。打在说明行或表格行上毫无意义——
       那些位置本来就不在检查范围内，删掉也不会报错，会得到"判据有效"的假象。
    2. 标记文本（如 `[环境]`）在全文出现多次，**必须按行号+列定位替换**，
       不能用 `str.replace(tag, ...)` —— 那会命中前面说明行里的同名标记。
    """
    text = target.read_text(encoding="utf-8")
    _, _, _, spans = check(target, collect_spans=True)
    mutants = []

    def splice(kind_filter, replacement):
        """按行列精确定位地替换第 1 个符合条件的标记。"""
        hit = [s for s in spans if s[0] in kind_filter]
        if not hit:
            return None
        _, tag, lineno, col = hit[0]
        ls = text.splitlines(keepends=True)
        old = ls[lineno - 1]
        ls[lineno - 1] = old[:col] + replacement + old[col + len(tag):]
        return "".join(ls)

    def strip_line(kind_filter):
        """把第 1 个符合条件条目所在行的**全部**标记删掉。

        只删一个是不够的：条目常带多个标记（`[战3][战6][战7]`），
        删掉 `[战3]` 后判据仍能看到 `[战6]` —— 变异形同没做。
        """
        hit = [s for s in spans if s[0] in kind_filter]
        if not hit:
            return None
        _, _, lineno, _ = hit[0]
        ls = text.splitlines(keepends=True)
        ls[lineno - 1] = TAG_RE.sub("", ls[lineno - 1])
        return "".join(ls)

    # 变异 1：把一个铁律条目的标记全部删掉
    m1 = strip_line(("triplet", "rule"))
    if m1:
        mutants.append(("删除一个铁律条目的全部溯源标记", m1))

    # 变异 2：把「待复现」章节里的降级标记改成铁律标记（伪装）
    m2 = splice(("pending",), "[战7]")
    if m2:
        mutants.append(("降级标记改成铁律标记", m2))

    # 变异 3：往待复现章节塞一条没有标记的 bullet（裸铁律）
    if PENDING_SECTION in text:
        mutants.append(
            ("待复现章节插入无标记条目", text + "\n- 这条没有任何溯源标记\n")
        )

    if len(mutants) < 3:
        print(f"[FAIL] 变异体不足（{len(mutants)}/3），无法证明判据有效")
        return 1

    ok = True
    with tempfile.TemporaryDirectory() as td:
        for name, content in mutants:
            p = Path(td) / "mutant.md"
            p.write_text(content, encoding="utf-8")
            errors, _, _, _ = check(p)
            caught = bool(errors)
            print(f"  变异「{name}」-> {'被正确拦截 OK' if caught else '漏检 FAIL'}")
            if not caught:
                ok = False

    if not ok:
        print("\n[FAIL] 判据无效：存在漏检的变异体。")
        return 1
    print(f"\n[OK] 变异验证通过（{len(mutants)}/{len(mutants)} 被拦截）。")
    return 0


if __name__ == "__main__":
    sys.exit(main())
