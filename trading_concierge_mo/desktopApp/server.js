import express from "express";
import fs from "fs";
import path from "path";
import { randomUUID } from "crypto";
import { fileURLToPath } from "url";

const __filename = fileURLToPath(import.meta.url);
const __dirname = path.dirname(__filename);

/** Ordered markdown bundle: same files as HITL `assets/includes/` (copied to `hitl-policy/` in Docker). */
const DESKTOP_SKILL_MARKDOWN_FILES = ["desktop_copilot_policy.md", "desktop_stack_behaviour.md"];

function loadSharedDesktopCopilotPolicy() {
  const bases = [
    path.join(__dirname, "hitl-policy"),
    path.join(__dirname, "..", "trade-blotter-hitl-agent", "assets", "includes")
  ];
  const chunks = [];
  for (const fname of DESKTOP_SKILL_MARKDOWN_FILES) {
    let text = "";
    for (const base of bases) {
      const candidate = path.join(base, fname);
      try {
        if (fs.existsSync(candidate)) {
          text = fs.readFileSync(candidate, { encoding: "utf8" }).trim();
          break;
        }
      } catch {
        /* try next base */
      }
    }
    if (text) chunks.push(text);
  }
  return chunks.join("\n\n---\n\n");
}

const SHARED_DESKTOP_COPILOT_POLICY = loadSharedDesktopCopilotPolicy();

const app = express();
const port = Number(process.env.PORT || 5173);
const mcpBaseUrl = process.env.MCP_HTTP_BASE_URL || "http://mcp-server:7001";
const hitlA2aBase = (process.env.HITL_A2A_BASE_URL || "http://trade-blotter-hitl-agent:8100").replace(/\/$/, "");
const hitlAdkWebPublicUrl = process.env.HITL_ADK_WEB_PUBLIC_URL || "http://localhost:8200";
const hitlFailClosed = process.env.HITL_FAIL_CLOSED !== "false";

/** Mirrors `trade-blotter-hitl-agent/assets/tool_classification.yaml` (fnmatch-style * only). */
const READ_ONLY_TOOL_GLOBS = [
  "check_*",
  "list_*",
  "get_*",
  "search_*",
  "read_*",
  "describe_*",
  "fetch_*",
  "show_*",
  "find_*",
  "lookup_*",
  "query_*",
  "blotter_*",
  "*_summary",
  "*_balance",
  "*_quote",
  "health",
  "ping"
];
const MUTATING_TOOL_GLOBS = [
  "place_*",
  "submit_*",
  "cancel_*",
  "amend_*",
  "modify_*",
  "delete_*",
  "create_*",
  "update_*",
  "set_*",
  "execute_*",
  "approve_*",
  "reject_*",
  "transfer_*",
  "trade_*"
];

function globToRegex(pattern) {
  const escaped = pattern.replace(/[.+^${}()|[\]\\]/g, "\\$&");
  return new RegExp(`^${escaped.replace(/\*/g, ".*")}$`);
}

function classifyToolName(name) {
  for (const g of READ_ONLY_TOOL_GLOBS) {
    if (globToRegex(g).test(name)) return "read_only";
  }
  for (const g of MUTATING_TOOL_GLOBS) {
    if (globToRegex(g).test(name)) return "mutating";
  }
  return hitlFailClosed ? "mutating" : "read_only";
}

const pendingGeminiApprovals = new Map();
const APPROVAL_TTL_MS = 30 * 60 * 1000;

