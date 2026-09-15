// DOM wiring for the self-hosted version. Same UI flow as the claude.ai
// artifact, but the AI-assisted steps call this app's own backend
// (/api/tailor, /api/polish) instead of claude.use("sample") — those
// endpoints call Claude with a server-held API key, so no viewer login is
// required and the page can be shared as a plain public link.
(function () {
  var state = {
    screen: 0,
    brief: "",
    archetypeId: "write",
    answers: {},
    tailoredQuestions: [], // [{ text, answer }]
    lastPrompt: "",
    lastAiAnswers: null
  };

  var busyUntil = { tailor: 0, polish: 0 };

  var el = {
    stepper: document.getElementById("stepper"),
    screenBrief: document.getElementById("screen-brief"),
    screenClarify: document.getElementById("screen-clarify"),
    screenPrompt: document.getElementById("screen-prompt"),
    briefInput: document.getElementById("brief-input"),
    briefError: document.getElementById("brief-error"),
    briefContinue: document.getElementById("brief-continue"),
    archetypeChip: document.getElementById("archetype-chip"),
    archetypeSelect: document.getElementById("archetype-select"),
    questionsStatic: document.getElementById("questions-static"),
    tailoredBlock: document.getElementById("tailored-block"),
    questionsTailored: document.getElementById("questions-tailored"),
    askTailoredBtn: document.getElementById("ask-tailored-btn"),
    tailoredStatus: document.getElementById("tailored-status"),
    clarifyBack: document.getElementById("clarify-back"),
    clarifyGenerate: document.getElementById("clarify-generate"),
    promptOutput: document.getElementById("prompt-output"),
    copyBtn: document.getElementById("copy-btn"),
    copiedFlag: document.getElementById("copied-flag"),
    polishBtn: document.getElementById("polish-btn"),
    polishStatus: document.getElementById("polish-status"),
    promptBack: document.getElementById("prompt-back")
  };

  // ---- archetype select options ----
  PE.ARCHETYPES.forEach(function (a) {
    var opt = document.createElement("option");
    opt.value = a.id;
    opt.textContent = a.label;
    el.archetypeSelect.appendChild(opt);
  });

  function labelFor(id) {
    for (var i = 0; i < PE.ARCHETYPES.length; i++) {
      if (PE.ARCHETYPES[i].id === id) return PE.ARCHETYPES[i].label;
    }
    return id;
  }

  function showScreen(index) {
    state.screen = index;
    el.screenBrief.hidden = index !== 0;
    el.screenClarify.hidden = index !== 1;
    el.screenPrompt.hidden = index !== 2;
    Array.prototype.forEach.call(el.stepper.querySelectorAll(".step"), function (stepEl) {
      var n = Number(stepEl.getAttribute("data-step"));
      stepEl.classList.toggle("active", n === index);
      stepEl.classList.toggle("done", n < index);
    });
    window.scrollTo({ top: 0, behavior: "instant" in window ? "instant" : "auto" });
  }

  // ---- Screen 1: Brief ----
  el.briefContinue.addEventListener("click", function () {
    var brief = el.briefInput.value;
    var result = PE.classify(brief);
    if (result.error) {
      el.briefError.classList.add("show");
      el.briefInput.focus();
      return;
    }
    el.briefError.classList.remove("show");
    state.brief = brief;
    state.archetypeId = result.archetype;
    state.answers = {};
    state.tailoredQuestions = [];
    renderClarify();
    showScreen(1);
  });

  // ---- Screen 2: Clarify ----
  function renderClarify() {
    el.archetypeChip.textContent = labelFor(state.archetypeId);
    el.archetypeSelect.value = state.archetypeId;

    el.questionsStatic.innerHTML = "";
    var questions = PE.getQuestions(state.archetypeId);
    questions.forEach(function (q) {
      el.questionsStatic.appendChild(buildQuestionField(q));
    });

    renderTailoredQuestions();
  }

  function buildQuestionField(q) {
    var wrap = document.createElement("div");
    wrap.className = "field";

    var label = document.createElement("label");
    label.className = "field-label";
    label.setAttribute("for", "q-" + q.id);
    label.textContent = q.label;
    wrap.appendChild(label);

    var input = document.createElement("textarea");
    input.className = "q-input";
    input.id = "q-" + q.id;
    input.placeholder = q.placeholder || "";
    input.value = state.answers[q.id] || "";
    input.addEventListener("input", function () {
      state.answers[q.id] = input.value;
    });
    wrap.appendChild(input);

    var hint = document.createElement("div");
    hint.className = "hint";
    hint.innerHTML = "If skipped: <strong>" + escapeHtml(q.default) + "</strong>";
    wrap.appendChild(hint);

    return wrap;
  }

  function escapeHtml(s) {
    return String(s)
      .replace(/&/g, "&amp;")
      .replace(/</g, "&lt;")
      .replace(/>/g, "&gt;");
  }

  el.archetypeSelect.addEventListener("change", function () {
    state.archetypeId = el.archetypeSelect.value;
    state.tailoredQuestions = [];
    renderClarify();
  });

  el.clarifyBack.addEventListener("click", function () {
    showScreen(0);
  });

  el.clarifyGenerate.addEventListener("click", function () {
    var aiAnswers = null;
    var answeredTailored = state.tailoredQuestions.filter(function (t) {
      return t.answer && t.answer.trim() !== "";
    });
    if (answeredTailored.length > 0) {
      aiAnswers = { context: [], constraints: [] };
      answeredTailored.forEach(function (t) {
        aiAnswers.context.push(t.text + " " + t.answer.trim());
      });
    }
    var prompt = PE.assemble({
      archetypeId: state.archetypeId,
      brief: state.brief,
      answers: state.answers,
      aiAnswers: aiAnswers
    });
    state.lastPrompt = prompt;
    state.lastAiAnswers = aiAnswers;
    el.promptOutput.textContent = prompt;
    el.polishStatus.textContent = "";
    showScreen(2);
  });

  // ---- Tailored questions (backend-assisted) ----
  function renderTailoredQuestions() {
    el.questionsTailored.innerHTML = "";
    if (state.tailoredQuestions.length === 0) {
      el.tailoredBlock.hidden = true;
      return;
    }
    el.tailoredBlock.hidden = false;
    state.tailoredQuestions.forEach(function (t, idx) {
      var wrap = document.createElement("div");
      wrap.className = "field";

      var label = document.createElement("label");
      label.className = "field-label";
      label.setAttribute("for", "qt-" + idx);
      label.textContent = t.text;
      wrap.appendChild(label);

      var input = document.createElement("textarea");
      input.className = "q-input";
      input.id = "qt-" + idx;
      input.value = t.answer || "";
      input.addEventListener("input", function () {
        t.answer = input.value;
      });
      wrap.appendChild(input);

      var hint = document.createElement("div");
      hint.className = "hint";
      hint.textContent = "Optional. Skip if it doesn't apply.";
      wrap.appendChild(hint);

      el.questionsTailored.appendChild(wrap);
    });
  }

  el.askTailoredBtn.addEventListener("click", function () {
    askForTailoredQuestions();
  });

  function askForTailoredQuestions() {
    if (Date.now() < busyUntil.tailor) return;
    el.askTailoredBtn.disabled = true;
    el.tailoredStatus.innerHTML = '<span class="spinner"></span> Thinking...';

    fetch("/api/tailor", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ brief: state.brief, archetypeLabel: labelFor(state.archetypeId) })
    })
      .then(handleJsonResponse)
      .then(function (data) {
        var list = Array.isArray(data.questions) ? data.questions : [];
        var qs = list
          .filter(function (x) { return typeof x === "string" && x.trim() !== ""; })
          .slice(0, 2)
          .map(function (text) { return { text: text.trim(), answer: "" }; });
        el.askTailoredBtn.disabled = false;
        if (qs.length === 0) {
          el.tailoredStatus.textContent = "Didn't get usable questions back this time.";
          return;
        }
        state.tailoredQuestions = qs;
        el.tailoredStatus.textContent = "";
        renderTailoredQuestions();
      })
      .catch(function (err) {
        handleBackendError(err, el.tailoredStatus, el.askTailoredBtn, "tailor");
      });
  }

  // ---- Screen 3: Prompt ----
  el.copyBtn.addEventListener("click", function () {
    var text = el.promptOutput.textContent;
    var done = function () {
      el.copiedFlag.classList.add("show");
      setTimeout(function () { el.copiedFlag.classList.remove("show"); }, 1600);
    };
    if (navigator.clipboard && navigator.clipboard.writeText) {
      navigator.clipboard.writeText(text).then(done, function () { fallbackCopy(text, done); });
    } else {
      fallbackCopy(text, done);
    }
  });

  function fallbackCopy(text, done) {
    var ta = document.createElement("textarea");
    ta.value = text;
    ta.style.position = "fixed";
    ta.style.opacity = "0";
    document.body.appendChild(ta);
    ta.select();
    try { document.execCommand("copy"); } catch (e) { /* ignore */ }
    document.body.removeChild(ta);
    done();
  }

  el.promptBack.addEventListener("click", function () {
    showScreen(1);
  });

  el.polishBtn.addEventListener("click", function () {
    if (Date.now() < busyUntil.polish) return;
    el.polishBtn.disabled = true;
    el.polishStatus.innerHTML = '<span class="spinner"></span> Polishing...';

    fetch("/api/polish", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ prompt: state.lastPrompt })
    })
      .then(handleJsonResponse)
      .then(function (data) {
        el.promptOutput.textContent = data.text;
        el.polishStatus.textContent = "Polished by Claude.";
        el.polishBtn.disabled = false;
      })
      .catch(function (err) {
        handleBackendError(err, el.polishStatus, el.polishBtn, "polish");
      });
  });

  // ---- Shared backend response/error handling ----
  function handleJsonResponse(response) {
    return response.json().then(function (data) {
      if (!response.ok) {
        var err = new Error(data && data.error ? data.error : "Request failed");
        err.status = response.status;
        err.retryAfter = response.headers.get("Retry-After");
        throw err;
      }
      return data;
    });
  }

  function handleBackendError(err, statusEl, buttonEl, kind) {
    if (err && err.status === 429) {
      var seconds = err.retryAfter ? parseInt(err.retryAfter, 10) : 60;
      busyUntil[kind] = Date.now() + Math.max(seconds, 1) * 1000;
      statusEl.textContent = err.message || "Too many requests. Try again in a bit.";
    } else if (err && typeof err.message === "string" && err.message) {
      statusEl.textContent = err.message;
    } else {
      statusEl.textContent = "Could not reach the AI service. You can carry on without it.";
    }
    if (buttonEl) buttonEl.disabled = false;
  }

  showScreen(0);
})();
