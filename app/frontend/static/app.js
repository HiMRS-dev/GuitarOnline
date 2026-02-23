const API_PREFIX = "/api/v1";
const ACCESS_TOKEN_KEY = "guitaronline_access_token";
const REFRESH_TOKEN_KEY = "guitaronline_refresh_token";

const state = {
  accessToken: null,
  refreshToken: null,
  currentUser: null,
};

const elements = {
  registerForm: document.getElementById("register-form"),
  loginForm: document.getElementById("login-form"),
  logoutButton: document.getElementById("logout-btn"),
  dashboardPanel: document.getElementById("dashboard-panel"),
  globalStatus: document.getElementById("global-status"),
  profileContent: document.getElementById("profile-content"),
  slotsContent: document.getElementById("slots-content"),
  bookingsContent: document.getElementById("bookings-content"),
  packagesContent: document.getElementById("packages-content"),
  tabButtons: Array.from(document.querySelectorAll(".tab-btn")),
  tabContents: Array.from(document.querySelectorAll(".tab-content")),
  refreshSlotsButton: document.getElementById("refresh-slots-btn"),
  refreshBookingsButton: document.getElementById("refresh-bookings-btn"),
  refreshPackagesButton: document.getElementById("refresh-packages-btn"),
};

document.addEventListener("DOMContentLoaded", () => {
  bindEvents();
  hydrateTokens();

  if (state.accessToken) {
    bootstrapAuthenticatedSession().catch((error) => {
      clearSession();
      showAuthMode();
      setGlobalStatus(`Сессия истекла: ${error.message}`, "error");
    });
    return;
  }

  showAuthMode();
  setGlobalStatus("Ожидание авторизации. Войдите или зарегистрируйтесь.", "muted");
});

function bindEvents() {
  elements.registerForm?.addEventListener("submit", handleRegister);
  elements.loginForm?.addEventListener("submit", handleLogin);
  elements.logoutButton?.addEventListener("click", handleLogout);
  elements.refreshSlotsButton?.addEventListener("click", () => refreshSlots());
  elements.refreshBookingsButton?.addEventListener("click", () => refreshBookings());
  elements.refreshPackagesButton?.addEventListener("click", () => refreshPackages());

  for (const button of elements.tabButtons) {
    button.addEventListener("click", () => {
      const tabName = button.dataset.tab;
      if (!tabName) {
        return;
      }
      activateTab(tabName);
    });
  }
}

function hydrateTokens() {
  state.accessToken = localStorage.getItem(ACCESS_TOKEN_KEY);
  state.refreshToken = localStorage.getItem(REFRESH_TOKEN_KEY);
}

function persistTokens(tokenPair) {
  state.accessToken = tokenPair.access_token;
  state.refreshToken = tokenPair.refresh_token;
  localStorage.setItem(ACCESS_TOKEN_KEY, state.accessToken);
  localStorage.setItem(REFRESH_TOKEN_KEY, state.refreshToken);
}

function clearSession() {
  state.accessToken = null;
  state.refreshToken = null;
  state.currentUser = null;
  localStorage.removeItem(ACCESS_TOKEN_KEY);
  localStorage.removeItem(REFRESH_TOKEN_KEY);
}

function showAuthMode() {
  elements.dashboardPanel.hidden = true;
  elements.logoutButton.hidden = true;
  elements.profileContent.innerHTML = "";
  elements.bookingsContent.innerHTML = "";
  elements.packagesContent.innerHTML = "";
}

function showDashboardMode() {
  elements.dashboardPanel.hidden = false;
  elements.logoutButton.hidden = false;
}

function setGlobalStatus(message, tone) {
  elements.globalStatus.textContent = message;
  elements.globalStatus.classList.remove("muted", "success", "error");
  elements.globalStatus.classList.add(tone);
}

function activateTab(tabName) {
  for (const button of elements.tabButtons) {
    button.classList.toggle("active", button.dataset.tab === tabName);
  }

  for (const content of elements.tabContents) {
    content.classList.toggle("active", content.id === `tab-${tabName}`);
  }
}

async function handleRegister(event) {
  event.preventDefault();
  const form = event.currentTarget;
  const payload = {
    email: form.email.value.trim(),
    password: form.password.value,
    timezone: form.timezone.value.trim() || "UTC",
    role: form.role.value,
  };

  try {
    await apiRequest("/identity/auth/register", {
      method: "POST",
      body: payload,
      auth: false,
      retryOnUnauthorized: false,
    });
    form.password.value = "";
    setGlobalStatus("Аккаунт создан. Теперь выполните вход.", "success");
  } catch (error) {
    setGlobalStatus(`Ошибка регистрации: ${error.message}`, "error");
  }
}

