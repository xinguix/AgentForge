/* ============================================================
   AgentForge 前端 · 视图与交互
   ============================================================ */

const $ = s => document.querySelector(s);
const $$ = s => document.querySelectorAll(s);

const VIEW_TITLES = { chat: "对话", tasks: "任务记录", kb: "知识库", agents: "Agents" };

/* 顶部细进度条（任务提交 / 列表刷新反馈） */
function topBar(on) {
  $("#topProgress").classList.toggle("on", !!on);
}

/* 任务列表筛选状态 */
let taskFilter = "all";
let taskSearch = "";

/* ============ 视图切换 ============ */
function switchView(name) {
  $$(".nav-item").forEach(b => b.classList.toggle("active", b.dataset.view === name));
  $$(".view").forEach(v => v.classList.toggle("active", v.id === "view-" + name));
  $("#viewTitle").textContent = VIEW_TITLES[name];
  if (name === "tasks") refreshTaskList();
  if (name === "agents") refreshAgentList();
}

/* ============ 健康检查 + 时钟 ============ */
async function checkHealth() {
  try {
    const d = await API.health();
    $("#healthDot").className = "health-dot ok";
    $("#healthText").textContent = "后端正常 · " + d.env;
    $("#envBadge").textContent = "env · " + d.env;
  } catch {
    $("#healthDot").className = "health-dot bad";
    $("#healthText").textContent = "后端离线";
  }
}

function tickClock() {
  $("#clock").textContent = new Date().toLocaleTimeString("zh-CN", { hour12: false });
}

/* ============================================================
   视图：对话（SSE 流式）
   ============================================================ */
const chatState = { history: [], streaming: false, controller: null };

function loadChatHistory() {
  try { chatState.history = JSON.parse(localStorage.getItem("agentforge_chat_v1") || "[]"); } catch { chatState.history = []; }
}

function saveChatHistory() {
  const keep = chatState.history.slice(-100);
  try { localStorage.setItem("agentforge_chat_v1", JSON.stringify(keep)); } catch { /* 忽略 */ }
}

function renderChatHistory() {
  const box = $("#chatMessages");
  box.innerHTML = "";
  if (!chatState.history.length) {
    box.innerHTML = $("#chatMessages").querySelector(".chat-empty").outerHTML;
    return;
  }
  chatState.history.forEach(m => appendMsg(m.role, m.content, false));
}

function appendMsg(role, content, save = true) {
  const box = $("#chatMessages");
  // 清除空态
  const empty = box.querySelector(".chat-empty");
  if (empty) empty.remove();

  const userIcon = '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="M12 12a4 4 0 1 0 0-8 4 4 0 0 0 0 8Z"/><path d="M4 21v-1a6 6 0 0 1 6-6h4a6 6 0 0 1 6 6v1"/></svg>';
  const botIcon = '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><rect x="5" y="5" width="14" height="14" rx="3"/><path d="M9 9h6v6H9z"/></svg>';

  const div = document.createElement("div");
  div.className = "msg " + role;
  const model = role === "bot" ? `<span>${escapeHtml($("#metaModel").textContent)}</span>` : "";
  div.innerHTML = `
    <div class="msg-avatar">${role === "user" ? userIcon : botIcon}</div>
    <div class="msg-body">
      <div class="msg-meta">${role === "user" ? "你" : model}</div>
      <div class="bubble"></div>
    </div>`;
  box.appendChild(div);
  const bubble = div.querySelector(".bubble");
  if (role === "bot") bubble.innerHTML = renderMarkdown(content);
  else bubble.textContent = content;
  box.scrollTop = box.scrollHeight;
  if (save) { chatState.history.push({ role, content }); saveChatHistory(); }
  return bubble;
}

/* —— 思考过程指示器（对话内嵌流水线） —— */
const THINK_ORDER = ["planner", "research", "reviewer", "writer"];

function thinkPipelineHTML() {
  const nodes = THINK_ORDER.map((n, i) =>
    `<div class="tp-node" data-node="${n}"><i></i><span class="tp-name">${n}</span><em class="tp-st"></em><div class="tp-detail"></div></div>` +
    (i < THINK_ORDER.length - 1 ? '<div class="tp-link"></div>' : "")
  ).join("");
  return `<div class="tp-head"><span class="tp-toggle"></span><span class="tp-label">思考过程</span><span class="tp-state" data-tp-state></span></div><div class="tp-body">${nodes}</div>`;
}

