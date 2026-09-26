#!/usr/bin/env python3
"""文档一致性机验 —— 把「文档落后于事实」变成 CI 红灯。

**为什么要有机验**：本仓库最忌讳「数字漂移」，但这几十个数字历来靠人眼 grep 把关，
而人眼会漏。2026-09-26 一次普查就漏出 3 处：PR 文案里的 `Python 3.8+`（全库其余处已是
3.10+）、`docs/distribution.md` §E 的「需要你的仓库权限」（已被证伪——本地 token 就够了）、
`HANDOFF.md` 的 Release 待办（实际早已发布）。**靠自觉不如靠机验。**

机验的七件事（全部零依赖、不联网、可离线复现）：

| # | 检查 | 拦的是什么 |
|---|---|---|
| 1 | Python 最低版本口径唯一 | 徽章 / 正文 / 文档各写各的版本号 |
| 2 | 文档引用的 Release tag 真实存在 | 「链接写好了但 Release 还没发」 |
| 3 | 官网标注的 SHA-256 / 体积 == 真实产物 | 重建 exe 后忘改站点（最典型的一类漂移） |
| 4 | 官网无外链资源、锚点齐全 | 单文件承诺被悄悄打破 |
| 5 | 中英 README 徽章集合一致 | 只改了其中一边 |
| 6 | 规则计数四方一致（SKILL.md / 维护侧文档 / 溯源台账 §3.1+§3.2 / 文档里的计数声明） | 「加了条目不进台账」「拆了表没同步声明」——长期静默缺口的成因 |
| 7 | 已证伪表述不再出现 | 被推翻的判断留在文档里误导后来人 |

**第 6 项的四方是**（2026-09-26 环境坑按读者拆表后确定）：`SKILL.md`「环境坑」（蒸馏侧，随打包产物分发）
↔ 台账 §3.1；`docs/engineering-pitfalls.md`（维护侧，**不进打包产物**）↔ 台账 §3.2；
外加**任何同时提到「铁律」与「环境事实」的句子**都必须按 4 元组写全（HANDOFF / ROADMAP 各一处）。
拆表本身是"改 SKILL.md 就得重发 exe"这个约束的解药——详见 `docs/rule-provenance.md` §3。

用法：
    python scripts/check_doc_consistency.py                  # 检查
    python scripts/check_doc_consistency.py --self-test      # 变异验证：故意改坏必须被拦
    python scripts/check_doc_consistency.py --exe dist/x.exe # 指定产物（默认自动找 dist/*.exe）
    python scripts/check_doc_consistency.py --no-artifact    # 跳过第 3 项（见下）

⚠️ **`--no-artifact` 是给 CI 打包工作流用的，不是偷懒开关**：
    站点上写的是**已发布的那一份产物**的 SHA-256，而 CI 重新打包得到的字节**必然不同**
    （PyInstaller 不是可复现构建）。在 CI 里硬比 SHA 会逼出"永远不许重建产物"的假红线。
    所以：CI 里用 `--no-artifact`；**本地出包后跑不带该开关的版本**，核对站点标注 == 你手上那份发布件。
    发布件是否真的等于本地验证件，则在**发布后下载回来复算哈希**（这一步已在 Release 说明里做过）。

`--self-test` 是本仓库的硬规矩：**判据自身必须能被变异打穿**，否则它只是装饰。
"""

import argparse
import hashlib
import os
import re
import shutil
import sys
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent

# 会被扫描口径的文档（排除 CHANGELOG —— 它**有意**记录历史版本号，不该被"修正"）
DOCS = [
    "README.md", "README.en.md", "SKILL.md", "HANDOFF.md", "ROADMAP.md",
    "CONTRIBUTING.md", "site/index.html",
]
DOC_GLOB_DIRS = ["docs"]          # docs/*.md 全部纳入
SKIP_DIR_PARTS = {"cases", "results", ".git", "build", "dist", "node_modules"}

