import styles from "./CharacterBansIngame.module.css";

export function CharacterBansIngame({ scene }) {
  const bans = scene?.hero_bans || [];
  const game = scene?.game || "";
  const fallbackImage = "/static/missing-char.png";

  if (!bans.length) return null;

  const handleImageError = ({ currentTarget }) => {
    if (currentTarget.getAttribute("src") !== fallbackImage) {
      currentTarget.src = fallbackImage;
      currentTarget.classList.add(styles.fallback);
    } else {
      currentTarget.style.visibility = "hidden";
    }
  };

  const viewportWidth =
    bans.length * 4.13 + Math.max(bans.length - 1, 0) * 0.42;
  const maximumWidth = bans.length * 79 + Math.max(bans.length - 1, 0) * 8;

  return (
    <div
      className={styles.strip}
      role="group"
      aria-label="In-game character bans"
      style={{
        gridTemplateColumns: `repeat(${bans.length}, minmax(0, 1fr))`,
        width: `min(${viewportWidth}vw, ${maximumWidth}px, calc(100vw - 2 * var(--inset, 0px)))`,
      }}
    >
      {bans.map((name, index) => (
        <div className={styles.ban} key={`${game}-${name}-${index}`}>
          <img
            src={`/static/${encodeURIComponent(game)}/Chars/${encodeURIComponent(name)}.png`}
            alt={`${name} banned`}
            className={styles.portrait}
            onError={handleImageError}
          />
          <img
            src="/static/Character Ban ICON.png"
            alt=""
            className={styles.banOverlay}
          />
        </div>
      ))}
    </div>
  );
}
