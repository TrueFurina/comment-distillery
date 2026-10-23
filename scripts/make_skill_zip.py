#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""把技能包打成可分发的 ZIP（`dist/comment-distillery-skill-vX.Y.Z.zip`）。

**为什么要有它**：现有三条入口各有缺口 —— `npx skills add` 要会命令行，
exe 要 Windows，Web 界面要本地起服务。而**一大群人用的是 ChatGPT / Claude 网页版**：
他们不会装 CLI，只会「上传一个文件」。ZIP 就是给这群人的入口。

**为什么 ZIP 可以自动挂载到 Release 而 exe 不行**：exe 是 PyInstaller 产物，
非可复现构建，每次打包字节都不同 → 覆盖 Release 资产会让官网声明的 SHA 当场失真
（见 `build-exe.yml` 里那段注释）。ZIP 用 `zipfile` 手写、固定时间戳/权限/排序，
**是可复现的**：同一份源码两次打包 SHA-256 完全相同。`--check` 会把这条也验一遍，
它一旦不成立，"自动挂载"就不再安全。

**为什么用显式清单而不是整目录打包**：与 `build_exe.py` 的 `ADD_DATA` 同一条纪律。
整目录会把 `cases/`（真实语料，按 `docs/compliance.md` 不公开）、`tests/`、`golden/`、
`.github/` 一起打进去 —— 那不是技能，是仓库快照。

零第三方依赖，仅标准库。
"""

import hashlib
import re
import sys
import zipfile
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent

# 显式清单：(仓库内相对路径, 包内相对路径)
# 判据是「用工具的人会用到吗」：会 → 进包；只有维护仓库才需要 → 不进。
INCLUDE = [
    ("SKILL.md", "SKILL.md"),
    ("LICENSE", "LICENSE"),
    ("scripts/prep.py", "scripts/prep.py"),
    ("scripts/verify_citations.py", "scripts/verify_citations.py"),
    ("scripts/emit_html.py", "scripts/emit_html.py"),
    ("docs/canonical-format.md", "docs/canonical-format.md"),
    ("docs/pipeline.md", "docs/pipeline.md"),
    ("docs/domains.md", "docs/domains.md"),
    ("docs/collecting.md", "docs/collecting.md"),
    ("docs/compliance.md", "docs/compliance.md"),
    ("examples/sample_corpus.csv", "examples/sample_corpus.csv"),
    ("examples/sample_guide.md", "examples/sample_guide.md"),
    ("contrib/fetch_bilibili_comments.py", "contrib/fetch_bilibili_comments.py"),
    ("contrib/README.md", "contrib/README.md"),
]

# 这些一旦出现在包里，就是打包逻辑写坏了（真实语料 / 维护侧 / 仓库脚手架）
FORBIDDEN = ("cases/", "tests/", "golden/", ".github/", "site/", "app/",
             "HANDOFF.md", "ROADMAP.md", "engineering-pitfalls.md",
             "distribution.md", "submittables/", "raw.csv")

REQUIRED = ["SKILL.md", "LICENSE", "PROMPT.md", "README.md",
            "scripts/prep.py", "scripts/verify_citations.py",
            "scripts/emit_html.py", "examples/sample_corpus.csv"]

# 可复现三件套：固定时间戳 / 固定权限 / 固定 create_system
FIXED_TIME = (1980, 1, 1, 0, 0, 0)
ATTR_FILE = 0o644 << 16
ATTR_DIR = (0o40755 << 16) | 0x10

ZIP_README = """# comment-distillery 技能包 v{version}

把**一群人对同一议题的自发文本**（评论区 / 问卷开放题 / 访谈逐字稿 / 产品反馈 /
Issue 讨论 / 弹幕）蒸馏成**带引用溯源、反例对冲、盲区说明**的厚指南。

## 三种用法，挑你顺手的

### 1. 上传给任意 AI（最简单，推荐）

把**整个解压后的文件夹**拖进对话，或至少上传这两样：

| 文件 | 作用 |
|---|---|
| `PROMPT.md` | **直接把它的内容粘进对话框** |
| `你的语料.csv` | 你要处理的那堆文本 |

AI 会按 `SKILL.md` 的方法论产出指南，引用格式 `［源:ID|权重N|层级］`，
每条结论都能倒推回具体条目。

### 2. 装进 AI 编程助手

```bash
npx skills add TrueFurina/comment-distillery
```

兼容 Claude Code / Cursor / Codex / Windsurf / Copilot 等 40+ agent。

### 3. 本地命令行（零依赖，只要 Python 3.10+）