# 已证伪的表述：命中即 FAIL。每条必须写明「何时 / 被什么证伪」，
# 否则下一个人只会看到禁令，看不到原因，然后绕过它。
#
# ⚠️ 已知的一类"误报"（实测踩到过）：**为了说明这个漂移，而在文档里原样引用被禁的字符串**。
#    本脚本首次跑通时，就拦下了我刚刚写下的、解释这三处漂移的那段文字——
#    检查是对的，措辞是错的：描述一个漂移时不该复现它的字面量。
#    两种解法任选：① 改成不带字面量的说法（推荐，可读性也更好）；
#    ② 同行带上 原以为 / 原判 / 误判 / 已证伪 等 CORRECTION_MARKERS 标记。
#    这与 verify_citations.py 的已知误报同源：**"提及"与"断言"在纯文本里无法区分**。
REFUTED = [
    ("Python 3.8", "版本口径漂移（2026-09-26）：CI matrix 最低为 3.10，全库其余处已统一"),
    ("需要你的仓库权限", "已被证伪（2026-09-26）：tag / Release / Pages 本地 token 即可完成，无需用户操作"),
]
CORRECTION_MARKERS = ("原以为", "原判", "误判", "判断错", "曾经", "已证伪", "修正为")


def utf8_stdout():
    for s in (sys.stdout, sys.stderr):
        try:
            s.reconfigure(encoding="utf-8", errors="replace")
        except (AttributeError, ValueError):
            pass


def _doc_files(root):
    out = []
    for name in DOCS:
        p = root / name
        if p.exists():
            out.append(p)
    for d in DOC_GLOB_DIRS:
        dd = root / d
        if dd.is_dir():
            for p in sorted(dd.rglob("*.md")):
                if not (SKIP_DIR_PARTS & set(p.parts)):
                    out.append(p)
    return out


def _rel(root, p):
    try:
        return str(p.relative_to(root)).replace("\\", "/")
    except ValueError:
        return str(p)


# ── 1. Python 最低版本口径唯一 ───────────────────────────────────────────────
def min_python_from_ci(root):
    ci = root / ".github/workflows/ci.yml"
    if not ci.exists():
        return None
    m = re.search(r"python-version:\s*\[([^\]]+)\]", ci.read_text(encoding="utf-8"))
    if not m:
        return None
    vers = re.findall(r"(\d+\.\d+)", m.group(1))
    if not vers:
        return None
    return min(vers, key=lambda v: tuple(int(x) for x in v.split(".")))


def check_python_version(root):
    want = min_python_from_ci(root)
    if not want:
        return [("SKIP", "找不到 CI matrix 的 python-version，跳过版本口径检查")]
    res = []
    # 允许出现的写法：徽章里的 python-3.10%2B、正文里的 Python 3.10+
    pat = re.compile(r"Python\s*3\.(\d+)\s*\+|python-3\.(\d+)%2B", re.I)
    bad = []
    for p in _doc_files(root):
        for i, line in enumerate(p.read_text(encoding="utf-8").splitlines(), 1):
            for m in pat.finditer(line):
                got = m.group(1) or m.group(2)
                if f"3.{got}" != want:
                    bad.append(f"{_rel(root, p)}:{i} 写作 3.{got}（CI 最低为 {want}）")
    if bad:
        res.append(("FAIL", "Python 版本口径不一致：\n    " + "\n    ".join(bad)))
    else:
        res.append(("OK", f"Python 版本口径唯一（全部为 {want}+）"))
    return res


