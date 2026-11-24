const byId = (id) => document.getElementById(id);
const pages = {
  "/dashboard": {
    title: "Employee dashboard",
    description: "Access your HR services.",
    next: ["/hr-services", "HR Services", "Browse the services available to employees."],
  },
  "/hr-services": {
    title: "HR Services",
    description: "Choose a service to contact HR.",
    back: ["/dashboard", "Employee dashboard"],
    next: ["/hr-services/salary", "Salary", "Send HR a question about your salary or payslip."],
    nextSecondary: ["/hr-services/hr-letter", "HR Letter", "Write and send an HR letter request."],
    nextTertiary: ["/hr-services/holidays", "Holiday request", "Choose your holiday dates and send HR your request."],
    nextQuaternary: ["/hr-services/insurance", "Insurance request", "Submit a request for HR to review your insurance needs."],
  },
  "/hr-services/salary": {
    title: "Salary",
    description: "Send a private salary inquiry to HR.",
    back: ["/hr-services", "HR Services"],
    panel: "salary-panel",
  },
  "/hr-services/hr-letter": {
    title: "HR Letter",
    description: "Write your request and send it to HR.",
    back: ["/hr-services", "HR Services"],
    panel: "hr-letter-panel",
  },
  "/hr-services/holidays": {
    title: "Holiday request",
    description: "Choose the dates you would like to take off and tell HR why.",
    back: ["/hr-services", "HR Services"],
    panel: "holiday-panel",
  },
  "/hr-services/insurance": {
    title: "Insurance request",
    description: "Submit an insurance request to HR.",
    back: ["/hr-services", "HR Services"],
    panel: "insurance-panel",
  },
  "/admin/dashboard": {
    title: "Admin dashboard",
    description: "Review requests and inquiries submitted by employees.",
    next: ["/admin/hr-inbox", "HR Inbox", "Open the latest messages sent to HR."],
    nextSecondary: ["/admin/holiday-requests", "Holiday requests", "Review holiday requests submitted by employees."],
    nextTertiary: ["/admin/insurance-requests", "Insurance requests", "Preview insurance requests submitted by employees."],
  },
  "/admin/hr-inbox": {
    title: "HR Inbox",
    description: "Employee messages, newest first.",
    back: ["/admin/dashboard", "Admin dashboard"],
    panel: "inbox-panel",
  },
  "/admin/holiday-requests": {
    title: "Holiday requests",
    description: "Employee holiday requests, newest first.",
    back: ["/admin/dashboard", "Admin dashboard"],
    panel: "holiday-requests-panel",
  },
  "/admin/insurance-requests": {
    title: "Insurance requests",
    description: "Employee insurance requests, newest first.",
    back: ["/admin/dashboard", "Admin dashboard"],
    panel: "insurance-requests-panel",
  },
};

const page = pages[location.pathname];
const dateFormat = new Intl.DateTimeFormat("en-EG", {
  dateStyle: "medium", timeStyle: "short", timeZone: "Africa/Cairo",
});

function feedback(id, message, kind = "info") {
  const field = byId(id);
  field.textContent = message;
  field.dataset.kind = kind;
  field.hidden = !message;
}

async function request(path, options = {}) {
  const response = await fetch(path, { ...options, credentials: "same-origin", cache: "no-store" });
  if (response.status === 401) {
    location.replace("/");
    throw new Error("Your session ended. Please sign in again.");
  }
  if (!response.ok) {
    const result = await response.json().catch(() => ({}));
    throw new Error(typeof result.detail === "string" && response.status < 500
      ? result.detail : "Could not complete the request. Please try again.");
  }
  return response.status === 204 ? null : response.json();
}

async function post(path, payload) {
  const { csrf_token } = await request("/api/v1/auth/csrf");
  const headers = { "X-CSRF-Token": csrf_token };
  const options = { method: "POST", headers };
  if (payload) {
    headers["Content-Type"] = "application/json";
    options.body = JSON.stringify(payload);
  }
  return request(path, options);
}

