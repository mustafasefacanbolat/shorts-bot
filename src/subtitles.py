"""Kelime zamanlamalarından ASS altyazı üretir (aktif kelime vurgulu)."""

BASLIK = """[Script Info]
ScriptType: v4.00+
PlayResX: {W}
PlayResY: {H}
WrapStyle: 2
ScaledBorderAndShadow: yes

[V4+ Styles]
Format: Name,Fontname,Fontsize,PrimaryColour,SecondaryColour,OutlineColour,BackColour,Bold,Italic,Underline,StrikeOut,ScaleX,ScaleY,Spacing,Angle,BorderStyle,Outline,Shadow,Alignment,MarginL,MarginR,MarginV,Encoding
Style: Ana,{font},{punto},{renk},&H000000FF,&H00000000,&H80000000,-1,0,0,0,100,100,0,0,1,{kenarlik},2,2,80,80,{margin},1
Style: Bitis,{font},{bpunto},{renk},&H000000FF,&H00000000,&H80000000,-1,0,0,0,100,100,2,0,1,{bkenarlik},3,5,60,60,60,1
Style: Kimlik,{font},74,&H00FFFFFF,&H000000FF,&H00000000,&H80000000,-1,0,0,0,100,100,3,0,1,5,3,8,60,60,150,1
Style: KimlikAlt,{font},40,&H00C8E6FF,&H000000FF,&H00000000,&H80000000,-1,0,0,0,100,100,2,0,1,4,2,8,60,60,240,1
Style: Rozet,{font},46,&H00E8E8E8,&H000000FF,&H00000000,&H80000000,-1,0,0,0,100,100,1,0,1,4,2,7,44,44,44,1
Style: BitisAlt,{font},{apunto},&H00C8E6FF,&H000000FF,&H00000000,&H80000000,-1,0,0,0,100,100,1,0,1,{bkenarlik},3,5,60,60,60,1

[Events]
Format: Layer,Start,End,Style,Name,MarginL,MarginR,MarginV,Effect,Text
"""


def _zaman(s):
    s = max(s, 0)
    sa, kalan = divmod(s, 3600)
    dk, sn = divmod(kalan, 60)
    return f"{int(sa)}:{int(dk):02d}:{sn:05.2f}"


def _temizle(k):
    return k.replace("{", "(").replace("}", ")").replace("\\", "")


def uret(kelimeler, cfg, yol, bitis=None, rozet=None, sure=None, kimlik=None):
    a = cfg["altyazi"]
    W, H = cfg["video"]["cozunurluk"]
    bk = cfg.get("bitis_karti", {})
    bpunto = int(bk.get("punto", 96))
    satirlar = [BASLIK.format(
        W=W, H=H, font="DejaVu Sans", punto=a["punto"], renk=a["renk"],
        kenarlik=a["kenarlik"], margin=a["alt_bosluk"],
        bpunto=bpunto, apunto=int(bpunto * 0.55),
        bkenarlik=a["kenarlik"] + 1)]

    n = max(1, int(a["kelime_grubu"]))
    kelimeler = [k for k in kelimeler if k["kelime"].strip()]

    for i in range(0, len(kelimeler), n):
        grup = kelimeler[i:i + n]
        for j, aktif in enumerate(grup):
            bas = aktif["bas"]
            # grubun son kelimesi bir sonraki gruba kadar ekranda kalsın
            if j + 1 < len(grup):
                bit = grup[j + 1]["bas"]
            else:
                sonraki = kelimeler[i + n] if i + n < len(kelimeler) else None
                bit = sonraki["bas"] if sonraki else aktif["bit"] + 0.45
            bit = max(bit, bas + 0.08)

            parcalar = []
            for k, kel in enumerate(grup):
                metin = _temizle(kel["kelime"])
                if k == j:
                    parcalar.append(f"{{\\c{a['vurgu_rengi']}}}{metin}{{\\c{a['renk']}}}")
                else:
                    parcalar.append(metin)
            giris = "{\\fad(60,0)\\fscx88\\fscy88\\t(0,110,\\fscx100\\fscy100)}" if j == 0 else ""
            satirlar.append(
                f"Dialogue: 0,{_zaman(bas)},{_zaman(bit)},Ana,,0,0,0,,{giris}"
                + " ".join(parcalar)
            )

    # --- açılışta kimlik kartı: izleyici anlatıcının kim olduğunu görsün ---
    # Anlatımın ilk 2 saniyesini kancaya bırakıp kimliği EKRANDA veriyoruz;
    # "Merhaba ben Momo" ile açmak izleyiciyi ilk saniyede kaçırır.
    if kimlik:
        k_bit = float(kimlik.get("saniye", 2.6))
        satirlar.append(
            f"Dialogue: 1,{_zaman(0.25)},{_zaman(k_bit)},Kimlik,,0,0,0,,"
            f"{{\\fad(300,450)}}{_temizle(kimlik['metin'])}")
        if kimlik.get("alt"):
            satirlar.append(
                f"Dialogue: 1,{_zaman(0.45)},{_zaman(k_bit)},KimlikAlt,,0,0,0,,"
                f"{{\\fad(350,450)}}{_temizle(kimlik['alt'])}")

    # --- köşede sabit seri işareti: "Momo · Bölüm 4" ---
    if rozet and sure:
        satirlar.append(
            f"Dialogue: 0,{_zaman(0.35)},{_zaman(max(sure - 0.3, 0.5))},Rozet,,0,0,0,,"
            f"{{\\fad(400,300)\\alpha&H50&}}{_temizle(rozet)}")

    # --- bitiş kartı: "Devamı için TAKİP ET" ---
    if bitis:
        b_bas, b_bit = bitis["bas"], bitis["bit"]
        giris = "{\\fad(350,250)}"
        # hafif nabız efekti: dikkat çeker ama rahatsız etmez
        nabiz = ("{\\fscx92\\fscy92\\t(0,260,\\fscx104\\fscy104)"
                 "\\t(260,520,\\fscx100\\fscy100)}")
        satirlar.append(
            f"Dialogue: 1,{_zaman(b_bas)},{_zaman(b_bit)},Bitis,,0,0,0,,"
            f"{{\\pos({W//2},{int(H*0.46)})}}{giris}{nabiz}{_temizle(bitis['metin'])}")
        if bitis.get("alt"):
            satirlar.append(
                f"Dialogue: 1,{_zaman(b_bas + 0.25)},{_zaman(b_bit)},BitisAlt,,0,0,0,,"
                f"{{\\pos({W//2},{int(H*0.53)})}}{giris}{_temizle(bitis['alt'])}")

    with open(yol, "w", encoding="utf-8") as f:
        f.write("\n".join(satirlar) + "\n")
    return str(yol)
