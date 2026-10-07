// Telegram WebApp Integration
const tg = window.Telegram?.WebApp;
if (tg) {
  try {
    tg.ready();
    tg.expand();
    if (tg.setHeaderColor) tg.setHeaderColor("#0e1710");
    if (tg.setBackgroundColor) tg.setBackgroundColor("#0e1710");
  } catch (e) {
    console.log("Telegram WebApp init:", e);
  }
}

// State
let appData = {
  status: null,
  quests: [],
  vet: [],
  expenses: null
};

// Current Telegram user info (or fallback)
let currentUserName = "Пользователь";
if (tg?.initDataUnsafe?.user?.first_name) {
  currentUserName = tg.initDataUnsafe.user.first_name;
  if (tg.initDataUnsafe.user.last_name) {
    currentUserName += " " + tg.initDataUnsafe.user.last_name;
  }
} else if (tg?.initDataUnsafe?.user?.username) {
  currentUserName = "@" + tg.initDataUnsafe.user.username;
}

const currentUser = {
  id: tg?.initDataUnsafe?.user?.id || 1,
  name: currentUserName
};

// Все API-запросы несут подписанные Telegram initData. Сервер сам извлекает
// пользователя из подписи и не доверяет user_id/name из браузера.
function apiFetch(url, options = {}) {
  const headers = new Headers(options.headers || {});
  headers.set("X-Telegram-Init-Data", tg?.initData || "");
  return window.fetch(url, { ...options, headers });
}

// Helper: Haptic feedback
function triggerHaptic(type = "light") {
  try {
    if (tg?.HapticFeedback) {
      if (type === "success") tg.HapticFeedback.notificationOccurred("success");
      else if (type === "warning") tg.HapticFeedback.notificationOccurred("warning");
      else tg.HapticFeedback.impactOccurred("medium");
    }
  } catch (e) {}
}

// Helper: Toast notification
function showToast(message) {
  const toast = document.getElementById("toast-notify");
  if (!toast) return;
  toast.innerText = message;
  toast.classList.add("show");
  setTimeout(() => {
    toast.classList.remove("show");
  }, 2600);
}

// Helper: Modals
function openModal(id) {
  triggerHaptic("light");
  const m = document.getElementById(id);
  if (m) m.classList.add("active");
}

function closeModal(id) {
  const m = document.getElementById(id);
  if (m) m.classList.remove("active");
}

document.querySelectorAll("[data-close]").forEach(btn => {
  btn.addEventListener("click", () => {
    closeModal(btn.dataset.close);
  });
});

document.querySelectorAll(".modal-overlay").forEach(overlay => {
  overlay.addEventListener("click", (e) => {
    if (e.target === overlay) {
      overlay.classList.remove("active");
    }
  });
});

