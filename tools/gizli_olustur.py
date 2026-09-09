"""gizli.sh dosyasını otomatik oluşturur — elle kopyalama yok.

Yaptığı işler:
  1. client_secret.json'dan client id ve secret'ı okur
  2. Tarayıcıda Google yetkilendirmesini açar, refresh token'ı alır
  3. Gemini anahtarını sorar (yazarken ekranda görünmez)
  4. Hepsini gizli.sh dosyasına yazar ve dosyayı kilitler (chmod 600)

Kullanım:  python tools/gizli_olustur.py
"""
import json
import os
import stat
import sys
from getpass import getpass
from pathlib import Path

KOK = Path(__file__).resolve().parent.parent
ISTEMCI = KOK / "client_secret.json"
HEDEF = KOK / "gizli.sh"

SCOPES = [
    "https://www.googleapis.com/auth/youtube.upload",
    "https://www.googleapis.com/auth/youtube.force-ssl",
]

if not ISTEMCI.exists():
    sys.exit("client_secret.json bulunamadı. Google Cloud > Clients sayfasından "
             "indirip proje klasörüne koy.")

print("\n[1/3] Tarayıcı açılıyor — kanalının Google hesabıyla giriş yap.")
print("      'Google bu uygulamayı doğrulamadı' derse: Gelişmiş > ... sayfasına git\n")

from google_auth_oauthlib.flow import InstalledAppFlow

akis = InstalledAppFlow.from_client_secrets_file(str(ISTEMCI), SCOPES)
kimlik = akis.run_local_server(port=0, prompt="consent", access_type="offline")

if not kimlik.refresh_token:
    sys.exit("Refresh token gelmedi. Tekrar dene; izin ekranında 'Continue' demen gerekiyor.")

print("\n[2/3] Yetki alındı.")

# Gemini anahtarı: ortamda varsa onu kullan, yoksa sor
gemini = os.environ.get("GEMINI_API_KEY", "").strip()
if gemini:
    print(f"      Gemini anahtarı ortamdan alındı ({gemini[:6]}...{gemini[-4:]})")
else:
    print("\n      Gemini API anahtarını yapıştır (yazarken ekranda GÖRÜNMEZ, "
          "yapıştırıp Enter'a bas):")
    gemini = getpass("      GEMINI_API_KEY: ").strip()
    if not gemini:
        sys.exit("Gemini anahtarı boş bırakılamaz.")

satirlar = [
    "# Bu dosya gizlidir. .gitignore'da olduğu için GitHub'a gitmez.",
    "# Kullanım:  source gizli.sh",
    f'export GEMINI_API_KEY="{gemini}"',
    f'export YT_CLIENT_ID="{kimlik.client_id}"',
    f'export YT_CLIENT_SECRET="{kimlik.client_secret}"',
    f'export YT_REFRESH_TOKEN="{kimlik.refresh_token}"',
    "",
]
HEDEF.write_text("\n".join(satirlar), encoding="utf-8")
HEDEF.chmod(stat.S_IRUSR | stat.S_IWUSR)   # sadece sen okuyabilirsin

print(f"\n[3/3] {HEDEF.name} oluşturuldu ve kilitlendi.\n")
print("Şimdi şunu çalıştır:\n")
print("    source gizli.sh\n")
