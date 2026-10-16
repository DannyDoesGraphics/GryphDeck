import { readdir } from "node:fs/promises";
import path from "node:path";

export const runtime = "nodejs";
export const dynamic = "force-dynamic";

export async function GET() {
  const headers = { "Cache-Control": "no-store" };
  try {
    const entries = await readdir(
      path.join(process.cwd(), "public", "static", "Sponsors"),
      { withFileTypes: true },
    );
    const images = entries
      .filter(
        (entry) =>
          entry.isFile() &&
          /\.(png|jpe?g|webp|gif|svg|avif)$/i.test(entry.name),
      )
      .map((entry) => entry.name)
      .sort((left, right) => left.localeCompare(right))
      .map((filename) => ({
        name: path.parse(filename).name,
        src: `/static/Sponsors/${encodeURIComponent(filename)}`,
      }));
    return Response.json(images, { headers });
  } catch (error) {
    if (error.code === "ENOENT") return Response.json([], { headers });
    console.error("Could not read the sponsor image directory:", error);
    return Response.json(
      { error: "Could not load sponsor images." },
      { status: 500, headers },
    );
  }
}