// ================= ЗВУКОВОЙ ДВИЖОК (WEB AUDIO API) =================
const SoundEngine = {
  ctx: null,
  enabled: true,

  init() {
    if (!this.ctx) {
      const AudioCtx = window.AudioContext || window.webkitAudioContext;
      if (AudioCtx) this.ctx = new AudioCtx();
    }
    if (this.ctx && this.ctx.state === "suspended") {
      this.ctx.resume();
    }
  },

  playPurr() {
    if (!this.enabled) return;
    this.init();
    if (!this.ctx) return;
    try {
      const osc = this.ctx.createOscillator();
      const gain = this.ctx.createGain();
      const mod = this.ctx.createOscillator();
      const modGain = this.ctx.createGain();

      osc.type = "sine";
      osc.frequency.setValueAtTime(65, this.ctx.currentTime);

      mod.type = "sine";
      mod.frequency.setValueAtTime(28, this.ctx.currentTime);
      modGain.gain.setValueAtTime(15, this.ctx.currentTime);
      mod.connect(osc.frequency);

      gain.gain.setValueAtTime(0, this.ctx.currentTime);
      gain.gain.linearRampToValueAtTime(0.18, this.ctx.currentTime + 0.1);
      gain.gain.exponentialRampToValueAtTime(0.01, this.ctx.currentTime + 0.8);

      osc.connect(gain);
      gain.connect(this.ctx.destination);

      mod.start();
      osc.start();
      mod.stop(this.ctx.currentTime + 0.8);
      osc.stop(this.ctx.currentTime + 0.8);
    } catch (e) {}
  },

  playFeed() {
    if (!this.enabled) return;
    this.init();
    if (!this.ctx) return;
    try {
      [0, 0.1, 0.22].forEach((delay) => {
        const osc = this.ctx.createOscillator();
        const gain = this.ctx.createGain();
        osc.type = "triangle";
        osc.frequency.setValueAtTime(320 - delay * 80, this.ctx.currentTime + delay);
        osc.frequency.exponentialRampToValueAtTime(80, this.ctx.currentTime + delay + 0.08);

        gain.gain.setValueAtTime(0.14, this.ctx.currentTime + delay);
        gain.gain.exponentialRampToValueAtTime(0.01, this.ctx.currentTime + delay + 0.08);

        osc.connect(gain);
        gain.connect(this.ctx.destination);
        osc.start(this.ctx.currentTime + delay);
        osc.stop(this.ctx.currentTime + delay + 0.09);
      });
    } catch (e) {}
  },

  playWater() {
    if (!this.enabled) return;
    this.init();
    if (!this.ctx) return;
    try {
      const osc = this.ctx.createOscillator();
      const gain = this.ctx.createGain();
      osc.type = "sine";
      osc.frequency.setValueAtTime(450, this.ctx.currentTime);
      osc.frequency.exponentialRampToValueAtTime(850, this.ctx.currentTime + 0.15);

      gain.gain.setValueAtTime(0.2, this.ctx.currentTime);
      gain.gain.exponentialRampToValueAtTime(0.01, this.ctx.currentTime + 0.2);

      osc.connect(gain);
      gain.connect(this.ctx.destination);
      osc.start();
      osc.stop(this.ctx.currentTime + 0.22);
    } catch (e) {}
  },

  playLitter() {
    if (!this.enabled) return;
    this.init();
    if (!this.ctx) return;
    try {
      [523.25, 659.25].forEach((freq, idx) => {
        const osc = this.ctx.createOscillator();
        const gain = this.ctx.createGain();
        osc.type = "sine";
        osc.frequency.setValueAtTime(freq, this.ctx.currentTime + idx * 0.1);
        gain.gain.setValueAtTime(0.12, this.ctx.currentTime + idx * 0.1);
        gain.gain.exponentialRampToValueAtTime(0.01, this.ctx.currentTime + idx * 0.1 + 0.3);
        osc.connect(gain);
        gain.connect(this.ctx.destination);
        osc.start(this.ctx.currentTime + idx * 0.1);
        osc.stop(this.ctx.currentTime + idx * 0.1 + 0.35);
      });
    } catch (e) {}
  },

  playPlay() {
    if (!this.enabled) return;
    this.init();
    if (!this.ctx) return;
    try {
      [659.25, 880].forEach((freq, idx) => {
        const osc = this.ctx.createOscillator();
        const gain = this.ctx.createGain();
        osc.type = "sine";
        osc.frequency.setValueAtTime(freq, this.ctx.currentTime + idx * 0.08);
        gain.gain.setValueAtTime(0.14, this.ctx.currentTime + idx * 0.08);
        gain.gain.exponentialRampToValueAtTime(0.01, this.ctx.currentTime + idx * 0.08 + 0.25);
        osc.connect(gain);
        gain.connect(this.ctx.destination);
        osc.start(this.ctx.currentTime + idx * 0.08);
        osc.stop(this.ctx.currentTime + idx * 0.08 + 0.28);
      });
    } catch (e) {}
  },

  toggleSound() {
    this.enabled = !this.enabled;
    const btn = document.getElementById("btn-sound-toggle");
    if (btn) {
      btn.innerText = this.enabled ? "🔊" : "🔇";
      btn.classList.toggle("muted", !this.enabled);
    }
    showToast(this.enabled ? "Звуки включены 🔊" : "Звуки выключены 🔇");
  }
};

document.getElementById("btn-sound-toggle")?.addEventListener("click", () => {
  SoundEngine.toggleSound();
});

// Floating Particle Generator
function createFloatingParticle(x, y, text = "❤️") {
  const p = document.createElement("div");
  p.className = "floating-heart";
  p.innerText = text;
  p.style.left = `${x}px`;
  p.style.top = `${y}px`;
  const tx = (Math.random() - 0.5) * 60;
  const rot = (Math.random() - 0.5) * 45;
  p.style.setProperty("--tx", `${tx}px`);
  p.style.setProperty("--rot", `${rot}deg`);
  document.body.appendChild(p);
  setTimeout(() => p.remove(), 1200);
}

// Lightbox
function openLightbox(imgSrc, caption) {
  const modal = document.getElementById("modal-lightbox");
  const img = document.getElementById("lightbox-img");
  const cap = document.getElementById("lightbox-caption");
  if (img) img.src = imgSrc;
  if (cap) cap.innerText = caption || "";
  if (modal) modal.classList.add("active");
}

function closeLightbox() {
  const modal = document.getElementById("modal-lightbox");
  if (modal) modal.classList.remove("active");
}

document.querySelector(".btn-close-lightbox")?.addEventListener("click", closeLightbox);

// Tab Switching
document.querySelectorAll(".nav-btn").forEach(btn => {
  btn.addEventListener("click", () => {
    triggerHaptic("light");
    document.querySelectorAll(".nav-btn").forEach(b => b.classList.remove("active"));
    document.querySelectorAll(".tab-content").forEach(c => c.classList.remove("active"));
    
    btn.classList.add("active");
    const tabId = btn.dataset.tab;
    const content = document.getElementById(tabId);
    if (content) content.classList.add("active");

    // Load data for selected tab
    if (tabId === "tab-quests") loadQuests();
    else if (tabId === "tab-gallery") loadGallery();
    else if (tabId === "tab-vet") { loadVet(); loadWeights(); }
    else if (tabId === "tab-expenses") loadExpenses();
  });
});

// ================= 1. СТАТУС И ТАМАГОЧИ =================

async function loadStatus() {
  try {
    const res = await apiFetch("/api/status");
    if (!res.ok) throw new Error("Status fetch error");
    const data = await res.json();
    appData.status = data;
    renderStatus(data);
  } catch (err) {
    console.error("loadStatus error:", err);
  }
}

