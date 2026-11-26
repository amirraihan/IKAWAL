"""UC-2 domain engine: automated reman countdown, risk scoring, recommended action.

Pure functions and one ``Case`` value object. No file, network, FastAPI or model
access, so the rules can be unit-tested directly. Weights and cut-offs follow
the SmartDepot design document (sections 5.2 and 5.3); they are advisory and are
meant to be agreed with the depot head and legal unit.
"""
from __future__ import annotations

import re
from dataclasses import dataclass, field
from datetime import date

# Normalised TINDAKAN codes. The register holds ~56 spellings of about 6 outcomes.
TINDAKAN_FINAL = frozenset({'USIR', 'USIR_BLI', 'USIR_RAI', 'BATAL_PAS', 'BEBAS_DENGAN_AMARAN'})
TINDAKAN_PENDING = frozenset({'BELUM_MUKTAMAD', 'TIDAK_JELAS'})

LABELS = ('Kritikal', 'Tinggi', 'Sederhana', 'Rendah')

_ACTIONS = {
    'Kritikal': 'Bertindak hari ini: rakam TINDAKAN (usir / bebas) atau mohon lanjutan reman; naikkan kepada ketua depot.',
    'Tinggi': 'Dalam 48 jam: siapkan draf lanjutan reman atau selesaikan langkah ujian DNA / rayuan.',
    'Sederhana': 'Minggu ini: betulkan jurang pentadbiran; sahkan urusan usir.',
    'Rendah': 'Pantau.',
}

_DATE = re.compile(r'(\d{1,2})[./-](\d{1,2})[./-](\d{4})')
_SECTION = re.compile(r'(\d+[A-Z]?(?:\(\s*[0-9A-Za-z]+\s*\))*)')
_GENDER = {'LELAKI', 'PEREMPUAN'}


def _to_date(parts) -> date | None:
    """Build a date from a (day, month, year) regex match group."""
    try:
        return date(int(parts[2]), int(parts[1]), int(parts[0]))
    except (ValueError, IndexError, TypeError):
        return None


def clean(value) -> str:
    """Trim a cell to a plain string; the register has leading spaces and NaN."""
    if value is None:
        return ''
    text = str(value).strip()
    return '' if text.lower() in {'nan', 'none'} else text


def parse_dates(text) -> tuple[date | None, date | None]:
    """Split ``TARIKH TAMAT REMAN`` when it holds ``DD.MM.YYYY-DD.MM.YYYY``."""
    found = _DATE.findall(clean(text))
    parsed = [_to_date(parts) for parts in found[:2]]
    start = parsed[0] if parsed else None
    end = parsed[1] if len(parsed) > 1 else (start if parsed else None)
    return start, end


def parse_reman_period(tamat_text, masuk_text: str = '') -> tuple[date | None, date | None, date | None]:
    """Resolve the reman period for both register shapes.

    v1/dummy file: one cell ``DD.MM.YYYY-DD.MM.YYYY``. BPK 2026 file: a single end
    date in ``TARIKH TAMAT REMAN`` with the start in ``TARIKH MASUK``.
    Returns (start, end, masuk).
    """
    found = _DATE.findall(clean(tamat_text))
    if len(found) >= 2:
        return _to_date(found[0]), _to_date(found[1]), None
    if len(found) == 1:
        end = _to_date(found[0])
        masuk_found = _DATE.findall(clean(masuk_text))
        masuk = _to_date(masuk_found[0]) if masuk_found else None
        return (masuk or end), end, masuk
    return None, None, None


def normalize_tindakan(raw: str) -> str:
    """Map a free-text TINDAKAN value to one normalised outcome code."""
    text = clean(raw).upper()
    tokens = re.sub(r'[^A-Z0-9]+', ' ', text)
    if 'BEBAS' in tokens:
        return 'BEBAS_DENGAN_AMARAN'
    if re.search(r'\b(USIR|USR|USI|RAI)\b', tokens):
        if 'BLI' in tokens:
            return 'USIR_BLI'
        if 'RAI' in tokens:
            return 'USIR_RAI'
        return 'USIR'
    if 'BATAL' in tokens:
        return 'BATAL_PAS'
    if 'DNA' in tokens or 'RAYUAN' in tokens:
        return 'BELUM_MUKTAMAD'
    if not text:
        return 'BELUM_MUKTAMAD'
    return 'TIDAK_JELAS'


