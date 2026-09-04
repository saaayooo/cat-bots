// Telegram WebApp Integration
const tg = window.Telegram?.WebApp;
if (tg) {
  try {
    tg.ready();
    tg.expand();
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
    else if (tabId === "tab-vet") loadVet();
    else if (tabId === "tab-expenses") loadExpenses();
  });
});

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
  const cats = data.cats || [];
  
  // Header: Avatars & Names
  if (cats.length >= 2) {
    document.getElementById("cat1-emoji").innerText = cats[0].emoji || "🐱";
    document.getElementById("cat2-emoji").innerText = cats[1].emoji || "😺";
    document.getElementById("cats-names").innerText = `${cats[0].name} & ${cats[1].name}`;
  } else if (cats.length === 1) {
    document.getElementById("cat1-emoji").innerText = cats[0].emoji || "🐱";
    document.getElementById("cats-names").innerText = cats[0].name;
  }

  // Last fed subtitle
  if (data.last_feeding) {
    const hours = data.hours_since_feed;
    const fedTime = data.last_feeding.fed_at ? data.last_feeding.fed_at.substring(11, 16) : "";
    document.getElementById("last-fed-info").innerText = `Кормление: ${fedTime} (${hours} ч. назад)`;
  } else {
    document.getElementById("last-fed-info").innerText = "Котики ждут первую трапезу 🥣";
  }

  // Streak
  const streakDays = data.streak?.current_streak || 0;
  document.getElementById("streak-days").innerText = streakDays;

  // Tamagotchi Mood & Satiety
  document.getElementById("cat-mood-avatar").innerText = data.mood_emoji || "😺";
  document.getElementById("mood-title").innerText = data.mood_title || "Довольны";
  document.getElementById("mood-desc").innerText = data.mood_desc || "";
  
  const satiety = data.satiety_percent ?? 100;
  document.getElementById("satiety-val").innerText = `${satiety}%`;
  document.getElementById("satiety-bar").style.width = `${satiety}%`;

  // Vital stats bars
  document.getElementById("water-bar").style.width = `${data.water_percent ?? 100}%`;
  document.getElementById("water-text").innerText = (data.water_percent >= 70) ? "Свежая 💧" : "Нужно обновить ⏳";

  document.getElementById("litter-bar").style.width = `${data.litter_percent ?? 100}%`;
  document.getElementById("litter-text").innerText = (data.litter_percent >= 70) ? "Чистый ✨" : "Почистить 🚽";

  document.getElementById("play-bar").style.width = `${data.play_percent ?? 80}%`;
  document.getElementById("play-text").innerText = (data.play_percent >= 80) ? "Поиграли 🎾" : "Ждут лазерку";

  // Cat profile cards
  const container = document.getElementById("cats-list-container");
  container.innerHTML = "";
  cats.forEach(c => {
    const card = document.createElement("div");
    const weightStr = (c.weight && c.weight > 0) ? `⚖️ ${c.weight} кг` : "⚖️ Вес неизвестен";
    const breedStr = c.breed || "Порода неизвестна";
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
  triggerHaptic("success");
  const btn = document.getElementById("btn-quick-feed");
  btn.disabled = true;
  btn.innerHTML = "<span>Накладываем корм... 🥣</span>";

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
      // Animate cat face
      const face = document.getElementById("cat-mood-avatar");
      face.innerText = "🥰";
      face.style.transform = "scale(1.2) translateY(-10px)";
      setTimeout(() => { face.style.transform = ""; }, 1000);
      await loadStatus();
    } else {
      showToast(result.msg || "Ошибка кормления");
    }
  } catch (err) {
    console.error("Feed error:", err);
    showToast("Ошибка сети");
  } finally {
    btn.disabled = false;
    btn.innerHTML = '<span class="btn-icon">🥣</span><span>Покормить котиков в 1 клик</span>';
  }
});

// Load Quests
async function loadQuests() {
  const container = document.getElementById("quests-container");
  container.innerHTML = '<div class="loading-spinner">Загрузка квестов...</div>';
  try {
    const res = await fetch("/api/quests");
    const quests = await res.json();
    appData.quests = quests;
    renderQuests(quests);
  } catch (err) {
    container.innerHTML = '<div class="loading-spinner">Ошибка загрузки квестов</div>';
  }
}