function renderStatus(data) {
  if (!data) return;
  const cats = data.cats || [];
  
  // Header: Avatars & Names
  const cat1Emoji = document.getElementById("cat1-emoji");
  const cat2Emoji = document.getElementById("cat2-emoji");
  const catsNames = document.getElementById("cats-names");
  
  if (cats.length >= 2) {
    if (cat1Emoji) cat1Emoji.innerText = cats[0].emoji || "🐈‍⬛";
    if (cat2Emoji) cat2Emoji.innerText = cats[1].emoji || "🐈‍⬛";
    if (catsNames) catsNames.innerText = `${cats[0].name} & ${cats[1].name}`;
  } else if (cats.length === 1) {
    if (cat1Emoji) cat1Emoji.innerText = cats[0].emoji || "🐈‍⬛";
    if (catsNames) catsNames.innerText = cats[0].name;
  }

  // Last fed subtitle
  const lastFedInfo = document.getElementById("last-fed-info");
  if (lastFedInfo) {
    if (data.last_feeding) {
      const hours = data.hours_since_feed;
      const fedTime = data.last_feeding.fed_at ? data.last_feeding.fed_at.substring(11, 16) : "";
      lastFedInfo.innerText = `Кормление: ${fedTime} (${hours} ч. назад)`;
    } else {
      lastFedInfo.innerText = "Котики ждут первую трапезу 🥣";
    }
  }

  // Streak
  const streakDays = data.streak?.current_streak || 0;
  const streakEl = document.getElementById("streak-days");
  if (streakEl) streakEl.innerText = streakDays;

  // Tamagotchi Mood & Satiety
  const avatarEl = document.getElementById("cat-mood-avatar");
  if (avatarEl) avatarEl.innerText = data.mood_emoji || "🥰";

  const moodTitleEl = document.getElementById("mood-title");
  if (moodTitleEl) moodTitleEl.innerText = data.mood_title || "Счастливы и мурчат";

  const moodDescEl = document.getElementById("mood-desc");
  if (moodDescEl) moodDescEl.innerText = data.mood_desc || "Оба котика сыты и довольны!";
  
  const satiety = data.satiety_percent ?? 100;
  const satietyVal = document.getElementById("satiety-val");
  if (satietyVal) satietyVal.innerText = `${satiety}%`;

  const satietyBar = document.getElementById("satiety-bar");
  if (satietyBar) satietyBar.style.width = `${satiety}%`;

  // Vital stats: Water
  const waterPct = data.water_percent ?? 100;
  const waterBar = document.getElementById("water-bar");
  if (waterBar) waterBar.style.width = `${waterPct}%`;

  const waterText = document.getElementById("water-text");
  const waterHint = document.getElementById("water-hint");
  if (waterPct >= 70) {
    if (waterText) waterText.innerText = "Свежая 💧";
    if (waterHint) waterHint.innerText = "Нажмите, если долили";
  } else {
    if (waterText) waterText.innerText = "Нужно налить ⏳";
    if (waterHint) waterHint.innerText = "Нажмите, чтобы налить 💧";
  }

  // Vital stats: Litter
  const litterPct = data.litter_percent ?? 100;
  const litterBar = document.getElementById("litter-bar");
  if (litterBar) litterBar.style.width = `${litterPct}%`;

  const litterText = document.getElementById("litter-text");
  const litterHint = document.getElementById("litter-hint");
  if (litterPct >= 70) {
    if (litterText) litterText.innerText = "Чистый ✨";
    if (litterHint) litterHint.innerText = "Нажмите, если убрали";
  } else {
    if (litterText) litterText.innerText = "Почистить 🚽";
    if (litterHint) litterHint.innerText = "Нажмите, чтобы убрать ✨";
  }

  // Vital stats: Play
  const playPct = data.play_percent ?? 80;
  const playBar = document.getElementById("play-bar");
  if (playBar) playBar.style.width = `${playPct}%`;

  const playText = document.getElementById("play-text");
  const playHint = document.getElementById("play-hint");
  if (playPct >= 80) {
    if (playText) playText.innerText = "Поиграли 🎾";
    if (playHint) playHint.innerText = "Нажмите, если поиграли";
  } else {
    if (playText) playText.innerText = "Ждут лазерку 🐾";
    if (playHint) playHint.innerText = "Нажмите, чтобы играть 🐾";
  }

  // Cat profile cards (clickable to edit)
  const container = document.getElementById("cats-list-container");
  if (container) {
    container.innerHTML = "";
    cats.forEach(c => {
      const card = document.createElement("div");
      card.className = "cat-profile-card";
      card.title = `Нажмите, чтобы изменить анкету ${c.name}`;
      card.addEventListener("click", () => openCatEditModal(c));

      const weightStr = (c.weight !== null && c.weight !== undefined && c.weight > 0) ? `⚖️ ${c.weight} кг` : "⚖️ Вес неизвестен";
      const breedStr = c.breed || "Черный котик";

      card.innerHTML = `
        <span class="cat-card-edit-btn" title="Редактировать">✏️</span>
        <div class="cat-profile-top">
          <span class="cat-avatar-icon">${c.emoji || "🐈‍⬛"}</span>
          <div>
            <div class="cat-name">${c.name}</div>
            <div class="cat-meta">${breedStr}</div>
          </div>
        </div>
        <div class="cat-weight-tag">${weightStr}</div>
      `;
      container.appendChild(card);
    });
  }

  // Populate cats select in vet modal
  const vetSelect = document.getElementById("vet-cat-select");
  if (vetSelect) {
    vetSelect.innerHTML = "";
    cats.forEach(c => {
      const opt = document.createElement("option");
      opt.value = c.id;
      opt.innerText = `${c.emoji || "🐱"} ${c.name}`;
      vetSelect.appendChild(opt);
    });
  }
}