def normalize_kesalahan(raw: str) -> tuple[str, str]:
    """Return (Act group, clean section) from the KESALAHAN free text."""
    text = clean(raw).upper()
    if 'IMMG' in text or 'IMIGRESEN' in text:
        act = 'Akta Imigresen 1959/63'
    elif 'ADB' in text:
        act = 'Akta Dadah Berbahaya 1952'
    elif 'KASTAM' in text:
        act = 'Akta Kastam 1967'
    elif 'KK' in text or 'KANUN' in text:
        act = 'Kanun Keseksaan'
    else:
        act = 'Lain-lain / tidak jelas'
    match = _SECTION.search(text)
    return act, (match.group(1).replace(' ', '') if match else '')


def age_band(age: int | None) -> str:
    if age is None:
        return '(tiada)'
    if age < 30:
        return '18-29'
    if age < 45:
        return '30-44'
    if age < 60:
        return '45-59'
    return '60+'


def mask_name(name: str) -> str:
    """Mask a detainee name for display and for the model (section 2.1, E10)."""
    parts = []
    for token in clean(name).split():
        parts.append(token[0].upper() + '*' * (len(token) - 1) if token else '')
    return ' '.join(part for part in parts if part) or '(tiada nama)'


def repeat_flag(catatan: str) -> bool:
    """Repeat cases are visible only as CATATAN keywords; never expose the text."""
    text = clean(catatan).upper()
    return 'TANGKAP SEMULA' in text or 'TAHAN SEMULA' in text


def status_reman(days_left: int | None, code: str, valid: bool) -> str:
    if not valid or days_left is None:
        return 'tidak sah'
    if code in TINDAKAN_FINAL:
        return 'selesai'
    if days_left < 0:
        return 'tertunggak'
    if days_left == 0:
        return 'tamat hari ini'
    if days_left <= 3:
        return 'tamat \u2264 3 hari'
    return 'aktif'


def label_for(score: int) -> str:
    if score >= 60:
        return 'Kritikal'
    if score >= 35:
        return 'Tinggi'
    if score >= 15:
        return 'Sederhana'
    return 'Rendah'


@dataclass
class Case:
    row: int
    no_reman: str
    nama: str
    jantina: str
    umur: int | None
    bangsa: str
    warganegara: str
    dokumen: str
    nama_pegawai: str
    fail: str
    depot: str
    tindakan_raw: str
    tindakan_kod: str
    kesalahan: str
    akta: str
    seksyen: str
    tarikh_mula: date | None
    tarikh_tamat: date | None
    tempoh_reman: int | None
    hari_berbaki: int | None
    status_reman: str
    kumpulan_umur: str
    ulangan: bool
    score: int
    label: str
    action: str
    reasons: list[str] = field(default_factory=list)
    issues: list[str] = field(default_factory=list)

    def to_public(self) -> dict:
        """Masked, model-safe representation (no CATATAN, no raw name)."""
        return {
            'no_reman': self.no_reman or '(kosong)',
            'nama': mask_name(self.nama),
            'jantina': self.jantina or '(kosong)',
            'umur': self.umur,
            'kumpulan_umur': self.kumpulan_umur,
            'bangsa': self.bangsa or '(kosong)',
            'warganegara': self.warganegara or '(kosong)',
            'depot': self.depot or '(kosong)',
            'nama_pegawai': self.nama_pegawai or '(kosong)',
            'fail': self.fail or '(kosong)',
            'tindakan': self.tindakan_kod,
            'tindakan_raw': self.tindakan_raw or '(kosong)',
            'akta': self.akta,
            'seksyen': self.seksyen,
            'kesalahan': self.kesalahan or '(kosong)',
            'tarikh_reman_mula': self.tarikh_mula.isoformat() if self.tarikh_mula else None,
            'tarikh_reman_tamat': self.tarikh_tamat.isoformat() if self.tarikh_tamat else None,
            'tempoh_reman': self.tempoh_reman,
            'hari_berbaki': self.hari_berbaki,
            'status_reman': self.status_reman,
            'ulangan': self.ulangan,
            'score': self.score,
            'label': self.label,
            'action': self.action,
            'reasons': list(self.reasons),
            'issues': list(self.issues),
        }


def score_case(days_left, tempoh, code, umur, repeat, no_reman, fail, capacity_pressure=False) -> tuple[int, list[str]]:
    """Apply the section 5.2 weights and return (score, reasons), capped at 100."""
    score = 0
    reasons: list[str] = []
    not_final = code not in TINDAKAN_FINAL
    if not_final and days_left is not None and days_left <= 0:
        score += 40
        reasons.append('Reman tamat/tertunggak dan TINDAKAN belum muktamad (+40)')
    elif not_final and days_left is not None and days_left <= 3:
        score += 25
        reasons.append('Reman tamat dalam 1-3 hari dan TINDAKAN belum muktamad (+25)')
    if code in TINDAKAN_PENDING:
        score += 15
        reasons.append('TINDAKAN belum muktamad / tidak jelas (+15)')
    if tempoh is not None and tempoh > 14:
        score += 10
        reasons.append('Tempoh reman melebihi 14 hari (+10)')
    if repeat:
        score += 10
        reasons.append('Kes ulangan (TANGKAP/TAHAN SEMULA) (+10)')
    if umur is not None and umur >= 60:
        score += 10
        reasons.append('Umur 60 tahun ke atas (+10)')
    if not clean(no_reman) or not clean(fail):
        score += 10
        reasons.append('Jurang pentadbiran: NO.REMAN atau FAIL kosong (+10)')
    if capacity_pressure:
        score += 5
        reasons.append('Depot melebihi 90% kapasiti (+5)')
    return min(score, 100), reasons


