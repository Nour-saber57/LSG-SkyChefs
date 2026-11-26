const byId = (id) => document.getElementById(id);
const pages = {
  "/dashboard": {
    title: "Employee dashboard",
    description: "Access your HR services.",
    next: ["/hr-services", "HR Services", "Browse the services available to employees."],
    nextSecondary: ["/courses", "Courses", "View available employee courses and respond."],
    nextTertiary: ["/activities", "Activities", "View activities and programs shared with you."],
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
  "/courses": {
    title: "Courses",
    description: "Review available courses and choose whether to enroll or excuse yourself.",
    back: ["/dashboard", "Employee dashboard"],
    panel: "courses-panel",
  },
  "/activities": {
    title: "Activities and programs",
    description: "View activities and programs shared with you.",
    back: ["/dashboard", "Employee dashboard"],
    panel: "activities-panel",
  },
  "/admin/dashboard": {
    title: "Admin dashboard",
    description: "Review requests and inquiries submitted by employees.",
    next: ["/admin/hr-inbox", "HR Inbox", "Open the latest messages sent to HR."],
    nextSecondary: ["/admin/holiday-requests", "Holiday requests", "Review holiday requests submitted by employees."],
    nextTertiary: ["/admin/insurance-requests", "Insurance requests", "Preview insurance requests submitted by employees."],
    nextQuaternary: ["/admin/courses", "Courses", "Add courses and review employee responses."],
    nextActivity: ["/admin/activities", "Activities", "Publish activities and programs for all or selected employees."],
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
  "/admin/courses": {
    title: "Manage courses",
    description: "Add courses and review which employees enrolled or excused themselves.",
    back: ["/admin/dashboard", "Admin dashboard"],
    panel: "admin-courses-panel",
  },
  "/admin/activities": {
    title: "Manage activities",
    description: "Publish activities and programs for all employees or selected people.",
    back: ["/admin/dashboard", "Admin dashboard"],
    panel: "admin-activities-panel",
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
    const detail = Array.isArray(result.detail)
      ? result.detail.map((issue) => issue.msg).filter(Boolean).join(" ")
      : result.detail;
    throw new Error(typeof detail === "string" && response.status < 500
      ? detail : "Could not complete the request. Please try again.");
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

async function put(path, payload) {
  const { csrf_token } = await request("/api/v1/auth/csrf");
  return request(path, {
    method: "PUT",
    headers: {
      "Content-Type": "application/json",
      "X-CSRF-Token": csrf_token,
    },
    body: JSON.stringify(payload),
  });
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
  if (page.nextActivity) {
    const link = byId("next-activity");
    [link.href, link.textContent, byId("next-activity-description").textContent] = page.nextActivity;
    byId("activity-navigation-card").hidden = false;
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

function addCourseDetails(container, course) {
  if (course.image_url) {
    const image = document.createElement("img");
    image.src = course.image_url;
    image.alt = "Course image for " + course.title;
    image.className = "course-image";
    container.append(image);
  }
  const title = document.createElement("h3");
  title.textContent = course.title;
  const info = document.createElement("p");
  info.className = "muted";
  const dates = course.end_date
    ? `${course.start_date} – ${course.end_date}`
    : course.start_date;
  info.textContent = [dates, course.duration, course.location].join(" · ");
  const description = document.createElement("p");
  description.className = "message-body";
  description.textContent = course.description;
  container.append(title, info, description);
}

function appendEmployeeCourse(course) {
  const card = document.createElement("article");
  card.className = "course-card";
  addCourseDetails(card, course);

  const current = document.createElement("p");
  current.className = "muted";
  current.textContent = course.decision
    ? `Your current response: ${course.decision}${course.reason ? " — " + course.reason : ""}`
    : "You have not responded to this course.";
  card.append(current);

  const form = document.createElement("form");
  const decision = document.createElement("select");
  decision.id = `course-decision-${course.id}`;
  decision.setAttribute("aria-label", "Course response");
  for (const [value, label] of [["enrolled", "Enroll"], ["excused", "Excuse myself"]]) {
    const option = document.createElement("option");
    option.value = value;
    option.textContent = label;
    decision.append(option);
  }
  if (course.decision) decision.value = course.decision;
  const reasonLabel = document.createElement("label");
  reasonLabel.htmlFor = `course-reason-${course.id}`;
  reasonLabel.textContent = "Reason for excusing yourself";
  const reason = document.createElement("textarea");
  reason.id = `course-reason-${course.id}`;
  reason.rows = 3;
  reason.maxLength = 2000;
  reason.value = course.decision === "excused" ? course.reason || "" : "";
  reason.hidden = decision.value !== "excused";
  reason.required = decision.value === "excused";
  decision.addEventListener("change", () => {
    reason.hidden = decision.value !== "excused";
    reason.required = decision.value === "excused";
  });
  const submit = document.createElement("button");
  submit.type = "submit";
  submit.textContent = "Save response";
  const result = document.createElement("p");
  result.className = "feedback";
  result.setAttribute("role", "status");
  result.hidden = true;
  form.append(decision, reasonLabel, reason, submit, result);
  form.addEventListener("submit", async (event) => {
    event.preventDefault();
    const reasonText = reason.value.trim();
    if (decision.value === "excused" && !reasonText) {
      result.textContent = "Enter a reason for excusing yourself.";
      result.dataset.kind = "error";
      result.hidden = false;
      reason.focus();
      return;
    }
    submit.disabled = true;
    try {
      await put(`/api/v1/courses/${course.id}/decision`, {
        decision: decision.value,
        reason: decision.value === "excused" ? reasonText : null,
      });
      await loadCourses();
    } catch (error) {
      result.textContent = error.message;
      result.dataset.kind = "error";
      result.hidden = false;
    } finally {
      submit.disabled = false;
    }
  });
  card.append(form);
  byId("courses-list").append(card);
}

const coursePageSize = 25;
const moreCourses = byId("more-courses");
let courseOffset = 0;
let loadingCourses = false;

async function loadCourses(append = false) {
  const refreshCourses = byId("refresh-courses");
  if (loadingCourses) return;
  loadingCourses = true;
  const offset = append ? courseOffset : 0;
  if (refreshCourses) refreshCourses.disabled = true;
  moreCourses.disabled = true;
  feedback("courses-feedback", "Loading courses…");
  try {
    const query = new URLSearchParams({
      offset: String(offset),
      limit: String(coursePageSize),
    });
    const courses = await request("/api/v1/courses?" + query);
    if (!append) byId("courses-list").replaceChildren();
    courses.forEach(appendEmployeeCourse);
    courseOffset = offset + courses.length;
    moreCourses.hidden = courses.length < coursePageSize;
    feedback(
      "courses-feedback",
      courses.length ? "" : append ? "No more courses." : "No courses are available yet.",
    );
  } catch (error) {
    feedback("courses-feedback", error.message, "error");
  } finally {
    if (refreshCourses) refreshCourses.disabled = false;
    moreCourses.disabled = false;
    loadingCourses = false;
  }
}

function appendAdminCourse(course) {
  const card = document.createElement("article");
  card.className = "course-card";
  addCourseDetails(card, course);

  const status = document.createElement("p");
  status.className = "muted";
  status.textContent = course.archived_at ? "Archived" : "Active";
  card.append(status);

  const counts = document.createElement("p");
  counts.className = "muted";
  counts.textContent = `${course.response_count} responses · ${course.enrolled_count} enrolled · ${course.excused_count} excused`;
  card.append(counts);

  const responsesTitle = document.createElement("h4");
  responsesTitle.textContent = "Employee responses";
  card.append(responsesTitle);

  const responseList = document.createElement("ul");
  const responseFeedback = document.createElement("p");
  responseFeedback.className = "feedback";
  responseFeedback.setAttribute("role", "status");
  responseFeedback.hidden = true;
  const moreResponses = document.createElement("button");
  moreResponses.type = "button";
  moreResponses.className = "secondary";
  moreResponses.textContent = "Load more responses";
  moreResponses.hidden = true;
  let responseOffset = 0;
  let loadingResponses = false;

  async function loadResponses(append = false) {
    if (loadingResponses) return;
    loadingResponses = true;
    moreResponses.disabled = true;
    feedbackForElement(responseFeedback, "Loading employee responses…");
    try {
      const query = new URLSearchParams({
        offset: String(append ? responseOffset : 0),
        limit: "50",
      });
      const responses = await request(
        `/api/v1/admin/courses/${course.id}/decisions?${query}`,
      );
      if (!append) responseList.replaceChildren();
      for (const response of responses) {
        const item = document.createElement("li");
        item.textContent = `${response.employee_name} — ${response.decision}`
          + (response.reason ? `: ${response.reason}` : "");
        responseList.append(item);
      }
      responseOffset = (append ? responseOffset : 0) + responses.length;
      moreResponses.hidden = responses.length < 50;
      feedbackForElement(
        responseFeedback,
        responses.length ? "" : append ? "No more responses." : "No employees have responded yet.",
      );
    } catch (error) {
      feedbackForElement(responseFeedback, error.message, "error");
    } finally {
      moreResponses.disabled = false;
      loadingResponses = false;
    }
  }

  card.append(responseList, responseFeedback, moreResponses);
  if (course.response_count) loadResponses();

  moreResponses.addEventListener("click", () => loadResponses(true));

  if (!course.archived_at) {
    const archiveButton = document.createElement("button");
    archiveButton.type = "button";
    archiveButton.className = "secondary";
    archiveButton.textContent = "Archive course";
    archiveButton.addEventListener("click", async () => {
      archiveButton.disabled = true;
      try {
        const { csrf_token } = await request("/api/v1/auth/csrf");
        await request(`/api/v1/admin/courses/${course.id}`, {
          method: "DELETE",
          headers: { "X-CSRF-Token": csrf_token },
        });
        await loadAdminCourses();
      } catch (error) {
        feedbackForElement(responseFeedback, error.message, "error");
      } finally {
        archiveButton.disabled = false;
      }
    });
    card.append(archiveButton);
  }

  byId("admin-courses-list").append(card);
}

function feedbackForElement(field, message, kind = "info") {
  field.textContent = message;
  field.dataset.kind = kind;
  field.hidden = !message;
}

const adminCoursePageSize = 25;
const moreAdminCourses = byId("more-admin-courses");
const courseArchiveFilter = byId("course-archive-filter");
let adminCourseOffset = 0;
let loadingAdminCourses = false;

async function loadAdminCourses(append = false) {
  if (loadingAdminCourses) return;
  loadingAdminCourses = true;
  const offset = append ? adminCourseOffset : 0;
  const refreshAdminCourses = byId("refresh-admin-courses");
  refreshAdminCourses.disabled = true;
  courseArchiveFilter.disabled = true;
  moreAdminCourses.disabled = true;
  feedback("admin-courses-feedback", "Loading course responses…");
  try {
    const query = new URLSearchParams({
      archived: courseArchiveFilter.value,
      offset: String(offset),
      limit: String(adminCoursePageSize),
    });
    const courses = await request("/api/v1/admin/courses?" + query);
    if (!append) byId("admin-courses-list").replaceChildren();
    courses.forEach(appendAdminCourse);
    adminCourseOffset = offset + courses.length;
    moreAdminCourses.hidden = courses.length < adminCoursePageSize;
    feedback(
      "admin-courses-feedback",
      courses.length ? "" : append ? "No more courses." : "No courses have been added.",
    );
  } catch (error) {
    feedback("admin-courses-feedback", error.message, "error");
  } finally {
    refreshAdminCourses.disabled = false;
    courseArchiveFilter.disabled = false;
    moreAdminCourses.disabled = false;
    loadingAdminCourses = false;
  }
}

byId("refresh-courses").addEventListener("click", () => loadCourses());
moreCourses.addEventListener("click", () => loadCourses(true));
byId("refresh-admin-courses").addEventListener("click", () => loadAdminCourses());
moreAdminCourses.addEventListener("click", () => loadAdminCourses(true));
courseArchiveFilter.addEventListener("change", () => loadAdminCourses());
byId("course-form").addEventListener("submit", async (event) => {
  event.preventDefault();
  const form = byId("course-form");
  const submit = form.querySelector("button");
  const startDate = byId("course-start-date").value;
  const endDate = byId("course-end-date").value;
  if (endDate < startDate) {
    feedback("course-form-feedback", "The end date must be on or after the start date.", "error");
    byId("course-end-date").focus();
    return;
  }
  submit.disabled = true;
  feedback("course-form-feedback", "");
  try {
    const { csrf_token } = await request("/api/v1/auth/csrf");
    await request("/api/v1/admin/courses", {
      method: "POST",
      headers: { "X-CSRF-Token": csrf_token },
      body: new FormData(form),
    });
    form.reset();
    feedback("course-form-feedback", "Course created.", "success");
    await loadAdminCourses();
  } catch (error) {
    feedback("course-form-feedback", error.message, "error");
  } finally {
    submit.disabled = false;
  }
});

function appendActivity(container, activity, admin = false) {
  const card = document.createElement("article");
  card.className = "activity-card";

  const title = document.createElement("h3");
  title.textContent = activity.title;
  const details = document.createElement("p");
  details.className = "muted";
  details.textContent = [
    activity.kind === "program" ? "Program" : "Activity",
    `${activity.start_date} – ${activity.end_date}`,
    activity.location,
  ].join(" · ");
  const description = document.createElement("p");
  description.className = "message-body";
  description.textContent = activity.description;
  card.append(title, details, description);

  if (admin) {
    const audience = document.createElement("p");
    audience.className = "muted";
    audience.textContent = activity.all_employees
      ? "Audience: All employees"
      : `Audience: ${activity.employee_names.join(", ")}`;
    card.append(audience);

    if (activity.archived_at === null) {
      const archive = document.createElement("button");
      archive.type = "button";
      archive.className = "secondary";
      archive.textContent = "Archive activity";
      archive.addEventListener("click", async () => {
        archive.disabled = true;
        try {
          const { csrf_token } = await request("/api/v1/auth/csrf");
          await request(`/api/v1/admin/activities/${activity.id}`, {
            method: "DELETE",
            headers: { "X-CSRF-Token": csrf_token },
          });
          await loadAdminActivities();
        } catch (error) {
          feedback("admin-activities-feedback", error.message, "error");
        } finally {
          archive.disabled = false;
        }
      });
      card.append(archive);
    } else {
      const status = document.createElement("p");
      status.className = "muted";
      status.textContent = "Archived";
      card.append(status);
    }
  }

  container.append(card);
}

async function loadActivities() {
  const refresh = byId("refresh-activities");
  refresh.disabled = true;
  feedback("activities-feedback", "Loading activities…");
  try {
    const activities = await request("/api/v1/activities?limit=100");
    byId("activities-list").replaceChildren();
    activities.forEach((activity) => appendActivity(byId("activities-list"), activity));
    feedback(
      "activities-feedback",
      activities.length ? "" : "No activities or programs have been shared with you.",
    );
  } catch (error) {
    feedback("activities-feedback", error.message, "error");
  } finally {
    refresh.disabled = false;
  }
}

const activityAudience = byId("activity-audience");
const activityEmployeePicker = byId("activity-employee-picker");
const activityArchiveFilter = byId("activity-archive-filter");

activityAudience.addEventListener("change", () => {
  activityEmployeePicker.hidden = activityAudience.value !== "selected";
});

async function loadActivityEmployees() {
  feedback("activity-employees-feedback", "Loading employees…");
  try {
    const employees = await request("/api/v1/admin/activities/recipients");
    const list = byId("activity-employees");
    list.replaceChildren();
    for (const employee of employees) {
      const label = document.createElement("label");
      label.className = "employee-option";
      const checkbox = document.createElement("input");
      checkbox.type = "checkbox";
      checkbox.name = "employee_ids";
      checkbox.value = String(employee.id);
      const name = document.createElement("span");
      name.textContent = `${employee.name} (${employee.identity})`;
      label.append(checkbox, name);
      list.append(label);
    }
    feedback(
      "activity-employees-feedback",
      employees.length ? "" : "There are no active employees to select.",
    );
  } catch (error) {
    feedback("activity-employees-feedback", error.message, "error");
  }
}

async function loadAdminActivities() {
  const refresh = byId("refresh-admin-activities");
  refresh.disabled = true;
  activityArchiveFilter.disabled = true;
  feedback("admin-activities-feedback", "Loading activities…");
  try {
    const query = new URLSearchParams({ archived: activityArchiveFilter.value, limit: "100" });
    const activities = await request("/api/v1/admin/activities?" + query);
    const list = byId("admin-activities-list");
    list.replaceChildren();
    activities.forEach((activity) => appendActivity(list, activity, true));
    feedback(
      "admin-activities-feedback",
      activities.length ? "" : "No activities or programs have been published.",
    );
  } catch (error) {
    feedback("admin-activities-feedback", error.message, "error");
  } finally {
    refresh.disabled = false;
    activityArchiveFilter.disabled = false;
  }
}

byId("refresh-activities").addEventListener("click", () => loadActivities());
byId("refresh-admin-activities").addEventListener("click", () => loadAdminActivities());
activityArchiveFilter.addEventListener("change", () => loadAdminActivities());
byId("activity-form").addEventListener("submit", async (event) => {
  event.preventDefault();
  const form = byId("activity-form");
  const submit = form.querySelector('button[type="submit"]');
  const startDate = byId("activity-start-date").value;
  const endDate = byId("activity-end-date").value;
  if (endDate < startDate) {
    feedback("activity-form-feedback", "The end date must be on or after the start date.", "error");
    byId("activity-end-date").focus();
    return;
  }

  const employeeIds = [...form.querySelectorAll('input[name="employee_ids"]:checked')]
    .map((checkbox) => Number(checkbox.value));
  if (activityAudience.value === "selected" && employeeIds.length === 0) {
    feedback("activity-form-feedback", "Select at least one employee for this activity.", "error");
    byId("activity-employees").querySelector("input")?.focus();
    return;
  }

  submit.disabled = true;
  feedback("activity-form-feedback", "");
  try {
    await post("/api/v1/admin/activities", {
      title: byId("activity-title").value.trim(),
      kind: byId("activity-kind").value,
      description: byId("activity-description").value.trim(),
      start_date: startDate,
      end_date: endDate,
      location: byId("activity-location").value.trim(),
      employee_ids: activityAudience.value === "selected" ? employeeIds : null,
    });
    form.reset();
    activityEmployeePicker.hidden = true;
    feedback("activity-form-feedback", "Activity published.", "success");
    await loadAdminActivities();
  } catch (error) {
    feedback("activity-form-feedback", error.message, "error");
  } finally {
    submit.disabled = false;
  }
});

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
  if (page.panel === "courses-panel") await loadCourses();
  if (page.panel === "admin-courses-panel") await loadAdminCourses();
  if (page.panel === "activities-panel") await loadActivities();
  if (page.panel === "admin-activities-panel") {
    await Promise.all([loadActivityEmployees(), loadAdminActivities()]);
  }
}

start();