// Quick Feed Action
document.getElementById("btn-quick-feed")?.addEventListener("click", async () => {
  SoundEngine.playFeed();
  triggerHaptic("success");
  const btn = document.getElementById("btn-quick-feed");
  const btnText = document.getElementById("feed-btn-text");
  if (btn) btn.disabled = true;
  if (btnText) btnText.innerText = "Накладываем корм... 🥣";

  try {
    const res = await apiFetch("/api/feed", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({
        user_id: currentUser.id,
        user_name: currentUser.name
      })
    });
    const result = await res.json();
    if (result.ok) {
      showToast("Котики сыты и довольно мурчат! 🐱✨");
      const face = document.getElementById("cat-mood-avatar");
      if (face) {
        face.innerText = "🥰";
        face.style.transform = "scale(1.25) translateY(-8px)";
        setTimeout(() => { face.style.transform = ""; }, 900);
      }
      loadCatThought("feed");
      if (result.status) {
        appData.status = result.status;
        renderStatus(result.status);
      } else {
        await loadStatus();
      }
    } else {
      showToast(result.msg || "Ошибка кормления");
    }
  } catch (err) {
    console.error("Feed error:", err);
    showToast("Ошибка сети");
  } finally {
    if (btn) btn.disabled = false;
    if (btnText) btnText.innerText = "Покормить котиков в 1 клик";
  }
});

// Interactive Petting (Ласка котиков)
document.getElementById("pet-interactive-area")?.addEventListener("click", (e) => {
  SoundEngine.playPurr();
  triggerHaptic("medium");
  const rect = e.currentTarget.getBoundingClientRect();
  const x = e.clientX || (rect.left + rect.width / 2);
  const y = e.clientY || (rect.top + rect.height / 2);
  const emojis = ["❤️", "🐾", "🥰", "✨", "😻"];
  const emoji = emojis[Math.floor(Math.random() * emojis.length)];
  createFloatingParticle(x - 12, y - 20, emoji);

  const face = document.getElementById("cat-mood-avatar");
  if (face) {
    face.innerText = "😻";
    face.style.transform = "scale(1.2) translateY(-6px)";
    setTimeout(() => {
      face.style.transform = "";
      if (appData.status) renderMood(appData.status.satiety_percent, appData.status.is_sleeping);
    }, 1400);
  }
  loadCatThought("pet");
});

// Interactive Care Actions: Water, Litter, Play
async function handleCareAction(type) {
  triggerHaptic("success");

  // Optimistic UI updates & Sound
  if (type === "water") {
    SoundEngine.playWater();
    const bar = document.getElementById("water-bar");
    if (bar) bar.style.width = "100%";
    const txt = document.getElementById("water-text");
    if (txt) txt.innerText = "Свежая 💧";
    const hint = document.getElementById("water-hint");
    if (hint) hint.innerText = "Обновлено ✨";
    loadCatThought("water");
  } else if (type === "litter") {
    SoundEngine.playLitter();
    const bar = document.getElementById("litter-bar");
    if (bar) bar.style.width = "100%";
    const txt = document.getElementById("litter-text");
    if (txt) txt.innerText = "Чистый ✨";
    const hint = document.getElementById("litter-hint");
    if (hint) hint.innerText = "Обновлено ✨";
    loadCatThought("litter");
  } else if (type === "play") {
    SoundEngine.playPlay();
    const bar = document.getElementById("play-bar");
    if (bar) bar.style.width = "100%";
    const txt = document.getElementById("play-text");
    if (txt) txt.innerText = "Поиграли 🎾";
    const hint = document.getElementById("play-hint");
    if (hint) hint.innerText = "Обновлено ✨";
    loadCatThought("play");
  }

  // Micro bounce on face avatar
  const face = document.getElementById("cat-mood-avatar");
  if (face) {
    face.style.transform = "scale(1.2) translateY(-6px)";
    setTimeout(() => { face.style.transform = ""; }, 800);
  }

  try {
    const res = await apiFetch("/api/care", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({
        type: type,
        user_id: currentUser.id,
        user_name: currentUser.name
      })
    });
    const result = await res.json();
    if (result.ok) {
      showToast(result.msg || "Действие сохранено! ✨");
      if (result.status) {
        appData.status = result.status;
        renderStatus(result.status);
      } else {
        await loadStatus();
      }
    } else {
      showToast(result.msg || "Ошибка сохранения");
      await loadStatus();
    }
  } catch (err) {
    console.error("Care action error:", err);
    showToast("Ошибка сети");
    await loadStatus();
  }
}

// Bind Care Buttons
document.getElementById("btn-care-water")?.addEventListener("click", () => handleCareAction("water"));
document.getElementById("btn-care-litter")?.addEventListener("click", () => handleCareAction("litter"));
document.getElementById("btn-care-play")?.addEventListener("click", () => handleCareAction("play"));

// ================= 2. РЕДАКТИРОВАНИЕ КОТИКА ПО КЛИКУ =================

