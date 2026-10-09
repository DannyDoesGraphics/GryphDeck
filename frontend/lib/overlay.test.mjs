import assert from "node:assert/strict";
import test from "node:test";
import { createOverlayStore, validOverlay } from "./overlay.mjs";

function document(score = 1) {
  return { game: "Valorant", scenes: { idle: [], pregame: [], ingame: [{
    name: "Score Ingame", location: "BottomCenter", data: {
      game: "Valorant", scene: "ingame", teams: [{ name: "Gryphons", score }, { name: "Rivals", score: 0 }],
    },
  }] } };
}

test("accepts scene documents and rejects data that cannot be rendered", () => {
  assert.equal(validOverlay(document()), true);
  for (const invalid of [null, [], {}, { game: "Game", scenes: { idle: [] } }]) {
    assert.equal(validOverlay(invalid), false);
  }
  for (const change of [
    c => { c.location = "Unknown"; },
    c => { c.data = null; },
    c => { c.data.scene = "idle"; },
    c => { c.data.teams[0].score = "2"; },
    c => { c.data.teams[0].players = [{}]; },
    c => { c.data.map_picks = [null]; },
    c => { c.data.hero_bans = "Ana"; },
  ]) {
    const value = document();
    change(value.scenes.ingame[0]);
    assert.equal(validOverlay(value), false);
  }
});

test("accepts optional nonnegative numeric scales and preserves them in the store", async () => {
  assert.equal(validOverlay(document()), true);
  for (const scale of [0, 0.5, 1, 1.5, 2]) {
    const value = document();
    value.scenes.ingame[0].scale = scale;
    assert.equal(validOverlay(value), true);
    const store = createOverlayStore();
    store.publish(value);
    assert.deepEqual(await store.read(() => assert.fail("Fresh state should be cached")), value);
  }
  for (const scale of [-1, "0.5", null, true, NaN, Infinity, {}, []]) {
    const value = document();
    value.scenes.ingame[0].scale = scale;
    assert.equal(validOverlay(value), false);
  }
});

test("retains posted state while offline and reconciles a missed POST", async () => {
  const store = createOverlayStore();
  store.publish(document(2));
  const offline = await store.read(async () => { throw Error("offline"); }, Date.now() + 5000);
  assert.deepEqual(offline, document(2));
  const recovered = await store.read(async () => document(9), Date.now() + 5000);
  assert.deepEqual(recovered, document(9));
  assert.throws(() => store.publish({}), /Invalid/);
  assert.deepEqual(await store.read(() => assert.fail("Fresh state should be cached")), document(9));
});

test("a newer POST wins over an in-flight recovery snapshot", async () => {
  const store = createOverlayStore();
  let finish;
  const pending = store.read(() => new Promise(resolve => { finish = resolve; }));
  store.publish(document(5));
  finish(document(1));
  assert.deepEqual(await pending, document(5));
});

test("starts from Flask state and retries after an unavailable startup", async () => {
  const store = createOverlayStore();
  await assert.rejects(store.read(async () => { throw Error("offline"); }), /offline/);
  assert.deepEqual(await store.read(async () => document(3)), document(3));
});
