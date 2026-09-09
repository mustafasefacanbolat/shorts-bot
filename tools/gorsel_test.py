"""Hangi görsel kaynağı ne kalitede veriyor? Ölçer ve örnekleri kaydeder.

Kullanım:  python tools/gorsel_test.py
Çıktı:     cikti/gorsel_testi/  (aç ve gözünle karşılaştır)
"""
import os
import struct
import sys
import urllib.parse
from pathlib import Path

import requests

KOK = Path(__file__).resolve().parent.parent
CIKTI = KOK / "cikti" / "gorsel_testi"
PROMPT = ("an elderly monkey with silver-grey muzzle sitting on a mossy fallen beech "
          "trunk at dawn, looking down at the misty forest floor, low angle close-up, "
          "backlit by golden sunrays through the canopy, photorealistic, 85mm lens, "
          "f/1.8, realistic fur texture, no text, no watermark")


def olcu(veri):
    """JPEG/PNG başlığından en x boy oku."""
    if veri[:8] == b"\x89PNG\r\n\x1a\n":
        w, h = struct.unpack(">II", veri[16:24])
        return f"{w}x{h}"
    i = 2
    while i < len(veri) - 9:
        if veri[i] != 0xFF:
            i += 1
            continue
        if veri[i + 1] in (0xC0, 0xC1, 0xC2):
            h, w = struct.unpack(">HH", veri[i + 5:i + 9])
            return f"{w}x{h}"
        i += 2 + struct.unpack(">H", veri[i + 2:i + 4])[0]
    return "?"


def kaydet(ad, veri):
    CIKTI.mkdir(parents=True, exist_ok=True)
    uzanti = ".png" if veri[:8] == b"\x89PNG\r\n\x1a\n" else ".jpg"
    (CIKTI / (ad + uzanti)).write_bytes(veri)


def pollinations(ad, **params):
    url = "https://image.pollinations.ai/prompt/" + urllib.parse.quote(PROMPT)
    try:
        y = requests.get(url, params=params, timeout=180)
        if y.status_code != 200 or len(y.content) < 3000:
            return f"{ad:34s} HATA http={y.status_code} ({len(y.content)} bayt)"
        kaydet(ad, y.content)
        return f"{ad:34s} OK  {olcu(y.content):>10s}  {len(y.content)//1024:>5d} KB"
    except Exception as e:
        return f"{ad:34s} HATA {type(e).__name__}"


def gemini(ad, model):
    anahtar = os.environ.get("GEMINI_IMAGE_API_KEY") or os.environ.get("GEMINI_API_KEY")
    if not anahtar:
        return f"{ad:34s} ATLANDI (anahtar yok)"
    url = f"https://generativelanguage.googleapis.com/v1beta/models/{model}:generateContent"
    govde = {"contents": [{"parts": [{"text": PROMPT}]}],
             "generationConfig": {"responseModalities": ["IMAGE"],
                                  "imageConfig": {"aspectRatio": "9:16"}}}
    try:
        y = requests.post(url, params={"key": anahtar}, json=govde, timeout=180)
        if y.status_code != 200:
            kisa = y.text.replace("\n", " ")[:110]
            return f"{ad:34s} HATA http={y.status_code}  {kisa}"
        import base64
        for p in y.json()["candidates"][0]["content"]["parts"]:
            v = p.get("inlineData") or p.get("inline_data")
            if v and v.get("data"):
                veri = base64.b64decode(v["data"])
                kaydet(ad, veri)
                return f"{ad:34s} OK  {olcu(veri):>10s}  {len(veri)//1024:>5d} KB"
        return f"{ad:34s} HATA görsel dönmedi"
    except Exception as e:
        return f"{ad:34s} HATA {type(e).__name__}: {str(e)[:70]}"


TESTLER = [
    lambda: pollinations("poll-flux-1024x1792", width=1024, height=1792,
                         model="flux", nologo="true", seed=7),
    lambda: pollinations("poll-flux-896x1568", width=896, height=1568,
                         model="flux", nologo="true", seed=7),
    lambda: pollinations("poll-flux-768x1344", width=768, height=1344,
                         model="flux", nologo="true", seed=7),
    lambda: pollinations("poll-turbo-1024x1792", width=1024, height=1792,
                         model="turbo", nologo="true", seed=7),
    lambda: gemini("gemini-3.1-flash-image", "gemini-3.1-flash-image"),
    lambda: gemini("gemini-2.5-flash-image", "gemini-2.5-flash-image"),
    lambda: gemini("gemini-3.1-flash-lite-image", "gemini-3.1-flash-lite-image"),
]

if __name__ == "__main__":
    print("Görsel kaynakları deneniyor (her biri 30-60 sn sürebilir)...\n")
    for t in TESTLER:
        print("  " + t(), flush=True)
    print(f"\nÖrnekler: {CIKTI}")
