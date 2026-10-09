"use strict";
// GryphDeck: report which players sit on which side of the spectator's top bar.
//
// Loaded by the GryphDeck mod's copy of hud_spectate_bar, so it only runs while spectating.
// Once a second it reads each CitadelHudTopBarTeam (class team1 = Hidden King, team2 =
// Archmother) and the PlayerName / HeroName labels of its players, and prints a line
//   GRYPHDECK {"type":"teams","teams":[{"side":1,"players":[{"name":..,"hero":..}]},..]}
// to the console when it changes (and every 10 seconds regardless). Deadlock started with
// -condebug copies the console to citadel/console.log, where tools/deadlock/spectator.py
// picks it up and forwards it to GryphDeck.
(function () {
    function emit(payload) {
        $.Msg("GRYPHDECK " + JSON.stringify(payload));
    }

    function root(panel) {
        while (panel.GetParent()) panel = panel.GetParent();
        return panel;
    }

    function walk(panel, visit) {
        visit(panel);
        for (let i = 0; i < panel.GetChildCount(); i++) walk(panel.GetChild(i), visit);
    }

    function labelText(panel, className) {
        let text = "";
        walk(panel, child => {
            if (!text && child.BHasClass(className) && typeof child.text === "string") text = child.text;
        });
        return text;
    }

    function readTeams() {
        const teams = [];
        walk(root($.GetContextPanel()), panel => {
            if (panel.paneltype !== "CitadelHudTopBarTeam") return;
            const side = panel.BHasClass("team1") ? 1 : panel.BHasClass("team2") ? 2 : 0;
            const players = [];
            walk(panel, child => {
                if (child.paneltype === "CitadelHudTopBarPlayer") {
                    players.push({ name: labelText(child, "PlayerName"), hero: labelText(child, "HeroName") });
                }
            });
            teams.push({ side, players });
        });
        return teams;
    }

    let last = "";
    let quiet = 0;
    function tick() {
        try {
            const teams = readTeams();
            const text = JSON.stringify(teams);
            if (text !== last || ++quiet >= 10) {
                last = text;
                quiet = 0;
                emit({ type: "teams", teams });
            }
        } catch (error) {
            emit({ type: "error", message: String(error) });
        }
        $.Schedule(1.0, tick);
    }

    emit({ type: "loaded" });
    tick();
})();
