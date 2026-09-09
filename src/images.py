"""Sahne görselleri.

Sıralama: Gemini görsel modeli (en gerçekçi) -> Pollinations (yedek)
-> degrade arka plan (internet yoksa üretim yine durmaz).
"""
import base64
import os
import random
import subprocess
import time
import urllib.parse

import requests

POLL = "https://image.pollinations.ai/prompt/{p}"
GEMINI_IMG = ("https://generativelanguage.googleapis.com/v1beta/"
              "models/{model}:generateContent")
GECICI = {429, 500, 502, 503, 504}

# Fotoğrafik gerçekçilik için her prompta eklenen teknik tarif
KALITE = ("photorealistic, shot on 85mm lens, f/1.8, natural light, "
          "high dynamic range, sharp focus on subject, realistic fur and skin "
          "texture, subtle depth of field, no text, no watermark, no logo")


def _tam_prompt(prompt, cfg, anlatici_var=True):
    """Sahne tarifi + (varsa) sabit karakter tarifi + seri stili + teknik kalite.

    Karakter tarifini biz ekliyoruz ki Momo her karede aynı görünsün;
    senaryo modeline görünüş tarif ettirmiyoruz (her seferinde başka yazıyor).
    """
    seri = cfg.get("seri", {})
    parcalar = [prompt]
    if anlatici_var and seri.get("karakter_gorunumu"):
        parcalar.append(seri["karakter_gorunumu"])
    parcalar.append(seri.get("gorsel_stil", ""))
    parcalar.append(KALITE)
    return ". ".join(" ".join(x.split()).rstrip(".")
                     for x in parcalar if x and x.strip())


# ------------------------------------------------------------------ Gemini
def _gemini(prompt, cfg, yol, deneme_sayisi=2):
    model = cfg["gorsel_uretimi"].get("gemini_model", "gemini-3.1-flash-image")
    govde = {
        "contents": [{"parts": [{"text": prompt}]}],
        "generationConfig": {
            "responseModalities": ["IMAGE"],
            "imageConfig": {"aspectRatio": "9:16",
                            "imageSize": cfg["gorsel_uretimi"].get("boyut", "1K")},
        },
    }
    url = GEMINI_IMG.format(model=model)
    # Görseller için ayrı (faturalı) anahtar varsa onu kullan; böylece
    # metin ve seslendirme ücretsiz katmanda kalmaya devam eder.
    anahtar = os.environ.get("GEMINI_IMAGE_API_KEY") or os.environ["GEMINI_API_KEY"]
    for deneme in range(deneme_sayisi):
        y = requests.post(url, params={"key": anahtar},
                          json=govde, timeout=240)
        if y.status_code == 400 and ("imageConfig" in y.text or "imageSize" in y.text):
            # bu model en/boy ayarını desteklemiyorsa ayarsız dene
            govde["generationConfig"].pop("imageConfig", None)
            continue
        if y.status_code in GECICI:
            time.sleep(4 * (deneme + 1))
            continue
        if y.status_code != 200:
            raise RuntimeError(f"Gemini görsel {y.status_code}: {y.text[:200]}")
        for p in y.json()["candidates"][0]["content"]["parts"]:
            veri = p.get("inlineData") or p.get("inline_data")
            if veri and veri.get("data"):
                with open(yol, "wb") as f:
                    f.write(base64.b64decode(veri["data"]))
                return str(yol)
        raise RuntimeError("Gemini görsel döndürmedi")
    raise RuntimeError("Gemini görsel: sunucu meşgul")


# ------------------------------------------------------------ Pollinations
def _pollinations(prompt, cfg, yol, seed):
    g = cfg["gorsel_uretimi"]
    en, boy = g.get("genislik", 896), g.get("yukseklik", 1568)
    y = requests.get(POLL.format(p=urllib.parse.quote(prompt[:1600])), params={
        "width": en, "height": boy, "model": g.get("model", "flux"),
        "nologo": "true", "seed": seed, "safe": "true", "enhance": "true",
    }, timeout=240)
    y.raise_for_status()
    if not y.content or len(y.content) < 5000:
        raise RuntimeError("Pollinations boş yanıt")
    with open(yol, "wb") as f:
        f.write(y.content)
    return str(yol)


# ------------------------------------------------------------------ yedek
def _yerel(cfg, yol, seed):
    en, boy = 1080, 1920
    rnd = random.Random(seed)
    r, g, b = (rnd.randint(20, 90) for _ in range(3))
    subprocess.run([
        "ffmpeg", "-y", "-v", "error", "-f", "lavfi", "-i",
        f"gradients=s={en}x{boy}:c0=0x{r:02x}{g:02x}{b:02x}:"
        f"c1=0x{min(r+70,255):02x}{min(g+55,255):02x}{min(b+40,255):02x}:"
        f"x0=0:y0=0:x1={en}:y1={boy}:d=1",
        "-frames:v", "1", str(yol)], check=True)
    return str(yol)


def indir(prompt, cfg, yol, seed, anlatici_var=True):
    tam = _tam_prompt(prompt, cfg, anlatici_var)
    saglayici = cfg["gorsel_uretimi"].get("saglayici", "gemini")

    sira = {
        "gemini": [lambda: _gemini(tam, cfg, yol),
                   lambda: _pollinations(tam, cfg, yol, seed)],
        "pollinations": [lambda: _pollinations(tam, cfg, yol, seed),
                         lambda: _gemini(tam, cfg, yol)],
        "yerel": [],
    }.get(saglayici, [])

    for deneme in sira:
        try:
            return deneme()
        except Exception as e:
            print(f"    ! görsel: {type(e).__name__}: {str(e)[:130]}")
    print("    ! degrade arka plana düşülüyor")
    return _yerel(cfg, yol, seed)
