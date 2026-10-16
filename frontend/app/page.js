import Link from "next/link";

const scenes = ["idle", "pregame", "ingame"];

export default function Home() {
  return (
    <main className="launcher">
      <div className="launcher-card">
        <h1>GryphDeck overlays</h1>
        <p>
          Add one scene URL as an OBS Browser Source. Set the source size to
          your broadcast resolution, for example 1920 × 1080.
        </p>
        <nav>
          {scenes.map((scene) => (
            <Link key={scene} href={`/${scene}`}>
              /{scene}
            </Link>
          ))}
        </nav>
        <p>Only enabled components appear. An empty scene is transparent.</p>
        <p>
          <a
            href={`${process.env.FLASK_API_URL || process.env.NEXT_PUBLIC_API_URL || "http://localhost:5000"}/UI`}
          >
            Open broadcast controls
          </a>
        </p>
      </div>
    </main>
  );
}
