// Pure logic only: classification, question bank, prompt assembly.
// No DOM access here. Exposed as the single global `PE`.
//
// This file must stay byte-identical to the LOGIC block in
// ../../prompt-engineer.html (the claude.ai artifact version) — both are
// covered by the same test suite in ../../tests/run_tests.mjs, which fails
// loudly if the two drift apart.
(function () {
  var ARCHETYPES = [
    { id: "write", label: "Write / Draft", keywords: [
      "write", "draft", "compose", "email", "letter", "announcement", "message"
    ] },
    { id: "summarize", label: "Summarize / Extract", keywords: [
      "summarize", "summarise", "summary", "extract", "key points", "key risks",
      "pull the key", "condense", "shorten", "tl;dr"
    ] },
    { id: "analyze", label: "Analyse / Decide", keywords: [
      "analyse", "analyze", "decide", "decision", "should we", "evaluate",
      "compare", "pros and cons", "recommend"
    ] },
    { id: "research", label: "Research", keywords: [
      "research", "find out", "investigate", "look into", "gather information"
    ] },
    { id: "rewrite", label: "Rewrite / Edit", keywords: [
      "rewrite", "proofread", "polish", "improve this", "revise", "clean up",
      "tighten this", "edit this"
    ] },
    { id: "code", label: "Code / Build", keywords: [
      "code", "script", "function", "bug", "python", "javascript", "debug",
      "fix this", "program", "sql", "typescript", "regex"
    ] },
    { id: "brainstorm", label: "Brainstorm", keywords: [
      "brainstorm", "ideas for", "idea for", "name for", "options for",
      "suggest names", "suggest ideas"
    ] },
    { id: "teach", label: "Teach / Explain", keywords: [
      "explain", "teach", "how does", "what is", "help me understand",
      "eli5", "in simple terms"
    ] }
  ];

  var CORE_QUESTIONS = [
    {
      id: "role", block: "Role",
      label: "What role or expertise should Claude bring to this?",
      placeholder: "e.g. a senior editor, a data analyst, a patient teacher",
      default: "A capable generalist with relevant expertise for this task."
    },
    {
      id: "audience", block: "Context",
      label: "Who is the output for?",
      placeholder: "e.g. my manager, a customer, myself",
      default: "A general audience with no specialist background assumed."
    },
    {
      id: "inputs", block: "Inputs",
      label: "What will you paste or attach alongside this prompt, if anything?",
      placeholder: "e.g. the report text, the script, a data table",
      default: "Nothing else; work from the task description alone."
    },
    {
      id: "format", block: "Output format",
      label: "What output format and length do you want?",
      placeholder: "e.g. bullet points under 200 words, a one-page memo, a table",
      default: "Plain prose, organized with headings where useful, as short as possible while covering everything asked for."
    },
    {
      id: "must_avoid", block: "Constraints",
      label: "Anything Claude should avoid doing or saying?",
      placeholder: "e.g. no jargon, no bullet points, do not guess numbers",
      default: "No specific exclusions."
    },
    {
      id: "success", block: "Success criteria",
      label: "What does a good result look like?",
      placeholder: "e.g. someone could act on it without asking questions",
      default: "The output fully answers the request and is usable as-is."
    }
  ];

  var ARCHETYPE_QUESTIONS = {
    write: [
      { id: "write_key_points", block: "Constraints",
        label: "What key points must be included?",
        placeholder: "e.g. the new go-live date, who to contact with questions",
        default: "Cover whatever points are implied by the brief; do not add unrelated points." },
      { id: "write_examples", block: "Context",
        label: "Any examples or reference material to match the style of?",
        placeholder: "e.g. a previous email, the brand voice guide",
        default: "No style reference given; use clear, professional prose." },
      { id: "write_cta", block: "Constraints",
        label: "Is there a call to action or next step to include?",
        placeholder: "e.g. reply by Friday, attend the town hall",
        default: "No explicit call to action needed." }
    ],
    summarize: [
      { id: "summarize_focus", block: "Context",
        label: "What should the summary focus on?",
        placeholder: "e.g. the decisions made, the biggest risks",
        default: "The main conclusions, decisions, and risks." },
      { id: "summarize_length", block: "Output format",
        label: "How much should it be reduced?",
        placeholder: "e.g. five bullet points, one paragraph",
        default: "Reduce to the essential points only, roughly a tenth of the original length." },
      { id: "summarize_omit", block: "Constraints",
        label: "Anything safe to leave out entirely?",
        placeholder: "e.g. methodology, background context",
        default: "Leave out background and methodology unless they affect the conclusions." }
    ],
    analyze: [
      { id: "analyze_options", block: "Context",
        label: "What are the options or choices being weighed?",
        placeholder: "e.g. one department vs three, build vs buy",
        default: "Infer the options from the brief." },
      { id: "analyze_criteria", block: "Method",
        label: "What criteria matter most in the decision?",
        placeholder: "e.g. cost, risk, time to value, staff impact",
        default: "Cost, risk, and time to value, in that order, unless stated otherwise." },
      { id: "analyze_recommendation", block: "Success criteria",
        label: "Do you want a firm recommendation or just the analysis?",
        placeholder: "e.g. recommend one option, or just lay out the trade-offs",
        default: "A firm recommendation, with the reasoning shown." }
    ],
    research: [
      { id: "research_scope", block: "Context",
        label: "What should the research focus on, and what is out of scope?",
        placeholder: "e.g. only public sources, only the last two years",
        default: "Focus on directly relevant, credible information; skip tangents." },
      { id: "research_depth", block: "Method",
        label: "How deep should it go?",
        placeholder: "e.g. a quick overview, a thorough review",
        default: "A solid overview, not an exhaustive review." },
      { id: "research_sources", block: "Constraints",
        label: "Any source types to prefer or avoid?",
        placeholder: "e.g. prefer primary sources, avoid forums",
        default: "No source preference given; use good judgment and flag uncertainty." }
    ],
    rewrite: [
      { id: "rewrite_goal", block: "Method",
        label: "What should change: tone, length, clarity, structure?",
        placeholder: "e.g. make it more concise and less formal",
        default: "Improve clarity and flow while preserving the original meaning." },
      { id: "rewrite_keep", block: "Constraints",
        label: "Anything that must stay exactly as written?",
        placeholder: "e.g. the numbers, a direct quote, the closing line",
        default: "Nothing is protected; the whole text may be improved." },
      { id: "rewrite_audience_shift", block: "Context",
        label: "Is the audience changing from the original text?",
        placeholder: "e.g. written for engineers, now needs to work for executives",
        default: "The audience is unchanged from the original text." }
    ],
    code: [
      { id: "code_language", block: "Context",
        label: "What language or framework is this in?",
        placeholder: "e.g. Python 3.11, React, PostgreSQL",
        default: "Infer the language and framework from the code or brief." },
      { id: "code_constraints", block: "Constraints",
        label: "Any constraints: performance, style guide, dependencies?",
        placeholder: "e.g. no new dependencies, must match the existing style",
        default: "No special constraints; follow common best practice for the language." },
      { id: "code_testing", block: "Method",
        label: "Should Claude include tests, or just the fix or feature?",
        placeholder: "e.g. add a unit test for the fix",
        default: "Explain the change briefly; add tests only if trivial to include." }
    ],
    brainstorm: [
      { id: "brainstorm_quantity", block: "Output format",
        label: "How many ideas do you want?",
        placeholder: "e.g. five, twenty, as many as possible",
        default: "Around eight to ten ideas." },
      { id: "brainstorm_constraints", block: "Constraints",
        label: "Any constraints the ideas must fit?",
        placeholder: "e.g. budget, timeline, team size",
        default: "No hard constraints given; favor variety over feasibility." },
      { id: "brainstorm_novelty", block: "Method",
        label: "Do you want safe options, bold ones, or a mix?",
        placeholder: "e.g. mostly practical, one or two wild ideas",
        default: "A mix, from safe to bold, clearly labeled." }
    ],
    teach: [
      { id: "teach_level", block: "Context",
        label: "What is the learner's current level?",
        placeholder: "e.g. complete beginner, some background, expert in a related field",
        default: "A complete beginner to this topic." },
      { id: "teach_method", block: "Method",
        label: "Should Claude use an analogy, a step-by-step build-up, or examples?",
        placeholder: "e.g. a real-world analogy, worked examples",
        default: "Use a simple analogy plus one concrete example." },
      { id: "teach_check", block: "Success criteria",
        label: "Should Claude check the learner's understanding at the end?",
        placeholder: "e.g. one question, a short quiz",
        default: "End with one short question to check understanding." }
    ]
  };

  var BLOCK_ORDER = [
    "Role", "Task", "Context", "Inputs", "Method",
    "Output format", "Constraints", "Success criteria"
  ];
  var CONDITIONAL_BLOCKS = { "Inputs": true, "Method": true };

  function classify(brief) {
    if (typeof brief !== "string" || brief.trim() === "") {
      return { error: "empty" };
    }
    var text = brief.toLowerCase();
    var best = null;
    var bestScore = 0;
    for (var i = 0; i < ARCHETYPES.length; i++) {
      var a = ARCHETYPES[i];
      var score = 0;
      for (var k = 0; k < a.keywords.length; k++) {
        if (text.indexOf(a.keywords[k]) !== -1) score++;
      }
      if (score > bestScore) {
        bestScore = score;
        best = a.id;
      }
    }
    if (!best) best = "write";
    return { archetype: best };
  }

  function getQuestions(archetypeId) {
    var specific = ARCHETYPE_QUESTIONS[archetypeId] || ARCHETYPE_QUESTIONS.write;
    return CORE_QUESTIONS.concat(specific);
  }

  function tighten(brief) {
    return String(brief == null ? "" : brief).trim().replace(/[ \t]+/g, " ");
  }

  function resolvedOrDefault(q, answers) {
    var v = answers && Object.prototype.hasOwnProperty.call(answers, q.id) ? answers[q.id] : "";
    var trimmed = (typeof v === "string" ? v : "").trim();
    return trimmed !== "" ? trimmed : q.default;
  }

  function resolvedOnly(q, answers) {
    var v = answers && Object.prototype.hasOwnProperty.call(answers, q.id) ? answers[q.id] : "";
    var trimmed = (typeof v === "string" ? v : "").trim();
    return trimmed !== "" ? trimmed : null;
  }

  function linesForBlock(questions, blockName, answers, mode) {
    var out = [];
    for (var i = 0; i < questions.length; i++) {
      var q = questions[i];
      if (q.block !== blockName) continue;
      var val = mode === "conditional" ? resolvedOnly(q, answers) : resolvedOrDefault(q, answers);
      if (val) out.push(val);
    }
    return out;
  }

  function appendAiLines(lines, aiList) {
    if (!aiList || !Array.isArray(aiList)) return lines;
    for (var i = 0; i < aiList.length; i++) {
      var t = String(aiList[i] == null ? "" : aiList[i]).trim();
      if (t) lines.push(t);
    }
    return lines;
  }

  function assemble(opts) {
    opts = opts || {};
    var archetypeId = opts.archetypeId;
    var brief = opts.brief;
    var answers = opts.answers || {};
    var aiAnswers = opts.aiAnswers;
    var questions = getQuestions(archetypeId);

    var blocks = [];

    blocks.push(["Role", linesForBlock(questions, "Role", answers, "default")]);
    blocks.push(["Task", [tighten(brief)]]);

    var contextLines = linesForBlock(questions, "Context", answers, "default");
    appendAiLines(contextLines, aiAnswers && aiAnswers.context);
    blocks.push(["Context", contextLines]);

    blocks.push(["Inputs", linesForBlock(questions, "Inputs", answers, "conditional")]);
    blocks.push(["Method", linesForBlock(questions, "Method", answers, "conditional")]);
    blocks.push(["Output format", linesForBlock(questions, "Output format", answers, "default")]);

    var constraintLines = linesForBlock(questions, "Constraints", answers, "default");
    appendAiLines(constraintLines, aiAnswers && aiAnswers.constraints);
    blocks.push(["Constraints", constraintLines]);

    blocks.push(["Success criteria", linesForBlock(questions, "Success criteria", answers, "default")]);

    var out = [];
    for (var i = 0; i < blocks.length; i++) {
      var heading = blocks[i][0];
      var lines = blocks[i][1];
      if (!lines || lines.length === 0) continue;
      out.push(heading + ":\n" + lines.join("\n"));
    }
    return out.join("\n\n");
  }

  var PE = {
    ARCHETYPES: ARCHETYPES,
    CORE_QUESTIONS: CORE_QUESTIONS,
    ARCHETYPE_QUESTIONS: ARCHETYPE_QUESTIONS,
    BLOCK_ORDER: BLOCK_ORDER,
    classify: classify,
    getQuestions: getQuestions,
    assemble: assemble
  };

  if (typeof globalThis !== "undefined") globalThis.PE = PE;
  if (typeof window !== "undefined") window.PE = PE;
})();
