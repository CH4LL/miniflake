(function () {
  "use strict";

  const loginView = document.getElementById("login-view");
  const chatView = document.getElementById("chat-view");
  const loginForm = document.getElementById("login-form");
  const chatForm = document.getElementById("chat-form");
  const messageInput = document.getElementById("message-input");
  const sendButton = document.getElementById("send-button");
  const messagesEl = document.getElementById("messages");
  const errorBanner = document.getElementById("error-banner");
  const errorMessage = document.getElementById("error-message");
  const errorRequestId = document.getElementById("error-request-id");
  const loadingIndicator = document.getElementById("loading-indicator");
  const elapsedSeconds = document.getElementById("elapsed-seconds");
  const newConversationBtn = document.getElementById("new-conversation");

  let inFlight = false;
  let elapsedTimer = null;

  function showError(message, requestId) {
    errorMessage.textContent = message;
    errorRequestId.textContent = requestId ? "Request ID: " + requestId : "";
    errorBanner.classList.remove("hidden");
  }

  function hideError() {
    errorBanner.classList.add("hidden");
  }

  function showLogin() {
    loginView.classList.remove("hidden");
    chatView.classList.add("hidden");
  }

  function showChat() {
    loginView.classList.add("hidden");
    chatView.classList.remove("hidden");
  }

  function setLoading(active) {
    inFlight = active;
    messageInput.disabled = active;
    sendButton.disabled = active;
    if (active) {
      loadingIndicator.classList.remove("hidden");
      let seconds = 0;
      elapsedSeconds.textContent = "0";
      elapsedTimer = setInterval(function () {
        seconds += 1;
        elapsedSeconds.textContent = String(seconds);
      }, 1000);
    } else {
      loadingIndicator.classList.add("hidden");
      if (elapsedTimer) {
        clearInterval(elapsedTimer);
        elapsedTimer = null;
      }
    }
  }

  function extractError(body, response) {
    if (body && body.error) {
      return {
        message: body.error.message || "An error occurred",
        requestId: body.error.request_id || response.headers.get("X-Request-Id"),
      };
    }
    return {
      message: "Request failed with status " + response.status,
      requestId: response.headers.get("X-Request-Id"),
    };
  }

  async function apiFetch(url, options) {
    const response = await fetch(url, {
      credentials: "same-origin",
      ...options,
    });
    const contentType = response.headers.get("content-type") || "";
    let body = null;
    if (contentType.includes("application/json")) {
      body = await response.json();
    }
    return { response, body };
  }

  function outcomeBadgeClass(outcome) {
    return "outcome-badge " + (outcome || "answer");
  }

  function formatProvenanceMeta(toolCall) {
    const parts = [];
    const data = toolCall.data || {};
    const input = toolCall.input || {};
    if (data.field_name || data.field_id || input.field_id) {
      parts.push("Variable: " + (data.field_name || data.field_id || input.field_id));
    }
    if (data.geography_name || data.geo_id || input.geo_id) {
      parts.push("Geography: " + (data.geography_name || data.geo_id || input.geo_id));
    }
    if (data.vintage || input.vintage) {
      parts.push("Year: " + (data.vintage || input.vintage));
    }
    if (toolCall.name) {
      parts.push("Tool: " + toolCall.name);
    }
    if (toolCall.result_kind) {
      parts.push("Result: " + toolCall.result_kind);
    }
    return parts.join(" · ");
  }

  function renderProvenance(provenance, toolCalls) {
    if ((!provenance || provenance.length === 0) && (!toolCalls || toolCalls.length === 0)) {
      return "";
    }

    let html = '<details class="provenance-panel"><summary>Provenance</summary>';

    if (toolCalls && toolCalls.length > 0) {
      toolCalls.forEach(function (tc) {
        html += '<div class="provenance-entry">';
        html += "<h4>" + escapeHtml(tc.name) + "</h4>";
        html += '<div class="provenance-meta">' + escapeHtml(formatProvenanceMeta(tc)) + "</div>";
        if (tc.input && Object.keys(tc.input).length > 0) {
          html += "<div>Input: " + escapeHtml(JSON.stringify(tc.input)) + "</div>";
        }
        html += "</div>";
      });
    }

    if (provenance && provenance.length > 0) {
      provenance.forEach(function (prov, idx) {
        html += '<div class="provenance-entry">';
        html += "<h4>Query " + (idx + 1) + "</h4>";
        if (prov.source) {
          html += '<div class="provenance-meta">Source: ' + escapeHtml(prov.source) + "</div>";
        }
        if (prov.aggregation_method) {
          html += '<div class="provenance-meta">Aggregation: ' + escapeHtml(prov.aggregation_method) + "</div>";
        }
        if (prov.sql) {
          const params = prov.parameters ? JSON.stringify(prov.parameters, null, 2) : "{}";
          html += '<div class="provenance-sql">' + escapeHtml(prov.sql) + "\n\n-- parameters:\n" + escapeHtml(params) + "</div>";
        }
        html += "</div>";
      });
    }

    html += "</details>";
    return html;
  }

  function escapeHtml(text) {
    const div = document.createElement("div");
    div.textContent = text;
    return div.innerHTML;
  }

  function appendMessage(role, text, outcome, provenance, toolCalls) {
    const div = document.createElement("div");
    div.className = "message " + role;

    if (role === "assistant" && outcome) {
      const header = document.createElement("div");
      header.className = "message-header";
      const badge = document.createElement("span");
      badge.className = outcomeBadgeClass(outcome);
      badge.textContent = outcome;
      header.appendChild(badge);
      div.appendChild(header);
    }

    const textEl = document.createElement("div");
    textEl.className = "message-text";
    textEl.textContent = text;
    div.appendChild(textEl);

    if (role === "assistant") {
      const provHtml = renderProvenance(provenance, toolCalls);
      if (provHtml) {
        const wrapper = document.createElement("div");
        wrapper.innerHTML = provHtml;
        div.appendChild(wrapper.firstChild);
      }
    }

    messagesEl.appendChild(div);
    div.scrollIntoView({ behavior: "smooth", block: "end" });
  }

  async function checkSession() {
    const { response, body } = await apiFetch("/api/session");
    if (!response.ok) {
      showError("Could not check session status", response.headers.get("X-Request-Id"));
      return;
    }
    if (!body.auth_required || body.authenticated) {
      showChat();
    } else {
      showLogin();
    }
  }

  loginForm.addEventListener("submit", async function (e) {
    e.preventDefault();
    hideError();
    const passphrase = document.getElementById("passphrase").value;
    const { response, body } = await apiFetch("/api/login", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ passphrase: passphrase }),
    });
    if (!response.ok) {
      const err = extractError(body, response);
      showError(err.message, err.requestId);
      return;
    }
    showChat();
    messageInput.focus();
  });

  chatForm.addEventListener("submit", async function (e) {
    e.preventDefault();
    if (inFlight) return;
    const message = messageInput.value.trim();
    if (!message) return;

    hideError();
    appendMessage("user", message);
    messageInput.value = "";
    setLoading(true);

    const { response, body } = await apiFetch("/api/chat", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ message: message }),
    });

    setLoading(false);

    if (!response.ok) {
      const err = extractError(body, response);
      showError(err.message, err.requestId);
      return;
    }

    appendMessage(
      "assistant",
      body.text,
      body.outcome,
      body.provenance,
      body.tool_calls
    );
  });

  messageInput.addEventListener("keydown", function (e) {
    if (e.key === "Enter" && !e.shiftKey) {
      e.preventDefault();
      chatForm.requestSubmit();
    }
  });

  newConversationBtn.addEventListener("click", async function () {
    if (inFlight) return;
    hideError();
    const { response, body } = await apiFetch("/api/conversations/reset", {
      method: "POST",
    });
    if (!response.ok) {
      const err = extractError(body, response);
      showError(err.message, err.requestId);
      return;
    }
    messagesEl.innerHTML = "";
    messageInput.focus();
  });

  checkSession();
})();