function setThinkStateText(extra, text) {
  const s = extra.querySelector("[data-tp-state]");
  if (s) s.textContent = text;
}

function setThinkState(extra, node, status) {
  const el = extra.querySelector(`.tp-node[data-node="${node}"]`);
  if (!el) return;
  const st = el.querySelector(".tp-st");
  if (status === "start") {
    el.classList.remove("done", "fail"); el.classList.add("active");
    if (st) { st.textContent = "进行中…"; st.className = "tp-st running"; }
    setThinkStateText(extra, "进行中…");
  }
  else {
    el.classList.remove("active", "fail"); el.classList.add("done");
    if (st) { st.textContent = "完成"; st.className = "tp-st ok"; }
  }
}

function showTraceLink(extra, taskId) {
  const link = document.createElement("button");
  link.className = "trace-link";
  link.innerHTML = `<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="M12 3v3M12 18v3M3 12h3M18 12h3M5.6 5.6l2.1 2.1M16.3 16.3l2.1 2.1M18.4 5.6l-2.1 2.1M7.7 16.3l-2.1 2.1"/><circle cx="12" cy="12" r="3.2"/></svg>查看执行轨迹`;
  link.addEventListener("click", () => {
    switchView("tasks");
    openTaskDetail(taskId);
  });
  extra.appendChild(link);
}

async function sendChat() {
  const input = $("#chatInput");
  const text = input.value.trim();
  if (!text || chatState.streaming) return;

  const payload = {
    message: text,
    system_prompt: $("#chatSystemPrompt").value.trim() || null,
    temperature: parseFloat($("#chatTemp").value),
    agent_id: $("#chatAgent").value || null,
  };

  appendMsg("user", text);
  input.value = "";
  autoResize(input);

  const bubble = appendMsg("bot", "", false);

  // 思考指示器容器（放在 bubble 之前：先思考，后答案）
  const extra = document.createElement("div");
  extra.className = "msg-extra";
  bubble.before(extra);

  runChatStream(payload, bubble, extra);
}

