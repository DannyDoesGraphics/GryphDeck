"use strict";

const workspace = document.querySelector("#workspace");
const notice = document.querySelector("#notice");
let state;
let requestQueue = Promise.resolve();
let swapping = false;
const teamSavers = [];

function element(tag, className, text) {
  const node = document.createElement(tag);
  node.className = className;
  if (text !== undefined) node.textContent = text;
  return node;
}

function render({ teams = false, game = false } = {}) {
  if (game) {
    const select = document.querySelector("#game");
    select.replaceChildren(...state.games.map(name => new Option(name, name)));
    select.value = state.game_key;
    const source = document.querySelector("#team-source");
    source.replaceChildren(...state.team_sources.map(name => new Option(name, name)));
    source.value = state.team_source.name;
  }
  const sourceError = document.querySelector(".team-source-error");
  sourceError.hidden = !state.team_source.error;
  sourceError.textContent = state.team_source.error || "";
  document.querySelectorAll("[data-scene-panel]").forEach(panel => {
    const scene = panel.dataset.scenePanel;
    const components = state.components[scene];
    panel.querySelector(".enabled-count").textContent = `${components.filter(item => item.enabled).length} enabled`;
    const list = panel.querySelector(".components");
    list.replaceChildren(...components.map(component => {
      const button = element("button", "component");
      button.type = "button";
      button.dataset.component = component.name;
      button.setAttribute("aria-pressed", String(component.enabled));
      const name = element("span", "component-name", component.name);
      name.append(element("small", "", component.position.replace(/([a-z])([A-Z])/g, "$1 $2")));
      const toggle = element("span", "toggle");
      toggle.setAttribute("aria-hidden", "true");
      button.append(name, element("span", "component-state", component.enabled ? "ON" : "OFF"), toggle);
      button.addEventListener("click", async () => {
        await send({ action: "toggle_component", scene, component: component.name }, "Component state updated.");
        [...list.children].find(item => item.dataset.component === component.name)?.focus();
      });
      return button;
    }));
    if (!components.length) list.append(element("p", "muted", "No components are configured for this scene."));
  });

  state.teams.forEach((team, index) => {
    const side = index === 0 ? "left" : "right";
    document.querySelector(`#summary-${side}`).textContent = team.Name || `Team ${index + 1}`;
    document.querySelector(`#score-${side}`).textContent = team.Score;
    const card = document.querySelector(`[data-team="${index + 1}"]`);
    if (teams) {
      card.querySelector('[name="name"]').value = team.Name;
      card.querySelector('[name="score"]').value = team.Score;
    }
    const manual = state.team_source.name === "Manual";
    card.querySelector('[name="name"]').disabled = !manual;
    card.querySelector(".player-form").hidden = !manual;
    const sourceTeamForm = card.querySelector(".source-team-form");
    sourceTeamForm.hidden = !state.team_source.teams.length;

    const players = state.rosters[index];
    card.querySelector(".player-count").textContent = `${team.Players.length}/${state.max_players} active, ${players.length} on roster`;

    const roster = card.querySelector(".players");
    roster.replaceChildren(...players.map(({ name: player }, playerIndex) => {
      const active = team.Players.includes(player);
      const row = element("li", "player");
      row.classList.toggle("benched", !active);
      const toggle = element("button", "player-active", active ? "Active" : "Benched");
      toggle.type = "button";
      toggle.setAttribute("aria-pressed", String(active));
      toggle.disabled = !active && team.Players.length >= state.max_players;
      toggle.setAttribute("aria-label", `${player} is ${active ? "active" : "benched"} on team ${index + 1}`);
      toggle.addEventListener("click", async () => {
        await send({ action: "set_player_active", team: index + 1, player, active: !active }, `${player} ${active ? "benched" : "activated"}.`);
        [...roster.querySelectorAll(".player-active")][playerIndex]?.focus();
      });
      const remove = element("button", "remove-player", "Remove");
      remove.type = "button";
      remove.setAttribute("aria-label", `Remove ${player} from team ${index + 1}`);
      remove.addEventListener("click", async () => {
        await send({ action: "remove_player", team: index + 1, player }, "Player removed.");
        card.querySelector('[name="player"]').focus();
      });
      remove.hidden = !manual;
      row.append(element("span", "player-index", String(playerIndex + 1).padStart(2, "0")), element("span", "player-name", player), toggle, remove);
      return row;
    }));
    if (!players.length) roster.append(element("li", "empty-roster", "No players added."));
  });
  renderBans({ game });
}

