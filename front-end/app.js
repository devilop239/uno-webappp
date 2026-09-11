(() => {
  "use strict";

  const app = document.querySelector("#app");
  const nameModal = document.querySelector("#name-modal");
  const colorModal = document.querySelector("#color-modal");
  const colorOptions = document.querySelector("#color-options");
  const storageKey = "uno-arena-player";
  const roomKey = "uno-arena-room";
  const colors = { r: "Red", b: "Blue", g: "Green", y: "Yellow", p: "Purple", o: "Orange" };
  const botClasses = {
    "Pawri Wala Bhai": "bot-1",
    "Chai Sutta Boss": "bot-2",
    "Titu Mama": "bot-3",
    Circuit: "bot-4",
    "Babu Bhaiya": "bot-5",
  };
  const defaultModes = [
    { id: "classic", name: "Classic UNO", description: "108 cards, stacking and Wild +4 challenges.", image: "/images/Modes_Selection/Classic.jpg" },
    { id: "fast", name: "Fast UNO", description: "Short turns for quick table action.", image: "/images/Modes_Selection/Sanic.png" },
    { id: "wild", name: "Wild UNO", description: "Extra wild cards and unpredictable turns.", image: "/images/Modes_Selection/Wild.jpg" },
    { id: "rainbow", name: "Rainbow UNO", description: "Six colors, Draw 8 and Rainbow cards.", image: "/images/Modes_Selection/rainbow.jpg" },
    { id: "no_mercy", name: "NO MERCY", description: "Ruthless stacking and elimination rules.", image: "/images/Modes_Selection/Wild.jpg" },
    { id: "sudden_death", name: "Sudden Death", description: "The first empty hand wins instantly.", image: "/images/Modes_Selection/sudden death.jpg" },
  ];

  let player = null;
  let room = null;
  let socket = null;
  let reconnectTimer = null;
  let state = {};
  let hand = [];
  let modes = defaultModes;
  let screen = "home";
  let setupType = "bot";
  let selectedMode = "classic";
  let selectedDeck = "normal";
  let actionBusy = false;
  let botThinking = null;
  let matchFinished = false;

  const esc = (value) => String(value ?? "").replace(/[&<>"']/g, (char) => ({
    "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#039;",
  }[char]));
  const $ = (selector) => document.querySelector(selector);

  function telegramPlayer() {
    const tgUser = window.Telegram?.WebApp?.initDataUnsafe?.user;
    if (!tgUser?.id) return null;
    return { id: Number(tgUser.id), name: tgUser.first_name || "Player", fromTelegram: true };
  }

  function getPlayer() {
    const telegram = telegramPlayer();
    if (telegram) return telegram;
    try {
      const saved = JSON.parse(localStorage.getItem(storageKey) || "null");
      if (saved?.id && saved?.name) return saved;
    } catch (_) {}
    return null;
  }

  function savePlayer(next) {
    player = next;
    if (!next.fromTelegram) localStorage.setItem(storageKey, JSON.stringify(next));
  }

  function setConnection(text, online = true) {
    const pill = $("#connection-pill");
    if (!pill) return;
    pill.innerHTML = `<i></i><span>${esc(text)}</span>`;
    pill.classList.toggle("offline", !online);
  }

  function toast(message) {
    const region = $("#toast-region");
    const item = document.createElement("div");
    item.className = "toast";
    item.textContent = message;
    region.append(item);
    setTimeout(() => item.remove(), 3600);
  }

  async function api(path, options = {}) {
    const response = await fetch(path, {
      headers: { "Content-Type": "application/json", ...(options.headers || {}) },
      ...options,
    });
    const payload = await response.json().catch(() => ({}));
    if (!response.ok) throw new Error(payload.detail || "Something went wrong. Try again.");
    return payload;
  }

  function modeFor(id = selectedMode) {
    return modes.find((mode) => mode.id === id) || defaultModes[0];
  }

  function avatarInfo(item) {
    const name = String(item?.name || "Player");
    const initials = name.split(/\s+/).filter(Boolean).slice(0, 2).map((part) => part[0]).join("").toUpperCase() || "?";
    const botClass = botClasses[name] || "";
    const isYou = Number(item?.id) === Number(player?.id);
    return { initials, botClass, isYou };
  }

  function avatarMarkup(item, extraClass = "") {
    const info = avatarInfo(item);
    return `<span class="avatar ${info.isYou ? "you" : ""} ${info.botClass} ${extraClass}">${esc(info.initials)}</span>`;
  }

  function playerTile(item) {
    const info = avatarInfo(item);
    const status = info.isYou ? "You · host" : item.is_bot ? "Bot opponent" : "Joined player";
    return `<div class="player-tile">${avatarMarkup(item)}<div><strong>${esc(item.name)}</strong><small>${status}</small></div></div>`;
  }

  function showNameModal() {
    nameModal.classList.remove("hidden");
    setTimeout(() => $("#name-input")?.focus(), 30);
  }

  function renderHome() {
    screen = "home";
    const selected = modeFor();
    app.innerHTML = `
      <section class="home-hero">
        <p class="eyebrow">WELCOME TO THE TABLE</p>
        <h1>Play your next<br />great hand.</h1>
        <p class="muted">A fast, friendly UNO table for Telegram and mobile browsers. Pick a mode, invite your crew, and play with clear controls.</p>
        <div class="home-stats">
          <span class="stat-pill"><strong>2–4</strong> players</span>
          <span class="stat-pill"><strong>6</strong> modes</span>
          <span class="stat-pill"><strong>Normal</strong> & Anime decks</span>
        </div>
      </section>
      <div class="section-heading"><h3>Choose your table</h3><span>Swipe to explore</span></div>
      <section class="mode-scroller" aria-label="Game modes">
        ${modes.map((mode) => `
          <button type="button" class="mode-card ${mode.id === selected.id ? "selected" : ""}" data-mode="${esc(mode.id)}">
            <img src="${esc(mode.image)}" alt="" />
            <div class="mode-card-content">
              ${mode.id === selected.id ? '<span class="mode-selected">SELECTED</span>' : ""}
              <strong>${esc(mode.name)}</strong>
              <p>${esc(mode.description)}</p>
            </div>
          </button>`).join("")}
      </section>
      <div class="home-actions">
        <button class="primary-button wide" type="button" data-action="bot">Play with bots <span>→</span></button>
        <button class="secondary-button wide" type="button" data-action="friend">Play with friends <span>→</span></button>
      </div>`;

    app.querySelectorAll("[data-mode]").forEach((button) => button.addEventListener("click", () => {
      selectedMode = button.dataset.mode;
      renderHome();
    }));
    app.querySelectorAll("[data-action]").forEach((button) => button.addEventListener("click", () => renderSetup(button.dataset.action)));
  }

  function renderSetup(type) {
    screen = "setup";
    setupType = type;
    const isBot = type === "bot";
    const selected = modeFor();
    app.innerHTML = `
      <section class="screen-header">
        <a class="back-link" href="#" data-back>← Back to modes</a>
        <p class="eyebrow">${isBot ? "SOLO MATCH" : "PRIVATE ROOM"}</p>
        <h2>${isBot ? "Set up your table" : "Create or join a room"}</h2>
        <p class="muted">${isBot ? "Choose a familiar Indian meme-style opponent and set the deck before you deal." : "Share a six-digit code with friends. Everyone joins from their own phone."}</p>
      </section>
      <section class="setup-card">
        <label class="choice-label">GAME MODE</label>
        <select id="mode-select" aria-label="Game mode">
          ${modes.map((mode) => `<option value="${esc(mode.id)}" ${mode.id === selected.id ? "selected" : ""}>${esc(mode.name)}</option>`).join("")}
        </select>
        <label class="choice-label">CARD DECK</label>
        <div class="deck-grid">
          <button type="button" class="deck-choice ${selectedDeck === "normal" ? "active" : ""}" data-deck="normal"><strong>Normal deck</strong><small>Original UNO artwork</small></button>
          <button type="button" class="deck-choice ${selectedDeck === "anime" ? "active" : ""}" data-deck="anime"><strong>Anime deck</strong><small>Anime card artwork</small></button>
        </div>
        ${isBot ? `
          <label class="choice-label" for="bot-count">OPPONENTS</label>
          <select id="bot-count"><option value="1">1 bot · Head-to-head</option><option value="2">2 bots · Three-way</option><option value="3">3 bots · Full table</option></select>
          <button class="primary-button wide" id="create-button" type="button">Deal the first hand <span>→</span></button>
        ` : `
          <div class="segmented" style="margin-top:17px">
            <button type="button" class="segment active" data-lobby-tab="create"><strong>Create a room</strong><small>Host a new table</small></button>
            <button type="button" class="segment" data-lobby-tab="join"><strong>Join a room</strong><small>Use a friend's code</small></button>
          </div>
          <div id="lobby-form"></div>
        `}
        <p class="error-text" id="setup-error"></p>
      </section>`;

    $("#mode-select").addEventListener("change", (event) => {
      selectedMode = event.target.value;
      renderSetup(type);
    });
    app.querySelectorAll("[data-deck]").forEach((button) => button.addEventListener("click", () => {
      selectedDeck = button.dataset.deck;
      renderSetup(type);
    }));
    $("[data-back]").addEventListener("click", (event) => { event.preventDefault(); renderHome(); });
    if (isBot) $("#create-button").addEventListener("click", () => createGame(true));
    else {
      renderFriendForm("create");
      app.querySelectorAll("[data-lobby-tab]").forEach((tab) => tab.addEventListener("click", () => {
        app.querySelectorAll("[data-lobby-tab]").forEach((item) => item.classList.toggle("active", item === tab));
        renderFriendForm(tab.dataset.lobbyTab);
      }));
    }
  }

  function renderFriendForm(tab) {
    const form = $("#lobby-form");
    form.innerHTML = tab === "create"
      ? `<button class="primary-button wide" id="create-button" type="button">Create private room <span>→</span></button>`
      : `<label class="choice-label" for="room-input">ROOM CODE</label><div class="inline-form"><input id="room-input" class="text-input" inputmode="numeric" maxlength="6" placeholder="e.g. 482190" /><button class="primary-button" id="join-button" type="button">Join</button></div>`;
    $("#create-button")?.addEventListener("click", () => createGame(false));
    $("#join-button")?.addEventListener("click", joinGame);
  }

  async function createGame(isBot) {
    const errorTarget = $("#setup-error");
    try {
      setConnection("Creating…");
      const data = await api("/api/game/create", {
        method: "POST",
        body: JSON.stringify({
          user_id: player.id,
          first_name: player.name,
          mode: selectedMode,
          deck_style: selectedDeck,
          hand_size: 7,
          stacking_enabled: true,
          is_bot_match: isBot,
          bot_count: isBot ? Number($("#bot-count").value) : 1,
        }),
      });
      room = { id: data.room_id, session: data.session_token, host: true };
      state = data.state || {};
      hand = data.hand || [];
      persistRoom();
      isBot ? enterGame() : enterLobby();
    } catch (error) {
      setConnection("Ready");
      if (errorTarget) errorTarget.textContent = error.message;
    }
  }

  async function joinGame() {
    const errorTarget = $("#setup-error");
    const value = $("#room-input").value.replace(/\D/g, "");
    if (value.length !== 6) { errorTarget.textContent = "Enter the six-digit room code."; return; }
    try {
      setConnection("Joining…");
      const data = await api("/api/game/join", {
        method: "POST",
        body: JSON.stringify({ room_id: Number(value), user_id: player.id, first_name: player.name }),
      });
      room = { id: data.room_id, session: data.session_token, host: false };
      state = data.state || {};
      hand = data.hand || [];
      persistRoom();
      enterLobby();
    } catch (error) {
      setConnection("Ready");
      errorTarget.textContent = error.message;
    }
  }

  function persistRoom() {
    sessionStorage.setItem(roomKey, JSON.stringify(room));
    history.replaceState({}, "", `?room=${room.id}`);
  }

  function enterLobby() {
    screen = "lobby";
    renderLobby();
    connectSocket();
  }

  function renderLobby() {
    const players = state.players || [];
    app.innerHTML = `
      <section class="lobby">
        <a class="back-link" href="/" data-leave>← Leave room</a>
        <p class="eyebrow">PRIVATE ROOM · ${esc(modeFor(state.mode || selectedMode).name.toUpperCase())}</p>
        <h2>Waiting for your crew</h2>
        <p class="muted">Send the code below to your friends. The host starts when everyone is ready.</p>
        <div class="lobby-card">
          <div class="room-code">${room.id}<button class="copy-button" id="copy-code" type="button">COPY</button></div>
          <div class="player-list">${players.map(playerTile).join("") || '<p class="muted">Waiting for players…</p>'}</div>
          ${room.host ? `<button class="primary-button wide" id="start-button" ${players.length < 2 ? "disabled" : ""}>Start match <span>→</span></button>` : '<p class="muted">Waiting for the host to start the match…</p>'}
          <p class="error-text" id="lobby-error"></p>
        </div>
      </section>`;
    $("#copy-code").addEventListener("click", async () => {
      await navigator.clipboard?.writeText(String(room.id));
      toast("Room code copied.");
    });
    $("[data-leave]")?.addEventListener("click", (event) => {
      event.preventDefault();
      leaveRoom();
    });
    $("#start-button")?.addEventListener("click", startGame);
  }

  function leaveRoom() {
    if (socket) socket.close();
    socket = null;
    room = null;
    sessionStorage.removeItem(roomKey);
    history.replaceState({}, "", "/");
    renderHome();
  }

  async function startGame() {
    try {
      const data = await api("/api/game/start", {
        method: "POST",
        body: JSON.stringify({ room_id: room.id, user_id: player.id, first_name: player.name, session_token: room.session }),
      });
      state = data.state || {};
      await refreshHand();
      enterGame(true);
    } catch (error) {
      $("#lobby-error").textContent = error.message;
    }
  }

  function enterGame(fromLobby = false) {
    screen = "game";
    renderGame();
    connectSocket();
    if (fromLobby) toast("The match is on. Good luck!");
  }

  function connectSocket() {
    if (!room?.session || socket) return;
    const protocol = location.protocol === "https:" ? "wss:" : "ws:";
    socket = new WebSocket(`${protocol}//${location.host}/ws/game/${room.id}/${player.id}?session_token=${encodeURIComponent(room.session)}`);
    socket.addEventListener("open", () => {
      clearTimeout(reconnectTimer);
      setConnection("Live");
    });
    socket.addEventListener("close", () => {
      socket = null;
      if (screen === "game" || screen === "lobby") {
        setConnection("Reconnecting…", false);
        reconnectTimer = setTimeout(connectSocket, 1400);
      }
    });
    socket.addEventListener("message", async (event) => {
      const message = JSON.parse(event.data);
      if (message.event === "bot_thinking") {
        botThinking = message;
        setConnection(`${message.bot_name} is thinking…`);
        renderCurrent();
        return;
      }
      if (message.event === "bot_turn" || message.state) botThinking = null;
      if (message.state) {
        state = message.state;
        await refreshHand();
        if (screen === "lobby" && state.started) enterGame();
        else renderCurrent();
      }
      if (message.event === "action_rejected") {
        actionBusy = false;
        toast(message.detail || "That move is not available.");
        renderCurrent();
      }
    });
  }

  async function refreshHand() {
    if (!room) return;
    try {
      if (state.started) hand = await api(`/api/game/${room.id}/hand/${player.id}?session_token=${encodeURIComponent(room.session)}`);
    } catch (_) {}
  }

  function renderCurrent() {
    if (screen === "lobby") renderLobby();
    if (screen === "game") renderGame();
  }

  function cardImage(card) {
    if (card.sticker_file_id) return card.sticker_file_id;
    const deck = state.deck_style === "anime" ? "anime_deck" : "classic";
    const playState = card.playable ? "playable" : "not_playable";
    return `/images/${deck}/${playState}/${card.id}.webp`;
  }

  function cardLabel(card) {
    if (!card) return "—";
    if (card.special === "draw_four") return "Wild +4";
    if (card.special === "colorchooser") return "Wild";
    if (card.special === "draw_eight") return "Wild +8";
    if (card.special === "rainbow_monster") return "Rainbow Monster";
    if (card.value === "draw") return `${colors[card.color] || ""} +2`;
    if (card.value === "reverse") return `${colors[card.color] || ""} Reverse`;
    if (card.value === "skip") return `${colors[card.color] || ""} Skip`;
    return `${colors[card.color] || ""} ${card.value || "Wild"}`.trim();
  }

  function opponentMarkup(item) {
    return `<div class="opponent">${avatarMarkup(item)}<span>${esc(item.name)}</span><strong>${item.card_count} cards</strong></div>`;
  }

  function renderGame() {
    const currentName = state.current_player_name || "Waiting";
    const myTurn = Number(state.current_player_id) === Number(player.id);
    const canAct = myTurn && !botThinking && !actionBusy && !matchFinished;
    const winner = matchFinished || state.finished ? "Match complete" : "";
    const modeName = modeFor(state.mode || selectedMode).name;
    const opponents = (state.players || []).filter((item) => Number(item.id) !== Number(player.id));
    const activeColor = state.active_color ? `${colors[state.active_color] || "Wild"} active` : "Table ready";
    app.innerHTML = `
      <section class="game-screen">
        <div class="game-topline">
          <div><p class="eyebrow">${esc(modeName.toUpperCase())}</p><span class="subtle">${esc(state.deck_style || selectedDeck)} deck · Room ${room.id}</span></div>
          <button class="round-button" id="leave-game" type="button" aria-label="Leave game">×</button>
        </div>
        <div class="table">
          <div class="turn-banner"><span>${winner || (myTurn && !botThinking ? "Your turn" : `${esc(currentName)}'s turn`)}</span><strong>${esc(activeColor)}</strong></div>
          <div class="opponents">${opponents.length ? opponents.map(opponentMarkup).join("") : '<span class="subtle">Waiting for opponents…</span>'}</div>
          <div class="board">
            <div class="pile">DRAW<br />PILE</div>
            ${state.last_card ? `<img class="discard-card" alt="${esc(cardLabel(state.last_card))}" src="${esc(state.last_card.image || cardImage(state.last_card))}" />` : '<span class="subtle">Dealing…</span>'}
          </div>
          ${botThinking ? `<div class="bot-thinking">${avatarMarkup({ id: botThinking.bot_id, name: botThinking.bot_name, is_bot: true })}<span><strong>${esc(botThinking.bot_name)}</strong> is thinking…</span><i></i></div>` : ""}
        </div>
        <section class="hand-panel">
          <div class="hand-header"><h3>Your hand</h3><span>${hand.length} cards</span></div>
          <div class="hand">
            ${hand.length ? hand.map((card) => {
              const playable = Boolean(card.playable && canAct && !state.choosing_color);
              return `<button class="card-button ${playable ? "playable" : ""}" data-card="${esc(card.id)}" ${playable ? "" : "disabled"} aria-label="Play ${esc(cardLabel(card))}"><img src="${esc(cardImage(card))}" alt="${esc(cardLabel(card))}" /></button>`;
            }).join("") : '<p class="empty-hand">Your cards will appear here.</p>'}
          </div>
          <div class="action-dock">
            <button class="secondary-button" id="draw-button" ${!canAct || !state.legal_actions?.draw ? "disabled" : ""}>Draw card</button>
            <button class="secondary-button" id="pass-button" ${!canAct || !state.legal_actions?.pass ? "disabled" : ""}>Pass turn</button>
          </div>
          <div class="match-meta"><span>Top card <strong>${esc(cardLabel(state.last_card))}</strong></span><span>Stack <strong>${state.draw_counter ? `+${state.draw_counter}` : "clear"}</strong></span></div>
          <p class="error-text" id="game-error"></p>
        </section>
      </section>`;

    $("#leave-game")?.addEventListener("click", leaveRoom);
    app.querySelectorAll("[data-card]").forEach((button) => button.addEventListener("click", () => performAction("play", { card_id: button.dataset.card })));
    $("#draw-button")?.addEventListener("click", () => performAction("draw"));
    $("#pass-button")?.addEventListener("click", () => performAction("pass"));
    if (state.choosing_color && myTurn && !botThinking) openColorPicker();
  }

  function openColorPicker() {
    colorOptions.innerHTML = (state.available_colors || ["r", "b", "g", "y"]).map((color) => `<button class="color-button" data-color="${color}">${colors[color] || color}</button>`).join("");
    colorModal.classList.remove("hidden");
    colorOptions.querySelectorAll("[data-color]").forEach((button) => button.addEventListener("click", () => {
      colorModal.classList.add("hidden");
      performAction("choose_color", { color: button.dataset.color });
    }));
  }

  async function performAction(action, extra = {}) {
    if (actionBusy || botThinking || !room) return;
    actionBusy = true;
    renderGame();
    try {
      const data = await api("/api/game/action", {
        method: "POST",
        body: JSON.stringify({ room_id: room.id, user_id: player.id, action_type: action, session_token: room.session, ...extra }),
      });
      state = data.state || {};
      if (data.finished) {
        matchFinished = true;
        hand = [];
        state.finished = true;
        toast("You won the match!");
        setConnection("Match complete");
      } else {
        await refreshHand();
      }
    } catch (error) {
      const errorTarget = $("#game-error");
      if (errorTarget) errorTarget.textContent = error.message;
    } finally {
      actionBusy = false;
      renderGame();
    }
  }

  $("#name-form").addEventListener("submit", (event) => {
    event.preventDefault();
    const name = $("#name-input").value.trim().replace(/\s+/g, " ");
    if (!name) return;
    savePlayer({ id: Math.floor(100000000 + Math.random() * 899999999), name: name.slice(0, 24), fromTelegram: false });
    nameModal.classList.add("hidden");
    renderHome();
  });

  $("#rules-button").addEventListener("click", () => toast("Match a color or number. Wild cards change color. Stack +2 cards when enabled, and challenge a Wild +4 when the rules allow it."));

  async function loadModes() {
    try {
      const remoteModes = await api("/api/modes");
      if (Array.isArray(remoteModes) && remoteModes.length) modes = remoteModes;
    } catch (_) {}
  }

  player = getPlayer();
  if (window.Telegram?.WebApp) {
    window.Telegram.WebApp.ready();
    window.Telegram.WebApp.expand();
  }
  if (!player) showNameModal();
  else renderHome();
  loadModes().then(() => { if (screen === "home") renderHome(); });
})();