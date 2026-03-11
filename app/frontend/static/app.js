const API_PREFIX = "/api/v1";

const state = {
  accessToken: null,
  currentUser: null,
  slots: [],
  bookings: [],
  packages: [],
  lessons: [],
  adminOperations: {
    lastExpiredHolds: null,
    lastExpiredPackages: null,
    updatedAt: null,
  },
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
  lessonsContent: document.getElementById("lessons-content"),
  adminActionsContent: document.getElementById("admin-actions-content"),
  tabButtons: Array.from(document.querySelectorAll(".tab-btn")),
  tabContents: Array.from(document.querySelectorAll(".tab-content")),
  refreshSlotsButton: document.getElementById("refresh-slots-btn"),
  refreshBookingsButton: document.getElementById("refresh-bookings-btn"),
  refreshPackagesButton: document.getElementById("refresh-packages-btn"),
  refreshLessonsButton: document.getElementById("refresh-lessons-btn"),
  runExpireHoldsButton: document.getElementById("run-expire-holds-btn"),
  runExpirePackagesButton: document.getElementById("run-expire-packages-btn"),
  slotPackageControls: document.getElementById("slot-package-controls"),
  slotPackageSelect: document.getElementById("slot-package-select"),
  registerSection: document.getElementById("register-section"),
  loginSection: document.getElementById("login-section"),
};

document.addEventListener("DOMContentLoaded", () => {
  bindEvents();
  hydrateTokens();

  if (state.accessToken) {
    bootstrapAuthenticatedSession().catch((error) => {
      clearSession();
      showAuthMode();
      setGlobalStatus(`РЎРµСЃСЃРёСЏ РёСЃС‚РµРєР»Р°: ${error.message}`, "error");
    });
    return;
  }

  showAuthMode();
  setGlobalStatus("РћР¶РёРґР°РЅРёРµ Р°РІС‚РѕСЂРёР·Р°С†РёРё. Р’РѕР№РґРёС‚Рµ РёР»Рё Р·Р°СЂРµРіРёСЃС‚СЂРёСЂСѓР№С‚РµСЃСЊ.", "muted");
  bootstrapSessionFromCookie().catch((error) => {
    clearSession();
    showAuthMode();
    setGlobalStatus(`Session expired: ${error.message}`, "error");
  });
});

async function bootstrapSessionFromCookie() {
  const refreshed = await refreshSession();
  if (!refreshed) {
    return false;
  }
  await bootstrapAuthenticatedSession();
  return true;
}

function bindEvents() {
  elements.registerForm?.addEventListener("submit", handleRegister);
  elements.loginForm?.addEventListener("submit", handleLogin);
  elements.logoutButton?.addEventListener("click", handleLogout);
  elements.refreshSlotsButton?.addEventListener("click", () => refreshSlots());
  elements.refreshBookingsButton?.addEventListener("click", () => refreshBookings());
  elements.refreshPackagesButton?.addEventListener("click", () => refreshPackages());
  elements.refreshLessonsButton?.addEventListener("click", () => refreshLessons());
  elements.runExpireHoldsButton?.addEventListener("click", handleExpireHolds);
  elements.runExpirePackagesButton?.addEventListener("click", handleExpirePackages);
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
  state.accessToken = null;
}

function persistTokens(tokenPair) {
  state.accessToken = tokenPair.access_token;
}

function clearSession() {
  state.accessToken = null;
  state.currentUser = null;
  state.slots = [];
  state.bookings = [];
  state.packages = [];
  state.lessons = [];
  state.adminOperations.lastExpiredHolds = null;
  state.adminOperations.lastExpiredPackages = null;
  state.adminOperations.updatedAt = null;

  if (elements.slotPackageSelect) {
    elements.slotPackageSelect.innerHTML = "";
  }
}

function moveToAuthState(message = "РЎРµСЃСЃРёСЏ РёСЃС‚РµРєР»Р°. Р’С‹РїРѕР»РЅРёС‚Рµ РІС…РѕРґ СЃРЅРѕРІР°.") {
  clearSession();
  showAuthMode();
  setGlobalStatus(message, "error");
}

function showAuthMode() {
  elements.dashboardPanel.hidden = true;
  elements.logoutButton.hidden = true;
  elements.profileContent.innerHTML = "";
  elements.slotsContent.innerHTML = "";
  elements.bookingsContent.innerHTML = "";
  elements.packagesContent.innerHTML = "";
  elements.lessonsContent.innerHTML = "";
  elements.adminActionsContent.innerHTML = "";

  if (elements.slotPackageControls) {
    elements.slotPackageControls.hidden = true;
  }

  const requestedMode = getAuthModeFromQuery();
  applyAuthMode(requestedMode);
}


function getAuthModeFromQuery() {
  const mode = new URLSearchParams(window.location.search).get("auth");
  if (mode === "login" || mode === "register") {
    return mode;
  }
  return null;
}