function pruneStaleApprovals() {
  const now = Date.now();
  for (const [id, entry] of pendingGeminiApprovals) {
    if (now - entry.createdAt > APPROVAL_TTL_MS) {
      pendingGeminiApprovals.delete(id);
    }
  }
}
const geminiApiKey = process.env.GEMINI_API_KEY || process.env.GOOGLE_API_KEY;
const geminiModel = process.env.GEMINI_INFERENCE_MODEL || "gemini-3.1-pro-preview";
const geminiTemperature = Number.parseFloat(process.env.GEMINI_TEMPERATURE ?? "1.0");
const geminiMaxOutputTokens = Number.parseInt(process.env.GEMINI_MAX_OUTPUT_TOKENS ?? "8192", 10);
const geminiContextModel = process.env.GEMINI_CONTEXT_MODEL || "gemini-3.1-pro-preview";
const geminiContextTemperature = Number.parseFloat(process.env.GEMINI_CONTEXT_TEMPERATURE ?? "1.0");
const geminiContextMaxOutputTokens = Number.parseInt(
  process.env.GEMINI_CONTEXT_MAX_OUTPUT_TOKENS ?? "512",
  10
);
const geminiThinkingLevel = process.env.GEMINI_THINKING_LEVEL || "high";
const geminiMaxToolSteps = Number.parseInt(process.env.GEMINI_MAX_TOOL_STEPS ?? "5", 10);

const LOG = {
  api: (method, path, status, detail = "") => {
    console.log(`[API] ${method} ${path} ${status}${detail ? ` ${detail}` : ""}`);
  },
  mcp: (method, path, status, detail = "") => {
    console.log(`[MCP] ${method} ${path} ${status}${detail ? ` ${detail}` : ""}`);
  },
  prompt: (event, detail = "") => {
    console.log(`[PROMPT] ${event}${detail ? ` ${detail}` : ""}`);
  },
  model: (event, detail = "") => {
    console.log(`[MODEL] ${event}${detail ? ` ${detail}` : ""}`);
  }
};

function truncate(str, maxLen = 200) {
  if (typeof str !== "string") return String(str).slice(0, maxLen);
  return str.length <= maxLen ? str : str.slice(0, maxLen) + "…";
}

app.use(express.json({ limit: "1mb" }));
app.use((req, _res, next) => {
  LOG.api(req.method, req.path, "(start)");
  next();
});
app.use(express.static(path.join(__dirname, "public")));
app.use("/css", express.static(path.join(__dirname, "css")));

async function proxyRequest(method, urlPath, body) {
  const targetUrl = `${mcpBaseUrl}${urlPath}`;
  const bodyPreview =
    body && method !== "GET"
      ? truncate(JSON.stringify(body), 150)
      : "";
  LOG.mcp(method, urlPath, "(request)", bodyPreview ? `body=${bodyPreview}` : "");

  const init = {
    method,
    headers: { "Content-Type": "application/json" }
  };

  if (body && method !== "GET") {
    init.body = JSON.stringify(body);
  }

  const response = await fetch(targetUrl, init);
  const text = await response.text();
  let payload = text;
  try {
    payload = JSON.parse(text);
  } catch {
    payload = text;
  }

  const status = response.status;
  const resultPreview =
    typeof payload === "string"
      ? truncate(payload, 120)
      : Array.isArray(payload)
        ? `array(${payload.length})`
        : payload && typeof payload === "object"
          ? Object.keys(payload).length
            ? `{${Object.keys(payload).slice(0, 5).join(",")}${Object.keys(payload).length > 5 ? "…" : ""}}`
            : "{}"
          : truncate(String(payload), 120);
  LOG.mcp(method, urlPath, status, `result=${resultPreview}`);

  if (!response.ok) {
    const errorMessage = typeof payload === "string" ? payload : JSON.stringify(payload);
    throw new Error(errorMessage);
  }

  return payload;
}

function formatPromptMessages(messages) {
  if (!Array.isArray(messages)) {
    return "";
  }
  return messages
    .map((message) => {
      const role = message?.role || "user";
      const content = message?.content;
      let text = "";
      if (typeof content === "string") {
        text = content;
      } else if (content && typeof content.text === "string") {
        text = content.text;
      } else if (content && content.type === "text" && typeof content.text === "string") {
        text = content.text;
      } else if (typeof message?.text === "string") {
        text = message.text;
      }
      return text ? `${role}: ${text}` : null;
    })
    .filter(Boolean)
    .join("\n");
}

