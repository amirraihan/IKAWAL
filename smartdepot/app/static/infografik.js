const note = document.querySelector('#live-note');
const source = document.querySelector('#meta-source');
const number = (value) => Number(value || 0).toLocaleString('ms-MY');

function setText(id, value) {
  const element = document.getElementById(id);
  if (element) element.textContent = value;
}

function setBar(key, count, max) {
  setText('cnt-' + key, number(count));
  const fill = document.getElementById('fill-' + key);
  if (fill) fill.style.width = (count <= 0 ? 0 : Math.max(2, (count / max) * 100)).toFixed(1) + '%';
}

async function loadInfographic() {
  if (note) note.textContent = 'Memuatkan angka…';
  try {
    const response = await fetch('/api/uc2/summary');
    if (response.status === 503) {
      const detail = await response.json();
      if (note) note.textContent = detail.detail || 'Tiada daftar reman dimuatkan.';
      return;
    }
    if (!response.ok) throw new Error('Tidak dapat memuatkan angka.');
    const data = await response.json();
    setText('kpi-total', number(data.total));
    setText('kpi-open', number(data.open));
    setText('kpi-overdue', number(data.overdue));
    setText('kpi-invalid', number(data.invalid));
    const labels = data.by_label || {};
    const counts = {
      kritikal: labels.Kritikal || 0,
      tinggi: labels.Tinggi || 0,
      sederhana: labels.Sederhana || 0,
      rendah: labels.Rendah || 0,
      tidaksah: data.invalid || 0,
    };
    const max = Math.max(...Object.values(counts), 1);
    for (const [key, count] of Object.entries(counts)) setBar(key, count, max);
    if (source) source.textContent = `Sumber: ${data.file} · setakat ${data.generated} · ${number(data.total)} kes diproses.`;
    if (note) note.textContent = 'Angka langsung daripada daftar; skor bersifat nasihat, pegawai yang memutuskan.';
  } catch (error) {
    if (note) note.textContent = error.message;
  }
}

const refresh = document.querySelector('#infografik-refresh');
if (refresh) refresh.addEventListener('click', loadInfographic);
loadInfographic();