function openCatEditModal(cat) {
  triggerHaptic("light");
  document.getElementById("cat-edit-modal-title").innerText = `Анкета: ${cat.name}`;
  document.getElementById("edit-cat-id").value = cat.id;
  document.getElementById("edit-cat-name").value = cat.name || "";
  document.getElementById("edit-cat-breed").value = cat.breed || "";
  document.getElementById("edit-cat-weight").value = (cat.weight && cat.weight > 0) ? cat.weight : "";
  
  const currentEmoji = cat.emoji || "🐈‍⬛";
  document.getElementById("edit-cat-emoji").value = currentEmoji;

  // Highlight emoji
  document.querySelectorAll(".emoji-btn").forEach(btn => {
    if (btn.dataset.emoji === currentEmoji) {
      btn.classList.add("selected");
    } else {
      btn.classList.remove("selected");
    }
  });

  openModal("modal-cat-edit");
}

// Emoji selection clicks
document.querySelectorAll(".emoji-btn").forEach(btn => {
  btn.addEventListener("click", () => {
    triggerHaptic("light");
    document.querySelectorAll(".emoji-btn").forEach(b => b.classList.remove("selected"));
    btn.classList.add("selected");
    const emoji = btn.dataset.emoji;
    document.getElementById("edit-cat-emoji").value = emoji;
  });
});

// Submit Cat Edit Form
document.getElementById("form-edit-cat")?.addEventListener("submit", async (e) => {
  e.preventDefault();
  triggerHaptic("success");

  const catId = document.getElementById("edit-cat-id").value;
  const name = document.getElementById("edit-cat-name").value.trim();
  const breed = document.getElementById("edit-cat-breed").value.trim();
  const weightVal = document.getElementById("edit-cat-weight").value.trim();
  const emoji = document.getElementById("edit-cat-emoji").value.trim();

  const saveBtn = document.getElementById("btn-save-cat");
  if (saveBtn) {
    saveBtn.disabled = true;
    saveBtn.innerText = "Сохраняем...";
  }

  try {
    const res = await apiFetch("/api/cats/update", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({
        id: catId,
        name: name,
        breed: breed,
        weight: weightVal ? parseFloat(weightVal) : null,
        emoji: emoji,
        user_id: currentUser.id,
        user_name: currentUser.name
      })
    });

    const result = await res.json();
    if (result.ok) {
      closeModal("modal-cat-edit");
      showToast(result.msg || `Котик ${name} успешно обновлен! ✨`);
      if (result.status) {
        appData.status = result.status;
        renderStatus(result.status);
      } else {
        await loadStatus();
      }
    } else {
      showToast(result.msg || "Ошибка сохранения");
    }
  } catch (err) {
    console.error("Save cat error:", err);
    showToast("Ошибка сети при сохранении");
  } finally {
    if (saveBtn) {
      saveBtn.disabled = false;
      saveBtn.innerText = "💾 Сохранить";
    }
  }
});

// ================= 3. КВЕСТЫ =================

async function loadQuests() {
  const container = document.getElementById("quests-container");
  if (!container) return;
  container.innerHTML = '<div class="loading-spinner">Загрузка квестов...</div>';
  try {
    const res = await apiFetch("/api/quests");
    const quests = await res.json();
    appData.quests = quests;
    renderQuests(quests);
  } catch (err) {
    container.innerHTML = '<div class="loading-spinner">Ошибка загрузки квестов</div>';
  }
}

function renderQuests(quests) {
  const container = document.getElementById("quests-container");
  if (!container) return;
  container.innerHTML = "";

  if (!quests || quests.length === 0) {
    container.innerHTML = '<div class="loading-spinner">Нет активных квестов на сегодня</div>';
    return;
  }

  quests.forEach(q => {
    const item = document.createElement("div");
    item.className = "quest-item";

    let statusClass = `status-${q.status}`;
    let statusText = "Свободен";
    let actionsHtml = "";

    if (q.status === "available") {
      statusText = "🟢 Доступен";
      actionsHtml = `
        <button class="btn-quest btn-quest-take" onclick="handleQuestAction('take', '${q.id}')">✋ Взять</button>
        <button class="btn-quest btn-quest-done" onclick="handleQuestAction('done', '${q.id}')">⚡ Выполнить</button>
      `;
    } else if (q.status === "taken") {
      if (q.taken_by_id === currentUser.id) {
        statusText = `🟡 В работе у ВАС`;
        actionsHtml = `
          <button class="btn-quest btn-quest-done" onclick="handleQuestAction('done', '${q.id}')">✅ Сделано</button>
          <button class="btn-quest btn-quest-drop" onclick="handleQuestAction('drop', '${q.id}')">↩️ Отказаться</button>
        `;
      } else {
        statusText = `🟡 Делает ${q.taken_by_name || 'партнер'}`;
      }
    } else if (q.status === "completed") {
      statusText = `✅ Выполнил(а) ${q.completed_by_name || ''}`;
    } else if (q.status === "locked") {
      statusText = "⏳ Закрыт по времени";
    }

    item.innerHTML = `
      <div class="quest-item-header">
        <div class="quest-title">${q.title}</div>
        <div class="quest-status-badge ${statusClass}">${statusText}</div>
      </div>
      ${actionsHtml ? `<div class="quest-actions-row">${actionsHtml}</div>` : ''}
    `;
    container.appendChild(item);
  });
}

async function handleQuestAction(action, qid) {
  triggerHaptic("light");
  try {
    const res = await apiFetch("/api/quests/action", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({
        action: action,
        quest_id: qid,
        user_id: currentUser.id,
        user_name: currentUser.name
      })
    });
    const result = await res.json();
    if (result.ok) {
      showToast(result.msg);
      loadQuests();
      loadStatus();
    } else {
      showToast(result.msg || "Ошибка выполнения");
    }
  } catch (err) {
    showToast("Ошибка сети");
  }
}