async function handleLogin(event) {
  event.preventDefault();
  const form = event.currentTarget;
  const payload = {
    email: form.email.value.trim(),
    password: form.password.value,
  };

  try {
    const tokenPair = await apiRequest("/identity/auth/login", {
      method: "POST",
      body: payload,
      auth: false,
      retryOnUnauthorized: false,
    });
    persistTokens(tokenPair);
    form.password.value = "";
    await bootstrapAuthenticatedSession();
    setGlobalStatus("Вход выполнен. Данные обновлены.", "success");
  } catch (error) {
    setGlobalStatus(`Ошибка входа: ${error.message}`, "error");
  }
}

async function handleLogout() {
  clearSession();
  showAuthMode();
  setGlobalStatus("Вы вышли из системы.", "muted");
}

async function bootstrapAuthenticatedSession() {
  await loadProfile();
  showDashboardMode();
  activateTab("profile");
  await Promise.all([refreshSlots(), refreshBookings(), refreshPackages()]);
}

async function refreshSlots() {
  try {
    const page = await apiRequest("/scheduling/slots/open?limit=20&offset=0", {
      auth: false,
      retryOnUnauthorized: false,
    });
    renderSlots(page.items ?? []);
  } catch (error) {
    renderEmpty(elements.slotsContent, `Не удалось загрузить слоты: ${error.message}`);
  }
}

async function refreshBookings() {
  if (!state.accessToken) {
    renderEmpty(elements.bookingsContent, "Выполните вход, чтобы увидеть бронирования.");
    return;
  }

  try {
    const page = await apiRequest("/booking/my?limit=20&offset=0");
    renderBookings(page.items ?? []);
  } catch (error) {
    renderEmpty(
      elements.bookingsContent,
      `Не удалось загрузить бронирования: ${error.message}`,
    );
  }
}

async function refreshPackages() {
  if (!state.currentUser) {
    renderEmpty(elements.packagesContent, "Профиль не загружен.");
    return;
  }

  if (state.currentUser.role.name !== "student") {
    renderEmpty(
      elements.packagesContent,
      "Раздел пакетов доступен только для роли student.",
    );
    return;
  }

  try {
    const page = await apiRequest(
      `/billing/packages/students/${state.currentUser.id}?limit=20&offset=0`,
    );
    renderPackages(page.items ?? []);
  } catch (error) {
    renderEmpty(elements.packagesContent, `Не удалось загрузить пакеты: ${error.message}`);
  }
}

async function loadProfile() {
  const user = await apiRequest("/identity/users/me");
  state.currentUser = user;
  renderProfile(user);
}

function renderProfile(user) {
  elements.profileContent.innerHTML = `
    <article class="card-item">
      <h4>${escapeHtml(user.email)}</h4>
      <p class="meta"><strong>ID:</strong> ${escapeHtml(user.id)}</p>
      <p class="meta"><strong>Роль:</strong> ${escapeHtml(user.role.name)}</p>
      <p class="meta"><strong>Таймзона:</strong> ${escapeHtml(user.timezone)}</p>
      <p class="meta"><strong>Активен:</strong> ${user.is_active ? "да" : "нет"}</p>
      <p class="meta"><strong>Создан:</strong> ${formatDateTime(user.created_at)}</p>
    </article>
  `;
}

function renderSlots(slots) {
  if (slots.length === 0) {
    renderEmpty(elements.slotsContent, "Открытых слотов пока нет.");
    return;
  }

  elements.slotsContent.innerHTML = slots
    .map((slot) => {
      return `
        <article class="card-item">
          <h4>Слот ${escapeHtml(slot.id)}</h4>
          <p class="meta"><strong>Преподаватель:</strong> ${escapeHtml(slot.teacher_id)}</p>
          <p class="meta"><strong>Начало:</strong> ${formatDateTime(slot.start_at)}</p>
          <p class="meta"><strong>Окончание:</strong> ${formatDateTime(slot.end_at)}</p>
          <p class="meta"><strong>Статус:</strong> ${escapeHtml(slot.status)}</p>
        </article>
      `;
    })
    .join("");
}

