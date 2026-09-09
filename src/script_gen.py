"""Senaryo motoru — bölümün metnini, başlığını ve açıklamasını üretir.

Ücretsiz sağlayıcılar:
  gemini -> Google AI Studio anahtarı (kart istemez)
  groq   -> Groq Cloud anahtarı (kart istemez)
"""
import json
import os
import random
import re
import time
import requests

GEMINI_URL = "https://generativelanguage.googleapis.com/v1beta/models/{model}:generateContent"
GROQ_URL = "https://api.groq.com/openai/v1/chat/completions"

SISTEM = """Sen kısa dikey video (YouTube Shorts) serileri yazan bir senaristsin.
Türkçe yazıyorsun. Sadece geçerli JSON döndür, başka hiçbir şey yazma.

TON VE MİZAH
- Anlatıcı geçmişteki haliyle dalga geçer: kendi beceriksizliğini, korkaklığını,
  gururunu komik bulur. Mizah SICAK ve kendine dönüktür; kimseyi aşağılamaz.
- Her bölümde en az 2 gülümsetme anı olsun: beklenmedik bir itiraf, abartılı
  bir benzetme, ya da ciddi bir cümlenin arkasından gelen kuru bir tespit.
- Şaka için hikayeyi bozma. Önce olay, sonra espri. Espriyi açıklama.
- Örnek ton: "O gün ormanın en cesur maymunu olacaktım. Üç dal sonra
  ormanın en yüksek sesle bağıran maymunu oldum."

KİMLİK
- Anlatıcı kendini ASLA tanıtarak açmaz ("Ben ...", "Merhaba" yasak, ilk kural).
- Ama en geç İKİNCİ SAHNEDE, hikâyenin İÇİNDE adı doğal olarak geçmeli:
  başkası ona seslenir, kendi adını anarak kendine kızar, ya da bir anıyı
  "o zamanlar bana ... derlerdi" diye açar. Zorlama tanıtım değil, akış içinde.
- Yeni izleyici, ikinci sahnenin sonunda anlatıcının kim olduğunu anlamış olmalı.

YAPI (her bölüm bunu izler)
- SAHNE 1: kanca — bir soru ya da itiraf, cevabı verilmez.
- ORTA SAHNELER: olay büyür, bir aksilik çıkar, gerilim artar.
- SONDAN BİR ÖNCEKİ: olay çözülür ya da beklenmedik biter (esprinin yeri burası).
- SON SAHNE: yeni bir kapı aralar, bir sonraki bölüme merak bırakır.

METİN KURALLARI
- Metin KONUŞMA metnidir, seslendirilecek. Sahne yönergesi, emoji, madde işareti,
  yıldız, tırnak içinde diyalog kullanma.
- Anlatıcı kendi ağzından konuşur. Diğer canlılar konuşmaz.
- Her sahne akıcı olsun; sesli okunduğunda doğal dursun.

İLK 2 SANİYE (en kritik kural)
- Birinci sahnenin İLK CÜMLESİ en fazla 12 kelime olsun ve olayın ORTASINDAN başlasın:
  bir itiraf, bir soru, ya da tuhaf bir tespit. Sahne kurma, açıklama yapma.
- Şunlarla BAŞLAMAK YASAK: "Merhaba", "Ben ...", "Bugün size", "Yıllar önce",
  "Hiç unutmam", "Size bir hikaye". Bunlar izleyiciyi ilk saniyede kaçırır.
- İyi açılış örnekleri: "O dala bir daha hiç çıkmadım." /
  "Ormanın en aptal maymunu bendim, kanıtlayayım." /
  "Kimseye söylemediğim bir şey var."

BAŞLIK (dikkat: burada en çok hata yapılıyor)
- 35-55 karakter. Sonunda " | Bölüm N".
- EN ÖNEMLİ KURAL: başlık olayı ÖZETLEMEZ, cevaplanmamış bir soru bırakır.
  Videoda ne olduğunu söylersen izleyicinin izlemeye sebebi kalmaz.
- Testi şu: başlığı okuyan biri "e sonra ne oldu?" diye soruyorsa doğru;
  "tamam anladım" diyorsa yanlış.
- Bir cümle kur, bir şeyi eksik bırak. Genelde en iyisi son sahnedeki
  cevapsız andan çıkar, olayın tamamından değil.

  YANLIŞ (olayı anlatıyor, merak bırakmıyor):
    "Güneşi Yakalamak İsterken Kovuğa Düşmek"
    "Ormanın En Çılgın Günü"
    "Momo'nun Ağaçtan Düşüşü"
  DOĞRU (eksik bırakıyor):
    "Kovuğun karanlığında biri vardı"
    "O dala bir daha hiç çıkmadım"
    "Kimseye anlatmadığım bir şey var"
    "Kardeşim bağırdı, ben duymadım"

- YASAK: büyük harfle bağırma, "İNANILMAZ", "ŞOK", "asla tahmin edemezsiniz",
  başlıkta emoji, "Ormanın En ... Günü" kalıbı, ve başlığın sonunu
  "...Düşmek / ...Kaçmak" gibi mastarla bitirmek (kuru ve özet gibi durur).

AÇIKLAMA
- İlk cümle akışta görünen tek satırdır: hikâyeden merak uyandıran bir cümle olsun,
  özet olmasın.

SABİT YORUM
- Videonun altına sabitlenecek TEK cümlelik bir soru yaz. Bu soru izleyiciyi
  yorum yazmaya itmeli: cevabı videoda verilmemiş, tahmin gerektiren bir şey olsun.
- "Nasıl buldunuz?" gibi genel sorular yasak. Hikâyeye özgü olsun.
- İyi örnek: "Sizce o dalın ucundaki iz kimindi?"

GÖRSEL PROMPT (İngilizce)
- EN ÖNEMLİ KURAL: prompt, O SAHNEDE ANLATILAN OLAYI göstermeli.
  Anlatımda ne oluyorsa görselde tam olarak o görünmeli — genel orman manzarası
  değil, o anki eylem. Anlatım "dala tırmandım" diyorsa görselde tırmanma olmalı.
- Fotoğraf tarifi gibi yaz: özne + ne yaptığı + ortam + günün saati + ışık + kamera açısı.
- Anlatıcının GÖRÜNÜŞÜNÜ TARİF ETME (kürk rengi, göz rengi, yaş vb.) — o ayrıca ekleniyor.
  Sadece ne yaptığını ve nerede olduğunu yaz.
- Birinci sahnenin görseli YAKIN PLAN olsun (yüz, el, göz) — uzak manzara ilk kareyi öldürür.
- İçinde yazı, metin, logo, filigran isteme.
"""