document.getElementById("btn-refresh-quests")?.addEventListener("click", () => {
  triggerHaptic("light");
  loadQuests();
});

// ================= 4. ВЕТ-ПАСПОРТ =================

async function loadVet() {
  const container = document.getElementById("vet-records-container");
  if (!container) return;
  container.innerHTML = '<div class="loading-spinner">Загрузка записей...</div>';
  try {
    const res = await apiFetch("/api/vet");
    const data = await res.json();
    appData.vet = data;
    renderVet(data);
  } catch (err) {
    container.innerHTML = '<div class="loading-spinner">Ошибка загрузки вет-паспорта</div>';
  }
}

function renderVet(data) {
  const recordsContainer = document.getElementById("vet-records-container");
  const alertsContainer = document.getElementById("vet-alerts-container");
  if (!recordsContainer || !alertsContainer) return;

  // Render upcoming alerts
  alertsContainer.innerHTML = "";
  const upcoming = data.upcoming || [];
  if (upcoming.length > 0) {
    upcoming.forEach(u => {
      const alert = document.createElement("div");
      alert.className = "vet-alert-card";
      alert.innerHTML = `
        <div class="alert-icon">⏰</div>
        <div>
          <div class="alert-title">${u.title} (${u.cat_name})</div>
          <div class="alert-date">Срок: ${u.next_due_date}</div>
        </div>
      `;
      alertsContainer.appendChild(alert);
    });
  }

  // Render history records
  recordsContainer.innerHTML = "";
  const records = data.records || [];
  if (records.length === 0) {
    recordsContainer.innerHTML = '<div class="loading-spinner">Записей пока нет</div>';
    return;
  }

  records.forEach(r => {
    const item = document.createElement("div");
    item.className = "vet-record-item";
    const typeEmojis = {
      vaccine: "💉",
      parasite: "💊",
      visit: "🏥",
      weight: "⚖️",
      other: "📝"
    };
    const icon = typeEmojis[r.record_type] || "📝";
    item.innerHTML = `
      <div class="record-icon">${icon}</div>
      <div class="record-content">
        <div class="record-title">${r.title} <span class="record-cat-tag">${r.cat_name}</span></div>
        <div class="record-desc">${r.description || ""}</div>
        <div class="record-meta">${r.record_date} ${r.next_due_date ? `| След: ${r.next_due_date}` : ''}</div>
      </div>
    `;
    recordsContainer.appendChild(item);
  });
}

document.getElementById("btn-open-vet-modal")?.addEventListener("click", () => {
  openModal("modal-vet");
});

document.getElementById("form-add-vet")?.addEventListener("submit", async (e) => {
  e.preventDefault();
  triggerHaptic("success");

  const catId = parseInt(document.getElementById("vet-cat-select").value);
  const type = document.getElementById("vet-type-select").value;
  const title = document.getElementById("vet-title").value.trim();
  const desc = document.getElementById("vet-desc").value.trim();
  const nextDate = document.getElementById("vet-next-date").value || null;

  try {
    const res = await apiFetch("/api/vet", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({
        cat_id: catId,
        record_type: type,
        title: title,
        description: desc,
        next_due_date: nextDate,
        user_id: currentUser.id,
        user_name: currentUser.name
      })
    });
    const result = await res.json();
    if (result.ok) {
      closeModal("modal-vet");
      document.getElementById("form-add-vet").reset();
      showToast("Запись успешно добавлена!");
      loadVet();
    } else {
      showToast(result.msg || "Ошибка сохранения");
    }
  } catch (err) {
    showToast("Ошибка сети");
  }
});

// ================= 5. РАСХОДЫ =================

async function loadExpenses() {
  const container = document.getElementById("expenses-list-container");
  if (!container) return;
  container.innerHTML = '<div class="loading-spinner">Загрузка расходов...</div>';
  try {
    const res = await apiFetch("/api/expenses");
    const data = await res.json();
    appData.expenses = data;
    renderExpenses(data);
  } catch (err) {
    container.innerHTML = '<div class="loading-spinner">Ошибка загрузки расходов</div>';
  }
}

function renderExpenses(data) {
  const totalEl = document.getElementById("expense-total");
  const catsContainer = document.getElementById("expense-categories-container");
  const listContainer = document.getElementById("expenses-list-container");
  if (!totalEl || !catsContainer || !listContainer) return;

  totalEl.innerText = `${(data.total_month || 0).toLocaleString("ru-RU")} ₽`;

  // Categories chips
  catsContainer.innerHTML = "";
  (data.by_category || []).forEach(c => {
    const chip = document.createElement("div");
    chip.className = "category-chip";
    chip.innerHTML = `
      <span>${c.label}</span>
      <span class="chip-val">${c.amount} ₽</span>
    `;
    catsContainer.appendChild(chip);
  });

  // Recent purchases
  listContainer.innerHTML = "";
  const recent = data.recent || [];
  if (recent.length === 0) {
    listContainer.innerHTML = '<div class="loading-spinner">Покупок в этом месяце нет</div>';
    return;
  }

  recent.forEach(r => {
    const item = document.createElement("div");
    item.className = "expense-item";
    item.innerHTML = `
      <div>
        <div class="expense-item-name">${r.note || r.category_label}</div>
        <div class="expense-item-meta">${r.expense_date.substring(0, 10)} • ${r.paid_by_name}</div>
      </div>
      <div class="expense-item-amount">${r.amount} ₽</div>
    `;
    listContainer.appendChild(item);
  });
}