function applyAuthMode(mode) {
  if (!elements.registerSection || !elements.loginSection) {
    return;
  }

  const registerActive = mode !== "login";
  const loginActive = mode !== "register";

  elements.registerSection.hidden = !registerActive;
  elements.loginSection.hidden = !loginActive;

  if (mode === "login") {
    elements.loginForm?.email?.focus();
  }
  if (mode === "register") {
    elements.registerForm?.email?.focus();
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
    button.classList.toggle("active", button.dataset.tab === tabName && !button.hidden);
  }

  for (const content of elements.tabContents) {
    content.classList.toggle("active", content.id === `tab-${tabName}` && !content.hidden);
  }
}

function getCurrentRole() {
  return state.currentUser?.role?.name ?? null;
}

function isStudentRole() {
  return getCurrentRole() === "student";
}

function isTeacherRole() {
  return getCurrentRole() === "teacher";
}

function isAdminRole() {
  return getCurrentRole() === "admin";
}

function isTabVisible(tabName, roleName) {
  if (!roleName) {
    return tabName === "profile";
  }

  const visibilityMap = {
    profile: ["student", "teacher", "admin"],
    slots: ["student"],
    bookings: ["student"],
    packages: ["student"],
    lessons: ["teacher"],
    "admin-ops": ["admin"],
  };

  const allowedRoles = visibilityMap[tabName] ?? [];
  return allowedRoles.includes(roleName);
}

function applyRoleAwareTabs() {
  const roleName = getCurrentRole();
  let firstVisibleTab = null;

  for (const button of elements.tabButtons) {
    const tabName = button.dataset.tab ?? "";
    const visible = isTabVisible(tabName, roleName);
    button.hidden = !visible;
    if (visible && firstVisibleTab === null) {
      firstVisibleTab = tabName;
    }
  }

  for (const content of elements.tabContents) {
    const tabName = content.id.replace("tab-", "");
    content.hidden = !isTabVisible(tabName, roleName);
  }

  const activeButton = elements.tabButtons.find(
    (button) => button.classList.contains("active") && !button.hidden,
  );
  if (activeButton?.dataset.tab) {
    activateTab(activeButton.dataset.tab);
    return;
  }

  if (firstVisibleTab) {
    activateTab(firstVisibleTab);
  }
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
    applyAuthMode("login");
    setGlobalStatus("РђРєРєР°СѓРЅС‚ СЃРѕР·РґР°РЅ. РўРµРїРµСЂСЊ РІС‹РїРѕР»РЅРёС‚Рµ РІС…РѕРґ.", "success");
  } catch (error) {
    setGlobalStatus(`РћС€РёР±РєР° СЂРµРіРёСЃС‚СЂР°С†РёРё: ${error.message}`, "error");
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
    setGlobalStatus("Р’С…РѕРґ РІС‹РїРѕР»РЅРµРЅ. Р”Р°РЅРЅС‹Рµ РѕР±РЅРѕРІР»РµРЅС‹.", "success");
  } catch (error) {
    setGlobalStatus(`РћС€РёР±РєР° РІС…РѕРґР°: ${error.message}`, "error");
  }
}

async function handleLogout() {
  try {
    await apiRequest("/identity/auth/logout", {
      method: "POST",
      auth: false,
      retryOnUnauthorized: false,
    });
  } catch (_) {
    // Continue local logout even if backend revocation request fails.
  }
  clearSession();
  showAuthMode();
  setGlobalStatus("Р’С‹ РІС‹С€Р»Рё РёР· СЃРёСЃС‚РµРјС‹.", "muted");
}

async function bootstrapAuthenticatedSession() {
  await loadProfile();
  showDashboardMode();
  activateTab("profile");
  applyRoleAwareTabs();
  await Promise.all([refreshSlots(), refreshBookings(), refreshPackages(), refreshLessons()]);
  renderAdminOperations();
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
    renderEmpty(elements.slotsContent, `РќРµ СѓРґР°Р»РѕСЃСЊ Р·Р°РіСЂСѓР·РёС‚СЊ СЃР»РѕС‚С‹: ${error.message}`);
  }
}

async function refreshBookings() {
  if (!state.accessToken) {
    state.bookings = [];
    renderEmpty(elements.bookingsContent, "Р’С‹РїРѕР»РЅРёС‚Рµ РІС…РѕРґ, С‡С‚РѕР±С‹ СѓРІРёРґРµС‚СЊ Р±СЂРѕРЅРёСЂРѕРІР°РЅРёСЏ.");
    return;
  }

  try {
    const page = await apiRequest("/booking/my?limit=20&offset=0");
    state.bookings = page.items ?? [];
    renderBookings(state.bookings);
  } catch (error) {
    state.bookings = [];
    renderEmpty(elements.bookingsContent, `РќРµ СѓРґР°Р»РѕСЃСЊ Р·Р°РіСЂСѓР·РёС‚СЊ Р±СЂРѕРЅРёСЂРѕРІР°РЅРёСЏ: ${error.message}`);
  }
}

