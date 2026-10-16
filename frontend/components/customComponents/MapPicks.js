import styles from "./MapPicks.module.css";

export function MapPicks({ scene }) {
  const maps = scene?.map_picks || [];
  const game = scene?.game || "";
  const fallbackImage = "/static/bg-blank.png";
  const handleImageError = ({ currentTarget }) => {
    if (currentTarget.getAttribute("src") !== fallbackImage) {
      currentTarget.src = fallbackImage;
    } else {
      // Avoid repeated requests if the fallback is also unavailable.
      currentTarget.style.visibility = "hidden";
    }
  };

  return (
    <div className={styles.frame} role="group" aria-label="Map picks">
      <img src="/static/Maps.png" alt="" className={styles.background} />
      <div
        className={styles.picks}
        style={{
          gridTemplateColumns: `repeat(${Math.max(maps.length, 1)}, minmax(0, 1fr))`,
        }}
      >
        {maps.map((name, index) => (
          <div
            className={styles.pick}
            key={`${game}-${name}-${index}`}
            data-map={name}
          >
            <div className={styles.name}>
              <span
                style={{
                  fontSize: `min(45cqh, ${Math.min(12, 130 / Math.max(name.length, 1))}cqw)`,
                }}
              >
                {name}
              </span>
            </div>
            <div className={styles.imageArea}>
              <img
                src={`/static/${encodeURIComponent(game)}/Maps/${encodeURIComponent(name)}.png`}
                alt=""
                className={styles.mapImage}
                onError={handleImageError}
              />
            </div>
          </div>
        ))}
        {!maps.length && <div className={styles.empty}>No maps selected</div>}
      </div>
    </div>
  );
}
