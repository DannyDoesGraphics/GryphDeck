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
    select.replaceChildren(
      ...state.games.map((name) => new Option(name, name)),
    );
    select.value = state.game_key;
  }
  document.querySelectorAll("[data-scene-panel]").forEach((panel) => {
    const scene = panel.dataset.scenePanel;
    const components = state.components[scene];
    panel.querySelector(".enabled-count").textContent =
      `${components.filter((item) => item.enabled).length} enabled`;
    const list = panel.querySelector(".components");
    list.replaceChildren(
      ...components.map((component) => {
        const button = element("button", "component");
        button.type = "button";
        button.dataset.component = component.name;
        button.setAttribute("aria-pressed", String(component.enabled));
        const name = element("span", "component-name", component.name);
        name.append(
          element(
            "small",
            "",
            component.position.replace(/([a-z])([A-Z])/g, "$1 $2"),
          ),
        );
        const toggle = element("span", "toggle");
        toggle.setAttribute("aria-hidden", "true");
        button.append(
          name,
          element("span", "component-state", component.enabled ? "ON" : "OFF"),
          toggle,
        );
        button.addEventListener("click", async () => {
          await send(
            { action: "toggle_component", scene, component: component.name },
            "Component state updated.",
          );
          [...list.children]
            .find((item) => item.dataset.component === component.name)
            ?.focus();
        });
        return button;
      }),
    );
    if (!components.length)
      list.append(
        element("p", "muted", "No components are configured for this scene."),
      );
  });

  state.teams.forEach((team, index) => {
    const side = index === 0 ? "left" : "right";
    document.querySelector(`#summary-${side}`).textContent =
      team.Name || `Team ${index + 1}`;
    document.querySelector(`#score-${side}`).textContent = team.Score;
    const card = document.querySelector(`[data-team="${index + 1}"]`);
    const editable = team.Source.Kind === "manual";
    // Locked teams follow source, refresh on each new render
    if (teams || !editable)
      card.querySelector('[name="name"]').value = team.Name;
    if (teams) card.querySelector('[name="score"]').value = team.Score;
    renderSource(card, team.Source);
    card.querySelector('[name="name"]').disabled = !editable;
    // Manual teams type their roster; sourced teams pick a lineup from the bench.
    card.querySelector(".player-form").hidden = !editable;
    renderBench(card, team, editable);
    const subs = new Set(
      team.Roster.filter((entry) => entry.Sub).map((entry) => entry.Name),
    );
    const label = (name) => (subs.has(name) ? `${name} (sub)` : name);
    card.querySelector(".player-count").textContent = editable
      ? `${team.Players.length} player${team.Players.length === 1 ? "" : "s"}`
      : `${team.Players.length} shown · ${team.Bench.length} on bench`;
    const roster = card.querySelector(".players");
    roster.replaceChildren(
      ...team.Players.map((player, playerIndex) => {
        const row = element("li", "player");
        const remove = element(
          "button",
          "remove-player",
          editable ? "Remove" : "Bench",
        );
        remove.type = "button";
        remove.setAttribute(
          "aria-label",
          editable
            ? `Remove ${player} from team ${index + 1}`
            : `Move ${player} to the bench`,
        );
        remove.addEventListener("click", async () => {
          await send(
            { action: "remove_player", team: index + 1, player },
            editable ? "Player removed." : `${player} moved to the bench.`,
          );
          card
            .querySelector(editable ? '[name="player"]' : '[name="bench"]')
            .focus();
        });
        row.dataset.index = String(playerIndex);
        // Drag the row, or focus the handle and use the arrow keys.
        row.draggable = true;
        const handle = element("button", "drag-handle", "⠿");
        handle.type = "button";
        handle.setAttribute(
          "aria-label",
          `Move ${player}. Drag, or press the up and down arrow keys.`,
        );
        handle.addEventListener("keydown", (event) => {
          const step = { ArrowUp: -1, ArrowDown: 1 }[event.key];
          if (!step) return;
          event.preventDefault();
          movePlayer(index + 1, playerIndex, playerIndex + step, player);
        });
        const position = element(
          "span",
          "player-index",
          String(playerIndex + 1).padStart(2, "0"),
        );
        if (editable) {
          row.append(
            handle,
            position,
            element("span", "player-name", player),
            remove,
          );
          return row;
        }
        // Swap a bench player into this slot.
        const slot = element("select", "lineup-player");
        slot.setAttribute("aria-label", `Player ${playerIndex + 1}`);
        slot.append(
          new Option(label(player), player, true, true),
          ...team.Bench.map((name) => new Option(label(name), name)),
        );
        slot.disabled = !team.Bench.length;
        slot.addEventListener("change", async () => {
          const substitute = slot.value;
          await send(
            {
              action: "substitute_player",
              team: index + 1,
              index: playerIndex,
              player,
              substitute,
            },
            `${substitute} subbed in for ${player}.`,
          );
          document
            .querySelector(
              `[data-team="${index + 1}"] .players [data-index="${playerIndex}"] .lineup-player`,
            )
            ?.focus();
        });
        row.append(handle, position, slot, remove);
        return row;
      }),
    );
    if (!team.Players.length)
      roster.append(
        element(
          "li",
          "empty-roster",
          editable ? "No players added." : "No players in the lineup.",
        ),
      );
  });
  renderBans({ game });
}

