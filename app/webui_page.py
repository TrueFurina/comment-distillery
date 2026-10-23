#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""本地 Web 界面的**页面资源**（纯数据，无逻辑）。

为什么单独一个文件：
`app/webui.py` 是逻辑（HTTP + 作业调度），本文件只是那一大段 HTML/CSS/JS。
拆开后两边都还能读 —— 混在一起会变成没人敢改的 900 行泥团。

为什么内联而不是拆 .html/.css/.js 三个文件：
本工具承诺"零第三方依赖、单文件可跑"。外链静态文件会让分发形态从 1 个入口
变成 4 个，且打包时要额外 --add-data。内联没有运行时成本。

零第三方依赖，仅标准库。
"""

PAGE_HTML = r"""<!DOCTYPE html>
<html lang="zh-CN">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<title>comment-distillery · 本地界面</title>
<style>
:root{
  --bg:#f6f7f9; --panel:#fff; --panel2:#fbfcfd; --line:#e2e5e9; --line2:#eef1f4;
  --ink:#16191d; --dim:#6b7280; --dim2:#9aa2ad;
  --acc:#2f6feb; --acc-soft:#eaf1fe;
  --ok:#1a7f37; --ok-soft:#e8f5ec; --warn:#9a6700; --warn-soft:#fdf3e0;
  --err:#cf222e; --err-soft:#fdecee;
  --mono:ui-monospace,SFMono-Regular,Menlo,Consolas,"Liberation Mono",monospace;
}
*{box-sizing:border-box}
html,body{margin:0;padding:0}
body{
  background:var(--bg); color:var(--ink);
  font:14px/1.65 system-ui,-apple-system,"Segoe UI","Microsoft YaHei UI",sans-serif;
  -webkit-font-smoothing:antialiased;
}
a{color:var(--acc);text-decoration:none}
a:hover{text-decoration:underline}
code,.mono{font-family:var(--mono)}

