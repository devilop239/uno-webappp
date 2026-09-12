(() => {
  "use strict";

  const BACKEND_ORIGIN = window.location.port === "8080"
    ? `${window.location.protocol}//${window.location.hostname}:8000`
    : "";
  const backendPath = (path) => `${BACKEND_ORIGIN}${path}`;
  const assetPath = (path) => window.location.port === "8080" ? `/public${path}` : path;
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
    { id: "classic", name: "Classic UNO", description: "108 cards, stacking and Wild +4 challenges.", image: assetPath("/images/Modes_Selection/Classic.jpg") },
    { id: "wild", name: "Wild UNO", description: "Extra wild cards and unpredictable turns.", image: assetPath("/images/Modes_Selection/Wild.jpg") },
    { id: "rainbow", name: "Rainbow UNO", description: "Six colors, Draw 8 and Rainbow cards.", image: assetPath("/images/Modes_Selection/rainbow.jpg") },
    { id: "no_mercy", name: "NO MERCY", description: "Ruthless stacking and elimination rules.", image: assetPath("/images/Modes_Selection/Wild.jpg") },
    { id: "sudden_death", name: "Sudden Death", description: "The first empty hand wins instantly.", image: assetPath("/images/Modes_Selection/sudden death.jpg") },
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

  const imageCache = new Map();

  function preloadImage(url) {
    if (!url || imageCache.has(url)) return;
    const img = new Image();
    img.src = url;
    imageCache.set(url, img);
  }

  function clearImageMemory() {
    imageCache.forEach((img) => {
      img.src = "";
    });
    imageCache.clear();
  }

  function preloadGameAssets() {
    if (spriteManifest) {
      preloadImage(assetPath("/images/sprites/classic.webp"));
      preloadImage(assetPath("/images/sprites/anime_deck.webp"));
      preloadImage(assetPath("/images/sprites/no_mercy.webp"));
    }
    if (Array.isArray(hand)) {
      hand.forEach((card) => {
        if (!card) return;
        preloadImage(cardImage(card));
      });
    }
    if (state.top_card) {
      preloadImage(cardImage(state.top_card));
    }
    defaultModes.forEach((m) => preloadImage(m.image));
  }

  window.addEventListener("beforeunload", clearImageMemory);
  window.addEventListener("pagehide", clearImageMemory);

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
    const response = await fetch(backendPath(path), {
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
          <span class="stat-pill"><strong>5</strong> modes</span>
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

    if (selectedMode !== "classic" && selectedDeck === "anime") {
      selectedDeck = "normal";
    }

    let deckGridHtml = "";
    if (selectedMode === "no_mercy") {
      deckGridHtml = `
        <button type="button" class="deck-choice active" disabled style="opacity:0.95; cursor:default;"><strong>No Mercy deck</strong><small>Exclusive Brutal Cards</small></button>`;
    } else if (selectedMode === "rainbow") {
      deckGridHtml = `
        <button type="button" class="deck-choice active" disabled style="opacity:0.95; cursor:default;"><strong>Rainbow deck</strong><small>Exclusive Spectrum Cards</small></button>`;
    } else if (selectedMode === "classic") {
      deckGridHtml = `
        <button type="button" class="deck-choice ${selectedDeck === "normal" ? "active" : ""}" data-deck="normal"><strong>Normal deck</strong><small>Original UNO artwork</small></button>
        <button type="button" class="deck-choice ${selectedDeck === "anime" ? "active" : ""}" data-deck="anime"><strong>Anime deck</strong><small>Anime card artwork</small></button>`;
    } else {
      deckGridHtml = `
        <button type="button" class="deck-choice active" data-deck="normal"><strong>Normal deck</strong><small>Original UNO artwork</small></button>
        <button type="button" class="deck-choice disabled" disabled style="opacity:0.5; cursor:not-allowed;" title="Anime deck is available in Classic mode only"><strong>Anime deck</strong><small>Classic mode only</small></button>`;
    }

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
          ${deckGridHtml}
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
      if (selectedMode !== "classic" && selectedDeck === "anime") {
        selectedDeck = "normal";
      }
      renderSetup(type);
    });
    app.querySelectorAll("[data-deck]:not([disabled])").forEach((button) => button.addEventListener("click", () => {
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
    const backendUrl = new URL(BACKEND_ORIGIN || window.location.origin);
    const protocol = backendUrl.protocol === "https:" ? "wss:" : "ws:";
    socket = new WebSocket(`${protocol}//${backendUrl.host}/ws/game/${room.id}/${player.id}?session_token=${encodeURIComponent(room.session)}`);
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
      if (message.notice) {
        toast(message.notice);
      }
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
        preloadGameAssets();
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
      if (state.started) {
        hand = await api(`/api/game/${room.id}/hand/${player.id}?session_token=${encodeURIComponent(room.session)}`);
        preloadGameAssets();
      }
    } catch (_) {}
  }

  function renderCurrent() {
    if (screen === "lobby") renderLobby();
    if (screen === "game") renderGame();
  }

  let spriteManifest = null;

  async function loadSpriteManifest() {
    try {
      const res = await fetch(assetPath("/sprites_manifest.json"));
      if (res.ok) {
        spriteManifest = await res.json();
        preloadAllSprites();
      }
    } catch (_) {}
  }

  function preloadAllSprites() {
    if (!spriteManifest) return;
    const urls = new Set();
    Object.values(spriteManifest).forEach((deckMeta) => {
      if (deckMeta.playable_sheet_path) urls.add(assetPath(deckMeta.playable_sheet_path + "?v=240x360_v2"));
      if (deckMeta.non_playable_sheet_path) urls.add(assetPath(deckMeta.non_playable_sheet_path + "?v=240x360_v2"));
      if (deckMeta.sheet_path) urls.add(assetPath(deckMeta.sheet_path + "?v=240x360_v2"));
    });
    urls.forEach((url) => {
      const img = new Image();
      img.src = url;
    });
  }

  function preloadGameAssets() {
    if (state && state.last_card) {
      const img = new Image();
      img.src = cardImage(state.last_card);
    }
    if (hand && hand.length) {
      hand.forEach((card) => {
        const img = new Image();
        img.src = cardImage(card);
      });
    }
  }

  function getSpriteStyle(card) {
    if (!card || !card.id || !spriteManifest) return null;
    let deckKey = "classic";
    if (state.mode === "no_mercy") {
      deckKey = "no_mercy";
    } else if (state.mode === "rainbow") {
      deckKey = "rainbow";
    } else if ((!state.mode || state.mode === "classic") && state.deck_style === "anime") {
      deckKey = "anime_deck";
    }

    let deckMeta = spriteManifest[deckKey];
    if ((!deckMeta || !deckMeta.cards || !deckMeta.cards[card.id]) && spriteManifest.classic?.cards?.[card.id]) {
      deckMeta = spriteManifest.classic;
    }
    if (!deckMeta || !deckMeta.cards || !deckMeta.cards[card.id]) return null;

    const pos = deckMeta.cards[card.id];
    const cols = deckMeta.cols || 10;
    const rows = deckMeta.rows || 6;
    const xPct = cols > 1 ? (pos.col / (cols - 1)) * 100 : 0;
    const yPct = rows > 1 ? (pos.row / (rows - 1)) * 100 : 0;
    const isPlayable = card.playable !== false;
    const sheetPath = isPlayable
      ? (deckMeta.playable_sheet_path || deckMeta.sheet_path)
      : (deckMeta.non_playable_sheet_path || deckMeta.sheet_path);
    const sheetUrl = assetPath(sheetPath + "?v=240x360_v2");
    return `background-image: url('${sheetUrl}'); background-position: ${xPct.toFixed(6)}% ${yPct.toFixed(6)}%; background-size: ${cols * 100}% ${rows * 100}%;`;
  }

  function cardImage(card) {
    if (card && card.image) {
      return assetPath(card.image);
    }
    const deck = ((!state.mode || state.mode === "classic") && state.deck_style === "anime") ? "anime_deck" : "classic";
    const playState = deck === "classic"
      ? (card.playable ? "playble" : "non_playble")
      : (card.playable ? "playable" : "not_playable");
    return assetPath(`/images/${deck}/${playState}/${card.id}.webp`);
  }

  function cardLabel(card) {
    if (!card) return "—";
    if (card.special === "w_wild") return "Wild No Mercy";
    if (card.special === "w_draw4") return "Wild +4";
    if (card.special === "w_draw6") return "Wild +6";
    if (card.special === "w_draw10") return "Wild +10";
    if (card.special === "w_draw4_reverse") return "Wild +4 Reverse";
    if (card.special === "w_skip_all") return "Wild Skip All";
    if (card.special === "w_roulette") return "Wild Roulette";
    if (card.special === "draw_four") return "Wild +4";
    if (card.special === "colorchooser") return "Wild";
    if (card.special === "draw_eight") return "Wild +8";
    if (card.special === "rainbow_monster") return "Rainbow Monster";
    if (card.special === "rainbow_wild") return "Rainbow Wild";
    if (card.special === "rainbow_lightning") return "Rainbow Lightning";
    if (card.value === "discard_all") return `${colors[card.color] || ""} Discard All`.trim();
    if (card.value === "draw2" || card.value === "draw") return `${colors[card.color] || ""} +2`.trim();
    if (card.value === "reverse") return `${colors[card.color] || ""} Reverse`.trim();
    if (card.value === "skip") return `${colors[card.color] || ""} Skip`.trim();
    if (card.value === "7" && state.mode === "no_mercy") return `${colors[card.color] || ""} 7 (Swap)`.trim();
    return `${colors[card.color] || ""} ${card.value || "Wild"}`.trim();
  }

  function opponentMarkup(item) {
    const isEliminated = Boolean(item.is_eliminated);
    const cardStatus = isEliminated ? "ELIMINATED 💀" : `${item.card_count} cards`;
    return `<div class="opponent ${isEliminated ? "eliminated" : ""}">${avatarMarkup(item)}<span>${esc(item.name)}</span><strong>${cardStatus}</strong></div>`;
  }

  function renderGame() {
    const currentName = state.current_player_name || "Waiting";
    const myTurn = Number(state.current_player_id) === Number(player.id);
    const isBlocked = Boolean(state.mercy_pending_swap || state.mercy_pending_roulette || state.choosing_color);
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
            <img class="pile" src="${assetPath("/images/card_back.png")}" alt="Draw pile" />
            ${state.last_card ? (() => {
              const spriteStyle = getSpriteStyle(state.last_card);
              if (spriteStyle) {
                return `<div class="discard-card sprite-card" style="${spriteStyle}" aria-label="${esc(cardLabel(state.last_card))}"></div>`;
              }
              return `<img class="discard-card" alt="${esc(cardLabel(state.last_card))}" src="${esc(cardImage(state.last_card))}" />`;
            })() : '<span class="subtle">Dealing…</span>'}
          </div>
          ${botThinking ? `<div class="bot-thinking">${avatarMarkup({ id: botThinking.bot_id, name: botThinking.bot_name, is_bot: true })}<span><strong>${esc(botThinking.bot_name)}</strong> is thinking…</span><i></i></div>` : ""}
        </div>
        <section class="hand-panel">
          <div class="hand-header"><h3>Your hand</h3><span>${hand.length} cards</span></div>
          <div class="hand">
            ${hand.length ? hand.map((card) => {
              const playable = Boolean(card.playable && canAct && !isBlocked);
              const spriteStyle = getSpriteStyle(card);
              if (spriteStyle) {
                return `<button class="card-button sprite-card ${playable ? "playable" : ""}" style="${spriteStyle}" data-card="${esc(card.id)}" ${playable ? "" : "disabled"} aria-label="Play ${esc(cardLabel(card))}"></button>`;
              }
              return `<button class="card-button ${playable ? "playable" : ""}" data-card="${esc(card.id)}" ${playable ? "" : "disabled"} aria-label="Play ${esc(cardLabel(card))}"><img src="${esc(cardImage(card))}" alt="${esc(cardLabel(card))}" loading="eager" /></button>`;
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
    app.querySelectorAll("[data-card]").forEach((button) => button.addEventListener("click", () => performAction("play", { card_id: button.dataset.card }, button)));
    $("#draw-button")?.addEventListener("click", () => performAction("draw"));
    $("#pass-button")?.addEventListener("click", () => performAction("pass"));
    if (myTurn && !botThinking) {
      if (state.choosing_color || state.mercy_pending_roulette === "color") openColorPicker();
      else if (state.mercy_pending_swap) openTargetPicker("Swap Hand (7 Card)", "Choose a player to swap your entire hand with:", state.swap_targets || [], "choose_swap_target");
      else if (state.mercy_pending_roulette === "target") openTargetPicker("Wild Roulette Target", "Choose an opponent to draw until they hit the selected color:", state.roulette_targets || [], "choose_roulette_target");
    }
  }

  function openColorPicker() {
    colorOptions.innerHTML = (state.available_colors || ["r", "b", "g", "y"]).map((color) => `<button class="color-button" data-color="${color}">${colors[color] || color}</button>`).join("");
    colorModal.classList.remove("hidden");
    colorOptions.querySelectorAll("[data-color]").forEach((button) => button.addEventListener("click", () => {
      colorModal.classList.add("hidden");
      performAction("choose_color", { color: button.dataset.color });
    }));
  }

  function openTargetPicker(title, desc, targets, actionName) {
    const targetModal = document.querySelector("#target-modal");
    const targetOptions = document.querySelector("#target-options");
    const targetTitle = document.querySelector("#target-title");
    const targetDesc = document.querySelector("#target-desc");
    if (!targetModal || !targetOptions) return;

    targetTitle.textContent = title;
    targetDesc.textContent = desc;
    targetOptions.innerHTML = targets.map((t) =>
      `<button type="button" class="target-button" data-target="${t.id}"><span>${esc(t.name)}</span><small>${t.card_count} cards</small></button>`
    ).join("") || '<p class="muted">No targets available</p>';
    targetModal.classList.remove("hidden");
    targetOptions.querySelectorAll("[data-target]").forEach((button) => button.addEventListener("click", () => {
      targetModal.classList.add("hidden");
      performAction(actionName, { target_id: Number(button.dataset.target) });
    }));
  }

  async function performAction(action, extra = {}, targetElement = null) {
    if (actionBusy || botThinking || !room) return;
    actionBusy = true;
    if (targetElement && action === "play") {
      targetElement.classList.add("optimistic-fly");
    } else {
      renderGame();
    }
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
      if (targetElement) targetElement.classList.remove("optimistic-fly");
      const errorTarget = $("#game-error");
      if (errorTarget) errorTarget.textContent = error.message;
    } finally {
      actionBusy = false;
      renderCurrent();
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
      if (Array.isArray(remoteModes) && remoteModes.length) {
        modes = remoteModes.map((mode) => ({
          ...mode,
          image: assetPath(mode.image || ""),
        }));
      }
    } catch (_) {}
  }

  player = getPlayer();
  if (window.Telegram?.WebApp) {
    window.Telegram.WebApp.ready();
    window.Telegram.WebApp.expand();
  }
  if (!player) showNameModal();
  else renderHome();
  loadSpriteManifest();
  loadModes().then(() => { if (screen === "home") renderHome(); });
})();