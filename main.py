#!/usr/bin/env python3
"""Günlük YouTube Shorts üretim hattı.

  python main.py                  -> üret + yükle
  python main.py --deneme         -> üret, YÜKLEME (yerel test)
  python main.py --devam          -> mevcut senaryo/görselleri yeniden kullan
  python main.py --bolum 7        -> belirli bölüm numarasını zorla
"""
import argparse
import json
import shutil
import sys
from pathlib import Path

import yaml

sys.path.insert(0, str(Path(__file__).resolve().parent))
from src import db, script_gen, tts, images, subtitles, video, align

KOK = Path(__file__).resolve().parent
KESIM_PAYI = 0.12     # sahne geçişi, kelimenin bitiminden bu kadar sonra olsun
BOSLUK = 0.35         # sahneler arası nefes payı (saniye)


def _zamanla(tam_metin, ses_yolu, sure_, cfg):
    """Kelime zamanlarını üret: önce Whisper, olmazsa süreye eşit bölme.

    Sonuç HER ZAMAN tam_metin.split() ile birebir aynı sayıda öğe döner;
    sahne sınırlarını kelime sayısıyla hesaplayabilmemiz buna dayanıyor.
    """
    asr = []
    if cfg["altyazi"].get("senkron", "whisper") == "whisper":
        try:
            asr = align.dinle(ses_yolu, cfg["altyazi"].get("whisper_model", "base"),
                              cfg["seri"]["dil"])
        except Exception as e:
            print(f"      ! Whisper kullanılamadı ({type(e).__name__}: "
                  f"{str(e)[:110]}) — süreye eşit bölünüyor")
    return align.hizala(tam_metin, asr, sure_)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--deneme", action="store_true", help="YouTube'a yükleme")
    ap.add_argument("--devam", action="store_true",
                    help="mevcut senaryo ve görselleri yeniden kullan (kota harcama)")
    ap.add_argument("--bolum", type=int, help="bölüm numarasını zorla")
    ap.add_argument("--config", default=str(KOK / "config.yaml"))
    args = ap.parse_args()

    cfg = yaml.safe_load(open(args.config, encoding="utf-8"))
    seri = cfg["seri"]["ad"]
    kanal = cfg.get("kanal", {})
    bk = cfg.get("bitis_karti", {})

    kon = db.baglan()
    if not db.kanon_listesi(kon, seri):
        db.kanon_ekle(kon, seri, cfg["seri"].get("baslangic_kanonu", []))
    bolum_no = args.bolum or db.sonraki_bolum_no(kon, seri)
    print(f"\n=== {seri} — Bölüm {bolum_no} ===")

    is_dizini = KOK / "cikti" / f"bolum_{bolum_no:04d}"
    senaryo_yolu = is_dizini / "senaryo.json"
    devam = args.devam and senaryo_yolu.exists()
    if not devam:
        if is_dizini.exists():
            shutil.rmtree(is_dizini)
        is_dizini.mkdir(parents=True)

    # ---------------------------------------------------------------- 1) Senaryo
    if devam:
        senaryo = json.loads(senaryo_yolu.read_text(encoding="utf-8"))
        print("[1/6] Mevcut senaryo kullanılıyor (yeni istek gönderilmedi).")
    else:
        print("[1/6] Senaryo yazılıyor...")
        senaryo = script_gen.uret(cfg, bolum_no, db.gecmis(kon, seri),
                                  db.kanon_listesi(kon, seri))
        db.bolum_kaydet(kon, seri, bolum_no, senaryo)
        senaryo_yolu.write_text(json.dumps(senaryo, ensure_ascii=False, indent=2),
                                encoding="utf-8")
    print("      Başlık:", senaryo["baslik"])

    sahneler = senaryo["sahneler"]

    # kapanış cümlesi (her bölümde sıradaki varyant)
    kapanis = None
    if bk.get("aktif") and bk.get("seslendir", True) and bk.get("cumleler"):
        c = bk["cumleler"]
        kapanis = c[(bolum_no - 1) % len(c)].format(
            kanal=kanal.get("ad", ""), handle=kanal.get("handle", ""),
            sonraki=bolum_no + 1)

    # ------------------------------------------------------------ 2) Seslendirme
    # Her sahne AYRI istekle seslendirilir. Tek istekte birleştirmek
    # (kota tasarrufu için denendi) uzun metinlerde modelin anlatımı
    # yarıda bırakmasına yol açıyor: ses dosyası uzun çıkıyor ama
    # ikinci sahneden sonrası sessiz kalıyor. Sahne başına istek hem
    # bunu engelliyor hem de sahne sınırlarını tahmine bırakmıyor.
    print("[2/6] Seslendiriliyor...")
    parcalar = [s["anlatim"].strip() for s in sahneler] + ([kapanis] if kapanis else [])
    ses_yollari, kelimeler, sahne_sinirlari = [], [], []
    imlec, kapanis_bas = 0.0, None

    for i, metin in enumerate(parcalar):
        yol = is_dizini / f"ses_{i:02d}.mp3"
        _, ham = tts.seslendir(metin, cfg, yol)
        d = video.sure(yol)
        sahne_mi = i < len(sahneler)

        if sahne_mi:
            k = align.hizala(metin, ham, d) if ham else _zamanla(metin, yol, d, cfg)
            kelimeler += [{"bas": w["bas"] + imlec, "bit": w["bit"] + imlec,
                           "kelime": w["kelime"]} for w in k]
            sahne_sinirlari.append((imlec, imlec + d))
            print(f"      sahne {i+1}: {d:.1f} sn, {len(k)} kelime")
        else:
            kapanis_bas = imlec
            print(f'      kapanış: "{metin}" ({d:.1f} sn)')

        ses_yollari.append(yol)
        imlec += d + BOSLUK

    ses_yolu = video.sesleri_birlestir(ses_yollari, BOSLUK, is_dizini / "ses.m4a")
    ses_suresi = video.sure(ses_yolu)
    konusma_suresi = sahne_sinirlari[-1][1]
    (is_dizini / "kelimeler.json").write_text(
        json.dumps(kelimeler, ensure_ascii=False), encoding="utf-8")
    print(f"      ses toplam: {ses_suresi:.1f} sn")

    # video, sesin bitiminden sonra bitiş kartı için biraz daha sürsün
    ek_saniye = (1.2 if kapanis else float(bk.get("saniye", 3.2))) if bk.get("aktif") else 0.0

    # -------------------------------------------------------------- 3) Görseller
    print("[3/6] Görseller üretiliyor...")
    gorseller = []
    for i, sahne in enumerate(sahneler):
        yol = is_dizini / f"gorsel_{i:02d}.jpg"
        if devam and yol.exists() and yol.stat().st_size > 5000:
            gorseller.append(yol)
            print(f"      görsel {i+1}/{len(sahneler)} (mevcut)")
            continue
        images.indir(sahne.get("gorsel_prompt") or "a quiet forest scene",
                     cfg, yol, seed=bolum_no * 100 + i,
                     anlatici_var=bool(sahne.get("anlatici_var", True)))
        gorseller.append(yol)
        print(f"      görsel {i+1}/{len(sahneler)}")

    # ---------------------------------------------------------------- 4) Altyazı
    altyazi = None
    if not cfg["altyazi"]["aktif"]:
        print("[4/6] Altyazı kapalı, atlanıyor.")
    elif not video.altyazi_destegi_var():
        print("[4/6] UYARI: ffmpeg'inde libass yok, altyazı BASILAMIYOR.")
        print("       Düzeltmek için:  brew install ffmpeg-full && "
              "brew unlink ffmpeg && brew link --force --overwrite ffmpeg-full")
    else:
        print("[4/6] Altyazı hazırlanıyor...")
        sahne_kelime_sayisi = len(kelimeler)   # kapanışın kelimeleri zaten dahil değil
        bitis = None
        if bk.get("aktif"):
            bitis = {
                "bas": max(0.0, (kapanis_bas or konusma_suresi) - 0.3),
                "bit": ses_suresi + ek_saniye - 0.15,
                "metin": bk.get("metin", "Devamı için TAKİP ET"),
                "alt": (bk.get("alt_metin") or "").format(
                    sonraki=bolum_no + 1, handle=kanal.get("handle", ""),
                    kanal=kanal.get("ad", "")),
            }
        # kapanış cümlesinin kelimeleri altyazıya girmiyor; orada bitiş kartı var
        altyazi = subtitles.uret(
            kelimeler[:sahne_kelime_sayisi], cfg, is_dizini / "altyazi.ass",
            bitis=bitis,
            rozet=(f"{cfg['seri'].get('anlatici_adi', '')} · Bölüm {bolum_no}".strip(" ·")
                   if cfg["video"].get("rozet") else None),
            sure=ses_suresi + ek_saniye,
            kimlik=({"metin": cfg["seri"].get("anlatici_adi", ""),
                     "alt": cfg["seri"].get("anlatici_tanimi", ""),
                     "saniye": cfg["video"].get("kimlik_saniye", 2.6)}
                    if cfg["video"].get("kimlik_karti") and
                    cfg["seri"].get("anlatici_adi") else None))

    # ----------------------------------------------------------------- 5) Montaj
    print("[5/6] Montaj...")
    toplam = ses_suresi + ek_saniye
    kesimler = [min(s + KESIM_PAYI, toplam) for _, s in sahne_sinirlari]
    kesimler[-1] = toplam                      # son kare kapanış boyunca kalsın

    # Her sahne, aynı görselin iki farklı kadrajı olarak kesilir (punch-in):
    # ek görsel maliyeti olmadan görsel ritmi ikiye katlanır.
    punch = bool(cfg["video"].get("punch_in", True))
    en_uzun_kesme = float(cfg["video"].get("en_uzun_kesme", 4.5))
    gecis = float(cfg["video"].get("gecis", 0.0))

    # Kesme planı: (görsel, süre, kadraj, zoom yönü, sahne no)
    # Kural: bir sahnenin kadrajları KADEMELİ ilerler (geniş->orta->yakın)
    # ve zoom yönü sahne boyunca DEĞİŞMEZ. İkisi birden, geçişlerin
    # sekme yerine kamera hareketi gibi okunmasını sağlıyor.
    plan, onceki = [], 0.0
    for i, (g, bit) in enumerate(zip(gorseller, kesimler)):
        uzunluk = max(0.6, bit - onceki)
        parca = max(1, min(3, int(-(-uzunluk // en_uzun_kesme)))) if punch else 1
        # İlk sahne yakından açılıp geriye çekilir (açılış kancası),
        # sonraki sahneler geniş plandan özneye yaklaşır.
        sira = [2, 1, 0] if i == 0 else [0, 1, 2]
        yon = (i % 2 == 1)                      # yön sahne başına değişir
        pay = uzunluk / parca
        for j in range(parca):
            plan.append((g, pay, sira[j % 3], yon, i))
        onceki = bit

    # Geçiş payı: ilk klip hariç her klip `gecis` kadar uzun render edilir,
    # o fazlalığı çapraz geçiş yutar, toplam süre değişmez.
    klipler = []
    for k, (g, sure_, kadraj, ters, _) in enumerate(plan):
        klipler.append(video.sahne_klibi(
            g, sure_ + (gecis if k else 0.0), cfg,
            is_dizini / f"klip_{k:02d}.mp4", ters=ters, kadraj=kadraj))

    print(f"      {len(gorseller)} görsel -> {len(klipler)} kesme "
          f"(~{(kesimler[-1] / max(1, len(klipler))):.1f} sn/kesme)")

    if gecis > 0 and len(klipler) > 1:
        # Aynı görselin kadrajları arasında sade erime (kamera yaklaşıyor hissi),
        # FARKLI görseller arasında hareketli geçiş (yeni sahneye geçildiği belli olsun).
        sahne_gecisleri = cfg["video"].get(
            "sahne_gecisleri", ["smoothleft", "circleopen", "smoothright", "fadegrays"])
        tipler, s_no = [], 0
        for k in range(1, len(plan)):
            if plan[k][4] != plan[k - 1][4]:      # görsel değişiyor
                tipler.append(sahne_gecisleri[s_no % len(sahne_gecisleri)])
                s_no += 1
            else:
                tipler.append("fade")
        print(f"      geçişler yumuşatılıyor ({gecis:.2f} sn) — "
              f"{tipler.count('fade')} erime, {len(tipler) - tipler.count('fade')} hareketli")
        klipler = [video.gecisli_birlestir(
            klipler, [p[1] for p in plan], gecis, is_dizini / "sahneler.mp4",
            tipler=tipler)]
    cikti = video.son_montaj(klipler, ses_yolu, altyazi, cfg,
                             is_dizini / f"bolum_{bolum_no:04d}.mp4", is_dizini,
                             muzik_seed=bolum_no, ek_saniye=ek_saniye)
    print(f"      video: {cikti} ({video.sure(cikti):.1f} sn)")

    # --------------------------------------------------------------- 6) Yükleme
    if args.deneme or not cfg["youtube"]["yukle"]:
        print("[6/6] Deneme modu — yükleme yapılmadı.")
        return
    print("[6/6] YouTube'a yükleniyor...")
    from src import upload
    vid = upload.yukle(cikti, senaryo, cfg)
    db.yayinlandi_isaretle(kon, seri, bolum_no, vid)
    db.kanon_ekle(kon, seri, senaryo.get("yeni_kanon"))
    print(f"      YAYINDA: https://youtube.com/shorts/{vid}")


if __name__ == "__main__":
    main()
