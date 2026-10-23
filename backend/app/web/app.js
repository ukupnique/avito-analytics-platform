const STORAGE_KEY = "avito-analytics.session";
const elements = Object.fromEntries(
  [...document.querySelectorAll("[id]")].map((element) => [element.id, element]),
);
const tabs = [...document.querySelectorAll("[data-mode]")];
let mode = "login";
let tokens = readTokens();
let refreshInFlight = null;

class ApiError extends Error {
  constructor(status, detail) {
    super(typeof detail === "string" ? detail : "Ошибка запроса");
    this.status = status;
  }
}

/** Читает токены текущей вкладки; повреждённые данные не используются. */
function readTokens() {
  try {
    const value = JSON.parse(sessionStorage.getItem(STORAGE_KEY));
    return validTokens(value) ? value : null;
  } catch {
    return null;
  }
}

/** Проверяет наличие обоих токенов в ответе сервера или хранилище. */
function validTokens(value) {
  return typeof value?.access_token === "string" && value.access_token.length > 0
    && typeof value?.refresh_token === "string" && value.refresh_token.length > 0;
}

/** Обновляет токены в памяти и sessionStorage без сохранения пароля. */
function saveTokens(value) {
  tokens = value;
  try {
    if (value) sessionStorage.setItem(STORAGE_KEY, JSON.stringify(value));
    else sessionStorage.removeItem(STORAGE_KEY);
  } catch {
    // Если хранилище отключено, вход работает до перезагрузки страницы.
  }
}

/** Выполняет запрос к API с ограничением времени ожидания и разбором ошибок. */
async function api(path, { method = "GET", body, accessToken } = {}) {
  const controller = new AbortController();
  const timeout = setTimeout(() => controller.abort(), 12000);
  try {
    const response = await fetch(`/api/v1/auth/${path}`, {
      method,
      headers: {
        ...(body ? { "Content-Type": "application/json" } : {}),
        ...(accessToken ? { Authorization: `Bearer ${accessToken}` } : {}),
      },
      body: body ? JSON.stringify(body) : undefined,
      signal: controller.signal,
      cache: "no-store",
    });
    if (!response.ok) {
      const data = await response.json().catch(() => ({}));
      throw new ApiError(response.status, data.detail);
    }
    return response.status === 204 ? null : response.json();
  } finally {
    clearTimeout(timeout);
  }
}

/** Возвращает понятное пользователю сообщение без технических деталей API. */
function errorMessage(error) {
  if (error.status === 401) return "Неверная почта или пароль. Попробуйте ещё раз.";
  if (error.status === 409) return "Аккаунт с такой почтой уже существует. Переключитесь на вход.";
  if (error.status === 422) return "Проверьте адрес электронной почты и заполните все поля.";
  if (error.name === "AbortError") return "Сервер долго не отвечает. Попробуйте ещё раз.";
  return "Не удалось связаться с сервером. Попробуйте немного позже.";
}

/** Показывает сообщение в форме или на приветственной странице. */
function showMessage(element, message = "", kind = "error") {
  element.textContent = message;
  element.dataset.kind = kind;
  element.hidden = !message;
}

/** Переключает видимую страницу без изменения состояния API. */
function showView(name) {
  for (const view of ["loading", "auth", "welcome"]) {
    elements[`${view}-view`].hidden = name !== view;
  }
  elements["logout-button"].hidden = name !== "welcome";
  elements["header-caption"].hidden = name === "welcome";
}

/** Настраивает одну форму для входа или регистрации. */
function setMode(nextMode) {
  mode = nextMode;
  const registering = mode === "register";
  tabs.forEach((tab) => {
    const selected = tab.dataset.mode === mode;
    tab.setAttribute("aria-selected", String(selected));
    tab.tabIndex = selected ? 0 : -1;
  });
  elements["auth-panel"].setAttribute("aria-labelledby", `${mode}-tab`);
  elements["auth-title"].textContent = registering ? "Создадим ваш аккаунт" : "Рады видеть вас";
  elements["auth-description"].textContent = registering
    ? "Один небольшой шаг — и вы с нами." : "Войдите в аккаунт, чтобы продолжить.";
  elements["submit-label"].textContent = registering ? "Создать аккаунт" : "Войти в аккаунт";
  elements["confirmation-field"].hidden = !registering;
  elements["password-confirmation"].required = registering;
  elements.password.autocomplete = registering ? "new-password" : "current-password";
  setPasswordVisibility(false);
  showMessage(elements["form-message"]);
}

/** Показывает или скрывает пароль и его подтверждение. */
function setPasswordVisibility(visible) {
  elements.password.type = visible ? "text" : "password";
  elements["password-confirmation"].type = visible ? "text" : "password";
  elements["password-toggle"].textContent = visible ? "Скрыть" : "Показать";
  elements["password-toggle"].setAttribute("aria-label", visible ? "Скрыть пароль" : "Показать пароль");
  elements["password-toggle"].setAttribute("aria-pressed", String(visible));
}