function buildGeminiPrompt(toolsPayload, userMessage, context, summary, promptMessages) {
  const contextLines = Array.isArray(context)
    ? context
        .slice(-10)
        .map((entry) => `${entry.role || "user"}: ${entry.content}`)
        .join("\n")
    : "";
  const preparedPrompt = formatPromptMessages(promptMessages);
  const lines = [];
  if (SHARED_DESKTOP_COPILOT_POLICY) {
    lines.push(SHARED_DESKTOP_COPILOT_POLICY, "");
  }
  lines.push(
    "You are an assistant for the trade blotter. You may respond in one of two ways:",
    "",
    "1) TO CALL A TOOL (or signal no tool): Respond with ONLY valid JSON, no other text:",
    '   { "tool": "tool_name_or_null", "arguments": { ... }, "message": "short user-facing message" }',
    "   Use only tools from the tools JSON. If no tool applies, set tool to null and put your reply in message.",
    "",
    "2) DIRECT ANSWER (no tool): Respond with plain text only (no JSON). Use this when answering from context, explaining, or when a tool is not needed. Do not wrap in code blocks.",
    "",
    "Choose JSON when the user needs data from trade views (list views, query trades, schema, etc.). Choose plain text for greetings, explanations, or when you can answer without calling a tool.",
    "If a trade query requires a view_id and it is missing, ask for it (in message if JSON, or in your text if direct).",
    "Analyse internally all trade views when relevant; list them and ask the user to select if needed.",
    "",
    "Conversation summary:",
    summary || "(none)",
    "",
    "Conversation context:",
    contextLines || "(none)",
    "",
    "Prepared MCP prompt context:",
    preparedPrompt || "(none)",
    "",
    "Available tools JSON:",
    JSON.stringify(toolsPayload),
    "",
    `User message: ${userMessage}`
  );
  return lines.join("\n");
}

function buildFollowUpPrompt(previousSteps) {
  if (!Array.isArray(previousSteps) || previousSteps.length === 0) {
    return "";
  }
  const lines = previousSteps.map((step, i) => {
    const resultPreview =
      typeof step.result === "string"
        ? step.result
        : JSON.stringify(step.result);
    const truncated =
      resultPreview.length > 2000 ? resultPreview.slice(0, 2000) + "…" : resultPreview;
    return `Step ${i + 1}: Tool "${step.name}" with arguments ${JSON.stringify(step.arguments)} returned: ${truncated}`;
  });
  return [
    "",
    "--- Previous tool step(s) (you will be called again for the next step) ---",
    ...lines,
    "--- If another tool call is needed, respond with JSON only: { \"tool\": \"...\", \"arguments\": {...}, \"message\": \"...\" }. If done with tools, set \"tool\" to null and put the final message in \"message\". Do not respond with plain text in this follow-up; use JSON. ---"
  ].join("\n");
}

function extractJsonFromText(text) {
  if (!text) {
    return null;
  }
  const fenced = text.match(/```(?:json)?\s*([\s\S]*?)```/i);
  if (fenced && fenced[1]) {
    try {
      return JSON.parse(fenced[1].trim());
    } catch {
      // fall through to raw parsing
    }
  }
  const firstBrace = text.indexOf("{");
  const lastBrace = text.lastIndexOf("}");
  if (firstBrace !== -1 && lastBrace !== -1 && lastBrace > firstBrace) {
    try {
      return JSON.parse(text.slice(firstBrace, lastBrace + 1));
    } catch {
      return null;
    }
  }
  return null;
}

async function callGemini(prompt, { model = geminiModel, temperature = geminiTemperature, maxOutputTokens, thinkingLevel } = {}) {
  const promptLen = typeof prompt === "string" ? prompt.length : 0;
  LOG.model("request", `model=${model} promptLen=${promptLen} temperature=${temperature ?? "default"}`);

  const url = `https://generativelanguage.googleapis.com/v1beta/models/${model}:generateContent?key=${geminiApiKey}`;
  const generationConfig = {
    temperature: Number.isFinite(temperature) ? temperature : 1.0
  };
  if (Number.isFinite(maxOutputTokens)) {
    generationConfig.maxOutputTokens = maxOutputTokens;
  }
  const level = thinkingLevel ?? geminiThinkingLevel;
  if (level) {
    generationConfig.thinkingConfig = { thinkingLevel: level };
  }
  const response = await fetch(url, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({
      contents: [{ role: "user", parts: [{ text: prompt }] }],
      generationConfig
    })
  });
  const payload = await response.json();
  if (!response.ok) {
    const message = payload?.error?.message || "Gemini request failed.";
    LOG.model("error", `model=${model} status=${response.status} message=${truncate(message, 200)}`);
    throw new Error(message);
  }
  const textParts = payload?.candidates?.[0]?.content?.parts || [];
  const combinedText = textParts.map((part) => part.text || "").join("").trim();
  LOG.model("response", `model=${model} outputLen=${combinedText.length} preview=${truncate(combinedText, 120)}`);
  return combinedText;
}