/* 流式请求执行器：sendChat 与失败重试共用 */
async function runChatStream(payload, bubble, extra) {
  bubble.classList.add("cursor");
  extra.innerHTML = thinkPipelineHTML();
  // 卡片渲染后聊天区变高，重新滚到底部（避免新气泡被输入栏遮住）
  const chatBox = $("#chatMessages");
  chatBox.scrollTop = chatBox.scrollHeight;
  // 点击头部折叠/展开思考过程
  const head = extra.querySelector(".tp-head");
  if (head) head.addEventListener("click", () => extra.classList.toggle("collapsed"));
  let acc = "";
  let taskId = null;

  /* 节点点击：懒加载该节点的 INPUT/OUTPUT（复用 trace raw 接口） */
  const bindNodeExpand = () => {
    extra.querySelectorAll(".tp-node").forEach(el => {
      el.addEventListener("click", async ev => {
        if (ev.target.closest(".tp-detail")) return; // 点击已展开的内容不折叠
        const open = el.classList.toggle("open");
        if (!open) return;
        const detail = el.querySelector(".tp-detail");
        if (!detail) return;
        if (!taskId) {
          detail.innerHTML = '<pre>任务尚未开始，暂无数据</pre>';
          return;
        }
        if (el.dataset.loaded) return;
        el.dataset.loaded = "1";
        detail.innerHTML = '<pre>加载中…</pre>';
        try {
          const raw = await API.getTraceRaw(taskId);
          const node = (raw || []).find(r => r.node === el.dataset.node);
          if (!node) {
            detail.innerHTML = '<pre>该节点暂无记录</pre>';
            return;
          }
          const parts = [];
          if (node.input != null) {
            parts.push(`<span class="detail-tag">INPUT</span><pre>${escapeHtml(
              typeof node.input === "string" ? node.input : JSON.stringify(node.input, null, 2)
            )}</pre>`);
          }
          if (node.output != null) {
            parts.push(`<span class="detail-tag">OUTPUT</span><pre>${escapeHtml(String(node.output))}</pre>`);
          }
          if (node.error) {
            parts.push(`<span class="detail-tag">ERROR</span><pre>${escapeHtml(node.error)}</pre>`);
          }
          detail.innerHTML = parts.length ? parts.join("") : '<pre>该节点暂无内容</pre>';
        } catch (e) {
          detail.innerHTML = '<pre>暂无内容</pre>';
        }
      });
    });
  };
  bindNodeExpand();

  const onEvent = ev => {
    if (ev.event === "start") {
      $("#metaModel").textContent = ev.model || "deepseek-chat";
      taskId = ev.task_id || taskId;
    } else if (ev.event === "thinking") {
      setThinkState(extra, ev.node, ev.status);
    } else if (ev.event === "token") {
      acc += ev.token;
      bubble.innerHTML = renderMarkdown(acc);
      const shell = bubble.closest(".chat-shell");
      if (shell) $("#chatMessages").scrollTo({ top: $("#chatMessages").scrollHeight, behavior: "smooth" });
    } else if (ev.event === "done") {
      // 用完整答案替换累积内容
      if (ev.answer) { acc = ev.answer; bubble.innerHTML = renderMarkdown(ev.answer); }
      extra.querySelectorAll(".tp-node").forEach(n => {
        n.classList.remove("active", "fail"); n.classList.add("done");
        const st = n.querySelector(".tp-st");
        if (st && !st.textContent) { st.textContent = "完成"; st.className = "tp-st ok"; }
      });
      setThinkStateText(extra, "已完成");
      if (ev.task_id) showTraceLink(extra, ev.task_id);
    } else if (ev.event === "error") {
      throw new Error(ev.message || "流式输出失败");
    }
  };

  const fail = e => {
    bubble.classList.remove("cursor");
    // 指示器活跃节点标红
    extra.querySelectorAll(".tp-node.active").forEach(n => {
      n.classList.remove("active"); n.classList.add("fail");
      const st = n.querySelector(".tp-st");
      if (st) { st.textContent = "失败"; st.className = "tp-st err"; }
    });
    setThinkStateText(extra, "失败");
    if (e.name === "AbortError") {
      setThinkStateText(extra, "已停止");
      if (acc.trim()) { bubble.innerHTML = renderMarkdown(acc); }
      else { bubble.textContent = "（已停止）"; }
      chatState.history.push({ role: "bot", content: acc.trim() || "（已停止）" });
      saveChatHistory();
      return;
    }
    bubble.innerHTML = `<span style="color:var(--red)">请求失败：${escapeHtml(e.message)}</span>`;
    // 重试按钮：一键重发同一问题，无需重新输入
    const retry = document.createElement("button");
    retry.className = "retry-btn";
    retry.innerHTML = `<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="M21 12a9 9 0 1 1-2.64-6.36"/><path d="M21 3v6h-6"/></svg>重试`;
    retry.addEventListener("click", () => {
      bubble.innerHTML = "";
      bubble.classList.add("cursor");
      extra.innerHTML = thinkPipelineHTML();
      $("#chatMessages").scrollTop = $("#chatMessages").scrollHeight;
      const head = extra.querySelector(".tp-head");
      if (head) head.addEventListener("click", () => extra.classList.toggle("collapsed"));
      taskId = null;
      bindNodeExpand();
      start();
    });
    bubble.appendChild(retry);
  };

  const start = () => {
    chatState.streaming = true;
    $("#chatSend").disabled = true;
    $("#chatStop").hidden = false;
    chatState.controller = new AbortController();
    API.chatStream(payload, onEvent, chatState.controller.signal)
      .then(() => {
        bubble.classList.remove("cursor");
        if (!acc.trim()) bubble.textContent = "（无返回内容）";
        chatState.history.push({ role: "bot", content: acc.trim() || "（无返回内容）" });
        saveChatHistory();
      })
      .catch(fail)
      .finally(() => {
        chatState.streaming = false;
        $("#chatSend").disabled = false;
        $("#chatStop").hidden = true;
      });
  };

  start();
}

function autoResize(el) {
  el.style.height = "auto";
  el.style.height = Math.min(el.scrollHeight, 150) + "px";
}

/* ============================================================
   视图：任务记录
   ============================================================ */
let currentTaskId = null;

