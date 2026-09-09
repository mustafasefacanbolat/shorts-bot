"""Kanala özel, telifsiz ambient fon müziği üretir (numpy + ffmpeg).

Üretilen parçalar tamamen özgündür: hiçbir kayıttan alıntı yoktur,
dolayısıyla YouTube'da telif/ContentID iddiası imkânsızdır.

Kullanım:  python tools/muzik_uret.py
Çıktı:     assets/muzik/*.mp3
"""
import subprocess
import sys
from pathlib import Path

import numpy as np

SR = 44100
KOK = Path(__file__).resolve().parent.parent
CIKTI = KOK / "assets" / "muzik"


def nota(midi):
    return 440.0 * 2 ** ((midi - 69) / 12.0)


def _tek_kutup(x, a):
    """Basit alçak geçiren süzgeç — tizleri yumuşatır, sıcaklık verir."""
    y = np.empty_like(x)
    onceki = 0.0
    for i in range(len(x)):
        onceki += a * (x[i] - onceki)
        y[i] = onceki
    return y


def _yumusak_lowpass(x, a=0.25):
    # vektörel yaklaşım: iki geçiş (ileri) ile IIR'a yakın sonuç, çok daha hızlı
    b = np.copy(x)
    for _ in range(2):
        b = np.convolve(b, np.ones(int(1 / a)) / int(1 / a), mode="same")
    return b


def pad_nota(frekans, sure, seviye=1.0, detune=0.006):
    t = np.linspace(0, sure, int(SR * sure), endpoint=False)
    ses = np.zeros_like(t)
    # hafif akortsuz üç osilatör -> koro etkisi, "tek tuş" hissini kırar
    for k, d in enumerate((-detune, 0.0, detune)):
        f = frekans * (1 + d)
        ses += np.sin(2 * np.pi * f * t + k)
        ses += 0.30 * np.sin(2 * np.pi * 2 * f * t + k)      # 2. harmonik
        ses += 0.14 * np.sin(2 * np.pi * 3 * f * t + k * 2)  # 3. harmonik
    ses /= 3.0
    # yavaş nefes alma (tremolo)
    ses *= 1.0 + 0.07 * np.sin(2 * np.pi * 0.11 * t)
    return ses * seviye


