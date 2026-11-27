import json
import zipfile
from datetime import date, timedelta
from pathlib import Path

from fastapi.testclient import TestClient

from app import store, xlsx
from app import pdf
from app.agent import execute_tool
from app.main import Settings, create_app
from app.reman import (
    build_case,
    label_for,
    mask_name,
    normalize_tindakan,
    parse_dates,
    parse_reman_period,
    repeat_flag,
    score_case,
    summarize,
)

TODAY = date(2026, 6, 15)


def write_xlsx(path: Path, header: list[str], rows: list[list]) -> Path:
    """Write a minimal inline-string .xlsx that app/xlsx.py can read."""

    def cell(reference, value):
        if value is None or value == '':
            return ''
        if isinstance(value, (int, float)):
            return f'<c r="{reference}"><v>{value}</v></c>'
        return f'<c r="{reference}" t="inlineStr"><is><t>{value}</t></is></c>'

    def row_xml(index, values):
        letters = 'ABCDEFGHIJKLMNOPQRSTUVWXYZ'
        cells = ''.join(cell(f'{letters[position]}{index}', value) for position, value in enumerate(values))
        return f'<row r="{index}">{cells}</row>'

    body = row_xml(1, header) + ''.join(row_xml(index, row) for index, row in enumerate(rows, start=2))
    sheet = f'<?xml version="1.0"?><worksheet xmlns="http://schemas.openxmlformats.org/spreadsheetml/2006/main"><sheetData>{body}</sheetData></worksheet>'
    with zipfile.ZipFile(path, 'w') as archive:
        archive.writestr('xl/worksheets/sheet1.xml', sheet)
    return path


HEADER = ['TARIKH TAMAT REMAN', 'NAMA', 'JANTINA', 'UMUR (THN)', 'BANGSA', 'WARGANEGARA', 'NO.REMAN',
          'DOKUMEN', 'NAMA PEGAWAI', 'FAIL', 'DEPOT', 'CATATAN', 'TINDAKAN', 'KESALAHAN']


def register_rows():
    return [
        ['01.06.2026-14.06.2026', 'MARIA SANTOS', 'PEREMPUAN', 38, 'TAGALOG', 'FILIPINA', '26(01)BD', 'NIL', 'PI YUSUF', '(06)2026', 'DIP', '', 'RAYUAN', '6(1)(C) IMMG'],
        ['15.06.2026-28.06.2026', 'AHMAD ALI', 'LELAKI', 61, 'BAJAU', 'FILIPINA', '26(02)BD', 'NIL', 'PI LIM', '(06)2026', 'DIKK', 'TANGKAP SEMULA', 'UJIAN DNA', 'SEK 15(1)(a) ADB 1952'],
        ['15.06.2026-01.07.2026', 'SITI BINTI', 'PEREMPUAN', 25, 'BUGIS', 'INDONESIA', '26(03)BD', 'NIL', 'PI YUSUF', '(06)2026', 'DIP', '', 'USIR', 'SEK 5(2) IMMG'],
        ['14.06.2026-28.06.2026', 'RAJESH KUMAR', 'LELAKI', 30, 'SULUK', 'FILIPINA', '', 'NIL', 'PI LIM', '', 'DIKK', '', 'BEBAS DENGAN AMARAN', 'SEK 411 KK'],
    ]


def load_sample(tmp_path):
    path = write_xlsx(tmp_path / 'reman.xlsx', HEADER, register_rows())
    return store.load_cases(path, TODAY)


def settings(**kwargs):
    kwargs.setdefault('api_key', 'test-only-dummy-credential')
    return Settings(**kwargs)


# --------------------------------------------------------------------------- parsing
def test_parse_dates_handles_register_formats():
    start, end = parse_dates('02.01.2026-15.01.2026')
    assert (start, end) == (date(2026, 1, 2), date(2026, 1, 15))
    assert parse_dates('27.04.2026-10.05.2026\\')[1] == date(2026, 5, 10)
    assert parse_dates('') == (None, None)
    assert parse_dates('nan') == (None, None)