document.getElementById("btn-open-expense-modal")?.addEventListener("click", () => {
  openModal("modal-expense");
});

document.getElementById("form-add-expense")?.addEventListener("submit", async (e) => {
  e.preventDefault();
  triggerHaptic("success");

  const amount = parseFloat(document.getElementById("expense-amount").value);
  const category = document.getElementById("expense-category").value;
  const note = document.getElementById("expense-note").value.trim();

  try {
    const res = await apiFetch("/api/expenses", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({
        amount: amount,
        category: category,
        note: note,
        paid_by_user_id: currentUser.id,
        paid_by_name: currentUser.name
      })
    });
    const result = await res.json();
    if (result.ok) {
      closeModal("modal-expense");
      document.getElementById("form-add-expense").reset();
      showToast("Расход записан!");
      loadExpenses();
    } else {
      showToast(result.msg || "Ошибка сохранения");
    }
  } catch (err) {
    showToast("Ошибка сети");
  }
});

// ================= 5. КОТО-ГАЛЕРЕЯ (СЕМЕЙНЫЙ АЛЬБОМ) =================

let currentGalleryFilter = "all";

async function loadGallery(filter = "all") {
  currentGalleryFilter = filter;
  const container = document.getElementById("gallery-container");
  if (!container) return;

  try {
    const res = await apiFetch("/api/photos");
    const data = await res.json();
    const photos = data.photos || [];

    const filtered = filter === "all" ? photos : photos.filter(p => p.category === filter);

    if (filtered.length === 0) {
      container.innerHTML = `
        <div class="empty-state" style="grid-column: span 2; padding: 32px 16px; text-align: center; color: var(--hint-color);">
          <div style="font-size: 36px; margin-bottom: 8px;">📸</div>
          <p>В этом альбоме пока нет фоток.<br>Нажмите <b>«➕ Фото»</b>, чтобы добавить!</p>
        </div>
      `;
      return;
    }

    container.innerHTML = "";
    filtered.forEach(p => {
      const card = document.createElement("div");
      card.className = "gallery-card";
      
      let badgeLabel = "✨ Момент";
      if (p.category === "feeding") badgeLabel = "🥣 Кормление";
      else if (p.category === "sleep") badgeLabel = "💤 Сон";
      else if (p.category === "play") badgeLabel = "🎾 Игра";

      const dateStr = p.created_at ? new Date(p.created_at).toLocaleDateString("ru-RU", { day: "numeric", month: "short" }) : "";

      card.innerHTML = `
        <div class="gallery-thumb-wrapper">
          <img class="gallery-thumb" src="${p.file_path}" alt="Фото котика" loading="lazy">
          <span class="gallery-badge-category">${badgeLabel}</span>
        </div>
        <div class="gallery-card-body">
          <div class="gallery-card-caption">${p.caption || "Без подписи"}</div>
          <div class="gallery-card-meta">
            <span>${p.user_name}</span>
            <span>${dateStr}</span>
          </div>
        </div>
      `;

      card.addEventListener("click", () => {
        openLightbox(p.file_path, p.caption || `${p.user_name} • ${dateStr}`);
      });

      container.appendChild(card);
    });
  } catch (err) {
    container.innerHTML = '<div class="loading-spinner">Ошибка загрузки галереи</div>';
  }
}

// Filter chips in Gallery
document.querySelectorAll(".gallery-filter-chips .filter-chip").forEach(chip => {
  chip.addEventListener("click", () => {
    triggerHaptic("light");
    document.querySelectorAll(".gallery-filter-chips .filter-chip").forEach(c => c.classList.remove("active"));
    chip.classList.add("active");
    loadGallery(chip.dataset.filter);
  });
});

// Photo upload flow
const photoInput = document.getElementById("input-photo-file");
const btnUpload = document.getElementById("btn-trigger-upload-photo");
let pendingPhotoBase64 = null;

btnUpload?.addEventListener("click", () => {
  photoInput?.click();
});

photoInput?.addEventListener("change", (e) => {
  const file = e.target.files?.[0];
  if (!file) return;

  const reader = new FileReader();
  reader.onload = (event) => {
    pendingPhotoBase64 = event.target.result;
    const preview = document.getElementById("upload-preview-img");
    if (preview) preview.src = pendingPhotoBase64;
    openModal("modal-upload-photo");
  };
  reader.readAsDataURL(file);
  photoInput.value = "";
});

document.getElementById("form-upload-photo")?.addEventListener("submit", async (e) => {
  e.preventDefault();
  if (!pendingPhotoBase64) return;

  triggerHaptic("success");
  const caption = document.getElementById("photo-caption").value.trim();
  const category = document.getElementById("photo-category").value;
  const submitBtn = document.getElementById("btn-submit-photo");

  if (submitBtn) {
    submitBtn.disabled = true;
    submitBtn.innerText = "Загрузка...";
  }

  try {
    const res = await apiFetch("/api/photos/upload", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({
        image_base64: pendingPhotoBase64,
        caption: caption,
        category: category,
        user_id: currentUser.id,
        user_name: currentUser.name
      })
    });
    const result = await res.json();
    if (result.ok) {
      closeModal("modal-upload-photo");
      document.getElementById("form-upload-photo").reset();
      pendingPhotoBase64 = null;
      showToast("Фото опубликовано! 📸");
      loadGallery(currentGalleryFilter);
    } else {
      showToast(result.msg || "Ошибка загрузки");
    }
  } catch (err) {
    showToast("Ошибка сети");
  } finally {
    if (submitBtn) {
      submitBtn.disabled = false;
      submitBtn.innerText = "Опубликовать в альбом 📸";
    }
  }
});

