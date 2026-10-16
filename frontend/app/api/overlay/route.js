import { createOverlayStore, validOverlay } from "@/lib/overlay.mjs";

export const runtime = "nodejs";
export const dynamic = "force-dynamic";

const storeKey = Symbol.for("gryphdeck.overlay");
const store = (globalThis[storeKey] ??= createOverlayStore());
const headers = { "Cache-Control": "no-store" };

export async function POST(request) {
  let document;
  try {
    document = await request.json();
  } catch {
    return Response.json({ error: "Expected JSON." }, { status: 400, headers });
  }
  if (!validOverlay(document)) {
    return Response.json(
      {
        error:
          "Expected game and idle, pregame, ingame component lists with valid locations and data.",
      },
      { status: 400, headers },
    );
  }
  store.publish(document);
  return Response.json({ received: true }, { headers });
}

export async function GET() {
  try {
    const document = await store.read(async () => {
      const backend =
        process.env.FLASK_API_URL ||
        process.env.NEXT_PUBLIC_API_URL ||
        "http://127.0.0.1:5000";
      const response = await fetch(
        `${backend.replace(/\/$/, "")}/api/overlay`,
        {
          cache: "no-store",
          signal: AbortSignal.timeout(1000),
        },
      );
      if (!response.ok) throw new Error("Flask snapshot unavailable.");
      return response.json();
    });
    return Response.json(document, { headers });
  } catch {
    return Response.json(
      { error: "Waiting for the Flask scene document." },
      { status: 503, headers },
    );
  }
}