function renderBookings(bookings) {
  if (bookings.length === 0) {
    renderEmpty(elements.bookingsContent, "У вас пока нет бронирований.");
    return;
  }

  elements.bookingsContent.innerHTML = bookings
    .map((booking) => {
      return `
        <article class="card-item">
          <h4>Бронирование ${escapeHtml(booking.id)}</h4>
          <p class="meta"><strong>Статус:</strong> ${escapeHtml(booking.status)}</p>
          <p class="meta"><strong>Слот:</strong> ${escapeHtml(booking.slot_id)}</p>
          <p class="meta"><strong>Пакет:</strong> ${escapeHtml(booking.package_id ?? "-")}</p>
          <p class="meta"><strong>Создано:</strong> ${formatDateTime(booking.created_at)}</p>
        </article>
      `;
    })
    .join("");
}

function renderPackages(packages) {
  if (packages.length === 0) {
    renderEmpty(elements.packagesContent, "У вас пока нет пакетов.");
    return;
  }

  elements.packagesContent.innerHTML = packages
    .map((item) => {
      return `
        <article class="card-item">
          <h4>Пакет ${escapeHtml(item.id)}</h4>
          <p class="meta"><strong>Статус:</strong> ${escapeHtml(item.status)}</p>
          <p class="meta"><strong>Уроков всего:</strong> ${escapeHtml(item.lessons_total)}</p>
          <p class="meta"><strong>Осталось уроков:</strong> ${escapeHtml(item.lessons_left)}</p>
          <p class="meta"><strong>Действует до:</strong> ${formatDateTime(item.expires_at)}</p>
        </article>
      `;
    })
    .join("");
}

function renderEmpty(container, message) {
  container.innerHTML = `<div class="empty-note">${escapeHtml(message)}</div>`;
}

function formatDateTime(value) {
  if (!value) {
    return "-";
  }
  const date = new Date(value);
  if (Number.isNaN(date.getTime())) {
    return value;
  }
  return new Intl.DateTimeFormat("ru-RU", {
    dateStyle: "medium",
    timeStyle: "short",
  }).format(date);
}

function escapeHtml(value) {
  return String(value)
    .replaceAll("&", "&amp;")
    .replaceAll("<", "&lt;")
    .replaceAll(">", "&gt;")
    .replaceAll('"', "&quot;")
    .replaceAll("'", "&#039;");
}

function extractErrorMessage(payload, statusCode) {
  if (payload && typeof payload === "object") {
    if (payload.error && typeof payload.error.message === "string") {
      return payload.error.message;
    }
    if (typeof payload.detail === "string") {
      return payload.detail;
    }
    if (typeof payload.message === "string") {
      return payload.message;
    }
  }
  return `HTTP ${statusCode}`;
}

async function refreshSession() {
  if (!state.refreshToken) {
    return false;
  }

  try {
    const tokenPair = await apiRequest("/identity/auth/refresh", {
      method: "POST",
      body: { refresh_token: state.refreshToken },
      auth: false,
      retryOnUnauthorized: false,
    });
    persistTokens(tokenPair);
    return true;
  } catch (_) {
    clearSession();
    return false;
  }
}

async function apiRequest(
  path,
  {
    method = "GET",
    body = null,
    auth = true,
    retryOnUnauthorized = true,
  } = {},
) {
  const headers = {
    Accept: "application/json",
  };
  if (body !== null) {
    headers["Content-Type"] = "application/json";
  }
  if (auth && state.accessToken) {
    headers.Authorization = `Bearer ${state.accessToken}`;
  }

  const response = await fetch(`${API_PREFIX}${path}`, {
    method,
    headers,
    body: body !== null ? JSON.stringify(body) : undefined,
  });

  const contentType = response.headers.get("content-type") ?? "";
  let payload = null;
  if (contentType.includes("application/json")) {
    payload = await response.json();
  } else {
    const textPayload = await response.text();
    if (textPayload) {
      payload = { message: textPayload };
    }
  }

  if (
    response.status === 401 &&
    auth &&
    retryOnUnauthorized &&
    state.refreshToken
  ) {
    const refreshed = await refreshSession();
    if (refreshed) {
      return apiRequest(path, {
        method,
        body,
        auth,
        retryOnUnauthorized: false,
      });
    }
  }

  if (!response.ok) {
    throw new Error(extractErrorMessage(payload, response.status));
  }

  return payload;
}