async function refreshPackages() {
  if (!state.currentUser) {
    state.packages = [];
    renderEmpty(elements.packagesContent, "РџСЂРѕС„РёР»СЊ РЅРµ Р·Р°РіСЂСѓР¶РµРЅ.");
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
      "Р Р°Р·РґРµР» РїР°РєРµС‚РѕРІ РґРѕСЃС‚СѓРїРµРЅ С‚РѕР»СЊРєРѕ РґР»СЏ СЂРѕР»Рё student.",
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
    renderEmpty(elements.packagesContent, `РќРµ СѓРґР°Р»РѕСЃСЊ Р·Р°РіСЂСѓР·РёС‚СЊ РїР°РєРµС‚С‹: ${error.message}`);
    renderSlotPackageControls();
    if (state.slots.length > 0) {
      renderSlots(state.slots);
    }
  }
}

async function refreshLessons() {
  if (!state.currentUser) {
    state.lessons = [];
    renderEmpty(elements.lessonsContent, "РџСЂРѕС„РёР»СЊ РЅРµ Р·Р°РіСЂСѓР¶РµРЅ.");
    return;
  }

  if (!isTeacherRole()) {
    state.lessons = [];
    renderEmpty(elements.lessonsContent, "Р Р°Р·РґРµР» СѓСЂРѕРєРѕРІ РґРѕСЃС‚СѓРїРµРЅ С‚РѕР»СЊРєРѕ РґР»СЏ СЂРѕР»Рё teacher.");
    return;
  }

  try {
    const page = await apiRequest("/lessons/my?limit=20&offset=0");
    state.lessons = page.items ?? [];
    renderLessons(state.lessons);
  } catch (error) {
    state.lessons = [];
    renderEmpty(elements.lessonsContent, `РќРµ СѓРґР°Р»РѕСЃСЊ Р·Р°РіСЂСѓР·РёС‚СЊ СѓСЂРѕРєРё: ${error.message}`);
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
      <p class="meta"><strong>Р РѕР»СЊ:</strong> ${escapeHtml(user.role.name)}</p>
      <p class="meta"><strong>РўР°Р№РјР·РѕРЅР°:</strong> ${escapeHtml(user.timezone)}</p>
      <p class="meta"><strong>РђРєС‚РёРІРµРЅ:</strong> ${user.is_active ? "РґР°" : "РЅРµС‚"}</p>
      <p class="meta"><strong>РЎРѕР·РґР°РЅ:</strong> ${formatDateTime(user.created_at)}</p>
    </article>
  `;
}

function renderLessons(lessons) {
  if (lessons.length === 0) {
    renderEmpty(elements.lessonsContent, "РЈ РІР°СЃ РїРѕРєР° РЅРµС‚ СѓСЂРѕРєРѕРІ.");
    return;
  }

  elements.lessonsContent.innerHTML = lessons
    .map((lesson) => {
      return `
        <article class="card-item">
          <h4>РЈСЂРѕРє ${escapeHtml(lesson.id)}</h4>
          <p class="meta"><strong>РЎС‚Р°С‚СѓСЃ:</strong> ${escapeHtml(lesson.status)}</p>
          <p class="meta"><strong>Р‘СЂРѕРЅРёСЂРѕРІР°РЅРёРµ:</strong> ${escapeHtml(lesson.booking_id)}</p>
          <p class="meta"><strong>РЎС‚СѓРґРµРЅС‚:</strong> ${escapeHtml(lesson.student_id)}</p>
          <p class="meta"><strong>РќР°С‡Р°Р»Рѕ:</strong> ${formatDateTime(lesson.scheduled_start_at)}</p>
          <p class="meta"><strong>РћРєРѕРЅС‡Р°РЅРёРµ:</strong> ${formatDateTime(lesson.scheduled_end_at)}</p>
          <p class="meta"><strong>РўРµРјР°:</strong> ${escapeHtml(lesson.topic ?? "-")}</p>
        </article>
      `;
    })
    .join("");
}

function renderAdminOperations() {
  if (!isAdminRole()) {
    renderEmpty(elements.adminActionsContent, "Р Р°Р·РґРµР» admin РґРѕСЃС‚СѓРїРµРЅ С‚РѕР»СЊРєРѕ РґР»СЏ СЂРѕР»Рё admin.");
    if (elements.runExpireHoldsButton) {
      elements.runExpireHoldsButton.disabled = true;
    }
    if (elements.runExpirePackagesButton) {
      elements.runExpirePackagesButton.disabled = true;
    }
    return;
  }

  if (elements.runExpireHoldsButton) {
    elements.runExpireHoldsButton.disabled = false;
  }
  if (elements.runExpirePackagesButton) {
    elements.runExpirePackagesButton.disabled = false;
  }

  const lastHolds =
    state.adminOperations.lastExpiredHolds === null
      ? "РµС‰Рµ РЅРµ Р·Р°РїСѓСЃРєР°Р»РѕСЃСЊ"
      : String(state.adminOperations.lastExpiredHolds);
  const lastPackages =
    state.adminOperations.lastExpiredPackages === null
      ? "РµС‰Рµ РЅРµ Р·Р°РїСѓСЃРєР°Р»РѕСЃСЊ"
      : String(state.adminOperations.lastExpiredPackages);
  const updatedAt = state.adminOperations.updatedAt
    ? formatDateTime(state.adminOperations.updatedAt)
    : "-";

  elements.adminActionsContent.innerHTML = `
    <article class="card-item">
      <h4>РЎРІРѕРґРєР° admin РѕРїРµСЂР°С†РёР№</h4>
      <p class="meta"><strong>РСЃС‚РµРєС€РёС… HOLD:</strong> ${escapeHtml(lastHolds)}</p>
      <p class="meta"><strong>РСЃС‚РµРєС€РёС… РїР°РєРµС‚РѕРІ:</strong> ${escapeHtml(lastPackages)}</p>
      <p class="meta"><strong>РћР±РЅРѕРІР»РµРЅРѕ:</strong> ${escapeHtml(updatedAt)}</p>
      <p class="hint">РљРЅРѕРїРєРё РІС‹С€Рµ Р·Р°РїСѓСЃРєР°СЋС‚ backend-С‚СЂРёРіРіРµСЂС‹ РёСЃС‚РµС‡РµРЅРёСЏ.</p>
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
      return `<option value="${escapeHtml(pkg.id)}">${escapeHtml(pkg.id)} (СѓСЂРѕРєРѕРІ: ${escapeHtml(pkg.lessons_left)})</option>`;
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
    renderEmpty(elements.slotsContent, "РћС‚РєСЂС‹С‚С‹С… СЃР»РѕС‚РѕРІ РїРѕРєР° РЅРµС‚.");
    return;
  }

  const canCreateHold = isStudentRole() && getHoldEligiblePackages().length > 0;
  const cards = slots
    .map((slot) => {
      const holdAction = isStudentRole()
        ? `<div class="action-row"><button type="button" class="action-btn" data-action="hold-slot" data-slot-id="${escapeHtml(slot.id)}" ${canCreateHold ? "" : "disabled"}>Р’Р·СЏС‚СЊ РІ hold</button></div>`
        : "";

      return `
        <article class="card-item">
          <h4>РЎР»РѕС‚ ${escapeHtml(slot.id)}</h4>
          <p class="meta"><strong>РџСЂРµРїРѕРґР°РІР°С‚РµР»СЊ:</strong> ${escapeHtml(slot.teacher_id)}</p>
          <p class="meta"><strong>РќР°С‡Р°Р»Рѕ:</strong> ${formatDateTime(slot.start_at)}</p>
          <p class="meta"><strong>РћРєРѕРЅС‡Р°РЅРёРµ:</strong> ${formatDateTime(slot.end_at)}</p>
          <p class="meta"><strong>РЎС‚Р°С‚СѓСЃ:</strong> ${escapeHtml(slot.status)}</p>
          ${holdAction}
        </article>
      `;
    })
    .join("");

  const hint = isStudentRole() && !canCreateHold
    ? "<p class=\"hint\">Р”Р»СЏ hold РЅСѓР¶РµРЅ Р°РєС‚РёРІРЅС‹Р№ РїР°РєРµС‚ СЃ РѕСЃС‚Р°РІС€РёРјРёСЃСЏ СѓСЂРѕРєР°РјРё.</p>"
    : "";

  elements.slotsContent.innerHTML = `${hint}${cards}`;
}

