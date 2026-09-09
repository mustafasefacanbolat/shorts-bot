"""Instagram Reels yayını (Facebook sayfası üzerinden Graph API).

Instagram dosya yüklemesi kabul etmez: videonun HERKESE AÇIK bir adreste
durmasını ister ve kendi sunucusuyla çeker. Bu yüzden video önce GitHub
release dosyası olarak yayınlanır, sonra o adres Instagram'a verilir.

Akış: kap oluştur -> işlenmesini bekle -> yayınla.

Gereken ortam değişkenleri:
  IG_USER_ID, IG_ACCESS_TOKEN          (Meta uygulamasından)
  GITHUB_TOKEN, GITHUB_REPOSITORY      (GitHub Actions bunları kendi verir)
"""
import os
import time
from pathlib import Path

import requests

SURUM = "v23.0"
GRAPH = f"https://graph.facebook.com/{SURUM}"
GH = "https://api.github.com"


# ------------------------------------------------------- herkese açık adres
def release_yukle(video_yolu, etiket, baslik=""):
    """Videoyu GitHub release dosyası olarak yükler, herkese açık adresi döner.

    Release dosyalarının süresi dolmaz; artefaktların aksine kalıcıdır.
    """
    token = os.environ["GITHUB_TOKEN"]
    depo = os.environ["GITHUB_REPOSITORY"]          # "kullanici/depo"
    bas = {"Authorization": f"Bearer {token}",
           "Accept": "application/vnd.github+json"}

    y = requests.post(f"{GH}/repos/{depo}/releases", headers=bas, json={
        "tag_name": etiket, "name": baslik or etiket,
        "body": "Otomatik üretim — Instagram yayını için barındırılıyor.",
        "draft": False, "prerelease": False,
    }, timeout=120)

    if y.status_code == 422:                        # etiket zaten var
        y = requests.get(f"{GH}/repos/{depo}/releases/tags/{etiket}",
                         headers=bas, timeout=60)
    y.raise_for_status()
    surum = y.json()

    # aynı isimde eski dosya varsa sil (tekrar çalıştırmalarda çakışmasın)
    ad = Path(video_yolu).name
    for d in surum.get("assets", []):
        if d["name"] == ad:
            requests.delete(f"{GH}/repos/{depo}/releases/assets/{d['id']}",
                            headers=bas, timeout=60)

    yukleme = surum["upload_url"].split("{")[0]
    with open(video_yolu, "rb") as f:
        y = requests.post(f"{yukleme}?name={ad}", headers={
            **bas, "Content-Type": "video/mp4"}, data=f, timeout=600)
    y.raise_for_status()
    return y.json()["browser_download_url"]


# ------------------------------------------------------------- Reels yayını
def _kap_olustur(video_url, aciklama):
    y = requests.post(f"{GRAPH}/{os.environ['IG_USER_ID']}/media", data={
        "media_type": "REELS",
        "video_url": video_url,
        "caption": aciklama[:2200],
        "share_to_feed": "true",
        "access_token": os.environ["IG_ACCESS_TOKEN"],
    }, timeout=180)
    if y.status_code != 200:
        raise RuntimeError(f"Instagram kap hatası {y.status_code}: {y.text[:300]}")
    return y.json()["id"]


def _bekle(kap_id, azami_saniye=300):
    """Instagram videoyu indirip işleyene kadar bekle."""
    bitis = time.time() + azami_saniye
    while time.time() < bitis:
        y = requests.get(f"{GRAPH}/{kap_id}", params={
            "fields": "status_code,status",
            "access_token": os.environ["IG_ACCESS_TOKEN"]}, timeout=60)
        durum = y.json().get("status_code", "?")
        if durum == "FINISHED":
            return
        if durum in ("ERROR", "EXPIRED"):
            raise RuntimeError(f"Instagram işleme hatası: {y.text[:300]}")
        time.sleep(10)
    raise RuntimeError("Instagram videoyu 5 dakikada işleyemedi")


def _yayinla(kap_id):
    y = requests.post(f"{GRAPH}/{os.environ['IG_USER_ID']}/media_publish", data={
        "creation_id": kap_id,
        "access_token": os.environ["IG_ACCESS_TOKEN"]}, timeout=120)
    if y.status_code != 200:
        raise RuntimeError(f"Instagram yayın hatası {y.status_code}: {y.text[:300]}")
    return y.json()["id"]


def aciklama_kur(senaryo, cfg):
    """YouTube açıklamasından Instagram'a uygun bir metin hazırlar."""
    kanal = cfg.get("kanal", {})
    ig = cfg.get("instagram", {})
    etiketler = senaryo.get("etiketler", [])[:int(ig.get("etiket_sayisi", 12))]
    satirlar = [
        (senaryo.get("aciklama_kanca") or senaryo.get("baslik", "")).strip(),
        "",
        f"{kanal.get('ad', '')} — Bölüm {senaryo.get('bolum_no', '')}".strip(" —"),
        "Yeni bölüm her gün 13:00'te.",
        "",
        cfg["youtube"]["seffaflik_notu"],
        "",
        " ".join(f"#{e.replace(' ', '')}" for e in etiketler),
    ]
    return "\n".join(satirlar)[:2200]


def paylas(video_yolu, senaryo, cfg):
    """Videoyu barındır ve Instagram'a Reels olarak yayınla. Medya kimliğini döner."""
    etiket = f"bolum-{senaryo.get('bolum_no', 0):04d}"
    print("      video herkese açık adrese yükleniyor...")
    url = release_yukle(video_yolu, etiket, senaryo.get("baslik", etiket))
    print(f"      adres hazır: {url}")

    kap = _kap_olustur(url, aciklama_kur(senaryo, cfg))
    print(f"      Instagram videoyu işliyor (kap {kap})...")
    _bekle(kap)
    return _yayinla(kap)
