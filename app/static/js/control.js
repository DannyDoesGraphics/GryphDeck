"use strict";

const workspace = document.querySelector("#workspace");
const notice = document.querySelector("#notice");
let state;
let requestQueue = Promise.resolve();
let swapping = false;
const teamSavers = [];
const unsavedTeams = new Set();

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
  }
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
    card.querySelector(".player-count").textContent = `${team.Players.length} player${team.Players.length === 1 ? "" : "s"}`;
    renderRoster(card, team, index);
  });
  // Sides by their in-game names (Deadlock: Hidden King left, Archmother right) once known,
  // like the overlays, which stay grey until then.
  document.body.dataset.game = state.game;
  document.body.toggleAttribute("data-sides-known", state.sides.known);
  document.querySelectorAll("[data-side-name]").forEach(label => {
    const name = sideNames()[label.dataset.sideName - 1];
    if (label.classList.contains("side-caption")) label.textContent = name.toUpperCase();
    else if (label.tagName === "OPTION") label.textContent = name;
    else label.textContent = ["Left", "Right"].includes(name) ? `${name} team` : name;
  });
  renderBans({ game });
  renderDraft({ game });
  renderSides();
}

const sidesSection = document.querySelector(".sides-section");

function sideNames() {
  return state.sides.known ? state.side_names : ["Left", "Right"];
}

function renderSides() {
  const sides = state.sides;
  sidesSection.hidden = state.game !== "Deadlock";
  const label = sidesSection.querySelector(".sides-state");
  label.textContent = sides.known ? "Known" : "Grey";
  label.classList.toggle("known", sides.known);
  const feedback = sidesSection.querySelector(".sides-feedback");
  feedback.textContent = sides.status;
  feedback.classList.toggle("error", sides.attention);
  sidesSection.querySelector("#sides-auto").setAttribute("aria-pressed", String(sides.auto));
  sidesSection.querySelector("#sides-grey").disabled = !sides.known;
}

sidesSection.querySelectorAll("[data-left]").forEach(button => button.addEventListener("click", async event => {
  const target = event.currentTarget;
  const left = Number(target.dataset.left);
  if (left === 1) {
    await send({ action: "update_sides", left }, "Sides set.");
    target.focus();
    return;
  }
  // Archmother on the left swaps the teams, so save team edits first like Swap sides.
  if (swapping) return;
  swapping = true;
  workspace.disabled = true;
  try {
    const saved = await Promise.all(teamSavers.map(save => save()));
    if (saved.every(Boolean)) {
      await send({ action: "update_sides", left }, "Sides set; teams swapped.", { teams: true, background: true });
    } else {
      notice.className = "error";
      notice.textContent = "Save or correct team details first.";
    }
  } finally {
    swapping = false;
    workspace.disabled = false;
    target.focus();
  }
}));
sidesSection.querySelector("#sides-grey").addEventListener("click", async event => {
  await send({ action: "update_sides", known: false }, "Team colours set to grey.");
  event.currentTarget.focus();
});
sidesSection.querySelector("#sides-auto").addEventListener("click", async event => {
  const auto = !state.sides.auto;
  await send({ action: "update_sides", auto }, auto ? "Side detection on." : "Side detection off.");
  event.currentTarget.focus();
});

const draftForm = document.querySelector(".draft-form");