async function proxyHitl(path, { method = "GET", body = undefined } = {}) {
  const url = `${hitlA2aBase}${path.startsWith("/") ? path : `/${path}`}`;
  const init = { method, headers: { Accept: "application/json" } };
  if (body !== undefined && method !== "GET" && method !== "HEAD") {
    init.headers["Content-Type"] = "application/json";
    init.body = JSON.stringify(body);
  }
  LOG.api(method, `[hitl]${path}`, "(request)");
  const response = await fetch(url, init);
  const text = await response.text();
  let payload = text;
  try {
    payload = JSON.parse(text);
  } catch {
    payload = text;
  }
  if (!response.ok) {
    const msg = typeof payload === "string" ? payload : JSON.stringify(payload);
    throw new Error(msg);
  }
  return payload;
}

async function runGeminiToolOrchestration(reqBody) {
  const message = typeof reqBody?.message === "string" ? reqBody.message : "";
  const context = Array.isArray(reqBody?.context) ? reqBody.context : [];
  const summary = typeof reqBody?.summary === "string" ? reqBody.summary : "";
  const resumeApprovalId = reqBody?.resumeApprovalId;
  const rejectApprovalId = reqBody?.rejectApprovalId;

  pruneStaleApprovals();

  if (rejectApprovalId) {
    if (pendingGeminiApprovals.has(rejectApprovalId)) {
      pendingGeminiApprovals.delete(rejectApprovalId);
    }
    return {
      message:
        "The proposed mutating operation was cancelled. Say if you want to try a different approach.",
      rejected: true
    };
  }

  let steps = [];
  let loopIterationStart = 0;
  let carryMessage = message.trim();
  let carryContext = context;
  let carrySummary = summary;
  let promptMessages = [];
  let toolsPayload;

  if (resumeApprovalId) {
    const pending = pendingGeminiApprovals.get(resumeApprovalId);
    if (!pending) {
      throw new Error("Approval session expired or unknown. Send a new request.");
    }
    const { tool, arguments: args, resume } = pending;
    pendingGeminiApprovals.delete(resumeApprovalId);
    LOG.prompt("hitl approve run", `tool=${tool}`);
    const toolResult = await proxyRequest("POST", `/tool/${encodeURIComponent(tool)}`, {
      arguments: args
    });
    steps = [...resume.steps, { name: tool, arguments: args, result: toolResult }];
    loopIterationStart = resume.loopIteration + 1;
    carryMessage = resume.message;
    carryContext = resume.context;
    carrySummary = resume.summary;
    promptMessages = resume.promptMessages;
    toolsPayload = resume.toolsPayload;
  } else {
    if (!carryMessage) {
      throw new Error("Missing message in request body.");
    }
    toolsPayload = await proxyRequest("GET", "/tools");
    try {
      const promptPayload = await proxyRequest("POST", "/prompt/analyze_trade_query", {
        arguments: { user_question: carryMessage }
      });
      promptMessages = Array.isArray(promptPayload?.messages) ? promptPayload.messages : [];
      LOG.prompt(
        "analyze_trade_query",
        `user_question=${truncate(carryMessage, 80)} messages=${promptMessages.length}`
      );
    } catch (error) {
      LOG.prompt("analyze_trade_query failed", `error=${error?.message || error}`);
      console.warn("Failed to load MCP prompt context:", error?.message || error);
    }
  }

  const toolsList = Array.isArray(toolsPayload)
    ? toolsPayload
    : Array.isArray(toolsPayload?.tools)
      ? toolsPayload.tools
      : [];
  const toolNames = new Set(toolsList.map((tool) => tool.name));
  const maxSteps = Number.isFinite(geminiMaxToolSteps) && geminiMaxToolSteps > 0 ? geminiMaxToolSteps : 5;

  let lastMessage = "";
  let lastModelText = "";

  for (let stepIndex = loopIterationStart; stepIndex < maxSteps; stepIndex++) {
    const basePrompt = buildGeminiPrompt(toolsPayload, carryMessage, carryContext, carrySummary, promptMessages);
    const followUp = buildFollowUpPrompt(steps);
    const prompt = basePrompt + followUp;

    const modelText = await callGemini(prompt, {
      maxOutputTokens: Number.isFinite(geminiMaxOutputTokens) ? geminiMaxOutputTokens : 8192,
      thinkingLevel: "high"
    });
    lastModelText = modelText;
    const modelJson = extractJsonFromText(modelText);
    const isToolJson = modelJson && typeof modelJson === "object" && "tool" in modelJson;

    if (!isToolJson) {
      const directAnswer = typeof modelText === "string" ? modelText.trim() : String(modelText);
      LOG.prompt("gemini result", `directAnswer preview=${truncate(directAnswer, 100)}`);
      return {
        message: directAnswer,
        directAnswer: true,
        modelText: lastModelText,
        toolCalls: steps.length ? steps : undefined
      };
    }

    lastMessage = modelJson.message || "";

    if (!modelJson.tool) {
      const lastStep = steps[steps.length - 1];
      LOG.prompt("gemini result", `toolCalls=${steps.length} message=${truncate(lastMessage, 80)}`);
      return {
        message: lastMessage || "No further tool selected.",
        toolCalls: steps.length ? steps : undefined,
        toolCall: lastStep ? { name: lastStep.name, arguments: lastStep.arguments } : undefined,
        toolResult: lastStep?.result,
        modelText: lastModelText,
        multiStep: steps.length > 1
      };
    }

    if (!toolNames.has(modelJson.tool)) {
      throw new Error(`Unknown tool selected: ${modelJson.tool}`);
    }

    const toolArgs = modelJson.arguments || {};
    LOG.prompt(
      "gemini tool step",
      `step=${stepIndex + 1} tool=${modelJson.tool} args=${truncate(JSON.stringify(toolArgs), 100)}`
    );

    const kind = classifyToolName(modelJson.tool);
    if (kind === "mutating") {
      const approvalId = randomUUID();
      pendingGeminiApprovals.set(approvalId, {
        createdAt: Date.now(),
        tool: modelJson.tool,
        arguments: toolArgs,
        resume: {
          message: carryMessage,
          context: carryContext,
          summary: carrySummary,
          promptMessages,
          steps: [...steps],
          toolsPayload,
          loopIteration: stepIndex
        }
      });
      LOG.api("POST", "/api/llm/gemini", 200, `needsApproval tool=${modelJson.tool}`);
      return {
        needsApproval: true,
        approvalId,
        tool: modelJson.tool,
        arguments: toolArgs,
        message:
          lastMessage ||
          `Human approval is required before running mutating tool «${modelJson.tool}».`,
        partialSteps: steps.length ? steps : undefined,
        modelText: lastModelText
      };
    }

    const toolResult = await proxyRequest("POST", `/tool/${encodeURIComponent(modelJson.tool)}`, {
      arguments: toolArgs
    });
    steps.push({ name: modelJson.tool, arguments: toolArgs, result: toolResult });
  }

  const lastStep = steps[steps.length - 1];
  LOG.prompt("gemini result", `multiStep message=${truncate(lastMessage, 80)}`);
  return {
    message: lastMessage || "Max steps reached.",
    toolCalls: steps,
    toolCall: lastStep ? { name: lastStep.name, arguments: lastStep.arguments } : undefined,
    toolResult: lastStep?.result,
    modelText: lastModelText,
    multiStep: true
  };
}

