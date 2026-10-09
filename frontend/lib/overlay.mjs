export const SCENES = ["idle", "pregame", "ingame"];
export const LOCATIONS = [
  "TopLeft", "TopCenter", "TopRight", "CenterLeft", "Center", "CenterRight",
  "BottomLeft", "BottomCenter", "BottomRight",
];

const object = value => value !== null && typeof value === "object" && !Array.isArray(value);
const strings = value => Array.isArray(value) && value.every(item => typeof item === "string");

export function validOverlay(document) {
  return object(document) && typeof document.game === "string" && object(document.scenes)
    && SCENES.every(scene => Array.isArray(document.scenes[scene]) && document.scenes[scene].every(component => {
      if (!object(component) || typeof component.name !== "string" || !component.name
          || !LOCATIONS.includes(component.location) || !object(component.data)) return false;
      if ("scale" in component && (!Number.isFinite(component.scale) || component.scale < 0)) return false;
      const data = component.data;
      if (typeof data.game !== "string" || data.scene !== scene) return false;
      if ("map_picks" in data && !strings(data.map_picks)) return false;
      if ("hero_bans" in data && !strings(data.hero_bans)) return false;
      if ("teams" in data && (!Array.isArray(data.teams) || data.teams.length !== 2
          || !data.teams.every(team => object(team) && typeof team.name === "string"
            && (!("score" in team) || (Number.isInteger(team.score) && team.score >= 0))
            && (!("players" in team) || strings(team.players))))) return false;
      return true;
    }));
}

// One store per local Next.js process. GET reconciles missed pushes with Flask.
export function createOverlayStore() {
  let document = null;
  let revision = 0;
  let lastSync = 0;
  let pending = null;
  return {
    publish(next) {
      if (!validOverlay(next)) throw new Error("Invalid scene document.");
      document = structuredClone(next);
      revision += 1;
      lastSync = Date.now();
    },
    async read(load, now = Date.now()) {
      if (document && now - lastSync < 2000) return document;
      if (!pending) {
        const startedAt = revision;
        pending = (async () => {
          try {
            const next = await load();
            if (!validOverlay(next)) throw new Error("Invalid scene document from Flask.");
            // A POST received during this fetch is newer than its snapshot.
            if (revision === startedAt) document = next;
          } catch (error) {
            if (!document) throw error;
          } finally {
            lastSync = Date.now();
          }
          return document;
        })().finally(() => { pending = null; });
      }
      return pending;
    },
  };
}
