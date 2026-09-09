"""Konuşmayı dinleyip senaryodaki kelimelerin zamanlarını bulur.

Gemini TTS kelime zamanı vermez. Whisper konuşmayı yazıya döker ve her
kelimenin saniyesini verir; biz de bunu SENARYO metniyle eşleştiririz.
Böylece altyazıda Whisper'ın olası yazım hataları değil, senaryonun
kendi doğru kelimeleri görünür — zamanlar ise gerçek konuşmadan gelir.
"""
import difflib
import re

_model = None


def _sadelestir(k):
    return re.sub(r"[^0-9a-zçğıöşüâîû]", "", k.casefold())


def model_yukle(boyut="base"):
    global _model
    if _model is None:
        from faster_whisper import WhisperModel
        print(f"      (Whisper '{boyut}' modeli yükleniyor, ilk sefer biraz sürer)")
        _model = WhisperModel(boyut, device="cpu", compute_type="int8")
    return _model


def dinle(ses_yolu, boyut="base", dil="tr"):
    """Ses dosyasını çözümle -> [{'kelime','bas','bit'}]"""
    model = model_yukle(boyut)
    parcalar, _ = model.transcribe(str(ses_yolu), language=dil,
                                   word_timestamps=True, vad_filter=False,
                                   beam_size=1)
    kelimeler = []
    for p in parcalar:
        for w in (p.words or []):
            yazi = w.word.strip()
            if yazi:
                kelimeler.append({"kelime": yazi, "bas": float(w.start),
                                  "bit": float(w.end)})
    return kelimeler


def hizala(senaryo_metni, asr_kelimeleri, toplam_sure):
    """Senaryo kelimelerine gerçek konuşma zamanlarını dağıtır."""
    hedef = [k for k in senaryo_metni.split() if k.strip()]
    if not hedef:
        return []
    if not asr_kelimeleri:
        adim = toplam_sure / len(hedef)
        return [{"bas": i * adim, "bit": (i + 1) * adim, "kelime": k}
                for i, k in enumerate(hedef)]

    a = [_sadelestir(k) for k in hedef]
    b = [_sadelestir(k["kelime"]) for k in asr_kelimeleri]
    zaman = [None] * len(hedef)

    for etiket, i1, i2, j1, j2 in difflib.SequenceMatcher(
            None, a, b, autojunk=False).get_opcodes():
        if etiket == "equal":
            for k in range(i2 - i1):
                w = asr_kelimeleri[j1 + k]
                zaman[i1 + k] = [w["bas"], w["bit"]]

    # eşleşmeyen kelimeleri, iki yanındaki çapa arasına eşit dağıt
    i = 0
    while i < len(zaman):
        if zaman[i] is not None:
            i += 1
            continue
        j = i
        while j < len(zaman) and zaman[j] is None:
            j += 1
        bas = zaman[i - 1][1] if i > 0 else 0.0
        bit = zaman[j][0] if j < len(zaman) else toplam_sure
        if bit <= bas:
            bit = bas + 0.25 * (j - i)
        adim = (bit - bas) / (j - i)
        for k in range(i, j):
            zaman[k] = [bas + (k - i) * adim, bas + (k - i + 1) * adim]
        i = j

    return [{"bas": max(0.0, z[0]), "bit": max(z[0] + 0.08, z[1]), "kelime": k}
            for k, z in zip(hedef, zaman)]
