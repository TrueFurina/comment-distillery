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

  <!-- 0 一键完成 -->
  <section class="pane" data-p="auto">
    <div class="card">
      <h2>⚡ 一键完成</h2>
      <p class="desc">给一个视频链接或 BV 号，<b>一次跑到底</b>：采集 → 预处理 → 蒸馏包，
      配了 AI 就继续写指南 → 引用机验 → 出 HTML 报告。没配 AI 就停在一个能直接拖进
      任意对话框的成品目录。<br>
      不需要一步步点；下面各页是同一套流程的手动版，需要细调参数时才用。</p>
      <div class="grid">
        <div class="field full"><label>视频链接 / BV 号 <span class="hint">也可以填一份现成的 CSV 路径，那样跳过采集</span></label>
          <input type="text" id="a_arg" placeholder="https://www.bilibili.com/video/BV1xx411c7XX 或 BV1xx411c7XX"></div>
        <div class="field"><label>输出根目录</label>
          <div class="row"><input type="text" id="a_out"><button class="mini" data-pick="a_out" data-dir="1">选择</button></div></div>
        <div class="field"><label>包名 <span class="hint">留空自动按时间生成</span></label>
          <input type="text" id="a_name" placeholder="例如：早餐真相-2190条"></div>
      </div>
      <div class="field full" id="paste_box" style="margin-top:12px">
        <label>或者：直接粘贴你的文本 <span class="hint">一行一条（评论 / 问卷 / 访谈）；只落本次演示的沙箱，不联网、不上传别处</span></label>
        <textarea id="a_paste" rows="6" placeholder="把一群人七嘴八舌的原文粘到这里，一行一条。例：&#10;这个面霜太油了&#10;敏感肌用着刺痛&#10;回购第三次了"></textarea>
        <div class="acts" style="margin-top:8px">
          <button class="mini" id="a_upload">使用我的文本</button>
          <span class="hint" id="a_upload_hint"></span>
        </div>
      </div>
      <div class="acts">
        <label class="chk"><input type="checkbox" id="a_roots" checked>只抓主楼（快 3 倍）</label>
        <label class="chk"><input type="checkbox" id="a_gloss">生成黑话提示
          <span class="hint">（圈内术语/疑似错字，帮 AI 别按字面读错）</span></label>
        <div class="spacer"></div>
        <button class="pri" data-run="auto">一键跑完</button>
        <button class="ghost" data-stop="auto" hidden>停止</button>
      </div>
      <div class="log" data-log="auto"></div>
      <div class="res" data-res="auto"></div>
      <div class="note" style="margin-top:14px" id="ai_note">
        <b>同一个按钮，走到哪一步取决于你是否配了 AI：</b><br>
        · <b>没配</b> → 采集 → 预处理 → 蒸馏包，拿到一个可直接拖进任意对话框的目录（零 Key、零成本）。<br>
        · <b>配了</b> → 再往下：AI 写指南 → 引用机验 → 出 HTML 报告，全程不用手动。<br>
        模型和额度都在你这边；本工具不内置模型、不代付、Key 不进日志。
        <a href="#" onclick="goTab('ai');return false;">去配 AI →</a>
      </div>
    </div>
  </section>

  <!-- AI 设置 -->
  <section class="pane" data-p="ai" hidden>
    <div class="card">
      <h2>🤖 AI 设置（可选）</h2>
      <p class="desc">填了这里，「一键出报告」才能跑到最后。<b>不填也完全可用</b>——那时一键只出蒸馏包，
      你自己把包拖进任意 AI。<br>
      支持任何 <b>OpenAI 兼容</b>接口：DeepSeek、通义、Kimi、智谱、OpenAI、本地 Ollama / vLLM 都行。
      填的是<b>你自己的</b> Key，本工具不内置模型、不代付、不转存。</p>

      <div class="grid">
        <div class="field full"><label>Base URL <span class="hint">到 /v1 为止，不要带 /chat/completions</span></label>
          <input type="text" id="m_base" placeholder="https://api.deepseek.com/v1"></div>
        <div class="field"><label>模型名</label>
          <input type="text" id="m_model" placeholder="deepseek-chat"></div>
        <div class="field"><label>API Key <span class="hint">推荐环境变量 CD_LLM_API_KEY（不落盘）；也可填这里存本机 llm.json（明文）</span></label>
          <input type="password" id="m_key" placeholder="留空表示不改动已保存的 Key"></div>
        <div class="field"><label>语料上限（字符） <span class="hint">超了会保留头尾并标注省略</span></label>
          <input type="text" id="m_chars" value="120000"></div>
        <div class="field"><label>单次超时（秒）</label>
          <input type="text" id="m_timeout" value="600"></div>
      </div>

      <div class="acts">
        <button class="pri" id="m_save">保存</button>
        <button class="ghost" id="m_test">测试连通</button>
        <div class="spacer"></div>
        <span class="hint" id="m_state">读取中…</span>
      </div>
      <div class="log" id="m_log"></div>

      <div class="note" style="margin-top:14px">
        <b>成本提示</b>：一次蒸馏 = 1 次生成 + 最多 2 次修引用。以 2,000 条语料为例，约 6–12 万字符输入，
        按各家中档模型价格大致在几毛到两三元一次。AI 只写指南，<b>不参与采集与机验</b>。<br>
        <b>写盘位置</b>：<code id="m_path">—</code>（已列入 .gitignore，不会被提交）<br>
        <b>推荐</b>：用环境变量 <code>CD_LLM_API_KEY</code> / <code>CD_LLM_BASE_URL</code> / <code>CD_LLM_MODEL</code> 注入配置，最干净、不落盘、不随项目走。<br>
        <b>注意</b>：配置文件跟着<b>程序</b>走，不是跟着你走。源码运行在仓库根，
        双击 exe 时在 <b>exe 所在目录</b>。换目录/换机器后要重新填，或把 <code>llm.json</code> 一起带过去。
      </div>
    </div>
  </section>

  <!-- 1 采集 -->
  <section class="pane" data-p="crawl" hidden>
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
        <label class="chk"><input type="checkbox" id="c_roots" checked>只要主楼（不抓楼中楼）</label>
        <div class="spacer"></div>
        <button class="pri" data-run="crawl">开始采集</button>
        <button class="ghost" data-stop="crawl" hidden>停止</button>
      </div>
      <div class="note" id="c_hint" style="margin-top:12px">
        默认只抓主楼：绝大多数观点都在主楼，几分钟能跑完。
        取消勾选会连楼中楼一起抓，同一个视频可能从 4 分钟变成十几分钟——中途可点「停止」，
        已抓到的部分会照常保留。
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
      <b>两种用法：</b>配了 AI 就在本页继续跑（下方「只跑 AI 蒸馏」），
      没配就把文件夹<b>整个拖进任意 AI</b>，它按 <code>SKILL.md</code> 产出带引用的指南。<br>
      <b>不内置模型</b>：配 AI 用的是你自己的 endpoint 与 Key，工具不代付、不转存；
      方法论每次从当前 <code>SKILL.md</code> 现读，不会固化进二进制。</p>
      <div class="grid">
        <div class="field"><label>原始语料 CSV</label>
          <div class="row"><input type="text" id="k_in"><button class="mini" data-pick="k_in" data-f="csv">选择</button></div></div>
        <div class="field"><label>输出目录</label>
          <div class="row"><input type="text" id="k_out"><button class="mini" data-pick="k_out" data-dir="1">选择</button></div></div>
        <div class="field full"><label>包名 <span class="hint">留空自动生成</span></label>
          <input type="text" id="k_name" placeholder="例如：早餐真相-2190条"></div>
      </div>
      <div class="acts">
        <label class="chk"><input type="checkbox" id="k_gloss">生成黑话提示</label>
        <div class="spacer"></div>
        <button class="pri" data-run="pack">导出蒸馏包</button>
      </div>
      <div class="note" style="margin-top:14px">
        <b>已有一个包，只想补跑 AI？</b> 填下面的包目录，直接生成指南（需先在「🤖 AI 设置」配好）。
        没配 AI 时这里有提示，不会静默失败。
        <div class="grid" style="margin-top:10px">
          <div class="field full"><label>蒸馏包目录 <span class="hint">含 corpus_ccf.csv 的那一层</span></label>
            <div class="row"><input type="text" id="k_pack" placeholder="E:/.../output/distill-20261030-031221">
              <button class="mini" data-pick="k_pack" data-dir="1">选择</button></div></div>
        </div>
        <div class="acts" style="margin-top:10px">
          <button class="pri alt" data-run="distill">只跑 AI 蒸馏</button>
        </div>
        <div class="log" data-log="distill"></div>
        <div class="res" data-res="distill"></div>
      </div>
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
  ["auto",   "⚡ 一键完成"],
  ["ai",     "🤖 AI 设置"],
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
  // 默认高亮必须和默认可见面板一致：之前把第 3 个页签写死成 on，
  // 而 HTML 里默认显示的是 ① 采集 —— 用户看到"选中的是③、内容是①"，
  // 点③才第一次对齐，等于让用户先怀疑一遍这软件是不是坏了。
  const first = $(".pane:not([hidden])");
  const firstKey = first ? first.dataset.p : (PANES[0] && PANES[0][0]);
  // 编号只给"有先后顺序的步骤"：⚡ 与 AI 设置不属于第几步，
  // 给它们编 1、2 会把 ① 采集挤成"3"，读起来像顺序错乱。
  const NO_NUM = new Set(["auto", "ai"]);
  let step = 0;
  PANES.forEach(p => {
    const b = document.createElement("button");
    b.className = "tab" + (p[0] === firstKey ? " on" : "");
    b.dataset.k = p[0];
    const num = NO_NUM.has(p[0]) ? "" : String(++step);
    b.innerHTML = num ? '<span class="n">' + num + "</span>" + p[1] : p[1];
    b.onclick = () => goTab(p[0], b);
    box.appendChild(b);
  });
}
/* 按 key 切页签。设置页与结果页要能互相跳（"去配 AI"、失败后"回去重跑"），
   所以抽成函数，不绑死在按钮的 onclick 里。 */
