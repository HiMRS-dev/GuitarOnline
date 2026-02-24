const API_PREFIX = "/api/v1";
const ACCESS_TOKEN_KEY = "guitaronline_access_token";
const REFRESH_TOKEN_KEY = "guitaronline_refresh_token";

const state = {
  accessToken: null,
  refreshToken: null,
  currentUser: null,
  slots: [],
  bookings: [],
  packages: [],
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
  slotPackageControls: document.getElementById("slot-package-controls"),
  slotPackageSelect: document.getElementById("slot-package-select"),
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
  elements.slotsContent?.addEventListener("click", handleSlotsActionClick);
  elements.bookingsContent?.addEventListener("click", handleBookingsActionClick);

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
  state.slots = [];
  state.bookings = [];
  state.packages = [];
  localStorage.removeItem(ACCESS_TOKEN_KEY);
  localStorage.removeItem(REFRESH_TOKEN_KEY);

  if (elements.slotPackageSelect) {
    elements.slotPackageSelect.innerHTML = "";
  }
}

function showAuthMode() {
  elements.dashboardPanel.hidden = true;
  elements.logoutButton.hidden = true;
  elements.profileContent.innerHTML = "";
  elements.slotsContent.innerHTML = "";
  elements.bookingsContent.innerHTML = "";
  elements.packagesContent.innerHTML = "";

  if (elements.slotPackageControls) {
    elements.slotPackageControls.hidden = true;
  }
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

function isStudentRole() {
  return state.currentUser?.role?.name === "student";
}

function getHoldEligiblePackages() {
  return state.packages.filter(
    (pkg) => pkg.status === "active" && Number(pkg.lessons_left) > 0,
  );
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
    state.slots = page.items ?? [];
    renderSlots(state.slots);
  } catch (error) {
    state.slots = [];
    renderEmpty(elements.slotsContent, `Не удалось загрузить слоты: ${error.message}`);
  }
}

async function refreshBookings() {
  if (!state.accessToken) {
    state.bookings = [];
    renderEmpty(elements.bookingsContent, "Выполните вход, чтобы увидеть бронирования.");
    return;
  }

  try {
    const page = await apiRequest("/booking/my?limit=20&offset=0");
    state.bookings = page.items ?? [];
    renderBookings(state.bookings);
  } catch (error) {
    state.bookings = [];
    renderEmpty(elements.bookingsContent, `Не удалось загрузить бронирования: ${error.message}`);
  }
}

