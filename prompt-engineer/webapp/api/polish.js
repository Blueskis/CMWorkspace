const { getClient } = require("./_lib/anthropic");
const { checkRateLimit, clientKey } = require("./_lib/rateLimit");
const { sendAnthropicError } = require("./_lib/anthropicError");

const MAX_PROMPT_CHARS = 8000;

module.exports = async function handler(req, res) {
  if (req.method !== "POST") {
    res.status(405).json({ error: "Method not allowed" });
    return;
  }

  const rl = checkRateLimit("polish:" + clientKey(req));
  if (!rl.allowed) {
    res.setHeader("Retry-After", String(Math.ceil(rl.retryAfterMs / 1000)));
    res.status(429).json({ error: "Too many requests from this address. Try again later." });
    return;
  }

  const { prompt } = req.body || {};
  if (typeof prompt !== "string" || prompt.trim() === "") {
    res.status(400).json({ error: "Missing prompt text." });
    return;
  }
  if (prompt.length > MAX_PROMPT_CHARS) {
    res.status(400).json({ error: `Prompt is too long (max ${MAX_PROMPT_CHARS} characters).` });
    return;
  }

  const instruction =
    "Improve the wording, flow, and precision of the following AI prompt without changing " +
    "its meaning, removing any of its section headings, or dropping any instruction it " +
    "contains. Keep the same section headings and overall structure. Reply with only the " +
    "improved prompt text, no preamble, no commentary, no code fences.\n\n---\n\n" +
    prompt;

  try {
    const client = getClient();
    const response = await client.messages.create({
      model: "claude-opus-5",
      max_tokens: 4096,
      output_config: { effort: "low" }, // text polishing doesn't need deep reasoning; keeps a public-facing cost down
      messages: [{ role: "user", content: instruction }],
    });
    const textBlock = response.content.find((b) => b.type === "text");
    res.status(200).json({ text: textBlock ? textBlock.text : "" });
  } catch (error) {
    sendAnthropicError(error, res);
  }
};
