"""Instagram bağlantısını doğrular: token geçerli mi, hangi hesaba yayın yapılacak?

Kullanım:  python tools/instagram_test.py
"""
import os
import sys

import requests

GRAPH = "https://graph.facebook.com/v23.0"
TAMAM, HATA = "  ✓", "  ✗"
sorun = 0

print("\n=== 1) Ortam değişkenleri ===")
for ad in ("IG_USER_ID", "IG_ACCESS_TOKEN"):
    v = os.environ.get(ad, "")
    if v:
        print(f"{TAMAM} {ad:16s} var ({len(v)} karakter)")
    else:
        print(f"{HATA} {ad:16s} EKSİK")
        sorun += 1

if not sorun:
    print("\n=== 2) Hesap ve yayın hakkı ===")
    try:
        y = requests.get(f"{GRAPH}/{os.environ['IG_USER_ID']}", params={
            "fields": "username,name,followers_count,media_count",
            "access_token": os.environ["IG_ACCESS_TOKEN"]}, timeout=60)
        if y.status_code != 200:
            print(f"{HATA} Hesap okunamadı: {y.text[:300]}")
            sorun += 1
        else:
            h = y.json()
            print(f"{TAMAM} Token geçerli")
            print(f"     HESAP     : @{h.get('username','?')}")
            print(f"     Takipçi   : {h.get('followers_count','?')}")
            print(f"     Gönderi   : {h.get('media_count','?')}")
            print("\n     >>> Videolar BU hesaba yüklenecek. Doğru mu? <<<")

        y = requests.get(f"{GRAPH}/{os.environ['IG_USER_ID']}/content_publishing_limit",
                         params={"access_token": os.environ["IG_ACCESS_TOKEN"]},
                         timeout=60)
        if y.status_code == 200:
            d = y.json().get("data", [{}])[0]
            print(f"\n{TAMAM} Yayın hakkı: son 24 saatte "
                  f"{d.get('quota_usage', 0)}/{d.get('config', {}).get('quota_total', 100)} kullanılmış")
        else:
            print(f"{HATA} Yayın hakkı sorgulanamadı — izinler eksik olabilir")
            print(f"     {y.text[:250]}")
            sorun += 1
    except Exception as e:
        print(f"{HATA} {type(e).__name__}: {str(e)[:200]}")
        sorun += 1

print("\n" + "=" * 50)
print("INSTAGRAM HAZIR." if not sorun else f"{sorun} sorun var, yukarıya bak.")
sys.exit(1 if sorun else 0)