function renderQuests(quests) {
  const container = document.getElementById("quests-container");
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
        <span class="quest-status-badge ${statusClass}">${statusText}</span>
      </div>
      ${actionsHtml ? `<div class="quest-actions">${actionsHtml}</div>` : ""}
    `;
    container.appendChild(item);
  });
}

// Quest Actions
async function handleQuestAction(action, qid) {
  triggerHaptic("success");
  try {
    const res = await fetch("/api/quests/action", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({
        action: action,
        quest_id: qid,
        user_id: currentUser.id,
        user_name: currentUser.name
      })
    });
    const resData = await res.json();
    showToast(resData.msg || "Готово!");
    await loadQuests();
    loadStatus();
  } catch (err) {
    showToast("Ошибка действия с квестом");
  }
}
window.handleQuestAction = handleQuestAction;

document.getElementById("btn-refresh-quests")?.addEventListener("click", () => {
  triggerHaptic("light");
  loadQuests();
});

// Load Vet Records
async function loadVet() {
  const container = document.getElementById("vet-records-container");
  const alertsContainer = document.getElementById("vet-alerts-container");
  container.innerHTML = '<div class="loading-spinner">Загрузка вет-паспорта...</div>';

  try {
    const res = await fetch("/api/vet");
    const data = await res.json();
    
    // Alerts
    alertsContainer.innerHTML = "";
    if (data.upcoming && data.upcoming.length > 0) {
      data.upcoming.forEach(up => {
        const al = document.createElement("div");
        al.className = "vet-alert-card";
        al.innerHTML = `
          <span>⚠️</span>
          <div>
            <strong>Скоро: ${up.title}</strong> (${up.cat_name})<br>
            <small>Запланировано на ${up.next_due_date}</small>
          </div>
        `;
        alertsContainer.appendChild(al);
      });
    }

    // Records
    container.innerHTML = "";
    if (!data.records || data.records.length === 0) {
      container.innerHTML = '<div class="loading-spinner">Пока нет записей в вет-паспорте</div>';
      return;
    }

    data.records.forEach(r => {
      const card = document.createElement("div");
      card.className = "vet-card";
      card.innerHTML = `
        <div class="vet-card-header">
          <span class="vet-card-title">${r.title}</span>
          <span class="vet-card-date">${r.record_date}</span>
        </div>
        <div class="vet-card-meta">
          <span>🐱 ${r.cat_name}</span>
          ${r.description ? ` • <span>${r.description}</span>` : ""}
          ${r.next_due_date ? `<br><small style="color: var(--link-color)">Повторить: ${r.next_due_date}</small>` : ""}
        </div>
      `;
      container.appendChild(card);
    });
  } catch (err) {
    container.innerHTML = '<div class="loading-spinner">Ошибка загрузки вет-паспорта</div>';
  }
}

// Load Expenses
async function loadExpenses() {
  const container = document.getElementById("expenses-list-container");
  const chipsContainer = document.getElementById("expense-categories-container");
  container.innerHTML = '<div class="loading-spinner">Загрузка расходов...</div>';

  try {
    const res = await fetch("/api/expenses");
    const data = await res.json();
    
    document.getElementById("expense-total").innerText = `${data.total_month.toLocaleString("ru-RU")} ₽`;

    // Category chips
    chipsContainer.innerHTML = "";
    if (data.by_category) {
      data.by_category.forEach(c => {
        const chip = document.createElement("div");
        chip.className = "cat-chip";
        chip.innerHTML = `
          <span>${c.label}</span>
          <span class="cat-chip-amt">${c.amount} ₽</span>
        `;
        chipsContainer.appendChild(chip);
      });
    }

    // Recent list
    container.innerHTML = "";
    if (!data.recent || data.recent.length === 0) {
      container.innerHTML = '<div class="loading-spinner">В этом месяце расходов еще не записано</div>';
      return;
    }

    data.recent.forEach(exp => {
      const row = document.createElement("div");
      row.className = "expense-item";
      row.innerHTML = `
        <div class="expense-item-left">
          <span class="expense-item-name">${exp.category_label}</span>
          <span class="expense-item-meta">${exp.note ? exp.note + ' • ' : ''}${exp.paid_by_name} (${exp.expense_date})</span>
        </div>
        <span class="expense-item-amount">${exp.amount} ₽</span>
      `;
      container.appendChild(row);
    });
  } catch (err) {
    container.innerHTML = '<div class="loading-spinner">Ошибка загрузки расходов</div>';
  }
}

// Modals Handling
function openModal(id) {
  triggerHaptic("light");
  document.getElementById(id)?.classList.add("active");
}
function closeModal(id) {
  document.getElementById(id)?.classList.remove("active");
}

document.querySelectorAll("[data-close]").forEach(btn => {
  btn.addEventListener("click", () => closeModal(btn.dataset.close));
});

document.getElementById("btn-open-vet-modal")?.addEventListener("click", () => openModal("modal-vet"));
document.getElementById("btn-open-expense-modal")?.addEventListener("click", () => openModal("modal-expense"));

// Submit Vet Record
document.getElementById("form-add-vet")?.addEventListener("submit", async (e) => {
  e.preventDefault();
  triggerHaptic("success");
  
  const catId = parseInt(document.getElementById("vet-cat-select").value);
  const type = document.getElementById("vet-type-select").value;
  const title = document.getElementById("vet-title").value;
  const desc = document.getElementById("vet-desc").value;
  const nextDate = document.getElementById("vet-next-date").value || null;

  try {
    const res = await fetch("/api/vet", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({
        cat_id: catId,
        record_type: type,
        title: title,
        description: desc,
        next_due_date: nextDate
      })
    });
    const result = await res.json();
    if (result.ok) {
      showToast("Запись в вет-паспорт добавлена!");
      closeModal("modal-vet");
      document.getElementById("form-add-vet").reset();
      loadVet();
    }
  } catch (err) {
    showToast("Ошибка сохранения вет-записи");
  }
});

// Submit Expense
document.getElementById("form-add-expense")?.addEventListener("submit", async (e) => {
  e.preventDefault();
  triggerHaptic("success");

  const amount = parseFloat(document.getElementById("expense-amount").value);
  const category = document.getElementById("expense-category").value;
  const note = document.getElementById("expense-note").value;

  try {
    const res = await fetch("/api/expenses", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({
        amount: amount,
        category: category,
        paid_by_user_id: currentUser.id,
        paid_by_name: currentUser.name,
        note: note
      })
    });
    const result = await res.json();
    if (result.ok) {
      showToast("Расход успешно записан! 💰");
      closeModal("modal-expense");
      document.getElementById("form-add-expense").reset();
      loadExpenses();
    }
  } catch (err) {
    showToast("Ошибка добавления расхода");
  }
});

// Initial load & Polling
loadStatus();
setInterval(() => {
  loadStatus();
}, 20000);