/* —— 任务列表（支持状态筛选 + 关键词搜索） —— */
async function refreshTaskList() {
  topBar(true);
  try {
    const tasks = await API.listTasks();
    const box = $("#taskList");
    if (!tasks.length) { box.innerHTML = '<div class="list-empty">暂无任务记录</div>'; return; }

    // 过滤：状态 + 关键词
    const kw = taskSearch.toLowerCase();
    const visible = tasks.filter(t =>
      (taskFilter === "all" || t.status === taskFilter) &&
      (!kw || (t.input || "").toLowerCase().includes(kw))
    );
    if (!visible.length) {
      box.innerHTML = '<div class="list-empty">没有匹配的任务</div>';
      return;
    }

    box.innerHTML = visible.map(t => `
      <div class="task-item ${t.id === currentTaskId ? "sel" : ""}" data-id="${t.id}">
        <div class="task-item-top">
          <span class="status-dot ${t.status}"></span>
          <span class="status-pill ${t.status}">${t.status}</span>
          <span class="task-time">${fmtDate(t.created_at)}</span>
        </div>
        <div class="task-input">${escapeHtml(t.input || "")}</div>
        <div class="task-meta">
          <span class="task-id" title="${escapeHtml(t.id)}">${shortId(t.id)}</span>
          <span>${t.plan_data && t.plan_data.steps ? t.plan_data.steps.length + " 步" : "--"}</span>
          <span class="task-tokens" id="tokens-${t.id}">--</span>
        </div>
      </div>`).join("");
    box.querySelectorAll(".task-item").forEach(item => {
      item.addEventListener("click", () => openTaskDetail(item.dataset.id));
    });
    // 异步补 token 数（trace 接口）
    visible.forEach(t => {
      if (["completed", "failed"].includes(t.status)) {
        API.getTrace(t.id).then(trace => {
          const el = document.getElementById("tokens-" + t.id);
          if (el) el.textContent = "≈" + (trace.total_tokens || 0) + " tok";
        }).catch(() => {});
      }
    });
  } catch (e) {
    $("#taskList").innerHTML = `<div class="list-empty">加载失败：${escapeHtml(e.message)}</div>`;
  } finally {
    topBar(false);
  }
}

/* 复制文本到剪贴板（含降级方案） */
async function copyText(text) {
  try {
    await navigator.clipboard.writeText(text);
  } catch {
    const ta = document.createElement("textarea");
    ta.value = text;
    ta.style.position = "fixed"; ta.style.opacity = "0";
    document.body.appendChild(ta);
    ta.select();
    document.execCommand("copy");
    ta.remove();
  }
  toast("已复制到剪贴板", "ok");
}

/* Trace 节点：点击展开输入/输出（懒加载 raw 接口，失败降级） */
function bindTraceExpand() {
  document.querySelectorAll(".trace-item").forEach(item => {
    item.addEventListener("click", () => {
      const open = item.classList.toggle("open");
      if (!open || item.dataset.loaded) return;
      item.dataset.loaded = "1";
      const box = item.querySelector(".trace-detail");
      const nodeName = item.dataset.node;
      API.getTraceRaw(item.dataset.id)
        .then(raw => {
          const node = (raw || []).find(r => r.node === nodeName);
          if (!node) return;
          const parts = [];
          if (node.input != null) {
            parts.push(`<span class="detail-tag">INPUT</span><pre>${escapeHtml(
              typeof node.input === "string" ? node.input : JSON.stringify(node.input, null, 2)
            )}</pre>`);
          }
          if (node.output != null) {
            parts.push(`<span class="detail-tag">OUTPUT</span><pre>${escapeHtml(String(node.output))}</pre>`);
          }
          if (parts.length) box.innerHTML = parts.join("");
        })
        .catch(() => { /* raw 不可用时保持现有内容 */ });
    });
  });
}