# ── 2. 文档引用的 Release tag 真实存在 ────────────────────────────────────────
# ⚠️ 操作顺序（否则这一项会把你自己卡住）：**先打 tag，再提交引用它的文档**。
#    实际的干净顺序是：commit（含文档）→ `git tag vX.Y.Z` → 再跑本脚本复核 → push。
#    CI 上 checkout 通常不带 tag，此时本项返回 SKIP（不算失败）——这是刻意的，
#    因为"远端是否已打 tag"在离线、零依赖的前提下无法判定。
def local_tags(root):
    """读本地 tag（refs/tags 目录 + packed-refs）。shallow clone 下可能为空。"""
    tags = set()
    d = root / ".git/refs/tags"
    if d.is_dir():
        tags |= {p.name for p in d.iterdir()}
    packed = root / ".git/packed-refs"
    if packed.exists():
        for line in packed.read_text(encoding="utf-8", errors="replace").splitlines():
            if "refs/tags/" in line:
                tags.add(line.rsplit("refs/tags/", 1)[1].strip())
    return tags


def check_release_tags(root, tags=None):
    if tags is None:
        tags = local_tags(root)
    if not tags:
        return [("SKIP", "读不到本地 tag（shallow clone？），跳过 Release 链接检查")]
    pat = re.compile(r"releases/tag/(v[\w.\-]+)")
    missing = []
    for p in _doc_files(root):
        for i, line in enumerate(p.read_text(encoding="utf-8").splitlines(), 1):
            hit = sorted(set(pat.findall(line)))          # 同一行出现多次只报一次
            for t in hit:
                if t not in tags:
                    missing.append(f"{_rel(root, p)}:{i} 引用了不存在的 tag {t}")
    if missing:
        return [("FAIL",
                 "引用了未发布的 Release tag：\n    " + "\n    ".join(missing) +
                 "\n    ⚠️ 若你确信这些 tag 存在，先怀疑**本地只同步了部分 tag**"
                 "\n       （实测：`actions/checkout` 在 tag 推送时默认只带那一个 tag，"
                 "\n        于是文档里对其他版本的引用会被误判为不存在）。"
                 "\n       修法是给 checkout 加 `fetch-depth: 0`，而不是删掉文档里的链接。")]
    return [("OK", f"文档引用的 Release tag 全部真实存在（本地共 {len(tags)} 个 tag）")]


# ── 3. 官网标注的 SHA / 体积 == 真实产物 ─────────────────────────────────────
def find_exe(root):
    d = root / "dist"
    if not d.is_dir():
        return None
    exes = sorted(d.glob("*.exe"))
    return exes[0] if exes else None


def check_site_numbers(root, exe=None):
    site = root / "site/index.html"
    if not site.exists():
        return [("FAIL", "site/index.html 不存在")]
    html = site.read_text(encoding="utf-8")
    if exe is None:
        exe = find_exe(root)
    if exe is None or not exe.exists():
        return [("SKIP", "无 dist/*.exe 产物，跳过站点 SHA/体积核对（本地出包后再跑）")]
    real_sha = hashlib.sha256(exe.read_bytes()).hexdigest()
    real_mb = f"{exe.stat().st_size / 1048576:.1f}"
    got_sha = re.findall(r"SHA-256：<code>([0-9a-f]{16,})", html)
    got_mb = re.findall(r"下载 exe · ([\d.]+) MB", html)
    bad = []
    if not got_sha:
        bad.append("站点未标注 SHA-256")
    elif got_sha[0] != real_sha:
        bad.append(f"站点 SHA {got_sha[0][:16]}… != 产物 {real_sha[:16]}…")
    if not got_mb:
        bad.append("站点未标注体积")
    elif got_mb[0] != real_mb:
        bad.append(f"站点体积 {got_mb[0]} MB != 产物 {real_mb} MB")
    if bad:
        return [("FAIL", "官网数字与产物不符（重建后忘了改站点？）：\n    " + "\n    ".join(bad))]
    return [("OK", f"官网 SHA/体积与产物一致（{real_mb} MB，{real_sha[:12]}…）")]