def test_parse_reman_period_supports_both_register_shapes():
    # BPK 2026 sheet: single end date plus TARIKH MASUK
    assert parse_reman_period('15.01.2026', '02.01.2026') == (date(2026, 1, 2), date(2026, 1, 15), date(2026, 1, 2))
    # dummy sheet: start-end in one cell
    assert parse_reman_period('02.01.2026-15.01.2026', '') == (date(2026, 1, 2), date(2026, 1, 15), None)


def test_build_case_uses_tarikh_masuk_for_single_end_date():
    row = {'TARIKH MASUK': '01.06.2026', 'TARIKH TAMAT REMAN': '14.06.2026', 'NAMA': 'X', 'JANTINA': 'LELAKI',
           'UMUR (THN)': '40', 'NO.REMAN': '26(9)BD', 'FAIL': '(6)2026', 'DEPOT': 'DIKK', 'TINDAKAN': 'USIR'}
    case = build_case(row, TODAY, index=2)
    assert case.tarikh_mula == date(2026, 6, 1)
    assert case.tarikh_tamat == date(2026, 6, 14)
    assert case.tempoh_reman == 14


def test_tindakan_normalisation_covers_real_spellings():
    assert normalize_tindakan('USIR') == 'USIR'
    assert normalize_tindakan('USIR/BLI') == 'USIR_BLI'
    assert normalize_tindakan('USIR / RAI') == 'USIR_RAI'
    assert normalize_tindakan('BEBAS AMARAN') == 'BEBAS_DENGAN_AMARAN'
    assert normalize_tindakan('RAYUAN-BEBAS DGN AMARAN') == 'BEBAS_DENGAN_AMARAN'
    assert normalize_tindakan('USIR/BATAL PAS') == 'USIR'
    assert normalize_tindakan('ujian DNA') == 'BELUM_MUKTAMAD'
    assert normalize_tindakan('') == 'BELUM_MUKTAMAD'
    assert normalize_tindakan('CHEN') == 'TIDAK_JELAS'


def test_mask_name_and_repeat_flag_never_leak_source():
    assert mask_name('MARIA SANTOS') == 'M**** S*****'
    assert mask_name('') == '(tiada nama)'
    assert repeat_flag('kes TANGKAP SEMULA 2026') is True
    assert repeat_flag('rayuan') is False


# --------------------------------------------------------------------------- scoring
def test_score_matches_document_weights_and_caps_at_100():
    score, reasons = score_case(days_left=-1, tempoh=14, code='BELUM_MUKTAMAD', umur=30, repeat=False, no_reman='26(1)BD', fail='(1)2026')
    assert score == 55 and len(reasons) == 2  # +40 overdue +15 pending
    score, _ = score_case(days_left=-1, tempoh=20, code='BELUM_MUKTAMAD', umur=65, repeat=True, no_reman='', fail='', capacity_pressure=True)
    assert score == 100  # 40 + 15 + 10 + 10 + 10 + 10 + 5 capped
    score, reasons = score_case(days_left=-5, tempoh=14, code='USIR', umur=30, repeat=False, no_reman='1', fail='2')
    assert score == 0 and reasons == []  # a final outcome needs no countdown risk


def test_label_thresholds_and_actions():
    assert label_for(60) == 'Kritikal'
    assert label_for(35) == 'Tinggi'
    assert label_for(15) == 'Sederhana'
    assert label_for(14) == 'Rendah'


def test_build_case_marks_invalid_dates():
    row = dict(zip(HEADER, ['20.06.2026-10.06.2026', 'X', 'LELAKI', 40, 'B', 'FILIPINA', '26(9)BD', 'NIL', 'PI', 'F', 'DIKK', '', 'USIR', 'KK']))
    case = build_case(row, TODAY, index=2)
    assert case.status_reman == 'tidak sah'
    assert 'tarikh_tamat_sebelum_mula' in case.issues


def test_summarize_counts_labels_and_due_states(tmp_path):
    summary = summarize(load_sample(tmp_path))
    assert summary['total'] == 4
    assert summary['overdue'] == 1  # the RAYUAN case ended before TODAY
    assert summary['by_depot'] == {'DIKK': 2, 'DIP': 2}
    assert sum(summary['by_label'].values()) == 4