SEMA_ACIKLAMA = """{
  "baslik": "string",
  "aciklama": "2-3 cümlelik açıklama",
  "etiketler": ["8-12 adet kısa etiket"],
  "sahneler": [{"anlatim": "seslendirilecek cümle(ler)",
                "gorsel_prompt": "english image prompt",
                "anlatici_var": true}],
  "ozet": "bu bölümde ne oldu, 1-2 cümle (sonraki bölümlerin hafızası için)",
  "aciklama_kanca": "akışta görünecek tek satırlık merak cümlesi",
  "sabit_yorum": "izleyiciye sorulacak tek cümlelik soru (yoruma sabitlenecek)",
  "yeni_kanon": ["seride kalıcı hale gelen yeni olgular, 0-3 adet"]
  // anlatici_var: o karede anlatıcı görünüyor mu (manzara/detay karesiyse false)
}"""


def _istem(cfg, bolum_no, gecmis, kanon):
    seri = cfg["seri"]
    v = cfg["video"]
    gecmis_metni = "\n".join(
        f"  Bölüm {g['bolum_no']}: {g['baslik']} — {g['ozet']}" for g in gecmis
    ) or "  (Bu ilk bölüm.)"
    kanon_metni = "\n".join(f"  - {k}" for k in kanon) or "  (henüz yok)"
    kelime = int(v["hedef_saniye"] * v.get("kelime_hizi", 1.7))
    sahne_kelime = max(8, round(kelime / max(1, v["sahne_sayisi"])))

    return f"""SERİ KONSEPTİ:
{seri['konsept']}

SERİDE KESİNLEŞMİŞ OLGULAR (bunlarla çelişme):
{kanon_metni}

ÖNCEKİ BÖLÜMLER:
{gecmis_metni}

GÖREV: Bölüm {bolum_no}'i yaz.
- Tam {v['sahne_sayisi']} sahne olsun.
- HER SAHNE yaklaşık {sahne_kelime} kelime olsun; toplam {kelime} kelimeye yakın dur.
  Bu uzunluk önemli: daha kısa yazarsan video hedeflenen {v['hedef_saniye']} saniyeyi tutmaz.
- Önceki bölümlere kısa bir gönderme yap ama yeni izleyici de anlasın.

Şu JSON şemasında döndür:
{SEMA_ACIKLAMA}"""


def _json_ayikla(metin):
    metin = re.sub(r"^```(?:json)?|```$", "", metin.strip(), flags=re.M).strip()
    ilk, son = metin.find("{"), metin.rfind("}")
    if ilk == -1 or son == -1:
        raise ValueError(f"Modelden JSON gelmedi:\n{metin[:400]}")
    return json.loads(metin[ilk:son + 1])


class GeciciHata(Exception):
    """Sunucu yoğun / kota anlık doldu — beklenip tekrar denenebilir."""


# Ana model cevap vermezse sırayla bunlar denenir
YEDEK_MODELLER = [
    "gemini-flash-latest",
    "gemini-flash-lite-latest",
    "gemini-3.1-flash-lite",
    "gemini-3-flash-preview",
]
GECICI_KODLAR = {429, 500, 502, 503, 504}