async function refreshPackages() {
  if (!state.currentUser) {
    state.packages = [];
    renderEmpty(elements.packagesContent, "Профиль не загружен.");
    renderSlotPackageControls();
    if (state.slots.length > 0) {
      renderSlots(state.slots);
    }
    return;
  }

  if (!isStudentRole()) {
    state.packages = [];
    renderEmpty(
      elements.packagesContent,
      "Раздел пакетов доступен только для роли student.",
    );
    renderSlotPackageControls();
    if (state.slots.length > 0) {
      renderSlots(state.slots);
    }
    return;
  }

  try {
    const page = await apiRequest(
      `/billing/packages/students/${state.currentUser.id}?limit=20&offset=0`,
    );
    state.packages = page.items ?? [];
    renderPackages(state.packages);
    renderSlotPackageControls();
    if (state.slots.length > 0) {
      renderSlots(state.slots);
    }
  } catch (error) {
    state.packages = [];
    renderEmpty(elements.packagesContent, `Не удалось загрузить пакеты: ${error.message}`);
    renderSlotPackageControls();
    if (state.slots.length > 0) {
      renderSlots(state.slots);
    }
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

function renderSlotPackageControls() {
  if (!elements.slotPackageControls || !elements.slotPackageSelect) {
    return;
  }

  if (!isStudentRole()) {
    elements.slotPackageControls.hidden = true;
    elements.slotPackageSelect.innerHTML = "";
    return;
  }

  const eligiblePackages = getHoldEligiblePackages();
  if (eligiblePackages.length === 0) {
    elements.slotPackageControls.hidden = true;
    elements.slotPackageSelect.innerHTML = "";
    return;
  }

  const previousValue = elements.slotPackageSelect.value;
  elements.slotPackageControls.hidden = false;
  elements.slotPackageSelect.innerHTML = eligiblePackages
    .map((pkg) => {
      return `<option value="${escapeHtml(pkg.id)}">${escapeHtml(pkg.id)} (уроков: ${escapeHtml(pkg.lessons_left)})</option>`;
    })
    .join("");

  if (previousValue) {
    const stillExists = eligiblePackages.some((pkg) => String(pkg.id) === previousValue);
    if (stillExists) {
      elements.slotPackageSelect.value = previousValue;
    }
  }
}

function renderSlots(slots) {
  renderSlotPackageControls();

  if (slots.length === 0) {
    renderEmpty(elements.slotsContent, "Открытых слотов пока нет.");
    return;
  }

  const canCreateHold = isStudentRole() && getHoldEligiblePackages().length > 0;
  const cards = slots
    .map((slot) => {
      const holdAction = isStudentRole()
        ? `<div class="action-row"><button type="button" class="action-btn" data-action="hold-slot" data-slot-id="${escapeHtml(slot.id)}" ${canCreateHold ? "" : "disabled"}>Взять в hold</button></div>`
        : "";

      return `
        <article class="card-item">
          <h4>Слот ${escapeHtml(slot.id)}</h4>
          <p class="meta"><strong>Преподаватель:</strong> ${escapeHtml(slot.teacher_id)}</p>
          <p class="meta"><strong>Начало:</strong> ${formatDateTime(slot.start_at)}</p>
          <p class="meta"><strong>Окончание:</strong> ${formatDateTime(slot.end_at)}</p>
          <p class="meta"><strong>Статус:</strong> ${escapeHtml(slot.status)}</p>
          ${holdAction}
        </article>
      `;
    })
    .join("");

  const hint = isStudentRole() && !canCreateHold
    ? "<p class=\"hint\">Для hold нужен активный пакет с оставшимися уроками.</p>"
    : "";

  elements.slotsContent.innerHTML = `${hint}${cards}`;
}

function renderBookings(bookings) {
  if (bookings.length === 0) {
    renderEmpty(elements.bookingsContent, "У вас пока нет бронирований.");
    return;
  }

  const studentMode = isStudentRole();
  elements.bookingsContent.innerHTML = bookings
    .map((booking) => {
      const status = String(booking.status).toLowerCase();
      const canConfirm = studentMode && status === "hold";
      const canCancel = studentMode && (status === "hold" || status === "confirmed");
      const canReschedule = studentMode && (status === "hold" || status === "confirmed");

      const rescheduleOptions = state.slots
        .filter((slot) => String(slot.id) !== String(booking.slot_id))
        .map((slot) => {
          return `<option value="${escapeHtml(slot.id)}">${formatDateTime(slot.start_at)} - ${formatDateTime(slot.end_at)}</option>`;
        })
        .join("");

      const confirmAction = canConfirm
        ? `<button type="button" class="action-btn" data-action="confirm-booking" data-booking-id="${escapeHtml(booking.id)}">Подтвердить</button>`
        : "";

      const cancelAction = canCancel
        ? `<button type="button" class="action-btn danger" data-action="cancel-booking" data-booking-id="${escapeHtml(booking.id)}">Отменить</button>`
        : "";

      const cancelReason = canCancel
        ? `
          <div class="action-row">
            <input
              type="text"
              maxlength="512"
              placeholder="Причина отмены (опционально)"
              data-role="cancel-reason"
              data-booking-id="${escapeHtml(booking.id)}"
            />
          </div>
        `
        : "";

      let rescheduleAction = "";
      if (canReschedule) {
        if (rescheduleOptions) {
          rescheduleAction = `
            <div class="action-row">
              <select data-role="reschedule-slot" data-booking-id="${escapeHtml(booking.id)}">
                ${rescheduleOptions}
              </select>
              <button
                type="button"
                class="action-btn secondary"
                data-action="reschedule-booking"
                data-booking-id="${escapeHtml(booking.id)}"
                data-current-slot-id="${escapeHtml(booking.slot_id)}"
              >
                Перенести
              </button>
            </div>
          `;
        } else {
          rescheduleAction = "<p class=\"hint\">Нет открытых слотов для переноса.</p>";
        }
      }

      return `
        <article class="card-item">
          <h4>Бронирование ${escapeHtml(booking.id)}</h4>
          <p class="meta"><strong>Статус:</strong> ${escapeHtml(booking.status)}</p>
          <p class="meta"><strong>Слот:</strong> ${escapeHtml(booking.slot_id)}</p>
          <p class="meta"><strong>Пакет:</strong> ${escapeHtml(booking.package_id ?? "-")}</p>
          <p class="meta"><strong>Hold до:</strong> ${formatDateTime(booking.hold_expires_at)}</p>
          <p class="meta"><strong>Создано:</strong> ${formatDateTime(booking.created_at)}</p>
          <div class="action-row">
            ${confirmAction}
            ${cancelAction}
          </div>
          ${cancelReason}
          ${rescheduleAction}
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

async function handleSlotsActionClick(event) {
  const button = event.target.closest("button[data-action]");
  if (!button) {
    return;
  }

  const action = button.dataset.action;
  if (action !== "hold-slot") {
    return;
  }

  if (!isStudentRole()) {
    setGlobalStatus("Hold доступен только для роли student.", "error");
    return;
  }

  const slotId = button.dataset.slotId;
  const packageId = elements.slotPackageSelect?.value ?? "";

  if (!slotId || !packageId) {
    setGlobalStatus("Выберите пакет и повторите попытку hold.", "error");
    return;
  }

  await withButtonAction(button, async () => {
    const booking = await apiRequest("/booking/hold", {
      method: "POST",
      body: {
        slot_id: slotId,
        package_id: packageId,
      },
    });

    setGlobalStatus(`Hold создан: ${booking.id}`, "success");
    await refreshAfterBookingMutation();
    activateTab("bookings");
  });
}

async function handleBookingsActionClick(event) {
  const button = event.target.closest("button[data-action]");
  if (!button) {
    return;
  }

  const action = button.dataset.action;
  if (
    action !== "confirm-booking" &&
    action !== "cancel-booking" &&
    action !== "reschedule-booking"
  ) {
    return;
  }

  const bookingId = button.dataset.bookingId;
  if (!bookingId) {
    return;
  }

  await withButtonAction(button, async () => {
    if (action === "confirm-booking") {
      await apiRequest(`/booking/${bookingId}/confirm`, {
        method: "POST",
      });
      setGlobalStatus(`Бронирование подтверждено: ${bookingId}`, "success");
      await refreshAfterBookingMutation();
      return;
    }

    if (action === "cancel-booking") {
      const reasonInput = elements.bookingsContent.querySelector(
        `input[data-role="cancel-reason"][data-booking-id="${bookingId}"]`,
      );
      const reason = reasonInput ? reasonInput.value.trim() : "";

      await apiRequest(`/booking/${bookingId}/cancel`, {
        method: "POST",
        body: {
          reason: reason || null,
        },
      });

      if (reasonInput) {
        reasonInput.value = "";
      }

      setGlobalStatus(`Бронирование отменено: ${bookingId}`, "success");
      await refreshAfterBookingMutation();
      return;
    }

    if (action === "reschedule-booking") {
      const select = elements.bookingsContent.querySelector(
        `select[data-role="reschedule-slot"][data-booking-id="${bookingId}"]`,
      );
      const newSlotId = select?.value ?? "";
      const currentSlotId = button.dataset.currentSlotId ?? "";

      if (!newSlotId) {
        setGlobalStatus("Выберите новый слот для переноса.", "error");
        return;
      }

      if (newSlotId === currentSlotId) {
        setGlobalStatus("Новый слот должен отличаться от текущего.", "error");
        return;
      }

      const newBooking = await apiRequest(`/booking/${bookingId}/reschedule`, {
        method: "POST",
        body: {
          new_slot_id: newSlotId,
        },
      });

      setGlobalStatus(`Бронирование перенесено. Новый ID: ${newBooking.id}`, "success");
      await refreshAfterBookingMutation();
      return;
    }
  });
}

async function refreshAfterBookingMutation() {
  await Promise.all([refreshSlots(), refreshBookings(), refreshPackages()]);
}

async function withButtonAction(button, action) {
  if (button.disabled) {
    return;
  }

  const originalText = button.textContent;
  button.disabled = true;
  button.textContent = "Выполняется...";

  try {
    await action();
  } catch (error) {
    setGlobalStatus(`Ошибка операции: ${error.message}`, "error");
  } finally {
    button.disabled = false;
    button.textContent = originalText;
  }
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

function extractValidationError(payload) {
  if (!Array.isArray(payload?.detail)) {
    return null;
  }

  const errors = payload.detail
    .map((item) => {
      if (!item || typeof item !== "object") {
        return null;
      }

      const message = typeof item.msg === "string" ? item.msg : null;
      if (!message) {
        return null;
      }

      if (Array.isArray(item.loc) && item.loc.length > 0) {
        return `${item.loc.join(".")}: ${message}`;
      }

      return message;
    })
    .filter(Boolean);

  if (errors.length === 0) {
    return null;
  }

  return errors.join("; ");
}

function extractErrorMessage(payload, statusCode) {
  const validationMessage = extractValidationError(payload);
  if (validationMessage) {
    return validationMessage;
  }

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
