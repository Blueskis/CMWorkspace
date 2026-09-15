const Anthropic = require("@anthropic-ai/sdk");

// Maps an error thrown by the Anthropic SDK to an HTTP response for the
// browser. Chain is most-specific-first, per the SDK's own error hierarchy —
// see shared/error-codes.md in the claude-api skill.
function sendAnthropicError(error, res) {
  if (error instanceof Anthropic.RateLimitError) {
    res.status(429).json({ error: "The AI service is busy right now. Try again shortly." });
  } else if (error instanceof Anthropic.AuthenticationError) {
    console.error("Anthropic authentication error:", error.message);
    res.status(500).json({ error: "Server misconfiguration. Contact the site owner." });
  } else if (error instanceof Anthropic.APIError) {
    console.error("Anthropic API error:", error.status, error.message);
    res.status(502).json({ error: "The AI service returned an error. Try again." });
  } else {
    console.error("Unexpected error calling Anthropic:", error);
    res.status(500).json({ error: "Something went wrong on the server." });
  }
}

module.exports = { sendAnthropicError };
