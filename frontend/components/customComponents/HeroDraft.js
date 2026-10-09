import styles from "./HeroDraft.module.css";

const fallbackImage = "/static/missing-char.png";
const placeholderLogo = "/static/Teams/placeholder.png";

function heroImage(game, hero) {
    return `/static/${encodeURIComponent(game)}/Chars/${encodeURIComponent(hero)}.png`;
}

function handleImageError({ currentTarget }) {
    if (currentTarget.getAttribute("src") !== fallbackImage) {
        currentTarget.src = fallbackImage;
    } else {
        currentTarget.style.visibility = "hidden";
    }
}

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

function Ban({ game, hero, index }) {
    return (
        <div className={`${styles.ban} ${hero ? "" : styles.emptyBan}`}>
            {hero
                ? <img src={heroImage(game, hero)} alt={`${hero} banned`} onError={handleImageError} />
                : <span aria-label={`Ban ${index + 1} open`}>{index + 1}</span>}
        </div>
    );
}

function Pick({ game, hero, player }) {
    return (
        <div className={`${styles.pick} ${hero ? "" : styles.emptyPick}`}>
            {hero
                ? <img src={heroImage(game, hero)} alt="" className={styles.portrait} onError={handleImageError} />
                : <span className={styles.pending} aria-hidden="true">?</span>}
            <div className={styles.plate}>
                <span className={styles.heroName}>{hero || "Picking"}</span>
                <span className={styles.playerName}>{player || " "}</span>
            </div>
        </div>
    );
}

function TeamPanel({ team, side, game, firstPick }) {
    const name = team.name || (side === "left" ? "Team 1" : "Team 2");
    const players = team.players || [];
    return (
        <section className={`${styles.team} ${styles[side]}`} aria-label={`${name} draft`}>
            <header className={styles.teamHeader}>
                <TeamLogo name={team.name} />
                <div className={styles.teamTitle}>
                    {/* Shrink long names so they fit beside the bans instead of truncating. */}
                    <span className={styles.teamName} style={{ fontSize: `${Math.min(2.9, 26 / Math.max(name.length, 1))}cqw` }}>
                        {name}
                    </span>
                    {firstPick && <span className={styles.firstPick}>1st pick</span>}
                </div>
                <div className={styles.bans} aria-label={`${name} bans`}>
                    <span className={styles.bansLabel}>Bans</span>
                    {(team.bans || []).map((hero, index) => (
                        <Ban game={game} hero={hero} index={index} key={`${index}-${hero}`} />
                    ))}
                </div>
            </header>
            <div className={styles.picks}>
                {(team.picks || []).map((hero, index) => (
                    <Pick game={game} hero={hero} player={players[index]} key={`${index}-${hero}`} />
                ))}
            </div>
        </section>
    );
}

export function HeroDraft({ scene }) {
    const game = scene?.game || "";
    const teams = scene?.teams || [];
    const left = teams[0] || { name: "", score: 0, players: [], picks: [], bans: [] };
    const right = teams[1] || { name: "", score: 0, players: [], picks: [], bans: [] };
    // Grey until GryphDeck knows which in-game side each team is on.
    const unknown = scene?.sides_known === false;

    return (
        <div className={`${styles.frame} ${unknown ? styles.unknown : ""}`} role="group" aria-label="Picks and bans">
            <img src="/static/bg-blank.png" alt="" className={styles.background} />
            <div className={styles.layout}>
                <TeamPanel team={left} side="left" game={game} firstPick={scene?.first_pick === 1} />
                <div className={styles.center}>
                    {scene?.label && <p className={styles.label}>{scene.label}</p>}
                    <h1 className={styles.title}>
                        <span>Picks</span>
                        <span className={styles.amp}>&amp;</span>
                        <span>Bans</span>
                    </h1>
                    <div className={styles.score} aria-label={`Series score ${left.score ?? 0} to ${right.score ?? 0}`}>
                        <span className={styles.leftScore}>{left.score ?? 0}</span>
                        <span className={styles.versus}>vs</span>
                        <span className={styles.rightScore}>{right.score ?? 0}</span>
                    </div>
                    <div className={styles.brand}>
                        <img src="/static/Sponsors/GryphonGaming.png" alt="Gryphon Gaming" />
                        <span>Deadlock Hero Picks</span>
                    </div>
                </div>
                <TeamPanel team={right} side="right" game={game} firstPick={scene?.first_pick === 2} />
            </div>
        </div>
    );
}
