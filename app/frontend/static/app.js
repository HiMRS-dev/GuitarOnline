const API_PREFIX = "/api/v1";
const ADMIN_DASHBOARD_PATH = "/admin/kpi";

const state = {
  accessToken: null,
  currentUser: null,
  slots: [],
  bookings: [],
  students: [],
  packages: [],
  packagePlans: [],
  payments: [],
  lessons: [],
  teacherSchedule: null,
  teacherScheduleError: null,
  adminOperations: {
    lastExpiredHolds: null,
    lastExpiredPackages: null,
    updatedAt: null,
  },
};

const elements = {
  layout: document.querySelector(".layout"),
  authPanel: document.querySelector(".auth-panel"),
  registerForm: document.getElementById("register-form"),
  loginForm: document.getElementById("login-form"),
  logoutButton: document.getElementById("logout-btn"),
  dashboardPanel: document.getElementById("dashboard-panel"),
  globalStatus: document.getElementById("global-status"),
  profileContent: document.getElementById("profile-content"),
  slotsContent: document.getElementById("slots-content"),
  bookingsContent: document.getElementById("bookings-content"),
  studentsContent: document.getElementById("students-content"),
  packagesContent: document.getElementById("packages-content"),
  lessonsContent: document.getElementById("lessons-content"),
  adminActionsContent: document.getElementById("admin-actions-content"),
  tabButtons: Array.from(document.querySelectorAll(".tab-btn")),
  tabContents: Array.from(document.querySelectorAll(".tab-content")),
  refreshSlotsButton: document.getElementById("refresh-slots-btn"),
  refreshBookingsButton: document.getElementById("refresh-bookings-btn"),
  refreshStudentsButton: document.getElementById("refresh-students-btn"),
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
      setGlobalStatus(`Сессия истекла: ${error.message}`, "error");
    });
    return;
  }

  showAuthMode();
  setGlobalStatus("Ожидание авторизации. Войдите или зарегистрируйтесь.", "muted");
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
  elements.refreshStudentsButton?.addEventListener("click", () => refreshStudents());
  elements.refreshPackagesButton?.addEventListener("click", () => refreshPackages());
  elements.refreshLessonsButton?.addEventListener("click", () => refreshLessons());
  elements.runExpireHoldsButton?.addEventListener("click", handleExpireHolds);
  elements.runExpirePackagesButton?.addEventListener("click", handleExpirePackages);
  elements.slotsContent?.addEventListener("click", handleSlotsActionClick);
  elements.bookingsContent?.addEventListener("click", handleBookingsActionClick);
  elements.packagesContent?.addEventListener("click", handlePackagesActionClick);
  elements.profileContent?.addEventListener("submit", handleProfileSave);
  elements.profileContent?.addEventListener("click", handleProfileActionClick);

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
  state.students = [];
  state.packages = [];
  state.packagePlans = [];
  state.payments = [];
  state.lessons = [];
  state.teacherSchedule = null;
  state.teacherScheduleError = null;
  state.adminOperations.lastExpiredHolds = null;
  state.adminOperations.lastExpiredPackages = null;
  state.adminOperations.updatedAt = null;

  if (elements.slotPackageSelect) {
    elements.slotPackageSelect.innerHTML = "";
  }
}

function moveToAuthState(message = "Сессия истекла. Выполните вход снова.") {
  clearSession();
  showAuthMode();
  setGlobalStatus(message, "error");
}

