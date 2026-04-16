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
      setGlobalStatus(`Р РЋР ВµРЎРѓРЎРѓР С‘РЎРЏ Р С‘РЎРѓРЎвЂљР ВµР С”Р В»Р В°: ${error.message}`, "error");
    });
    return;
  }

  showAuthMode();
  setGlobalStatus("Р С›Р В¶Р С‘Р Т‘Р В°Р Р…Р С‘Р Вµ Р В°Р Р†РЎвЂљР С•РЎР‚Р С‘Р В·Р В°РЎвЂ Р С‘Р С‘. Р вЂ™Р С•Р в„–Р Т‘Р С‘РЎвЂљР Вµ Р С‘Р В»Р С‘ Р В·Р В°РЎР‚Р ВµР С–Р С‘РЎРѓРЎвЂљРЎР‚Р С‘РЎР‚РЎС“Р в„–РЎвЂљР ВµРЎРѓРЎРЉ.", "muted");
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

function moveToAuthState(message = "Р РЋР ВµРЎРѓРЎРѓР С‘РЎРЏ Р С‘РЎРѓРЎвЂљР ВµР С”Р В»Р В°. Р вЂ™РЎвЂ№Р С—Р С•Р В»Р Р…Р С‘РЎвЂљР Вµ Р Р†РЎвЂ¦Р С•Р Т‘ РЎРѓР Р…Р С•Р Р†Р В°.") {
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
      bookingsButton.textContent = "Р вЂ”Р В°Р В±РЎР‚Р С•Р Р…Р С‘РЎР‚Р С•Р Р†Р В°Р Р…Р Р…РЎвЂ№Р Вµ РЎРѓР В»Р С•РЎвЂљРЎвЂ№";
    }
    if (bookingsHeading) {
      bookingsHeading.textContent = "Р вЂ”Р В°Р В±РЎР‚Р С•Р Р…Р С‘РЎР‚Р С•Р Р†Р В°Р Р…Р Р…РЎвЂ№Р Вµ РЎРѓР В»Р С•РЎвЂљРЎвЂ№";
    }
    return;
  }

  if (bookingsButton) {
    bookingsButton.textContent = "Р СљР С•Р С‘ Р В±РЎР‚Р С•Р Р…Р С‘РЎР‚Р С•Р Р†Р В°Р Р…Р С‘РЎРЏ";
  }
  if (bookingsHeading) {
    bookingsHeading.textContent = "Р СљР С•Р С‘ Р В±РЎР‚Р С•Р Р…Р С‘РЎР‚Р С•Р Р†Р В°Р Р…Р С‘РЎРЏ";
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
    setGlobalStatus("Р С’Р С”Р С”Р В°РЎС“Р Р…РЎвЂљ РЎРѓР С•Р В·Р Т‘Р В°Р Р…. Р СћР ВµР С—Р ВµРЎР‚РЎРЉ Р Р†РЎвЂ№Р С—Р С•Р В»Р Р…Р С‘РЎвЂљР Вµ Р Р†РЎвЂ¦Р С•Р Т‘.", "success");
  } catch (error) {
    setGlobalStatus(`Р С›РЎв‚¬Р С‘Р В±Р С”Р В° РЎР‚Р ВµР С–Р С‘РЎРѓРЎвЂљРЎР‚Р В°РЎвЂ Р С‘Р С‘: ${error.message}`, "error");
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
      setGlobalStatus("Р вЂ™РЎвЂ¦Р С•Р Т‘ Р Р†РЎвЂ№Р С—Р С•Р В»Р Р…Р ВµР Р…. Р вЂќР В°Р Р…Р Р…РЎвЂ№Р Вµ Р С•Р В±Р Р…Р С•Р Р†Р В»Р ВµР Р…РЎвЂ№.", "success");
    }
  } catch (error) {
    setGlobalStatus(`Р С›РЎв‚¬Р С‘Р В±Р С”Р В° Р Р†РЎвЂ¦Р С•Р Т‘Р В°: ${error.message}`, "error");
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
  setGlobalStatus("Р вЂ™РЎвЂ№ Р Р†РЎвЂ№РЎв‚¬Р В»Р С‘ Р С‘Р В· РЎРѓР С‘РЎРѓРЎвЂљР ВµР СРЎвЂ№.", "muted");
}

async function bootstrapAuthenticatedSession() {
  await loadProfile();
  const requestedRedirectPath = getSafePostLoginRedirectPath();
  if (isAdminRole()) {
    const redirectPath =
      requestedRedirectPath?.startsWith("/admin") ? requestedRedirectPath : ADMIN_DASHBOARD_PATH;
    setGlobalStatus("Р вЂ™РЎвЂ¦Р С•Р Т‘ Р Р†РЎвЂ№Р С—Р С•Р В»Р Р…Р ВµР Р…. Р СџР ВµРЎР‚Р ВµР Р…Р В°Р С—РЎР‚Р В°Р Р†Р В»РЎРЏР ВµР С Р Р† Р В°Р Т‘Р СР С‘Р Р…Р С”РЎС“...", "success");
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
    renderEmpty(elements.slotsContent, `Р СњР Вµ РЎС“Р Т‘Р В°Р В»Р С•РЎРѓРЎРЉ Р В·Р В°Р С–РЎР‚РЎС“Р В·Р С‘РЎвЂљРЎРЉ РЎРѓР В»Р С•РЎвЂљРЎвЂ№: ${error.message}`);
  }
}

async function refreshBookings() {
  if (!state.accessToken) {
    state.bookings = [];
    renderEmpty(elements.bookingsContent, "Р вЂ™РЎвЂ№Р С—Р С•Р В»Р Р…Р С‘РЎвЂљР Вµ Р Р†РЎвЂ¦Р С•Р Т‘, РЎвЂЎРЎвЂљР С•Р В±РЎвЂ№ РЎС“Р Р†Р С‘Р Т‘Р ВµРЎвЂљРЎРЉ Р В±РЎР‚Р С•Р Р…Р С‘РЎР‚Р С•Р Р†Р В°Р Р…Р С‘РЎРЏ.");
    return;
  }

  if (isTeacherRole()) {
    try {
      const page = await apiRequest("/teacher/lessons?limit=50&offset=0");
      state.lessons = page.items ?? [];
      renderTeacherBookedSlots(state.lessons);
    } catch (error) {
      state.lessons = [];
      renderEmpty(elements.bookingsContent, `Р СњР Вµ РЎС“Р Т‘Р В°Р В»Р С•РЎРѓРЎРЉ Р В·Р В°Р С–РЎР‚РЎС“Р В·Р С‘РЎвЂљРЎРЉ Р В·Р В°Р В±РЎР‚Р С•Р Р…Р С‘РЎР‚Р С•Р Р†Р В°Р Р…Р Р…РЎвЂ№Р Вµ РЎРѓР В»Р С•РЎвЂљРЎвЂ№: ${error.message}`);
    }
    return;
  }

  try {
    const page = await apiRequest("/booking/my?limit=20&offset=0");
    state.bookings = page.items ?? [];
    renderBookings(state.bookings);
  } catch (error) {
    state.bookings = [];
    renderEmpty(elements.bookingsContent, `Р СњР Вµ РЎС“Р Т‘Р В°Р В»Р С•РЎРѓРЎРЉ Р В·Р В°Р С–РЎР‚РЎС“Р В·Р С‘РЎвЂљРЎРЉ Р В±РЎР‚Р С•Р Р…Р С‘РЎР‚Р С•Р Р†Р В°Р Р…Р С‘РЎРЏ: ${error.message}`);
  }
}

async function refreshStudents() {
  if (!isTeacherRole()) {
    state.students = [];
    renderEmpty(elements.studentsContent, "Р В Р В°Р В·Р Т‘Р ВµР В» РЎС“РЎвЂЎР ВµР Р…Р С‘Р С”Р С•Р Р† Р Т‘Р С•РЎРѓРЎвЂљРЎС“Р С—Р ВµР Р… РЎвЂљР С•Р В»РЎРЉР С”Р С• Р С—РЎР‚Р ВµР С—Р С•Р Т‘Р В°Р Р†Р В°РЎвЂљР ВµР В»РЎР‹.");
    return;
  }

  try {
    const page = await apiRequest("/booking/teacher/students?limit=50&offset=0");
    state.students = page.items ?? [];
    renderStudents(state.students);
  } catch (error) {
    state.students = [];
    renderEmpty(elements.studentsContent, `Р СњР Вµ РЎС“Р Т‘Р В°Р В»Р С•РЎРѓРЎРЉ Р В·Р В°Р С–РЎР‚РЎС“Р В·Р С‘РЎвЂљРЎРЉ РЎС“РЎвЂЎР ВµР Р…Р С‘Р С”Р С•Р Р†: ${error.message}`);
  }
}