function renderBans({ game }) {
  document.querySelectorAll("[data-ban-kind]").forEach(section => {
    const kind = section.dataset.banKind;
    const selection = kind === "map" ? "pick" : "ban";
    const options = state.ban_options[kind];
    const selected = state.bans[kind];
    const input = section.querySelector('[name="ban"]');
    section.hidden = !options.supported;
    input.disabled = !options.supported || !options.choices.length;
    section.querySelector('[type="submit"]').disabled = input.disabled;
    if (game) {
      input.value = "";
      const feedback = section.querySelector(".ban-feedback");
      feedback.classList.remove("error");
      feedback.textContent = options.choices.length ? `Type to search the game's ${kind === "map" ? "maps" : "heroes"}.` : `No ${kind === "map" ? "maps" : "heroes"} configured for this game.`;
    }
    section.querySelector(".ban-count").textContent = `${selected.length} ${selection}${selected.length === 1 ? "" : "s"}`;
    const list = section.querySelector(".ban-list");
    list.replaceChildren(...selected.map((name, index) => {
      const row = element("li", "player");
      const remove = element("button", "remove-player", "Remove");
      remove.type = "button";
      remove.setAttribute("aria-label", `Remove ${name} ${kind} ${selection}`);
      remove.addEventListener("click", async () => {
        await saveBan(section, "remove_ban", name);
        input.focus();
      });
      row.append(element("span", "player-index", String(index + 1).padStart(2, "0")), element("span", "player-name", name), remove);
      return row;
    }));
    if (!selected.length) list.append(element("li", "empty-roster", `No ${kind} ${selection}s added.`));
  });
}

async function saveBan(section, action, name) {
  const kind = section.dataset.banKind;
  const message = `${kind === "map" ? "Map pick" : "Hero ban"} ${action === "add_ban" ? "added" : "removed"}.`;
  const success = await send({ action, kind, name }, message);
  const feedback = section.querySelector(".ban-feedback");
  feedback.textContent = success ? message : notice.textContent;
  feedback.classList.toggle("error", !success);
  return success;
}

function send(payload, message, options = {}) {
  const request = requestQueue.then(() => performRequest(payload, message, options));
  requestQueue = request.catch(() => false);
  return request;
}

async function performRequest(payload, message, options) {
  if (!options.background) workspace.disabled = true;
  workspace.setAttribute("aria-busy", "true");
  try {
    const response = await fetch("/api/control", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(payload),
    });
    const data = await response.json();
    if (!response.ok) throw new Error(data.error || "The change could not be saved.");
    state = data;
    render(options);
    notice.className = "";
    notice.textContent = message;
    return true;
  } catch (error) {
    notice.className = "error";
    notice.textContent = error.message || "Unable to reach the server. Try again.";
    return false;
  } finally {
    if (!options.background) workspace.disabled = swapping;
    workspace.setAttribute("aria-busy", "false");
  }
}

document.querySelector("#game-form").addEventListener("submit", event => {
  event.preventDefault();
  send({ action: "load_game", game: document.querySelector("#game").value }, "Game loaded. Components, map picks, and hero bans reset; teams retained.", { game: true });
});

document.querySelector("#team-source").addEventListener("change", async event => {
  const select = event.currentTarget;
  await send({ action: "select_team_source", source: select.value }, `${select.value} team source selected. Current teams kept.`);
  select.value = state.team_source.name;
  select.focus();
});