/* —— 任务详情 —— */
async function openTaskDetail(id) {
  currentTaskId = id;
  $$(".task-item").forEach(i => i.classList.toggle("sel", i.dataset.id === id));
  const box = $("#taskDetail");
  // 骨架屏：加载反馈
  box.innerHTML = `
    <div class="skeleton sk-card"></div>
    <div class="skeleton sk-block w80"></div>
    <div class="skeleton sk-block w60"></div>
    <div class="skeleton sk-card"></div>
    <div class="skeleton sk-block w40"></div>
  `;

  try {
    const [task, trace] = await Promise.all([API.getTask(id), API.getTrace(id)]);

    const plan = task.plan_data;
    const stepsHtml = plan && plan.steps && plan.steps.length
      ? `<div class="plan-steps">${plan.steps.map(s => `
          <div class="plan-step">
            <span class="step-no">${s.step_id}</span>
            <span class="agent-badge ${s.agent_type}">${s.agent_type}</span>
            <span class="step-desc">${escapeHtml(s.description)}</span>
            ${s.depends_on && s.depends_on.length ? `<span class="step-dep">依赖 #${s.depends_on.join(",#")}</span>` : ""}
          </div>`).join("")}</div>`
      : '<div class="list-empty">无计划数据</div>';

    const traceHtml = trace.nodes && trace.nodes.length
      ? `<div class="trace-list">${trace.nodes.map(n => `
          <div class="trace-item ${n.status === "success" ? "ok" : "err"}" data-node="${escapeHtml(n.name)}" data-id="${escapeHtml(trace.task_id || id)}">
            <div class="trace-item-head">
              <span class="trace-node">${escapeHtml(n.name)}</span>
              <span class="agent-badge ${escapeHtml(n.type === "tool" ? "research" : n.name)}">${escapeHtml(n.type)}</span>
              <span class="status-pill ${n.status === "success" ? "completed" : "failed"}">${escapeHtml(n.status)}</span>
            </div>
            <div class="trace-meta">
              <span class="lat-chip">耗时 <b>${fmtLatency(n.latency_ms)}</b></span>
              <span class="lat-chip">tokens <b class="tok-num">${n.tokens ?? 0}</b></span>
              <span>${fmtTime(n.timestamp)}</span>
            </div>
            <div class="trace-detail">
              ${n.error ? `<span class="detail-tag">ERROR</span><pre>${escapeHtml(n.error)}</pre><span class="detail-tag">点击加载输入 / 输出</span>` : `<span class="detail-tag">点击加载输入 / 输出</span>`}
            </div>
          </div>`).join("")}</div>`
      : '<div class="list-empty">暂无轨迹</div>';

    const resumeBtn = task.status === "failed"
      ? `<div class="resume-row">
           <span class="resume-hint">任务失败，可从 Checkpoint 断点续跑</span>
           <button class="btn-send" id="resumeBtn">恢复任务</button>
         </div>`
      : "";

    box.innerHTML = `
      <div class="detail-head">
        <h2>${task.status === "completed" ? "执行结果" : "任务详情"}</h2>
        <span class="status-pill ${task.status}">${task.status}</span>
        <span class="task-id" title="${escapeHtml(task.id)}">${shortId(task.id)}</span>
      </div>
      <div class="detail-sec">
        <h3>任务输入</h3>
        <div class="rationale">${escapeHtml(task.input || "")}</div>
      </div>
      ${resumeBtn}
      ${plan ? `<div class="detail-sec">
        <h3>执行计划 · ${plan.steps ? plan.steps.length : 0} 步</h3>
        ${stepsHtml}
        ${plan.rationale ? `<div class="rationale" style="margin-top:10px">${escapeHtml(plan.rationale)}</div>` : ""}
      </div>` : ""}
      <div class="detail-sec">
        <h3>节点轨迹 · ${trace.total_nodes || 0} 个 · 总耗时 ${fmtLatency(trace.total_latency_ms)} · 总 tokens <span style="color:var(--violet);text-shadow:0 0 10px rgba(167,139,250,.35)">${trace.total_tokens ?? 0}</span></h3>
        ${traceHtml}
      </div>
      ${task.output ? `<div class="detail-sec">
        <div class="report-head">
          <h3>最终报告</h3>
          <button class="btn-ghost" id="copyReport">
            <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round" style="width:13px;height:13px"><rect x="9" y="9" width="11" height="11" rx="2"/><path d="M5 15V5a2 2 0 0 1 2-2h10"/></svg>
            复制报告
          </button>
        </div>
        <div class="answer-body">${renderMarkdown(task.output)}</div>
      </div>` : ""}
      ${task.error ? `<div class="detail-sec"><h3>错误信息</h3><div class="trace-io"><pre>${escapeHtml(task.error)}</pre></div></div>` : ""}
    `;

    if (task.status === "failed") {
      $("#resumeBtn").addEventListener("click", async () => {
        try {
          toast("正在从 Checkpoint 恢复…");
          await API.resumeTask(id);
          toast("恢复成功", "ok");
          await refreshTaskList();
          await openTaskDetail(id);
        } catch (e) { toast("恢复失败：" + e.message, "err"); }
      });
    }

    const copyBtn = $("#copyReport");
    if (copyBtn) copyBtn.addEventListener("click", () => copyText(task.output || ""));

    bindTraceExpand();
  } catch (e) {
    box.innerHTML = `<div class="list-empty">加载失败：${escapeHtml(e.message)}</div>`;
  }
}