// One row per player with their hero pick (roster player N drafted pick N), plus open pick slots.
function renderRoster(card, team, index) {
  const picks = state.draft?.teams[index].picks ?? [];
  const roster = card.querySelector(".players");
  roster.classList.toggle("with-picks", picks.length > 0);
  card.querySelector(".roster-title").textContent = picks.length ? "Players and picks" : "Player roster";
  // Rebuild only when the rows change, so a focused hero select is not replaced.
  const layout = JSON.stringify([team.Players, picks.length]);
  if (roster.dataset.layout === layout) return;
  roster.dataset.layout = layout;
  const rows = Math.max(team.Players.length, picks.length);
  roster.replaceChildren(...Array.from({ length: rows }, (_, slot) => {
    const player = team.Players[slot];
    const row = element("li", "player");
    row.append(
      element("span", "player-index", String(slot + 1).padStart(2, "0")),
      element("span", player === undefined ? "player-name open-slot" : "player-name", player ?? "No player"),
    );
    if (slot < picks.length) row.append(heroSelect(index + 1, "picks", slot, `${player ?? `Pick ${slot + 1}`} hero`));
    if (player !== undefined) {
      const remove = element("button", "remove-player", "Remove");
      remove.type = "button";
      remove.setAttribute("aria-label", `Remove ${player} from team ${index + 1}`);
      remove.addEventListener("click", async () => {
        await send({ action: "remove_player", team: index + 1, player }, "Player removed.");
        card.querySelector('[name="player"]').focus();
      });
      row.append(remove);
    }
    return row;
  }));
  if (!rows) roster.append(element("li", "empty-roster", "No players added."));
}

function heroSelect(team, kind, slot, label) {
  const select = element("select", "hero-select");
  select.dataset.draftTeam = team;
  select.dataset.kind = kind;
  select.dataset.slot = slot;
  select.setAttribute("aria-label", label);
  const choose = async move => {
    const success = await send(
      { action: "set_draft_slot", team, kind, slot, hero: select.value || null, move },
      `${select.value || "Slot"} ${select.value ? (kind === "picks" ? "picked" : "banned") : "cleared"}.`,
    );
    draftFeedback(success);
    document.querySelector(`.hero-select[data-draft-team="${team}"][data-kind="${kind}"][data-slot="${slot}"]`)?.focus();
  };
  select.addEventListener("change", () => {
    // Choosing again drops any move still waiting for an answer.
    const hero = select.value;
    document.querySelector(".move-confirm")?.cancel();
    select.value = hero;
    const from = draftSlotOf(select.value);
    if (from) confirmMove(select, from, () => choose(true));
    else choose(false);
  });
  return select;
}

// Where a hero sits in the draft, e.g. "Catnip Inc pick 2", or null.
function draftSlotOf(hero) {
  if (!hero || !state.draft) return null;
  for (const [index, team] of state.draft.teams.entries()) {
    for (const kind of ["picks", "bans"]) {
      const slot = team[kind].indexOf(hero);
      if (slot >= 0) return `${state.teams[index].Name || sideNames()[index]} ${kind === "picks" ? "pick" : "ban"} ${slot + 1}`;
    }
  }
  return null;
}

// Taking a hero from another slot shows on stream at once, so it is confirmed next to the select.
function confirmMove(select, from, move) {
  const previous = state.draft.teams[select.dataset.draftTeam - 1][select.dataset.kind][Number(select.dataset.slot)] || "";
  const box = element("div", "move-confirm");
  box.setAttribute("role", "group");
  box.append(element("span", "", `Move ${select.value} from ${from}?`));
  const confirm = element("button", "primary", "Move");
  const cancel = element("button", "secondary", "Cancel");
  confirm.type = cancel.type = "button";
  box.cancel = () => {
    box.remove();
    select.value = previous;
  };
  confirm.addEventListener("click", () => {
    box.remove();
    move();
  });
  cancel.addEventListener("click", () => {
    box.cancel();
    select.focus();
  });
  box.addEventListener("keydown", event => {
    if (event.key !== "Escape") return;
    box.cancel();
    select.focus();
  });
  box.append(confirm, cancel);
  select.after(box);
  confirm.focus();
}

function draftFeedback(success) {
  const feedback = draftForm.querySelector(".draft-feedback");
  feedback.textContent = notice.textContent;
  feedback.classList.toggle("error", !success);
}