document.querySelectorAll("[data-ban-kind]").forEach(section => {
  const kind = section.dataset.banKind;
  searchable(section.querySelector('[name="ban"]'), () => state.ban_options[kind].choices.filter(name => !state.bans[kind].includes(name)));
  section.querySelector(".ban-form").addEventListener("submit", async event => {
    event.preventDefault();
    const form = event.currentTarget;
    if (await saveBan(section, "add_ban", form.elements.ban.value)) form.reset();
    form.elements.ban.focus();
  });
});
document.querySelector("#swap-sides").addEventListener("click", async () => {
  if (swapping) return;
  swapping = true;
  workspace.disabled = true;
  try {
    const saved = await Promise.all(teamSavers.map(save => save()));
    if (saved.every(Boolean)) {
      await send({ action: "swap_sides" }, "Team names, scores, and rosters swapped.", { teams: true, background: true });
    } else {
      notice.className = "error";
      notice.textContent = "Save or correct team details before swapping sides.";
    }
  } finally {
    swapping = false;
    workspace.disabled = false;
  }
});

document.querySelectorAll(".team-card").forEach(card => {
  const team = Number(card.dataset.team);
  const form = card.querySelector(".team-form");
  const status = card.querySelector(".save-status");
  const retry = card.querySelector(".retry-save");
  let timer;
  let revision = 0;
  let pendingSave = Promise.resolve(true);

  const save = () => {
    clearTimeout(timer);
    const currentRevision = revision;
    // Read the latest draft after earlier saves finish, including before a side swap.
    pendingSave = pendingSave.then(async () => {
      const saved = state.teams[team - 1];
      const name = form.elements.name.value.trim();
      const scoreInput = form.elements.score;
      const score = scoreInput.valueAsNumber;
      const payload = { action: "update_team", team };
      let invalid = false;
      if (name !== saved.Name) {
        if (name && name.length <= 80) payload.name = name;
        else invalid = true;
      }
      if (score !== saved.Score || scoreInput.validity.badInput) {
        if (Number.isInteger(score) && score >= 0 && score <= 999) payload.score = score;
        else invalid = true;
      }
      let success = true;
      if ("name" in payload || "score" in payload) {
        status.textContent = "Saving...";
        success = await send(payload, `Team ${team} details saved.`, { background: true });
      }
      if (revision === currentRevision) {
        status.textContent = !success ? "Not saved. Retry when connected." : invalid ? "Not saved. Enter a name and a score from 0 to 999." : "Saved automatically.";
        status.classList.toggle("error", !success || invalid);
        retry.hidden = success;
      }
      return success && !invalid;
    });
    return pendingSave;
  };
  teamSavers.push(save);
  form.addEventListener("input", () => {
    revision += 1;
    clearTimeout(timer);
    status.textContent = "Unsaved changes...";
    status.classList.remove("error");
    retry.hidden = true;
    timer = setTimeout(save, 450);
  });
  form.addEventListener("change", save);
  form.addEventListener("submit", event => {
    event.preventDefault();
    save();
  });
  retry.addEventListener("click", save);
  card.querySelector(".player-form").addEventListener("submit", async event => {
    event.preventDefault();
    const form = event.currentTarget;
    if (await send({ action: "add_player", team, player: form.elements.player.value }, "Player added to roster.")) form.reset();
    form.elements.player.focus();
  });
  searchable(card.querySelector('.source-team-form [name="team"]'), () => state.team_source.teams);
  card.querySelector(".source-team-form").addEventListener("submit", async event => {
    event.preventDefault();
    const form = event.currentTarget;
    if (await send({ action: "load_source_team", team, name: form.elements.team.value }, `Team ${team} loaded from source.`, { teams: true })) form.reset();
  });
});

async function initialize() {
  try {
    const response = await fetch("/api/state", { cache: "no-store" });
    if (!response.ok) throw new Error("Could not load the workspace. Refresh to try again.");
    state = await response.json();
    render({ teams: true, game: true });
    workspace.disabled = false;
    document.querySelector("#connection").textContent = "Server connected";
    document.querySelector("#connection").classList.add("connected");
    notice.textContent = `${state.game} loaded. Controls ready.`;
  } catch (error) {
    notice.className = "error";
    notice.textContent = error.message;
    document.querySelector("#connection").textContent = "Connection unavailable";
  }
}
initialize();