function showPage() {
  document.title = page.title + " | LSG Sky Chefs";
  byId("page-title").textContent = page.title;
  byId("page-description").textContent = page.description;

  if (page.back) {
    const link = byId("back");
    [link.href, link.textContent] = page.back;
    link.hidden = false;
  }
  if (page.next) {
    const link = byId("next");
    [link.href, link.textContent, byId("next-description").textContent] = page.next;
    byId("navigation-card").hidden = false;
  }
  if (page.nextSecondary) {
    const link = byId("next-secondary");
    [link.href, link.textContent, byId("next-secondary-description").textContent] = page.nextSecondary;
    byId("secondary-navigation-card").hidden = false;
  }
  if (page.nextTertiary) {
    const link = byId("next-tertiary");
    [link.href, link.textContent, byId("next-tertiary-description").textContent] = page.nextTertiary;
    byId("tertiary-navigation-card").hidden = false;
  }
  if (page.nextQuaternary) {
    const link = byId("next-quaternary");
    [link.href, link.textContent, byId("next-quaternary-description").textContent] = page.nextQuaternary;
    byId("quaternary-navigation-card").hidden = false;
  }
  if (page.panel) byId(page.panel).hidden = false;
}

const logout = byId("logout");
logout.addEventListener("click", async () => {
  logout.disabled = true;
  feedback("session-feedback", "");
  try {
    await post("/api/v1/auth/logout");
    location.replace("/");
  } catch (error) {
    feedback("session-feedback", error.message, "error");
    logout.disabled = false;
  }
});

function bindRequestForm(formId, messageId, feedbackId, endpoint, emptyMessage) {
  const form = byId(formId);
  const send = form.querySelector("button");

  form.addEventListener("submit", async (event) => {
    event.preventDefault();
    const message = byId(messageId).value.trim();
    if (!message) {
      feedback(feedbackId, emptyMessage, "error");
      byId(messageId).focus();
      return;
    }

    send.disabled = true;
    logout.disabled = true;
    feedback(feedbackId, "");
    try {
      const result = await post(endpoint, { message });
      form.reset();
      feedback(feedbackId, result.confirmation, "success");
    } catch (error) {
      feedback(feedbackId, error.message, "error");
    } finally {
      send.disabled = false;
      logout.disabled = false;
    }
  });
}

bindRequestForm(
  "salary-form",
  "message",
  "salary-feedback",
  "/api/v1/hr/services/salary/messages",
  "Write a message before sending.",
);
bindRequestForm(
  "hr-letter-form",
  "hr-letter-message",
  "hr-letter-feedback",
  "/api/v1/hr/services/hr-letter/requests",
  "Write your HR Letter request before sending.",
);

const holidayForm = byId("holiday-form");
holidayForm.addEventListener("submit", async (event) => {
  event.preventDefault();
  const startDate = byId("holiday-start-date").value;
  const endDate = byId("holiday-end-date").value;
  const reason = byId("holiday-reason").value.trim();
  if (endDate < startDate) {
    feedback("holiday-feedback", "The last day must be on or after the first day.", "error");
    byId("holiday-end-date").focus();
    return;
  }
  if (!reason) {
    feedback("holiday-feedback", "Enter a reason for your holiday request.", "error");
    byId("holiday-reason").focus();
    return;
  }

  const submit = holidayForm.querySelector("button");
  submit.disabled = true;
  logout.disabled = true;
  feedback("holiday-feedback", "");
  try {
    const result = await post("/api/v1/hr/services/holidays/requests", {
      start_date: startDate,
      end_date: endDate,
      reason,
    });
    holidayForm.reset();
    feedback("holiday-feedback", result.confirmation, "success");
  } catch (error) {
    feedback("holiday-feedback", error.message, "error");
  } finally {
    submit.disabled = false;
    logout.disabled = false;
  }
});

const refresh = byId("refresh");
const loadMore = byId("load-more");
const pageSize = 50;
let beforeId;

function appendMessage(item) {
  const entry = document.createElement("li");
  const sender = document.createElement("h3");
  sender.textContent = item.employee_name;
  const details = document.createElement("p");
  details.className = "muted";
  const service = {
    salary: "Salary",
    hr_letter: "HR Letter",
  }[item.service] || item.service;
  details.textContent = [service, dateFormat.format(new Date(item.created_at)) + " Cairo"].join(" · ");
  const body = document.createElement("p");
  body.className = "message-body";
  body.textContent = item.message;
  entry.append(sender, details, body);
  byId("messages").append(entry);
}