app.get("/api/config", (_req, res) => {
  res.json({
    hitlAdkWebUrl: hitlAdkWebPublicUrl,
    hitlA2aConfigured: Boolean(hitlA2aBase),
    toolPolicy: { failClosed: hitlFailClosed }
  });
});

app.get("/api/health", async (_req, res) => {
  try {
    const data = await proxyRequest("GET", "/health");
    LOG.api("GET", "/api/health", 200);
    res.json(data);
  } catch (error) {
    LOG.api("GET", "/api/health", 502, `error=${error.message}`);
    res.status(502).json({ error: error.message });
  }
});

app.get("/api/tools", async (_req, res) => {
  try {
    const data = await proxyRequest("GET", "/tools");
    LOG.api("GET", "/api/tools", 200);
    res.json(data);
  } catch (error) {
    LOG.api("GET", "/api/tools", 502, `error=${error.message}`);
    res.status(502).json({ error: error.message });
  }
});

app.get("/api/resources", async (_req, res) => {
  try {
    const data = await proxyRequest("GET", "/resources");
    LOG.api("GET", "/api/resources", 200);
    res.json(data);
  } catch (error) {
    LOG.api("GET", "/api/resources", 502, `error=${error.message}`);
    res.status(502).json({ error: error.message });
  }
});

