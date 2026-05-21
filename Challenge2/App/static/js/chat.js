const Err = Object.freeze({
  USER_NOT_FOUND: "User not found.",
  INCORRECT_FLAG: "Incorrect flag.",
  FLAG_ERROR: "Error submitting flag.",
});

const conversations = {};
let activeReceiver = null;
let modalMode = null;

function showModalError(msg) {
  clearModalSuccess();
  const el = document.getElementById("modalError");
  el.textContent = msg;
  el.classList.add("visible");
}

function clearModalError() {
  const el = document.getElementById("modalError");
  el.textContent = "";
  el.classList.remove("visible");
}

function showModalSuccess(msg) {
  clearModalError();
  const el = document.getElementById("modalSuccess");
  el.textContent = msg;
  el.classList.add("visible");
}

function clearModalSuccess() {
  const el = document.getElementById("modalSuccess");
  el.textContent = "";
  el.classList.remove("visible");
}

async function loadConversations() {
  const res = await fetch("/conversations");
  if (!res.ok) return;
  const contacts = await res.json();
  contacts.forEach((name) => {
    if (!conversations[name]) conversations[name] = [];
  });
  renderDmList();
}

function openModal(mode) {
  modalMode = mode;

  const title = document.querySelector(".modal h2");
  const input = document.getElementById("targetUsername");
  const btnConfirm = document.querySelector(".btn-confirm");

  if (mode === "dm") {
    title.textContent = "Start a conversation";
    input.placeholder = "Username";
    btnConfirm.textContent = "Open";
  } else if (mode === "flag") {
    title.textContent = "What is Flag?";
    input.placeholder = "FLAG{...}";
    btnConfirm.textContent = "Submit";
  }

  clearModalError();
  clearModalSuccess();
  document.getElementById("modalOverlay").classList.add("open");
  input.focus();
}

function closeModal() {
  document.getElementById("modalOverlay").classList.remove("open");
  document.getElementById("targetUsername").value = "";
  clearModalError();
  clearModalSuccess();
}

async function confirmModal() {
  const value = document.getElementById("targetUsername").value.trim();
  if (!value) return;

  if (modalMode === "dm") {
    const res = await fetch(`/users/${encodeURIComponent(value)}`);
    if (!res.ok) {
      showModalError(`"${value}": ${Err.USER_NOT_FOUND}`);
      return;
    }
    if (!conversations[value]) {
      conversations[value] = [];
      renderDmList();
    }
    closeModal();
    selectDm(value);
  }

  if (modalMode === "flag") {
    const res = await fetch("/flag", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ flag: value }),
    });

    if (res.ok) {
      const data = await res.json();
      if (data.status === "correct") {
        showModalSuccess("Congratulations!");
      } else {
        showModalError(Err.INCORRECT_FLAG);
      }
    } else {
      showModalError(Err.FLAG_ERROR);
    }
  }
}

function renderDmList() {
  const list = document.getElementById("dmList");
  list.innerHTML = Object.keys(conversations)
    .map(
      (name) =>
        `<div class="dm-item" onclick="selectDm('${name}')" id="dm-${name}">${name}</div>`,
    )
    .join("");
}

function selectDm(name) {
  activeReceiver = name;
  document
    .querySelectorAll(".dm-item")
    .forEach((el) => el.classList.remove("active"));
  const el = document.getElementById(`dm-${name}`);
  if (el) el.classList.add("active");

  document.getElementById("mainArea").innerHTML = `
        <div class="chat-header">Conversation with <strong>${name}</strong></div>
        <div class="messages" id="messages"></div>
        <div class="input-bar">
            <input type="text" id="msgInput" placeholder="Message ${name}..." autocomplete="off" />
            <button onclick="sendMessage()">Send</button>
        </div>
    `;

  document.getElementById("msgInput").addEventListener("keydown", (e) => {
    if (e.key === "Enter") sendMessage();
  });

  renderMessages();
  document.getElementById("msgInput").focus();
}

async function sendMessage() {
  const input = document.getElementById("msgInput");
  const text = input.value.trim();
  if (!text || !activeReceiver) return;

  await fetch("/messages", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({
      receiver: activeReceiver,
      text: text,
    }),
  });

  input.value = "";
  renderMessages();
}

async function renderMessages() {
  if (!activeReceiver) return;

  const res = await fetch(`/messages/${activeReceiver}`);
  if (!res.ok) return;

  const messages = await res.json();
  const container = document.getElementById("messages");
  container.innerHTML = messages
    .map(
      (msg) => `
        <div class="message ${msg.author === ME ? "mine" : "theirs"}">
            <span class="message-author">${msg.author}</span>
            <div class="message-bubble">${msg.text}</div>
        </div>
    `,
    )
    .join("");

  container.scrollTop = container.scrollHeight;
}

document.getElementById("modalOverlay").addEventListener("click", function (e) {
  if (e.target === this) closeModal();
});

setInterval(() => {
  loadConversations();
  renderMessages();
}, 2000);

loadConversations();