async function loadInbox(append = false) {
  const query = new URLSearchParams({ limit: pageSize });
  if (append) query.set("before_id", beforeId);
  refresh.disabled = true;
  loadMore.disabled = true;
  feedback("inbox-feedback", "Loading messages…");

  try {
    const entries = await request("/api/v1/admin/hr/messages?" + query);
    if (!append) byId("messages").replaceChildren();
    entries.forEach(appendMessage);
    beforeId = entries.at(-1)?.id;
    loadMore.hidden = entries.length < pageSize;
    const emptyText = append ? "No more messages." : "No messages yet.";
    feedback("inbox-feedback", entries.length ? "" : emptyText);
  } catch (error) {
    feedback("inbox-feedback", error.message, "error");
  } finally {
    refresh.disabled = false;
    loadMore.disabled = false;
  }
}

refresh.addEventListener("click", () => loadInbox());
loadMore.addEventListener("click", () => loadInbox(true));

const refreshHolidays = byId("refresh-holidays");
const loadMoreHolidays = byId("load-more-holidays");
let beforeHolidayId;

function appendHolidayRequest(item) {
  const entry = document.createElement("li");
  const sender = document.createElement("h3");
  sender.textContent = item.employee_name;
  const dates = document.createElement("p");
  dates.className = "muted";
  const start = new Date(item.start_date + "T00:00:00");
  const end = new Date(item.end_date + "T00:00:00");
  dates.textContent = `Holiday: ${new Intl.DateTimeFormat("en-EG", { dateStyle: "medium" }).format(start)} – ${new Intl.DateTimeFormat("en-EG", { dateStyle: "medium" }).format(end)}`;
  const submitted = document.createElement("p");
  submitted.className = "muted";
  submitted.textContent = "Submitted " + dateFormat.format(new Date(item.created_at)) + " Cairo";
  const reason = document.createElement("p");
  reason.className = "message-body";
  reason.textContent = item.reason;
  entry.append(sender, dates, submitted, reason);
  byId("holiday-requests").append(entry);
}

async function loadHolidayRequests(append = false) {
  const query = new URLSearchParams({ limit: pageSize });
  if (append) query.set("before_id", beforeHolidayId);
  refreshHolidays.disabled = true;
  loadMoreHolidays.disabled = true;
  feedback("holiday-requests-feedback", "Loading holiday requests…");

  try {
    const entries = await request("/api/v1/admin/hr/holiday-requests?" + query);
    if (!append) byId("holiday-requests").replaceChildren();
    entries.forEach(appendHolidayRequest);
    beforeHolidayId = entries.at(-1)?.id;
    loadMoreHolidays.hidden = entries.length < pageSize;
    const emptyText = append ? "No more holiday requests." : "No holiday requests yet.";
    feedback("holiday-requests-feedback", entries.length ? "" : emptyText);
  } catch (error) {
    feedback("holiday-requests-feedback", error.message, "error");
  } finally {
    refreshHolidays.disabled = false;
    loadMoreHolidays.disabled = false;
  }
}

refreshHolidays.addEventListener("click", () => loadHolidayRequests());
loadMoreHolidays.addEventListener("click", () => loadHolidayRequests(true));

const insuranceForm = byId("insurance-form");
insuranceForm.addEventListener("submit", async (event) => {
  event.preventDefault();
  const employeeCode = byId("insurance-employee-code").value.trim();
  const message = byId("insurance-message").value.trim();
  if (!employeeCode) {
    feedback("insurance-feedback", "Enter your employee code.", "error");
    byId("insurance-employee-code").focus();
    return;
  }
  if (!message) {
    feedback("insurance-feedback", "Write a message for HR.", "error");
    byId("insurance-message").focus();
    return;
  }

  const submit = insuranceForm.querySelector("button");
  submit.disabled = true;
  logout.disabled = true;
  feedback("insurance-feedback", "");
  try {
    const result = await post("/api/v1/hr/services/insurance/requests", {
      employee_code: employeeCode,
      message,
    });
    insuranceForm.reset();
    feedback("insurance-feedback", result.confirmation, "success");
  } catch (error) {
    feedback("insurance-feedback", error.message, "error");
  } finally {
    submit.disabled = false;
    logout.disabled = false;
  }
});

const insuranceChangeForm = byId("insurance-change-form");
insuranceChangeForm.addEventListener("submit", async (event) => {
  event.preventDefault();
  const submit = insuranceChangeForm.querySelector("button");
  submit.disabled = true;
  logout.disabled = true;
  feedback("insurance-change-feedback", "");
  try {
    const result = await post("/api/v1/hr/services/insurance/changes");
    feedback("insurance-change-feedback", result.confirmation, "success");
  } catch (error) {
    feedback("insurance-change-feedback", error.message, "error");
  } finally {
    submit.disabled = false;
    logout.disabled = false;
  }
});