app.get("/api/prompts", async (_req, res) => {
  try {
    const data = await proxyRequest("GET", "/prompts");
    LOG.api("GET", "/api/prompts", 200);
    res.json(data);
  } catch (error) {
    LOG.api("GET", "/api/prompts", 502, `error=${error.message}`);
    res.status(502).json({ error: error.message });
  }
});

app.get("/api/resource", async (req, res) => {
  try {
    const uri = req.query.uri;
    if (!uri) {
      LOG.api("GET", "/api/resource", 400, "missing uri");
      res.status(400).json({ error: "Missing uri query parameter." });
      return;
    }
    const data = await proxyRequest("GET", `/resource?uri=${encodeURIComponent(uri)}`);
    LOG.api("GET", "/api/resource", 200, `uri=${truncate(uri, 80)}`);
    res.json(data);
  } catch (error) {
    LOG.api("GET", "/api/resource", 502, `error=${error.message}`);
    res.status(502).json({ error: error.message });
  }
});

app.post("/api/tool/:name", async (req, res) => {
  const name = req.params.name;
  try {
    const data = await proxyRequest("POST", `/tool/${encodeURIComponent(name)}`, {
      arguments: req.body || {}
    });
    LOG.api("POST", `/api/tool/${name}`, 200);
    res.json(data);
  } catch (error) {
    LOG.api("POST", `/api/tool/${name}`, 502, `error=${error.message}`);
    res.status(502).json({ error: error.message });
  }
});

app.post("/api/prompt/:name", async (req, res) => {
  const name = req.params.name;
  try {
    const data = await proxyRequest("POST", `/prompt/${encodeURIComponent(name)}`, {
      arguments: req.body || {}
    });
    const msgCount = Array.isArray(data?.messages) ? data.messages.length : 0;
    LOG.api("POST", `/api/prompt/${name}`, 200, `messages=${msgCount}`);
    LOG.prompt("result", `prompt=${name} messages=${msgCount}`);
    res.json(data);
  } catch (error) {
    LOG.api("POST", `/api/prompt/${name}`, 502, `error=${error.message}`);
    LOG.prompt("error", `prompt=${name} error=${error.message}`);
    res.status(502).json({ error: error.message });
  }
});

app.post("/api/llm/gemini", async (req, res) => {
  try {
    if (!geminiApiKey) {
      LOG.api("POST", "/api/llm/gemini", 400, "no API key");
      res.status(400).json({ error: "Gemini API key not configured. Set GEMINI_API_KEY." });
      return;
    }
    const hasResume = Boolean(req.body?.resumeApprovalId);
    const hasReject = Boolean(req.body?.rejectApprovalId);
    const message = req.body?.message?.trim();
    if (!message && !hasResume && !hasReject) {
      LOG.api("POST", "/api/llm/gemini", 400, "missing message");
      res.status(400).json({ error: "Missing message or approval action in request body." });
      return;
    }
    const payload = await runGeminiToolOrchestration(req.body);
    LOG.api("POST", "/api/llm/gemini", 200, payload.needsApproval ? "needsApproval" : "ok");
    res.json(payload);
  } catch (error) {
    const status = /Unknown tool/.test(error.message) ? 400 : 502;
    LOG.api("POST", "/api/llm/gemini", status, `error=${error.message}`);
    res.status(status).json({ error: error.message });
  }
});