// ================= 6. AI ВЕТ-КОНСУЛЬТАНТ =================

document.querySelectorAll(".chip-item").forEach(chip => {
  chip.addEventListener("click", () => {
    triggerHaptic("light");
    const q = chip.dataset.q;
    const input = document.getElementById("vet-ai-input");
    if (input) {
      input.value = q;
      document.getElementById("form-vet-ai").dispatchEvent(new Event("submit"));
    }
  });
});

document.getElementById("form-vet-ai")?.addEventListener("submit", async (e) => {
  e.preventDefault();
  triggerHaptic("medium");
  const input = document.getElementById("vet-ai-input");
  const q = input.value.trim();
  if (!q) return;

  const btn = document.getElementById("btn-vet-ai-ask");
  if (btn) btn.disabled = true;

  const box = document.getElementById("vet-ai-response-box");
  const textElem = document.getElementById("vet-ai-response-text");
  if (box && textElem) {
    box.style.display = "block";
    textElem.innerHTML = "<i>Врач-консультант думает над ответом... 🐱🩺</i>";
  }

  try {
    const res = await apiFetch("/api/vet/ask", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ question: q })
    });
    const data = await res.json();
    if (textElem) {
      let html = (data.answer || "Ответ не получен").replace(/\n/g, "<br>");
      if (data.cat_specific) {
        html += `<br><br>🐾 <b>${data.cat_specific}</b>`;
      }
      textElem.innerHTML = html;
    }
  } catch (err) {
    if (textElem) textElem.innerHTML = "Ошибка связи с консультантом.";
  } finally {
    if (btn) btn.disabled = false;
  }
});

document.getElementById("btn-close-vet-response")?.addEventListener("click", () => {
  const box = document.getElementById("vet-ai-response-box");
  if (box) box.style.display = "none";
});

// ================= 7. ИСТОРИЯ ВЗВЕШИВАНИЙ =================

async function loadWeights() {
  const container = document.getElementById("weight-history-container");
  if (!container) return;

  try {
    const res = await apiFetch("/api/cats/weights");
    const data = await res.json();
    const weights = data.weights || [];

    if (weights.length === 0) {
      container.innerHTML = '<div style="font-size:12px; color:var(--hint-color); padding: 8px;">Нет записей о взвешиваниях</div>';
      return;
    }

    container.innerHTML = "";
    weights.slice(0, 6).forEach(w => {
      const row = document.createElement("div");
      row.className = "weight-row";
      const dateStr = w.created_at ? new Date(w.created_at).toLocaleDateString("ru-RU", { day: "numeric", month: "short" }) : "";
      row.innerHTML = `
        <div>
          <div class="weight-cat-name">${w.cat_name}</div>
          <div class="weight-meta-date">${dateStr} • ${w.recorded_by_name}</div>
        </div>
        <div class="weight-value-badge">${w.weight} кг</div>
      `;
      container.appendChild(row);
    });
  } catch (err) {
    container.innerHTML = '<div class="loading-spinner">Ошибка загрузки веса</div>';
  }
}

document.getElementById("btn-open-weight-modal")?.addEventListener("click", () => {
  const select = document.getElementById("weight-cat-select");
  if (select && appData.status?.cats) {
    select.innerHTML = appData.status.cats.map(c => `<option value="${c.id}">${c.name}</option>`).join("");
  }
  openModal("modal-weight");
});

document.getElementById("form-add-weight")?.addEventListener("submit", async (e) => {
  e.preventDefault();
  triggerHaptic("success");
  const catId = document.getElementById("weight-cat-select").value;
  const weight = parseFloat(document.getElementById("weight-input").value);

  try {
    const res = await apiFetch("/api/cats/weight", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({
        cat_id: catId,
        weight: weight,
        user_name: currentUser.name,
        user_id: currentUser.id
      })
    });
    const result = await res.json();
    if (result.ok) {
      closeModal("modal-weight");
      document.getElementById("form-add-weight").reset();
      showToast("Вес записан! ⚖️");
      loadWeights();
      loadStatus();
    } else {
      showToast(result.msg || "Ошибка сохранения");
    }
  } catch (err) {
    showToast("Ошибка сети");
  }
});

// ================= 8. МЫСЛИ КОТИКОВ =================

async function loadCatThought(ctx = "feed") {
  const textElem = document.getElementById("cat-thought-text");
  if (!textElem) return;
  try {
    const res = await apiFetch(`/api/thoughts?context=${ctx}`);
    const data = await res.json();
    if (data.thought) {
      textElem.innerText = data.thought;
    }
  } catch (e) {}
}

document.getElementById("btn-refresh-thought")?.addEventListener("click", () => {
  triggerHaptic("light");
  loadCatThought("general");
});

// ================= ИНИЦИАЛИЗАЦИЯ =================

loadStatus();
loadCatThought("feed");
setInterval(loadStatus, 60000);