# ── 4. 官网单文件承诺 / 锚点 ────────────────────────────────────────────────
def check_site_structure(root):
    site = root / "site/index.html"
    if not site.exists():
        return [("FAIL", "site/index.html 不存在")]
    html = site.read_text(encoding="utf-8")
    bad = []
    ext = re.findall(r'(?:src|href)="https?://[^"]+\.(?:js|css|woff2?)"', html)
    if ext:
        bad.append(f"外链资源：{ext}")
    ids = set(re.findall(r'\bid="([^"]+)"', html))
    miss = sorted(set(re.findall(r'href="#([^"]+)"', html)) - ids)
    if miss:
        bad.append(f"锚点无对应元素：{miss}")
    for tag in ("<html", "</html>", "<head>", "</head>", "<body>", "</body>"):
        if tag not in html:
            bad.append(f"缺少结构标签 {tag}")
    if bad:
        return [("FAIL", "官网自检失败：\n    " + "\n    ".join(bad))]
    return [("OK", f"官网自检通过（{len(ids)} 个锚点目标、零外链资源）")]


# ── 5. 中英 README 徽章集合一致 ─────────────────────────────────────────────
def _badges(text):
    return sorted(re.findall(r"\[!\[[^\]]*\]\(([^)]+)\)\]", text))


def check_readme_parity(root):
    zh, en = root / "README.md", root / "README.en.md"
    if not zh.exists() or not en.exists():
        return [("SKIP", "缺少 README.md / README.en.md 之一，跳过错位检查")]
    bz, be = _badges(zh.read_text(encoding="utf-8")), _badges(en.read_text(encoding="utf-8"))
    if bz != be:
        only_zh = sorted(set(bz) - set(be))
        only_en = sorted(set(be) - set(bz))
        return [("FAIL", f"中英 README 徽章不一致：仅中文 {only_zh} / 仅英文 {only_en}")]
    return [("OK", f"中英 README 徽章集合一致（{len(bz)} 个）")]


# ── 6. 已证伪表述不再出现 ───────────────────────────────────────────────────
def check_refuted(root):
    hits = []
    for p in _doc_files(root):
        for i, line in enumerate(p.read_text(encoding="utf-8").splitlines(), 1):
            if any(mk in line for mk in CORRECTION_MARKERS):
                continue    # 「曾经这么以为」的句子是合法的自我纠正，不算违规
            for phrase, why in REFUTED:
                if phrase in line:
                    hits.append(f"{_rel(root, p)}:{i} 「{phrase}」—— {why}")
    if hits:
        return [("FAIL", "文档里还留着已证伪的表述：\n    " + "\n    ".join(hits))]
    return [("OK", f"无已证伪表述（黑名单 {len(REFUTED)} 条）")]


# ── 7. 规则计数：SKILL.md 的条目数 == 溯源台账的行数 == HANDOFF 的声明数 ──────
def _section(text, header):
    m = re.search(rf"^{re.escape(header)}.*?(?=\n## |\Z)", text, re.S | re.M)
    return m.group(0) if m else ""


def _sub_section(text, header):
    """取三级子章节（`### 3.1 …`），在下一个 `## ` 或 `### ` 处截止。

    §3 拆成 §3.1/§3.2 后必须分开取——否则 `_section(text, "## 3.")` 会把两张表
    的行数加在一起，计数核对就失去意义。
    """
    m = re.search(rf"^{re.escape(header)}.*?(?=\n#{{2,3}} |\Z)", text, re.S | re.M)
    return m.group(0) if m else ""


def _env_count(text):
    """数形如 `- **…** `[环境]`` 的条目（SKILL.md 与维护侧文档共用同一写法）。"""
    return len(re.findall(r"^- .*?`\[环境\]`", text, re.M))


def _table_rows(sec):
    """取 markdown 表格的数据行（排除表头与分隔行）。"""
    out = []
    for line in sec.splitlines():
        s = line.strip()
        if not s.startswith("|"):
            continue
        if set(s) <= set("|-: "):          # 分隔行 |---|---|
            continue
        first = s.strip("|").split("|")[0].strip()
        if first in ("#", "条目", "规则", "观察", "编号", "项"):
            continue
        out.append(s)
    return out


