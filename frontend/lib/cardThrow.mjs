// Cards played onto the draft board. Rest poses tilt a little but stay inside their slot, so
// a card never overlaps a neighbour, even one that has not been played yet. Lengths are in
// card widths; angles in degrees.

export function seededRandom(text) {
  let hash = 2166136261;
  for (const char of String(text)) hash = Math.imul(hash ^ char.codePointAt(0), 16777619);
  return () => {
    hash = (hash + 0x6d2b79f5) | 0;
    let value = Math.imul(hash ^ (hash >>> 15), 1 | hash);
    value = (value + Math.imul(value ^ (value >>> 7), 61 | value)) ^ value;
    return ((value ^ (value >>> 14)) >>> 0) / 4294967296;
  };
}

// Half the width and height of a card's bounding box when turned by `radians`.
function halfExtents(width, height, radians) {
  const cos = Math.cos(radians);
  const sin = Math.abs(Math.sin(radians));
  return [(width * cos + height * sin) / 2, (width * sin + height * cos) / 2];
}

// The largest tilt that keeps a width x height card inside its slot, the slot being the
// card plus half the gap on every side.
export function maxTilt(width, height, gapX, gapY) {
  let low = 0;
  let high = Math.PI / 4;
  for (let i = 0; i < 40; i++) {
    const middle = (low + high) / 2;
    const [x, y] = halfExtents(width, height, middle);
    if (x <= (width + gapX) / 2 && y <= (height + gapY) / 2) low = middle;
    else high = middle;
  }
  return low;
}

const TILT_SHARE = 0.85; // of the largest tilt that still fits the slot
const NUDGE_SHARE = 0.6; // of the room left beside a tilted card

// How far a card turned by `tilt` may be nudged and stay in its slot, each way.
function nudgeRoom(tilt, { width, height, gapX, gapY }) {
  const [x, y] = halfExtents(width, height, tilt);
  return [Math.max(0, (width + gapX) / 2 - x) * NUDGE_SHARE, Math.max(0, (height + gapY) / 2 - y) * NUDGE_SHARE];
}

// Where a card settles in its slot: a slight, seeded tilt and nudge that stay inside it.
export function restPose(seed, { width = 1, height, gapX, gapY }) {
  const random = seededRandom(`rest:${seed}`);
  const limit = maxTilt(width, height, gapX, gapY) * TILT_SHARE;
  // At least a third of the allowed tilt, so a card never looks machine-placed.
  const tilt = limit * (1 / 3 + (2 / 3) * random()) * (random() < 0.5 ? -1 : 1);
  const [roomX, roomY] = nudgeRoom(tilt, { width, height, gapX, gapY });
  return {
    x: (random() * 2 - 1) * roomX,
    y: (random() * 2 - 1) * roomY,
    angle: (tilt * 180) / Math.PI,
  };
}

// The scale of the slot's centred blank that any resting card covers completely, whatever
// tilt and nudge it landed with, so the blank can hide under it.
export function coverScale({ width = 1, height, gapX, gapY }) {
  const limit = maxTilt(width, height, gapX, gapY) * TILT_SHARE;
  const inside = (scale, tilt, dx, dy) => [[-1, -1], [1, -1], [1, 1], [-1, 1]].every(([sx, sy]) => {
    // The blank's corner in the card's own frame.
    const px = (sx * scale * width) / 2 - dx;
    const py = (sy * scale * height) / 2 - dy;
    const x = px * Math.cos(tilt) + py * Math.sin(tilt);
    const y = -px * Math.sin(tilt) + py * Math.cos(tilt);
    return Math.abs(x) <= width / 2 && Math.abs(y) <= height / 2;
  });
  let scale = 1;
  for (let i = 0; i <= 24; i++) {
    const tilt = (limit * i) / 24;
    const [roomX, roomY] = nudgeRoom(tilt, { width, height, gapX, gapY });
    for (const [dx, dy] of [[roomX, roomY], [roomX, -roomY], [-roomX, roomY], [-roomX, -roomY]]) {
      let low = 0;
      let high = scale;
      for (let step = 0; step < 30; step++) {
        const middle = (low + high) / 2;
        if (inside(middle, tilt, dx, dy)) low = middle;
        else high = middle;
      }
      scale = low;
    }
  }
  return scale;
}

// Motion, modelled on a dealer at a poker table. Positions are relative to the slot's centre.
//
// Pitch: a dealer's pitch keeps the card a fraction of an inch above the felt; it glides in a
// straight line to its spot with a little spin, touches down and skids to a stop. The skid's
// friction is solved so it stops exactly on its rest pose, and (as with any card sliding on
// cloth) the spin and the slide stop at the same moment. A small spring settles it.
// Take: collecting is a controlled push along the table, never a toss: the hand presses the
// card and drags it back, speeding up, lifting it only as it reaches the hand.

const FRAME = 1 / 60;
const RELEASE_HEIGHT = 0.08; // card widths: the pitch skims the felt
const IMPACT_KEEP = 0.75; // share of the speed a card keeps as it touches down
const SETTLE_TIME = 0.28; // s
const SETTLE_RATE = 2 * Math.PI * 5; // 5 wobbles a second
const SETTLE_DAMPING = 11;