function renderBookings(bookings) {
  if (bookings.length === 0) {
    renderEmpty(elements.bookingsContent, "РЈ РІР°СЃ РїРѕРєР° РЅРµС‚ Р±СЂРѕРЅРёСЂРѕРІР°РЅРёР№.");
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
        ? `<button type="button" class="action-btn" data-action="confirm-booking" data-booking-id="${escapeHtml(booking.id)}">РџРѕРґС‚РІРµСЂРґРёС‚СЊ</button>`
        : "";

      const cancelAction = canCancel
        ? `<button type="button" class="action-btn danger" data-action="cancel-booking" data-booking-id="${escapeHtml(booking.id)}">РћС‚РјРµРЅРёС‚СЊ</button>`
        : "";

      const cancelReason = canCancel
        ? `
          <div class="action-row">
            <input
              type="text"
              maxlength="512"
              placeholder="РџСЂРёС‡РёРЅР° РѕС‚РјРµРЅС‹ (РѕРїС†РёРѕРЅР°Р»СЊРЅРѕ)"
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
                РџРµСЂРµРЅРµСЃС‚Рё
              </button>
            </div>
          `;
        } else {
          rescheduleAction = "<p class=\"hint\">РќРµС‚ РѕС‚РєСЂС‹С‚С‹С… СЃР»РѕС‚РѕРІ РґР»СЏ РїРµСЂРµРЅРѕСЃР°.</p>";
        }
      }

      return `
        <article class="card-item">
          <h4>Р‘СЂРѕРЅРёСЂРѕРІР°РЅРёРµ ${escapeHtml(booking.id)}</h4>
          <p class="meta"><strong>РЎС‚Р°С‚СѓСЃ:</strong> ${escapeHtml(booking.status)}</p>
          <p class="meta"><strong>РЎР»РѕС‚:</strong> ${escapeHtml(booking.slot_id)}</p>
          <p class="meta"><strong>РџР°РєРµС‚:</strong> ${escapeHtml(booking.package_id ?? "-")}</p>
          <p class="meta"><strong>Hold РґРѕ:</strong> ${formatDateTime(booking.hold_expires_at)}</p>
          <p class="meta"><strong>РЎРѕР·РґР°РЅРѕ:</strong> ${formatDateTime(booking.created_at)}</p>
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
    renderEmpty(elements.packagesContent, "РЈ РІР°СЃ РїРѕРєР° РЅРµС‚ РїР°РєРµС‚РѕРІ.");
    return;
  }

  elements.packagesContent.innerHTML = packages
    .map((item) => {
      return `
        <article class="card-item">
          <h4>РџР°РєРµС‚ ${escapeHtml(item.id)}</h4>
          <p class="meta"><strong>РЎС‚Р°С‚СѓСЃ:</strong> ${escapeHtml(item.status)}</p>
          <p class="meta"><strong>РЈСЂРѕРєРѕРІ РІСЃРµРіРѕ:</strong> ${escapeHtml(item.lessons_total)}</p>
          <p class="meta"><strong>РћСЃС‚Р°Р»РѕСЃСЊ СѓСЂРѕРєРѕРІ:</strong> ${escapeHtml(item.lessons_left)}</p>
          <p class="meta"><strong>Р”РµР№СЃС‚РІСѓРµС‚ РґРѕ:</strong> ${formatDateTime(item.expires_at)}</p>
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
    setGlobalStatus("Hold РґРѕСЃС‚СѓРїРµРЅ С‚РѕР»СЊРєРѕ РґР»СЏ СЂРѕР»Рё student.", "error");
    return;
  }

  const slotId = button.dataset.slotId;
  const packageId = elements.slotPackageSelect?.value ?? "";

  if (!slotId || !packageId) {
    setGlobalStatus("Р’С‹Р±РµСЂРёС‚Рµ РїР°РєРµС‚ Рё РїРѕРІС‚РѕСЂРёС‚Рµ РїРѕРїС‹С‚РєСѓ hold.", "error");
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

    setGlobalStatus(`Hold СЃРѕР·РґР°РЅ: ${booking.id}`, "success");
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
      setGlobalStatus(`Р‘СЂРѕРЅРёСЂРѕРІР°РЅРёРµ РїРѕРґС‚РІРµСЂР¶РґРµРЅРѕ: ${bookingId}`, "success");
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

      setGlobalStatus(`Р‘СЂРѕРЅРёСЂРѕРІР°РЅРёРµ РѕС‚РјРµРЅРµРЅРѕ: ${bookingId}`, "success");
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
        setGlobalStatus("Р’С‹Р±РµСЂРёС‚Рµ РЅРѕРІС‹Р№ СЃР»РѕС‚ РґР»СЏ РїРµСЂРµРЅРѕСЃР°.", "error");
        return;
      }

      if (newSlotId === currentSlotId) {
        setGlobalStatus("РќРѕРІС‹Р№ СЃР»РѕС‚ РґРѕР»Р¶РµРЅ РѕС‚Р»РёС‡Р°С‚СЊСЃСЏ РѕС‚ С‚РµРєСѓС‰РµРіРѕ.", "error");
        return;
      }

      const newBooking = await apiRequest(`/booking/${bookingId}/reschedule`, {
        method: "POST",
        body: {
          new_slot_id: newSlotId,
        },
      });

      setGlobalStatus(`Р‘СЂРѕРЅРёСЂРѕРІР°РЅРёРµ РїРµСЂРµРЅРµСЃРµРЅРѕ. РќРѕРІС‹Р№ ID: ${newBooking.id}`, "success");
      await refreshAfterBookingMutation();
      return;
    }
  });
}

