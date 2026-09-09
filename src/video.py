"""ffmpeg montaj hattı: görseller + seslendirme + altyazı + müzik -> dikey Short."""
import os
import random
import re
import subprocess
from pathlib import Path


def _calistir(args, cwd=None):
    s = subprocess.run(args, capture_output=True, text=True, cwd=cwd)
    if s.returncode != 0:
        raise RuntimeError("ffmpeg hatası:\n" + s.stderr[-2500:])
    return s


def altyazi_destegi_var():
    """ffmpeg libass ile derlenmiş mi? (Homebrew'un 'lite' sürümünde değil.)"""
    try:
        c = subprocess.run(["ffmpeg", "-hide_banner", "-filters"],
                           capture_output=True, text=True, timeout=30).stdout
    except Exception:
        return False
    return re.search(r"^\s*[A-Z.]+\s+ass\s", c, re.M) is not None


MUZIK_UZANTILARI = (".mp3", ".m4a", ".wav", ".aac", ".ogg", ".flac")


def muzik_sec(cfg, seed=None):
    """config'deki 'muzik' tek dosya da olabilir klasör de.
    Klasörse her bölümde farklı parça seçilir (tek düzelik kırılır)."""
    yol = (cfg["video"].get("muzik") or "").strip()
    if not yol:
        return None
    p = Path(yol)
    if not p.is_absolute():
        p = Path(__file__).resolve().parent.parent / p
    if p.is_dir():
        parcalar = sorted(f for f in p.iterdir()
                          if f.suffix.lower() in MUZIK_UZANTILARI)
        if not parcalar:
            return None
        # bölüm numarasına göre sırayla dön: art arda aynı parça gelmesin
        return str(parcalar[(seed or 0) % len(parcalar)])
    return str(p) if p.exists() else None


def sure(yol):
    s = subprocess.run(
        ["ffprobe", "-v", "error", "-show_entries", "format=duration",
         "-of", "default=nw=1:nk=1", str(yol)],
        capture_output=True, text=True, check=True)
    return float(s.stdout.strip())


# Aynı görselden çıkarılan kadrajlar: (zoom başlangıç, zoom bitiş, odak x, odak y)
# Tek bir fotoğraftan üç ayrı "çekim" üretir; ek görsel maliyeti yoktur.
# Kadrajlar KADEMELİ: geniş -> orta -> yakın. Her kadrajın bitiş zoom'u
# bir sonrakinin başlangıcına yakın; böylece geçiş "sekme" değil
# "kameranın yaklaşması" gibi okunur.
KADRAJLAR = [
    (1.00, 1.14, 0.50, 0.50),   # 0 - geniş
    (1.14, 1.30, 0.53, 0.45),   # 1 - orta, hafif yukarı kayarak
    (1.30, 1.48, 0.50, 0.38),   # 2 - yakın, özneye
]


def sahne_klibi(gorsel, saniye, cfg, cikti, ters=False, kadraj=0):
    """Tek görselden, seçilen kadrajla klip üretir.

    ters=True kliplerin zoom yönünü çevirir. ÖNEMLİ: bir sahnenin
    kadrajları arasında yön DEĞİŞMEMELİ; yön değişirse geçiş
    yumuşama yerine sekme gibi görünür.
    """
    W, H = cfg["video"]["cozunurluk"]
    fps = cfg["video"]["fps"]
    hiz = cfg["video"]["zoom_hizi"]
    kare = max(2, int(round(saniye * fps)))
    bas, bit, ox, oy = KADRAJLAR[kadraj % len(KADRAJLAR)]
    zoom = (f"max({bit}-{hiz}*on,{bas})" if ters else f"min({bas}+{hiz}*on,{bit})")
    odak_x = f"iw*{ox}-(iw/zoom/2)"
    odak_y = f"ih*{oy}-(ih/zoom/2)"
    vf = (
        f"scale={W*2}:{H*2}:force_original_aspect_ratio=increase,"
        f"crop={W*2}:{H*2},"
        f"zoompan=z='{zoom}':x='{odak_x}':y='{odak_y}':"
        f"d={kare}:s={W}x{H}:fps={fps},"
        f"unsharp=5:5:0.4:3:3:0.2,"
        f"format=yuv420p"
    )
    _calistir(["ffmpeg", "-y", "-v", "error", "-loop", "1", "-i", str(gorsel),
               "-t", f"{saniye:.3f}", "-vf", vf, "-r", str(fps),
               "-c:v", "libx264", "-preset", "veryfast", "-crf", "20",
               "-pix_fmt", "yuv420p", str(cikti)])
    return str(cikti)


def gecisli_birlestir(klipler, planlanan, gecis, cikti, tipler=None):
    """Klipleri aralarına çapraz geçiş (dissolve) koyarak tek videoya birleştirir.

    Sert kesme yerine yumuşak geçiş: her klibin sonu bir sonrakinin başıyla
    `gecis` saniye boyunca karışır. Klipler bu payı karşılamak için zaten
    uzun render edilmiştir, bu yüzden toplam süre değişmez.
    """
    if len(klipler) == 1:
        return str(klipler[0])

    girisler, zincir, onceki = [], [], "[0:v]"
    for i, k in enumerate(klipler):
        girisler += ["-i", str(k)]

    imlec = 0.0
    for i in range(1, len(klipler)):
        imlec += planlanan[i - 1]
        cikis = f"[v{i}]" if i < len(klipler) - 1 else "[out]"
        tip = (tipler[i - 1] if tipler and i - 1 < len(tipler) else "fade")
        zincir.append(
            f"{onceki}[{i}:v]xfade=transition={tip}:duration={gecis:.3f}:"
            f"offset={max(imlec - gecis, 0):.3f}{cikis}")
        onceki = cikis

    _calistir(["ffmpeg", "-y", "-v", "error", *girisler,
               "-filter_complex", ";".join(zincir), "-map", "[out]",
               "-c:v", "libx264", "-preset", "veryfast", "-crf", "19",
               "-pix_fmt", "yuv420p", str(cikti)])
    return str(cikti)