# ── 6. 规则计数：四处必须对上 ────────────────────────────────────────────────
#    SKILL.md「环境坑」(蒸馏侧)  ↔  台账 §3.1
#    docs/engineering-pitfalls.md (维护侧)  ↔  台账 §3.2
#    SKILL.md「待复现观察」  ↔  台账 §2
#    + 任何同时提到「铁律」与「环境事实」的句子，都必须按 4 元组写全
#
# 2026-09-26 起 §3 按读者拆成两张表（蒸馏侧随打包产物分发、维护侧不进产物）。
# 拆表让"改一条构建笔记"不再触发热发布——所以这里也要**分别**核对两张表，
# 不能把两处行数加总了事（那会让"少记一条"永远看不出来）。
CANON_COUNTS = re.compile(
    r"(\d+)\s*条?\s*铁律[^/\n]{0,16}/\s*"
    r"(\d+)\s*条?\s*待复现[^/\n]{0,16}/\s*"
    r"(\d+)\s*条?\s*环境事实[^/\n]{0,16}/\s*"
    r"(\d+)\s*条?\s*工程坑")


def check_rule_counts(root):
    skill = root / "SKILL.md"
    prov = root / "docs/rule-provenance.md"
    eng = root / "docs/engineering-pitfalls.md"
    if not skill.exists() or not prov.exists():
        return [("SKIP", "缺少 SKILL.md 或 docs/rule-provenance.md，跳过规则计数核对")]
    st, pt = skill.read_text(encoding="utf-8"), prov.read_text(encoding="utf-8")

    env_skill = _env_count(_section(st, "### 环境坑"))
    tw_skill = len(re.findall(r"^- .*?`\[战\d+·(?:待复现|单样本)\]`",
                              _section(st, "## 待复现观察"), re.M))
    tw_prov = len(_table_rows(_section(pt, "## 2.")))
    iron_prov = len(_table_rows(_section(pt, "## 1.")))
    env_prov_a = len(_table_rows(_sub_section(pt, "### 3.1")))
    env_prov_b = len(_table_rows(_sub_section(pt, "### 3.2")))

    bad = []
    if env_skill != env_prov_a:
        bad.append(f"蒸馏侧环境坑：SKILL.md 有 {env_skill} 条，台账 §3.1 只有 {env_prov_a} 行"
                   "（加了条目不进台账——这正是它长期静默缺口的成因）")
    if tw_skill != tw_prov:
        bad.append(f"待复现：SKILL.md 有 {tw_skill} 条，台账 §2 只有 {tw_prov} 行")

    env_eng = None
    if eng.exists():
        env_eng = _env_count(eng.read_text(encoding="utf-8"))
        if env_eng != env_prov_b:
            bad.append(f"维护侧工程坑：docs/engineering-pitfalls.md 有 {env_eng} 条，"
                       f"台账 §3.2 只有 {env_prov_b} 行")
    else:
        bad.append("缺少 docs/engineering-pitfalls.md（维护侧环境坑的唯一真源）")

    # 计数声明：**同时出现「铁律」与「环境事实」的句子，必须按 4 元组写全**。
    # 为什么按"句"扫而不是只查 HANDOFF 一处：这类手写数字历史上散在多份文档里，
    # 只钉一处等于让其余几处继续漂移（同族的漏检比已知那处更危险）。
    want = (iron_prov, tw_prov, env_prov_a, env_prov_b) if env_eng is not None else None
    seen_in = set()
    for p in _doc_files(root):
        for i, line in enumerate(p.read_text(encoding="utf-8").splitlines(), 1):
            if "铁律" not in line or "环境事实" not in line:
                continue
            m = CANON_COUNTS.search(line)
            if not m:
                bad.append(f"{_rel(root, p)}:{i} 提到规则计数却没按新口径写全"
                           "（须形如「N 铁律 / N 待复现 / N 环境事实 / N 工程坑」）")
                continue
            seen_in.add(_rel(root, p))
            got = tuple(int(x) for x in m.groups())
            if want and got != want:
                bad.append(f"{_rel(root, p)}:{i} 声明 {got[0]} 铁律 / {got[1]} 待复现 / "
                           f"{got[2]} 环境事实 / {got[3]} 工程坑，台账实际为 "
                           f"{want[0]} / {want[1]} / {want[2]} / {want[3]}")
    if "HANDOFF.md" not in seen_in:
        bad.append("HANDOFF.md 里找不到规则计数声明"
                   "（那句 N 铁律 / N 待复现 / N 环境事实 / N 工程坑）")

    if bad:
        return [("FAIL", "规则计数口径不一致：\n    " + "\n    ".join(bad))]
    return [("OK", f"规则计数一致（{iron_prov} 铁律 / {tw_prov} 待复现 / "
                   f"{env_prov_a} 环境事实（蒸馏侧）/ {env_prov_b} 工程坑（维护侧））")]



