// Simple fixed-window rate limiter, keyed by client IP + endpoint.
//
// NOTE ON LIMITS: state lives in this serverless function's process memory.
// It resets on cold start and is NOT shared across concurrent instances, so
// under real concurrent load this is a soft cap, not a hard guarantee. That
// tradeoff is intentional for a low-traffic public tool with no login: it
// bounds the worst case (a script hammering one instance) without needing an
// external store. If abuse becomes a real problem, replace this module with
// one backed by Vercel KV or Upstash Redis — the call sites don't need to
// change.
const WINDOW_MS = 60 * 60 * 1000; // 1 hour
const MAX_REQUESTS = 20; // per key, per window

const buckets = new Map();

function checkRateLimit(key) {
  const now = Date.now();
  const bucket = buckets.get(key);

  if (!bucket || now - bucket.windowStart > WINDOW_MS) {
    buckets.set(key, { windowStart: now, count: 1 });
    return { allowed: true };
  }
  if (bucket.count >= MAX_REQUESTS) {
    return { allowed: false, retryAfterMs: WINDOW_MS - (now - bucket.windowStart) };
  }
  bucket.count += 1;
  return { allowed: true };
}

function clientKey(req) {
  const fwd = req.headers["x-forwarded-for"];
  const first = Array.isArray(fwd) ? fwd[0] : fwd || "";
  const ip = first.split(",")[0].trim();
  return ip || "unknown";
}

module.exports = { checkRateLimit, clientKey };
