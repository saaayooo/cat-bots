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
  status: null
};

// Current Telegram user info (or fallback)
const currentUser = {
  id: tg?.initDataUnsafe?.user?.id || 1,
  name: tg?.initDataUnsafe?.user?.first_name || "Пользователь"
};

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
  }, 2500);
}

// Load Overall Status (Tamagotchi & Cats)
async function loadStatus() {
  try {
    const res = await fetch("/api/status");
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

  // Cat profile cards
  const container = document.getElementById("cats-list-container");
  if (container) {
    container.innerHTML = "";
    cats.forEach(c => {
      const card = document.createElement("div");
      card.className = "cat-card";
      const weightStr = (c.weight && c.weight > 0) ? `⚖️ ${c.weight} кг` : "⚖️ Вес неизвестен";
      const breedStr = c.breed || "Черный котик";
      card.innerHTML = `
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
}

// Quick Feed Action
document.getElementById("btn-quick-feed")?.addEventListener("click", async () => {
  triggerHaptic("success");
  const btn = document.getElementById("btn-quick-feed");
  const btnText = document.getElementById("feed-btn-text");
  if (btn) btn.disabled = true;
  if (btnText) btnText.innerText = "Накладываем корм... 🥣";

  try {
    const res = await fetch("/api/feed", {
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

// Interactive Care Actions: Water, Litter, Play
async function handleCareAction(type) {
  triggerHaptic("success");

  // Optimistic UI updates
  if (type === "water") {
    const bar = document.getElementById("water-bar");
    if (bar) bar.style.width = "100%";
    const txt = document.getElementById("water-text");
    if (txt) txt.innerText = "Свежая 💧";
    const hint = document.getElementById("water-hint");
    if (hint) hint.innerText = "Обновлено ✨";
  } else if (type === "litter") {
    const bar = document.getElementById("litter-bar");
    if (bar) bar.style.width = "100%";
    const txt = document.getElementById("litter-text");
    if (txt) txt.innerText = "Чистый ✨";
    const hint = document.getElementById("litter-hint");
    if (hint) hint.innerText = "Обновлено ✨";
  } else if (type === "play") {
    const bar = document.getElementById("play-bar");
    if (bar) bar.style.width = "100%";
    const txt = document.getElementById("play-text");
    if (txt) txt.innerText = "Поиграли 🎾";
    const hint = document.getElementById("play-hint");
    if (hint) hint.innerText = "Обновлено ✨";
  }

  // Micro bounce on face avatar
  const face = document.getElementById("cat-mood-avatar");
  if (face) {
    face.style.transform = "scale(1.2) translateY(-6px)";
    setTimeout(() => { face.style.transform = ""; }, 800);
  }

  try {
    const res = await fetch("/api/care", {
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

// Initial Load & Polling every 60 seconds
loadStatus();
setInterval(loadStatus, 60000);
