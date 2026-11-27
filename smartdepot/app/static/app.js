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
    tile('Kes terbuka', data.open),
    tile('Kritikal', data.by_label.Kritikal),
    tile('Tinggi', data.by_label.Tinggi),
    tile('Sederhana', data.by_label.Sederhana),
    tile('Rendah', data.by_label.Rendah),
    tile('Tertunggak', data.overdue),
    tile('Tamat hari ini', data.due_today),
    tile('Tamat ≤ 3 hari', data.due_soon),
    tile('Rekod tidak sah', data.invalid),
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
    row.append(cell('Tiada kes sepadan dengan tapisan semasa.', 'empty'));
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
  uc2Status.textContent = `Menyediakan eksport ${format.toUpperCase()}…`;
}
async function loadWorklist() {
  uc2Status.textContent = 'Memuat semula kes…';
  const params = filterParams();
  try {
    const [summaryResponse, casesResponse] = await Promise.all([
      fetch('/api/uc2/summary'),
      fetch('/api/uc2/cases?' + params.toString()),
    ]);
    if (summaryResponse.status === 503 || casesResponse.status === 503) {
      const detail = await (summaryResponse.status === 503 ? summaryResponse : casesResponse).json();
      summaryBox.replaceChildren();
      uc2Status.textContent = detail.detail || 'Tiada daftar reman dimuatkan.';
      return;
    }
    if (!summaryResponse.ok || !casesResponse.ok) throw new Error('Tidak dapat memuatkan senarai keutamaan.');
    const summary = await summaryResponse.json();
    const cases = await casesResponse.json();
    renderSummary(summary);
    renderCases(cases);
    caption.textContent = `${cases.shown} daripada ${cases.total} kes · daftar ${cases.file} · setakat ${cases.generated}`;
    uc2Status.textContent = 'Skor ialah peraturan nasihat; pegawai yang memutuskan.';
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
  if (!response.ok) throw new Error('Buka aplikasi melalui URL daftar masuknya.');
  const data = await response.json();
  document.querySelector('#connection').textContent = `${data.model} · ${data.tools_enabled ? 'Alat kes tersedia' : 'Sembang sahaja'} · ${data.identity}`;
}
info().catch(error => { status.textContent = error.message; });
form.addEventListener('submit', async event => {
  event.preventDefault();
  const text = prompt.value.trim();
  if (!text) return;
  send.disabled = reset.disabled = true;
  status.textContent = 'Sedang menyediakan jawapan. Ini boleh mengambil sehingga tiga minit.';
  message('Anda', text);
  try {
    const response = await fetch('/api/chat', {method: 'POST', headers: {'Content-Type': 'application/json'}, body: JSON.stringify({prompt: text, history: history.slice(-4)})});
    if (!(response.headers.get('content-type') || '').includes('application/json')) throw new Error('Sesi anda mungkin telah tamat. Muat semula halaman ini dan daftar masuk semula.');
    const data = await response.json();
    if (!response.ok) throw new Error(data.detail || 'Permintaan gagal.');
    message('Pembantu', data.answer);
    history.push({role: 'user', content: text.slice(0, 8000)}, {role: 'assistant', content: data.answer.slice(0, 8000)});
    lastAnswer = data.answer;
    download.disabled = false;
    prompt.value = '';
    status.textContent = data.tools.length ? `Alat digunakan: ${data.tools.map(tool => tool.name + (tool.ok ? '' : ' (gagal)')).join(', ')}` : 'Jawapan sedia.';
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
  const link = document.createElement('a'); link.href = url; link.download = 'ringkasan-smartdepot.md'; link.click();
  setTimeout(() => URL.revokeObjectURL(url), 1000);
});
loadWorklist();
