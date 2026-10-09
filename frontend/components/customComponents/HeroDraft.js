import { useEffect, useLayoutEffect, useRef, useState } from "react";
import { coverScale, restPose, restTransform, takeKeyframes, throwKeyframes } from "@/lib/cardThrow.mjs";
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

// A slot's size, in card widths, with the gap around it.
function slotGeometry(slot) {
    const box = slot.getBoundingClientRect();
    const gap = (parseFloat(getComputedStyle(slot.parentElement).columnGap) || 0) / box.width;
    return { box, geometry: { width: 1, height: box.height / box.width, gapX: gap, gapY: gap } };
}

// Where the card rests in its slot, and where its team's hand is from there: just below the
// board, under the middle of the team's picks.
function measure(slot, seed) {
    const { box, geometry } = slotGeometry(slot);
    const picks = slot.closest("section").querySelector("[data-hand]").getBoundingClientRect();
    const board = slot.closest("[data-board]").getBoundingClientRect();
    const hand = {
        x: (picks.left + picks.width / 2 - (box.left + box.width / 2)) / box.width,
        y: (board.bottom + box.height * 0.55 - (box.top + box.height / 2)) / box.width,
    };
    return { box, height: geometry.height, rest: restPose(seed, geometry), hand };
}


function cardSeed(kind, slot, hero) {
    return `${kind}:${slot}:${hero}`;
}

// The card on a slot, keyed by hero: a different hero is a different card. It is thrown from
// the team's hand: in turn when the board first shows (dealing), at once after that. Whether
// it is being dealt is decided once, as React's dev mode mounts twice.
function Card({ game, hero, player, kind, slot, rank, order, board }) {
    const cardRef = useRef(null);
    const shadowRef = useRef(null);
    const stampRef = useRef(null);
    const entrance = useRef(null);

    useLayoutEffect(() => {
        const element = cardRef.current.parentElement;
        const seed = cardSeed(kind, slot, hero);
        const { height, rest, hand } = measure(element, seed);
        const card = cardRef.current;
        const shadow = shadowRef.current;
        card.style.transform = shadow.style.transform = restTransform(rest, height);

        entrance.current ??= { dealing: !board.current.ready };
        // Dealing the board: each card waits its turn, hidden until thrown.
        const delay = entrance.current.dealing ? order * 110 : 0;
        const motion = throwKeyframes(seed, rest, { from: hand, aspect: height });
        const duration = delay + motion.duration;
        const animations = [
            card.animate(motion.card, { duration: motion.duration, delay, fill: "backwards" }),
            shadow.animate(motion.shadow, { duration: motion.duration, delay, fill: "backwards" }),
        ];
        if (stampRef.current) {
            animations.push(stampRef.current.animate(
                [{ opacity: 0, transform: "rotate(-14deg) scale(1.8)" }, { opacity: 1, transform: "rotate(-14deg) scale(1)" }],
                { duration: 160, delay: delay + motion.landed, easing: "cubic-bezier(.3, 0, .6, 1)", fill: "backwards" },
            ));
        }
        // The slot's blank shows until the card has landed on it.
        element.classList.remove(styles.covered);
        element.classList.add(styles.moving);
        const settle = setTimeout(() => {
            element.classList.remove(styles.moving);
            element.classList.add(styles.covered);
        }, duration);
        return () => {
            clearTimeout(settle);
            element.classList.remove(styles.covered);
            animations.forEach(animation => animation.cancel());
        };
        // A card keeps its hero, kind, and slot for life; the player name updates in place.
        // eslint-disable-next-line react-hooks/exhaustive-deps
    }, []);

    return (
        <>
            <div ref={shadowRef} className={styles.shadow} data-part="shadow" />
            <div ref={cardRef} className={`${styles.card} ${kind === "bans" ? styles.banned : ""}`} data-part="card">
                <div className={styles.picture}>
                    <img src={heroImage(game, hero)} alt="" className={styles.art} onError={handleImageError} />
                    <div className={styles.plate}>
                        <span className={styles.heroName}>{hero}</span>
                        {player && (
                            <span className={styles.playerName} style={{ fontSize: `${Math.min(1.45, 11 / player.length)}cqw` }}>
                                {player}
                            </span>
                        )}
                    </div>
                </div>
                {/* Poker-style corner indices: the card's rank, and the team's side as the suit. */}
                {[styles.corner, `${styles.corner} ${styles.flipped}`].map(className => (
                    <span className={className} key={className} aria-hidden="true">
                        <span className={styles.rank}>{rank}</span>
                        <span className={styles.suit} />
                    </span>
                ))}
                {kind === "bans" && <span ref={stampRef} className={styles.stamp}>Banned</span>}
            </div>
        </>
    );
}