/* ============================================================
   视图：知识库
   ============================================================ */
function bindDropzone() {
  const dz = $("#dropzone");
  const fileInput = $("#kbFile");

  dz.addEventListener("click", () => fileInput.click());
  dz.addEventListener("dragover", e => { e.preventDefault(); dz.classList.add("drag"); });
  dz.addEventListener("dragleave", () => dz.classList.remove("drag"));
  dz.addEventListener("drop", e => {
    e.preventDefault();
    dz.classList.remove("drag");
    if (e.dataTransfer.files.length) uploadDoc(e.dataTransfer.files[0]);
  });
  fileInput.addEventListener("change", () => {
    if (fileInput.files.length) uploadDoc(fileInput.files[0]);
    fileInput.value = "";
  });
}

async function uploadDoc(file) {
  const prog = $("#kbProgress");
  const fill = $("#kbBarFill");
  const txt = $("#kbBarText");
  prog.hidden = false;
  fill.style.width = "20%";
  txt.textContent = "上传中：" + file.name;

  try {
    // fetch 上传不支持进度，模拟推进到 70%，实际完成再拉满
    let p = 20;
    const timer = setInterval(() => {
      p = Math.min(p + 8, 70);
      fill.style.width = p + "%";
    }, 400);

    const res = await API.uploadDoc(file);
    clearInterval(timer);
    fill.style.width = "100%";
    txt.textContent = "解析 + 向量化完成，共 " + res.chunk_count + " 块";
    setTimeout(() => { prog.hidden = true; }, 1600);

    const result = $("#kbResult");
    result.hidden = false;
    $("#kbStats").innerHTML = `
      <div><dt>${res.char_count}</dt><dd>字符数</dd></div>
      <div><dt>${res.chunk_count}</dt><dd>向量分块</dd></div>`;
    $("#kbPreview").textContent = res.content_preview || "(无预览内容)";
    toast("文档已入库：" + file.name, "ok");
  } catch (e) {
    fill.style.width = "100%";
    fill.style.background = "var(--red)";
    txt.textContent = "上传失败：" + e.message;
    setTimeout(() => { prog.hidden = true; fill.style.background = ""; }, 2600);
    toast("入库失败：" + e.message, "err");
  }
}

/* ============================================================
   视图：Agents
   ============================================================ */
/* 聊天栏 Agent 选择器：填充已铸造的 Agent 列表 */
async function loadAgentOptions() {
  const sel = $("#chatAgent");
  if (!sel) return;
  const current = sel.value;
  try {
    const agents = await API.listAgents();
    sel.innerHTML = '<option value="">默认</option>' +
      agents.map(a => `<option value="${a.id}">${escapeHtml(a.name)}</option>`).join("");
    sel.value = current;
  } catch { /* 列表不可用时保留空选项 */ }
}

