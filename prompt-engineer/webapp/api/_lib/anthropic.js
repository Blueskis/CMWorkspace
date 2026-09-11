const Anthropic = require("@anthropic-ai/sdk");

let client;

// Lazy singleton: the API key is only required once a request actually
// arrives, not at cold-start/import time.
function getClient() {
  if (!client) {
    if (!process.env.ANTHROPIC_API_KEY) {
      throw new Error("ANTHROPIC_API_KEY is not set in this deployment's environment variables.");
    }
    client = new Anthropic();
  }
  return client;
}

module.exports = { getClient };