# --------------------------------------------------------------------------- store + reader
def test_store_maps_headers_and_scores_rows(tmp_path):
    cases = load_sample(tmp_path)
    first = next(c for c in cases if c.no_reman == '26(01)BD')
    assert first.depot == 'DIP'
    assert first.tindakan_kod == 'BELUM_MUKTAMAD'
    assert first.hari_berbaki == -1
    assert first.status_reman == 'tertunggak'
    assert first.score == 40 + 15  # overdue + pending, no other factor
    masked = first.to_public()
    assert masked['nama'] == 'M**** S*****'
    assert 'catatan' not in masked and 'CATATAN' not in masked


def test_xlsx_reader_handles_sparse_rows_and_leading_space(tmp_path):
    path = write_xlsx(tmp_path / 's.xlsx', ['A', 'B', 'C'], [['x', None, 'z']])
    rows = xlsx.read_rows(path)
    assert rows[0] == ['A', 'B', 'C']
    assert rows[1] == ['x', '', 'z']


def test_resolve_reman_file_prefers_configured_path(tmp_path):
    missing = tmp_path / 'nope.xlsx'
    assert store.resolve_reman_file(tmp_path, str(missing)) is None
    real = write_xlsx(tmp_path / 'data-ish.xlsx', HEADER, register_rows())
    assert store.resolve_reman_file(tmp_path, str(real)) == real


# --------------------------------------------------------------------------- HTTP boundary
def client_for(path):
    return TestClient(create_app(settings(reman_file=str(path))))


def test_uc2_endpoints_return_worklist_and_summary(tmp_path):
    path = write_xlsx(tmp_path / 'reman.xlsx', HEADER, register_rows())
    with client_for(path) as client:
        summary = client.get('/api/uc2/summary')
        assert summary.status_code == 200
        assert summary.json()['overdue'] >= 1
        listing = client.get('/api/uc2/cases?open=1')
        assert listing.status_code == 200
        body = listing.json()
        assert body['total'] >= 1 and body['cases'][0]['score'] >= body['cases'][-1]['score']
        # CATATAN and raw names never cross the boundary
        assert 'TANGKAP SEMULA' not in listing.text
        assert 'AHMAD ALI' not in listing.text
        detail = client.get('/api/uc2/case/26(02)BD')
        assert detail.status_code == 200 and detail.json()['case']['nama'] == 'A**** A**'


def test_uc2_endpoints_validate_and_report_missing_register(tmp_path):
    path = write_xlsx(tmp_path / 'reman.xlsx', HEADER, register_rows())
    with client_for(path) as client:
        assert client.get('/api/uc2/cases?limit=nope').status_code == 422
        assert client.get('/api/uc2/case/UNKNOWN').status_code == 404
    with client_for(tmp_path / 'absent.xlsx') as client:
        assert client.get('/api/uc2/summary').status_code == 503
        assert client.get('/api/uc2/cases').status_code == 503


def test_static_ui_exposes_worklist_without_inline_script(tmp_path):
    path = write_xlsx(tmp_path / 'reman.xlsx', HEADER, register_rows())
    with client_for(path) as client:
        page = client.get('/').text
        assert 'Senarai Keutamaan' in page
        assert '<script>' not in page
        assert client.get('/app.js').status_code == 200


# --------------------------------------------------------------------------- agent tools
def test_uc2_agent_tools_are_read_only_and_masked(tmp_path):
    cases = load_sample(tmp_path)
    summary = execute_tool('reman_summary', '{}', cases)
    assert summary['total'] == 4
    listed = execute_tool('list_priority_cases', json.dumps({'label': 'Kritikal'}), cases)
    assert all(case['label'] == 'Kritikal' for case in listed['cases'])
    assert execute_tool('list_priority_cases', json.dumps({'limit': 99}), cases)['error']
    filtered = execute_tool('list_priority_cases', json.dumps({'depot': 'DIP'}), cases)
    assert all(case['depot'] == 'DIP' for case in filtered['cases'])
    one = execute_tool('get_case', json.dumps({'no_reman': '26(01)BD'}), cases)
    assert 'catatan' not in one and one['nama'] == 'M**** S*****'
    assert execute_tool('get_case', json.dumps({'no_reman': 'zzz'}), cases)['error']
    assert execute_tool('reman_summary', '{}', [])['error']