async function refreshAgentList() {
  try {
    const agents = await API.listAgents();
    loadAgentOptions();
    const box = $("#agentList");
    if (!agents.length) { box.innerHTML = '<div class="list-empty">暂无 Agent，先铸造一个</div>'; return; }
    box.innerHTML = agents.map(a => `
      <div class="agent-card">
        <div class="agent-card-top">
          <div>
            <div class="agent-card-name">${escapeHtml(a.name)}</div>
            <span class="agent-card-model">${escapeHtml(a.model)}</span>
          </div>
          <button class="btn-del" data-id="${a.id}" title="删除">
            <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="M4 7h16M10 11v6M14 11v6M6 7l1 13h10l1-13M9 7V4h6v3"/></svg>
            删除
          </button>
        </div>
        ${a.description ? `<div class="agent-card-desc">${escapeHtml(a.description)}</div>` : ""}
        ${a.tools && a.tools.length ? `<div class="tool-tags">${a.tools.map(t => `<span class="tool-tag">${escapeHtml(t)}</span>`).join("")}</div>` : ""}
        ${a.system_prompt ? `<div class="tool-tags" style="margin-top:7px"><span class="tool-tag" style="color:var(--cyan)">sys: ${escapeHtml(a.system_prompt.slice(0, 60))}${a.system_prompt.length > 60 ? "…" : ""}</span></div>` : ""}
        <div class="agent-card-foot">
          <span class="agent-card-time">${fmtTime(a.created_at)}</span>
        </div>
      </div>`).join("");

    box.querySelectorAll(".btn-del").forEach(btn => {
      btn.addEventListener("click", async () => {
        if (!confirm("确认删除 Agent " + shortId(btn.dataset.id) + "？")) return;
        try {
          await API.deleteAgent(btn.dataset.id);
          toast("已删除", "ok");
          refreshAgentList();
        } catch (e) { toast("删除失败：" + e.message, "err"); }
      });
    });
  } catch (e) {
    $("#agentList").innerHTML = `<div class="list-empty">加载失败：${escapeHtml(e.message)}</div>`;
  }
}

/* ============================================================
   初始化
   ============================================================ */
function init() {
  // 视图切换
  $$(".nav-item").forEach(b => b.addEventListener("click", () => switchView(b.dataset.view)));

  // 时钟 + 健康
  tickClock();
  setInterval(tickClock, 1000);
  checkHealth();
  setInterval(checkHealth, 15000);

  // 对话
  const input = $("#chatInput");
  input.addEventListener("input", () => autoResize(input));
  input.addEventListener("keydown", e => {
    if (e.key === "Enter" && !e.shiftKey) { e.preventDefault(); sendChat(); }
  });
  $("#chatSend").addEventListener("click", sendChat);
  $("#chatStop").addEventListener("click", () => chatState.controller && chatState.controller.abort());
  $("#chatTemp").addEventListener("input", e => $("#tempVal").textContent = e.target.value);
  $("#exampleChips").addEventListener("click", e => {
    const chip = e.target.closest(".chip");
    if (chip) { input.value = chip.dataset.q; autoResize(input); input.focus(); }
  });
  loadChatHistory();
  renderChatHistory();
  loadAgentOptions();

  // 任务
  $("#taskRefresh").addEventListener("click", refreshTaskList);

  // 任务筛选 chips
  $("#taskFilterChips").addEventListener("click", e => {
    const chip = e.target.closest(".chip");
    if (!chip) return;
    taskFilter = chip.dataset.filter;
    $$("#taskFilterChips .chip").forEach(c => c.classList.toggle("on", c === chip));
    refreshTaskList();
  });

  // 任务搜索（防抖 300ms）
  let searchTimer = null;
  $("#taskSearch").addEventListener("input", e => {
    clearTimeout(searchTimer);
    searchTimer = setTimeout(() => {
      taskSearch = e.target.value.trim();
      refreshTaskList();
    }, 300);
  });

  // 知识库
  bindDropzone();

  // Agents
  $("#agentForm").addEventListener("submit", async e => {
    e.preventDefault();
    const fd = new FormData(e.target);
    const body = {
      name: fd.get("name").trim(),
      model: fd.get("model").trim(),
      description: fd.get("description").trim() || null,
      system_prompt: fd.get("system_prompt").trim() || null,
      tools: fd.get("tools").trim() ? fd.get("tools").split(/[,，]/).map(s => s.trim()).filter(Boolean) : [],
      knowledge_bindings: [],
    };
    try {
      await API.createAgent(body);
      toast("Agent 铸造成功", "ok");
      e.target.reset();
      refreshAgentList();
    } catch (err) { toast("创建失败：" + err.message, "err"); }
  });
  $("#agentRefresh").addEventListener("click", refreshAgentList);

  // 默认进入对话视图
  refreshTaskList();
  refreshAgentList();
}

document.addEventListener("DOMContentLoaded", init);