async function handleExpireHolds(event) {
  if (!isAdminRole()) {
    setGlobalStatus("РћРїРµСЂР°С†РёСЏ РґРѕСЃС‚СѓРїРЅР° С‚РѕР»СЊРєРѕ РґР»СЏ СЂРѕР»Рё admin.", "error");
    return;
  }

  const button = event.currentTarget;
  await withButtonAction(button, async () => {
    const expiredCount = await apiRequest("/booking/holds/expire", {
      method: "POST",
    });

    state.adminOperations.lastExpiredHolds = Number(expiredCount);
    state.adminOperations.updatedAt = new Date().toISOString();
    renderAdminOperations();
    setGlobalStatus(`РСЃС‚РµРєС€РёС… HOLD-Р±СЂРѕРЅРёСЂРѕРІР°РЅРёР№: ${expiredCount}`, "success");
    await Promise.all([refreshSlots(), refreshBookings()]);
  });
}

async function handleExpirePackages(event) {
  if (!isAdminRole()) {
    setGlobalStatus("РћРїРµСЂР°С†РёСЏ РґРѕСЃС‚СѓРїРЅР° С‚РѕР»СЊРєРѕ РґР»СЏ СЂРѕР»Рё admin.", "error");
    return;
  }

  const button = event.currentTarget;
  await withButtonAction(button, async () => {
    const expiredCount = await apiRequest("/billing/packages/expire", {
      method: "POST",
    });

    state.adminOperations.lastExpiredPackages = Number(expiredCount);
    state.adminOperations.updatedAt = new Date().toISOString();
    renderAdminOperations();
    setGlobalStatus(`РСЃС‚РµРєС€РёС… РїР°РєРµС‚РѕРІ: ${expiredCount}`, "success");
    await refreshPackages();
  });
}

