import styles from "./CharacterBansPregame.module.css";

export function CharacterBansPregame({ scene }) {
  const bans = scene?.hero_bans || [];
  const game = scene?.game || "";
  const fallbackImage = "/static/missing-char.png";

  const handleImageError = ({ currentTarget }) => {
    if (currentTarget.getAttribute("src") !== fallbackImage) {
      currentTarget.src = fallbackImage;
    } else {
      currentTarget.style.visibility = "hidden";
    }
  };

  return (
    <div className={styles.frame} role="group" aria-label="Character bans">
      <img src="/static/Bans.png" alt="" className={styles.background} />
      <div
        className={styles.bans}
        style={
          bans.length
            ? { gridTemplateColumns: `repeat(${bans.length}, minmax(0, 1fr))` }
            : undefined
        }
      >
        {bans.map((name, index) => (
          <div className={styles.ban} key={`${game}-${name}-${index}`}>
            <div className={styles.name}>
              <span
                style={{
                  fontSize: `min(45cqh, ${Math.min(12, 130 / Math.max(name.length, 1))}cqw)`,
                }}
              >
                {name}
              </span>
            </div>
            <div className={styles.portraitArea}>
              <img
                src={`/static/${encodeURIComponent(game)}/Chars/${encodeURIComponent(name)}.png`}
                alt=""
                className={styles.portrait}
                onError={handleImageError}
              />
            </div>
          </div>
        ))}
        {!bans.length && (
          <div className={styles.empty}>No characters banned</div>
        )}
      </div>
    </div>
  );
}
