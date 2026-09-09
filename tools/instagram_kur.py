"""Instagram için süresiz token ve hesap kimliğini alır, gizli.sh'a yazar.

Sen sadece Graph API Explorer'dan aldığın GEÇİCİ token'ı verirsin.
Bu araç şunları kendisi yapar:
  1. Geçici kullanıcı token'ını uzun ömürlüye çevirir
  2. Yönettiğin sayfaları listeler, seçtiğin sayfanın token'ını alır
     (sayfa token'larının son kullanma tarihi YOKTUR)
  3. O sayfaya bağlı Instagram işletme hesabının kimliğini bulur
  4. IG_USER_ID ve IG_ACCESS_TOKEN'ı gizli.sh dosyasına ekler

Kullanım:  python tools/instagram_kur.py
"""
import re
import stat
import sys
from getpass import getpass
from pathlib import Path

import requests

SURUM = "v23.0"
GRAPH = f"https://graph.facebook.com/{SURUM}"
KOK = Path(__file__).resolve().parent.parent
GIZLI = KOK / "gizli.sh"


def sor(etiket, gizli=False):
    d = (getpass(f"  {etiket}: ") if gizli else input(f"  {etiket}: ")).strip()
    if not d:
        sys.exit("Boş bırakılamaz.")
    return d


def kontrol(y, ne):
    if y.status_code != 200:
        sys.exit(f"\n{ne} başarısız (HTTP {y.status_code}):\n{y.text[:400]}")
    return y.json()


print("\n=== Instagram kurulumu ===\n")
print("Meta uygulamanın kimlik bilgileri (App settings > Basic):")
app_id = sor("App ID")
app_secret = sor("App Secret (görünmez)", gizli=True)
print("\nGraph API Explorer'dan aldığın geçici token:")
gecici = sor("Access Token (görünmez)", gizli=True)

# 1) uzun omurlu kullanici token'i
print("\n[1/4] Token uzun ömürlüye çevriliyor...")
uzun = kontrol(requests.get(f"{GRAPH}/oauth/access_token", params={
    "grant_type": "fb_exchange_token", "client_id": app_id,
    "client_secret": app_secret, "fb_exchange_token": gecici}, timeout=60),
    "Token değişimi")["access_token"]
print("      tamam")

# 2) sayfalar
print("\n[2/4] Yönettiğin sayfalar alınıyor...")
sayfalar = kontrol(requests.get(f"{GRAPH}/me/accounts",
                                params={"access_token": uzun}, timeout=60),
                   "Sayfa listesi").get("data", [])

if not sayfalar:
    # Neden boş? Verilen izinleri ve hesabı göster.
    print("\n      Sayfa bulunamadı. Sebebi anlamak için kontrol ediliyor...\n")
    izin = requests.get(f"{GRAPH}/me/permissions",
                        params={"access_token": uzun}, timeout=60).json()
    verilen = [d["permission"] for d in izin.get("data", [])
               if d.get("status") == "granted"]
    reddedilen = [d["permission"] for d in izin.get("data", [])
                  if d.get("status") != "granted"]
    print("      VERİLEN izinler   :", ", ".join(verilen) or "(hiçbiri)")
    if reddedilen:
        print("      VERİLMEYEN izinler:", ", ".join(reddedilen))

    ben = requests.get(f"{GRAPH}/me", params={"fields": "id,name",
                       "access_token": uzun}, timeout=60).json()
    print("      Giriş yapan hesap :", ben.get("name", "?"))

    if not verilen or "pages_show_list" not in verilen:
        print("""
      İzinler eksik. Graph API Explorer'a dön, 'Generate Access Token'a
      tekrar bas ve açılan pencerede sayfanı İŞARETLE, sonra tekrar dene.
      """)
        sys.exit(1)

    # İzinler tamam ama liste boş: yeni sayfa deneyiminde olabiliyor.
    # Sayfanın kimliğini biliyorsak doğrudan onunla devam edebiliriz.
    print("""
      İzinler verilmiş ama liste boş döndü. Bu, yeni sayfa deneyiminde
      görülen bir durum; sayfaya kimliğiyle doğrudan erişebiliriz.

      Sayfa kimliğini Facebook izin penceresinde sayfa adının altında
      görmüştün (uzun bir sayı). Ayrıca sayfanın 'Hakkında' bölümünde de var.
      """)
    sayfa_id = sor("Facebook sayfa kimliği")
    s2 = kontrol(requests.get(f"{GRAPH}/{sayfa_id}", params={
        "fields": "name,access_token", "access_token": uzun}, timeout=60),
        "Sayfa erişimi")
    if "access_token" not in s2:
        sys.exit("Sayfa token'ı alınamadı — bu sayfanın yöneticisi misin?")
    sayfalar = [{"id": sayfa_id, "name": s2.get("name", "?"),
                 "access_token": s2["access_token"]}]
    print(f"      sayfa bulundu: {sayfalar[0]['name']}")

for i, s in enumerate(sayfalar, 1):
    print(f"      {i}) {s['name']}")
secim = sayfalar[0] if len(sayfalar) == 1 else sayfalar[
    int(sor(f"Hangi sayfa? (1-{len(sayfalar)})")) - 1]
sayfa_token = secim["access_token"]
print(f"      seçilen: {secim['name']}")

# 3) sayfaya bagli instagram hesabi
print("\n[3/4] Sayfaya bağlı Instagram hesabı aranıyor...")
bilgi = kontrol(requests.get(f"{GRAPH}/{secim['id']}", params={
    "fields": "instagram_business_account{id,username,name}",
    "access_token": sayfa_token}, timeout=60), "Instagram hesabı")
hesap = bilgi.get("instagram_business_account")
if not hesap:
    sys.exit("Bu sayfaya bağlı bir Instagram İŞLETME hesabı görünmüyor.\n"
             "Kontrol et: hesap İşletme tipinde mi, sayfaya bağlı mı?")
print(f"      bulundu: @{hesap.get('username', '?')} (kimlik {hesap['id']})")

# 4) gizli.sh guncelle
print("\n[4/4] gizli.sh güncelleniyor...")
mevcut = GIZLI.read_text(encoding="utf-8") if GIZLI.exists() else ""
mevcut = re.sub(r'^export IG_(USER_ID|ACCESS_TOKEN)=.*\n?', '', mevcut, flags=re.M)
GIZLI.write_text(mevcut.rstrip() + "\n"
                 + f'export IG_USER_ID="{hesap["id"]}"\n'
                 + f'export IG_ACCESS_TOKEN="{sayfa_token}"\n', encoding="utf-8")
GIZLI.chmod(stat.S_IRUSR | stat.S_IWUSR)

print(f"""
Tamamlandı.

  Instagram hesabı : @{hesap.get('username', '?')}
  Facebook sayfası : {secim['name']}
  Token türü       : sayfa token'ı (son kullanma tarihi YOK)

Şimdi şunu çalıştır:

    source gizli.sh
    python tools/instagram_test.py
""")
