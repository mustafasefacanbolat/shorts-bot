"""Sadece montaj adımını tekrar çalıştırır (senaryo/ses/görsel yeniden üretilmez).
Kullanım:  python tools/montaj_tekrar.py
"""
import sys
from pathlib import Path
import yaml

KOK = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(KOK))
from src import video

cfg = yaml.safe_load(open(KOK / "config.yaml", encoding="utf-8"))
dizinler = sorted((KOK / "cikti").glob("bolum_*"))
if not dizinler:
    sys.exit("cikti/ içinde bölüm klasörü yok.")
d = dizinler[-1]
klipler = sorted(str(p) for p in d.glob("klip_*.mp4"))
alt = d / "altyazi.ass"
print(f"Klasör: {d.name} | klip: {len(klipler)}")
out = video.son_montaj(klipler, d / "ses.m4a", str(alt) if alt.exists() else None,
                       cfg, d / f"{d.name}.mp4", d)
print(f"MONTAJ TAMAM: {out}  ({video.sure(out):.1f} sn)")