const refreshInsurance = byId("refresh-insurance");
const loadMoreInsurance = byId("load-more-insurance");
let beforeInsuranceId;

function appendInsuranceRequest(item) {
  const entry = document.createElement("li");
  const sender = document.createElement("h3");
  sender.textContent = item.employee_name;
  const submitted = document.createElement("p");
  submitted.className = "muted";
  submitted.textContent = [
    "Employee code: " + (item.employee_code || "Not recorded"),
    "Submitted " + dateFormat.format(new Date(item.created_at)) + " Cairo",
  ].join(" · ");
  const body = document.createElement("p");
  body.className = "message-body";
  body.textContent = item.message || "No message was recorded.";
  entry.append(sender, submitted, body);
  byId("insurance-requests").append(entry);
}

async function loadInsuranceRequests(append = false) {
  const query = new URLSearchParams({ limit: pageSize });
  if (append) query.set("before_id", beforeInsuranceId);
  refreshInsurance.disabled = true;
  loadMoreInsurance.disabled = true;
  feedback("insurance-requests-feedback", "Loading insurance requests…");

  try {
    const entries = await request("/api/v1/admin/hr/insurance-requests?" + query);
    if (!append) byId("insurance-requests").replaceChildren();
    entries.forEach(appendInsuranceRequest);
    beforeInsuranceId = entries.at(-1)?.id;
    loadMoreInsurance.hidden = entries.length < pageSize;
    const emptyText = append ? "No more insurance requests." : "No insurance requests yet.";
    feedback("insurance-requests-feedback", entries.length ? "" : emptyText);
  } catch (error) {
    feedback("insurance-requests-feedback", error.message, "error");
  } finally {
    refreshInsurance.disabled = false;
    loadMoreInsurance.disabled = false;
  }
}

refreshInsurance.addEventListener("click", () => loadInsuranceRequests());
loadMoreInsurance.addEventListener("click", () => loadInsuranceRequests(true));

const refreshInsuranceChanges = byId("refresh-insurance-changes");
const loadMoreInsuranceChanges = byId("load-more-insurance-changes");
let beforeInsuranceChangeId;

function appendInsuranceChange(item) {
  const entry = document.createElement("li");
  const sender = document.createElement("h3");
  sender.textContent = item.employee_name;
  const submitted = document.createElement("p");
  submitted.className = "muted";
  submitted.textContent = "Insurance change · Submitted " + dateFormat.format(new Date(item.created_at)) + " Cairo";
  entry.append(sender, submitted);
  byId("insurance-changes").append(entry);
}

async function loadInsuranceChanges(append = false) {
  const query = new URLSearchParams({ limit: pageSize });
  if (append) query.set("before_id", beforeInsuranceChangeId);
  refreshInsuranceChanges.disabled = true;
  loadMoreInsuranceChanges.disabled = true;
  feedback("insurance-changes-feedback", "Loading insurance changes…");

  try {
    const entries = await request("/api/v1/admin/hr/insurance-changes?" + query);
    if (!append) byId("insurance-changes").replaceChildren();
    entries.forEach(appendInsuranceChange);
    beforeInsuranceChangeId = entries.at(-1)?.id;
    loadMoreInsuranceChanges.hidden = entries.length < pageSize;
    const emptyText = append ? "No more insurance changes." : "No insurance changes yet.";
    feedback("insurance-changes-feedback", entries.length ? "" : emptyText);
  } catch (error) {
    feedback("insurance-changes-feedback", error.message, "error");
  } finally {
    refreshInsuranceChanges.disabled = false;
    loadMoreInsuranceChanges.disabled = false;
  }
}

refreshInsuranceChanges.addEventListener("click", () => loadInsuranceChanges());
loadMoreInsuranceChanges.addEventListener("click", () => loadInsuranceChanges(true));

async function start() {
  showPage();
  try {
    const account = await request("/api/v1/me");
    byId("account-name").textContent = account.name;
  } catch (error) {
    feedback("session-feedback", error.message, "error");
  }
  if (page.panel === "inbox-panel") await loadInbox();
  if (page.panel === "holiday-requests-panel") await loadHolidayRequests();
  if (page.panel === "insurance-requests-panel") {
    await Promise.all([loadInsuranceRequests(), loadInsuranceChanges()]);
  }
}

start();