{
  const form = draftForm;
  let timer;
  const saveLabel = async () => {
    clearTimeout(timer);
    if (form.elements.label.value.trim() === state.draft?.label) return;
    draftFeedback(await send({ action: "update_draft", label: form.elements.label.value }, "Match label saved.", { background: true }));
  };
  form.elements.label.addEventListener("input", () => {
    clearTimeout(timer);
    timer = setTimeout(saveLabel, 450);
  });
  form.elements.label.addEventListener("change", saveLabel);
  const names = form.querySelector("#draft-player-names");
  names.addEventListener("click", async () => {
    const player_names = !state.draft.player_names;
    draftFeedback(await send({ action: "update_draft", player_names }, player_names ? "Player names shown on picks." : "Hero picks only."));
    names.focus();
  });
  form.elements.first_pick.addEventListener("change", async () => {
    draftFeedback(await send({ action: "update_draft", first_pick: Number(form.elements.first_pick.value) }, "First pick updated."));
    form.elements.first_pick.focus();
  });
  form.addEventListener("submit", event => {
    event.preventDefault();
    saveLabel();
  });
}

function renderDraft({ game }) {
  const draft = state.draft;
  draftForm.hidden = !draft;
  document.querySelectorAll("[data-bans]").forEach(bans => { bans.hidden = !draft; });
  if (!draft) return;
  const form = draftForm;
  if (game || document.activeElement !== form.elements.label) form.elements.label.value = draft.label;
  form.elements.first_pick.value = String(draft.first_pick);
  form.querySelector("#draft-player-names").setAttribute("aria-pressed", String(draft.player_names));

  draft.teams.forEach((team, index) => {
    const slots = document.querySelector(`[data-bans="${index + 1}"] .ban-slots`);
    if (game || slots.childElementCount !== team.bans.length) {
      const name = sideNames()[index];
      slots.replaceChildren(...team.bans.map((_, slot) => heroSelect(index + 1, "bans", slot, `${name} ban ${slot + 1}`)));
    }
  });
  document.querySelectorAll(".hero-select").forEach(select => {
    const current = draft.teams[select.dataset.draftTeam - 1][select.dataset.kind][Number(select.dataset.slot)] || "";
    // Heroes in another slot stay choosable: picking one moves it here, after a confirmation.
    select.replaceChildren(new Option("—", ""), ...draft.choices.map(name => {
      const from = name === current ? null : draftSlotOf(name);
      return new Option(from ? `${name} · ${from}` : name, name);
    }));
    if (!select.nextElementSibling?.matches(".move-confirm")) select.value = current;
  });
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
    const suggestions = section.querySelector("datalist");
    const available = options.choices.filter(name => !selected.includes(name));
    if (JSON.stringify([...suggestions.options].map(option => option.value)) !== JSON.stringify(available)) {
      suggestions.replaceChildren(...available.map(name => new Option(name, name)));
    }
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
  send({ action: "load_game", game: document.querySelector("#game").value }, "Game loaded. Components, map picks, hero bans, and the draft reset; teams retained.", { game: true });
});

document.querySelectorAll("[data-ban-kind]").forEach(section => {
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
      await send({ action: "swap_sides" }, "Team names, scores, rosters, and drafts swapped.", { teams: true, background: true });
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
        if (success && !invalid) unsavedTeams.delete(team);
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
    unsavedTeams.add(team);
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
});

// Deadlock can change the state (side detection swaps teams), so follow the server while
// nothing is being edited here. Team fields refresh unless one of them has focus.
async function poll() {
  try {
    if (!swapping && workspace.getAttribute("aria-busy") !== "true") {
      const response = await fetch("/api/state", { cache: "no-store" });
      if (response.ok) {
        const next = await response.json();
        if (JSON.stringify(next) !== JSON.stringify(state)) {
          const editingTeams = document.activeElement?.closest(".team-form, .draft-form, .ban-form");
          state = next;
          render({ teams: !editingTeams && !unsavedTeams.size });
        }
      }
    }
  } catch {
    // The status line reports failures from real edits; polling stays quiet.
  } finally {
    setTimeout(poll, 2000);
  }
}

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
    setTimeout(poll, 2000);
  } catch (error) {
    notice.className = "error";
    notice.textContent = error.message;
    document.querySelector("#connection").textContent = "Connection unavailable";
  }
}
initialize();