async function refreshPackages() {
  if (!state.currentUser) {
    state.packages = [];
    state.packagePlans = [];
    state.payments = [];
    renderEmpty(elements.packagesContent, "Р СџРЎР‚Р С•РЎвЂћР С‘Р В»РЎРЉ Р Р…Р Вµ Р В·Р В°Р С–РЎР‚РЎС“Р В¶Р ВµР Р….");
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
      "Р В Р В°Р В·Р Т‘Р ВµР В» Р С—Р В°Р С”Р ВµРЎвЂљР С•Р Р† Р Т‘Р С•РЎРѓРЎвЂљРЎС“Р С—Р ВµР Р… РЎвЂљР С•Р В»РЎРЉР С”Р С• Р Т‘Р В»РЎРЏ РЎР‚Р С•Р В»Р С‘ student.",
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
    renderEmpty(elements.packagesContent, `Р СњР Вµ РЎС“Р Т‘Р В°Р В»Р С•РЎРѓРЎРЉ Р В·Р В°Р С–РЎР‚РЎС“Р В·Р С‘РЎвЂљРЎРЉ Р С—Р В°Р С”Р ВµРЎвЂљРЎвЂ№: ${error.message}`);
    renderSlotPackageControls();
    if (state.slots.length > 0) {
      renderSlots(state.slots);
    }
  }
}

async function refreshLessons() {
  if (!state.currentUser) {
    state.lessons = [];
    renderEmpty(elements.lessonsContent, "Р СџРЎР‚Р С•РЎвЂћР С‘Р В»РЎРЉ Р Р…Р Вµ Р В·Р В°Р С–РЎР‚РЎС“Р В¶Р ВµР Р….");
    return;
  }

  if (!isTeacherRole()) {
    state.lessons = [];
    renderEmpty(elements.lessonsContent, "Р В Р В°Р В·Р Т‘Р ВµР В» РЎС“РЎР‚Р С•Р С”Р С•Р Р† Р Т‘Р С•РЎРѓРЎвЂљРЎС“Р С—Р ВµР Р… РЎвЂљР С•Р В»РЎРЉР С”Р С• Р Т‘Р В»РЎРЏ РЎР‚Р С•Р В»Р С‘ teacher.");
    return;
  }

  try {
    const page = await apiRequest("/teacher/lessons?limit=20&offset=0");
    state.lessons = page.items ?? [];
    renderLessons(state.lessons);
  } catch (error) {
    state.lessons = [];
    renderEmpty(elements.lessonsContent, `Р СњР Вµ РЎС“Р Т‘Р В°Р В»Р С•РЎРѓРЎРЉ Р В·Р В°Р С–РЎР‚РЎС“Р В·Р С‘РЎвЂљРЎРЉ РЎС“РЎР‚Р С•Р С”Р С‘: ${error.message}`);
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
    setGlobalStatus("Р СџР С•Р В»Р Вµ Р В¤Р ВР С› Р С•Р В±РЎРЏР В·Р В°РЎвЂљР ВµР В»РЎРЉР Р…Р С•.", "error");
    fullNameInput.focus();
    return;
  }

  const rawAgeValue = ageInput.value.trim();
  let normalizedAge = null;
  if (rawAgeValue) {
    const parsedAge = Number(rawAgeValue);
    const isInvalidAge = !Number.isInteger(parsedAge) || parsedAge < 1 || parsedAge > 120;
    if (isInvalidAge) {
      setGlobalStatus("Р вЂ™Р С•Р В·РЎР‚Р В°РЎРѓРЎвЂљ Р Т‘Р С•Р В»Р В¶Р ВµР Р… Р В±РЎвЂ№РЎвЂљРЎРЉ РЎвЂ Р ВµР В»РЎвЂ№Р С РЎвЂЎР С‘РЎРѓР В»Р С•Р С Р С•РЎвЂљ 1 Р Т‘Р С• 120.", "error");
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
    setGlobalStatus("Р СџРЎР‚Р С•РЎвЂћР С‘Р В»РЎРЉ РЎРѓР С•РЎвЂ¦РЎР‚Р В°Р Р…Р ВµР Р….", "success");
  });
}

function renderProfile(user, options = {}) {
  const roleName = user.role?.name ?? "";
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
      <p class="meta"><strong>\u0420\u043E\u043B\u044C:</strong> ${escapeHtml(roleName || "-")}</p>
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
    renderEmpty(elements.lessonsContent, "Р Р€ Р Р†Р В°РЎРѓ Р С—Р С•Р С”Р В° Р Р…Р ВµРЎвЂљ РЎС“РЎР‚Р С•Р С”Р С•Р Р†.");
    return;
  }

  elements.lessonsContent.innerHTML = lessons
    .map((lesson) => {
      return `
        <article class="card-item">
          <h4>Р Р€РЎР‚Р С•Р С” ${escapeHtml(lesson.id)}</h4>
          <p class="meta"><strong>Р РЋРЎвЂљР В°РЎвЂљРЎС“РЎРѓ:</strong> ${escapeHtml(lesson.status)}</p>
          <p class="meta"><strong>Р вЂРЎР‚Р С•Р Р…Р С‘РЎР‚Р С•Р Р†Р В°Р Р…Р С‘Р Вµ:</strong> ${escapeHtml(lesson.booking_id)}</p>
          <p class="meta"><strong>Р РЋРЎвЂљРЎС“Р Т‘Р ВµР Р…РЎвЂљ:</strong> ${escapeHtml(lesson.student_id)}</p>
          <p class="meta"><strong>Р СњР В°РЎвЂЎР В°Р В»Р С•:</strong> ${formatDateTime(lesson.scheduled_start_at)}</p>
          <p class="meta"><strong>Р С›Р С”Р С•Р Р…РЎвЂЎР В°Р Р…Р С‘Р Вµ:</strong> ${formatDateTime(lesson.scheduled_end_at)}</p>
          <p class="meta"><strong>Р СћР ВµР СР В°:</strong> ${escapeHtml(lesson.topic ?? "-")}</p>
        </article>
      `;
    })
    .join("");
}

