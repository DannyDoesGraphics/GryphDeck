"use client";

import { useEffect, useState } from "react";

const ROTATION_INTERVAL = 5000;
const FADE_DURATION = 800;

export function SponsorshipBadge() {
  const [sponsors, setSponsors] = useState([]);
  const [index, setIndex] = useState(0);
  const [visible, setVisible] = useState(true);

  useEffect(() => {
    const controller = new AbortController();

    async function loadSponsors() {
      try {
        const response = await fetch("/api/sponsors", {
          cache: "no-store",
          signal: controller.signal,
        });

        if (!response.ok) {
          throw new Error("Could not load sponsor images.");
        }

        const images = await response.json();

        if (!controller.signal.aborted) {
          setSponsors(images);
        }
      } catch (error) {
        if (error.name !== "AbortError") {
          console.warn("Sponsor images unavailable.");
        }
      }
    }

    loadSponsors();

    return () => controller.abort();
  }, []);

  useEffect(() => {
    if (sponsors.length < 2) return;

    const timer = setInterval(() => {
      setVisible(false);

      setTimeout(() => {
        setIndex((current) => (current + 1) % sponsors.length);
        setVisible(true);
      }, FADE_DURATION);
    }, ROTATION_INTERVAL);

    return () => clearInterval(timer);
  }, [sponsors.length]);

  if (!sponsors.length) return null;

  const sponsor = sponsors[index % sponsors.length];

  return (
    <div
      style={{
        width: "200px",
        height: "auto",
      }}
    >
      <img
        src={sponsor.src}
        alt={sponsor.name}
        style={{
          display: "block",
          width: "200px",
          height: "auto",
          objectFit: "contain",
          opacity: visible ? 1 : 0,
          transition: `opacity ${FADE_DURATION}ms ease-in-out`,
        }}
        onError={() =>
          setSponsors((current) =>
            current.filter((image) => image.src !== sponsor.src),
          )
        }
      />
    </div>
  );
}