function goTab(key, btn){
  const tabBtn = btn || $$(".tab").find(x => x.dataset.k === key);
  $$(".tab").forEach(x => x.classList.remove("on"));
  if (tabBtn){ tabBtn.classList.add("on"); tabBtn.scrollIntoView({block:"nearest"}); }
  $$(".pane").forEach(s => s.hidden = s.dataset.p !== key);
}

/* ── 接口 ── */
const TOKEN = new URLSearchParams(location.search).get("token") || "";
function authHeaders(extra){
  const h = extra || {};
  if (TOKEN) h["Authorization"] = "Bearer " + TOKEN;
  return h;
}
function tokParam(){
  return TOKEN ? ("&token=" + encodeURIComponent(TOKEN)) : "";
}
async function api(url, opt){
  opt = opt || {};
  opt.headers = authHeaders(opt.headers);
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
// 一个页签可能挂多个动作（「一键完成」同时有 auto / full）：
// 日志框、结果框、停止键都归属页签，不归属动作。
const RUNPANE = {distill: "pack"};
function paneOf(a){ return $$(".pane").find(s => s.dataset.p === (RUNPANE[a] || a)); }
function setBusy(a, on, label){
  // auto 与 full 共用「一键完成」这一页，所以不能笼统取页内第一个按钮——
  // 那样点「一键出报告」会把「跑到蒸馏包」那个按钮改成"运行中"。
  const b = paneOf(RUNPANE[a] || a).querySelector('[data-run="' + a + '"]')
          || paneOf(a).querySelector("[data-run]");
  b.disabled = on;
  if (on){
    // 原件标签必须在**还没被改写**的这一刻存下来。
    // 旧写法把 "运行中…" 也存进 dataset.label，于是任务结束后
    // 按钮还原成"运行中…"并且 disabled 已放开 —— 看上去永远在跑。
    if (!b.dataset.label) b.dataset.label = b.textContent.trim();
    b.textContent = label || "运行中…";
  } else {
    b.textContent = b.dataset.label || "运行";
  }
  // 有「停止」按钮的步骤（如采集）在跑的时候才把它露出来
  const s = paneOf(RUNPANE[a] || a).querySelector("[data-stop]");
  if (s) s.hidden = !on;
}
function logBox(a){
  const p = paneOf(a);
  return p.querySelector('[data-log="' + a + '"]') || p.querySelector("[data-log]");
}
function resBox(a){
  const p = paneOf(a);
  return p.querySelector('[data-res="' + a + '"]') || p.querySelector("[data-res]");
}

function num(id, dflt){
  const v = parseFloat($("#" + id).value);
  return isNaN(v) ? dflt : v;
}
function lines(id){
  return $("#" + id).value.split(/\r?\n/).map(s => s.trim()).filter(Boolean);
}

const BUILDERS = {
  auto:  () => ({arg: $("#a_arg").value.trim(), outdir: $("#a_out").value.trim(),
                 name: $("#a_name").value.trim(),
                 roots_only: $("#a_roots").checked,
                 with_glossary: $("#a_gloss").checked,
                 low_max: num("p_lowmax", 8), low_min_len: num("p_lowlen", 120)}),
  // full 与 auto 吃同一组输入，只在"要不要继续跑 AI"上不同
  distill: () => ({pack_dir: $("#k_pack").value.trim()}),
  crawl: () => ({arg: $("#c_arg").value.trim(), out: $("#c_out").value.trim(),
                 roots_only: $("#c_roots").checked}),
  prep:  () => ({input: $("#p_in").value.trim(), outdir: $("#p_out").value.trim(),
                 low_max: num("p_lowmax", 8), low_min_len: num("p_lowlen", 120)}),
  pack:  () => ({input: $("#k_in").value.trim(), outdir: $("#k_out").value.trim(),
                 name: $("#k_name").value.trim(),
                 with_glossary: $("#k_gloss").checked,
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
    // 主动停止不是失败：别拿红框喊"失败"，用户会以为程序坏了
    if (d.status === "cancelled"){
      return showRes(a, Object.assign({cls:"warn", head:"⏹ 已停止（部分结果）"}, d.result || {}));
    }
    if (d.error) return fail(a, d.error);
    showRes(a, d.result || {});
  };
  tick();
}

async function stop(a){
  const id = JOBS[a];
  if (!id) return;
  const btn = paneOf(a).querySelector("[data-stop]");
  if (btn){ btn.disabled = true; btn.textContent = "正在停止…"; }
  try { await post("/api/cancel", {job: id}); }
  catch(e){ /* 轮询会看到最终状态，这里不吵 */ }
  if (btn){ btn.disabled = false; btn.textContent = "停止"; }
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
  auto(d){
    let s = "";
    // 报告是"一键到底"的最终交付物，必须能一键打开。
    // 没有这段，用户看到"🎉 报告已生成"却在页面上找不到入口——
    // 只能从文件列表里下载 HTML，体验上等于没完成。
    const rep = (d.kv || {})["报告"];
    if (rep){
      s += '<div style="margin:12px 0;display:flex;gap:8px;flex-wrap:wrap">' +
        '<a href="/preview?path=' + encodeURIComponent(rep) + tokParam() + '" target="_blank" ' +
        'style="background:var(--acc);color:#fff;border-radius:8px;padding:8px 16px;font-size:13px;font-weight:550">↗ 打开报告</a>' +
        '<a href="/download?path=' + encodeURIComponent(rep) + tokParam() + '" ' +
        'style="border:1px solid var(--line);border-radius:8px;padding:8px 14px;font-size:13px">⬇ 下载 HTML</a>' +
        "</div>";
    }
    if (d.verdict) s += '<div class="steps">' + d.verdict + "</div>";
    s += kv(d.kv || {}) + files(d.files);
    if (d.next) s += '<div class="steps"><b>下一步</b>：' + esc(d.next) + "</div>";
    return s;
  },
  crawl(d){
    return kv(d.kv || {}) + files(d.files) +
      (d.next ? '<div class="steps">' + esc(d.next) + "</div>" : "");
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
  distill(d){
    let s = '<div class="steps">' + (d.verdict || "") + "</div>";
    if (d.bad && d.bad.length){
      s += '<div style="margin-top:10px;color:var(--err);font-family:var(--mono);font-size:12px">' +
           "幻觉引用：" + esc(d.bad.join("、")) + "</div>";
    }
    return s + kv(d.kv || {}) + files(d.files) +
      (d.next ? '<div class="steps">' + esc(d.next) + "</div>" : "");
  },
  emit(d){
    let s = '<div class="steps">' + d.verdict + "</div>";
    if (d.out){
      s += '<div style="margin-top:12px;display:flex;gap:8px;flex-wrap:wrap">' +
        '<a href="/preview?path=' + encodeURIComponent(d.out) + tokParam() + '" target="_blank" ' +
        'style="background:var(--acc);color:#fff;border-radius:8px;padding:8px 16px;font-size:13px;font-weight:550">↗ 打开报告</a>' +
        '<a href="/download?path=' + encodeURIComponent(d.out) + tokParam() + '" ' +
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
    '<a href="/download?path=' + encodeURIComponent(f.path) + tokParam() + '" target="_blank">' +
    esc(f.name) + "</a>").join("") + "</div>";
}

/* ── AI 设置 ── */
function mlog(msg){
  const b = $("#m_log");
  b.classList.add("show");
  b.textContent = msg;
}
async function loadLLM(){
  try {
    const d = await api("/api/llm");
    if (d.configured){
      $("#m_base").value = d.base_url || "";
      $("#m_model").value = d.model || "";
      $("#m_state").textContent = "已配置：" + (d.model || "") ;
      $("#m_state").style.color = "var(--ok)";
      $("#ai_note").dataset.on = "1";
    } else {
      $("#m_state").textContent = "未配置 → 一键只到蒸馏包";
      $("#m_state").style.color = "var(--muted)";
      $("#ai_note").dataset.on = "0";
    }
    $("#m_path").textContent = d.path || "—";
  } catch(e){
    $("#m_state").textContent = "读取失败：" + e.message;
  }
}
async function saveLLM(){
  const btn = $("#m_save");
  btn.disabled = true;
  try {
    const r = await post("/api/llm", {
      base_url: $("#m_base").value.trim(),
      model: $("#m_model").value.trim(),
      api_key: $("#m_key").value,          // 留空 = 不改已存的 Key
      timeout: num("m_timeout", 600),
      max_corpus_chars: num("m_chars", 120000),
    });
    if (r.error) return mlog("✗ " + r.error);
    $("#m_key").value = "";
    mlog("✓ 已保存到 " + r.path + "\n" + (r.status || {}).describe);
    await loadLLM();
  } catch(e){ mlog("✗ 保存失败：" + e.message); }
  finally { btn.disabled = false; }
}
async function testLLM(){
  const btn = $("#m_test");
  btn.disabled = true;
  mlog("正在发一条最小请求…（用的是已保存的配置，改了记得先保存）");
  try {
    const r = await post("/api/llm/test", {});
    if (r.ok) mlog("✓ 连通（" + r.elapsed + "s），模型回复：" + (r.reply || ""));
    else mlog("✗ " + (r.error || "失败"));
  } catch(e){ mlog("✗ " + e.message); }
  finally { btn.disabled = false; }
}

/* ── 启动 ── */
async function boot(){
  buildTabs();
  $$("[data-run]").forEach(b => b.onclick = () => run(b.dataset.run));
  $$("[data-stop]").forEach(b => b.onclick = () => stop(b.dataset.stop));
  $$("[data-pick]").forEach(b => b.onclick = () => openPicker(b));
  $("#m_save").onclick = saveLLM;
  $("#m_test").onclick = testLLM;
  loadLLM();
  $("#dclose").onclick = closePicker;
  $("#dup").onclick = () => browse($("#dbody").dataset.parent || "");
  $("#dok").onclick = okPick;
  $("#mask").onclick = e => { if (e.target.id === "mask") closePicker(); };
  document.addEventListener("keydown", e => { if (e.key === "Escape") closePicker(); });

  // 「粘贴文本」上传（公开 demo 的主要输入方式；本地模式也可用）
  const upBtn = $("#a_upload");
  if (upBtn) upBtn.onclick = async () => {
    const t = $("#a_paste").value.trim();
    const hint = $("#a_upload_hint");
    if (!t){ hint.textContent = "先粘贴点文本"; return; }
    upBtn.disabled = true; hint.textContent = "上传中…";
    try {
      const r = await post("/api/upload", {text: t});
      if (r.error){ hint.textContent = r.error; return; }
      $("#a_arg").value = r.file;
      hint.textContent = "已接收 " + r.count + " 行 → " + r.file + "，现在点「一键跑完」";
    } catch(e){
      hint.textContent = "上传失败：" + e.message;
    } finally {
      upBtn.disabled = false;
    }
  };

  try {
    const h = await api("/api/hello");
    $("#ver").textContent = "v" + h.version;
    const ck = $("#ck");
    ck.className = "badge " + (h.selfcheck.ok ? "ok" : "err");
    $("#ckt").textContent = h.selfcheck.ok ? "自检通过 · 资源齐全" : "自检失败 · 缺资源";
    ck.title = (h.selfcheck.msgs || []).map(m => (m[0] ? "✓ " : "✗ ") + m[1]).join("\n");
    if (h.mode === "public"){
      const lb = document.querySelector(".local");
      if (lb){ lb.textContent = "🔓 公开（令牌）"; lb.title = "公开托管模式：需令牌访问，文件限制在沙箱内"; }
    } else if (h.mode === "lan"){
      const lb = document.querySelector(".local");
      if (lb){ lb.textContent = "🌐 局域网（令牌）"; lb.title = "局域网模式：同网段设备凭令牌访问，文件选择器可用，功能全开"; }
    }
    // 只有「输出目录」类字段才预填默认目录。
    // *_out 里混着两类语义：p_out / k_out 是目录，c_out / e_out 是文件路径。
    // 早先用 input[id$="_out"] 一刀切，把目录名填进了文件名位置，
    // ① 采集和 ⑤ 报告会在写盘时抛 PermissionError / IsADirectoryError。
    $("#p_out").value = h.outdir; $("#k_out").value = h.outdir;
    const cOut = $("#c_out"), eOut = $("#e_out");
    const aOut = $("#a_out");
    if (aOut && !aOut.value) aOut.value = h.outdir;
    if (cOut && !cOut.value) cOut.value = h.outdir + "\\comments.csv";
    if (eOut && !eOut.value) eOut.value = h.outdir + "\\report.html";
    if (h.sample_corpus){ $("#p_in").value = h.sample_corpus; $("#k_in").value = h.sample_corpus; }
    if (h.sample_guide){
      $("#v_guide").value = h.sample_guide; $("#e_guide").value = h.sample_guide;
      if (!$("#v_corpus").value && h.sample_corpus) $("#v_corpus").value = h.sample_corpus;
      if (!$("#e_corpus").value && h.sample_corpus) $("#e_corpus").value = h.sample_corpus;
    }
    restoreForm();   // 有上次填过的就盖回默认值
    bindFormMemory();
  } catch(e){
    $("#ck").className = "badge err"; $("#ckt").textContent = "无法连接后端";
  }
}

/* ── 表单记忆 ──
   五个步骤是一条长链，用户可能中途去改别的东西、手一抖关了页面、或者刷新。
   没有记忆时所有填过的路径全部归零，得从头再选一遍——这不是"够用"，
   是逼人重做。存 localStorage 只是路径字符串，不碰任何语料内容。 */
const MEMKEY = "cd.form.v1";
const MEM_IDS = ["a_arg","a_out","a_name","c_arg","c_out","p_in","p_out","p_lowmax","p_lowlen",
                 "k_in","k_out","k_name","v_guide","v_field","v_corpus",
                 "e_guide","e_out","e_title","e_sub","e_corpus"];

function restoreForm(){
  let saved = {};
  try { saved = JSON.parse(localStorage.getItem(MEMKEY) || "{}") || {}; } catch(e){ saved = {}; }
  // 表单记忆里可能存着旧版本算坏的路径：参数一旦混入 CR/LF/NUL，
  // 再回填就会把脏值永久带下去，刷新也修不好。
  // 这里丢掉控制字符，并顺手清掉存档，让下次重算默认值。
  const cleanInput = (v) => String(v).replace(/[\u0000-\u001f\u007f]/g, "");
  let memDirty = false;
  MEM_IDS.forEach(id => {
    const el = document.getElementById(id);
    if (!el || typeof saved[id] !== "string" || !saved[id]) return;
    const v = cleanInput(saved[id]);
    // 存档本身是脏的（含控制字符）：直接丢掉这一项，不回填半截值，
    // 让页面后面用 h.outdir 重新算一遍默认路径。
    if (v !== saved[id]) { memDirty = true; return; }
    if (v) el.value = v;
  });
  if (memDirty) {
    try { localStorage.removeItem(MEMKEY); } catch(e){}
  }
  if (typeof saved.c_roots === "boolean"){
    const cb = document.getElementById("c_roots");
    if (cb) cb.checked = saved.c_roots;
  }
  if (typeof saved.a_roots === "boolean"){
    const cb = document.getElementById("a_roots");
    if (cb) cb.checked = saved.a_roots;
  }
  if (saved.e_noverify === true){
    const cb = document.getElementById("e_noverify");
    if (cb) cb.checked = true;
  }
}

function bindFormMemory(){
  const save = () => {
    const o = {};
    MEM_IDS.forEach(id => {
      const el = document.getElementById(id);
      if (el) o[id] = el.value;
    });
    const r = document.getElementById("c_roots");
    if (r) o.c_roots = r.checked;
    const ar = document.getElementById("a_roots");
    if (ar) o.a_roots = ar.checked;
    const nv = document.getElementById("e_noverify");
    if (nv) o.e_noverify = nv.checked;
    try { localStorage.setItem(MEMKEY, JSON.stringify(o)); } catch(e){ /* 隐私模式忽略 */ }
  };
  MEM_IDS.forEach(id => {
    const el = document.getElementById(id);
    if (el) el.addEventListener("change", save);
  });
  ["c_roots", "a_roots", "e_noverify"].forEach(id => {
    const el = document.getElementById(id);
    if (el) el.addEventListener("change", save);
  });
}
boot();
</script>
</body>
</html>
"""