function frames(path, aspect) {
  const duration = path[path.length - 1].t;
  const card = [];
  const shadow = [];
  for (const { t, x, y, z, angle } of path) {
    const offset = duration ? t / duration : 1;
    card.push({
      offset,
      transform: `translate(${(x * 100).toFixed(2)}%, ${((y / aspect) * 100).toFixed(2)}%) rotate(${angle.toFixed(2)}deg) scale(${(1 + z * 0.22).toFixed(4)})`,
    });
    // The shadow stays on the table, drifting from the card and fading as it rises.
    shadow.push({
      offset,
      transform: `translate(${((x + z * 0.35) * 100).toFixed(2)}%, ${(((y + z * 0.5) / aspect) * 100).toFixed(2)}%) rotate(${angle.toFixed(2)}deg)`,
      opacity: Math.min(1, Math.max(0.15, 1 - z * 0.4)),
    });
  }
  return { card, shadow, duration: Math.round(duration * 1000) };
}

function sample(duration, at) {
  const path = [];
  for (let t = 0; t < duration; t += FRAME) path.push({ t, ...at(t) });
  path.push({ t: duration, ...at(duration) });
  return path;
}

// A card pitched from the hand at `from` ({x, y}) that comes to rest on `rest`. `aspect` is
// height / width, for turning card widths into a percentage of the card's height.
export function throwKeyframes(seed, rest, { from, aspect = 1.36 }) {
  const random = seededRandom(`throw:${seed}`);
  const dx = rest.x - from.x;
  const dy = rest.y - from.y;
  const distance = Math.hypot(dx, dy) || 1e-6;
  const [ux, uy] = [dx / distance, dy / distance];

  // Glide most of the way, then skid the last stretch.
  const skid = Math.min(0.55, distance * 0.2) * (0.8 + random() * 0.4);
  const glide = distance - skid;
  const airTime = 0.16 + distance * 0.045;
  const airSpeed = glide / airTime;
  const landingSpeed = airSpeed * IMPACT_KEEP;
  const friction = (landingSpeed * landingSpeed) / (2 * skid);
  const skidTime = landingSpeed / friction;

  // A little spin: constant in the air, dying out with the skid.
  const turn = (15 + random() * 45) * (random() < 0.5 ? -1 : 1);
  const airSpin = turn / (airTime + (IMPACT_KEEP * skidTime) / 2);
  const startAngle = rest.angle - turn;

  const stop = airTime + skidTime;
  const wobble = Math.sign(turn) * (0.8 + random() * 0.6); // degrees, carrying on the spin
  const motion = frames(sample(stop + SETTLE_TIME, t => {
    if (t <= airTime) {
      return {
        x: from.x + ux * airSpeed * t,
        y: from.y + uy * airSpeed * t,
        z: RELEASE_HEIGHT * (1 - t / airTime) ** 2, // gliding down onto the felt
        angle: startAngle + airSpin * t,
      };
    }
    if (t <= stop) {
      const s = t - airTime;
      const travelled = glide + landingSpeed * s - (friction * s * s) / 2;
      const spun = airSpin * airTime + airSpin * IMPACT_KEEP * (s - (s * s) / (2 * skidTime));
      return { x: from.x + ux * travelled, y: from.y + uy * travelled, z: 0, angle: startAngle + spun };
    }
    // Settle: a small damped spring (a slight squash and wobble), ending exactly at rest.
    const u = t - stop;
    const spring = u >= SETTLE_TIME ? 0 : Math.exp(-SETTLE_DAMPING * u) * Math.sin(SETTLE_RATE * u);
    return { x: rest.x, y: rest.y, z: -0.08 * spring, angle: rest.angle + wobble * spring };
  }), aspect);
  return { ...motion, landed: Math.round(stop * 1000) };
}

// The hand drags the card from `rest` back to `to` ({x, y}).
export function takeKeyframes(seed, rest, { to, aspect = 1.36 }) {
  const random = seededRandom(`take:${seed}`);
  const distance = Math.hypot(to.x - rest.x, to.y - rest.y);
  const duration = 0.28 + distance * 0.07;
  const turn = (8 + random() * 20) * (random() < 0.5 ? -1 : 1);
  return frames(sample(duration, t => {
    const p = t / duration;
    const along = p * p * p; // pressed down, then pulled away faster and faster
    return {
      x: rest.x + (to.x - rest.x) * along,
      y: rest.y + (to.y - rest.y) * along,
      z: p > 0.75 ? ((p - 0.75) / 0.25) * 0.2 : 0,
      angle: rest.angle + turn * p * p,
    };
  }), aspect);
}

export function restTransform(rest, aspect = 1.36) {
  return `translate(${(rest.x * 100).toFixed(2)}%, ${((rest.y / aspect) * 100).toFixed(2)}%) rotate(${rest.angle.toFixed(2)}deg)`;
}