def sesleri_birlestir(ses_yollari, bosluk, cikti):
    """Sahne seslerini aralarına sessizlik koyarak birleştirir."""
    girisler, zincir = [], []
    for i, y in enumerate(ses_yollari):
        girisler += ["-i", str(y)]
        zincir.append(f"[{i}:a]aresample=44100,apad=pad_dur={bosluk}[a{i}]")
    zincir.append("".join(f"[a{i}]" for i in range(len(ses_yollari)))
                  + f"concat=n={len(ses_yollari)}:v=0:a=1[out]")
    _calistir(["ffmpeg", "-y", "-v", "error", *girisler,
               "-filter_complex", ";".join(zincir), "-map", "[out]",
               "-c:a", "aac", "-b:a", "192k", str(cikti)])
    return str(cikti)


def son_montaj(klipler, ses, altyazi, cfg, cikti, is_dizini,
               muzik_seed=None, ek_saniye=0.0):
    liste = Path(is_dizini) / "klipler.txt"
    liste.write_text("".join(f"file '{os.path.abspath(k)}'\n" for k in klipler))

    toplam = sure(ses) + max(0.0, ek_saniye)
    muzik = muzik_sec(cfg, seed=muzik_seed)
    muzik_var = bool(muzik)
    if muzik_var:
        print(f"      müzik: {Path(muzik).name}")

    ortam = cfg["video"].get("ortam_sesi")
    if ortam:
        oy = Path(ortam)
        if not oy.is_absolute():
            oy = Path(__file__).resolve().parent.parent / oy
        ortam = str(oy) if oy.exists() else None

    girisler = ["-f", "concat", "-safe", "0", "-i", str(liste.resolve()),
                "-i", str(Path(ses).resolve())]
    idx = 2
    muzik_i = ortam_i = None
    if muzik_var:
        girisler += ["-stream_loop", "-1", "-i", str(Path(muzik).resolve())]
        muzik_i = idx; idx += 1
    if ortam:
        girisler += ["-stream_loop", "-1", "-i", ortam]
        ortam_i = idx; idx += 1
        print(f"      ortam sesi: {Path(ortam).name}")

    # ffmpeg'in ass filtresi yol içindeki özel karakterlerde boğuluyor.
    # Çözüm: ffmpeg'i iş dizininde çalıştırıp altyazıyı sade dosya adıyla vermek.
    fade = f"fade=t=in:st=0:d=0.4,fade=t=out:st={max(toplam - 0.5, 0):.2f}:d=0.5"
    if altyazi:
        v_zincir = f"[0:v]ass=filename={Path(altyazi).name},{fade}[v]"
    else:
        v_zincir = f"[0:v]{fade}[v]"

    # --- ses zinciri: konuşma + (ducking'li) müzik + sabit ortam sesi ---
    duck = cfg["video"].get("muzik_kisilsin", True)
    parcalar, karisim = [], []

    if muzik_var and duck:
        parcalar.append(f"[1:a]aresample=44100,apad=whole_dur={toplam:.3f},"
                        f"asplit=2[konusma][tetik]")
    else:
        parcalar.append(f"[1:a]aresample=44100,apad=whole_dur={toplam:.3f}[konusma]")
    karisim.append("[konusma]")

    if muzik_var:
        seviye = cfg["video"]["muzik_seviyesi"]
        parcalar.append(
            f"[{muzik_i}:a]atrim=0:{toplam:.3f},asetpts=N/SR/TB,aresample=44100,"
            f"volume={seviye},afade=t=in:st=0:d=1.5,"
            f"afade=t=out:st={max(toplam - 2.5, 0):.2f}:d=2.5[m]")
        if duck:
            parcalar.append("[m][tetik]sidechaincompress=threshold=0.02:ratio=12:"
                            "attack=15:release=500:makeup=1[mduck]")
            karisim.append("[mduck]")
        else:
            karisim.append("[m]")

    if ortam_i is not None:
        # Ortam sesi kısılmaz: konuşmanın altında sabit doku olarak durur.
        oseviye = cfg["video"].get("ortam_seviyesi", 1.0)
        parcalar.append(
            f"[{ortam_i}:a]atrim=0:{toplam:.3f},asetpts=N/SR/TB,aresample=44100,"
            f"volume={oseviye},afade=t=in:st=0:d=2,"
            f"afade=t=out:st={max(toplam - 2, 0):.2f}:d=2[amb]")
        karisim.append("[amb]")

    parcalar.append("".join(karisim) +
                    f"amix=inputs={len(karisim)}:duration=first:normalize=0[a]")
    a_zincir = ";".join(parcalar)

    _calistir(["ffmpeg", "-y", "-v", "error", *girisler,
               "-filter_complex", f"{v_zincir};{a_zincir}",
               "-map", "[v]", "-map", "[a]",
               "-c:v", "libx264", "-preset", "medium", "-crf", "21",
               "-profile:v", "high", "-pix_fmt", "yuv420p",
               "-c:a", "aac", "-b:a", "192k", "-movflags", "+faststart",
               "-t", f"{toplam:.3f}", str(Path(cikti).resolve())],
              cwd=str(is_dizini))
    return str(cikti)