/** Блокирует повторную отправку формы до завершения текущего запроса. */
function setFormBusy(busy) {
  [...elements["auth-form"].elements, ...tabs].forEach((element) => { element.disabled = busy; });
  elements["submit-button"].setAttribute("aria-busy", String(busy));
  elements["submit-label"].textContent = busy
    ? (mode === "register" ? "Создаём аккаунт…" : "Входим…")
    : (mode === "register" ? "Создать аккаунт" : "Войти в аккаунт");
}

/** Сериализует обновления, чтобы один refresh-токен не ушёл в два запроса. */
async function refreshTokens() {
  if (!refreshInFlight) {
    refreshInFlight = api("refresh", {
      method: "POST", body: { refresh_token: tokens.refresh_token },
    }).then((value) => {
      if (!validTokens(value)) throw new Error("Неполный ответ сервера");
      saveTokens(value);
    }).finally(() => { refreshInFlight = null; });
  }
  return refreshInFlight;
}

/** Загружает пользователя; при истёкшем access-токене один раз обновляет пару. */
async function currentUser() {
  try {
    return await api("me", { accessToken: tokens.access_token });
  } catch (error) {
    if (error.status !== 401) throw error;
    await refreshTokens();
    return api("me", { accessToken: tokens.access_token });
  }
}

/** Показывает приветствие только после успешной проверки пользователя сервером. */
function showWelcome(user) {
  elements["user-email"].textContent = user.email;
  elements["user-avatar"].textContent = user.email.charAt(0).toUpperCase();
  showMessage(elements["welcome-message"]);
  showView("welcome");
  document.title = "Добро пожаловать — Avito Analytics";
  elements["welcome-title"].focus({ preventScroll: true });
}

/** Регистрирует пользователя при необходимости, выполняет вход и открывает кабинет. */
async function submitAuth(event) {
  event.preventDefault();
  if (mode === "register" && elements.password.value !== elements["password-confirmation"].value) {
    showMessage(elements["form-message"], "Пароли не совпадают. Проверьте подтверждение.");
    elements["password-confirmation"].focus();
    return;
  }
  const credentials = { email: elements.email.value.trim(), password: elements.password.value };
  let registered = false;
  showMessage(elements["form-message"]);
  setFormBusy(true);
  try {
    if (mode === "register") {
      await api("register", { method: "POST", body: credentials });
      registered = true;
    }
    const value = await api("login", { method: "POST", body: credentials });
    if (!validTokens(value)) throw new Error("Неполный ответ сервера");
    saveTokens(value);
    const user = await currentUser();
    elements["auth-form"].reset();
    setPasswordVisibility(false);
    showWelcome(user);
  } catch (error) {
    if (registered) {
      setMode("login");
      showMessage(elements["form-message"], "Аккаунт создан. Не удалось выполнить вход — попробуйте войти ещё раз.");
    } else {
      showMessage(elements["form-message"], errorMessage(error));
    }
  } finally {
    setFormBusy(false);
  }
}

/** Отзывает сессию на сервере и после успеха удаляет токены из вкладки. */
async function logout() {
  const button = elements["logout-button"];
  button.disabled = true;
  button.setAttribute("aria-busy", "true");
  showMessage(elements["welcome-message"]);
  try {
    await api("logout", { method: "POST", body: { refresh_token: tokens.refresh_token } });
    saveTokens(null);
    elements["user-email"].textContent = "";
    elements["user-avatar"].textContent = "";
    elements["auth-form"].reset();
    setMode("login");
    showView("auth");
    document.title = "Личный кабинет — Avito Analytics";
    showMessage(elements["form-message"], "Вы вышли из аккаунта. До встречи!", "success");
    elements.email.focus();
  } catch {
    showMessage(elements["welcome-message"], "Не удалось завершить выход. Проверьте подключение и попробуйте ещё раз.");
  } finally {
    button.disabled = false;
    button.setAttribute("aria-busy", "false");
  }
}

/** Восстанавливает вход в текущей вкладке или открывает форму авторизации. */
async function init() {
  if (!tokens) {
    showView("auth");
    return;
  }
  try {
    showWelcome(await currentUser());
  } catch (error) {
    if (error.status === 401) saveTokens(null);
    showView("auth");
    showMessage(elements["form-message"], error.status === 401
      ? "Сессия завершена. Войдите в аккаунт ещё раз." : errorMessage(error));
  }
}

tabs.forEach((tab) => {
  tab.addEventListener("click", () => setMode(tab.dataset.mode));
  tab.addEventListener("keydown", (event) => {
    if (!["ArrowLeft", "ArrowRight", "Home", "End"].includes(event.key)) return;
    event.preventDefault();
    const next = event.key === "Home" ? tabs[0]
      : event.key === "End" ? tabs[1] : tabs.find((item) => item !== tab);
    setMode(next.dataset.mode);
    next.focus();
  });
});
elements["auth-form"].addEventListener("submit", submitAuth);
elements["password-toggle"].addEventListener("click", () => {
  setPasswordVisibility(elements.password.type === "password");
});
elements["logout-button"].addEventListener("click", logout);
void init();
