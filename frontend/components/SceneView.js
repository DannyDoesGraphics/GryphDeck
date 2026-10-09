"use client";

import { useEffect, useState } from "react";
import { LOCATIONS, validOverlay } from "@/lib/overlay.mjs";
import { Intermission } from "./customComponents/Intermission.js";
import { TechPause } from "./customComponents/TechPause.js";
import { StartingSoon } from "./customComponents/StartingSoon.js";
import { ScorePregame } from "./customComponents/ScorePregame.js";
import { ScoreIngame } from "./customComponents/ScoreIngame.js";
import { MapPicks } from "./customComponents/MapPicks.js";
import { SponsorshipBadge } from "./customComponents/SponsorshipBadge.js";
import { TeamRoster } from "./customComponents/TeamRoster.js";
import { CharacterBansPregame } from "./customComponents/CharacterBansPregame.js";
import { CharacterBansIngame } from "./customComponents/CharacterBansIngame.js";

function ComponentContent({ component }) {
  const { name, data } = component;
  const key = name.toLowerCase();

  if (key === "team roster") {
    return <TeamRoster scene={data} />;
  }
  if (key === "score ingame") {
    return <ScoreIngame scene={data} />;
  }
  if (key === "score pregame") {
    return <ScorePregame scene={data} />;
  }
  if (key === "map picks") {
    return <MapPicks scene={data} />;
  }
  if (key === "sponsorships badge") {
    return <SponsorshipBadge />;
  }
  if (key === "character bans ingame") {
    return <CharacterBansIngame scene={data} />;
  }
  if (key === "character bans pregame") {
    return <CharacterBansPregame scene={data} />;
  }
  if (key === "intermission") {
    return <Intermission scene={data} />;
  }
  if (key === "tech pause") {
    return <TechPause scene={data} />;
  }
  if (key === "starting soon") {
    return <StartingSoon scene={data} />;
  }

  return <p>how did we get here?</p>;
}

export default function SceneView({ scene }) {
  const [document, setDocument] = useState(null);

  useEffect(() => {
    let stopped = false;
    let timer;
    let activeRequest;
    async function refresh() {
      activeRequest = new AbortController();
      const timeout = setTimeout(() => activeRequest.abort(), 3000);
      try {
        const response = await fetch("/api/overlay", { cache: "no-store", signal: activeRequest.signal });
        if (!response.ok) throw new Error(`Overlay receiver returned ${response.status}`);
        const next = await response.json();
        if (!validOverlay(next)) throw new Error("Invalid overlay document");
        if (!stopped) setDocument(next);
      } catch {
        // Keep the last frame on a disconnect. Never put connection errors on air.
      } finally {
        clearTimeout(timeout);
        if (!stopped) timer = setTimeout(refresh, 400);
      }
    }
    refresh();
    return () => { stopped = true; clearTimeout(timer); activeRequest?.abort(); };
  }, []);

  const components = document?.scenes[scene] || [];
  const backgroundComponents = components.filter(c => c.location === "Center");
  const overlayComponents = components.filter(c => c.location !== "Center");

  return (
    <main className="overlay-canvas" data-scene={scene} aria-label={`${scene} overlay`}>
      {backgroundComponents.map((component, index) => (
        <div className="overlay-background" style={{ "--element-scale": component.scale ?? 1 }} key={index}>
          <ComponentContent component={component} />
        </div>
      ))}

      {LOCATIONS.filter(location => location !== "Center").map(location => {
        const placed = overlayComponents.filter(component => component.location === location);
        return placed.length > 0 && (
          <div className="overlay-slot" data-location={location} key={location}>
            {placed.map((component, index) => (
              <section className="overlay-scaled" style={{ "--element-scale": component.scale ?? 1 }} key={index}>
                <ComponentContent component={component} />
              </section>
            ))}
          </div>
        );
      })}
    </main>
  );
}
