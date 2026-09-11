const { getClient } = require("./_lib/anthropic");
const { checkRateLimit, clientKey } = require("./_lib/rateLimit");
const { sendAnthropicError } = require("./_lib/anthropicError");

const MAX_BRIEF_CHARS = 4000;

module.exports = async function handler(req, res) {
  if (req.method !== "POST") {
    res.status(405).json({ error: "Method not allowed" });
    return;
  }

  const rl = checkRateLimit("tailor:" + clientKey(req));
  if (!rl.allowed) {
    res.setHeader("Retry-After", String(Math.ceil(rl.retryAfterMs / 1000)));
    res.status(429).json({ error: "Too many requests from this address. Try again later." });
    return;
  }

  const { brief, archetypeLabel } = req.body || {};
  if (typeof brief !== "string" || brief.trim() === "") {
    res.status(400).json({ error: "Missing brief text." });
    return;
  }
  if (brief.length > MAX_BRIEF_CHARS) {
    res.status(400).json({ error: `Brief is too long (max ${MAX_BRIEF_CHARS} characters).` });
    return;
  }

  const prompt =
    "A person is about to write a prompt for an AI assistant. Their brief:\n\n" +
    brief +
    "\n\nTask type: " + (typeof archetypeLabel === "string" && archetypeLabel ? archetypeLabel : "General") +
    "\n\nSuggest exactly 2 short follow-up questions that would meaningfully sharpen this " +
    "prompt (things not already obvious from the brief). Reply with only a JSON array of " +
    '2 short strings, no other text. Example: ["Question one?", "Question two?"]';

  try {
    const client = getClient();
    const response = await client.messages.create({
      model: "claude-haiku-4-5",
      max_tokens: 1024,
      // No `output_config.effort` here: Haiku 4.5 doesn't support the effort
      // parameter (the API rejects it), unlike the Opus/Sonnet 5 tier.
      messages: [{ role: "user", content: prompt }],
    });
    const textBlock = response.content.find((b) => b.type === "text");

    let questions = [];
    try {
      const parsed = JSON.parse((textBlock && textBlock.text) || "[]");
      if (Array.isArray(parsed)) {
        questions = parsed.filter((x) => typeof x === "string" && x.trim() !== "").slice(0, 2);
      }
    } catch (_parseError) {
      // Leave questions empty; the frontend already handles "no usable questions".
    }

    res.status(200).json({ questions });
  } catch (error) {
    sendAnthropicError(error, res);
  }
};
