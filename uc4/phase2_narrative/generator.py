"""Phase 2: AI Narrative Generator (LLM + deterministic fallback) & Numeric Guard."""

from __future__ import annotations

import datetime as dt
import json
import os
import re
import urllib.error
import urllib.request
from typing import Any

from uc4.contracts import SCHEMA_VERSION, assert_kpi_payload_safe

# Statutory/domain reference numbers naturally cited in Malay operational prose.
DOMAIN_REFERENCE_NUMBERS = frozenset({
    "1", "2", "3", "4", "14", "1952", "1959", "63", "1967", "59", "60",
})


def _collect_allowed_numbers(obj: Any, sink: set[str]) -> None:
    """Recursively collect all numeric representations present in a KPI payload."""
    if isinstance(obj, bool):
        return
    if isinstance(obj, int):
        sink.add(str(obj))
        sink.add(str(abs(obj)))
        sink.add(f"{obj}.0")
        sink.add(f"{abs(obj)}.0")
    elif isinstance(obj, float):
        sink.add(str(obj))
        sink.add(str(abs(obj)))
        sink.add(f"{obj:.1f}")
        sink.add(f"{abs(obj):.1f}")
        if obj.is_integer():
            sink.add(str(int(abs(obj))))
    elif isinstance(obj, str):
        for tok in re.findall(r"\d+(?:\.\d+)?", obj):
            sink.add(tok)
    elif isinstance(obj, dict):
        for v in obj.values():
            _collect_allowed_numbers(v, sink)
    elif isinstance(obj, list):
        for item in obj:
            _collect_allowed_numbers(item, sink)


def trace_narrative_numbers(narrative_text: str, kpi_payload: dict[str, Any]) -> dict[str, Any]:
    """Verify every numeric figure in the narrative traces back to the KPI payload."""
    allowed: set[str] = set(DOMAIN_REFERENCE_NUMBERS)
    _collect_allowed_numbers(kpi_payload, allowed)

    # Extract standalone numbers (numbers not embedded inside statute codes like 6(1)(c) or 15(1)(a)).
    cleaned = re.sub(r"\b\d+\([^)]+\)(?:\([^)]+\))?", " ", narrative_text)
    found = re.findall(r"(?<![A-Za-z0-9_])\d+(?:,\d{3})*(?:\.\d+)?(?![A-Za-z0-9_])", cleaned)

    untraced: list[str] = []
    for raw in found:
        norm = raw.replace(",", "")
        if norm not in allowed and norm.rstrip("0").rstrip(".") not in allowed:
            if norm not in untraced:
                untraced.append(raw)

    return {
        "passed": len(untraced) == 0,
        "checked_count": len(found),
        "untraced_numbers": untraced,
    }


def _compact_kpi_for_prompt(kpi_payload: dict[str, Any]) -> dict[str, Any]:
    """Build a concise, strictly PII-free summary table for LLM prompting."""
    assert_kpi_payload_safe(kpi_payload)
    k = kpi_payload["kpis"]
    return {
        "month": kpi_payload["month"],
        "month_label": kpi_payload["month_label"],
        "kpis": {
            "total_reman": k["total_reman"],
            "aktif": k["aktif"],
            "bebas": k["bebas"],
            "urgent_atau_tertunggak": k["urgent_atau_tertunggak"],
            "tempoh_lebih_14_hari": k["tempoh_lebih_14_hari"],
            "depot": k["depot"],
            "warganegara_top5": k["warganegara"][:5],
            "akta": k["akta"],
            "top_seksyen_top3": k["top_seksyen"][:3],
            "tindakan": k["tindakan"],
            "pegawai_ringkasan": {
                "jumlah_pegawai_aktif": k["pegawai"]["jumlah_pegawai_aktif"],
                "purata_kes_per_pegawai": k["pegawai"]["purata_kes_per_pegawai"],
                "beban_tertinggi": k["pegawai"]["beban_tertinggi"],
            },
            "kualiti_data": k["kualiti_data"],
        },
        "mom": kpi_payload["mom"],
        "uc2_summary": kpi_payload["uc2_summary"],
        "uc3_forecast": kpi_payload["uc3_forecast"],
        "insights": kpi_payload["insights"],
    }


