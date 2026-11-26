const form = document.querySelector('#chat');
const prompt = document.querySelector('#prompt');
const conversation = document.querySelector('#conversation');
const status = document.querySelector('#status');
const send = document.querySelector('#send');
const download = document.querySelector('#download');
const reset = document.querySelector('#reset');
const summaryBox = document.querySelector('#uc2-summary');
const tableBody = document.querySelector('#uc2-table tbody');
const caption = document.querySelector('#uc2-caption');
const uc2Status = document.querySelector('#uc2-status');
const labelFilter = document.querySelector('#uc2-label');
const depotFilter = document.querySelector('#uc2-depot');
const openFilter = document.querySelector('#uc2-open');
let history = [];
let lastAnswer = '';

// --- UC-2 priority worklist -------------------------------------------------
function cell(text, className) {
  const td = document.createElement('td');
  td.textContent = text === null || text === undefined ? '' : String(text);
  if (className) td.className = className;
  return td;
}
function tile(label, value) {
  const box = document.createElement('div');
  box.className = 'tile';
  const key = document.createElement('b');
  key.textContent = label;
  const val = document.createElement('span');
  val.textContent = String(value);
  box.append(key, val);
  return box;
}
function renderSummary(data) {
  summaryBox.replaceChildren(
    tile('Open cases', data.open),
    tile('Kritikal', data.by_label.Kritikal),
    tile('Tinggi', data.by_label.Tinggi),
    tile('Sederhana', data.by_label.Sederhana),
    tile('Rendah', data.by_label.Rendah),
    tile('Overdue', data.overdue),
    tile('Due today', data.due_today),
    tile('Due ≤ 3 days', data.due_soon),
    tile('Invalid records', data.invalid),
  );
  if (depotFilter.options.length <= 1) {
    for (const [depot, count] of Object.entries(data.by_depot)) {
      const option = document.createElement('option');
      option.value = depot;
      option.textContent = `${depot} (${count})`;
      depotFilter.append(option);
    }
  }
}
function renderCases(data) {
  tableBody.replaceChildren();
  if (!data.cases.length) {
    const row = document.createElement('tr');
    row.append(cell('No cases match the current filters.', 'empty'));
    row.lastChild.colSpan = 9;
    tableBody.append(row);
    return;
  }
  for (const item of data.cases) {
    const row = document.createElement('tr');
    row.append(
      cell(item.no_reman),
      cell(item.nama),
      cell(item.depot),
      cell(item.nama_pegawai),
      cell(item.hari_berbaki),
      cell(item.status_reman),
      cell(item.label, 'badge ' + String(item.label).toLowerCase()),
      cell(item.score),
      cell(item.action),
    );
    row.title = (item.reasons || []).join('; ');
    tableBody.append(row);
  }
}
function filterParams() {
  const params = new URLSearchParams();
  if (labelFilter.value) params.set('label', labelFilter.value);
  if (depotFilter.value) params.set('depot', depotFilter.value);
  if (openFilter.checked) params.set('open', '1');
  return params;
}
function exportWorklist(format) {
  const link = document.createElement('a');
  link.href = `/api/uc2/export.${format}?` + filterParams().toString();
  link.download = '';
  document.body.append(link);
  link.click();
  link.remove();
  uc2Status.textContent = `Preparing the ${format.toUpperCase()} export…`;
}
async function loadWorklist() {
  uc2Status.textContent = 'Refreshing cases…';
  const params = filterParams();
  try {
    const [summaryResponse, casesResponse] = await Promise.all([
      fetch('/api/uc2/summary'),
      fetch('/api/uc2/cases?' + params.toString()),
    ]);
    if (summaryResponse.status === 503 || casesResponse.status === 503) {
      const detail = await (summaryResponse.status === 503 ? summaryResponse : casesResponse).json();
      summaryBox.replaceChildren();
      uc2Status.textContent = detail.detail || 'No reman register is loaded.';
      return;
    }
    if (!summaryResponse.ok || !casesResponse.ok) throw new Error('Could not load the worklist.');
    const summary = await summaryResponse.json();
    const cases = await casesResponse.json();
    renderSummary(summary);
    renderCases(cases);
    caption.textContent = `${cases.shown} of ${cases.total} cases · register ${cases.file} · as at ${cases.generated}`;
    uc2Status.textContent = 'Scores are advisory rules; officers decide.';
  } catch (error) {
    uc2Status.textContent = error.message;
  }
}
document.querySelector('#uc2-filters').addEventListener('submit', event => event.preventDefault());
document.querySelector('#uc2-refresh').addEventListener('click', loadWorklist);
labelFilter.addEventListener('change', loadWorklist);
depotFilter.addEventListener('change', loadWorklist);
openFilter.addEventListener('change', loadWorklist);
document.querySelector('#uc2-export-xlsx').addEventListener('click', () => exportWorklist('xlsx'));
document.querySelector('#uc2-export-pdf').addEventListener('click', () => exportWorklist('pdf'));

// --- Assistant chat ---------------------------------------------------------
function message(role, text) {
  const article = document.createElement('article');
  const label = document.createElement('h2');
  label.textContent = role;
  const body = document.createElement('p');
  body.textContent = text;
  article.append(label, body);
  conversation.append(article);
  article.scrollIntoView({block: 'nearest', behavior: 'smooth'});
}
async function info() {
  const response = await fetch('/api/info');
  if (!response.ok) throw new Error('Open the app through its sign-in URL.');
  const data = await response.json();
  document.querySelector('#connection').textContent = `${data.model} · ${data.tools_enabled ? 'Case tools available' : 'Chat only'} · ${data.identity}`;
}
info().catch(error => { status.textContent = error.message; });
form.addEventListener('submit', async event => {
  event.preventDefault();
  const text = prompt.value.trim();
  if (!text) return;
  send.disabled = reset.disabled = true;
  status.textContent = 'Working on your answer. This can take up to three minutes.';
  message('You', text);
  try {
    const response = await fetch('/api/chat', {method: 'POST', headers: {'Content-Type': 'application/json'}, body: JSON.stringify({prompt: text, history: history.slice(-4)})});
    if (!(response.headers.get('content-type') || '').includes('application/json')) throw new Error('Your session may have expired. Reload this page and sign in again.');
    const data = await response.json();
    if (!response.ok) throw new Error(data.detail || 'The request failed.');
    message('Assistant', data.answer);
    history.push({role: 'user', content: text.slice(0, 8000)}, {role: 'assistant', content: data.answer.slice(0, 8000)});
    lastAnswer = data.answer;
    download.disabled = false;
    prompt.value = '';
    status.textContent = data.tools.length ? `Tools used: ${data.tools.map(tool => tool.name + (tool.ok ? '' : ' (failed)')).join(', ')}` : 'Answer ready.';
  } catch (error) {
    status.textContent = error.message;
  } finally {
    send.disabled = reset.disabled = false;
  }
});
reset.addEventListener('click', () => {
  history = []; lastAnswer = ''; conversation.replaceChildren();
  status.textContent = ''; download.disabled = true; prompt.focus();
});
download.addEventListener('click', () => {
  const url = URL.createObjectURL(new Blob([lastAnswer], {type: 'text/markdown;charset=utf-8'}));
  const link = document.createElement('a'); link.href = url; link.download = 'smartdepot-briefing.md'; link.click();
  setTimeout(() => URL.revokeObjectURL(url), 1000);
});
loadWorklist();
