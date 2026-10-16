"use client";

import { useLayoutEffect, useRef } from "react";
import styles from "./ScoreIngame.module.css";

function FittedText({ children, className, sizeRatio = 0.65 }) {
  const boxRef = useRef(null);
  const textRef = useRef(null);

  useLayoutEffect(() => {
    const box = boxRef.current;
    const text = textRef.current;
    let mounted = true;
    const fit = () => {
      if (!mounted || !box.clientWidth || !box.clientHeight) return;
      const style = getComputedStyle(box);
      const width =
        box.clientWidth -
        parseFloat(style.paddingLeft) -
        parseFloat(style.paddingRight);
      const height =
        box.clientHeight -
        parseFloat(style.paddingTop) -
        parseFloat(style.paddingBottom);
      let low = 1;
      let high = height * sizeRatio;
      // Measure the wrapped text, rather than guessing from character count.
      while (high - low > 0.25) {
        const size = (low + high) / 2;
        text.style.fontSize = `${size}px`;
        // Use layout dimensions so the overlay scale does not affect text fitting.
        if (
          text.scrollWidth <= Math.ceil(width) &&
          text.offsetHeight <= Math.ceil(height)
        ) {
          low = size;
        } else {
          high = size;
        }
      }
      text.style.fontSize = `${low}px`;
    };
    const observer = new ResizeObserver(fit);
    observer.observe(box);
    fit();
    document.fonts.ready.then(fit);
    document.fonts.addEventListener("loadingdone", fit);
    return () => {
      mounted = false;
      observer.disconnect();
      document.fonts.removeEventListener("loadingdone", fit);
    };
  }, [children, sizeRatio]);

  return (
    <div ref={boxRef} className={`${styles.fitBox} ${className}`}>
      <span ref={textRef} className={styles.text}>
        {children}
      </span>
    </div>
  );
}

function TeamLogo({ name }) {
  const placeholder = "/static/Teams/placeholder.png";
  return (
    <img
      key={name}
      src={name ? `/static/Teams/${encodeURIComponent(name)}.png` : placeholder}
      alt=""
      className={styles.logo}
      onError={({ currentTarget }) => {
        if (currentTarget.getAttribute("src") !== placeholder)
          currentTarget.src = placeholder;
      }}
    />
  );
}

export function ScoreIngame({ scene }) {
  const left = scene?.teams?.[0] || { name: "", score: 0 };
  const right = scene?.teams?.[1] || { name: "", score: 0 };

  return (
    <div
      className={styles.frame}
      data-scale-layout="internal"
      role="group"
      aria-label="Match score"
    >
      <div className={`${styles.panel} ${styles.leftPanel}`}>
        <img
          src="/static/Score Ingame.png"
          alt=""
          className={styles.background}
        />
        <div className={styles.content}>
          <div className={`${styles.team} ${styles.leftTeam}`}>
            <FittedText className={styles.leftName}>
              {left.name || "Team 1"}
            </FittedText>
            <TeamLogo name={left.name} />
          </div>
          <FittedText
            className={`${styles.score} ${styles.leftScore}`}
            sizeRatio={0.9}
          >
            {String(left.score ?? 0).padStart(2, "0")}
          </FittedText>
        </div>
      </div>
      <div className={`${styles.panel} ${styles.rightPanel}`}>
        <img
          src="/static/Score Ingame.png"
          alt=""
          className={styles.background}
        />
        <div className={styles.content}>
          <FittedText
            className={`${styles.score} ${styles.rightScore}`}
            sizeRatio={0.9}
          >
            {String(right.score ?? 0).padStart(2, "0")}
          </FittedText>
          <div className={`${styles.team} ${styles.rightTeam}`}>
            <TeamLogo name={right.name} />
            <FittedText className={styles.rightName}>
              {right.name || "Team 2"}
            </FittedText>
          </div>
        </div>
      </div>
    </div>
  );
}