def test_priority_tool_without_register_is_unavailable():
    assert 'error' in execute_tool('list_priority_cases', '{}')


def test_infografik_page_is_served_and_csp_safe(tmp_path):
    path = write_xlsx(tmp_path / 'reman.xlsx', HEADER, register_rows())
    with client_for(path) as client:
        page = client.get('/infografik')
        assert page.status_code == 200
        assert 'Sokongan Keputusan Kes' in page.text
        # CSP keeps style-src/script-src 'self': no inline style or script
        assert '<style' not in page.text
        assert '<script>' not in page.text
        assert '/infografik.css' in page.text and '/infografik.js' in page.text
        css = client.get('/infografik.css')
        assert css.status_code == 200 and 'text/css' in css.headers['content-type']
        js = client.get('/infografik.js')
        assert js.status_code == 200 and 'javascript' in js.headers['content-type']
        assert '/infografik' in client.get('/').text


# --------------------------------------------------------------------------- exports
def test_xlsx_writer_round_trips(tmp_path):
    body = xlsx.dumps([['NO.REMAN', 'Skor'], ['26(1)BD', 55], ['26(2)BD', 15]])
    path = tmp_path / 'out.xlsx'
    path.write_bytes(body)
    rows = xlsx.read_rows(path)
    assert rows[0] == ['NO.REMAN', 'Skor']
    assert rows[1] == ['26(1)BD', '55']
    assert rows[2] == ['26(2)BD', '15']


def test_table_pdf_has_valid_scaffolding():
    body = pdf.table_pdf('Title', 'subtitle', ['A', 'B'], [['1', '2'], ['3', '4']], [1, 2])
    assert body.startswith(b'%PDF-1.4')
    assert body.rstrip().endswith(b'%%EOF')
    assert b'/Type /Page' in body and b'/Count 1' in body
    assert b'startxref' in body


def test_table_pdf_paginates_and_transliterates():
    rows = [[f'CASE-{i}', 'tamat \u2264 3 hari'] for i in range(120)]
    body = pdf.table_pdf('T', 's', ['A', 'B'], rows, [1, 1])
    assert body.count(b'/Type /Page') >= 2  # 120 rows cannot fit on one page
    assert b'<= 3 hari' in body and b'\xe2\x89\xa4' not in body


def test_uc2_export_endpoints(tmp_path):
    path = write_xlsx(tmp_path / 'reman.xlsx', HEADER, register_rows())
    with client_for(path) as client:
        book = client.get('/api/uc2/export.xlsx?open=1')
        assert book.status_code == 200
        assert 'spreadsheet' in book.headers['content-type']
        assert 'attachment' in book.headers['content-disposition']
        saved = tmp_path / 'download.xlsx'
        saved.write_bytes(book.content)
        rows = xlsx.read_rows(saved)
        assert rows[0][:3] == ['NO.REMAN', 'Nama', 'Jantina']
        assert any(row and row[0] == '26(01)BD' for row in rows)

        doc = client.get('/api/uc2/export.pdf?open=1')
        assert doc.status_code == 200
        assert doc.headers['content-type'] == 'application/pdf'
        assert doc.content.startswith(b'%PDF')

        sheet = client.get('/api/uc2/export.csv?open=1')
        assert sheet.status_code == 200
        assert 'text/csv' in sheet.headers['content-type']
        lines = sheet.text.splitlines()
        assert lines[0].startswith('NO.REMAN')
        # masked names, and CATATAN never leaves the server
        assert 'AHMAD ALI' not in sheet.text and 'TANGKAP SEMULA' not in sheet.text
        assert 'A**** A**' in sheet.text
