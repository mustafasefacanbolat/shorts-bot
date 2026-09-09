"""Orman ortam sesi üretir (rüzgâr + yaprak hışırtısı + seyrek uzak ötüş).

Tamamen sentezlenmiştir: telif riski yoktur, hiçbir kayıttan alıntı değildir.
Kullanım:  python tools/ortam_uret.py   ->  assets/ortam/orman.mp3
"""
import subprocess
import sys
from pathlib import Path

import numpy as np

SR = 44100
SURE = 180.0
KOK = Path(__file__).resolve().parent.parent
YOL = KOK / "assets" / "ortam" / "orman.mp3"


def bant_gecir(x, alt, ust):
    """FFT ile bant geçiren süzgeç — yaprak dokusunu belirleyen şey bu."""
    S = np.fft.rfft(x)
    f = np.fft.rfftfreq(len(x), 1 / SR)
    maske = np.clip((f - alt) / max(alt, 1), 0, 1) * np.clip((ust - f) / ust, 0, 1)
    return np.fft.irfft(S * maske, n=len(x))


def ruzgar(n, rng):
    """Pembe gürültü + yavaş nefes: uzaktan gelen rüzgâr."""
    beyaz = rng.standard_normal(n)
    S = np.fft.rfft(beyaz)
    f = np.fft.rfftfreq(n, 1 / SR)
    S /= np.sqrt(np.maximum(f, 1.0))           # pembeleştir
    x = np.fft.irfft(S, n=n)
    t = np.arange(n) / SR
    nefes = (1.0
             + 0.45 * np.sin(2 * np.pi * 0.037 * t)
             + 0.30 * np.sin(2 * np.pi * 0.061 * t + 1.3)
             + 0.18 * np.sin(2 * np.pi * 0.013 * t + 2.7))
    return bant_gecir(x, 260, 5200) * nefes


def hisirti(n, rng):
    """Kısa, seyrek yaprak kıpırtıları."""
    y = np.zeros(n)
    t_im = 0.7
    while t_im < SURE - 1:
        d = float(rng.uniform(0.25, 0.9))
        m = int(d * SR)
        parca = bant_gecir(rng.standard_normal(m), 1800, 9000)
        parca *= np.hanning(m) * float(rng.uniform(0.25, 0.7))
        i = int(t_im * SR)
        y[i:i + m] += parca[:len(y) - i]
        t_im += float(rng.uniform(1.1, 4.0))
    return y


def otus(n, rng):
    """Çok uzakta, çok seyrek kuş ötüşü — doku olarak duyulur, öne çıkmaz."""
    y = np.zeros(n)
    t_im = float(rng.uniform(6, 14))
    while t_im < SURE - 3:
        nota = float(rng.uniform(2100, 3600))
        d = float(rng.uniform(0.08, 0.16))
        m = int(d * SR)
        tt = np.arange(m) / SR
        kayma = np.linspace(1.0, float(rng.uniform(0.88, 1.15)), m)
        ses = np.sin(2 * np.pi * nota * kayma * tt)
        ses *= np.exp(-tt * 14) * 0.055
        i = int(t_im * SR)
        y[i:i + m] += ses[:len(y) - i]
        if rng.random() < 0.55:                 # bazen iki kez öter
            i2 = i + int(0.22 * SR)
            y[i2:i2 + m] += ses[:len(y) - i2] * 0.8
        t_im += float(rng.uniform(7, 20))
    return y


def main():
    n = int(SR * SURE)
    rng = np.random.default_rng(20260909)
    mix = ruzgar(n, rng) / 1.8 + 0.16 * hisirti(n, rng) + otus(n, rng)

    tepe = np.max(np.abs(mix)) or 1.0
    mix = mix / tepe * 0.7
    kenar = int(SR * 2)
    mix[:kenar] *= np.linspace(0, 1, kenar)
    mix[-kenar:] *= np.linspace(1, 0, kenar)

    sag = np.concatenate([np.zeros(int(SR * 0.017)), mix])[:len(mix)]
    stereo = np.stack([mix, 0.5 * mix + 0.5 * sag], axis=1)
    pcm = (np.clip(stereo, -1, 1) * 32767).astype(np.int16).tobytes()

    YOL.parent.mkdir(parents=True, exist_ok=True)
    p = subprocess.run(
        ["ffmpeg", "-y", "-v", "error", "-f", "s16le", "-ar", str(SR), "-ac", "2",
         "-i", "pipe:0", "-af", "highpass=f=170,lowpass=f=6500,loudnorm=I=-29:TP=-6",
         "-c:a", "libmp3lame", "-b:a", "160k", str(YOL)],
        input=pcm, capture_output=True)
    if p.returncode != 0:
        sys.exit("ffmpeg: " + p.stderr.decode()[-300:])
    print(f"  {YOL.name}  {SURE:.0f} sn")


if __name__ == "__main__":
    main()
