import styles from "./DeadlockTopBar.module.css";

const placeholderLogo = "/static/Teams/placeholder.png";

function TeamLogo({ name }) {
    return (
        <img
            key={name}
            src={name ? `/static/Teams/${encodeURIComponent(name)}.png` : placeholderLogo}
            alt=""
            className={styles.logo}
            onError={({ currentTarget }) => {
                if (currentTarget.getAttribute("src") !== placeholderLogo) currentTarget.src = placeholderLogo;
            }}
        />
    );
}

// Player names sit directly above Deadlock's hero portraits, so enter each roster in the
// in-game slot order. Each team block matches the game's own top bar team (see the CSS).
function Team({ team, side }) {
    const name = team.name || (side === "left" ? "Team 1" : "Team 2");
    const players = (team.players || []).slice(0, 6);
    return (
        <section className={`${styles.team} ${styles[side]}`} aria-label={name}>
            <div className={styles.teamRow}>
                <TeamLogo name={team.name} />
                <span className={styles.teamName} style={{ fontSize: `calc(${Math.min(28, 400 / Math.max(name.length, 1))} * var(--u))` }}>
                    {name}
                </span>
            </div>
            <ol className={styles.players} aria-label={`${name} players`}>
                {players.map((player, index) => (
                    <li key={`${index}-${player}`} style={{ "--slot": index }}>
                        {/* Shrink long names to fit the portrait column before truncating. */}
                        <span style={{ fontSize: `calc(${Math.min(13, 125 / Math.max(player.length, 1))} * var(--u))` }}>{player}</span>
                    </li>
                ))}
            </ol>
        </section>
    );
}

export function DeadlockTopBar({ scene }) {
    const teams = scene?.teams || [];
    const left = teams[0] || { name: "", score: 0, players: [] };
    const right = teams[1] || { name: "", score: 0, players: [] };
    // Grey until GryphDeck knows which in-game side each team is on.
    const unknown = scene?.sides_known === false;

    return (
        <div className={`${styles.frame} ${unknown ? styles.unknown : ""}`} role="banner" aria-label="Match bar">
            <div className={styles.band}>
                <div className={styles.brand}>
                    <img src="/static/Sponsors/GryphonGaming.png" alt="Gryphon Gaming" />
                    <div>
                        <span className={styles.brandName}>Gryphon Gaming</span>
                        <span className={styles.brandGame}>Deadlock</span>
                    </div>
                </div>
                <Team team={left} side="left" />
                <div className={styles.score} aria-label={`Series score ${left.score ?? 0} to ${right.score ?? 0}`}>
                    <span className={`${styles.scoreChip} ${styles.leftScore}`}>{left.score ?? 0}</span>
                    <span className={styles.divider} aria-hidden="true" />
                    <span className={`${styles.scoreChip} ${styles.rightScore}`}>{right.score ?? 0}</span>
                </div>
                <Team team={right} side="right" />
                <div className={styles.matchInfo}>
                    {scene?.label
                        ? <span>{scene.label}</span>
                        : <span className={styles.live}>Live</span>}
                </div>
            </div>
        </div>
    );
}
