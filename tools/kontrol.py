"""Yüklemeden önce her şeyi doğrular: anahtarlar çalışıyor mu, hangi kanala yüklenecek?

Kullanım:  python tools/kontrol.py
"""
import os
import sys

TAMAM, HATA = "  ✓", "  ✗"
sorun = 0


def bak(ad):
    global sorun
    v = os.environ.get(ad, "").strip()
    if v:
        print(f"{TAMAM} {ad:18s} var ({v[:6]}...{v[-4:]}, {len(v)} karakter)")
    else:
        print(f"{HATA} {ad:18s} EKSİK")
        sorun += 1
    return v


print("\n=== 1) Ortam değişkenleri ===")
for a in ("GEMINI_API_KEY", "YT_CLIENT_ID", "YT_CLIENT_SECRET", "YT_REFRESH_TOKEN"):
    bak(a)

print("\n=== 2) Gemini anahtarı çalışıyor mu? ===")
try:
    import requests
    y = requests.get("https://generativelanguage.googleapis.com/v1beta/models",
                     params={"key": os.environ.get("GEMINI_API_KEY", "")}, timeout=60)
    if y.status_code == 200:
        n = len(y.json().get("models", []))
        print(f"{TAMAM} Gemini yanıt verdi, {n} model erişilebilir")
    else:
        print(f"{HATA} Gemini reddetti (HTTP {y.status_code})")
        print(f"     {y.text[:200]}")
        sorun += 1
except Exception as e:
    print(f"{HATA} Gemini'ye ulaşılamadı: {type(e).__name__}: {e}")
    sorun += 1

print("\n=== 3) YouTube yetkisi ve HANGİ KANAL? ===")
try:
    from google.oauth2.credentials import Credentials
    from googleapiclient.discovery import build

    kimlik = Credentials(
        token=None,
        refresh_token=os.environ["YT_REFRESH_TOKEN"],
        client_id=os.environ["YT_CLIENT_ID"],
        client_secret=os.environ["YT_CLIENT_SECRET"],
        token_uri="https://oauth2.googleapis.com/token",
        scopes=["https://www.googleapis.com/auth/youtube.force-ssl"],
    )
    yt = build("youtube", "v3", credentials=kimlik, cache_discovery=False)
    y = yt.channels().list(part="snippet,statistics", mine=True).execute()
    if not y.get("items"):
        print(f"{HATA} Bu hesaba bağlı kanal bulunamadı")
        sorun += 1
    else:
        k = y["items"][0]
        print(f"{TAMAM} Yetki geçerli")
        print(f"     KANAL     : {k['snippet']['title']}")
        print(f"     Handle    : {k['snippet'].get('customUrl', '(yok)')}")
        print(f"     Abone     : {k['statistics'].get('subscriberCount', '?')}")
        print(f"     Video     : {k['statistics'].get('videoCount', '?')}")
        print("\n     >>> Videolar BU kanala yüklenecek. Doğru kanal mı? <<<")
except Exception as e:
    print(f"{HATA} YouTube yetkisi çalışmadı: {type(e).__name__}: {str(e)[:220]}")
    sorun += 1

print("\n" + "=" * 50)
print("HER ŞEY HAZIR — yüklemeye geçebilirsin." if not sorun
      else f"{sorun} sorun var, yukarıya bak.")
sys.exit(1 if sorun else 0)
