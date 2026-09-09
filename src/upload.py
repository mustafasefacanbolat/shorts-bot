"""YouTube Data API v3 ile yükleme. Ücretsiz: günlük 10.000 birim kota,
videos.insert ~100 birim (Aralık 2025'ten beri), yani günde onlarca video."""
import os
from google.oauth2.credentials import Credentials
from googleapiclient.discovery import build
from googleapiclient.http import MediaFileUpload


def _servis():
    kimlik = Credentials(
        token=None,
        refresh_token=os.environ["YT_REFRESH_TOKEN"],
        client_id=os.environ["YT_CLIENT_ID"],
        client_secret=os.environ["YT_CLIENT_SECRET"],
        token_uri="https://oauth2.googleapis.com/token",
        scopes=["https://www.googleapis.com/auth/youtube.upload",
                "https://www.googleapis.com/auth/youtube.force-ssl"],
    )
    return build("youtube", "v3", credentials=kimlik, cache_discovery=False)


def yukle(video_yolu, senaryo, cfg):
    yt = cfg["youtube"]
    govde = {
        "snippet": {
            "title": senaryo["baslik"],
            "description": senaryo["aciklama"],
            "tags": senaryo["etiketler"],
            "categoryId": str(yt["kategori_id"]),
            "defaultLanguage": cfg["seri"]["dil"],
            "defaultAudioLanguage": cfg["seri"]["dil"],
        },
        "status": {
            "privacyStatus": yt["gizlilik"],
            "selfDeclaredMadeForKids": bool(yt["cocuklar_icin"]),
        },
    }
    medya = MediaFileUpload(str(video_yolu), chunksize=-1, resumable=True,
                            mimetype="video/mp4")
    istek = _servis().videos().insert(
        part="snippet,status", body=govde, media_body=medya, notifySubscribers=True)

    yanit = None
    while yanit is None:
        _, yanit = istek.next_chunk()
    video_id = yanit["id"]

    # Sabit yorum sorusunu kanal adına otomatik yaz.
    # (Sabitleme API'de yok; Studio'dan tek dokunuşla sabitlersin.)
    soru = (senaryo.get("sabit_yorum") or "").strip()
    if soru:
        try:
            _servis().commentThreads().insert(
                part="snippet",
                body={"snippet": {"videoId": video_id, "topLevelComment": {
                    "snippet": {"textOriginal": soru}}}},
            ).execute()
            print(f"      yorum yazıldı: {soru}")
        except Exception as e:
            print(f"      ! yorum yazılamadı ({type(e).__name__}: {str(e)[:120]})")
    return video_id
