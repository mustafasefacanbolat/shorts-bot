"""Seslendirme: Gemini TTS (insansı, yönerge alabilen) veya edge-tts (yedek).

Gemini TTS ham PCM döndürür; ffmpeg ile mp3'e çeviriyoruz.
Gemini herhangi bir sebeple çalışmazsa (kota, kesinti) otomatik olarak
edge-tts devreye girer — üretim asla durmaz.
"""
import asyncio
import base64
import html
import os
import subprocess
import time
from pathlib import Path

import requests
import edge_tts

BIRIM = 10_000_000  # 100 ns -> saniye
GEMINI_TTS_URL = ("https://generativelanguage.googleapis.com/v1beta/"
                  "models/{model}:generateContent")
GECICI_KODLAR = {429, 500, 502, 503, 504}


# ---------------------------------------------------------------- yardımcı
def esit_dagit(metin, baslangic, sure_):
    """Zamanlama yoksa kelimeleri süreye eşit paylaştır (son çare)."""
    kelimeler = [k for k in metin.split() if k]
    if not kelimeler or sure_ <= 0:
        return []
    adim = sure_ / len(kelimeler)
    return [{"bas": baslangic + i * adim, "bit": baslangic + (i + 1) * adim,
             "kelime": k} for i, k in enumerate(kelimeler)]


# ---------------------------------------------------------------- Gemini
def _pcm_to_mp3(pcm_bayt, hiz_hz, cikti_yolu):
    p = subprocess.run(
        ["ffmpeg", "-y", "-v", "error", "-f", "s16le", "-ar", str(hiz_hz),
         "-ac", "1", "-i", "pipe:0", "-c:a", "libmp3lame", "-b:a", "128k",
         str(cikti_yolu)],
        input=pcm_bayt, capture_output=True)
    if p.returncode != 0:
        raise RuntimeError("PCM->mp3 çevrilemedi: " + p.stderr.decode()[-400:])


def _gemini_tts(metin, cfg, cikti_yolu, deneme_sayisi=3):
    s = cfg["ses"]
    istem = f"{s.get('gemini_stil', '').strip()}\n\n{metin}".strip()
    govde = {
        "contents": [{"parts": [{"text": istem}]}],
        "generationConfig": {
            "responseModalities": ["AUDIO"],
            "speechConfig": {"voiceConfig": {"prebuiltVoiceConfig": {
                "voiceName": s.get("gemini_ses", "Charon")}}},
        },
    }
    url = GEMINI_TTS_URL.format(model=s.get("model", "gemini-2.5-flash-preview-tts"))
    son = None
    for deneme in range(deneme_sayisi):
        y = requests.post(url, params={"key": os.environ["GEMINI_API_KEY"]},
                          json=govde, timeout=240)
        if y.status_code in GECICI_KODLAR:
            bekle = 5 * (2 ** deneme)
            print(f"      ! Gemini TTS {y.status_code} — {bekle} sn bekleniyor")
            son = RuntimeError(f"Gemini TTS {y.status_code}")
            time.sleep(bekle)
            continue
        if y.status_code != 200:
            raise RuntimeError(f"Gemini TTS {y.status_code}: {y.text[:300]}")
        parcalar = y.json()["candidates"][0]["content"]["parts"]
        for p in parcalar:
            veri = p.get("inlineData") or p.get("inline_data")
            if veri and veri.get("data"):
                mime = veri.get("mimeType") or veri.get("mime_type") or ""
                hiz = 24000
                if "rate=" in mime:
                    try:
                        hiz = int(mime.split("rate=")[1].split(";")[0])
                    except ValueError:
                        pass
                _pcm_to_mp3(base64.b64decode(veri["data"]), hiz, cikti_yolu)
                return str(cikti_yolu)
        raise RuntimeError("Gemini TTS ses döndürmedi")
    raise son or RuntimeError("Gemini TTS başarısız")


# ---------------------------------------------------------------- edge-tts
def _edge_iletisim(metin, voice, hiz, perde):
    try:
        return edge_tts.Communicate(metin, voice, rate=hiz, pitch=perde,
                                    boundary="WordBoundary")
    except TypeError:
        return edge_tts.Communicate(metin, voice, rate=hiz, pitch=perde)


async def _edge_uret(metin, voice, hiz, perde, cikti_yolu):
    kom = _edge_iletisim(metin, voice, hiz, perde)
    kelimeler = []
    with open(cikti_yolu, "wb") as f:
        async for parca in kom.stream():
            tur = parca.get("type")
            if tur == "audio":
                f.write(parca["data"])
            elif tur in ("WordBoundary", "SentenceBoundary"):
                bas = parca["offset"] / BIRIM
                sure_ = parca["duration"] / BIRIM
                yazi = html.unescape(parca.get("text", "")).strip()
                if not yazi:
                    continue
                if tur == "WordBoundary" and len(yazi.split()) == 1:
                    kelimeler.append({"bas": bas, "bit": bas + sure_, "kelime": yazi})
                else:
                    kelimeler.extend(esit_dagit(yazi, bas, sure_))
    return kelimeler


def _edge_tts(metin, cfg, cikti_yolu):
    s = cfg["ses"]
    return asyncio.run(_edge_uret(metin, s["voice"], s["hiz"], s["perde"],
                                  str(cikti_yolu)))


# ---------------------------------------------------------------- dış kapı
def seslendir(metin, cfg, cikti_yolu):
    """metin -> (mp3 yolu, kelime zamanlamaları veya [] )

    Zamanlama boş dönerse hizalamayı align.py yapar.
    """
    saglayici = cfg["ses"].get("saglayici", "gemini")
    if saglayici == "gemini":
        try:
            _gemini_tts(metin, cfg, cikti_yolu)
            return str(cikti_yolu), []          # zamanlama Whisper'dan gelecek
        except Exception as e:
            print(f"      ! Gemini TTS kullanılamadı ({type(e).__name__}: "
                  f"{str(e)[:120]}) — edge-tts'e geçiliyor")
    kelimeler = _edge_tts(metin, cfg, cikti_yolu)
    return str(cikti_yolu), kelimeler