CHECKS = [
    ("Python 版本口径", check_python_version),
    ("Release tag 引用", check_release_tags),
    ("官网数字 == 产物", check_site_numbers),
    ("官网结构", check_site_structure),
    ("中英 README 对等", check_readme_parity),
    ("规则计数一致", check_rule_counts),
    ("已证伪表述", check_refuted),
]


def run(root, exe=None, tags=None, with_artifact=True):
    res = []
    for name, fn in CHECKS:
        if fn is check_site_numbers:
            if not with_artifact:
                res.append((name, "SKIP", "--no-artifact：站点标注的是已发布产物，CI 现打包的字节不同，不比"))
                continue
            out = fn(root, exe)
        elif fn is check_release_tags:
            out = fn(root, tags)
        else:
            out = fn(root)
        res.extend((name, status, msg) for status, msg in out)
    return res


# ── 变异验证：故意改坏，检查必须失败 ────────────────────────────────────────
def _stage(root, tmp):
    """把检查所需的文件复制到 tmp，得到可安全破坏的副本。"""
    for name in DOCS:
        src = root / name
        if src.exists():
            dst = tmp / name
            dst.parent.mkdir(parents=True, exist_ok=True)
            shutil.copyfile(src, dst)
    for d in DOC_GLOB_DIRS:
        if (root / d).is_dir():
            shutil.copytree(root / d, tmp / d, dirs_exist_ok=True)
    (tmp / ".github/workflows").mkdir(parents=True, exist_ok=True)
    ci = root / ".github/workflows/ci.yml"
    if ci.exists():
        shutil.copyfile(ci, tmp / ".github/workflows/ci.yml")
    return tmp


def _case(root, tags, label, check_name, mutate):
    """在临时副本上施加变异并**立即**检查。

    必须在 with 块内完成——早期版本把副本路径存进列表、with 退出后才检查，
    结果临时目录已被删除，检查因"文件不存在"给出 SKIP / 假 FAIL。
    **这个 bug 是 self-test 自己抓出来的**（首跑报「没被拦下」）。
    """
    with tempfile.TemporaryDirectory() as td:
        st = _stage(root, Path(td) / "case")
        fake_exe = mutate(st)
        res = run(st, exe=fake_exe, tags=tags)
        sts = [s for n, s, _ in res if n == check_name]
        return label, check_name, sts


def _mut_python(st):
    f = st / "README.md"
    f.write_text(f.read_text(encoding="utf-8").replace("python-3.10%2B", "python-3.8%2B"),
                 encoding="utf-8")
    return None


def _mut_tag(st):
    f = st / "README.md"
    f.write_text(f.read_text(encoding="utf-8")
                 + "\n[v9.9.9](https://github.com/x/y/releases/tag/v9.9.9)\n", encoding="utf-8")
    return None


def _mut_site_sha(st):
    fake = st / "fake_artifact.exe"
    fake.write_bytes(b"not the real artifact" * 2000)
    f = st / "site/index.html"
    f.write_text(re.sub(r"(SHA-256：<code>)[0-9a-f]+", r"\g<1>" + "0" * 64,
                        f.read_text(encoding="utf-8")), encoding="utf-8")
    return fake


