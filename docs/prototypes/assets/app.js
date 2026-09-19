const KEY = "cs_proto_v1";
const DEMO_USER = "demo";
const DEMO_PASS = "demo";

function seed() {
  return {
    loggedIn: false,
    sessions: [
      {
        id: "s1",
        title: "VPN 提示认证失败",
        handoff: "none",
        messages: [
          { role: "user", text: "VPN 提示认证失败" },
          { role: "sys", source: "FAQ", text: "先检查账号是否锁定，再重试连接公司 VPN。" }
        ]
      }
    ],
    activeSession: "s1",
    documents: [
      {
        id: "d1",
        name: "VPN认证失败.md",
        status: "ready",
        progress: 100,
        objectTag: "网络与远程接入",
        requestTag: "故障与异常排查",
        chunks: ["VPN 认证失败时先确认账号未锁定，再重新导入配置文件。"],
        faqs: [{ q: "VPN 提示认证失败怎么办", a: "先检查账号是否锁定，再重试连接公司 VPN。" }],
        error: ""
      }
    ],
    activeDoc: "d1",
    tickets: [],
    activeTicket: null,
    agentFilter: "waiting"
  };
}

function load() {
  try {
    const raw = localStorage.getItem(KEY);
    if (!raw) return seed();
    return { ...seed(), ...JSON.parse(raw) };
  } catch {
    return seed();
  }
}

function save(state) {
  localStorage.setItem(KEY, JSON.stringify(state));
}

function requireAuth() {
  const params = new URLSearchParams(location.search);
  if (params.get("preview") === "1") {
    const s = load();
    s.loggedIn = true;
    save(s);
    return s;
  }
  const s = load();
  if (!s.loggedIn) {
    location.href = "../01-login/index.html";
    return null;
  }
  return s;
}

function logoutToLogin() {
  const s = load();
  s.loggedIn = false;
  save(s);
  location.href = "../01-login/index.html";
}

function sourceClass(source) {
  if (source === "FAQ") return "source-faq";
  if (source === "闲聊") return "source-chat";
  return "source-knowledge";
}

function replyFor(text) {
  const t = text.trim();
  if (/vpn|认证失败/i.test(t)) {
    return { source: "FAQ", text: "先检查账号是否锁定，再重试连接公司 VPN。" };
  }
  if (/天气|你好|哈哈|聊/.test(t)) {
    return { source: "闲聊", text: "你好，我是内部智能客服，有 IT 问题可以直接问我。" };
  }
  if (/工单|办到哪|进度|我那张/.test(t) || t.length < 4) {
    return { source: "知识问答", text: "当前问题超出知识服务范围，你可以点击转人工。" };
  }
  if (/Photoshop|没见过的系统/.test(t)) {
    return { source: "知识问答", text: "现有知识无法回答，你可以点击转人工。" };
  }
  return { source: "知识问答", text: "连接公司 VPN 前请确认网络正常，并使用公司下发的配置文件。" };
}

function statusLabel(status) {
  return { queued: "排队中", processing: "处理中", ready: "已生效", failed: "失败", waiting: "待接入", in_progress: "处理中", closed: "关闭" }[status] || status;
}

function renderMessages(el, messages, streaming) {
  el.innerHTML = messages.map((m) => {
    const kind = m.role === "user" ? "user" : m.role === "agent" ? "agent" : "sys";
    const src = m.source ? `<span class="source ${sourceClass(m.source)}">${m.source}</span>` : "";
    return `<div class="bubble ${kind}">${src}<div>${escapeHtml(m.text)}</div></div>`;
  }).join("");
  if (streaming) {
    const src = `<span class="source ${sourceClass(streaming.source)}">${streaming.source}</span>`;
    el.insertAdjacentHTML("beforeend", `<div class="bubble sys">${src}<div>${escapeHtml(streaming.text)}</div></div>`);
  }
  el.scrollTop = el.scrollHeight;
}

function escapeHtml(str) {
  return String(str).replace(/[&<>"']/g, (c) => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" }[c]));
}

function streamText(full, onTick, onDone) {
  const reduce = window.matchMedia("(prefers-reduced-motion: reduce)").matches;
  if (reduce) {
    onTick(full);
    onDone();
    return;
  }
  let i = 0;
  const timer = setInterval(() => {
    i += 1;
    onTick(full.slice(0, i));
    if (i >= full.length) {
      clearInterval(timer);
      onDone();
    }
  }, 28);
}

window.CS = {
  KEY, DEMO_USER, DEMO_PASS, load, save, seed, requireAuth, logoutToLogin,
  sourceClass, replyFor, statusLabel, renderMessages, escapeHtml, streamText
};