async function refreshAfterBookingMutation() {
  await Promise.all([refreshSlots(), refreshBookings(), refreshPackages(), refreshLessons()]);
}

async function withButtonAction(button, action) {
  if (button.disabled) {
    return;
  }

  const originalText = button.textContent;
  button.disabled = true;
  button.textContent = "Р’С‹РїРѕР»РЅСЏРµС‚СЃСЏ...";

  try {
    await action();
  } catch (error) {
    setGlobalStatus(`РћС€РёР±РєР° РѕРїРµСЂР°С†РёРё: ${error.message}`, "error");
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

function translateBackendMessage(message) {
  const normalized = String(message ?? "").trim();
  if (!normalized) {
    return normalized;
  }

  const directTranslations = {
    "Not authenticated": "РўСЂРµР±СѓРµС‚СЃСЏ Р°РІС‚РѕСЂРёР·Р°С†РёСЏ.",
    "Could not validate credentials": "РќРµ СѓРґР°Р»РѕСЃСЊ РїСЂРѕРІРµСЂРёС‚СЊ СѓС‡РµС‚РЅС‹Рµ РґР°РЅРЅС‹Рµ.",
    "Invalid credentials": "РќРµРІРµСЂРЅС‹Р№ email РёР»Рё РїР°СЂРѕР»СЊ.",
    "Unauthorized": "РќРµРґРѕСЃС‚Р°С‚РѕС‡РЅРѕ РїСЂР°РІ РґР»СЏ РІС‹РїРѕР»РЅРµРЅРёСЏ РѕРїРµСЂР°С†РёРё.",
    "Access denied": "Р”РѕСЃС‚СѓРї Р·Р°РїСЂРµС‰РµРЅ.",
    "Slot not found": "РЎР»РѕС‚ РЅРµ РЅР°Р№РґРµРЅ.",
    "Slot is not available": "РЎР»РѕС‚ СЃРµР№С‡Р°СЃ РЅРµРґРѕСЃС‚СѓРїРµРЅ.",
    "Cannot book a slot in the past": "РќРµР»СЊР·СЏ Р±СЂРѕРЅРёСЂРѕРІР°С‚СЊ СЃР»РѕС‚ РІ РїСЂРѕС€Р»РѕРј.",
    "Package not found": "РџР°РєРµС‚ РЅРµ РЅР°Р№РґРµРЅ.",
    "Package does not belong to current student": "РџР°РєРµС‚ РЅРµ РїСЂРёРЅР°РґР»РµР¶РёС‚ С‚РµРєСѓС‰РµРјСѓ СЃС‚СѓРґРµРЅС‚Сѓ.",
    "Package does not belong to current user": "РџР°РєРµС‚ РЅРµ РїСЂРёРЅР°РґР»РµР¶РёС‚ С‚РµРєСѓС‰РµРјСѓ РїРѕР»СЊР·РѕРІР°С‚РµР»СЋ.",
    "Package is not active": "РџР°РєРµС‚ РЅРµ Р°РєС‚РёРІРµРЅ.",
    "Package is expired": "РЎСЂРѕРє РґРµР№СЃС‚РІРёСЏ РїР°РєРµС‚Р° РёСЃС‚РµРє.",
    "No lessons left in package": "Р’ РїР°РєРµС‚Рµ РЅРµ РѕСЃС‚Р°Р»РѕСЃСЊ СѓСЂРѕРєРѕРІ.",
    "No lessons left": "Р’ РїР°РєРµС‚Рµ РЅРµ РѕСЃС‚Р°Р»РѕСЃСЊ СѓСЂРѕРєРѕРІ.",
    "Only students can hold bookings": "РўРѕР»СЊРєРѕ СЃС‚СѓРґРµРЅС‚С‹ РјРѕРіСѓС‚ СЃРѕР·РґР°РІР°С‚СЊ HOLD-Р±СЂРѕРЅРёСЂРѕРІР°РЅРёСЏ.",
    "Booking not found": "Р‘СЂРѕРЅРёСЂРѕРІР°РЅРёРµ РЅРµ РЅР°Р№РґРµРЅРѕ.",
    "Only HOLD booking can be confirmed": "РџРѕРґС‚РІРµСЂРґРёС‚СЊ РјРѕР¶РЅРѕ С‚РѕР»СЊРєРѕ Р±СЂРѕРЅРёСЂРѕРІР°РЅРёРµ РІ СЃС‚Р°С‚СѓСЃРµ HOLD.",
    "Booking hold has expired": "Р’СЂРµРјСЏ HOLD-Р±СЂРѕРЅРёСЂРѕРІР°РЅРёСЏ РёСЃС‚РµРєР»Рѕ.",
    "Booking package is required": "Р”Р»СЏ Р±СЂРѕРЅРёСЂРѕРІР°РЅРёСЏ С‚СЂРµР±СѓРµС‚СЃСЏ РїР°РєРµС‚.",
    "Package is inactive or expired": "РџР°РєРµС‚ РЅРµР°РєС‚РёРІРµРЅ РёР»Рё СѓР¶Рµ РёСЃС‚РµРє.",
    "Booking already expired": "Р‘СЂРѕРЅРёСЂРѕРІР°РЅРёРµ СѓР¶Рµ РёСЃС‚РµРєР»Рѕ.",
    "Booking cannot be rescheduled in current status":
      "Р’ С‚РµРєСѓС‰РµРј СЃС‚Р°С‚СѓСЃРµ Р±СЂРѕРЅРёСЂРѕРІР°РЅРёРµ РЅРµР»СЊР·СЏ РїРµСЂРµРЅРµСЃС‚Рё.",
    "You cannot manage this booking": "РЈ РІР°СЃ РЅРµС‚ РїСЂР°РІ СѓРїСЂР°РІР»СЏС‚СЊ СЌС‚РёРј Р±СЂРѕРЅРёСЂРѕРІР°РЅРёРµРј.",
    "Only admin can run hold expiration": "РўРѕР»СЊРєРѕ admin РјРѕР¶РµС‚ Р·Р°РїСѓСЃРєР°С‚СЊ РёСЃС‚РµС‡РµРЅРёРµ HOLD-Р±СЂРѕРЅРёСЂРѕРІР°РЅРёР№.",
    "Only admin can expire packages": "РўРѕР»СЊРєРѕ admin РјРѕР¶РµС‚ Р·Р°РїСѓСЃРєР°С‚СЊ РёСЃС‚РµС‡РµРЅРёРµ РїР°РєРµС‚РѕРІ.",
    "Only admin can create lesson packages": "РўРѕР»СЊРєРѕ admin РјРѕР¶РµС‚ СЃРѕР·РґР°РІР°С‚СЊ РїР°РєРµС‚С‹ СѓСЂРѕРєРѕРІ.",
    "Only admin or teacher can create lessons": "РўРѕР»СЊРєРѕ admin РёР»Рё teacher РјРѕР¶РµС‚ СЃРѕР·РґР°РІР°С‚СЊ СѓСЂРѕРєРё.",
    "Only admin or teacher can update lessons": "РўРѕР»СЊРєРѕ admin РёР»Рё teacher РјРѕР¶РµС‚ РёР·РјРµРЅСЏС‚СЊ СѓСЂРѕРєРё.",
    "Teacher can update only own lessons": "Teacher РјРѕР¶РµС‚ РёР·РјРµРЅСЏС‚СЊ С‚РѕР»СЊРєРѕ СЃРІРѕРё СѓСЂРѕРєРё.",
    "Lesson not found": "РЈСЂРѕРє РЅРµ РЅР°Р№РґРµРЅ.",
  };

  if (normalized in directTranslations) {
    return directTranslations[normalized];
  }
  return normalized;
}

function translateValidationMessage(message) {
  const normalized = String(message ?? "").trim();
  if (!normalized) {
    return normalized;
  }

  const directTranslations = {
    "Field required": "РџРѕР»Рµ РѕР±СЏР·Р°С‚РµР»СЊРЅРѕ.",
    "Input should be a valid UUID": "Р’РІРµРґРёС‚Рµ РєРѕСЂСЂРµРєС‚РЅС‹Р№ UUID.",
    "Input should be a valid datetime": "Р’РІРµРґРёС‚Рµ РєРѕСЂСЂРµРєС‚РЅСѓСЋ РґР°С‚Сѓ Рё РІСЂРµРјСЏ.",
    "Input should be a valid email address": "Р’РІРµРґРёС‚Рµ РєРѕСЂСЂРµРєС‚РЅС‹Р№ email.",
  };

  if (normalized in directTranslations) {
    return directTranslations[normalized];
  }

  const minLengthMatch = normalized.match(/^String should have at least (\d+) character/);
  if (minLengthMatch) {
    return `РњРёРЅРёРјР°Р»СЊРЅР°СЏ РґР»РёРЅР°: ${minLengthMatch[1]} СЃРёРјРІРѕР»РѕРІ.`;
  }

  const maxLengthMatch = normalized.match(/^String should have at most (\d+) character/);
  if (maxLengthMatch) {
    return `РњР°РєСЃРёРјР°Р»СЊРЅР°СЏ РґР»РёРЅР°: ${maxLengthMatch[1]} СЃРёРјРІРѕР»РѕРІ.`;
  }

  return translateBackendMessage(normalized);
}

function translateValidationPath(pathItems) {
  const fieldTranslations = {
    body: "С‚РµР»Рѕ Р·Р°РїСЂРѕСЃР°",
    query: "query-РїР°СЂР°РјРµС‚СЂ",
    path: "РїСѓС‚СЊ",
    email: "email",
    password: "РїР°СЂРѕР»СЊ",
    timezone: "С‚Р°Р№РјР·РѕРЅР°",
    role: "СЂРѕР»СЊ",
    slot_id: "ID СЃР»РѕС‚Р°",
    package_id: "ID РїР°РєРµС‚Р°",
    booking_id: "ID Р±СЂРѕРЅРёСЂРѕРІР°РЅРёСЏ",
    new_slot_id: "ID РЅРѕРІРѕРіРѕ СЃР»РѕС‚Р°",
    reason: "РїСЂРёС‡РёРЅР°",
    refresh_token: "refresh token",
  };

  return pathItems.map((item) => fieldTranslations[item] ?? String(item)).join(" -> ");
}

function fallbackStatusMessage(statusCode) {
  const fallbackMessages = {
    400: "РќРµРєРѕСЂСЂРµРєС‚РЅС‹Р№ Р·Р°РїСЂРѕСЃ.",
    401: "РўСЂРµР±СѓРµС‚СЃСЏ Р°РІС‚РѕСЂРёР·Р°С†РёСЏ.",
    403: "РќРµРґРѕСЃС‚Р°С‚РѕС‡РЅРѕ РїСЂР°РІ.",
    404: "Р РµСЃСѓСЂСЃ РЅРµ РЅР°Р№РґРµРЅ.",
    409: "РљРѕРЅС„Р»РёРєС‚ РґР°РЅРЅС‹С….",
    422: "РћС€РёР±РєР° РІР°Р»РёРґР°С†РёРё Р·Р°РїСЂРѕСЃР°.",
    429: "РЎР»РёС€РєРѕРј РјРЅРѕРіРѕ Р·Р°РїСЂРѕСЃРѕРІ. РџРѕРїСЂРѕР±СѓР№С‚Рµ РїРѕР·Р¶Рµ.",
    500: "Р’РЅСѓС‚СЂРµРЅРЅСЏСЏ РѕС€РёР±РєР° СЃРµСЂРІРµСЂР°.",
  };
  return fallbackMessages[statusCode] ?? `HTTP ${statusCode}`;
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
        return `${translateValidationPath(item.loc)}: ${translateValidationMessage(message)}`;
      }

      return translateValidationMessage(message);
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
      return translateBackendMessage(payload.error.message);
    }
    if (typeof payload.detail === "string") {
      return translateBackendMessage(payload.detail);
    }
    if (typeof payload.message === "string") {
      return translateBackendMessage(payload.message);
    }
  }
  return fallbackStatusMessage(statusCode);
}

