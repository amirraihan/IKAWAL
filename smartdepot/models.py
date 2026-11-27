"""Pydantic models for structured input (E1 entry form)."""

from __future__ import annotations

from datetime import date

from pydantic import BaseModel, Field, field_validator

from .constants import (
    DEPOTS, GENDER_MAP, KNOWN_AKTA, KNOWN_BANGSA, KNOWN_NATIONALITIES, TINDAKAN_CODES,
)


class RemanForm(BaseModel):
    """A single reman case as captured on the entry form.

    Uses dropdown-friendly fields where the design calls for controlled
    vocabularies, and two date pickers for the reman period.
    """

    no_reman: str = Field(..., min_length=1, description="Reman reference (key), e.g. 26(0001)BD")
    nama: str = Field(..., min_length=1)
    jantina: str = "LELAKI"
    umur_thn: int = Field(..., ge=0, le=120)
    bangsa: str = "-"
    warganegara: str = "Tidak Dinyatakan"
    dokumen: str = "NIL"
    nama_pegawai: str = ""
    fail: str = ""
    depot: str = "DIKK"
    catatan: str = ""
    tindakan: str = "BELUM MUKTAMAD"
    kesalahan: str = ""
    tarikh_reman_mula: date
    tarikh_reman_tamat: date

    @field_validator("jantina")
    @classmethod
    def _norm_gender(cls, v: str) -> str:
        return GENDER_MAP.get(str(v).strip().lower(), v.strip().upper())

    @field_validator("depot")
    @classmethod
    def _check_depot(cls, v: str) -> str:
        v = v.strip().upper()
        if v not in DEPOTS:
            raise ValueError(f"DEPOT must be one of {DEPOTS}")
        return v

    @field_validator("tindakan")
    @classmethod
    def _check_tindakan(cls, v: str) -> str:
        v = v.strip().upper()
        if v not in TINDAKAN_CODES:
            raise ValueError(f"TINDAKAN must be one of {TINDAKAN_CODES}")
        return v

    @field_validator("warganegara")
    @classmethod
    def _check_warga(cls, v: str) -> str:
        return v if v in KNOWN_NATIONALITIES else "Lain-lain"

    @field_validator("bangsa")
    @classmethod
    def _check_bangsa(cls, v: str) -> str:
        return v if v in KNOWN_BANGSA else "Lain-lain"

    def to_record(self) -> dict:
        """Flatten to the canonical record shape used by the feature layer."""
        return {
            "no_reman": self.no_reman.strip().upper(),
            "nama": self.nama.strip().upper(),
            "jantina": self.jantina,
            "umur_thn": int(self.umur_thn),
            "bangsa": self.bangsa,
            "warganegara": self.warganegara,
            "dokumen": self.dokumen,
            "nama_pegawai": self.nama_pegawai,
            "fail": self.fail,
            "depot": self.depot,
            "catatan": self.catatan,
            "tindakan": self.tindakan,
            "kesalahan": self.kesalahan,
            "tarikh_reman_mula": self.tarikh_reman_mula,
            "tarikh_reman_tamat": self.tarikh_reman_tamat,
            "tarikh_masuk": f"{self.tarikh_reman_mula:%d.%m.%Y}",
            "tarikh_tamat_reman_raw": f"{self.tarikh_reman_tamat:%d.%m.%Y}",
        }