def _call_llm(compact_kpi: dict[str, Any]) -> tuple[str, str]:
    """Call OpenAI-compatible or local Ollama endpoint if configured. Returns (text, model_name)."""
    prompt = (
        "Anda ialah penganalisis operasi BPK (SmartDepot IKAWAL). Tulis laporan eksekutif bulanan "
        "dalam Bahasa Melayu rasmi (3 hingga 4 perenggan ringkas) berdasarkan DATA KPI JSON berikut sahaja.\n"
        "PERATURAN KETAT:\n"
        "1. Gunakan HANYA angka yang wujud dalam JSON di bawah. Jangan reka atau anggar nombor baharu.\n"
        "2. Jangan sebut sebarang nama tahanan atau nombor kad pengenalan.\n"
        "3. Sentuh: (a) jumlah reman & perubahan MoM, (b) depot/warganegara/kesalahan utama, "
        "(c) kes mendesak/tertunggak & beban pegawai, dan (d) kualiti data serta syor tindakan.\n\n"
        f"DATA KPI:\n{json.dumps(compact_kpi, ensure_ascii=False)}"
    )

    ollama_url = os.environ.get("IKAWAL_OLLAMA_URL", "").strip()
    api_key = os.environ.get("IKAWAL_LLM_API_KEY", "").strip()

    if ollama_url:
        model = os.environ.get("IKAWAL_LLM_MODEL", "llama3.1")
        req_body = json.dumps({
            "model": model,
            "messages": [{"role": "user", "content": prompt}],
            "stream": False,
        }).encode("utf-8")
        req = urllib.request.Request(
            ollama_url.rstrip("/") + "/api/chat",
            data=req_body,
            headers={"Content-Type": "application/json"},
            method="POST",
        )
        with urllib.request.urlopen(req, timeout=20) as resp:
            data = json.loads(resp.read().decode("utf-8"))
        text = ((data.get("message") or {}).get("content") or "").strip()
        if not text:
            raise RuntimeError("Empty response from Ollama")
        return text, f"ollama:{model}"

    if api_key:
        base_url = os.environ.get("IKAWAL_LLM_BASE_URL", "https://api.openai.com/v1").rstrip("/")
        model = os.environ.get("IKAWAL_LLM_MODEL", "gpt-4o-mini")
        req_body = json.dumps({
            "model": model,
            "temperature": 0.2,
            "messages": [
                {"role": "system", "content": "Penganalisis data rasmi BPK. Guna angka tepat daripada JSON sahaja."},
                {"role": "user", "content": prompt},
            ],
        }).encode("utf-8")
        req = urllib.request.Request(
            f"{base_url}/chat/completions",
            data=req_body,
            headers={
                "Content-Type": "application/json",
                "Authorization": f"Bearer {api_key}",
            },
            method="POST",
        )
        with urllib.request.urlopen(req, timeout=25) as resp:
            data = json.loads(resp.read().decode("utf-8"))
        text = (data["choices"][0]["message"]["content"] or "").strip()
        if not text:
            raise RuntimeError("Empty response from LLM API")
        return text, f"llm:{model}"

    raise RuntimeError("Tiada konfigurasi LLM (IKAWAL_LLM_API_KEY / IKAWAL_OLLAMA_URL).")


