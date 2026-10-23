#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""GUI 接线的**静态**机验（app/gui.py）。

为什么要用静态分析而不是真的构造窗口：
CI 的 Python（含本机的 managed 版）**没有 tkinter**，窗口构造不起来。
改了 `gui.py` 却没法验证，等于把"按钮点了会不会炸"交给运气——
本项目不接受这种缺口，所以把它变成可机验的：

    1. 每个控件 `command=` 指向的 `self.xxx`，必须是所在类真实存在的方法
       （防"改了方法名、忘了改按钮"，运行到点击时才会炸的那一类 bug）
    2. 「启动本地 Web 界面」这个出口必须在（它是非 Windows 用户唯一的图形入口）
    3. `from app import webui` 这条**静态 import** 必须在
       （PyInstaller 靠它把 webui 模块收进产物；改成动态 import 就静默漏打包）

纯 AST，不 import tkinter，任何环境都能跑。
"""

import ast
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
GUI = ROOT / "app" / "gui.py"

# 带 command= 参数的控件
_CMD_WIDGETS = {"Button", "Checkbutton", "Radiobutton", "Combobox", "Spinbox"}


def _self_attr_names(node):
    """收集表达式里所有 `self.xxx` 的名字（含 lambda 体内的）。"""
    out = set()
    for n in ast.walk(node):
        if isinstance(n, ast.Attribute) and isinstance(n.value, ast.Name) \
                and n.value.id == "self":
            out.add(n.attr)
    return out


class TestGuiWiring(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.src = GUI.read_text(encoding="utf-8")
        cls.tree = ast.parse(cls.src)
        cls.classes = {}
        for node in ast.walk(cls.tree):
            if not isinstance(node, ast.ClassDef):
                continue
            methods, attrs, bases = set(), set(), []
            for f in node.body:
                if isinstance(f, ast.FunctionDef):
                    methods.add(f.name)
                # 类体与 __init__/方法里的 `self.xxx = ...` 都是可绑定目标
                # （如 self.var_out = tk.StringVar() 写在 __init__ 里）
                for sub in ast.walk(f):
                    if isinstance(sub, ast.Assign):
                        for t in sub.targets:
                            if isinstance(t, ast.Attribute) \
                                    and isinstance(t.value, ast.Name) \
                                    and t.value.id == "self":
                                attrs.add(t.attr)
            for b in node.bases:
                bases.append(getattr(b, "id", None) or getattr(b, "attr", None))
            cls.classes[node.name] = {"methods": methods, "attrs": attrs,
                                      "bases": [b for b in bases if b]}

    @classmethod
    def _visible(cls, cname, seen=None):
        """类可见的绑定目标 = 自身(方法+属性) + 继承链上游（只解析本文件内的基类）。"""
        seen = seen or set()
        if cname in seen or cname not in cls.classes:
            return set()
        seen.add(cname)
        c = cls.classes[cname]
        out = c["methods"] | c["attrs"]
        for b in c["bases"]:
            out |= cls._visible(b, seen)
        return out

    # ── 1. command= 指向的方法必须存在 ──
    def test_commands_resolve_to_real_methods(self):
        bad = []
        total = 0
        for cls_node in ast.walk(self.tree):
            if not isinstance(cls_node, ast.ClassDef):
                continue
            own = self._visible(cls_node.name)
            for call in ast.walk(cls_node):
                if not isinstance(call, ast.Call):
                    continue
                f = call.func
                name = getattr(f, "attr", None) or getattr(f, "id", None)
                if name not in _CMD_WIDGETS:
                    continue
                for kw in call.keywords:
                    if kw.arg != "command":
                        continue
                    total += 1
                    v = kw.value
                    if isinstance(v, ast.Attribute):
                        want = {v.attr}
                    else:
                        want = _self_attr_names(v)
                    for w in want:
                        if w not in own:
                            bad.append(f"{cls_node.name}.{w}()"
                                       f"（第 {getattr(call, 'lineno', '?')} 行）")
        self.assertTrue(total >= 5, f"只识别到 {total} 个 command=，扫描逻辑可能失效")
        self.assertEqual(bad, [],
                         "以下 command= 指向了不存在的方法：\n  " + "\n  ".join(bad))

    # ── 2. Web 界面出口必须在 ──
    def test_webui_entry_point_present(self):
        self.assertIn("启动本地 Web 界面", self.src,
                      "关于页应保留「启动本地 Web 界面」按钮——非 Windows 用户靠它")
        self.assertIn("def start_webui", self.src)

    # ── 3. 静态 import 必须在（打包靠它收模块） ──
    def test_webui_import_is_static(self):
        found = False
        for n in ast.walk(self.tree):
            if isinstance(n, ast.ImportFrom) and n.module == "app":
                if any(a.name == "webui" for a in n.names):
                    found = True
        self.assertTrue(
            found,
            "app/gui.py 里必须有 `from app import webui` 这条静态 import：\n"
            "PyInstaller 按静态 import 图收模块，删掉它 exe 会静默缺 Web 界面。")

    # ── 4. 入口支持 --web ──
    def test_main_supports_web_flag(self):
        src = (ROOT / "app" / "__main__.py").read_text(encoding="utf-8")
        self.assertIn("--web", src)
        tree = ast.parse(src)
        mods = set()
        for n in ast.walk(tree):
            if isinstance(n, ast.ImportFrom) and n.module == "app.webui":
                mods.add("webui")
        self.assertTrue(mods, "app/__main__.py 应能导入 app.webui 以支持 --web")

    # ── 5. webui 与 core 的委托关系（不许另立实现） ──
    def test_webui_delegates_to_core_only(self):
        src = (ROOT / "app" / "webui.py").read_text(encoding="utf-8")
        tree = ast.parse(src)
        imported = set()
        for n in ast.walk(tree):
            if isinstance(n, ast.Import):
                for a in n.names:
                    imported.add(a.name.split(".")[0])
            elif isinstance(n, ast.ImportFrom) and n.module:
                imported.add(n.module.split(".")[0])
        third = {m for m in imported
                 if m not in {"app", "json", "mimetypes", "os", "tempfile",
                              "threading", "time", "urllib", "webbrowser",
                              "http", "pathlib", "socket", "ipaddress",
                              "sys", "argparse"}}
        self.assertEqual(third, set(), f"webui.py 引入了第三方依赖：{third}")


if __name__ == "__main__":
    unittest.main()
