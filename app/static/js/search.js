"use strict";

function searchable(input, names) {
  const search = document.createElement("div");
  search.className = "search";
  const results = document.createElement("ul");
  results.className = "search-results";
  results.id = `${input.id}-results`;
  results.setAttribute("role", "listbox");
  results.hidden = true;
  input.replaceWith(search);
  search.append(input, results);
  input.setAttribute("role", "combobox");
  input.setAttribute("aria-autocomplete", "list");
  input.setAttribute("aria-controls", results.id);
  input.setAttribute("aria-expanded", "false");

  let found = [];
  let active = -1;
  const close = () => {
    results.hidden = true;
    input.setAttribute("aria-expanded", "false");
  };
  const pick = name => {
    input.value = name;
    close();
    input.form.requestSubmit();
  };
  const show = () => {
    const query = input.value.trim().toLowerCase();
    found = names().filter(name => name.toLowerCase().includes(query));
    active = Math.min(active, found.length - 1);
    results.replaceChildren(...found.map((name, index) => {
      const option = document.createElement("li");
      option.className = "search-result";
      option.textContent = name;
      option.setAttribute("role", "option");
      option.setAttribute("aria-selected", String(index === active));
      option.addEventListener("mousedown", event => {
        event.preventDefault();
        pick(name);
      });
      return option;
    }));
    if (!found.length) {
      const empty = document.createElement("li");
      empty.className = "search-empty";
      empty.textContent = "No matches";
      results.append(empty);
    }
    results.children[active]?.scrollIntoView({ block: "nearest" });
    results.hidden = false;
    input.setAttribute("aria-expanded", "true");
  };

  input.addEventListener("focus", () => {
    show();
    results.scrollIntoView({ block: "nearest" });
  });
  input.addEventListener("blur", close);
  input.addEventListener("input", () => {
    active = -1;
    show();
  });
  input.addEventListener("keydown", event => {
    if (event.key === "ArrowDown" || event.key === "ArrowUp") {
      event.preventDefault();
      active = event.key === "ArrowDown" ? Math.min(active + 1, found.length - 1) : Math.max(active - 1, -1);
      show();
    } else if (event.key === "Enter" && !results.hidden && found[active]) {
      event.preventDefault();
      pick(found[active]);
    } else if (event.key === "Escape") {
      close();
    }
  });
}