function renderAdminOperations() {
  if (!isAdminRole()) {
    renderEmpty(
      elements.adminActionsContent,
      "Р В Р В°Р В·Р Т‘Р ВµР В» Р С•Р С—Р ВµРЎР‚Р В°РЎвЂ Р С‘Р в„– Р В°Р Т‘Р СР С‘Р Р…Р С‘РЎРѓРЎвЂљРЎР‚Р В°РЎвЂљР С•РЎР‚Р В° Р Т‘Р С•РЎРѓРЎвЂљРЎС“Р С—Р ВµР Р… РЎвЂљР С•Р В»РЎРЉР С”Р С• Р Т‘Р В»РЎРЏ РЎР‚Р С•Р В»Р С‘ admin.",
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
      ? "Р ВµРЎвЂ°Р Вµ Р Р…Р Вµ Р В·Р В°Р С—РЎС“РЎРѓР С”Р В°Р В»Р С•РЎРѓРЎРЉ"
      : String(state.adminOperations.lastExpiredHolds);
  const lastPackages =
    state.adminOperations.lastExpiredPackages === null
      ? "Р ВµРЎвЂ°Р Вµ Р Р…Р Вµ Р В·Р В°Р С—РЎС“РЎРѓР С”Р В°Р В»Р С•РЎРѓРЎРЉ"
      : String(state.adminOperations.lastExpiredPackages);
  const updatedAt = state.adminOperations.updatedAt
    ? formatDateTime(state.adminOperations.updatedAt)
    : "-";

  elements.adminActionsContent.innerHTML = `
    <article class="card-item">
      <h4>Р РЋР Р†Р С•Р Т‘Р С”Р В° Р С•Р С—Р ВµРЎР‚Р В°РЎвЂ Р С‘Р в„– Р В°Р Т‘Р СР С‘Р Р…Р С‘РЎРѓРЎвЂљРЎР‚Р В°РЎвЂљР С•РЎР‚Р В°</h4>
      <p class="meta"><strong>Р ВРЎРѓРЎвЂљР ВµР С”РЎв‚¬Р С‘РЎвЂ¦ HOLD:</strong> ${escapeHtml(lastHolds)}</p>
      <p class="meta"><strong>Р ВРЎРѓРЎвЂљР ВµР С”РЎв‚¬Р С‘РЎвЂ¦ Р С—Р В°Р С”Р ВµРЎвЂљР С•Р Р†:</strong> ${escapeHtml(lastPackages)}</p>
      <p class="meta"><strong>Р С›Р В±Р Р…Р С•Р Р†Р В»Р ВµР Р…Р С•:</strong> ${escapeHtml(updatedAt)}</p>
      <p class="hint">Р С™Р Р…Р С•Р С—Р С”Р С‘ Р Р†РЎвЂ№РЎв‚¬Р Вµ Р В·Р В°Р С—РЎС“РЎРѓР С”Р В°РЎР‹РЎвЂљ backend-РЎвЂљРЎР‚Р С‘Р С–Р С–Р ВµРЎР‚РЎвЂ№ Р С‘РЎРѓРЎвЂљР ВµРЎвЂЎР ВµР Р…Р С‘РЎРЏ.</p>
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
      return `<option value="${escapeHtml(pkg.id)}">${escapeHtml(pkg.id)} (Р Т‘Р С•РЎРѓРЎвЂљРЎС“Р С—Р Р…Р С• РЎС“РЎР‚Р С•Р С”Р С•Р Р†: ${escapeHtml(availableLessons)})</option>`;
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
      <div class="empty-note">РЈ РІР°СЃ РїРѕРєР° РЅРµС‚ РѕС‚РєСЂС‹С‚С‹С… СЃР»РѕС‚РѕРІ. Р”РѕР±Р°РІСЊС‚Рµ СЂР°Р±РѕС‡РёРµ С‡Р°СЃС‹ РёР»Рё РґРѕР¶РґРёС‚РµСЃСЊ РіРµРЅРµСЂР°С†РёРё СЃР»РѕС‚РѕРІ.</div>
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
          <h4>Р СџРЎР‚Р ВµР С—Р С•Р Т‘Р В°Р Р†Р В°РЎвЂљР ВµР В»РЎРЉ ${escapeHtml(stats.displayName)}</h4>
          <p class="meta"><strong>Р РЋР Р†Р С•Р В±Р С•Р Т‘Р Р…РЎвЂ№РЎвЂ¦ Р С•Р С”Р С•Р Р…:</strong> ${escapeHtml(stats.count)}</p>
          <p class="meta"><strong>Р вЂР В»Р С‘Р В¶Р В°Р в„–РЎв‚¬Р ВµР Вµ Р С•Р С”Р Р…Р С•:</strong> ${formatDateTime(stats.nextStartAt)}</p>
        </article>
      `;
    })
    .join("");

  const canCreateHold = isStudentRole() && getHoldEligiblePackages().length > 0;
  const cards = slots
    .map((slot) => {
      const holdAction = isStudentRole()
        ? `<div class="action-row"><button type="button" class="action-btn" data-action="hold-slot" data-slot-id="${escapeHtml(slot.id)}" ${canCreateHold ? "" : "disabled"}>Р вЂ™Р В·РЎРЏРЎвЂљРЎРЉ Р Р† hold</button></div>`
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
          <h4>Р РЋР В»Р С•РЎвЂљ ${escapeHtml(slot.id)}</h4>
          <p class="meta"><strong>Р СџРЎР‚Р ВµР С—Р С•Р Т‘Р В°Р Р†Р В°РЎвЂљР ВµР В»РЎРЉ:</strong> ${escapeHtml(resolveTeacherDisplayName(slot))}</p>
          <p class="meta"><strong>Р СњР В°РЎвЂЎР В°Р В»Р С•:</strong> ${formatDateTime(slot.start_at)}</p>
          <p class="meta"><strong>Р С›Р С”Р С•Р Р…РЎвЂЎР В°Р Р…Р С‘Р Вµ:</strong> ${formatDateTime(slot.end_at)}</p>
          <p class="meta"><strong>Р РЋРЎвЂљР В°РЎвЂљРЎС“РЎРѓ:</strong> ${escapeHtml(slot.status)}</p>
          ${holdRangeControls}
          ${holdAction}
        </article>
      `;
    })
    .join("");

  const holdHint = isStudentRole() && !canCreateHold
    ? '<p class="hint">Р вЂќР В»РЎРЏ hold Р Р…РЎС“Р В¶Р ВµР Р… Р В°Р С”РЎвЂљР С‘Р Р†Р Р…РЎвЂ№Р в„– Р С—Р В°Р С”Р ВµРЎвЂљ РЎРѓ Р С•РЎРѓРЎвЂљР В°Р Р†РЎв‚¬Р С‘Р СР С‘РЎРѓРЎРЏ РЎС“РЎР‚Р С•Р С”Р В°Р СР С‘.</p>'
    : "";

  elements.slotsContent.innerHTML = `
    <article class="card-item">
      <h4>Р РЋР Р†Р С•Р В±Р С•Р Т‘Р Р…РЎвЂ№Р Вµ Р С•Р С”Р Р…Р В° Р С—Р С• Р С—РЎР‚Р ВµР С—Р С•Р Т‘Р В°Р Р†Р В°РЎвЂљР ВµР В»РЎРЏР С</h4>
      <p class="meta"><strong>Р вЂ™РЎРѓР ВµР С–Р С• Р С—РЎР‚Р ВµР С—Р С•Р Т‘Р В°Р Р†Р В°РЎвЂљР ВµР В»Р ВµР в„–:</strong> ${escapeHtml(teacherStats.size)}</p>
      <p class="meta"><strong>Р вЂ™РЎРѓР ВµР С–Р С• Р Т‘Р С•РЎРѓРЎвЂљРЎС“Р С—Р Р…РЎвЂ№РЎвЂ¦ РЎРѓР В»Р С•РЎвЂљР С•Р Р†:</strong> ${escapeHtml(slots.length)}</p>
    </article>
    ${teacherOverview}
    ${holdHint}
    ${cards}
  `;
}

function formatScheduleWeekday(weekday) {
  const labels = ["Р СџР С•Р Р…Р ВµР Т‘Р ВµР В»РЎРЉР Р…Р С‘Р С”", "Р вЂ™РЎвЂљР С•РЎР‚Р Р…Р С‘Р С”", "Р РЋРЎР‚Р ВµР Т‘Р В°", "Р В§Р ВµРЎвЂљР Р†Р ВµРЎР‚Р С–", "Р СџРЎРЏРЎвЂљР Р…Р С‘РЎвЂ Р В°", "Р РЋРЎС“Р В±Р В±Р С•РЎвЂљР В°", "Р вЂ™Р С•РЎРѓР С”РЎР‚Р ВµРЎРѓР ВµР Р…РЎРЉР Вµ"];
  const value = Number(weekday);
  if (!Number.isInteger(value) || value < 0 || value > 6) {
    return `Р вЂќР ВµР Р…РЎРЉ ${escapeHtml(weekday)}`;
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
        <h4>Р В Р В°Р В±Р С•РЎвЂЎР С‘Р Вµ РЎвЂЎР В°РЎРѓРЎвЂ№ Р С—РЎР‚Р ВµР С—Р С•Р Т‘Р В°Р Р†Р В°РЎвЂљР ВµР В»РЎРЏ</h4>
        <p class="hint">Р СњР Вµ РЎС“Р Т‘Р В°Р В»Р С•РЎРѓРЎРЉ Р В·Р В°Р С–РЎР‚РЎС“Р В·Р С‘РЎвЂљРЎРЉ РЎР‚Р В°Р В±Р С•РЎвЂЎР С‘Р Вµ РЎвЂЎР В°РЎРѓРЎвЂ№: ${escapeHtml(scheduleError)}</p>
      </article>
    `;
  }

  const timezoneLabel = schedule?.timezone ?? state.currentUser?.timezone ?? "-";
  const windows = Array.isArray(schedule?.windows) ? schedule.windows : [];

  if (windows.length === 0) {
    return `
      <article class="card-item">
        <h4>Р В Р В°Р В±Р С•РЎвЂЎР С‘Р Вµ РЎвЂЎР В°РЎРѓРЎвЂ№ Р С—РЎР‚Р ВµР С—Р С•Р Т‘Р В°Р Р†Р В°РЎвЂљР ВµР В»РЎРЏ</h4>
        <p class="meta"><strong>Р СћР В°Р в„–Р СР В·Р С•Р Р…Р В°:</strong> ${escapeHtml(timezoneLabel)}</p>
        <p class="hint">Р В Р В°Р В±Р С•РЎвЂЎР С‘Р Вµ РЎвЂЎР В°РЎРѓРЎвЂ№ Р С—Р С•Р С”Р В° Р Р…Р Вµ Р В·Р В°Р Т‘Р В°Р Р…РЎвЂ№ Р В°Р Т‘Р СР С‘Р Р…Р С‘РЎРѓРЎвЂљРЎР‚Р В°РЎвЂљР С•РЎР‚Р С•Р С.</p>
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
      <h4>Р В Р В°Р В±Р С•РЎвЂЎР С‘Р Вµ РЎвЂЎР В°РЎРѓРЎвЂ№ Р С—РЎР‚Р ВµР С—Р С•Р Т‘Р В°Р Р†Р В°РЎвЂљР ВµР В»РЎРЏ</h4>
      <p class="meta"><strong>Р СћР В°Р в„–Р СР В·Р С•Р Р…Р В°:</strong> ${escapeHtml(timezoneLabel)}</p>
      ${windowsMarkup}
    </article>
  `;
}

function renderTeacherOpenSlots(slots) {
  const workingHoursCard = renderTeacherWorkingHoursCard();

  if (slots.length === 0) {
    elements.slotsContent.innerHTML = `
      <div class="empty-note">РЈ РІР°СЃ РїРѕРєР° РЅРµС‚ РѕС‚РєСЂС‹С‚С‹С… СЃР»РѕС‚РѕРІ. Р”РѕР±Р°РІСЊС‚Рµ СЂР°Р±РѕС‡РёРµ С‡Р°СЃС‹ РёР»Рё РґРѕР¶РґРёС‚РµСЃСЊ РіРµРЅРµСЂР°С†РёРё СЃР»РѕС‚РѕРІ.</div>
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
          <h4>Р РЋР В»Р С•РЎвЂљ ${escapeHtml(slot.id)}</h4>
          <p class="meta"><strong>Р СњР В°РЎвЂЎР В°Р В»Р С•:</strong> ${formatDateTime(slot.start_at)}</p>
          <p class="meta"><strong>Р С›Р С”Р С•Р Р…РЎвЂЎР В°Р Р…Р С‘Р Вµ:</strong> ${formatDateTime(slot.end_at)}</p>
          <p class="meta"><strong>Р РЋРЎвЂљР В°РЎвЂљРЎС“РЎРѓ:</strong> ${escapeHtml(slot.status)}</p>
        </article>
      `;
    })
    .join("");

  elements.slotsContent.innerHTML = `
    <article class="card-item">
      <h4>Р СљР С•Р С‘ Р С•РЎвЂљР С”РЎР‚РЎвЂ№РЎвЂљРЎвЂ№Р Вµ РЎРѓР В»Р С•РЎвЂљРЎвЂ№</h4>
      <p class="meta"><strong>Р вЂ™РЎРѓР ВµР С–Р С• Р С•РЎвЂљР С”РЎР‚РЎвЂ№РЎвЂљРЎвЂ№РЎвЂ¦ РЎРѓР В»Р С•РЎвЂљР С•Р Р†:</strong> ${escapeHtml(sortedSlots.length)}</p>
      <p class="meta"><strong>Р вЂР В»Р С‘Р В¶Р В°Р в„–РЎв‚¬Р С‘Р в„– РЎРѓР В»Р С•РЎвЂљ:</strong> ${formatDateTime(nextStartAt)}</p>
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
    renderEmpty(elements.bookingsContent, "Р Р€ Р Р†Р В°РЎРѓ Р С—Р С•Р С”Р В° Р Р…Р ВµРЎвЂљ Р В±РЎР‚Р С•Р Р…Р С‘РЎР‚Р С•Р Р†Р В°Р Р…Р С‘Р в„–.");
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
        ? `<button type="button" class="action-btn" data-action="confirm-booking" data-booking-id="${escapeHtml(booking.id)}">Р СџР С•Р Т‘РЎвЂљР Р†Р ВµРЎР‚Р Т‘Р С‘РЎвЂљРЎРЉ</button>`
        : "";

      const cancelAction = canCancel
        ? `<button type="button" class="action-btn danger" data-action="cancel-booking" data-booking-id="${escapeHtml(booking.id)}">Р С›РЎвЂљР СР ВµР Р…Р С‘РЎвЂљРЎРЉ</button>`
        : "";

      const cancelReason = canCancel
        ? `
          <div class="action-row">
            <input
              type="text"
              maxlength="512"
              placeholder="Р СџРЎР‚Р С‘РЎвЂЎР С‘Р Р…Р В° Р С•РЎвЂљР СР ВµР Р…РЎвЂ№ (Р С•Р С—РЎвЂ Р С‘Р С•Р Р…Р В°Р В»РЎРЉР Р…Р С•)"
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
                Р СџР ВµРЎР‚Р ВµР Р…Р ВµРЎРѓРЎвЂљР С‘
              </button>
            </div>
          `;
        } else {
          rescheduleAction = "<p class=\"hint\">Р СњР ВµРЎвЂљ Р С•РЎвЂљР С”РЎР‚РЎвЂ№РЎвЂљРЎвЂ№РЎвЂ¦ РЎРѓР В»Р С•РЎвЂљР С•Р Р† Р Т‘Р В»РЎРЏ Р С—Р ВµРЎР‚Р ВµР Р…Р С•РЎРѓР В°.</p>";
        }
      }

      return `
        <article class="card-item">
          <h4>Р вЂРЎР‚Р С•Р Р…Р С‘РЎР‚Р С•Р Р†Р В°Р Р…Р С‘Р Вµ ${escapeHtml(booking.id)}</h4>
          <p class="meta"><strong>Р РЋРЎвЂљР В°РЎвЂљРЎС“РЎРѓ:</strong> ${escapeHtml(booking.status)}</p>
          <p class="meta"><strong>Р РЋР В»Р С•РЎвЂљ:</strong> ${escapeHtml(booking.slot_id)}</p>
          <p class="meta"><strong>Р СџР В°Р С”Р ВµРЎвЂљ:</strong> ${escapeHtml(booking.package_id ?? "-")}</p>
          <p class="meta"><strong>Hold Р Т‘Р С•:</strong> ${formatDateTime(booking.hold_expires_at)}</p>
          <p class="meta"><strong>Р РЋР С•Р В·Р Т‘Р В°Р Р…Р С•:</strong> ${formatDateTime(booking.created_at)}</p>
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
    renderEmpty(elements.bookingsContent, "Р Р€ Р Р†Р В°РЎРѓ Р С—Р С•Р С”Р В° Р Р…Р ВµРЎвЂљ Р В·Р В°Р В±РЎР‚Р С•Р Р…Р С‘РЎР‚Р С•Р Р†Р В°Р Р…Р Р…РЎвЂ№РЎвЂ¦ РЎРѓР В»Р С•РЎвЂљР С•Р Р†.");
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
          <h4>Р вЂРЎР‚Р С•Р Р…Р С‘РЎР‚Р С•Р Р†Р В°Р Р…Р С‘Р Вµ ${escapeHtml(lesson.booking_id ?? lesson.id)}</h4>
          <p class="meta"><strong>Р РЋРЎвЂљРЎС“Р Т‘Р ВµР Р…РЎвЂљ:</strong> ${escapeHtml(lesson.student_id)}</p>
          <p class="meta"><strong>Р РЋР В»Р С•РЎвЂљ:</strong> ${formatDateTime(lesson.scheduled_start_at)} - ${formatDateTime(lesson.scheduled_end_at)}</p>
          <p class="meta"><strong>Р РЋРЎвЂљР В°РЎвЂљРЎС“РЎРѓ РЎС“РЎР‚Р С•Р С”Р В°:</strong> ${escapeHtml(lesson.status)}</p>
          <p class="meta"><strong>Р СћР ВµР СР В°:</strong> ${escapeHtml(lesson.topic ?? "-")}</p>
        </article>
      `;
    })
    .join("");

  elements.bookingsContent.innerHTML = `
    <article class="card-item">
      <h4>Р вЂ”Р В°Р В±РЎР‚Р С•Р Р…Р С‘РЎР‚Р С•Р Р†Р В°Р Р…Р Р…РЎвЂ№Р Вµ РЎРѓР В»Р С•РЎвЂљРЎвЂ№</h4>
      <p class="meta"><strong>Р вЂ™РЎРѓР ВµР С–Р С• РЎРѓР В»Р С•РЎвЂљР С•Р Р†:</strong> ${escapeHtml(sortedLessons.length)}</p>
    </article>
    ${cards}
  `;
}

function renderStudents(students) {
  if (students.length === 0) {
    renderEmpty(elements.studentsContent, "Р С’Р С”РЎвЂљР С‘Р Р†Р Р…РЎвЂ№РЎвЂ¦ РЎС“РЎвЂЎР ВµР Р…Р С‘Р С”Р С•Р Р† Р С—Р С•Р С”Р В° Р Р…Р ВµРЎвЂљ.");
    return;
  }

  const studentsMarkup = students
    .map((student) => {
      const packages = Array.isArray(student.packages) ? student.packages : [];
      const packageMarkup = packages.length === 0
        ? "<p class=\"hint\">Р С’Р С”РЎвЂљР С‘Р Р†Р Р…РЎвЂ№РЎвЂ¦ Р С—Р В°Р С”Р ВµРЎвЂљР С•Р Р† Р Р…Р ВµРЎвЂљ.</p>"
        : packages
            .map((pkg) => {
              return `
                <article class="card-item">
                  <h4>Р СџР В°Р С”Р ВµРЎвЂљ ${escapeHtml(pkg.package_id)}</h4>
                  <p class="meta"><strong>Р РЋРЎвЂљР В°РЎвЂљРЎС“РЎРѓ:</strong> ${escapeHtml(pkg.status)}</p>
                  <p class="meta"><strong>Р вЂ™РЎРѓР ВµР С–Р С• РЎС“РЎР‚Р С•Р С”Р С•Р Р†:</strong> ${escapeHtml(pkg.lessons_total)}</p>
                  <p class="meta"><strong>Р С›РЎРѓРЎвЂљР В°Р В»Р С•РЎРѓРЎРЉ:</strong> ${escapeHtml(pkg.lessons_left)}</p>
                  <p class="meta"><strong>Р вЂ™ РЎР‚Р ВµР В·Р ВµРЎР‚Р Р†Р Вµ:</strong> ${escapeHtml(pkg.lessons_reserved)}</p>
                  <p class="meta"><strong>Р вЂќР С•РЎРѓРЎвЂљРЎС“Р С—Р Р…Р С•:</strong> ${escapeHtml(pkg.lessons_available)}</p>
                  <p class="meta"><strong>Р вЂќР ВµР в„–РЎРѓРЎвЂљР Р†РЎС“Р ВµРЎвЂљ Р Т‘Р С•:</strong> ${formatDateTime(pkg.expires_at)}</p>
                </article>
              `;
            })
            .join("");

      return `
        <article class="card-item">
          <h4>${escapeHtml(student.student_full_name || student.student_email)}</h4>
          <p class="meta"><strong>Email:</strong> ${escapeHtml(student.student_email)}</p>
          <p class="meta"><strong>ID:</strong> ${escapeHtml(student.student_id)}</p>
          <p class="meta"><strong>Р С’Р С”РЎвЂљР С‘Р Р†Р Р…РЎвЂ№РЎвЂ¦ Р В±РЎР‚Р С•Р Р…Р С‘РЎР‚Р С•Р Р†Р В°Р Р…Р С‘Р в„–:</strong> ${escapeHtml(student.active_bookings_count)}</p>
          <p class="meta"><strong>Р СџР С•РЎРѓР В»Р ВµР Т‘Р Р…Р ВµР Вµ Р В±РЎР‚Р С•Р Р…Р С‘РЎР‚Р С•Р Р†Р В°Р Р…Р С‘Р Вµ:</strong> ${formatDateTime(student.last_booking_at)}</p>
        </article>
        ${packageMarkup}
      `;
    })
    .join("");

  elements.studentsContent.innerHTML = `
    <article class="card-item">
      <h4>Р С’Р С”РЎвЂљР С‘Р Р†Р Р…РЎвЂ№Р Вµ РЎС“РЎвЂЎР ВµР Р…Р С‘Р С”Р С‘</h4>
      <p class="meta"><strong>Р вЂ™РЎРѓР ВµР С–Р С• РЎС“РЎвЂЎР ВµР Р…Р С‘Р С”Р С•Р Р†:</strong> ${escapeHtml(students.length)}</p>
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
      <h4>Р РЋР Р†Р С•Р Т‘Р С”Р В° Р С—Р С• Р С—Р В°Р С”Р ВµРЎвЂљР В°Р С</h4>
      <p class="meta"><strong>Р СџР В°Р С”Р ВµРЎвЂљР С•Р Р† Р С”РЎС“Р С—Р В»Р ВµР Р…Р С•:</strong> ${escapeHtml(packages.length)}</p>
      <p class="meta"><strong>Р Р€РЎР‚Р С•Р С”Р С•Р Р† Р С”РЎС“Р С—Р В»Р ВµР Р…Р С•:</strong> ${escapeHtml(totalLessonsPurchased)}</p>
      <p class="meta"><strong>Р Р€РЎР‚Р С•Р С”Р С•Р Р† Р С•РЎРѓРЎвЂљР В°Р В»Р С•РЎРѓРЎРЉ:</strong> ${escapeHtml(totalLessonsLeft)}</p>
      <p class="meta"><strong>Р вЂ™ РЎР‚Р ВµР В·Р ВµРЎР‚Р Р†Р Вµ:</strong> ${escapeHtml(totalLessonsReserved)}</p>
      <p class="meta"><strong>Р С’Р С”РЎвЂљР С‘Р Р†Р Р…РЎвЂ№РЎвЂ¦ Р С—Р В°Р С”Р ВµРЎвЂљР С•Р Р†:</strong> ${escapeHtml(activePackagesCount)}</p>
    </article>
  `;

  const plansMarkup = state.packagePlans.length === 0
    ? '<div class="empty-note">Р СћР В°РЎР‚Р С‘РЎвЂћРЎвЂ№ Р Т‘Р В»РЎРЏ Р С—Р С•Р С”РЎС“Р С—Р С”Р С‘ Р Р†РЎР‚Р ВµР СР ВµР Р…Р Р…Р С• Р Р…Р ВµР Т‘Р С•РЎРѓРЎвЂљРЎС“Р С—Р Р…РЎвЂ№.</div>'
    : state.packagePlans
        .map((plan) => {
          const priceLabel = `${plan.price_amount} ${plan.price_currency}`;
          return `
            <article class="card-item">
              <h4>${escapeHtml(plan.title)}</h4>
              <p class="meta">${escapeHtml(plan.description ?? "")}</p>
              <p class="meta"><strong>Р Р€РЎР‚Р С•Р С”Р С•Р Р†:</strong> ${escapeHtml(plan.lessons_total)}</p>
              <p class="meta"><strong>Р РЋРЎР‚Р С•Р С”:</strong> ${escapeHtml(plan.duration_days)} Р Т‘Р Р…Р ВµР в„–</p>
              <p class="meta"><strong>Р В¦Р ВµР Р…Р В°:</strong> ${escapeHtml(priceLabel)}</p>
              <div class="action-row">
                <button
                  type="button"
                  class="action-btn"
                  data-action="purchase-plan"
                  data-plan-id="${escapeHtml(plan.id)}"
                >
                  Р С™РЎС“Р С—Р С‘РЎвЂљРЎРЉ Р С—Р В°Р С”Р ВµРЎвЂљ
                </button>
              </div>
            </article>
          `;
        })
        .join("");

  const packageListMarkup = packages.length === 0
    ? '<div class="empty-note">Р Р€ Р Р†Р В°РЎРѓ Р С—Р С•Р С”Р В° Р Р…Р ВµРЎвЂљ Р С—Р В°Р С”Р ВµРЎвЂљР С•Р Р†.</div>'
    : packages
        .map((item) => {
          const packagePrice =
            item.price_amount === null || item.price_amount === undefined
              ? "-"
              : `${item.price_amount} ${item.price_currency ?? ""}`.trim();
          return `
            <article class="card-item">
              <h4>Р СџР В°Р С”Р ВµРЎвЂљ ${escapeHtml(item.id)}</h4>
              <p class="meta"><strong>Р РЋРЎвЂљР В°РЎвЂљРЎС“РЎРѓ:</strong> ${escapeHtml(item.status)}</p>
              <p class="meta"><strong>Р Р€РЎР‚Р С•Р С”Р С•Р Р† Р Р†РЎРѓР ВµР С–Р С•:</strong> ${escapeHtml(item.lessons_total)}</p>
              <p class="meta"><strong>Р С›РЎРѓРЎвЂљР В°Р В»Р С•РЎРѓРЎРЉ РЎС“РЎР‚Р С•Р С”Р С•Р Р†:</strong> ${escapeHtml(item.lessons_left)}</p>
              <p class="meta"><strong>Р вЂ™ РЎР‚Р ВµР В·Р ВµРЎР‚Р Р†Р Вµ:</strong> ${escapeHtml(item.lessons_reserved)}</p>
              <p class="meta"><strong>Р РЋРЎвЂљР С•Р С‘Р СР С•РЎРѓРЎвЂљРЎРЉ:</strong> ${escapeHtml(packagePrice)}</p>
              <p class="meta"><strong>Р вЂќР ВµР в„–РЎРѓРЎвЂљР Р†РЎС“Р ВµРЎвЂљ Р Т‘Р С•:</strong> ${formatDateTime(item.expires_at)}</p>
            </article>
          `;
        })
        .join("");

  const paymentsMarkup = state.payments.length === 0
    ? '<div class="empty-note">Р ВРЎРѓРЎвЂљР С•РЎР‚Р С‘РЎРЏ Р С—Р С•Р С”РЎС“Р С—Р С•Р С” Р С—Р С•Р С”Р В° Р С—РЎС“РЎРѓРЎвЂљР В°РЎРЏ.</div>'
    : state.payments
        .map((payment) => {
          const amountLabel = `${payment.amount} ${payment.currency}`;
          return `
            <article class="card-item">
              <h4>Р СџР В»Р В°РЎвЂљР ВµР В¶ ${escapeHtml(payment.id)}</h4>
              <p class="meta"><strong>Р СџР В°Р С”Р ВµРЎвЂљ:</strong> ${escapeHtml(payment.package_id)}</p>
              <p class="meta"><strong>Р РЋРЎвЂљР В°РЎвЂљРЎС“РЎРѓ:</strong> ${escapeHtml(payment.status)}</p>
              <p class="meta"><strong>Р РЋРЎС“Р СР СР В°:</strong> ${escapeHtml(amountLabel)}</p>
              <p class="meta"><strong>Р СџРЎР‚Р С•Р Р†Р В°Р в„–Р Т‘Р ВµРЎР‚:</strong> ${escapeHtml(payment.provider_name)}</p>
              <p class="meta"><strong>Р С›Р С—Р В»Р В°РЎвЂЎР ВµР Р…:</strong> ${formatDateTime(payment.paid_at)}</p>
              <p class="meta"><strong>Р РЋР С•Р В·Р Т‘Р В°Р Р…:</strong> ${formatDateTime(payment.created_at)}</p>
            </article>
          `;
        })
        .join("");

  elements.packagesContent.innerHTML = `
    ${summary}
    <article class="card-item">
      <h4>Р СџР С•Р С”РЎС“Р С—Р С”Р В° Р С—Р В°Р С”Р ВµРЎвЂљР С•Р Р†</h4>
      <p class="meta">Р вЂ™РЎвЂ№Р В±Р ВµРЎР‚Р С‘РЎвЂљР Вµ РЎвЂљР В°РЎР‚Р С‘РЎвЂћ Р С‘ Р С”РЎС“Р С—Р С‘РЎвЂљР Вµ Р С—Р В°Р С”Р ВµРЎвЂљ Р В·Р В°Р Р…РЎРЏРЎвЂљР С‘Р в„–.</p>
    </article>
    ${plansMarkup}
    <article class="card-item">
      <h4>Р СљР С•Р С‘ Р С—Р В°Р С”Р ВµРЎвЂљРЎвЂ№</h4>
      <p class="meta">Р СћР ВµР С”РЎС“РЎвЂ°Р С‘Р Вµ Р С‘ Р В°РЎР‚РЎвЂ¦Р С‘Р Р†Р Р…РЎвЂ№Р Вµ Р С—Р В°Р С”Р ВµРЎвЂљРЎвЂ№ Р В·Р В°Р Р…РЎРЏРЎвЂљР С‘Р в„–.</p>
    </article>
    ${packageListMarkup}
    <article class="card-item">
      <h4>Р ВРЎРѓРЎвЂљР С•РЎР‚Р С‘РЎРЏ Р С—Р С•Р С”РЎС“Р С—Р С•Р С”</h4>
      <p class="meta">Р вЂ™РЎРѓР Вµ Р Р†Р В°РЎв‚¬Р С‘ Р С—Р В»Р В°РЎвЂљР ВµР В¶Р С‘ Р С—Р С• Р С—Р В°Р С”Р ВµРЎвЂљР В°Р С.</p>
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
    setGlobalStatus("Hold Р Т‘Р С•РЎРѓРЎвЂљРЎС“Р С—Р ВµР Р… РЎвЂљР С•Р В»РЎРЉР С”Р С• Р Т‘Р В»РЎРЏ РЎР‚Р С•Р В»Р С‘ student.", "error");
    return;
  }

  const slotId = button.dataset.slotId;
  const packageId = elements.slotPackageSelect?.value ?? "";

  if (!slotId || !packageId) {
    setGlobalStatus("Р вЂ™РЎвЂ№Р В±Р ВµРЎР‚Р С‘РЎвЂљР Вµ Р С—Р В°Р С”Р ВµРЎвЂљ Р С‘ Р С—Р С•Р Р†РЎвЂљР С•РЎР‚Р С‘РЎвЂљР Вµ Р С—Р С•Р С—РЎвЂ№РЎвЂљР С”РЎС“ hold.", "error");
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

    setGlobalStatus(`Hold РЎРѓР С•Р В·Р Т‘Р В°Р Р…: ${booking.id}`, "success");
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
      setGlobalStatus(`Р вЂРЎР‚Р С•Р Р…Р С‘РЎР‚Р С•Р Р†Р В°Р Р…Р С‘Р Вµ Р С—Р С•Р Т‘РЎвЂљР Р†Р ВµРЎР‚Р В¶Р Т‘Р ВµР Р…Р С•: ${bookingId}`, "success");
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

      setGlobalStatus(`Р вЂРЎР‚Р С•Р Р…Р С‘РЎР‚Р С•Р Р†Р В°Р Р…Р С‘Р Вµ Р С•РЎвЂљР СР ВµР Р…Р ВµР Р…Р С•: ${bookingId}`, "success");
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
        setGlobalStatus("Р вЂ™РЎвЂ№Р В±Р ВµРЎР‚Р С‘РЎвЂљР Вµ Р Р…Р С•Р Р†РЎвЂ№Р в„– РЎРѓР В»Р С•РЎвЂљ Р Т‘Р В»РЎРЏ Р С—Р ВµРЎР‚Р ВµР Р…Р С•РЎРѓР В°.", "error");
        return;
      }

      if (newSlotId === currentSlotId) {
        setGlobalStatus("Р СњР С•Р Р†РЎвЂ№Р в„– РЎРѓР В»Р С•РЎвЂљ Р Т‘Р С•Р В»Р В¶Р ВµР Р… Р С•РЎвЂљР В»Р С‘РЎвЂЎР В°РЎвЂљРЎРЉРЎРѓРЎРЏ Р С•РЎвЂљ РЎвЂљР ВµР С”РЎС“РЎвЂ°Р ВµР С–Р С•.", "error");
        return;
      }

      const newBooking = await apiRequest(`/booking/${bookingId}/reschedule`, {
        method: "POST",
        body: {
          new_slot_id: newSlotId,
        },
      });

      setGlobalStatus(`Р вЂРЎР‚Р С•Р Р…Р С‘РЎР‚Р С•Р Р†Р В°Р Р…Р С‘Р Вµ Р С—Р ВµРЎР‚Р ВµР Р…Р ВµРЎРѓР ВµР Р…Р С•. Р СњР С•Р Р†РЎвЂ№Р в„– ID: ${newBooking.id}`, "success");
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
    setGlobalStatus("Р СџР С•Р С”РЎС“Р С—Р С”Р В° Р С—Р В°Р С”Р ВµРЎвЂљР С•Р Р† Р Т‘Р С•РЎРѓРЎвЂљРЎС“Р С—Р Р…Р В° РЎвЂљР С•Р В»РЎРЉР С”Р С• Р Т‘Р В»РЎРЏ РЎР‚Р С•Р В»Р С‘ student.", "error");
    return;
  }

  const planId = button.dataset.planId ?? "";
  if (!planId) {
    setGlobalStatus("Р СњР Вµ РЎС“Р Т‘Р В°Р В»Р С•РЎРѓРЎРЉ Р С•Р С—РЎР‚Р ВµР Т‘Р ВµР В»Р С‘РЎвЂљРЎРЉ Р Р†РЎвЂ№Р В±РЎР‚Р В°Р Р…Р Р…РЎвЂ№Р в„– РЎвЂљР В°РЎР‚Р С‘РЎвЂћ.", "error");
    return;
  }

  await withButtonAction(button, async () => {
    const purchase = await apiRequest("/billing/packages/purchase", {
      method: "POST",
      body: {
        plan_id: planId,
      },
    });

    setGlobalStatus(`Р СџР В°Р С”Р ВµРЎвЂљ Р С”РЎС“Р С—Р В»Р ВµР Р…: ${purchase.package.id}`, "success");
    await refreshAfterBillingMutation();
  });
}