function showAuthMode() {
  if (elements.layout) {
    elements.layout.classList.remove("dashboard-only");
  }
  if (elements.authPanel) {
    elements.authPanel.hidden = false;
  }
  elements.dashboardPanel.hidden = true;
  elements.logoutButton.hidden = true;
  elements.profileContent.innerHTML = "";
  elements.slotsContent.innerHTML = "";
  elements.bookingsContent.innerHTML = "";
  elements.studentsContent.innerHTML = "";
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

function getSafePostLoginRedirectPath() {
  const path = new URLSearchParams(window.location.search).get("next");
  if (!path) {
    return null;
  }
  if (!path.startsWith("/") || path.startsWith("//")) {
    return null;
  }
  return path;
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
  if (elements.layout) {
    elements.layout.classList.add("dashboard-only");
  }
  if (elements.authPanel) {
    elements.authPanel.hidden = true;
  }
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

function isProfileEditableRole() {
  return isStudentRole() || isTeacherRole();
}

function getTabButton(tabName) {
  return elements.tabButtons.find((button) => button.dataset.tab === tabName) ?? null;
}

function syncRoleAwareLabels() {
  const bookingsButton = getTabButton("bookings");
  const bookingsHeading = document.querySelector("#tab-bookings h3");
  if (isTeacherRole()) {
    if (bookingsButton) {
      bookingsButton.textContent = "Забронированные слоты";
    }
    if (bookingsHeading) {
      bookingsHeading.textContent = "Забронированные слоты";
    }
    return;
  }

  if (bookingsButton) {
    bookingsButton.textContent = "Мои бронирования";
  }
  if (bookingsHeading) {
    bookingsHeading.textContent = "Мои бронирования";
  }
}

function isTabVisible(tabName, roleName) {
  if (!roleName) {
    return tabName === "profile";
  }

  const visibilityMap = {
    profile: ["student", "teacher", "admin"],
    slots: ["student", "teacher"],
    bookings: ["student", "teacher"],
    students: ["teacher"],
    packages: ["student"],
    lessons: [],
    "admin-ops": ["admin"],
  };

  const allowedRoles = visibilityMap[tabName] ?? [];
  return allowedRoles.includes(roleName);
}

function applyRoleAwareTabs() {
  const roleName = getCurrentRole();
  let firstVisibleTab = null;
  syncRoleAwareLabels();

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
    (pkg) =>
      pkg.status === "active" &&
      Number(pkg.lessons_left) - Number(pkg.lessons_reserved ?? 0) > 0,
  );
}

async function handleRegister(event) {
  event.preventDefault();
  const form = event.currentTarget;
  const payload = {
    email: form.email.value.trim(),
    password: form.password.value,
    timezone: form.timezone.value.trim() || "UTC",
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
    const redirectedToAdmin = await bootstrapAuthenticatedSession();
    if (!redirectedToAdmin) {
      setGlobalStatus("Вход выполнен. Данные обновлены.", "success");
    }
  } catch (error) {
    setGlobalStatus(`Ошибка входа: ${error.message}`, "error");
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
  setGlobalStatus("Вы вышли из системы.", "muted");
}

async function bootstrapAuthenticatedSession() {
  await loadProfile();
  const requestedRedirectPath = getSafePostLoginRedirectPath();
  if (isAdminRole()) {
    const redirectPath =
      requestedRedirectPath?.startsWith("/admin") ? requestedRedirectPath : ADMIN_DASHBOARD_PATH;
    setGlobalStatus("Вход выполнен. Перенаправляем в админку...", "success");
    window.location.assign(redirectPath);
    return true;
  }

  showDashboardMode();
  activateTab("profile");
  applyRoleAwareTabs();
  await Promise.all([refreshSlots(), refreshBookings(), refreshStudents(), refreshPackages()]);
  renderAdminOperations();
  return false;
}

async function refreshSlots() {
  try {
    const queryParams = new URLSearchParams();
    queryParams.set("limit", isTeacherRole() ? "50" : "20");
    queryParams.set("offset", "0");
    if (isTeacherRole() && state.currentUser?.id) {
      queryParams.set("teacher_id", state.currentUser.id);
    }

    const page = await apiRequest(`/scheduling/slots/open?${queryParams.toString()}`, {
      auth: false,
      retryOnUnauthorized: false,
    });
    state.slots = page.items ?? [];
    if (isTeacherRole()) {
      try {
        state.teacherSchedule = await apiRequest("/scheduling/teachers/me/schedule");
        state.teacherScheduleError = null;
      } catch (scheduleError) {
        state.teacherSchedule = null;
        state.teacherScheduleError = scheduleError.message;
      }
    } else {
      state.teacherSchedule = null;
      state.teacherScheduleError = null;
    }
    renderSlots(state.slots);
  } catch (error) {
    state.slots = [];
    state.teacherSchedule = null;
    state.teacherScheduleError = null;
    renderEmpty(elements.slotsContent, `Не удалось загрузить слоты: ${error.message}`);
  }
}

async function refreshBookings() {
  if (!state.accessToken) {
    state.bookings = [];
    renderEmpty(elements.bookingsContent, "Выполните вход, чтобы увидеть бронирования.");
    return;
  }

  if (isTeacherRole()) {
    try {
      const page = await apiRequest("/teacher/lessons?limit=50&offset=0");
      state.lessons = page.items ?? [];
      renderTeacherBookedSlots(state.lessons);
    } catch (error) {
      state.lessons = [];
      renderEmpty(elements.bookingsContent, `Не удалось загрузить забронированные слоты: ${error.message}`);
    }
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

async function refreshStudents() {
  if (!isTeacherRole()) {
    state.students = [];
    renderEmpty(elements.studentsContent, "Раздел учеников доступен только преподавателю.");
    return;
  }

  try {
    const page = await apiRequest("/booking/teacher/students?limit=50&offset=0");
    state.students = page.items ?? [];
    renderStudents(state.students);
  } catch (error) {
    state.students = [];
    renderEmpty(elements.studentsContent, `Не удалось загрузить учеников: ${error.message}`);
  }
}

async function refreshPackages() {
  if (!state.currentUser) {
    state.packages = [];
    state.packagePlans = [];
    state.payments = [];
    renderEmpty(elements.packagesContent, "Профиль не загружен.");
    renderSlotPackageControls();
    if (state.slots.length > 0) {
      renderSlots(state.slots);
    }
    return;
  }

  if (!isStudentRole()) {
    state.packages = [];
    state.packagePlans = [];
    state.payments = [];
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
    const [packagesPage, plansPayload, paymentsPage] = await Promise.all([
      apiRequest(`/billing/packages/students/${state.currentUser.id}?limit=50&offset=0`),
      apiRequest("/billing/plans"),
      apiRequest(`/billing/payments/students/${state.currentUser.id}?limit=50&offset=0`),
    ]);

    state.packages = packagesPage.items ?? [];
    state.packagePlans = Array.isArray(plansPayload) ? plansPayload : [];
    state.payments = paymentsPage.items ?? [];
    renderPackages(state.packages);
    renderSlotPackageControls();
    if (state.slots.length > 0) {
      renderSlots(state.slots);
    }
  } catch (error) {
    state.packages = [];
    state.packagePlans = [];
    state.payments = [];
    renderEmpty(elements.packagesContent, `Не удалось загрузить пакеты: ${error.message}`);
    renderSlotPackageControls();
    if (state.slots.length > 0) {
      renderSlots(state.slots);
    }
  }
}

async function refreshLessons() {
  if (!state.currentUser) {
    state.lessons = [];
    renderEmpty(elements.lessonsContent, "Профиль не загружен.");
    return;
  }

  if (!isTeacherRole()) {
    state.lessons = [];
    renderEmpty(elements.lessonsContent, "Раздел уроков доступен только для роли teacher.");
    return;
  }

  try {
    const page = await apiRequest("/teacher/lessons?limit=20&offset=0");
    state.lessons = page.items ?? [];
    renderLessons(state.lessons);
  } catch (error) {
    state.lessons = [];
    renderEmpty(elements.lessonsContent, `Не удалось загрузить уроки: ${error.message}`);
  }
}

async function loadProfile() {
  const user = await apiRequest("/identity/users/me");
  state.currentUser = user;
  renderProfile(user);
}

function handleProfileActionClick(event) {
  if (!(event.target instanceof Element)) {
    return;
  }

  const actionTrigger = event.target.closest("[data-profile-action]");
  if (!actionTrigger) {
    return;
  }

  if (!isProfileEditableRole()) {
    return;
  }

  const action = actionTrigger.dataset.profileAction;
  if (action === "edit") {
    if (!state.currentUser) {
      return;
    }
    renderProfile(state.currentUser, { isEditing: true });
    return;
  }

  if (action === "cancel") {
    if (!state.currentUser) {
      return;
    }
    renderProfile(state.currentUser);
  }
}

async function handleProfileSave(event) {
  const form = event.target;
  if (!form || form.id !== "profile-form") {
    return;
  }
  event.preventDefault();

  if (!isProfileEditableRole()) {
    return;
  }

  const fullNameInput = form.full_name;
  const ageInput = form.age;
  if (!fullNameInput || !ageInput) {
    return;
  }

  const normalizedFullName = fullNameInput.value.trim();
  if (!normalizedFullName) {
    setGlobalStatus("Поле ФИО обязательно.", "error");
    fullNameInput.focus();
    return;
  }

  const rawAgeValue = ageInput.value.trim();
  let normalizedAge = null;
  if (rawAgeValue) {
    const parsedAge = Number(rawAgeValue);
    const isInvalidAge = !Number.isInteger(parsedAge) || parsedAge < 1 || parsedAge > 120;
    if (isInvalidAge) {
      setGlobalStatus("Возраст должен быть целым числом от 1 до 120.", "error");
      ageInput.focus();
      return;
    }
    normalizedAge = parsedAge;
  }

  const submitButton = form.querySelector('button[type="submit"]');
  if (!submitButton) {
    return;
  }

  await withButtonAction(submitButton, async () => {
    const updatedUser = await apiRequest("/identity/users/me", {
      method: "PATCH",
      body: { full_name: normalizedFullName, age: normalizedAge },
    });
    state.currentUser = updatedUser;
    renderProfile(updatedUser);
    setGlobalStatus("Профиль сохранен.", "success");
  });
}

function renderProfile(user, options = {}) {
  const roleName = user.role?.name ?? "";
  const roleLabelByName = {
    student: "Ученик",
    teacher: "Преподаватель",
    admin: "Администратор",
  };
  const roleDisplay = (roleLabelByName[roleName] ?? roleName) || "-";
  const isEditableProfile = roleName === "student" || roleName === "teacher";
  const isEditing = isEditableProfile && options.isEditing === true;
  const adminPanelLink =
    roleName === "admin"
      ? `<p class="meta"><a href="${ADMIN_DASHBOARD_PATH}">\u041E\u0442\u043A\u0440\u044B\u0442\u044C \u0430\u0434\u043C\u0438\u043D-\u043F\u0430\u043D\u0435\u043B\u044C</a></p>`
      : "";
  const fullNameValue = user.full_name ?? "";
  const fullNameDisplay = fullNameValue.trim() ? fullNameValue : "\u043D\u0435 \u0443\u043A\u0430\u0437\u0430\u043D\u043E";
  const ageValue = user.age === null || user.age === undefined ? "" : String(user.age);
  const ageDisplay = ageValue || "\u043D\u0435 \u0443\u043A\u0430\u0437\u0430\u043D";
  const studentProfileDetails = `
      <p class="meta"><strong>\u0420\u043E\u043B\u044C:</strong> ${escapeHtml(roleDisplay)}</p>
      <p class="meta"><strong>\u0424\u0418\u041E:</strong> ${escapeHtml(fullNameDisplay)}</p>
      <p class="meta"><strong>\u0412\u043E\u0437\u0440\u0430\u0441\u0442:</strong> ${escapeHtml(ageDisplay)}</p>
  `;
  const studentProfileEditor = `
      <form id="profile-form" class="form-stack">
        <label>
          \u0424\u0418\u041E
          <input
            name="full_name"
            type="text"
            minlength="1"
            maxlength="255"
            value="${escapeHtml(fullNameValue)}"
            required
          />
        </label>
        <label>
          \u0412\u043E\u0437\u0440\u0430\u0441\u0442
          <input
            name="age"
            type="number"
            min="1"
            max="120"
            step="1"
            value="${escapeHtml(ageValue)}"
            placeholder="\u041D\u0430\u043F\u0440\u0438\u043C\u0435\u0440, 25"
          />
        </label>
        <div class="action-row">
          <button type="submit">\u0421\u043E\u0445\u0440\u0430\u043D\u0438\u0442\u044C \u043F\u0440\u043E\u0444\u0438\u043B\u044C</button>
          <button type="button" class="secondary" data-profile-action="cancel">\u041E\u0442\u043C\u0435\u043D\u0430</button>
        </div>
      </form>
      <p class="hint">\u0418\u0437\u043C\u0435\u043D\u0435\u043D\u0438\u044F \u043F\u0440\u043E\u0444\u0438\u043B\u044F \u0441\u043E\u0445\u0440\u0430\u043D\u044F\u044E\u0442\u0441\u044F \u0432 \u0431\u0430\u0437\u0435 \u0434\u0430\u043D\u043D\u044B\u0445.</p>
  `;
  const studentProfileViewActions = `
      <div class="action-row">
        <button type="button" class="secondary" data-profile-action="edit">\u0418\u0437\u043C\u0435\u043D\u0438\u0442\u044C</button>
      </div>
  `;
  const nonStudentProfileDetails = `
      <p class="meta"><strong>ID:</strong> ${escapeHtml(user.id ?? "-")}</p>
      <p class="meta"><strong>\u0420\u043E\u043B\u044C:</strong> ${escapeHtml(roleDisplay)}</p>
  `;
  const roleSpecificSection = isEditableProfile
    ? isEditing
      ? studentProfileEditor
      : `${studentProfileDetails}${studentProfileViewActions}`
    : nonStudentProfileDetails;

  elements.profileContent.innerHTML = `
    <article class="card-item">
      <h4>${escapeHtml(user.full_name || user.email)}</h4>
      <p class="meta"><strong>\u041B\u043E\u0433\u0438\u043D:</strong> ${escapeHtml(user.email)}</p>
      <p class="meta"><strong>\u0422\u0430\u0439\u043C\u0437\u043E\u043D\u0430:</strong> ${escapeHtml(user.timezone)}</p>
      <p class="meta"><strong>\u0410\u043A\u0442\u0438\u0432\u0435\u043D:</strong> ${user.is_active ? "\u0434\u0430" : "\u043D\u0435\u0442"}</p>
      <p class="meta"><strong>\u0421\u043E\u0437\u0434\u0430\u043D:</strong> ${formatDateTime(user.created_at)}</p>
      ${adminPanelLink}
      ${roleSpecificSection}
    </article>
  `;
}

function renderLessons(lessons) {
  if (lessons.length === 0) {
    renderEmpty(elements.lessonsContent, "У вас пока нет уроков.");
    return;
  }

  elements.lessonsContent.innerHTML = lessons
    .map((lesson) => {
      return `
        <article class="card-item">
          <h4>Урок ${escapeHtml(lesson.id)}</h4>
          <p class="meta"><strong>Статус:</strong> ${escapeHtml(lesson.status)}</p>
          <p class="meta"><strong>Бронирование:</strong> ${escapeHtml(lesson.booking_id)}</p>
          <p class="meta"><strong>Студент:</strong> ${escapeHtml(lesson.student_id)}</p>
          <p class="meta"><strong>Начало:</strong> ${formatDateTime(lesson.scheduled_start_at)}</p>
          <p class="meta"><strong>Окончание:</strong> ${formatDateTime(lesson.scheduled_end_at)}</p>
          <p class="meta"><strong>Тема:</strong> ${escapeHtml(lesson.topic ?? "-")}</p>
        </article>
      `;
    })
    .join("");
}

function renderAdminOperations() {
  if (!isAdminRole()) {
    renderEmpty(
      elements.adminActionsContent,
      "Раздел операций администратора доступен только для роли admin.",
    );
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
      ? "еще не запускалось"
      : String(state.adminOperations.lastExpiredHolds);
  const lastPackages =
    state.adminOperations.lastExpiredPackages === null
      ? "еще не запускалось"
      : String(state.adminOperations.lastExpiredPackages);
  const updatedAt = state.adminOperations.updatedAt
    ? formatDateTime(state.adminOperations.updatedAt)
    : "-";

  elements.adminActionsContent.innerHTML = `
    <article class="card-item">
      <h4>Сводка операций администратора</h4>
      <p class="meta"><strong>Истекших HOLD:</strong> ${escapeHtml(lastHolds)}</p>
      <p class="meta"><strong>Истекших пакетов:</strong> ${escapeHtml(lastPackages)}</p>
      <p class="meta"><strong>Обновлено:</strong> ${escapeHtml(updatedAt)}</p>
      <p class="hint">Кнопки выше запускают backend-триггеры истечения.</p>
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
      const availableLessons = Number(pkg.lessons_left) - Number(pkg.lessons_reserved ?? 0);
      return `<option value="${escapeHtml(pkg.id)}">${escapeHtml(pkg.id)} (доступно уроков: ${escapeHtml(availableLessons)})</option>`;
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

  if (isTeacherRole()) {
    renderTeacherOpenSlots(slots);
    return;
  }

  if (slots.length === 0) {
    elements.slotsContent.innerHTML = `
      <div class="empty-note">У вас пока нет открытых слотов. Добавьте рабочие часы или дождитесь генерации слотов.</div>
    `;
    return;
  }

  const resolveTeacherDisplayName = (slot) => {
    const fullName = typeof slot.teacher_full_name === "string" ? slot.teacher_full_name.trim() : "";
    if (fullName.length > 0) {
      return fullName;
    }
    return String(slot.teacher_id);
  };

  const teacherStats = new Map();
  for (const slot of slots) {
    const teacherId = String(slot.teacher_id);
    const existing = teacherStats.get(teacherId) ?? {
      count: 0,
      nextStartAt: null,
      displayName: resolveTeacherDisplayName(slot),
    };
    existing.count += 1;
    if (existing.displayName === teacherId) {
      existing.displayName = resolveTeacherDisplayName(slot);
    }
    if (!existing.nextStartAt || new Date(slot.start_at).getTime() < new Date(existing.nextStartAt).getTime()) {
      existing.nextStartAt = slot.start_at;
    }
    teacherStats.set(teacherId, existing);
  }

  const teacherOverview = Array.from(teacherStats.entries())
    .sort((left, right) => {
      const byCount = right[1].count - left[1].count;
      if (byCount !== 0) {
        return byCount;
      }
      return left[1].displayName.localeCompare(right[1].displayName);
    })
    .map(([, stats]) => {
      return `
        <article class="card-item">
          <h4>Преподаватель ${escapeHtml(stats.displayName)}</h4>
          <p class="meta"><strong>Свободных окон:</strong> ${escapeHtml(stats.count)}</p>
          <p class="meta"><strong>Ближайшее окно:</strong> ${formatDateTime(stats.nextStartAt)}</p>
        </article>
      `;
    })
    .join("");

  const canCreateHold = isStudentRole() && getHoldEligiblePackages().length > 0;
  const cards = slots
    .map((slot) => {
      const holdAction = isStudentRole()
        ? `<div class="action-row"><button type="button" class="action-btn" data-action="hold-slot" data-slot-id="${escapeHtml(slot.id)}" ${canCreateHold ? "" : "disabled"}>Взять в hold</button></div>`
        : "";
      const holdRangeControls = isStudentRole()
        ? `
          <div class="action-row">
            <label>
              С
              <input
                type="datetime-local"
                data-role="hold-start-at"
                data-slot-id="${escapeHtml(slot.id)}"
                value="${escapeHtml(formatDateTimeInputValue(slot.start_at))}"
              />
            </label>
            <label>
              До
              <input
                type="datetime-local"
                data-role="hold-end-at"
                data-slot-id="${escapeHtml(slot.id)}"
                value="${escapeHtml(formatDateTimeInputValue(slot.end_at))}"
              />
            </label>
          </div>
        `
        : "";

      return `
        <article class="card-item">
          <h4>Слот ${escapeHtml(slot.id)}</h4>
          <p class="meta"><strong>Преподаватель:</strong> ${escapeHtml(resolveTeacherDisplayName(slot))}</p>
          <p class="meta"><strong>Начало:</strong> ${formatDateTime(slot.start_at)}</p>
          <p class="meta"><strong>Окончание:</strong> ${formatDateTime(slot.end_at)}</p>
          <p class="meta"><strong>Статус:</strong> ${escapeHtml(slot.status)}</p>
          ${holdRangeControls}
          ${holdAction}
        </article>
      `;
    })
    .join("");

  const holdHint = isStudentRole() && !canCreateHold
    ? '<p class="hint">Для hold нужен активный пакет с оставшимися уроками.</p>'
    : "";

  elements.slotsContent.innerHTML = `
    <article class="card-item">
      <h4>Свободные окна по преподавателям</h4>
      <p class="meta"><strong>Всего преподавателей:</strong> ${escapeHtml(teacherStats.size)}</p>
      <p class="meta"><strong>Всего доступных слотов:</strong> ${escapeHtml(slots.length)}</p>
    </article>
    ${teacherOverview}
    ${holdHint}
    ${cards}
  `;
}

function formatScheduleWeekday(weekday) {
  const labels = ["Понедельник", "Вторник", "Среда", "Четверг", "Пятница", "Суббота", "Воскресенье"];
  const value = Number(weekday);
  if (!Number.isInteger(value) || value < 0 || value > 6) {
    return `День ${escapeHtml(weekday)}`;
  }
  return labels[value];
}

function formatScheduleLocalTime(value) {
  if (value === null || value === undefined) {
    return "-";
  }
  const normalized = String(value).trim();
  if (!normalized) {
    return "-";
  }
  if (normalized.includes(":")) {
    return normalized.slice(0, 5);
  }
  return normalized;
}

function renderTeacherWorkingHoursCard() {
  const schedule = state.teacherSchedule;
  const scheduleError = state.teacherScheduleError;

  if (scheduleError) {
    return `
      <article class="card-item">
        <h4>Рабочие часы преподавателя</h4>
        <p class="hint">Не удалось загрузить рабочие часы: ${escapeHtml(scheduleError)}</p>
      </article>
    `;
  }

  const timezoneLabel = schedule?.timezone ?? state.currentUser?.timezone ?? "-";
  const windows = Array.isArray(schedule?.windows) ? schedule.windows : [];

  if (windows.length === 0) {
    return `
      <article class="card-item">
        <h4>Рабочие часы преподавателя</h4>
        <p class="meta"><strong>Таймзона:</strong> ${escapeHtml(timezoneLabel)}</p>
        <p class="hint">Рабочие часы пока не заданы администратором.</p>
      </article>
    `;
  }

  const windowsMarkup = windows
    .map((window) => {
      return `<p class="meta"><strong>${escapeHtml(formatScheduleWeekday(window.weekday))}:</strong> ${escapeHtml(formatScheduleLocalTime(window.start_local_time))} - ${escapeHtml(formatScheduleLocalTime(window.end_local_time))}</p>`;
    })
    .join("");

  return `
    <article class="card-item">
      <h4>Рабочие часы преподавателя</h4>
      <p class="meta"><strong>Таймзона:</strong> ${escapeHtml(timezoneLabel)}</p>
      ${windowsMarkup}
    </article>
  `;
}

function renderTeacherOpenSlots(slots) {
  const workingHoursCard = renderTeacherWorkingHoursCard();

  if (slots.length === 0) {
    elements.slotsContent.innerHTML = `
      <div class="empty-note">У вас пока нет открытых слотов. Добавьте рабочие часы или дождитесь генерации слотов.</div>
    `;
    return;
  }

  const sortedSlots = [...slots].sort(
    (left, right) => new Date(left.start_at).getTime() - new Date(right.start_at).getTime(),
  );
  const nextStartAt = sortedSlots[0]?.start_at ?? null;

  const slotCards = sortedSlots
    .map((slot) => {
      return `
        <article class="card-item">
          <h4>Слот ${escapeHtml(slot.id)}</h4>
          <p class="meta"><strong>Начало:</strong> ${formatDateTime(slot.start_at)}</p>
          <p class="meta"><strong>Окончание:</strong> ${formatDateTime(slot.end_at)}</p>
          <p class="meta"><strong>Статус:</strong> ${escapeHtml(slot.status)}</p>
        </article>
      `;
    })
    .join("");

  elements.slotsContent.innerHTML = `
    <article class="card-item">
      <h4>Мои открытые слоты</h4>
      <p class="meta"><strong>Всего открытых слотов:</strong> ${escapeHtml(sortedSlots.length)}</p>
      <p class="meta"><strong>Ближайший слот:</strong> ${formatDateTime(nextStartAt)}</p>
    </article>
    ${slotCards}
  `;
}

function renderBookings(bookings) {
  if (isTeacherRole()) {
    renderTeacherBookedSlots(bookings);
    return;
  }

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

function renderTeacherBookedSlots(lessons) {
  if (lessons.length === 0) {
    renderEmpty(elements.bookingsContent, "У вас пока нет забронированных слотов.");
    return;
  }

  const sortedLessons = [...lessons].sort(
    (left, right) =>
      new Date(left.scheduled_start_at).getTime() - new Date(right.scheduled_start_at).getTime(),
  );

  const cards = sortedLessons
    .map((lesson) => {
      return `
        <article class="card-item">
          <h4>Бронирование ${escapeHtml(lesson.booking_id ?? lesson.id)}</h4>
          <p class="meta"><strong>Студент:</strong> ${escapeHtml(lesson.student_id)}</p>
          <p class="meta"><strong>Слот:</strong> ${formatDateTime(lesson.scheduled_start_at)} - ${formatDateTime(lesson.scheduled_end_at)}</p>
          <p class="meta"><strong>Статус урока:</strong> ${escapeHtml(lesson.status)}</p>
          <p class="meta"><strong>Тема:</strong> ${escapeHtml(lesson.topic ?? "-")}</p>
        </article>
      `;
    })
    .join("");

  elements.bookingsContent.innerHTML = `
    <article class="card-item">
      <h4>Забронированные слоты</h4>
      <p class="meta"><strong>Всего слотов:</strong> ${escapeHtml(sortedLessons.length)}</p>
    </article>
    ${cards}
  `;
}

function renderStudents(students) {
  if (students.length === 0) {
    renderEmpty(elements.studentsContent, "Активных учеников пока нет.");
    return;
  }

  const studentsMarkup = students
    .map((student) => {
      const packages = Array.isArray(student.packages) ? student.packages : [];
      const packageMarkup = packages.length === 0
        ? "<p class=\"hint\">Активных пакетов нет.</p>"
        : packages
            .map((pkg) => {
              return `
                <article class="card-item">
                  <h4>Пакет ${escapeHtml(pkg.package_id)}</h4>
                  <p class="meta"><strong>Статус:</strong> ${escapeHtml(pkg.status)}</p>
                  <p class="meta"><strong>Всего уроков:</strong> ${escapeHtml(pkg.lessons_total)}</p>
                  <p class="meta"><strong>Осталось:</strong> ${escapeHtml(pkg.lessons_left)}</p>
                  <p class="meta"><strong>В резерве:</strong> ${escapeHtml(pkg.lessons_reserved)}</p>
                  <p class="meta"><strong>Доступно:</strong> ${escapeHtml(pkg.lessons_available)}</p>
                  <p class="meta"><strong>Действует до:</strong> ${formatDateTime(pkg.expires_at)}</p>
                </article>
              `;
            })
            .join("");

      return `
        <article class="card-item">
          <h4>${escapeHtml(student.student_full_name || student.student_email)}</h4>
          <p class="meta"><strong>Email:</strong> ${escapeHtml(student.student_email)}</p>
          <p class="meta"><strong>ID:</strong> ${escapeHtml(student.student_id)}</p>
          <p class="meta"><strong>Активных бронирований:</strong> ${escapeHtml(student.active_bookings_count)}</p>
          <p class="meta"><strong>Последнее бронирование:</strong> ${formatDateTime(student.last_booking_at)}</p>
        </article>
        ${packageMarkup}
      `;
    })
    .join("");

  elements.studentsContent.innerHTML = `
    <article class="card-item">
      <h4>Активные ученики</h4>
      <p class="meta"><strong>Всего учеников:</strong> ${escapeHtml(students.length)}</p>
    </article>
    ${studentsMarkup}
  `;
}

function renderPackages(packages) {
  const totalLessonsPurchased = packages.reduce((sum, item) => sum + Number(item.lessons_total ?? 0), 0);
  const totalLessonsLeft = packages.reduce((sum, item) => sum + Number(item.lessons_left ?? 0), 0);
  const totalLessonsReserved = packages.reduce((sum, item) => sum + Number(item.lessons_reserved ?? 0), 0);
  const activePackagesCount = packages.filter((item) => String(item.status).toLowerCase() === "active").length;

  const summary = `
    <article class="card-item">
      <h4>Сводка по пакетам</h4>
      <p class="meta"><strong>Пакетов куплено:</strong> ${escapeHtml(packages.length)}</p>
      <p class="meta"><strong>Уроков куплено:</strong> ${escapeHtml(totalLessonsPurchased)}</p>
      <p class="meta"><strong>Уроков осталось:</strong> ${escapeHtml(totalLessonsLeft)}</p>
      <p class="meta"><strong>В резерве:</strong> ${escapeHtml(totalLessonsReserved)}</p>
      <p class="meta"><strong>Активных пакетов:</strong> ${escapeHtml(activePackagesCount)}</p>
    </article>
  `;

  const plansMarkup = state.packagePlans.length === 0
    ? '<div class="empty-note">Тарифы для покупки временно недоступны.</div>'
    : state.packagePlans
        .map((plan) => {
          const priceLabel = `${plan.price_amount} ${plan.price_currency}`;
          return `
            <article class="card-item">
              <h4>${escapeHtml(plan.title)}</h4>
              <p class="meta">${escapeHtml(plan.description ?? "")}</p>
              <p class="meta"><strong>Уроков:</strong> ${escapeHtml(plan.lessons_total)}</p>
              <p class="meta"><strong>Срок:</strong> ${escapeHtml(plan.duration_days)} дней</p>
              <p class="meta"><strong>Цена:</strong> ${escapeHtml(priceLabel)}</p>
              <div class="action-row">
                <button
                  type="button"
                  class="action-btn"
                  data-action="purchase-plan"
                  data-plan-id="${escapeHtml(plan.id)}"
                >
                  Купить пакет
                </button>
              </div>
            </article>
          `;
        })
        .join("");

  const packageListMarkup = packages.length === 0
    ? '<div class="empty-note">У вас пока нет пакетов.</div>'
    : packages
        .map((item) => {
          const packagePrice =
            item.price_amount === null || item.price_amount === undefined
              ? "-"
              : `${item.price_amount} ${item.price_currency ?? ""}`.trim();
          return `
            <article class="card-item">
              <h4>Пакет ${escapeHtml(item.id)}</h4>
              <p class="meta"><strong>Статус:</strong> ${escapeHtml(item.status)}</p>
              <p class="meta"><strong>Уроков всего:</strong> ${escapeHtml(item.lessons_total)}</p>
              <p class="meta"><strong>Осталось уроков:</strong> ${escapeHtml(item.lessons_left)}</p>
              <p class="meta"><strong>В резерве:</strong> ${escapeHtml(item.lessons_reserved)}</p>
              <p class="meta"><strong>Стоимость:</strong> ${escapeHtml(packagePrice)}</p>
              <p class="meta"><strong>Действует до:</strong> ${formatDateTime(item.expires_at)}</p>
            </article>
          `;
        })
        .join("");

  const paymentsMarkup = state.payments.length === 0
    ? '<div class="empty-note">История покупок пока пустая.</div>'
    : state.payments
        .map((payment) => {
          const amountLabel = `${payment.amount} ${payment.currency}`;
          return `
            <article class="card-item">
              <h4>Платеж ${escapeHtml(payment.id)}</h4>
              <p class="meta"><strong>Пакет:</strong> ${escapeHtml(payment.package_id)}</p>
              <p class="meta"><strong>Статус:</strong> ${escapeHtml(payment.status)}</p>
              <p class="meta"><strong>Сумма:</strong> ${escapeHtml(amountLabel)}</p>
              <p class="meta"><strong>Провайдер:</strong> ${escapeHtml(payment.provider_name)}</p>
              <p class="meta"><strong>Оплачен:</strong> ${formatDateTime(payment.paid_at)}</p>
              <p class="meta"><strong>Создан:</strong> ${formatDateTime(payment.created_at)}</p>
            </article>
          `;
        })
        .join("");

  elements.packagesContent.innerHTML = `
    ${summary}
    <article class="card-item">
      <h4>Покупка пакетов</h4>
      <p class="meta">Выберите тариф и купите пакет занятий.</p>
    </article>
    ${plansMarkup}
    <article class="card-item">
      <h4>Мои пакеты</h4>
      <p class="meta">Текущие и архивные пакеты занятий.</p>
    </article>
    ${packageListMarkup}
    <article class="card-item">
      <h4>История покупок</h4>
      <p class="meta">Все ваши платежи по пакетам.</p>
    </article>
    ${paymentsMarkup}
  `;
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

async function handlePackagesActionClick(event) {
  const button = event.target.closest("button[data-action]");
  if (!button) {
    return;
  }

  const action = button.dataset.action;
  if (action !== "purchase-plan") {
    return;
  }

  if (!isStudentRole()) {
    setGlobalStatus("Покупка пакетов доступна только для роли student.", "error");
    return;
  }

  const planId = button.dataset.planId ?? "";
  if (!planId) {
    setGlobalStatus("Не удалось определить выбранный тариф.", "error");
    return;
  }

  await withButtonAction(button, async () => {
    const purchase = await apiRequest("/billing/packages/purchase", {
      method: "POST",
      body: {
        plan_id: planId,
      },
    });

    setGlobalStatus(`Пакет куплен: ${purchase.package.id}`, "success");
    await refreshAfterBillingMutation();
  });
}

async function handleExpireHolds(event) {
  if (!isAdminRole()) {
    setGlobalStatus("Операция доступна только для роли admin.", "error");
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
    setGlobalStatus(`Истекших HOLD-бронирований: ${expiredCount}`, "success");
    await Promise.all([refreshSlots(), refreshBookings()]);
  });
}

async function handleExpirePackages(event) {
  if (!isAdminRole()) {
    setGlobalStatus("Операция доступна только для роли admin.", "error");
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
    setGlobalStatus(`Истекших пакетов: ${expiredCount}`, "success");
    await refreshPackages();
  });
}

async function refreshAfterBookingMutation() {
  await Promise.all([refreshSlots(), refreshBookings(), refreshPackages(), refreshLessons()]);
}

async function refreshAfterBillingMutation() {
  await Promise.all([refreshSlots(), refreshPackages()]);
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

function formatDateTimeInputValue(value) {
  if (!value) {
    return "";
  }
  const date = new Date(value);
  if (Number.isNaN(date.getTime())) {
    return "";
  }

  const pad = (part) => String(part).padStart(2, "0");
  return `${date.getFullYear()}-${pad(date.getMonth() + 1)}-${pad(date.getDate())}T${pad(date.getHours())}:${pad(date.getMinutes())}`;
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
    "Not authenticated": "Требуется авторизация.",
    "Could not validate credentials": "Не удалось проверить учетные данные.",
    "Invalid credentials": "Неверный email или пароль.",
    "Unauthorized": "Недостаточно прав для выполнения операции.",
    "Access denied": "Доступ запрещен.",
    "Slot not found": "Слот не найден.",
    "Slot is not available": "Слот сейчас недоступен.",
    "Cannot book a slot in the past": "Нельзя бронировать слот в прошлом.",
    "Package not found": "Пакет не найден.",
    "Package does not belong to current student": "Пакет не принадлежит текущему студенту.",
    "Package does not belong to current user": "Пакет не принадлежит текущему пользователю.",
    "Package plan not found": "Выбранный тариф не найден.",
    "Package is not active": "Пакет не активен.",
    "Package is expired": "Срок действия пакета истек.",
    "No lessons left in package": "В пакете не осталось уроков.",
    "No lessons left": "В пакете не осталось уроков.",
    "Only students can purchase packages": "Покупка пакетов доступна только студентам.",
    "Only students can hold bookings": "Только студенты могут создавать HOLD-бронирования.",
    "Booking not found": "Бронирование не найдено.",
    "Only HOLD booking can be confirmed": "Подтвердить можно только бронирование в статусе HOLD.",
    "Booking hold has expired": "Время HOLD-бронирования истекло.",
    "Booking package is required": "Для бронирования требуется пакет.",
    "Package is inactive or expired": "Пакет неактивен или уже истек.",
    "Booking already expired": "Бронирование уже истекло.",
    "Booking cannot be rescheduled in current status":
      "В текущем статусе бронирование нельзя перенести.",
    "You cannot manage this booking": "У вас нет прав управлять этим бронированием.",
    "Only admin can run hold expiration": "Только admin может запускать истечение HOLD-бронирований.",
    "Only admin can expire packages": "Только admin может запускать истечение пакетов.",
    "Only teacher can list own students": "Только преподаватель может просматривать список своих учеников.",
    "Only admin can create lesson packages": "Только admin может создавать пакеты уроков.",
    "Only admin or teacher can create lessons": "Только admin или teacher может создавать уроки.",
    "Only admin or teacher can update lessons": "Только admin или teacher может изменять уроки.",
    "Teacher can update only own lessons": "Teacher может изменять только свои уроки.",
    "Lesson not found": "Урок не найден.",
    "Full name cannot be empty": "\u041F\u043E\u043B\u0435 \u0424\u0418\u041E \u043E\u0431\u044F\u0437\u0430\u0442\u0435\u043B\u044C\u043D\u043E.",
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
    "Field required": "Поле обязательно.",
    "Input should be a valid UUID": "Введите корректный UUID.",
    "Input should be a valid datetime": "Введите корректную дату и время.",
    "Input should be a valid email address": "Введите корректный email.",
  };

  if (normalized in directTranslations) {
    return directTranslations[normalized];
  }

  const minLengthMatch = normalized.match(/^String should have at least (\d+) character/);
  if (minLengthMatch) {
    return `Минимальная длина: ${minLengthMatch[1]} символов.`;
  }

  const maxLengthMatch = normalized.match(/^String should have at most (\d+) character/);
  if (maxLengthMatch) {
    return `Максимальная длина: ${maxLengthMatch[1]} символов.`;
  }

  return translateBackendMessage(normalized);
}

function translateValidationPath(pathItems) {
  const fieldTranslations = {
    body: "тело запроса",
    query: "query-параметр",
    path: "путь",
    email: "email",
    password: "пароль",
    full_name: "\u0424\u0418\u041E",
    age: "\u0432\u043E\u0437\u0440\u0430\u0441\u0442",
    timezone: "таймзона",
    role: "роль",
    slot_id: "ID слота",
    package_id: "ID пакета",
    booking_id: "ID бронирования",
    new_slot_id: "ID нового слота",
    reason: "причина",
    refresh_token: "refresh token",
  };

  return pathItems.map((item) => fieldTranslations[item] ?? String(item)).join(" -> ");
}

function fallbackStatusMessage(statusCode) {
  const fallbackMessages = {
    400: "Некорректный запрос.",
    401: "Требуется авторизация.",
    403: "Недостаточно прав.",
    404: "Ресурс не найден.",
    409: "Конфликт данных.",
    422: "Ошибка валидации запроса.",
    429: "Слишком много запросов. Попробуйте позже.",
    500: "Внутренняя ошибка сервера.",
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
    moveToAuthState("Сессия истекла. Выполните вход снова.");
    throw new Error("Сессия истекла. Выполните вход снова.");
  }

  if (response.status === 401 && auth) {
    moveToAuthState("Сессия истекла. Выполните вход снова.");
    throw new Error("Сессия истекла. Выполните вход снова.");
  }

  if (!response.ok) {
    throw new Error(extractErrorMessage(payload, response.status));
  }

  return payload;
}