async function movePlayer(team, from, to, player) {
  const players = state.teams[team - 1].Players;
  if (to < 0 || to >= players.length || to === from) return;
  await send(
    { action: "move_player", team, player, from, to },
    `${player} moved to position ${to + 1}.`,
  );
  // Keep the handle focused so the arrow keys can keep moving the player.
  document
    .querySelector(
      `[data-team="${team}"] .players [data-index="${to}"] .drag-handle`,
    )
    ?.focus();
}

// Where a dragged row would land: the number of other rows above the pointer.
function dropPosition(roster, draggedRow, clientY) {
  const rows = [...roster.querySelectorAll(".player")].filter(
    (row) => row !== draggedRow,
  );
  const below = rows.find((row) => {
    const box = row.getBoundingClientRect();
    return clientY < box.top + box.height / 2;
  });
  return { rows, below, position: below ? rows.indexOf(below) : rows.length };
}

function renderBench(card, team, editable) {
  const form = card.querySelector(".bench-form");
  form.hidden = editable;
  if (editable) return;
  const select = form.elements.bench;
  const subs = new Set(
    team.Roster.filter((entry) => entry.Sub).map((entry) => entry.Name),
  );
  select.replaceChildren(
    new Option(
      team.Bench.length ? "+ Add from bench" : "Bench is empty",
      "",
      true,
      true,
    ),
    ...team.Bench.map(
      (name) => new Option(subs.has(name) ? `${name} (sub)` : name, name),
    ),
  );
  select.disabled = !team.Bench.length;
}

function renderSource(card, source) {
  const select = card.querySelector('[name="source"]');
  if (select.options.length !== state.sources.length) {
    select.replaceChildren(
      ...state.sources.map((option) => new Option(option.label, option.kind)),
    );
  }
  select.value = source.Kind;
  const option = state.sources.find((item) => item.kind === source.Kind);
  const note = card.querySelector(".source-note");
  note.textContent = source.Error
    ? `${source.Label} failed: ${source.Error}. Keeping the team as it was.`
    : option
      ? option.description
      : `Name and roster come from ${source.Label}.`;
  note.classList.toggle("error", Boolean(source.Error));
  card.dataset.locked = String(source.Kind !== "manual");
}

function renderBans({ game }) {
  document.querySelectorAll("[data-ban-kind]").forEach((section) => {
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
      feedback.textContent = options.choices.length
        ? `Type to search the game's ${kind === "map" ? "maps" : "heroes"}.`
        : `No ${kind === "map" ? "maps" : "heroes"} configured for this game.`;
    }
    section.querySelector(".ban-count").textContent =
      `${selected.length} ${selection}${selected.length === 1 ? "" : "s"}`;
    const suggestions = section.querySelector("datalist");
    const available = options.choices.filter(
      (name) => !selected.includes(name),
    );
    if (
      JSON.stringify([...suggestions.options].map((option) => option.value)) !==
      JSON.stringify(available)
    ) {
      suggestions.replaceChildren(
        ...available.map((name) => new Option(name, name)),
      );
    }
    const list = section.querySelector(".ban-list");
    list.replaceChildren(
      ...selected.map((name, index) => {
        const row = element("li", "player");
        const remove = element("button", "remove-player", "Remove");
        remove.type = "button";
        remove.setAttribute(
          "aria-label",
          `Remove ${name} ${kind} ${selection}`,
        );
        remove.addEventListener("click", async () => {
          await saveBan(section, "remove_ban", name);
          input.focus();
        });
        row.append(
          element("span", "player-index", String(index + 1).padStart(2, "0")),
          element("span", "player-name", name),
          remove,
        );
        return row;
      }),
    );
    if (!selected.length)
      list.append(
        element("li", "empty-roster", `No ${kind} ${selection}s added.`),
      );
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
  const request = requestQueue.then(() =>
    performRequest(payload, message, options),
  );
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
    if (!response.ok)
      throw new Error(data.error || "The change could not be saved.");
    state = data;
    render(options);
    notice.className = "";
    notice.textContent = message;
    return true;
  } catch (error) {
    notice.className = "error";
    notice.textContent =
      error.message || "Unable to reach the server. Try again.";
    return false;
  } finally {
    if (!options.background) workspace.disabled = swapping;
    workspace.setAttribute("aria-busy", "false");
  }
}

document.querySelector("#game-form").addEventListener("submit", (event) => {
  event.preventDefault();
  send(
    { action: "load_game", game: document.querySelector("#game").value },
    "Game loaded. Components, map picks, and hero bans reset; teams retained.",
    { game: true },
  );
});