def build_case(row: dict, today: date, index: int = 0, capacity_pressure: bool = False) -> Case:
    """Turn one register row (already mapped to clean header keys) into a scored Case."""
    no_reman = clean(row.get('NO.REMAN'))
    fail = clean(row.get('FAIL'))
    depot = clean(row.get('DEPOT'))
    if depot.upper() in {'NIL', ''}:
        depot = ''
    jantina = clean(row.get('JANTINA')).upper()
    try:
        umur = int(float(clean(row.get('UMUR (THN)'))))
    except ValueError:
        umur = None
    tindakan_raw = clean(row.get('TINDAKAN'))
    code = normalize_tindakan(tindakan_raw)
    kesalahan = clean(row.get('KESALAHAN'))
    akta, seksyen = normalize_kesalahan(kesalahan)
    start, end, _masuk = parse_reman_period(row.get('TARIKH TAMAT REMAN'), row.get('TARIKH MASUK'))
    issues: list[str] = []
    valid = start is not None and end is not None
    if start and end and end < start:
        issues.append('tarikh_tamat_sebelum_mula')
        valid = False
    if not valid:
        issues.append('tarikh_tidak_sah')
    if not no_reman:
        issues.append('no_reman_kosong')
    if not fail:
        issues.append('fail_kosong')
    if not depot:
        issues.append('depot_kosong')
    if jantina and jantina not in _GENDER:
        issues.append('jantina_tidak_sah')
    if code == 'TIDAK_JELAS':
        issues.append('tindakan_tidak_jelas')
    tempoh = (end - start).days + 1 if valid else None
    days_left = (end - today).days if valid else None
    status = status_reman(days_left, code, valid)
    score, reasons = score_case(days_left, tempoh, code, umur, repeat_flag(row.get('CATATAN')), no_reman, fail, capacity_pressure)
    if not valid:
        score, reasons = 0, ['Rekod tidak sah: tarikh reman tidak boleh dibaca']
    label = label_for(score) if valid else 'tidak sah'
    return Case(
        row=index, no_reman=no_reman, nama=clean(row.get('NAMA')), jantina=jantina, umur=umur,
        bangsa=clean(row.get('BANGSA')), warganegara=clean(row.get('WARGANEGARA')), dokumen=clean(row.get('DOKUMEN')),
        nama_pegawai=clean(row.get('NAMA PEGAWAI')), fail=fail, depot=depot, tindakan_raw=tindakan_raw,
        tindakan_kod=code, kesalahan=kesalahan, akta=akta, seksyen=seksyen, tarikh_mula=start, tarikh_tamat=end,
        tempoh_reman=tempoh, hari_berbaki=days_left, status_reman=status, kumpulan_umur=age_band(umur),
        ulangan=repeat_flag(row.get('CATATAN')), score=score, label=label,
        action=_ACTIONS.get(label, 'Pantau.'), reasons=reasons, issues=issues,
    )


def summarize(cases: list[Case]) -> dict:
    """Counts for the worklist header and the chat summary tool."""
    by_label = {name: 0 for name in LABELS}
    by_depot: dict[str, int] = {}
    overdue = due_today = due_soon = invalid = 0
    for case in cases:
        by_label[case.label] = by_label.get(case.label, 0) + 1
        key = case.depot or '(kosong)'
        by_depot[key] = by_depot.get(key, 0) + 1
        if case.status_reman == 'tertunggak':
            overdue += 1
        elif case.status_reman == 'tamat hari ini':
            due_today += 1
        elif case.status_reman == 'tamat \u2264 3 hari':
            due_soon += 1
        if case.status_reman == 'tidak sah':
            invalid += 1
    return {
        'total': len(cases),
        'open': sum(1 for c in cases if c.status_reman not in {'selesai', 'tidak sah'}),
        'by_label': by_label,
        'by_depot': dict(sorted(by_depot.items())),
        'overdue': overdue,
        'due_today': due_today,
        'due_soon': due_soon,
        'invalid': invalid,
    }
