export default {
  async fetch(request, env) {
    if (request.method === "OPTIONS") {
      return handleCors();
    }

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

    return jsonResponse({ answer }, 200);
  },
};

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