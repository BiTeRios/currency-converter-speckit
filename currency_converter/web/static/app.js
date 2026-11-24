"use strict";

const byId = (id) => document.getElementById(id);
const form = byId("converter");
const amount = byId("amount");
const from = byId("from");
const to = byId("to");
const rateDate = byId("date");
const convert = byId("convert");
const refresh = byId("refresh");
const swap = byId("swap");
const today = byId("today");
const status = byId("status");
const problem = byId("problem");
const recovery = byId("recovery");
const useSaved = byId("use-saved");
const retry = byId("retry");
const loading = byId("loading");
const noRates = status.textContent;

let busy = false;
let serverToday = "";
let active = null;
let offered = null;
let initializedOptions = false;

function show(id, text) {
  const element = byId(id);
  element.textContent = text || "";
  element.hidden = !text;
}

function showOutput(result, rates) {
  show("result", result);
  show("rates", rates);
  byId("result-hint").hidden = Boolean(result);
}

function setOptions(currencies) {
  let removed = false;
  for (const [select, defaultCode] of [[from, "USD"], [to, "MDL"]]) {
    const current = initializedOptions ? select.value : defaultCode;
    select.replaceChildren(
      new Option("Выберите валюту", ""),
      ...currencies.map(([code, label]) => new Option(label, code)),
    );
    const available = currencies.some(([code]) => code === current);
    removed ||= initializedOptions && Boolean(current) && !available;
    select.value = available ? current : "";
  }
  initializedOptions = true;
  return removed;
}

function activate(snapshot) {
  active = snapshot;
  const removed = setOptions(snapshot.currencies);
  status.textContent = snapshot.statusText;
  show("rate-notice", [snapshot.notice, snapshot.warning].filter(Boolean).join(" "));
  show("selection-notice", removed ? "Выберите валюту заново." : "");
}

function updateControls() {
  const hasOptions = from.options.length > 1;
  amount.readOnly = busy;
  rateDate.readOnly = busy;
  from.disabled = to.disabled = busy || !hasOptions;
  today.disabled = refresh.disabled = busy || !serverToday;
  swap.disabled = busy || !from.value || !to.value;
  convert.disabled = busy || !amount.value.trim() || !from.value || !to.value;
  useSaved.disabled = retry.disabled = busy;
  loading.hidden = !busy;
}

function showProblem(error = "", canRetry = false, saved = null) {
  offered = saved;
  problem.hidden = !error;
  byId("error").textContent = error;
  recovery.hidden = !canRetry;
  useSaved.hidden = !saved;
  useSaved.textContent = saved ? `Использовать сохранённый курс от ${saved.ratesDate}` : "";
}

async function request(path, payload) {
  const options = payload === undefined ? {} : {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(payload),
  };
  const response = await fetch(path, options);
  return response.json();
}

function applyReply(reply) {
  if (reply.snapshot) {
    activate(reply.snapshot);
    if (!reply.snapshot.warning) show("cache-notice", "");
  } else if (reply.retry) {
    active = null;
    status.textContent = noRates;
    show("rate-notice", "");
  }
  if (reply.cacheWarning) show("cache-notice", reply.cacheWarning);
  if (reply.error) {
    const noSaved = reply.retry && reply.saved === null ? " Сохранённых курсов нет." : "";
    showProblem(reply.error + noSaved, reply.retry, reply.saved);
  } else if (reply.result) {
    showOutput(reply.result, reply.rates);
    if (reply.note) show("selection-notice", reply.note);
  }
}

async function run(action) {
  if (busy) return;
  busy = true;
  showOutput();
  showProblem();
  show("selection-notice", "");
  updateControls();
  try {
    await action();
  } catch {
    showProblem("Нет связи с локальным приложением. Попробуйте ещё раз.", true);
  } finally {
    busy = false;
    updateControls();
  }
}

const loadRates = async () => applyReply(await request("/api/rates", { date: rateDate.value }));

function start() {
  run(async () => {
    const initial = await request("/api/bootstrap");
    serverToday = rateDate.value = initial.today;
    if (initial.saved) setOptions(initial.saved.currencies);
    show("cache-notice", initial.cacheWarning);
    await loadRates();
  });
}

form.addEventListener("submit", (event) => {
  event.preventDefault();
  if (convert.disabled) return;
  run(async () => applyReply(await request("/api/convert", {
    amount: amount.value,
    date: rateDate.value,
    fromCode: from.value,
    toCode: to.value,
    snapshotId: active?.id || "",
  })));
});

function resetResult() {
  showOutput();
  show("selection-notice", "");
  if (!problem.hidden && recovery.hidden) showProblem();
  updateControls();
}

for (const field of [amount, rateDate]) field.addEventListener("input", resetResult);
for (const select of [from, to]) select.addEventListener("change", resetResult);

refresh.addEventListener("click", () => run(loadRates));
retry.addEventListener("click", () => serverToday ? run(loadRates) : start());
today.addEventListener("click", () => {
  rateDate.value = serverToday;
  resetResult();
});
swap.addEventListener("click", () => {
  [from.value, to.value] = [to.value, from.value];
  resetResult();
});
useSaved.addEventListener("click", () => {
  if (!offered) return;
  rateDate.value = offered.requestedDate;
  activate(offered);
  showProblem();
  updateControls();
});

start();
