import assert from "node:assert/strict";
import test from "node:test";
import { coverScale, maxTilt, restPose, takeKeyframes, throwKeyframes } from "./cardThrow.mjs";

// The draft board's pick card: 280 x 380 art, 1.2cqw gaps on a 12cqw card.
const PICK = { width: 1, height: 380 / 280, gapX: 0.1, gapY: 0.1 };

function corners(pose, { width, height }) {
  const radians = (pose.angle * Math.PI) / 180;
  return [[-1, -1], [1, -1], [1, 1], [-1, 1]].map(([sx, sy]) => {
    const x = (sx * width) / 2;
    const y = (sy * height) / 2;
    return [pose.x + x * Math.cos(radians) - y * Math.sin(radians), pose.y + x * Math.sin(radians) + y * Math.cos(radians)];
  });
}

test("rest poses tilt but never leave their slot", () => {
  const limit = (maxTilt(PICK.width, PICK.height, PICK.gapX, PICK.gapY) * 180) / Math.PI;
  assert.ok(limit > 2 && limit < 10, `tilt limit ${limit}`);
  for (let i = 0; i < 2000; i++) {
    const pose = restPose(`hero-${i}`, PICK);
    assert.ok(Math.abs(pose.angle) > 0.5, "every card leans a little");
    for (const [x, y] of corners(pose, PICK)) {
      assert.ok(Math.abs(x) <= (PICK.width + PICK.gapX) / 2 + 1e-9, `x ${x} for hero-${i}`);
      assert.ok(Math.abs(y) <= (PICK.height + PICK.gapY) / 2 + 1e-9, `y ${y} for hero-${i}`);
    }
  }
});

test("every resting card covers its slot's blank", () => {
  for (const geometry of [PICK, { width: 1, height: 380 / 280, gapX: 0.18, gapY: 0.18 }]) {
    const scale = coverScale(geometry);
    assert.ok(scale > 0.75 && scale < 1, `scale ${scale}`);
    const blank = corners({ x: 0, y: 0, angle: 0 }, { width: scale, height: scale * geometry.height });
    for (let i = 0; i < 2000; i++) {
      const pose = restPose(`hero-${i}`, geometry);
      const radians = (pose.angle * Math.PI) / 180;
      for (const [cx, cy] of blank) {
        const px = cx - pose.x;
        const py = cy - pose.y;
        const x = px * Math.cos(radians) + py * Math.sin(radians);
        const y = -px * Math.sin(radians) + py * Math.cos(radians);
        assert.ok(Math.abs(x) <= 0.5 + 1e-9 && Math.abs(y) <= geometry.height / 2 + 1e-9, `hero-${i} uncovers the blank`);
      }
    }
  }
});

// The transform a pose ends on, as the keyframes write it.
function pose({ x, y, angle }, scale = "1.0000") {
  return `translate(${(x * 100).toFixed(2)}%, ${((y / PICK.height) * 100).toFixed(2)}%) rotate(${angle.toFixed(2)}deg) scale(${scale})`;
}

function at({ x, y }) {
  return `translate(${(x * 100).toFixed(2)}%, ${((y / PICK.height) * 100).toFixed(2)}%) `;
}

// A hand below the board, for a top-row and a bottom-row slot.
const HANDS = [{ x: 1.1, y: 4.2 }, { x: -1.1, y: 1.6 }];

test("a pitched card leaves the hand and lands exactly on its rest pose", () => {
  const rest = restPose("Haze", PICK);
  for (const from of HANDS) {
    const { card, shadow, duration } = throwKeyframes("Haze", rest, { from, aspect: PICK.height });
    assert.ok(duration > 250 && duration < 1200, `duration ${duration}`);
    assert.ok(card[0].transform.startsWith(at(from)));
    assert.equal(card.at(-1).offset, 1);
    assert.equal(card.at(-1).transform, pose(rest));
    assert.equal(shadow.length, card.length);
    assert.ok(card.every((frame, index) => index === 0 || frame.offset >= card[index - 1].offset));
  }
});

test("a taken card goes from its rest pose to the hand", () => {
  const rest = restPose("Ivy", PICK);
  const to = HANDS[0];
  const { card } = takeKeyframes("Ivy", rest, { to, aspect: PICK.height });
  assert.equal(card[0].transform, pose(rest));
  assert.ok(card.at(-1).transform.startsWith(at(to)));
});

test("the same card is always played the same way", () => {
  const rest = restPose("Kelvin", PICK);
  const from = HANDS[0];
  assert.deepEqual(throwKeyframes("Kelvin", rest, { from }), throwKeyframes("Kelvin", rest, { from }));
  assert.notDeepEqual(throwKeyframes("Kelvin", rest, { from }).card, throwKeyframes("Ivy", rest, { from }).card);
});
