"""Hazır bir bölümü SADECE Instagram'a yayınlar (yeni video üretmez).

YouTube'a çıkmış bir videoyu Instagram'a da atmak için kullanılır.

Kullanım:
    python tools/instagram_tek.py                    # cikti/ içindeki son bölüm
    python tools/instagram_tek.py <klasör>           # belirli bir klasör
      (klasörde bolum_XXXX.mp4 ve senaryo.json bulunmalı)
"""
import json
import os
import subprocess
import sys
from pathlib import Path

KOK = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(KOK))
import yaml
from src import instagram


def komut(*args):
    try:
        c = subprocess.run(args, capture_output=True, text=True, timeout=60)
        return c.stdout.strip() if c.returncode == 0 else ""
    except Exception:
        return ""


def klasor_bul():
    if len(sys.argv) > 1:
        return Path(sys.argv[1]).expanduser().resolve()
    adaylar = sorted(KOK.glob("**/bolum_[0-9]*"), key=lambda p: p.stat().st_mtime)
    adaylar = [a for a in adaylar if a.is_dir() and list(a.glob("bolum_*.mp4"))]
    if not adaylar:
        sys.exit("Bölüm klasörü bulunamadı. Klasör yolunu argüman olarak ver.")
    return adaylar[-1]


d = klasor_bul()
videolar = sorted(d.glob("bolum_*.mp4"))
senaryo_yolu = d / "senaryo.json"
if not videolar or not senaryo_yolu.exists():
    sys.exit(f"{d} içinde bolum_*.mp4 ve senaryo.json bulunmalı.\n"
             f"Bulunanlar: {[p.name for p in d.iterdir()][:10]}")

video = videolar[0]
senaryo = json.loads(senaryo_yolu.read_text(encoding="utf-8"))
cfg = yaml.safe_load(open(KOK / "config.yaml", encoding="utf-8"))

# GitHub bilgileri: ortamda yoksa gh komutundan al
if not os.environ.get("GITHUB_TOKEN"):
    t = komut("gh", "auth", "token")
    if not t:
        sys.exit("GitHub yetkisi yok. 'gh auth login' çalıştır.")
    os.environ["GITHUB_TOKEN"] = t
if not os.environ.get("GITHUB_REPOSITORY"):
    r = komut("gh", "repo", "view", "--json", "nameWithOwner", "-q", ".nameWithOwner")
    if not r:
        sys.exit("Depo adı bulunamadı. Proje klasöründe misin?")
    os.environ["GITHUB_REPOSITORY"] = r

for a in ("IG_USER_ID", "IG_ACCESS_TOKEN"):
    if not os.environ.get(a):
        sys.exit(f"{a} tanımlı değil. Önce: source gizli.sh")

mb = video.stat().st_size / 1024 / 1024
print(f"\nKlasör : {d}")
print(f"Video  : {video.name}  ({mb:.0f} MB)")
print(f"Başlık : {senaryo.get('baslik','?')}")
print(f"Bölüm  : {senaryo.get('bolum_no','?')}")
print(f"Depo   : {os.environ['GITHUB_REPOSITORY']}")
if mb > 100:
    sys.exit("Video 100 MB'ı aşıyor — Instagram kabul etmez.")

print("\n--- Instagram açıklaması ---")
print(instagram.aciklama_kur(senaryo, cfg))
print("---")

if input("\nYayınlansın mı? (evet/hayır): ").strip().lower() not in ("e", "evet"):
    sys.exit("Vazgeçildi.")

mid = instagram.paylas(str(video), senaryo, cfg)
print(f"\nYAYINDA — Instagram medya kimliği: {mid}")
print("https://www.instagram.com/" + cfg.get("kanal", {}).get("handle", "").lstrip("@"))