app.post("/api/hitl/plan", async (req, res) => {
  try {
    const goal = req.body?.goal?.trim();
    if (!goal) {
      res.status(400).json({ error: "Missing goal." });
      return;
    }
    const data = await proxyHitl("/v1/a2a/plan", {
      method: "POST",
      body: {
        goal,
        context: req.body?.context,
        tool_names: req.body?.tool_names
      }
    });
    LOG.api("POST", "/api/hitl/plan", 200);
    res.json(data);
  } catch (error) {
    LOG.api("POST", "/api/hitl/plan", 502, `error=${error.message}`);
    res.status(502).json({ error: error.message });
  }
});

app.post("/api/hitl/classify", async (req, res) => {
  try {
    const names = req.body?.names;
    if (!Array.isArray(names) || !names.length) {
      res.status(400).json({ error: "Missing names array." });
      return;
    }
    const data = await proxyHitl("/v1/a2a/classify", { method: "POST", body: { names } });
    res.json(data);
  } catch (error) {
    res.status(502).json({ error: error.message });
  }
});

app.post("/api/hitl/validate_step", async (req, res) => {
  try {
    const data = await proxyHitl("/v1/a2a/validate_step", {
      method: "POST",
      body: {
        tool: req.body?.tool,
        arguments: req.body?.arguments || {},
        rationale: req.body?.rationale,
        prior_steps: req.body?.prior_steps
      }
    });
    res.json(data);
  } catch (error) {
    res.status(502).json({ error: error.message });
  }
});

app.get("/api/hitl/skills", async (_req, res) => {
  try {
    const data = await proxyHitl("/v1/a2a/skills", { method: "GET" });
    res.json(data);
  } catch (error) {
    res.status(502).json({ error: error.message });
  }
});

app.post("/api/llm/summarize", async (req, res) => {
  try {
    if (!geminiApiKey) {
      LOG.api("POST", "/api/llm/summarize", 400, "no API key");
      res.status(400).json({ error: "Gemini API key not configured. Set GEMINI_API_KEY." });
      return;
    }
    const summary = typeof req.body?.summary === "string" ? req.body.summary : "";
    const history = Array.isArray(req.body?.history) ? req.body.history : [];
    const historyLines = history
      .map((entry) => `${entry.role || "user"}: ${entry.content}`)
      .join("\n");

    const prompt = [
      "You summarize a long-running trading assistant session for tool selection.",
      "Return a concise summary focusing on:",
      "- user intent and constraints",
      "- selected trade view IDs",
      "- filters and parameters used",
      "- important tool results (counts, key fields)",
      "Keep it short and actionable.",
      "",
      "Existing summary:",
      summary || "(none)",
      "",
      "New conversation lines:",
      historyLines || "(none)"
    ].join("\n");

    const modelText = await callGemini(prompt, {
      model: geminiContextModel,
      temperature: Number.isFinite(geminiContextTemperature) ? geminiContextTemperature : 0.2,
      maxOutputTokens: Number.isFinite(geminiContextMaxOutputTokens) ? geminiContextMaxOutputTokens : 512,
      thinkingLevel: "low"
    });

    LOG.api("POST", "/api/llm/summarize", 200, `summaryLen=${modelText?.length ?? 0}`);
    LOG.prompt("summarize result", `preview=${truncate(modelText, 100)}`);
    res.json({ summary: modelText });
  } catch (error) {
    LOG.api("POST", "/api/llm/summarize", 502, `error=${error.message}`);
    res.status(502).json({ error: error.message });
  }
});

app.listen(port, () => {
  console.log(`Desktop app running on http://localhost:${port}`);
});