document.querySelectorAll("[data-ban-kind]").forEach((section) => {
  section
    .querySelector(".ban-form")
    .addEventListener("submit", async (event) => {
      event.preventDefault();
      const form = event.currentTarget;
      if (await saveBan(section, "add_ban", form.elements.ban.value))
        form.reset();
      form.elements.ban.focus();
    });
});
document.querySelector("#swap-sides").addEventListener("click", async () => {
  if (swapping) return;
  swapping = true;
  workspace.disabled = true;
  try {
    const saved = await Promise.all(teamSavers.map((save) => save()));
    if (saved.every(Boolean)) {
      await send(
        { action: "swap_sides" },
        "Team names, scores, and rosters swapped.",
        { teams: true, background: true },
      );
    } else {
      notice.className = "error";
      notice.textContent =
        "Save or correct team details before swapping sides.";
    }
  } finally {
    swapping = false;
    workspace.disabled = false;
  }
});

document.querySelectorAll(".team-card").forEach((card) => {
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
        if (Number.isInteger(score) && score >= 0 && score <= 999)
          payload.score = score;
        else invalid = true;
      }
      let success = true;
      if ("name" in payload || "score" in payload) {
        status.textContent = "Saving...";
        success = await send(payload, `Team ${team} details saved.`, {
          background: true,
        });
      }
      if (revision === currentRevision) {
        status.textContent = !success
          ? "Not saved. Retry when connected."
          : invalid
            ? "Not saved. Enter a name and a score from 0 to 999."
            : "Saved automatically.";
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
  form.addEventListener("submit", (event) => {
    event.preventDefault();
    save();
  });
  retry.addEventListener("click", save);
  card
    .querySelector(".source-form")
    .addEventListener("change", async (event) => {
      const select = event.target;
      const option = state.sources.find((item) => item.kind === select.value);
      // Keep a typed name before the new source takes over the team.
      if (!(await save())) {
        select.value = state.teams[team - 1].Source.Kind;
        return;
      }
      if (
        !(await send(
          { action: "set_team_source", team, source: select.value },
          `Team ${team} source set to ${option ? option.label : select.value}.`,
          { teams: true },
        ))
      ) {
        select.value = state.teams[team - 1].Source.Kind;
      }
      select.focus();
    });
  card
    .querySelector(".source-form")
    .addEventListener("submit", (event) => event.preventDefault());
  const bench = card.querySelector(".bench-form");
  bench.addEventListener("submit", (event) => event.preventDefault());
  bench.elements.bench.addEventListener("change", async (event) => {
    const player = event.target.value;
    if (!player) return;
    await send(
      { action: "add_player", team, player },
      `${player} added to the lineup.`,
    );
    card.querySelector('[name="bench"]').focus();
  });
  const roster = card.querySelector(".players");
  let dragged = null;
  const clearDropMarks = () =>
    roster
      .querySelectorAll(".drop-before, .drop-after")
      .forEach((row) => row.classList.remove("drop-before", "drop-after"));
  roster.addEventListener("dragstart", (event) => {
    const row = event.target.closest(".player[draggable='true']");
    if (!row) return;
    dragged = { index: Number(row.dataset.index), row };
    event.dataTransfer.effectAllowed = "move";
    event.dataTransfer.setData("text/plain", row.dataset.index);
    // Mark it after the browser has captured the drag image.
    requestAnimationFrame(() => row.classList.add("dragging"));
  });
  roster.addEventListener("dragover", (event) => {
    if (!dragged) return;
    event.preventDefault();
    event.dataTransfer.dropEffect = "move";
    const { rows, below } = dropPosition(roster, dragged.row, event.clientY);
    clearDropMarks();
    if (below) below.classList.add("drop-before");
    else rows.at(-1)?.classList.add("drop-after");
  });
  roster.addEventListener("dragleave", (event) => {
    if (!roster.contains(event.relatedTarget)) clearDropMarks();
  });
  roster.addEventListener("drop", (event) => {
    if (!dragged) return;
    event.preventDefault();
    const { position } = dropPosition(roster, dragged.row, event.clientY);
    const player = state.teams[team - 1].Players[dragged.index];
    movePlayer(team, dragged.index, position, player);
  });
  roster.addEventListener("dragend", () => {
    dragged?.row.classList.remove("dragging");
    dragged = null;
    clearDropMarks();
  });
  card
    .querySelector(".player-form")
    .addEventListener("submit", async (event) => {
      event.preventDefault();
      const form = event.currentTarget;
      if (
        await send(
          { action: "add_player", team, player: form.elements.player.value },
          "Player added to roster.",
        )
      )
        form.reset();
      form.elements.player.focus();
    });
});

async function initialize() {
  try {
    const response = await fetch("/api/state", { cache: "no-store" });
    if (!response.ok)
      throw new Error("Could not load the workspace. Refresh to try again.");
    state = await response.json();
    render({ teams: true, game: true });
    workspace.disabled = false;
    document.querySelector("#connection").textContent = "Server connected";
    document.querySelector("#connection").classList.add("connected");
    notice.textContent = `${state.game} loaded. Controls ready.`;
  } catch (error) {
    notice.className = "error";
    notice.textContent = error.message;
    document.querySelector("#connection").textContent =
      "Connection unavailable";
  }
}
initialize();