def _gemini(model, istem):
    anahtar = os.environ["GEMINI_API_KEY"]
    y = requests.post(
        GEMINI_URL.format(model=model),
        params={"key": anahtar},
        json={
            "systemInstruction": {"parts": [{"text": SISTEM}]},
            "contents": [{"role": "user", "parts": [{"text": istem}]}],
            "generationConfig": {"temperature": 1.0, "responseMimeType": "application/json"},
        },
        timeout=180,
    )
    if y.status_code in GECICI_KODLAR:
        raise GeciciHata(f"Gemini {y.status_code}")
    if y.status_code != 200:
        raise RuntimeError(f"Gemini hatası {y.status_code}: {y.text[:500]}")
    try:
        return y.json()["candidates"][0]["content"]["parts"][0]["text"]
    except (KeyError, IndexError):
        raise GeciciHata("Gemini boş yanıt döndü")


def _groq(model, istem):
    anahtar = os.environ["GROQ_API_KEY"]
    y = requests.post(
        GROQ_URL,
        headers={"Authorization": f"Bearer {anahtar}"},
        json={
            "model": model,
            "temperature": 1.0,
            "response_format": {"type": "json_object"},
            "messages": [
                {"role": "system", "content": SISTEM},
                {"role": "user", "content": istem},
            ],
        },
        timeout=180,
    )
    if y.status_code in GECICI_KODLAR:
        raise GeciciHata(f"Groq {y.status_code}")
    if y.status_code != 200:
        raise RuntimeError(f"Groq hatası {y.status_code}: {y.text[:500]}")
    return y.json()["choices"][0]["message"]["content"]


def _israrla_iste(saglayici, model, istem, deneme_sayisi=3):
    """Sunucu yoğunsa bekleyip tekrar dener, olmazsa yedek modele geçer."""
    cagir = _gemini if saglayici == "gemini" else _groq
    modeller = [model] + ([m for m in YEDEK_MODELLER if m != model]
                          if saglayici == "gemini" else [])
    son_hata = None
    for sira, m in enumerate(modeller):
        for deneme in range(deneme_sayisi):
            try:
                if sira or deneme:
                    print(f"      (deneme: model={m}, {deneme + 1}. tur)")
                return cagir(m, istem)
            except GeciciHata as e:
                son_hata = e
                bekle = min(60, 5 * (2 ** deneme)) + random.uniform(0, 3)
                print(f"      ! {e} — {bekle:.0f} sn beklenip tekrar denenecek")
                time.sleep(bekle)
            except Exception as e:
                son_hata = e
                print(f"      ! {type(e).__name__}: {str(e)[:160]}")
                break          # kalıcı hata: bu modelde ısrar etme, yedeğe geç
    raise RuntimeError(f"Tüm modeller denendi, senaryo üretilemedi. Son hata: {son_hata}")


def uret(cfg, bolum_no, gecmis, kanon):
    mu = cfg["metin_uretimi"]
    istem = _istem(cfg, bolum_no, gecmis, kanon)
    ham = _israrla_iste(mu["saglayici"], mu["model"], istem)
    try:
        s = _json_ayikla(ham)
    except Exception:
        # Model bozuk JSON döndürdüyse bir kez daha şansını dene
        print("      ! JSON bozuk geldi, bir kez daha isteniyor")
        s = _json_ayikla(_israrla_iste(mu["saglayici"], mu["model"], istem))

    # --- doğrulama ---
    if not s.get("sahneler"):
        raise ValueError("Senaryoda sahne yok.")
    for sahne in s["sahneler"]:
        sahne["anlatim"] = re.sub(r"[*_#]", "", sahne.get("anlatim", "")).strip()
    s["sahneler"] = [x for x in s["sahneler"] if x["anlatim"]]
    s["baslik"] = (s.get("baslik") or f"Bölüm {bolum_no}").strip()[:95]
    if "ölüm" not in s["baslik"] and "Bölüm" not in s["baslik"]:
        s["baslik"] = f"{s['baslik']} | Bölüm {bolum_no}"
    s["bolum_no"] = bolum_no
    s["sabit_yorum"] = (s.get("sabit_yorum") or "").strip()[:400]

    etiketler = [e.strip().lstrip("#") for e in (s.get("etiketler") or []) if e.strip()]
    s["etiketler"] = etiketler[:15] or ["shorts", "hikaye", "animasyon"]

    kanca = (s.get("aciklama_kanca") or "").strip()
    aciklama = (s.get("aciklama") or "").strip()
    kanal = cfg.get("kanal", {})
    s["aciklama"] = "\n".join(x for x in [
        kanca,
        "",
        aciklama,
        "",
        f"{kanal.get('ad', '')} — Bölüm {bolum_no}".strip(" —"),
        "Yeni bölüm her gün 13:00'te.",
        "",
        cfg["youtube"]["seffaflik_notu"],
        "",
        " ".join(f"#{e.replace(' ', '')}" for e in s["etiketler"][:6]),
    ] if x is not None)[:4900]
    return s