def zarf(n, atak, birak):
    e = np.ones(n)
    a = min(int(atak * SR), n // 2)
    b = min(int(birak * SR), n // 2)
    if a:
        e[:a] = np.linspace(0, 1, a) ** 1.6
    if b:
        e[-b:] = np.linspace(1, 0, b) ** 1.6
    return e


def can(frekans, sure, seviye=0.16):
    """Seyrek çalan yumuşak çan sesi — boşluğu doldurur, dikkat dağıtmaz."""
    t = np.linspace(0, sure, int(SR * sure), endpoint=False)
    s = (np.sin(2 * np.pi * frekans * t)
         + 0.5 * np.sin(2 * np.pi * frekans * 2.01 * t)
         + 0.25 * np.sin(2 * np.pi * frekans * 3.02 * t))
    return s * np.exp(-t * 1.9) * seviye


def yanki(x, gecikmeler=((0.09, 0.26), (0.17, 0.19), (0.31, 0.13), (0.53, 0.08))):
    y = np.copy(x)
    for sn, kazanc in gecikmeler:
        d = int(sn * SR)
        if d < len(x):
            y[d:] += x[:-d] * kazanc
    return y


def parca_uret(akorlar, olcu_sn, tekrar, can_notalari, taban_midi, yol,
                can_arasi=(3.5, 7.0), detune=0.006):
    toplam = int(SR * olcu_sn * len(akorlar) * tekrar)
    mix = np.zeros(toplam + SR * 3)
    imlec = 0
    gecis = 1.6
    for _ in range(tekrar):
        for akor in akorlar:
            n = int(SR * (olcu_sn + gecis))
            blok = np.zeros(n)
            for derece in akor:
                f = nota(taban_midi + derece)
                blok += pad_nota(f, n / SR, seviye=0.9, detune=detune)
                blok += pad_nota(f * 2, n / SR, seviye=0.22, detune=detune)
            blok *= zarf(n, 1.3, 1.8)
            mix[imlec:imlec + n] += blok
            imlec += int(SR * olcu_sn)

    # seyrek çanlar
    rng = np.random.default_rng(abs(hash(yol.name)) % (2 ** 32))
    zaman = 3.0
    while zaman < (toplam / SR) - 4:
        derece = can_notalari[rng.integers(0, len(can_notalari))]
        c = can(nota(taban_midi + 12 + derece), 3.0)
        i = int(zaman * SR)
        mix[i:i + len(c)] += c
        zaman += float(rng.uniform(*can_arasi))

    mix = _yumusak_lowpass(mix, 0.22)
    mix = yanki(mix)
    mix = mix[:toplam]
    mix *= zarf(len(mix), 3.0, 4.0)

    tepe = np.max(np.abs(mix)) or 1.0
    mix = (mix / tepe) * 0.82

    # hafif stereo genişlik
    sag = np.concatenate([np.zeros(int(SR * 0.011)), mix])[:len(mix)]
    stereo = np.stack([mix, 0.55 * mix + 0.45 * sag], axis=1)
    pcm = (np.clip(stereo, -1, 1) * 32767).astype(np.int16).tobytes()

    yol.parent.mkdir(parents=True, exist_ok=True)
    # Konuşmanın bas bölgesini boşalt (150 Hz altı), tizi yumuşat,
    # seviyeyi eşitle: fon müziğinin sesi ezmemesi için standart hazırlık.
    p = subprocess.run(
        ["ffmpeg", "-y", "-v", "error", "-f", "s16le", "-ar", str(SR),
         "-ac", "2", "-i", "pipe:0",
         "-af", "highpass=f=150,highpass=f=150,lowpass=f=7500,"
                "acompressor=threshold=0.15:ratio=3:attack=200:release=800,"
                "loudnorm=I=-23:TP=-3:LRA=7",
         "-c:a", "libmp3lame", "-b:a", "192k",
         str(yol)], input=pcm, capture_output=True)
    if p.returncode != 0:
        sys.exit("ffmpeg hatası: " + p.stderr.decode()[-400:])
    rms = float(np.sqrt(np.mean(mix ** 2)))
    print(f"  {yol.name}  {len(mix)/SR:.0f} sn  RMS {20*np.log10(rms+1e-9):.1f} dBFS")


# (dosya, akorlar, ölçü sn, tekrar, çan notaları, taban midi, çan aralığı, detune)
PARCALAR = [
    ("01-hatira.mp3", [[0, 3, 7], [-4, 0, 5], [-9, -5, 0], [-2, 2, 7]], 8.0, 4,
     [0, 3, 7, 10], 57, (3.5, 7.0), 0.006),        # nostaljik, minör
    ("02-orman-sabahi.mp3", [[0, 4, 7], [-5, 0, 4], [-3, 2, 5], [-7, -3, 0]], 7.0, 4,
     [0, 4, 7, 9], 60, (3.0, 6.0), 0.005),         # ılık, umutlu
    ("03-gece.mp3", [[0, 3, 7], [-2, 3, 5], [-5, 0, 3], [-7, -2, 2]], 9.0, 3,
     [0, 3, 5, 10], 53, (5.0, 9.0), 0.008),        # koyu, geniş, seyrek
    ("04-yagmur.mp3", [[0, 3, 7], [-3, 0, 5], [-5, -1, 2], [-7, -4, 0]], 8.5, 3,
     [0, 3, 5, 7], 55, (4.0, 8.0), 0.009),         # ıslak, dingin
    ("05-kesif.mp3", [[0, 4, 7], [2, 5, 9], [-3, 0, 4], [-5, -1, 2]], 6.0, 5,
     [0, 2, 4, 7, 11], 62, (2.5, 5.0), 0.004),     # parlak, hareketli
    ("06-veda.mp3", [[0, 3, 7], [-4, 0, 3], [-5, -2, 3], [-9, -5, -2]], 9.5, 3,
     [0, 3, 7, 8], 52, (5.5, 10.0), 0.007),        # hüzünlü, ağır
    ("07-guven.mp3", [[0, 4, 7], [-7, -3, 0], [-5, 0, 4], [-2, 2, 5]], 7.5, 4,
     [0, 4, 7, 12], 58, (3.5, 7.0), 0.005),        # sıcak, güven veren
    ("08-macera.mp3", [[0, 3, 7], [-2, 2, 5], [3, 7, 10], [0, 5, 8]], 5.5, 5,
     [0, 3, 5, 7, 10], 59, (2.0, 4.5), 0.006),     # tempolu, merak uyandıran
    ("09-huzun.mp3", [[0, 3, 7], [-5, -2, 2], [-4, 0, 3], [-7, -4, 0]], 10.0, 3,
     [0, 3, 8, 10], 54, (6.0, 11.0), 0.010),       # ağır melankoli
    ("10-safak.mp3", [[0, 4, 7], [-3, 2, 5], [-5, 0, 4], [-8, -4, -1]], 8.0, 4,
     [0, 2, 7, 9], 61, (3.0, 6.5), 0.004),         # ferah, aydınlık
]

if __name__ == "__main__":
    print("Özgün fon müzikleri üretiliyor...")
    for ad, akorlar, olcu, tekrar, canlar, taban, can_ara, det in PARCALAR:
        parca_uret(akorlar, olcu, tekrar, canlar, taban, CIKTI / ad,
                   can_arasi=can_ara, detune=det)
    print(f"Bitti -> {CIKTI}")