async function handleExpireHolds(event) {
  if (!isAdminRole()) {
    setGlobalStatus("Р С›Р С—Р ВµРЎР‚Р В°РЎвЂ Р С‘РЎРЏ Р Т‘Р С•РЎРѓРЎвЂљРЎС“Р С—Р Р…Р В° РЎвЂљР С•Р В»РЎРЉР С”Р С• Р Т‘Р В»РЎРЏ РЎР‚Р С•Р В»Р С‘ admin.", "error");
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
    setGlobalStatus(`Р ВРЎРѓРЎвЂљР ВµР С”РЎв‚¬Р С‘РЎвЂ¦ HOLD-Р В±РЎР‚Р С•Р Р…Р С‘РЎР‚Р С•Р Р†Р В°Р Р…Р С‘Р в„–: ${expiredCount}`, "success");
    await Promise.all([refreshSlots(), refreshBookings()]);
  });
}

async function handleExpirePackages(event) {
  if (!isAdminRole()) {
    setGlobalStatus("Р С›Р С—Р ВµРЎР‚Р В°РЎвЂ Р С‘РЎРЏ Р Т‘Р С•РЎРѓРЎвЂљРЎС“Р С—Р Р…Р В° РЎвЂљР С•Р В»РЎРЉР С”Р С• Р Т‘Р В»РЎРЏ РЎР‚Р С•Р В»Р С‘ admin.", "error");
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
    setGlobalStatus(`Р ВРЎРѓРЎвЂљР ВµР С”РЎв‚¬Р С‘РЎвЂ¦ Р С—Р В°Р С”Р ВµРЎвЂљР С•Р Р†: ${expiredCount}`, "success");
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
  button.textContent = "Р вЂ™РЎвЂ№Р С—Р С•Р В»Р Р…РЎРЏР ВµРЎвЂљРЎРѓРЎРЏ...";

  try {
    await action();
  } catch (error) {
    setGlobalStatus(`Р С›РЎв‚¬Р С‘Р В±Р С”Р В° Р С•Р С—Р ВµРЎР‚Р В°РЎвЂ Р С‘Р С‘: ${error.message}`, "error");
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
    "Not authenticated": "Р СћРЎР‚Р ВµР В±РЎС“Р ВµРЎвЂљРЎРѓРЎРЏ Р В°Р Р†РЎвЂљР С•РЎР‚Р С‘Р В·Р В°РЎвЂ Р С‘РЎРЏ.",
    "Could not validate credentials": "Р СњР Вµ РЎС“Р Т‘Р В°Р В»Р С•РЎРѓРЎРЉ Р С—РЎР‚Р С•Р Р†Р ВµРЎР‚Р С‘РЎвЂљРЎРЉ РЎС“РЎвЂЎР ВµРЎвЂљР Р…РЎвЂ№Р Вµ Р Т‘Р В°Р Р…Р Р…РЎвЂ№Р Вµ.",
    "Invalid credentials": "Р СњР ВµР Р†Р ВµРЎР‚Р Р…РЎвЂ№Р в„– email Р С‘Р В»Р С‘ Р С—Р В°РЎР‚Р С•Р В»РЎРЉ.",
    "Unauthorized": "Р СњР ВµР Т‘Р С•РЎРѓРЎвЂљР В°РЎвЂљР С•РЎвЂЎР Р…Р С• Р С—РЎР‚Р В°Р Р† Р Т‘Р В»РЎРЏ Р Р†РЎвЂ№Р С—Р С•Р В»Р Р…Р ВµР Р…Р С‘РЎРЏ Р С•Р С—Р ВµРЎР‚Р В°РЎвЂ Р С‘Р С‘.",
    "Access denied": "Р вЂќР С•РЎРѓРЎвЂљРЎС“Р С— Р В·Р В°Р С—РЎР‚Р ВµРЎвЂ°Р ВµР Р….",
    "Slot not found": "Р РЋР В»Р С•РЎвЂљ Р Р…Р Вµ Р Р…Р В°Р в„–Р Т‘Р ВµР Р….",
    "Slot is not available": "Р РЋР В»Р С•РЎвЂљ РЎРѓР ВµР в„–РЎвЂЎР В°РЎРѓ Р Р…Р ВµР Т‘Р С•РЎРѓРЎвЂљРЎС“Р С—Р ВµР Р….",
    "Cannot book a slot in the past": "Р СњР ВµР В»РЎРЉР В·РЎРЏ Р В±РЎР‚Р С•Р Р…Р С‘РЎР‚Р С•Р Р†Р В°РЎвЂљРЎРЉ РЎРѓР В»Р С•РЎвЂљ Р Р† Р С—РЎР‚Р С•РЎв‚¬Р В»Р С•Р С.",
    "Package not found": "Р СџР В°Р С”Р ВµРЎвЂљ Р Р…Р Вµ Р Р…Р В°Р в„–Р Т‘Р ВµР Р….",
    "Package does not belong to current student": "Р СџР В°Р С”Р ВµРЎвЂљ Р Р…Р Вµ Р С—РЎР‚Р С‘Р Р…Р В°Р Т‘Р В»Р ВµР В¶Р С‘РЎвЂљ РЎвЂљР ВµР С”РЎС“РЎвЂ°Р ВµР СРЎС“ РЎРѓРЎвЂљРЎС“Р Т‘Р ВµР Р…РЎвЂљРЎС“.",
    "Package does not belong to current user": "Р СџР В°Р С”Р ВµРЎвЂљ Р Р…Р Вµ Р С—РЎР‚Р С‘Р Р…Р В°Р Т‘Р В»Р ВµР В¶Р С‘РЎвЂљ РЎвЂљР ВµР С”РЎС“РЎвЂ°Р ВµР СРЎС“ Р С—Р С•Р В»РЎРЉР В·Р С•Р Р†Р В°РЎвЂљР ВµР В»РЎР‹.",
    "Package plan not found": "Р вЂ™РЎвЂ№Р В±РЎР‚Р В°Р Р…Р Р…РЎвЂ№Р в„– РЎвЂљР В°РЎР‚Р С‘РЎвЂћ Р Р…Р Вµ Р Р…Р В°Р в„–Р Т‘Р ВµР Р….",
    "Package is not active": "Р СџР В°Р С”Р ВµРЎвЂљ Р Р…Р Вµ Р В°Р С”РЎвЂљР С‘Р Р†Р ВµР Р….",
    "Package is expired": "Р РЋРЎР‚Р С•Р С” Р Т‘Р ВµР в„–РЎРѓРЎвЂљР Р†Р С‘РЎРЏ Р С—Р В°Р С”Р ВµРЎвЂљР В° Р С‘РЎРѓРЎвЂљР ВµР С”.",
    "No lessons left in package": "Р вЂ™ Р С—Р В°Р С”Р ВµРЎвЂљР Вµ Р Р…Р Вµ Р С•РЎРѓРЎвЂљР В°Р В»Р С•РЎРѓРЎРЉ РЎС“РЎР‚Р С•Р С”Р С•Р Р†.",
    "No lessons left": "Р вЂ™ Р С—Р В°Р С”Р ВµРЎвЂљР Вµ Р Р…Р Вµ Р С•РЎРѓРЎвЂљР В°Р В»Р С•РЎРѓРЎРЉ РЎС“РЎР‚Р С•Р С”Р С•Р Р†.",
    "Only students can purchase packages": "Р СџР С•Р С”РЎС“Р С—Р С”Р В° Р С—Р В°Р С”Р ВµРЎвЂљР С•Р Р† Р Т‘Р С•РЎРѓРЎвЂљРЎС“Р С—Р Р…Р В° РЎвЂљР С•Р В»РЎРЉР С”Р С• РЎРѓРЎвЂљРЎС“Р Т‘Р ВµР Р…РЎвЂљР В°Р С.",
    "Only students can hold bookings": "Р СћР С•Р В»РЎРЉР С”Р С• РЎРѓРЎвЂљРЎС“Р Т‘Р ВµР Р…РЎвЂљРЎвЂ№ Р СР С•Р С–РЎС“РЎвЂљ РЎРѓР С•Р В·Р Т‘Р В°Р Р†Р В°РЎвЂљРЎРЉ HOLD-Р В±РЎР‚Р С•Р Р…Р С‘РЎР‚Р С•Р Р†Р В°Р Р…Р С‘РЎРЏ.",
    "Booking not found": "Р вЂРЎР‚Р С•Р Р…Р С‘РЎР‚Р С•Р Р†Р В°Р Р…Р С‘Р Вµ Р Р…Р Вµ Р Р…Р В°Р в„–Р Т‘Р ВµР Р…Р С•.",
    "Only HOLD booking can be confirmed": "Р СџР С•Р Т‘РЎвЂљР Р†Р ВµРЎР‚Р Т‘Р С‘РЎвЂљРЎРЉ Р СР С•Р В¶Р Р…Р С• РЎвЂљР С•Р В»РЎРЉР С”Р С• Р В±РЎР‚Р С•Р Р…Р С‘РЎР‚Р С•Р Р†Р В°Р Р…Р С‘Р Вµ Р Р† РЎРѓРЎвЂљР В°РЎвЂљРЎС“РЎРѓР Вµ HOLD.",
    "Booking hold has expired": "Р вЂ™РЎР‚Р ВµР СРЎРЏ HOLD-Р В±РЎР‚Р С•Р Р…Р С‘РЎР‚Р С•Р Р†Р В°Р Р…Р С‘РЎРЏ Р С‘РЎРѓРЎвЂљР ВµР С”Р В»Р С•.",
    "Booking package is required": "Р вЂќР В»РЎРЏ Р В±РЎР‚Р С•Р Р…Р С‘РЎР‚Р С•Р Р†Р В°Р Р…Р С‘РЎРЏ РЎвЂљРЎР‚Р ВµР В±РЎС“Р ВµРЎвЂљРЎРѓРЎРЏ Р С—Р В°Р С”Р ВµРЎвЂљ.",
    "Package is inactive or expired": "Р СџР В°Р С”Р ВµРЎвЂљ Р Р…Р ВµР В°Р С”РЎвЂљР С‘Р Р†Р ВµР Р… Р С‘Р В»Р С‘ РЎС“Р В¶Р Вµ Р С‘РЎРѓРЎвЂљР ВµР С”.",
    "Booking already expired": "Р вЂРЎР‚Р С•Р Р…Р С‘РЎР‚Р С•Р Р†Р В°Р Р…Р С‘Р Вµ РЎС“Р В¶Р Вµ Р С‘РЎРѓРЎвЂљР ВµР С”Р В»Р С•.",
    "Booking cannot be rescheduled in current status":
      "Р вЂ™ РЎвЂљР ВµР С”РЎС“РЎвЂ°Р ВµР С РЎРѓРЎвЂљР В°РЎвЂљРЎС“РЎРѓР Вµ Р В±РЎР‚Р С•Р Р…Р С‘РЎР‚Р С•Р Р†Р В°Р Р…Р С‘Р Вµ Р Р…Р ВµР В»РЎРЉР В·РЎРЏ Р С—Р ВµРЎР‚Р ВµР Р…Р ВµРЎРѓРЎвЂљР С‘.",
    "You cannot manage this booking": "Р Р€ Р Р†Р В°РЎРѓ Р Р…Р ВµРЎвЂљ Р С—РЎР‚Р В°Р Р† РЎС“Р С—РЎР‚Р В°Р Р†Р В»РЎРЏРЎвЂљРЎРЉ РЎРЊРЎвЂљР С‘Р С Р В±РЎР‚Р С•Р Р…Р С‘РЎР‚Р С•Р Р†Р В°Р Р…Р С‘Р ВµР С.",
    "Only admin can run hold expiration": "Р СћР С•Р В»РЎРЉР С”Р С• admin Р СР С•Р В¶Р ВµРЎвЂљ Р В·Р В°Р С—РЎС“РЎРѓР С”Р В°РЎвЂљРЎРЉ Р С‘РЎРѓРЎвЂљР ВµРЎвЂЎР ВµР Р…Р С‘Р Вµ HOLD-Р В±РЎР‚Р С•Р Р…Р С‘РЎР‚Р С•Р Р†Р В°Р Р…Р С‘Р в„–.",
    "Only admin can expire packages": "Р СћР С•Р В»РЎРЉР С”Р С• admin Р СР С•Р В¶Р ВµРЎвЂљ Р В·Р В°Р С—РЎС“РЎРѓР С”Р В°РЎвЂљРЎРЉ Р С‘РЎРѓРЎвЂљР ВµРЎвЂЎР ВµР Р…Р С‘Р Вµ Р С—Р В°Р С”Р ВµРЎвЂљР С•Р Р†.",
    "Only teacher can list own students": "Р СћР С•Р В»РЎРЉР С”Р С• Р С—РЎР‚Р ВµР С—Р С•Р Т‘Р В°Р Р†Р В°РЎвЂљР ВµР В»РЎРЉ Р СР С•Р В¶Р ВµРЎвЂљ Р С—РЎР‚Р С•РЎРѓР СР В°РЎвЂљРЎР‚Р С‘Р Р†Р В°РЎвЂљРЎРЉ РЎРѓР С—Р С‘РЎРѓР С•Р С” РЎРѓР Р†Р С•Р С‘РЎвЂ¦ РЎС“РЎвЂЎР ВµР Р…Р С‘Р С”Р С•Р Р†.",
    "Only admin can create lesson packages": "Р СћР С•Р В»РЎРЉР С”Р С• admin Р СР С•Р В¶Р ВµРЎвЂљ РЎРѓР С•Р В·Р Т‘Р В°Р Р†Р В°РЎвЂљРЎРЉ Р С—Р В°Р С”Р ВµРЎвЂљРЎвЂ№ РЎС“РЎР‚Р С•Р С”Р С•Р Р†.",
    "Only admin or teacher can create lessons": "Р СћР С•Р В»РЎРЉР С”Р С• admin Р С‘Р В»Р С‘ teacher Р СР С•Р В¶Р ВµРЎвЂљ РЎРѓР С•Р В·Р Т‘Р В°Р Р†Р В°РЎвЂљРЎРЉ РЎС“РЎР‚Р С•Р С”Р С‘.",
    "Only admin or teacher can update lessons": "Р СћР С•Р В»РЎРЉР С”Р С• admin Р С‘Р В»Р С‘ teacher Р СР С•Р В¶Р ВµРЎвЂљ Р С‘Р В·Р СР ВµР Р…РЎРЏРЎвЂљРЎРЉ РЎС“РЎР‚Р С•Р С”Р С‘.",
    "Teacher can update only own lessons": "Teacher Р СР С•Р В¶Р ВµРЎвЂљ Р С‘Р В·Р СР ВµР Р…РЎРЏРЎвЂљРЎРЉ РЎвЂљР С•Р В»РЎРЉР С”Р С• РЎРѓР Р†Р С•Р С‘ РЎС“РЎР‚Р С•Р С”Р С‘.",
    "Lesson not found": "Р Р€РЎР‚Р С•Р С” Р Р…Р Вµ Р Р…Р В°Р в„–Р Т‘Р ВµР Р….",
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
    "Field required": "Р СџР С•Р В»Р Вµ Р С•Р В±РЎРЏР В·Р В°РЎвЂљР ВµР В»РЎРЉР Р…Р С•.",
    "Input should be a valid UUID": "Р вЂ™Р Р†Р ВµР Т‘Р С‘РЎвЂљР Вµ Р С”Р С•РЎР‚РЎР‚Р ВµР С”РЎвЂљР Р…РЎвЂ№Р в„– UUID.",
    "Input should be a valid datetime": "Р вЂ™Р Р†Р ВµР Т‘Р С‘РЎвЂљР Вµ Р С”Р С•РЎР‚РЎР‚Р ВµР С”РЎвЂљР Р…РЎС“РЎР‹ Р Т‘Р В°РЎвЂљРЎС“ Р С‘ Р Р†РЎР‚Р ВµР СРЎРЏ.",
    "Input should be a valid email address": "Р вЂ™Р Р†Р ВµР Т‘Р С‘РЎвЂљР Вµ Р С”Р С•РЎР‚РЎР‚Р ВµР С”РЎвЂљР Р…РЎвЂ№Р в„– email.",
  };

  if (normalized in directTranslations) {
    return directTranslations[normalized];
  }

  const minLengthMatch = normalized.match(/^String should have at least (\d+) character/);
  if (minLengthMatch) {
    return `Р СљР С‘Р Р…Р С‘Р СР В°Р В»РЎРЉР Р…Р В°РЎРЏ Р Т‘Р В»Р С‘Р Р…Р В°: ${minLengthMatch[1]} РЎРѓР С‘Р СР Р†Р С•Р В»Р С•Р Р†.`;
  }

  const maxLengthMatch = normalized.match(/^String should have at most (\d+) character/);
  if (maxLengthMatch) {
    return `Р СљР В°Р С”РЎРѓР С‘Р СР В°Р В»РЎРЉР Р…Р В°РЎРЏ Р Т‘Р В»Р С‘Р Р…Р В°: ${maxLengthMatch[1]} РЎРѓР С‘Р СР Р†Р С•Р В»Р С•Р Р†.`;
  }

  return translateBackendMessage(normalized);
}

function translateValidationPath(pathItems) {
  const fieldTranslations = {
    body: "РЎвЂљР ВµР В»Р С• Р В·Р В°Р С—РЎР‚Р С•РЎРѓР В°",
    query: "query-Р С—Р В°РЎР‚Р В°Р СР ВµРЎвЂљРЎР‚",
    path: "Р С—РЎС“РЎвЂљРЎРЉ",
    email: "email",
    password: "Р С—Р В°РЎР‚Р С•Р В»РЎРЉ",
    full_name: "\u0424\u0418\u041E",
    age: "\u0432\u043E\u0437\u0440\u0430\u0441\u0442",
    timezone: "РЎвЂљР В°Р в„–Р СР В·Р С•Р Р…Р В°",
    role: "РЎР‚Р С•Р В»РЎРЉ",
    slot_id: "ID РЎРѓР В»Р С•РЎвЂљР В°",
    package_id: "ID Р С—Р В°Р С”Р ВµРЎвЂљР В°",
    booking_id: "ID Р В±РЎР‚Р С•Р Р…Р С‘РЎР‚Р С•Р Р†Р В°Р Р…Р С‘РЎРЏ",
    new_slot_id: "ID Р Р…Р С•Р Р†Р С•Р С–Р С• РЎРѓР В»Р С•РЎвЂљР В°",
    reason: "Р С—РЎР‚Р С‘РЎвЂЎР С‘Р Р…Р В°",
    refresh_token: "refresh token",
  };

  return pathItems.map((item) => fieldTranslations[item] ?? String(item)).join(" -> ");
}

function fallbackStatusMessage(statusCode) {
  const fallbackMessages = {
    400: "Р СњР ВµР С”Р С•РЎР‚РЎР‚Р ВµР С”РЎвЂљР Р…РЎвЂ№Р в„– Р В·Р В°Р С—РЎР‚Р С•РЎРѓ.",
    401: "Р СћРЎР‚Р ВµР В±РЎС“Р ВµРЎвЂљРЎРѓРЎРЏ Р В°Р Р†РЎвЂљР С•РЎР‚Р С‘Р В·Р В°РЎвЂ Р С‘РЎРЏ.",
    403: "Р СњР ВµР Т‘Р С•РЎРѓРЎвЂљР В°РЎвЂљР С•РЎвЂЎР Р…Р С• Р С—РЎР‚Р В°Р Р†.",
    404: "Р В Р ВµРЎРѓРЎС“РЎР‚РЎРѓ Р Р…Р Вµ Р Р…Р В°Р в„–Р Т‘Р ВµР Р….",
    409: "Р С™Р С•Р Р…РЎвЂћР В»Р С‘Р С”РЎвЂљ Р Т‘Р В°Р Р…Р Р…РЎвЂ№РЎвЂ¦.",
    422: "Р С›РЎв‚¬Р С‘Р В±Р С”Р В° Р Р†Р В°Р В»Р С‘Р Т‘Р В°РЎвЂ Р С‘Р С‘ Р В·Р В°Р С—РЎР‚Р С•РЎРѓР В°.",
    429: "Р РЋР В»Р С‘РЎв‚¬Р С”Р С•Р С Р СР Р…Р С•Р С–Р С• Р В·Р В°Р С—РЎР‚Р С•РЎРѓР С•Р Р†. Р СџР С•Р С—РЎР‚Р С•Р В±РЎС“Р в„–РЎвЂљР Вµ Р С—Р С•Р В·Р В¶Р Вµ.",
    500: "Р вЂ™Р Р…РЎС“РЎвЂљРЎР‚Р ВµР Р…Р Р…РЎРЏРЎРЏ Р С•РЎв‚¬Р С‘Р В±Р С”Р В° РЎРѓР ВµРЎР‚Р Р†Р ВµРЎР‚Р В°.",
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
    moveToAuthState("Р РЋР ВµРЎРѓРЎРѓР С‘РЎРЏ Р С‘РЎРѓРЎвЂљР ВµР С”Р В»Р В°. Р вЂ™РЎвЂ№Р С—Р С•Р В»Р Р…Р С‘РЎвЂљР Вµ Р Р†РЎвЂ¦Р С•Р Т‘ РЎРѓР Р…Р С•Р Р†Р В°.");
    throw new Error("Р РЋР ВµРЎРѓРЎРѓР С‘РЎРЏ Р С‘РЎРѓРЎвЂљР ВµР С”Р В»Р В°. Р вЂ™РЎвЂ№Р С—Р С•Р В»Р Р…Р С‘РЎвЂљР Вµ Р Р†РЎвЂ¦Р С•Р Т‘ РЎРѓР Р…Р С•Р Р†Р В°.");
  }

  if (response.status === 401 && auth) {
    moveToAuthState("Р РЋР ВµРЎРѓРЎРѓР С‘РЎРЏ Р С‘РЎРѓРЎвЂљР ВµР С”Р В»Р В°. Р вЂ™РЎвЂ№Р С—Р С•Р В»Р Р…Р С‘РЎвЂљР Вµ Р Р†РЎвЂ¦Р С•Р Т‘ РЎРѓР Р…Р С•Р Р†Р В°.");
    throw new Error("Р РЋР ВµРЎРѓРЎРѓР С‘РЎРЏ Р С‘РЎРѓРЎвЂљР ВµР С”Р В»Р В°. Р вЂ™РЎвЂ№Р С—Р С•Р В»Р Р…Р С‘РЎвЂљР Вµ Р Р†РЎвЂ¦Р С•Р Т‘ РЎРѓР Р…Р С•Р Р†Р В°.");
  }

  if (!response.ok) {
    throw new Error(extractErrorMessage(payload, response.status));
  }

  return payload;
}