// One slot, holding at most one card. When its hero changes or is cleared, the team's hand
// drags the card back, then the new card is thrown. The slot's blank is sized so any resting
// card covers it, and hides only under one.
function Slot({ game, hero, player, kind, slot, rank, order, board, label }) {
    const slotRef = useRef(null);
    const [shown, setShown] = useState(hero);
    const latest = useRef(hero);
    useLayoutEffect(() => { latest.current = hero; });

    if (hero !== shown && !shown) setShown(hero);
    const leaving = Boolean(shown) && hero !== shown;
    // A card being taken away keeps its rank until it is gone.
    const [shownRank, setShownRank] = useState(rank);
    if (hero === shown && rank !== shownRank) setShownRank(rank);

    useLayoutEffect(() => {
        slotRef.current.style.setProperty("--cover", coverScale(slotGeometry(slotRef.current).geometry));
    }, []);

    useLayoutEffect(() => {
        if (!leaving) return undefined;
        const element = slotRef.current;
        const seed = cardSeed(kind, slot, shown);
        const { height, rest, hand } = measure(element, seed);
        const motion = takeKeyframes(seed, rest, { to: hand, aspect: height });
        const options = { duration: motion.duration, fill: "forwards" };
        const animations = [
            element.querySelector("[data-part=card]").animate(motion.card, options),
            element.querySelector("[data-part=shadow]").animate(motion.shadow, options),
        ];
        element.classList.remove(styles.covered);
        element.classList.add(styles.moving);
        animations[0].finished.then(() => {
            element.classList.remove(styles.moving);
            setShown(latest.current);
        }, () => {});
        return () => animations.forEach(animation => animation.cancel());
    }, [leaving, shown, kind, slot]);

    return (
        <div ref={slotRef} className={styles.slot}>
            <div className={styles.blank}>
                <span className={styles.slotLabel}>{label}</span>
                {player && <span className={styles.slotPlayer}>{player}</span>}
            </div>
            {shown && <Card key={shown} game={game} hero={shown} player={player} kind={kind} slot={slot} rank={shownRank}
                order={order} board={board} />}
        </div>
    );
}

function TeamPanel({ team, side, game, firstPick, board }) {
    const name = team.name || (side === "left" ? "Team 1" : "Team 2");
    const players = team.players || [];
    const seat = side === "left" ? 0 : 1;
    // Ranks: picks count 1-6 in order among the played picks (clearing one renumbers the
    // rest in place); bans are Kings.
    const ranks = { picks: [], bans: [] };
    let played = 0;
    for (const hero of team.picks || []) ranks.picks.push(hero ? String(++played) : "");
    for (const hero of team.bans || []) ranks.bans.push(hero ? "K" : "");
    // Dealt like a heads-up hand: alternating seats, picks first, then bans.
    const slots = (kind, heroes, label, player) => heroes.map((hero, index) => (
        <Slot key={index} game={game} hero={hero} player={player(index)} kind={kind} slot={index} side={side}
            rank={ranks[kind][index]}
            order={(kind === "bans" ? (team.picks || []).length : 0) * 2 + index * 2 + seat}
            board={board} label={label(index)} />
    ));

    return (
        <section className={`${styles.team} ${styles[side]}`} aria-label={`${name} draft`}>
            <header className={styles.teamHeader}>
                <TeamLogo name={team.name} />
                {/* Shrink long names so they fit instead of truncating. */}
                <span className={styles.teamName} style={{ fontSize: `${Math.min(2.9, 34 / Math.max(name.length, 1))}cqw` }}>
                    {name}
                </span>
                {firstPick && <span className={styles.firstPick}>1st pick</span>}
            </header>
            <div className={styles.picks} aria-label={`${name} picks`} data-hand>
                {slots("picks", team.picks || [], () => "?", index => (team.pick_players || players)[index])}
            </div>
            <div className={styles.bansRow}>
                <span className={styles.bansLabel}>Bans</span>
                <div className={styles.bans} aria-label={`${name} bans`}>
                    {slots("bans", team.bans || [], index => index + 1, () => null)}
                </div>
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
    // Cards on the board when it first shows are dealt; after that only new ones are thrown.
    const board = useRef({ ready: false });
    useEffect(() => { board.current.ready = true; }, []);
    return (
        <div className={`${styles.frame} ${unknown ? styles.unknown : ""}`} role="group" aria-label="Picks and bans" data-board>
            <img src="/static/bg-blank.png" alt="" className={styles.background} />
            <div className={styles.layout}>
                <TeamPanel team={left} side="left" game={game} firstPick={scene?.first_pick === 1}
                    board={board} />
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
                <TeamPanel team={right} side="right" game={game} firstPick={scene?.first_pick === 2}
                    board={board} />
            </div>
        </div>
    );
}