```bash
python scripts/prep.py 你的语料.csv out/          # ① 预处理
# ② 通读 out/all_comments.txt —— 这一步是 AI 的活
python scripts/verify_citations.py 指南.md out/corpus_ccf.csv   # ③ 机验引用（硬门）
python scripts/emit_html.py 指南.md --corpus out/corpus_ccf.csv # ④ 出 HTML 报告
```

不需要 `pip install`，无第三方依赖。

## 包内文件

| 文件 | 用途 |
|---|---|
| `SKILL.md` | **方法论本体**（AI 读它） |
| `PROMPT.md` | 直接粘给 AI 的提示词 |
| `scripts/prep.py` | 预处理：去重 / 去噪 / 统计 / ID 映射 |
| `scripts/verify_citations.py` | **引用真实性机验**（差集非空 = 幻觉引用 = 不得交付） |
| `scripts/emit_html.py` | 指南 Markdown → 自包含 HTML（引用角标可点击溯源） |
| `docs/` | 语料格式规范 / 流水线 / 语料域 / 采集 / 合规 |
| `examples/` | 合成示例语料与对应指南（**不含任何真实用户数据**） |
| `contrib/` | ⚠️ 可选采集桥接，非核心、无支持 |

## 两条纪律，别跳过

1. **先看 `dup_dropped` 再信任何规模数字** —— 抓取端分页游标重叠会产出大量纯重复行。
2. **交付前必须跑引用机验，差集为空才算完成** —— 这一步不靠 AI 自觉，是脚本硬判。

---

MIT · <https://github.com/TrueFurina/comment-distillery>
本包由 `scripts/make_skill_zip.py` 生成，可复现构建。
"""

PROMPT = """# 任务：把这份语料蒸馏成一份带引用的深度指南

你现在是 **comment-distillery** 的执行者。请严格按 `SKILL.md` 的完整方法论处理语料。

## 硬性要求

1. **先看 `dup_dropped`，再信任何规模数字** —— 抓取端分页游标重叠会产出大量纯重复行，
   不去重会让「评论总数」「总赞数」虚高，并让同一条观点被重复计入共识度。
2. **每条带数据的结论必须标引用**：`[源:ID|权重N|层级]`，ID 必须真实出自语料。
3. **反例对冲**：每条共识都要配反方论据。语料一片和谐时，必须**主动**去楼中楼与
   低权重长文里开采反例，不能因为「没看到反例」就省略本章。
4. **盲区诚实说明**：主动披露幸存者 / 平台 / 算法 / 时间四类偏差。
5. **交付前必须机验引用**，差集为空才算完成：

```bash
python scripts/verify_citations.py 你的指南.md corpus_ccf.csv
```

## 交付物

一份 Markdown 深度指南（建议 8 章以上）。建议结构：

> 开场结论 → 认知框架 → 共识 vs 争议 → 反例对冲 → 行动清单 → 盲区说明

拿到指南后可选再跑一步，产出可转发 / 可打印的单文件 HTML（引用角标可点击溯源）：

```bash
python scripts/emit_html.py 你的指南.md --corpus corpus_ccf.csv
```

---

