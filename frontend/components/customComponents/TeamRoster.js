import styles from "./TeamRoster.module.css";

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

function PlayerList({ players, teamName }) {
  const visiblePlayers = players.slice(0, 6);

  return (
    <div
      className={styles.players}
      aria-label={`${teamName} players`}
      style={{ "--player-count": Math.max(visiblePlayers.length, 1) }}
    >
      {visiblePlayers.map((player, index) => (
        <div className={styles.player} key={`${player}-${index}`}>
          <span>{player}</span>
        </div>
      ))}
    </div>
  );
}

export function TeamRoster({ scene }) {
  const left = scene?.teams?.[0] || { name: "", players: [] };
  const right = scene?.teams?.[1] || { name: "", players: [] };
  const leftName = left.name || "Team 1";
  const rightName = right.name || "Team 2";

  return (
    <div className={styles.frame} role="group" aria-label="Team rosters">
      <img src="/static/bg-half.png" alt="" className={styles.background} />
      <div className={`${styles.heading} ${styles.leftHeading}`}>
        <div className={styles.teamName}>{leftName}</div>
        <TeamLogo name={left.name} />
      </div>
      <div className={`${styles.heading} ${styles.rightHeading}`}>
        <TeamLogo name={right.name} />
        <div className={styles.teamName}>{rightName}</div>
      </div>
      <div className={`${styles.roster} ${styles.leftRoster}`}>
        <PlayerList players={left.players || []} teamName={leftName} />
      </div>
      <div className={`${styles.roster} ${styles.rightRoster}`}>
        <PlayerList players={right.players || []} teamName={rightName} />
      </div>
    </div>
  );
}