def _mut_refuted(st):
    f = st / "HANDOFF.md"
    f.write_text(f.read_text(encoding="utf-8") + "\n该步骤需要你的仓库权限才能完成。\n",
                 encoding="utf-8")
    return None


def _mut_badge(st):
    """只删英文 README 的一个徽章 → 中英对等检查必须报错"""
    f = st / "README.en.md"
    f.write_text(f.read_text(encoding="utf-8").replace(
        "[![License: MIT](https://img.shields.io/badge/License-MIT-blue.svg)](LICENSE)\n", ""),
        encoding="utf-8")
    return None


def _mut_anchor(st):
    """站点加一个无对应元素的锚点链接 → 结构检查必须报错"""
    f = st / "site/index.html"
    f.write_text(f.read_text(encoding="utf-8").replace(
        "</body>", '<a href="#nope-not-here">x</a>\n</body>'), encoding="utf-8")
    return None


def _drop_line(path, needle):
    """删掉第一个含 needle 的整行（变异用）。定位不到就直接炸，避免"变异没生效却报 OK"。"""
    ls = path.read_text(encoding="utf-8").splitlines(keepends=True)
    hit = [i for i, l in enumerate(ls) if needle in l]
    if not hit:
        raise AssertionError(f"变异定位失败：{path.name} 里找不到 {needle!r}")
    del ls[hit[0]]
    path.write_text("".join(ls), encoding="utf-8")


def _mut_table_a(st):
    """台账 §3.1（蒸馏侧）少记一条 → 计数核对必须报错"""
    _drop_line(st / "docs/rule-provenance.md", "别自己写 bv2av")
    return None


def _mut_env_doc_entry(st):
    """维护侧文档删掉一条 → §3.2 的行数就对不上了，必须报错。

    这条同时证明「新拆出来的维护侧文档真的被读了」——否则它是一份没人管的孤儿文档。
    """
    _drop_line(st / "docs/engineering-pitfalls.md", "Actions 的 job 日志端点")
    return None


def _mut_count_statement(st):
    """把计数声明里的数字改错（9→8）→ 必须报错"""
    f = st / "ROADMAP.md"
    f.write_text(f.read_text(encoding="utf-8").replace("9 条铁律（≥2 战）", "8 条铁律（≥2 战）"),
                 encoding="utf-8")
    return None


def _mut_stmt_gone(st):
    """删掉 HANDOFF 的计数声明整行 → 必须报错。

    「声明被整段删掉」是一种伪装成"没有不一致"的漂移——没有声明就没有矛盾可查，
    所以必须单独把"声明存在"本身当作判据。
    """
    _drop_line(st / "HANDOFF.md", "工程坑")
    return None


def _mut_legacy_statement(st):
    """在别的文档里写回**旧的三段式**声明（只写铁律/待复现/环境事实）→ 必须报错。

    这条单独造在一个原本没有声明的位置，为的是**只**触发"未按新口径写全"那个分支；
    真实历史正是这样漏的：声明换了口径，散落各处的副本还停在旧格式。
    """
    f = st / "CONTRIBUTING.md"
    f.write_text(f.read_text(encoding="utf-8")
                 + "\n> 规则计数：9 铁律 / 5 待复现 / 6 环境事实。\n", encoding="utf-8")
    return None


CASES = [
    ("Python 版本写错（3.10→3.8）", "Python 版本口径", _mut_python),
    ("引用不存在的 Release tag", "Release tag 引用", _mut_tag),
    ("站点 SHA 与产物不符", "官网数字 == 产物", _mut_site_sha),
    ("写回已证伪表述", "已证伪表述", _mut_refuted),
    ("只删英文 README 的一个徽章", "中英 README 对等", _mut_badge),
    ("站点加了无对应元素的锚点", "官网结构", _mut_anchor),
    ("台账 §3.1 少记一条（蒸馏侧）", "规则计数一致", _mut_table_a),
    ("维护侧文档少一条（未进 §3.2）", "规则计数一致", _mut_env_doc_entry),
    ("计数声明里的数字改错", "规则计数一致", _mut_count_statement),
    ("HANDOFF 的计数声明整行被删", "规则计数一致", _mut_stmt_gone),
    ("别处写回旧的三段式声明", "规则计数一致", _mut_legacy_statement),
]