def _build_deterministic_narrative(kpi_payload: dict[str, Any]) -> str:
    """Generate structured formal Malay executive narrative strictly from KPI numbers."""
    month_label = kpi_payload["month_label"]
    k = kpi_payload["kpis"]
    mom = kpi_payload["mom"]
    total = k["total_reman"]

    if total == 0:
        return (
            f"Tiada rekod kemasukan atau kes reman baharu direkodkan bagi tempoh {month_label}. "
            f"Bulan sebelumnya ({mom['prev_month_label']}) mencatat {mom['prev_total_reman']} kes. "
            "Sila pastikan data daftar reman telah dimuat naik sebelum menjana laporan akhir."
        )

    # Paragraph 1: Overall & MoM
    pct = mom.get("total_pct_change")
    delta = mom.get("total_delta", 0)
    if pct is None:
        trend_txt = f"tiada rekod perbandingan bagi {mom['prev_month_label']} ({mom['prev_total_reman']} kes)"
    elif delta > 0:
        trend_txt = f"meningkat sebanyak {pct}% (+{delta} kes) berbanding {mom['prev_month_label']} ({mom['prev_total_reman']} kes)"
    elif delta < 0:
        trend_txt = f"menurun sebanyak {abs(pct)}% ({delta} kes) berbanding {mom['prev_month_label']} ({mom['prev_total_reman']} kes)"
    else:
        trend_txt = f"kekal sama berbanding {mom['prev_month_label']} ({mom['prev_total_reman']} kes)"

    p1 = (
        f"Bagi tempoh {month_label}, sebanyak {total} rekod tahanan reman direkodkan, "
        f"{trend_txt}. Daripada jumlah tersebut, {k['aktif']} kes masih berstatus aktif manakala "
        f"{k['bebas']} kes telah dibebaskan."
    )

    # Paragraph 2: Depot, Nationality, Offence
    depot_parts = [f"Depot {d['name']} sebanyak {d['count']} kes ({d['pct']}%)" for d in k["depot"][:3]]
    depot_txt = ", ".join(depot_parts) if depot_parts else "tiada pecahan depot"

    nat_txt = (
        f"{k['warganegara'][0]['name']} ({k['warganegara'][0]['count']} kes, {k['warganegara'][0]['pct']}%)"
        if k["warganegara"] else "tidak dinyatakan"
    )
    act_txt = (
        f"{k['akta'][0]['name']} ({k['akta'][0]['count']} kes, {k['akta'][0]['pct']}%)"
        if k["akta"] else "tidak dinyatakan"
    )
    sec_txt = (
        f" dengan seksyen paling kerap ialah {k['top_seksyen'][0]['name']} ({k['top_seksyen'][0]['count']} kes)"
        if k["top_seksyen"] else ""
    )

    p2 = (
        f"Mengikut pecahan lokasi, taburan kes merangkumi {depot_txt}. "
        f"Kumpulan warganegara tertinggi ialah {nat_txt}, manakala kategori kesalahan utama ialah "
        f"{act_txt}{sec_txt}."
    )

    # Paragraph 3: Urgency, Workload, UC-2/UC-3
    peg = k["pegawai"]
    top_off = peg["beban_tertinggi"]
    uc3 = kpi_payload["uc3_forecast"]
    uc3_parts = []
    for dep, val in (uc3.get("anggaran_kemasukan_bulanan_depot") or {}).items():
        uc3_parts.append(f"Depot {dep}: {val} kes/bulan")
    uc3_txt = (
        f" Rujukan anggaran kemasukan bulanan (UC-3: {uc3['source']}) mengunjurkan "
        + ", ".join(uc3_parts) + "."
        if uc3_parts else ""
    )

    p3 = (
        f"Dari sudut pemantauan kes (UC-2), terdapat {k['urgent_atau_tertunggak']} kes aktif yang tamat tempoh "
        f"dalam 3 hari atau sudah tertunggak, serta {k['tempoh_lebih_14_hari']} kes melebihi tempoh 14 hari. "
        f"Seramai {peg['jumlah_pegawai_aktif']} pegawai aktif mengendalikan purata {peg['purata_kes_per_pegawai']} kes seorang, "
        f"dengan beban tertinggi oleh {top_off['name']} ({top_off['count']} kes).{uc3_txt}"
    )

    # Paragraph 4: Data quality & recommendations
    dq = k["kualiti_data"]
    dq_notes = []
    if dq["nombor_reman_kosong"] > 0:
        dq_notes.append(f"{dq['nombor_reman_kosong']} rekod tanpa No. Reman")
    if dq["tarikh_tamat_sebelum_masuk"] > 0:
        dq_notes.append(f"{dq['tarikh_tamat_sebelum_masuk']} rekod tarikh tamat sebelum tarikh masuk")
    if dq["tahun_tamat_janggal"] > 0:
        dq_notes.append(f"{dq['tahun_tamat_janggal']} rekod tahun tamat janggal")

    dq_txt = (
        "Semakan kualiti data mengesan " + ", ".join(dq_notes) + " yang perlu disahkan oleh pegawai data. "
        if dq_notes else
        "Tiada anomali kritikal kualiti data dikesan bagi kohort bulan ini. "
    )

    insights = kpi_payload.get("insights") or []
    top_insight = insights[0]["title"] if insights else "Pemantauan rutin diteruskan"
    p4 = (
        f"{dq_txt}Keutamaan tindakan operasi bulan seterusnya tertumpu kepada: {top_insight}."
    )

    return "\n\n".join([p1, p2, p3, p4])


def generate_narrative(kpi_payload: dict[str, Any], mode: str = "auto") -> dict[str, Any]:
    """Generate narrative + numeric traceability guard from a Phase 1 KPI payload.

    Args:
        kpi_payload: Output dictionary from `uc4.phase1_kpi.build_monthly_kpi`.
        mode: 'auto' (try LLM, fallback deterministic), 'fallback', or 'llm'.
    """
    assert_kpi_payload_safe(kpi_payload)
    compact = _compact_kpi_for_prompt(kpi_payload)

    used_mode = "deterministic_fallback"
    provider = "template_engine"
    fallback_reason = ""

    if mode in ("auto", "llm"):
        try:
            text, provider = _call_llm(compact)
            used_mode = "llm"
        except Exception as exc:  # noqa: BLE001
            if mode == "llm":
                raise
            fallback_reason = str(exc)
            text = _build_deterministic_narrative(kpi_payload)
    elif mode == "fallback":
        text = _build_deterministic_narrative(kpi_payload)
    else:
        raise ValueError(f"Mode naratif tidak sah: {mode}")

    trace = trace_narrative_numbers(text, compact)
    # If an LLM hallucinated an untraced number in auto mode, fall back safely so target 0 mismatch holds.
    if used_mode == "llm" and not trace["passed"] and mode == "auto":
        fallback_reason = f"LLM untraced numbers blocked: {trace['untraced_numbers']}"
        text = _build_deterministic_narrative(kpi_payload)
        used_mode = "deterministic_fallback"
        provider = "template_engine"
        trace = trace_narrative_numbers(text, compact)

    return {
        "schema_version": SCHEMA_VERSION,
        "phase": "phase2_narrative",
        "generated_at": dt.datetime.now().isoformat(timespec="seconds"),
        "month": kpi_payload["month"],
        "month_label": kpi_payload["month_label"],
        "mode": used_mode,
        "provider": provider,
        "fallback_reason": fallback_reason,
        "privacy_verified": True,
        "numeric_guard": trace,
        "narrative_text": text,
        "paragraphs": [p.strip() for p in text.split("\n\n") if p.strip()],
    }