*本提示词由 comment-distillery v{version} 技能包提供。*
"""


def utf8_stdout():
    """Windows 控制台可能是 cp1252，print 中文会 UnicodeEncodeError。"""
    for s in (sys.stdout, sys.stderr):
        try:
            s.reconfigure(encoding="utf-8", errors="replace")
        except Exception:
            pass


def skill_version(root=None):
    """从 SKILL.md 的 frontmatter 取版本 —— **单一真值源**，不在这里另写一份。"""
    root = Path(root) if root else ROOT
    md = (root / "SKILL.md").read_text(encoding="utf-8")
    m = re.match(r"^---\s*\n(.*?)\n---\s*\n", md, re.S)
    if not m:
        return None
    v = re.search(r"^\s*version:\s*([0-9][^\s\"']+)", m.group(1), re.M)
    return v.group(1) if v else None


def _write(z, arcname, data, is_dir=False):
    zi = zipfile.ZipInfo(arcname, date_time=FIXED_TIME)
    zi.compress_type = zipfile.ZIP_DEFLATED
    zi.external_attr = ATTR_DIR if is_dir else ATTR_FILE
    zi.create_system = 3                      # 固定 unix，避免 Windows/Linux 差异
    z.writestr(zi, data)


def build(out=None, root=None, version=None):
    """打包。返回 dict（不打印）。"""
    root = Path(root) if root else ROOT
    ver = version or skill_version(root) or "0.0.0"
    stem = f"comment-distillery-skill-v{ver}"
    out_p = Path(out) if out else root / "dist" / f"{stem}.zip"
    out_p.parent.mkdir(parents=True, exist_ok=True)

    files = []
    with zipfile.ZipFile(out_p, "w", zipfile.ZIP_DEFLATED) as z:
        _write(z, f"{stem}/", b"", is_dir=True)
        for src, dst in sorted(INCLUDE):
            p = root / src
            if not p.exists():
                files.append({"path": dst, "missing": True})
                continue
            _write(z, f"{stem}/{dst}", p.read_bytes())
            files.append({"path": dst, "size": p.stat().st_size})
        # 包内专用说明（不是仓库 README —— 那里有下载链接等与"喂给 AI"无关的噪音）
        _write(z, f"{stem}/README.md",
               ZIP_README.replace("{version}", ver).encode("utf-8"))
        _write(z, f"{stem}/PROMPT.md",
               PROMPT.replace("{version}", ver).encode("utf-8"))

    missing = [f["path"] for f in files if f.get("missing")]
    data = out_p.read_bytes()
    return {
        "out": str(out_p), "version": ver, "stem": stem,
        "bytes": len(data),
        "sha256": hashlib.sha256(data).hexdigest(),
        "n_files": len([f for f in files if not f.get("missing")]) + 2,
        "missing": missing,
    }


def check(path) -> list:
    """校验包结构，返回问题列表（空 = 通过）。"""
    problems = []
    p = Path(path)
    if not p.exists():
        return [f"包不存在：{p}"]
    with zipfile.ZipFile(p) as z:
        names = z.namelist()
        # 统一剥掉顶层目录，便于比对
        stripped = []
        for n in names:
            parts = n.split("/", 1)
            stripped.append(parts[1] if len(parts) > 1 else "")
        have = set(x for x in stripped if x)
        for req in REQUIRED:
            if req not in have:
                problems.append(f"缺少必需文件：{req}")
        for n in names:
            if n.startswith("/") or n.startswith("../") or "\\" in n or ".." in n.split("/"):
                problems.append(f"包内路径不安全：{n}")
        for bad in FORBIDDEN:
            hit = [s for s in stripped if s.startswith(bad) or bad in s]
            if hit:
                problems.append(f"混入了不该进包的条目（{bad}）：{hit[:3]}")
        # SKILL.md 必须有 frontmatter，否则 agent 装不上
        sk = [n for n in names if n.endswith("/SKILL.md") or n == "SKILL.md"]
        if sk:
            head = z.read(sk[0]).decode("utf-8", "replace")[:400]
            if not head.startswith("---"):
                problems.append("SKILL.md 缺少 frontmatter（agent 无法识别）")
    return problems


def main(argv=None):
    utf8_stdout()
    import argparse
    ap = argparse.ArgumentParser(
        description="打包 comment-distillery 技能包为可分发的 ZIP（可复现构建，零依赖）")
    ap.add_argument("-o", "--out", default=None, help="输出路径（默认 dist/<stem>.zip）")
    ap.add_argument("--root", default=None, help="仓库根（默认本脚本上一级）")
    ap.add_argument("--check", metavar="ZIP", default=None,
                    help="校验已存在的包（结构 + 必需文件 + 排除项）")
    ap.add_argument("--print-sha", action="store_true",
                    help="只打印 SHA256= 与 SIZE_MB=（供 Release 记录）")
    args = ap.parse_args(argv)

    if args.check:
        problems = check(args.check)
        for m in problems:
            print(f"  ✗ {m}")
        if problems:
            print(f"\n❌ 校验未通过（{len(problems)} 项）")
            return 1
        print(f"✅ 包结构校验通过：{args.check}")
        return 0

    res = build(args.out, args.root)
    if args.print_sha:
        print(f"SHA256={res['sha256']}")
        print(f"SIZE_MB={round(res['bytes'] / 1048576, 2)}")
        return 0

    print(f"[ok] 已生成 {res['out']}")
    print(f"     版本：v{res['version']}　文件数：{res['n_files']}　"
          f"体积：{res['bytes']:,} 字节（{res['bytes'] / 1024:.1f} KB）")
    print(f"     SHA-256：{res['sha256']}")
    if res["missing"]:
        print(f"     ⚠️ 清单里有 {len(res['missing'])} 项不存在已跳过：{res['missing']}")
    problems = check(res["out"])
    if problems:
        for m in problems:
            print(f"  ✗ {m}")
        return 1
    print("     结构校验：通过")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