def _selftest_tags(root):
    """self-test 专用的 tag 集合 = 本地 tag ∪ 文档里出现的所有 tag。

    为什么必须并上后者：CI 的 checkout 默认只带被推送的那一个 tag（甚至一个都不带），
    此时「引用不存在的 tag」这一项会 SKIP，于是那个变异就成了**漏网变异**、self-test 假红。
    self-test 要验的是**判据本身有效**，不该依赖运行环境的 tag 完整性；
    真实检查（`check_release_tags`）仍然严格要求 tag 在本地存在。
    """
    tags = local_tags(root)
    for p in _doc_files(root):
        tags |= set(re.findall(r"releases/tag/(v[\w.\-]+)", p.read_text(encoding="utf-8")))
    return tags


def self_test(root):
    print("[self-test] 变异验证：故意改坏，每个变异都必须被**对应**的检查拦下\n")
    tags = _selftest_tags(root)
    ok = True

    with tempfile.TemporaryDirectory() as td:
        st = _stage(root, Path(td) / "clean")
        res = run(st, tags=tags)
        clean_bad = [f"{n}: {m}" for n, s, m in res if s == "FAIL"]
        if clean_bad:
            print("  [FAIL] 未变异的副本本应全绿，却报错（检查可能过严）：")
            for b in clean_bad:
                print("      ", b.replace("\n", " "))
            ok = False
        else:
            print("  [OK]   基准副本全绿（说明检查不是无条件失败）")

    for label, check_name, mutate in CASES:
        got_label, got_check, sts = _case(root, tags, label, check_name, mutate)
        if "FAIL" in sts:
            print(f"  [OK]   变异「{got_label}」被「{got_check}」拦下")
        elif sts and all(s == "SKIP" for s in sts):
            print(f"  [FAIL] 变异「{got_label}」的检查被跳过（SKIP）——环境不满足，等于没验")
            ok = False
        else:
            print(f"  [FAIL] 变异「{got_label}」**没被拦下**（{got_check} 报 {sts}）——检查形同虚设")
            ok = False

    print()
    print("[self-test] " + ("全部变异均被拦截 ✅" if ok else "存在漏网变异 ❌"))
    return 0 if ok else 1


def main(argv=None):
    utf8_stdout()
    ap = argparse.ArgumentParser(description="文档一致性机验（防「文档落后于事实」）")
    ap.add_argument("--root", default=None, help="仓库根（默认自动定位）")
    ap.add_argument("--exe", default=None, help="指定 exe 产物路径（默认自动找 dist/*.exe）")
    ap.add_argument("--no-artifact", action="store_true",
                    help="跳过站点数字 == 产物的核对（CI 打包用：站点记的是已发布产物，与现打包字节必然不同）")
    ap.add_argument("--self-test", action="store_true", help="变异验证：故意改坏必须被拦")
    args = ap.parse_args(argv)

    root = Path(args.root).resolve() if args.root else ROOT

    if args.self_test:
        return self_test(root)

    exe = Path(args.exe).resolve() if args.exe else None
    res = run(root, exe, with_artifact=not args.no_artifact)

    print("=== 文档一致性机验 ===")
    for name, status, msg in res:
        print(f"  [{status}] {name}: {msg}")
    failed = [n for n, s, _ in res if s == "FAIL"]
    print()
    if failed:
        print(f"❌ {len(failed)} 项未通过：{', '.join(failed)}")
        print("   → 请把文档改成事实，而不是把检查关掉。")
        return 1
    print("✅ 全部通过（跳过的项因缺产物，本地出包后重跑可覆盖）")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