async function refreshSession() {
  try {
    const tokenPair = await apiRequest("/identity/auth/refresh", {
      method: "POST",
      auth: false,
      retryOnUnauthorized: false,
    });
    persistTokens(tokenPair);
    return true;
  } catch (_) {
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
    credentials: "include",
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
    retryOnUnauthorized
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
    moveToAuthState("РЎРµСЃСЃРёСЏ РёСЃС‚РµРєР»Р°. Р’С‹РїРѕР»РЅРёС‚Рµ РІС…РѕРґ СЃРЅРѕРІР°.");
    throw new Error("РЎРµСЃСЃРёСЏ РёСЃС‚РµРєР»Р°. Р’С‹РїРѕР»РЅРёС‚Рµ РІС…РѕРґ СЃРЅРѕРІР°.");
  }

  if (response.status === 401 && auth) {
    moveToAuthState("РЎРµСЃСЃРёСЏ РёСЃС‚РµРєР»Р°. Р’С‹РїРѕР»РЅРёС‚Рµ РІС…РѕРґ СЃРЅРѕРІР°.");
    throw new Error("РЎРµСЃСЃРёСЏ РёСЃС‚РµРєР»Р°. Р’С‹РїРѕР»РЅРёС‚Рµ РІС…РѕРґ СЃРЅРѕРІР°.");
  }

  if (!response.ok) {
    throw new Error(extractErrorMessage(payload, response.status));
  }

  return payload;
}
