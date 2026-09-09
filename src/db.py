"""Bölüm sürekliliği için SQLite hafızası.

Her bölümün özeti burada tutulur; senaryo motoru bir sonraki bölümü
yazarken önceki bölümlerin özetini okur. Böylece "Bölüm 1, 2, 3..."
gerçekten birbirinin devamı olur.
"""
import sqlite3
import json
from pathlib import Path

DB_YOLU = Path(__file__).resolve().parent.parent / "state.db"

SEMA = """
CREATE TABLE IF NOT EXISTS bolumler (
    id           INTEGER PRIMARY KEY AUTOINCREMENT,
    seri         TEXT NOT NULL,
    bolum_no     INTEGER NOT NULL,
    baslik       TEXT,
    ozet         TEXT,
    senaryo_json TEXT,
    video_id     TEXT,
    durum        TEXT DEFAULT 'uretiliyor',
    olusturma    TEXT DEFAULT (datetime('now')),
    UNIQUE(seri, bolum_no)
);
CREATE TABLE IF NOT EXISTS kanon (
    id       INTEGER PRIMARY KEY AUTOINCREMENT,
    seri     TEXT NOT NULL,
    olgu     TEXT NOT NULL
);
"""


def baglan():
    kon = sqlite3.connect(DB_YOLU)
    kon.row_factory = sqlite3.Row
    kon.executescript(SEMA)
    return kon


def sonraki_bolum_no(kon, seri: str) -> int:
    satir = kon.execute(
        "SELECT MAX(bolum_no) AS m FROM bolumler WHERE seri=? AND durum='yayinlandi'",
        (seri,),
    ).fetchone()
    return (satir["m"] or 0) + 1


def gecmis(kon, seri: str, limit: int = 8):
    """Son N bölümün özeti (eskiden yeniye)."""
    satirlar = kon.execute(
        "SELECT bolum_no, baslik, ozet FROM bolumler "
        "WHERE seri=? AND durum='yayinlandi' ORDER BY bolum_no DESC LIMIT ?",
        (seri, limit),
    ).fetchall()
    return list(reversed([dict(s) for s in satirlar]))


def kanon_listesi(kon, seri: str):
    return [s["olgu"] for s in kon.execute(
        "SELECT olgu FROM kanon WHERE seri=?", (seri,)).fetchall()]


def kanon_ekle(kon, seri: str, olgular):
    mevcut = set(kanon_listesi(kon, seri))
    for o in olgular or []:
        o = (o or "").strip()
        if o and o not in mevcut:
            kon.execute("INSERT INTO kanon(seri, olgu) VALUES (?,?)", (seri, o))
    kon.commit()


def bolum_kaydet(kon, seri, bolum_no, senaryo):
    kon.execute(
        "INSERT OR REPLACE INTO bolumler(seri, bolum_no, baslik, ozet, senaryo_json, durum) "
        "VALUES (?,?,?,?,?, 'uretiliyor')",
        (seri, bolum_no, senaryo.get("baslik"), senaryo.get("ozet"),
         json.dumps(senaryo, ensure_ascii=False)),
    )
    kon.commit()


def yayinlandi_isaretle(kon, seri, bolum_no, video_id):
    kon.execute(
        "UPDATE bolumler SET durum='yayinlandi', video_id=? WHERE seri=? AND bolum_no=?",
        (video_id, seri, bolum_no),
    )
    kon.commit()