/* ── 顶栏 ── */
header{
  position:sticky;top:0;z-index:20;background:var(--panel);
  border-bottom:1px solid var(--line);
}
.hwrap{max-width:1080px;margin:0 auto;padding:14px 22px;display:flex;align-items:center;gap:14px;flex-wrap:wrap}
.brand{font-size:16px;font-weight:650;letter-spacing:-.2px}
.brand .sub{color:var(--dim);font-weight:400;font-size:12.5px;margin-left:8px}
.spacer{flex:1}
.badge{
  display:inline-flex;align-items:center;gap:6px;font-size:12px;padding:4px 10px;
  border-radius:999px;border:1px solid var(--line);background:var(--panel2);color:var(--dim);
}
.badge.ok{background:var(--ok-soft);border-color:#bfe3cb;color:var(--ok)}
.badge.err{background:var(--err-soft);border-color:#f3c6ca;color:var(--err)}
.badge .dot{width:7px;height:7px;border-radius:50%;background:currentColor}
.local{
  font-size:11.5px;color:var(--dim);border:1px dashed var(--line);
  padding:3px 9px;border-radius:6px;background:var(--panel2);
}

/* ── 主体 ── */
main{max-width:1080px;margin:0 auto;padding:22px 22px 80px}
.tabs{display:flex;gap:6px;flex-wrap:wrap;margin-bottom:18px}
.tab{
  border:1px solid var(--line);background:var(--panel);color:var(--dim);
  padding:8px 15px;border-radius:9px;cursor:pointer;font-size:13px;
  transition:.13s;display:flex;align-items:center;gap:7px;
}
.tab:hover{border-color:#cfd5dc;color:var(--ink)}
.tab.on{background:var(--acc);border-color:var(--acc);color:#fff;font-weight:550}
.tab .n{
  font-size:11px;opacity:.75;background:rgba(0,0,0,.07);border-radius:5px;
  padding:1px 6px;font-weight:600;
}
.tab.on .n{background:rgba(255,255,255,.22)}

.card{
  background:var(--panel);border:1px solid var(--line);border-radius:12px;
  padding:20px 22px;margin-bottom:16px;
}
.card h2{margin:0 0 4px;font-size:15.5px;font-weight:620;letter-spacing:-.1px}
.card .desc{margin:0 0 18px;color:var(--dim);font-size:13px;line-height:1.7}

.grid{display:grid;grid-template-columns:1fr 1fr;gap:14px}
@media(max-width:760px){.grid{grid-template-columns:1fr}}
.field{display:flex;flex-direction:column;gap:6px}
.field.full{grid-column:1/-1}
label{font-size:12.5px;color:var(--dim);font-weight:550;display:flex;gap:6px;align-items:center}
label .hint{font-weight:400;color:var(--dim2)}
.row{display:flex;gap:8px}
input[type=text],textarea,select{
  width:100%;border:1px solid var(--line);border-radius:8px;padding:9px 11px;
  font:inherit;font-size:13px;background:var(--panel2);color:var(--ink);outline:none;
}
input[type=text]:focus,textarea:focus{border-color:var(--acc);background:#fff}
textarea{resize:vertical;min-height:64px;font-family:var(--mono);font-size:12.3px;line-height:1.6}
select{background:var(--panel2)}
button{
  font:inherit;font-size:13px;border-radius:8px;border:1px solid var(--line);
  background:var(--panel);color:var(--ink);padding:9px 15px;cursor:pointer;transition:.13s;
}
button:hover:not(:disabled){border-color:#c6ccd4;background:var(--panel2)}
button:disabled{opacity:.5;cursor:not-allowed}
button.pri{background:var(--acc);border-color:var(--acc);color:#fff;font-weight:550;padding:9px 22px}
button.pri:hover:not(:disabled){background:#2559c4;border-color:#2559c4}
button.mini{padding:9px 12px;font-size:12.5px;color:var(--dim);white-space:nowrap}
button.ghost{border-style:dashed;color:var(--dim)}
.acts{display:flex;gap:10px;align-items:center;margin-top:18px;flex-wrap:wrap}
.chk{display:flex;align-items:center;gap:7px;font-size:13px;color:var(--dim);cursor:pointer;user-select:none}
.chk input{width:15px;height:15px;accent-color:var(--acc);cursor:pointer}

/* ── 日志 ── */
.log{
  display:none;margin-top:16px;background:#12151a;color:#d6dbe3;border-radius:10px;
  padding:12px 14px;font-family:var(--mono);font-size:12px;line-height:1.75;
  max-height:260px;overflow:auto;white-space:pre-wrap;word-break:break-all;
}
.log.show{display:block}
.log .t{color:#7d8794}

/* ── 结果 ── */
.res{display:none;margin-top:16px;border-radius:10px;border:1px solid var(--line);overflow:hidden}
.res.show{display:block}
.res .rh{
  padding:11px 16px;font-size:13px;font-weight:600;display:flex;align-items:center;gap:9px;
  border-bottom:1px solid var(--line);
}
.res.ok .rh{background:var(--ok-soft);color:var(--ok)}
.res.err .rh{background:var(--err-soft);color:var(--err)}
.res.warn .rh{background:var(--warn-soft);color:var(--warn)}
.res .rb{padding:14px 16px;font-size:13px;line-height:1.8}
.kv{display:grid;grid-template-columns:auto 1fr;gap:5px 16px;font-size:12.8px}
.kv dt{color:var(--dim);white-space:nowrap}
.kv dd{margin:0;font-family:var(--mono);font-size:12.2px;word-break:break-all}
.files{display:flex;flex-wrap:wrap;gap:6px;margin-top:10px}
.files a{
  font-family:var(--mono);font-size:11.5px;background:var(--panel2);border:1px solid var(--line);
  border-radius:6px;padding:3px 9px;color:var(--acc);
}
.files a:hover{background:var(--acc-soft);text-decoration:none}
.steps{margin-top:10px;font-size:12.5px;color:var(--dim);line-height:1.9}
.steps b{color:var(--ink);font-weight:600}

.note{
  background:var(--acc-soft);border:1px solid #d3e2fd;border-radius:9px;
  padding:11px 14px;font-size:12.8px;color:#1c3d72;line-height:1.75;
}
.note.warn{background:var(--warn-soft);border-color:#f0dcae;color:#6b4a06}

/* ── 文件选择器 ── */
.mask{
  display:none;position:fixed;inset:0;background:rgba(16,19,25,.42);z-index:50;
  align-items:center;justify-content:center;padding:24px;
}
.mask.show{display:flex}
.dlg{
  background:var(--panel);border-radius:13px;width:min(680px,100%);
  max-height:82vh;display:flex;flex-direction:column;overflow:hidden;
  box-shadow:0 18px 48px rgba(16,19,25,.22);
}
.dlg .dh{
  padding:14px 18px;border-bottom:1px solid var(--line);display:flex;align-items:center;gap:12px;
}
.dlg .dh .ti{font-weight:600;font-size:14px}
.dlg .dh path{font-family:var(--mono);font-size:11.5px;color:var(--dim);word-break:break-all}
.dlg .db{flex:1;overflow:auto;padding:8px}
.dlg .df{padding:12px 18px;border-top:1px solid var(--line);display:flex;gap:10px;align-items:center}
.entry{
  display:flex;align-items:center;gap:10px;padding:8px 10px;border-radius:8px;
  cursor:pointer;font-size:13px;
}
.entry:hover{background:var(--panel2)}
.entry .ic{width:18px;text-align:center;flex:none;opacity:.75}
.entry .nm{flex:1;word-break:break-all}
.entry .sz{color:var(--dim2);font-size:11.5px;font-family:var(--mono);flex:none}
.entry.dim{opacity:.42;cursor:default}
.entry.dim:hover{background:none}
.empty{padding:26px;text-align:center;color:var(--dim2);font-size:13px}
.dlg input[type=text]{font-family:var(--mono);font-size:12px}
</style>
</head>
<body>

<header>
  <div class="hwrap">
    <div class="brand">comment-distillery<span class="sub">本地界面</span></div>
    <span class="local" title="只监听 127.0.0.1，不出网、不上传任何数据">🔒 仅本机</span>
    <div class="spacer"></div>
    <span class="badge" id="ck"><span class="dot"></span><span id="ckt">自检中…</span></span>
    <span class="badge" id="ver">—</span>
  </div>
</header>

<main>
  <div class="tabs" id="tabs"></div>

  <!-- 1 采集 -->
  <section class="pane" data-p="crawl">
    <div class="card">
      <h2>① 采集 B 站评论</h2>
      <p class="desc">给视频链接或 BV 号，抓成规范 CSV。<b>可选</b>——你手头已有 CSV 就直接跳到 ②。<br>
      注意：抓取端分页游标重叠会产出重复行，<b>去重交给 ② 预处理</b>，这里不处理。</p>
      <div class="grid">
        <div class="field"><label>视频链接 / BV 号</label>
          <input type="text" id="c_arg" placeholder="https://www.bilibili.com/video/BV1xx411c7XX 或 BV1xx411c7XX"></div>
        <div class="field"><label>输出 CSV</label>
          <div class="row"><input type="text" id="c_out"><button class="mini" data-pick="c_out" data-new="1" data-f="csv">另存为</button></div></div>
      </div>
      <div class="acts">
        <label class="chk"><input type="checkbox" id="c_roots">只要主楼（不抓楼中楼）</label>
        <div class="spacer"></div>
        <button class="pri" data-run="crawl">开始采集</button>
      </div>
      <div class="log" data-log="crawl"></div>
      <div class="res" data-res="crawl"></div>
    </div>
  </section>

  <!-- 2 预处理 -->
  <section class="pane" data-p="prep" hidden>
    <div class="card">
      <h2>② 预处理</h2>
      <p class="desc">原始 CSV → 规范语料（CCF）+ 易读文本 + 统计 + ID 映射。<br>
      <b>先看 <code>dup_dropped</code></b>：数字大说明抓取端分页重叠过，规模数字要以去噪后为准。</p>
      <div class="grid">
        <div class="field"><label>原始语料 CSV</label>
          <div class="row"><input type="text" id="p_in"><button class="mini" data-pick="p_in" data-f="csv">选择</button></div></div>
        <div class="field"><label>输出目录</label>
          <div class="row"><input type="text" id="p_out"><button class="mini" data-pick="p_out" data-dir="1">选择</button></div></div>
        <div class="field"><label>低权重阈值 <span class="hint">点赞 ≤ N 算低权重</span></label>
          <input type="text" id="p_lowmax" value="8"></div>
        <div class="field"><label>长文下限 <span class="hint">低权重里 ≥ N 字算长文</span></label>
          <input type="text" id="p_lowlen" value="120"></div>
      </div>
      <div class="acts"><button class="pri" data-run="prep">开始预处理</button></div>
      <div class="log" data-log="prep"></div>
      <div class="res" data-res="prep"></div>
    </div>
  </section>

  <!-- 3 蒸馏包 -->
  <section class="pane" data-p="pack" hidden>
    <div class="card">
      <h2>③ 导出蒸馏包 <span style="font-weight:400;color:var(--dim);font-size:13px">· 核心一步</span></h2>
      <p class="desc">产出一个文件夹：语料 + 方法论 + 可直接粘贴的提示词。<br>
      <b>把它整个拖进任意 AI</b>，AI 就能按 <code>SKILL.md</code> 产出带引用的深度指南。<br>
      本工具<b>不内置 LLM</b>——不收你的 Key，也不会把上个月的方法论固化进二进制。</p>
      <div class="grid">
        <div class="field"><label>原始语料 CSV</label>
          <div class="row"><input type="text" id="k_in"><button class="mini" data-pick="k_in" data-f="csv">选择</button></div></div>
        <div class="field"><label>输出目录</label>
          <div class="row"><input type="text" id="k_out"><button class="mini" data-pick="k_out" data-dir="1">选择</button></div></div>
        <div class="field full"><label>包名 <span class="hint">留空自动生成</span></label>
          <input type="text" id="k_name" placeholder="例如：早餐真相-2190条"></div>
      </div>
      <div class="acts"><button class="pri" data-run="pack">导出蒸馏包</button></div>
      <div class="log" data-log="pack"></div>
      <div class="res" data-res="pack"></div>
      <div class="note" style="margin-top:14px">
        <b>下一步（在工具外）</b>：把包目录整个拖进你的 AI → 拿到 Markdown 指南 → 回到 <b>④ 引用机验</b> 卡一道 → <b>⑤</b> 出成品。
      </div>
    </div>
  </section>

  <!-- 4 机验 -->
  <section class="pane" data-p="verify" hidden>
    <div class="card">
      <h2>④ 引用真实性机验 <span style="font-weight:400;color:var(--dim);font-size:13px">· 质量门</span></h2>
      <p class="desc">抽出指南里所有 <code>[源:ID|权重N|层级]</code>，与语料真实 ID 求差集。<br>
      <b>差集非空 = 存在幻觉引用 = 不得交付。</b>这一步不靠 AI 自觉，是脚本硬判。</p>
      <div class="grid">
        <div class="field"><label>指南 Markdown</label>
          <div class="row"><input type="text" id="v_guide"><button class="mini" data-pick="v_guide" data-f="md">选择</button></div></div>
        <div class="field"><label>ID 列名 <span class="hint">留空自动识别</span></label>
          <input type="text" id="v_field" placeholder="留空"></div>
        <div class="field full"><label>语料 CSV <span class="hint">每行一个，可多个</span></label>
          <textarea id="v_corpus" placeholder="每行一个绝对路径"></textarea>
          <div class="row"><button class="mini" data-pick="v_corpus" data-f="csv" data-multi="1">＋ 追加语料</button></div></div>
      </div>
      <div class="acts"><button class="pri" data-run="verify">跑机验</button></div>
      <div class="log" data-log="verify"></div>
      <div class="res" data-res="verify"></div>
    </div>
  </section>

  <!-- 5 报告 -->
  <section class="pane" data-p="emit" hidden>
    <div class="card">
      <h2>⑤ 出 HTML 报告</h2>
      <p class="desc">Markdown 指南 → 单文件自包含 HTML（内联样式，可转发、可保存）。<br>
      每条引用渲染成<b>可点击角标</b>，点它跳到附录原句，再点「返回正文」跳回——
      <b>把「可溯源」从一句声明变成可按的交互证据</b>。<br>
      页首信任条直接复用 ④ 的差集结果：差集非空会翻红写「不得交付」。</p>
      <div class="grid">
        <div class="field"><label>指南 Markdown</label>
          <div class="row"><input type="text" id="e_guide"><button class="mini" data-pick="e_guide" data-f="md">选择</button></div></div>
        <div class="field"><label>输出 HTML <span class="hint">留空自动同名</span></label>
          <div class="row"><input type="text" id="e_out"><button class="mini" data-pick="e_out" data-new="1" data-f="html">另存为</button></div></div>
        <div class="field"><label>标题 <span class="hint">留空取首个 H1</span></label>
          <input type="text" id="e_title" placeholder="留空"></div>
        <div class="field"><label>副标题</label><input type="text" id="e_sub" placeholder="留空"></div>
        <div class="field full"><label>语料 CSV <span class="hint">挂原句 + 跑机验，强烈建议填</span></label>
          <textarea id="e_corpus" placeholder="每行一个绝对路径"></textarea>
          <div class="row"><button class="mini" data-pick="e_corpus" data-f="csv" data-multi="1">＋ 追加语料</button></div></div>
      </div>
      <div class="acts">
        <label class="chk"><input type="checkbox" id="e_noverify">跳过机验（会丢掉信任条，不推荐）</label>
        <div class="spacer"></div>
        <button class="pri" data-run="emit">生成报告</button>
      </div>
      <div class="log" data-log="emit"></div>
      <div class="res" data-res="emit"></div>
    </div>
  </section>
</main>

<!-- 文件选择器 -->
<div class="mask" id="mask">
  <div class="dlg">
    <div class="dh"><span class="ti">选择文件</span><span class="path" id="dpath"></span><div class="spacer"></div>
      <button class="mini" id="dup">↑ 上级</button><button class="mini" id="dclose">关闭</button></div>
    <div class="db" id="dbody"><div class="empty">载入中…</div></div>
    <div class="df">
      <input type="text" id="dname" placeholder="文件名（「另存为」时填）">
      <div class="spacer"></div>
      <button class="pri" id="dok">确定</button>
    </div>
  </div>
</div>

<script>
"use strict";
const $ = (s, r) => (r || document).querySelector(s);
const $$ = (s, r) => Array.from((r || document).querySelectorAll(s));

const PANES = [
  ["crawl",  "① 采集"],
  ["prep",   "② 预处理"],
  ["pack",   "③ 蒸馏包"],
  ["verify", "④ 引用机验"],
  ["emit",   "⑤ 出报告"],
];
const FILTERS = {csv: [".csv"], md: [".md", ".markdown"], html: [".html", ".htm"]};

/* ── 标签切换 ── */
function buildTabs(){
  const box = $("#tabs");
  PANES.forEach((p, i) => {
    const b = document.createElement("button");
    b.className = "tab" + (i === 2 ? " on" : "");
    b.innerHTML = '<span class="n">' + (i + 1) + "</span>" + p[1];
    b.onclick = () => {
      $$(".tab").forEach(x => x.classList.remove("on"));
      b.classList.add("on");
      $$(".pane").forEach(s => s.hidden = s.dataset.p !== p[0]);
    };
    box.appendChild(b);
  });
}

/* ── 接口 ── */
async function api(url, opt){
  const r = await fetch(url, opt);
  if (!r.ok) throw new Error("HTTP " + r.status);
  return r.json();
}
async function post(path, body){
  return api(path, {method: "POST", headers: {"Content-Type": "application/json"},
                    body: JSON.stringify(body)});
}

/* ── 文件选择器 ── */
let PK = null;   // {target, filter, dir, multi, isNew}
function openPicker(btn){
  PK = {
    target: btn.dataset.pick, filter: btn.dataset.f || "",
    dir: !!btn.dataset.dir, multi: !!btn.dataset.multi, isNew: !!btn.dataset["new"],
  };
  $("#dname").value = "";
  $("#dname").style.display = PK.isNew ? "" : "none";
  $("#mask").classList.add("show");
  browse("");
}
async function browse(p){
  const q = p ? ("?path=" + encodeURIComponent(p)) : "";
  let d;
  try { d = await api("/api/fs" + q); }
  catch(e){ $("#dbody").innerHTML = '<div class="empty">读取失败：' + e.message + "</div>"; return; }
  if (d.error){ $("#dbody").innerHTML = '<div class="empty">' + d.error + "</div>"; return; }
  $("#dpath").textContent = d.path;
  $("#dbody").dataset.cur = d.path;
  const exts = FILTERS[PK.filter] || null;
  const rows = [];
  rows.push(rowHtml({name: "..", path: d.parent || "", is_dir: true}, true));
  d.entries.forEach(e => {
    if (e.is_dir){ rows.push(rowHtml(e, true)); return; }
    const ok = !PK.dir && (!exts || exts.some(x => e.name.toLowerCase().endsWith(x)));
    rows.push(rowHtml(e, ok));
  });
  $("#dbody").innerHTML = rows.join("") ||
    '<div class="empty">这一层没有可选的文件</div>';
  $$("#dbody .entry").forEach(el => {
    if (el.classList.contains("dim") && el.dataset.name !== "..") return;
    el.onclick = () => {
      if (el.dataset.dir === "1"){ browse(el.dataset.path); return; }
      if (el.dataset.name === ".."){ browse(el.dataset.path); return; }
      $("#dname").value = el.dataset.path;
    };
    el.ondblclick = () => { if (el.dataset.dir === "1") browse(el.dataset.path); else okPick(); };
  });
}
function rowHtml(e, selectable){
  const icon = e.is_dir ? "📁" : "📄";
  return '<div class="entry' + (selectable ? "" : " dim") + '" data-name="' +
    esc(e.name) + '" data-path="' + esc(e.path) + '" data-dir="' + (e.is_dir ? 1 : 0) + '">' +
    '<span class="ic">' + icon + '</span><span class="nm">' + esc(e.name) + "</span>" +
    '<span class="sz">' + (e.size != null ? kb(e.size) : "") + "</span></div>";
}
function esc(s){ return String(s).replace(/[&<>"]/g, c => ({"&":"&amp;","<":"&lt;",">":"&gt;",'"':"&quot;"}[c])); }
function kb(n){ return n < 1024 ? n + " B" : n < 1048576 ? (n/1024).toFixed(1) + " KB" : (n/1048576).toFixed(1) + " MB"; }
function okPick(){
  let v = $("#dname").value.trim();
  if (PK.isNew && v && !/[\\/]/.test(v)) v = ($("#dbody").dataset.cur || "").replace(/[\\/]+$/, "") + "/" + v;
  if (v){
    const t = $("#" + PK.target);
    if (PK.multi && t.value.trim()) t.value = t.value.replace(/\s*$/, "") + "\n" + v;
    else t.value = v;
  }
  closePicker();
}
function closePicker(){ $("#mask").classList.remove("show"); }

/* ── 运行作业 ── */
const JOBS = {};
function paneOf(a){ return $$(".pane").find(s => s.dataset.p === a); }
function setBusy(a, on, label){
  const b = paneOf(a).querySelector("[data-run]");
  b.disabled = on;
  b.textContent = on ? (label || "运行中…") : b.dataset.label || b.textContent;
  if (on) b.dataset.label = b.dataset.label || label || "运行中…";
}
function logBox(a){ return paneOf(a).querySelector('[data-log="' + a + '"]'); }
function resBox(a){ return paneOf(a).querySelector('[data-res="' + a + '"]'); }

function num(id, dflt){
  const v = parseFloat($("#" + id).value);
  return isNaN(v) ? dflt : v;
}
function lines(id){
  return $("#" + id).value.split(/\r?\n/).map(s => s.trim()).filter(Boolean);
}

const BUILDERS = {
  crawl: () => ({arg: $("#c_arg").value.trim(), out: $("#c_out").value.trim(),
                 roots_only: $("#c_roots").checked}),
  prep:  () => ({input: $("#p_in").value.trim(), outdir: $("#p_out").value.trim(),
                 low_max: num("p_lowmax", 8), low_min_len: num("p_lowlen", 120)}),
  pack:  () => ({input: $("#k_in").value.trim(), outdir: $("#k_out").value.trim(),
                 name: $("#k_name").value.trim(),
                 low_max: num("p_lowmax", 8), low_min_len: num("p_lowlen", 120)}),
  verify:() => ({guide: $("#v_guide").value.trim(), corpora: lines("v_corpus"),
                 field: $("#v_field").value.trim() || null}),
  emit:  () => ({guide: $("#e_guide").value.trim(), out: $("#e_out").value.trim() || null,
                 corpora: lines("e_corpus"), title: $("#e_title").value.trim() || null,
                 subtitle: $("#e_sub").value.trim() || null,
                 no_verify: $("#e_noverify").checked}),
};

async function run(a){
  const box = logBox(a), rbox = resBox(a);
  box.textContent = ""; box.classList.add("show");
  rbox.className = "res"; rbox.innerHTML = "";
  setBusy(a, true);
  let payload;
  try { payload = BUILDERS[a](); }
  catch(e){ return fail(a, "参数读取失败：" + e.message); }
  try {
    const r = await post("/api/start", {action: a, params: payload});
    if (r.error) return fail(a, r.error);
    poll(a, r.job);
  } catch(e){ fail(a, "请求失败：" + e.message); }
}

function poll(a, id){
  JOBS[a] = id;
  const box = logBox(a), rbox = resBox(a);
  const tick = async () => {
    let d;
    try { d = await api("/api/job?id=" + encodeURIComponent(id)); }
    catch(e){ return fail(a, "轮询失败：" + e.message); }
    const t = new Date().toLocaleTimeString("zh-CN", {hour12: false});
    box.textContent = (d.log || []).map(l => l).join("\n");
    box.scrollTop = box.scrollHeight;
    if (!d.done){ setTimeout(tick, 400); return; }
    setBusy(a, false);
    if (d.error) return fail(a, d.error);
    showRes(a, d.result || {});
  };
  tick();
}
function fail(a, msg){
  setBusy(a, false);
  const r = resBox(a);
  r.className = "res err show";
  r.innerHTML = '<div class="rh">✗ 失败</div><div class="rb">' + esc(msg) + "</div>";
}

function showRes(a, d){
  const r = resBox(a);
  const body = RENDER[a] ? RENDER[a](d) : "";
  const cls = d.cls || "ok", head = d.head || "✓ 完成";
  r.className = "res " + cls + " show";
  r.innerHTML = '<div class="rh">' + esc(head) + '</div><div class="rb">' + body + "</div>";
}

const RENDER = {
  crawl(d){
    return kv(d.kv || {}) + files(d.files);
  },
  prep(d){
    return kv(d.kv || {}) + files(d.files) +
      '<div class="steps">' + esc(d.next || "下一步：③ 导出蒸馏包") + "</div>";
  },
  pack(d){
    return '<div class="steps">' + esc(d.next || "") + "</div>" + kv(d.kv || {}) + files(d.files);
  },
  verify(d){
    let s = '<div class="steps">' + d.verdict + "</div>";
    if (d.bad && d.bad.length){
      s += '<div style="margin-top:10px;color:var(--err);font-family:var(--mono);font-size:12px">' +
           "幻觉引用：" + esc(d.bad.join("、")) + "</div>";
    }
    return s + kv(d.kv || {});
  },
  emit(d){
    let s = '<div class="steps">' + d.verdict + "</div>";
    if (d.out){
      s += '<div style="margin-top:12px;display:flex;gap:8px;flex-wrap:wrap">' +
        '<a href="/preview?path=' + encodeURIComponent(d.out) + '" target="_blank" ' +
        'style="background:var(--acc);color:#fff;border-radius:8px;padding:8px 16px;font-size:13px;font-weight:550">↗ 打开报告</a>' +
        '<a href="/download?path=' + encodeURIComponent(d.out) + '" ' +
        'style="border:1px solid var(--line);border-radius:8px;padding:8px 14px;font-size:13px">⬇ 下载 HTML</a>' +
        "</div>";
    }
    return s + kv(d.kv || {});
  },
};
function kv(o){
  const ks = Object.keys(o);
  if (!ks.length) return "";
  return '<dl class="kv">' + ks.map(k => "<dt>" + esc(k) + "</dt><dd>" + esc(o[k]) + "</dd>").join("") + "</dl>";
}
function files(fs){
  if (!fs || !fs.length) return "";
  return '<div class="files">' + fs.map(f =>
    '<a href="/download?path=' + encodeURIComponent(f.path) + '" target="_blank">' +
    esc(f.name) + "</a>").join("") + "</div>";
}

/* ── 启动 ── */
async function boot(){
  buildTabs();
  $$("[data-run]").forEach(b => b.onclick = () => run(b.dataset.run));
  $$("[data-pick]").forEach(b => b.onclick = () => openPicker(b));
  $("#dclose").onclick = closePicker;
  $("#dup").onclick = () => browse($("#dbody").dataset.parent || "");
  $("#dok").onclick = okPick;
  $("#mask").onclick = e => { if (e.target.id === "mask") closePicker(); };
  document.addEventListener("keydown", e => { if (e.key === "Escape") closePicker(); });

  try {
    const h = await api("/api/hello");
    $("#ver").textContent = "v" + h.version;
    const ck = $("#ck");
    ck.className = "badge " + (h.selfcheck.ok ? "ok" : "err");
    $("#ckt").textContent = h.selfcheck.ok ? "自检通过 · 资源齐全" : "自检失败 · 缺资源";
    ck.title = (h.selfcheck.msgs || []).map(m => (m[0] ? "✓ " : "✗ ") + m[1]).join("\n");
    $$('input[id$="_out"]').forEach(i => { if (!i.value) i.value = h.outdir; });
    $$('input[id$="_in"]').forEach(i => { if (!i.value) i.value = ""; });
    $("#p_out").value = h.outdir; $("#k_out").value = h.outdir;
    if (h.sample_corpus){ $("#p_in").value = h.sample_corpus; $("#k_in").value = h.sample_corpus; }
    if (h.sample_guide){
      $("#v_guide").value = h.sample_guide; $("#e_guide").value = h.sample_guide;
      if (!$("#v_corpus").value && h.sample_corpus) $("#v_corpus").value = h.sample_corpus;
      if (!$("#e_corpus").value && h.sample_corpus) $("#e_corpus").value = h.sample_corpus;
    }
  } catch(e){
    $("#ck").className = "badge err"; $("#ckt").textContent = "无法连接后端";
  }
}
boot();
</script>
</body>
</html>
"""
