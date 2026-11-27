"""LLM insight narrative (E9).

The narrative is generated **only** from the computed KPI table — no names, no
CATATAN, no raw rows. A deterministic template is the default; an optional LLM
hook can be enabled with SMARTDEPOT_LLM=1 and is fed strictly the KPI numbers.
"""

from __future__ import annotations

from typing import Any

from ..config import get_settings


def build_narrative(snapshot: dict[str, Any]) -> str:
    """Produce the report narrative from a KPI snapshot dict."""
    if get_settings().enable_llm:
        try:
            return _llm_narrative(snapshot)
        except Exception:
            pass  # fall back to the deterministic template
    return _template_narrative(snapshot)


def _pct_change(cur: float, chg: float) -> str:
    if cur == 0:
        return "tiada perubahan"
    pct = round(100 * chg / cur, 1)
    if chg > 0:
        return f"naik {abs(pct)}%"
    if chg < 0:
        return f"turun {abs(pct)}%"
    return "tidak berubah"


def _template_narrative(snapshot: dict[str, Any]) -> str:
    period = snapshot["period"]
    ov = snapshot["overview"]
    chg = snapshot["change"]
    bd = snapshot["breakdowns"]

    def top(table: str, n: int = 3) -> str:
        df = bd.get(table)
        if df is None or df.empty:
            return "-"
        head = df.head(n)
        col = head.columns[0]
        return ", ".join(f"{r[col]} ({int(r['bilangan'])})" for _, r in head.iterrows())

    lines = [
        f"LAPORAN BULANAN SMARTDEPOT — {period}",
        "",
        f"Pada bulan {period}, sejumlah {ov['jumlah_reman']} rekod reman baharu "
        f"didaftarkan ({_pct_change(ov['jumlah_reman'], chg['jumlah_reman'])} berbanding bulan sebelumnya).",
        "",
        "Kedudukan semasa:",
        f"- Reman aktif: {ov['reman_aktif']} kes",
        f"- Tamat dalam 3 hari: {ov['tamat_3_hari']} kes",
        f"- Tertunggak (melepasi tarikh tamat): {ov['tertunggak']} kes",
        f"- Belum muktamad (TINDAKAN belum ditetapkan): {ov['kes_belum_muktamad']} kes",
        "",
        f"Pecahan nasionaliti teratas: {top('warganegara')}.",
        f"Kesalahan (kumpulan akta) teratas: {top('akta')}.",
        f"Tindakan teratas: {top('tindakan')}.",
        f"Depot: {top('depot')}.",
        "",
        f"Kadar usir: {ov['pct_usir']}%; bebas dengan amaran: {ov['pct_bebas']}%.",
        "",
        "Nota: Semua angka dijana terus daripada jadual reman yang telah dibersihkan. "
        "Nama dan catatan peribadi tidak digunakan dalam laporan ini.",
    ]
    return "\n".join(lines)


def _llm_narrative(snapshot: dict[str, Any]) -> str:  # pragma: no cover - needs LLM
    """Pluggable LLM hook. Only the KPI numbers are passed — never raw PII."""
    import json

    from ..config import get_settings as _get

    payload = {
        "period": snapshot["period"],
        "overview": snapshot["overview"],
        "change": snapshot["change"],
        "breakdowns": {
            k: df.head(10).to_dict("records") for k, df in snapshot["breakdowns"].items()
        },
    }
    # Replace this stub with a real client (e.g. Amazon Bedrock) in production.
    raise NotImplementedError(
        "LLM narrative not configured; enable and implement _llm_narrative(). "
        f"Payload was: {json.dumps(payload)[:200]}..."
    )
