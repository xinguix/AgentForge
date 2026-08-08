/* ============================================================
   AgentForge 前端 · API 封装 + 工具函数
   后端基地址统一走 nginx 代理 /api/
   ============================================================ */

const API = {
  health: () => fetch("/api/health").then(r => r.json()),

  // —— 对话 ——
  chatStream: (body, onEvent, signal) =>
    fetch("/api/v1/chat/stream", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(body),
      signal,
    }).then(r => {
      if (!r.ok) throw new Error("对话接口异常 " + r.status);
      const reader = r.body.getReader();
      const decoder = new TextDecoder();
      let buffer = "";
      const pump = () =>
        reader.read().then(({ done, value }) => {
          if (done) { onEvent({ done: true }); return; }
          buffer += decoder.decode(value, { stream: true });
          const lines = buffer.split("\n");
          buffer = lines.pop();
          for (const line of lines) {
            const t = line.trim();
            if (!t.startsWith("data:")) continue;
            const payload = t.slice(5).trim();
            if (!payload) continue;
            try { onEvent(JSON.parse(payload)); }
            catch { /* 忽略非 JSON 行 */ }
          }
          return pump();
        });
      return pump();
    }),

  chatOnce: body =>
    fetch("/api/v1/chat", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(body),
    }).then(handleRes),

  // —— 任务 ——
  createTask: body =>
    fetch("/api/v1/tasks/plan", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(body),
    }).then(handleRes),

  listTasks: () => fetch("/api/v1/tasks/").then(handleRes),
  getTask: id => fetch(`/api/v1/tasks/${id}`).then(handleRes),
  getTaskStatus: id => fetch(`/api/v1/tasks/${id}/status`).then(handleRes),
  resumeTask: id =>
    fetch(`/api/v1/tasks/${id}/resume`, { method: "POST" }).then(handleRes),
  getTrace: id => fetch(`/api/v1/tasks/${id}/trace`).then(handleRes),
  getTraceRaw: id => fetch(`/api/v1/tasks/${id}/trace/raw`).then(handleRes),

  // —— 知识库 ——
  uploadDoc: file => {
    const fd = new FormData();
    fd.append("file", file);
    return fetch("/api/v1/documents/upload", { method: "POST", body: fd }).then(handleRes);
  },
  listDocuments: () => fetch("/api/v1/documents/").then(handleRes),
  deleteDocument: name =>
    fetch(`/api/v1/documents/${encodeURIComponent(name)}`, { method: "DELETE" }).then(handleRes),

  // —— Agents ——
  listAgents: () => fetch("/api/v1/agents/").then(handleRes),
  createAgent: body =>
    fetch("/api/v1/agents/", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(body),
    }).then(handleRes),
  deleteAgent: id => fetch(`/api/v1/agents/${id}`, { method: "DELETE" }).then(handleRes),
};

async function handleRes(r) {
  if (!r.ok) {
    let detail = "HTTP " + r.status;
    try { const j = await r.json(); detail = j.detail || detail; } catch { /* 忽略 */ }
    throw new Error(detail);
  }
  if (r.status === 204) return null;
  return r.json();
}

/* ============================================================
   Markdown 渲染：优先 marked（CDN），失败则降级纯文本
   ============================================================ */
function renderMarkdown(text) {
  if (window.marked && typeof window.marked.parse === "function") {
    try { return window.marked.parse(text); } catch { /* fallthrough */ }
  }
  return "<p>" + escapeHtml(text).replace(/\n/g, "<br>") + "</p>";
}

/* ============================================================
   工具函数
   ============================================================ */
function escapeHtml(s) {
  return String(s ?? "")
    .replace(/&/g, "&amp;").replace(/</g, "&lt;").replace(/>/g, "&gt;")
    .replace(/"/g, "&quot;").replace(/'/g, "&#39;");
}

function fmtTime(iso) {
  if (!iso) return "--";
  const d = new Date(iso);
  return d.toLocaleString("zh-CN", { hour12: false });
}

function fmtLatency(ms) {
  if (ms == null) return "--";
  if (ms < 1000) return ms + "ms";
  return (ms / 1000).toFixed(2) + "s";
}

function fmtDate(iso) {
  const d = new Date(iso);
  return d.toLocaleString("zh-CN", { month: "2-digit", day: "2-digit", hour: "2-digit", minute: "2-digit", hour12: false });
}

function shortId(id) {
  return id ? id.slice(0, 8) + "…" : "";
}

/* 轻量 toast */
function toast(msg, type = "info", ms = 3200) {
  const wrap = document.getElementById("toastWrap");
  const t = document.createElement("div");
  t.className = "toast " + (type === "err" ? "err" : type === "ok" ? "ok" : "");
  t.innerHTML = `<span class="t-dot"></span><span>${escapeHtml(msg)}</span>`;
  wrap.appendChild(t);
  setTimeout(() => { t.style.opacity = "0"; t.style.transition = "opacity .35s"; }, ms);
  setTimeout(() => t.remove(), ms + 400);
}
