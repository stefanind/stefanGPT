export default {
  async fetch(request, env, ctx) {
    if (request.method === "OPTIONS") {
      return handleCors();
    }

    const startedAt = Date.now();
    const url = new URL(request.url);

    if (url.pathname !== "/chat") {
      return jsonResponse({ error: "Not found" }, 404);
    }

    if (request.method !== "POST") {
      return jsonResponse({ error: "Method not allowed" }, 405);
    }

    let body;

    try {
      body = await request.json();
    } catch {
      return jsonResponse({ error: "Invalid JSON body" }, 400);
    }

    const message = body.message;

    if (!message || typeof message !== "string" || !message.trim()) {
      return jsonResponse({ error: "Missing message" }, 400);
    }

    const maxNewTokens = body.max_new_tokens ?? 250;

    const runpodUrl = `https://api.runpod.ai/v2/${env.RUNPOD_ENDPOINT_ID}/runsync`;

    let runpodResponse;
    let data;

    try {
      runpodResponse = await fetch(runpodUrl, {
        method: "POST",
        headers: {
          "Content-Type": "application/json",
          "Authorization": `Bearer ${env.RUNPOD_API_KEY}`,
        },
        body: JSON.stringify({
          input: {
            message: message.trim(),
            max_new_tokens: maxNewTokens,
          },
        }),
      });

      data = await runpodResponse.json();
    } catch (error) {
      return jsonResponse(
        {
          error: "Failed to contact RunPod",
          detail: String(error),
        },
        502
      );
    }

    if (!runpodResponse.ok) {
      return jsonResponse(
        {
          error: "RunPod request failed",
          detail: data,
        },
        runpodResponse.status
      );
    }

    if (data.status !== "COMPLETED") {
      return jsonResponse(
        {
          error: "RunPod job did not complete",
          status: data.status,
        },
        500
      );
    }

    const answer = data.output?.answer ?? "";

    if (!answer) {
      return jsonResponse(
        {
          error: "RunPod completed but returned no answer",
        },
        500
      );
    }

    ctx.waitUntil(
      logChat(env, {
        message: message.trim(),
        answer,
        status: data.status,
        latencyMs: Date.now() - startedAt,
        maxNewTokens,
        modelName: data.output?.model_name ?? "",
        adapterDir: data.output?.adapter_dir ?? "",
      })
    );

    return jsonResponse({ answer }, 200);
  },
};

async function logChat(env, entry) {
  if (!env.DB) {
    return;
  }

  try {
    await env.DB.prepare(
      `INSERT INTO chat_logs
       (id, created_at, message, answer, status, latency_ms, max_new_tokens, model_name, adapter_dir)
       VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)`
    ).bind(
      crypto.randomUUID(),
      new Date().toISOString(),
      entry.message,
      entry.answer,
      entry.status,
      entry.latencyMs,
      entry.maxNewTokens,
      entry.modelName,
      entry.adapterDir
    ).run();
  } catch (error) {
    console.error("Failed to log chat", error);
  }
}

function handleCors() {
  return new Response(null, {
    status: 204,
    headers: corsHeaders(),
  });
}

function jsonResponse(data, status = 200) {
  return new Response(JSON.stringify(data), {
    status,
    headers: {
      "Content-Type": "application/json",
      ...corsHeaders(),
    },
  });
}

function corsHeaders() {
  return {
    "Access-Control-Allow-Origin": "*",
    "Access-Control-Allow-Methods": "POST, OPTIONS",
    "Access-Control-Allow-Headers": "Content-Type",
  };
}
