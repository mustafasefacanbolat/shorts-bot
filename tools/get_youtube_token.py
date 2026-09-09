"""TEK SEFERLİK: YouTube refresh token üretir (kendi bilgisayarında çalıştır).

1) Google Cloud Console > yeni proje > "YouTube Data API v3" etkinleştir
2) OAuth consent screen: External, kendi Gmail'ini "Test users"a ekle
3) Credentials > Create > OAuth client ID > "Desktop app" > client_secret.json indir
4) Bu dosyanın yanına client_secret.json koy ve çalıştır:
      pip install google-auth-oauthlib
      python tools/get_youtube_token.py
5) Çıktıdaki üç değeri GitHub Secrets'a ekle.
"""
from google_auth_oauthlib.flow import InstalledAppFlow

SCOPES = [
    "https://www.googleapis.com/auth/youtube.upload",     # video yükleme
    "https://www.googleapis.com/auth/youtube.force-ssl",  # sabit yorumu yazma
]

akis = InstalledAppFlow.from_client_secrets_file("client_secret.json", SCOPES)
kimlik = akis.run_local_server(port=0, prompt="consent", access_type="offline")

print("\n=== GitHub Secrets'a şunları ekle ===")
print("YT_CLIENT_ID     =", kimlik.client_id)
print("YT_CLIENT_SECRET =", kimlik.client_secret)
print("YT_REFRESH_TOKEN =", kimlik.refresh_token)
