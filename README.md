# Günlük YouTube Shorts Otomasyonu (0 ₺)

Her gün **13:00 (TR)** otomatik olarak seri bir Shorts videosu üretir ve kanalına yükler:
senaryo → Türkçe seslendirme → görseller → kelime kelime altyazı → montaj → yükleme.
Bölümler birbirinin devamıdır; önceki bölümlerin hafızası `state.db` içinde tutulur.

## Maliyet

| Bileşen | Servis | Ücret | Limit |
|---|---|---|---|
| Senaryo/başlık/açıklama | Gemini API (AI Studio) | 0 ₺ | Free tier günlük istek limiti (1 video = 1 istek) |
| Seslendirme | edge-tts | 0 ₺ | Yok |
| Görseller | Pollinations.ai | 0 ₺ | Anahtarsız, kaba oran limiti var (otomatik yeniden dener) |
| Montaj | ffmpeg | 0 ₺ | — |
| Yükleme | YouTube Data API v3 | 0 ₺ | Günlük 10.000 birim, yükleme ~100 birim |
| Zamanlama | GitHub Actions | 0 ₺ | Public repo'da sınırsız dakika (private: 2000 dk/ay, 1 video ≈ 4 dk) |

Hiçbir adımda kredi kartı istenmez.

---

## Kurulum (yaklaşık 20 dakika)

### 1. Repo
Bu klasörü GitHub'a **public** repo olarak yükle (private de olur; Actions dakikası ayda 2000 ile sınırlı, yine de yeter).

```bash
git init && git add . && git commit -m "ilk kurulum"
git remote add origin https://github.com/KULLANICI/shorts-bot.git
git push -u origin main
```

### 2. Gemini anahtarı (ücretsiz)
1. https://aistudio.google.com/apikey → **Create API key**
2. Kart bilgisi istemez, anahtarı kopyala.

> Alternatif: https://console.groq.com → API key alıp `config.yaml`'da
> `saglayici: groq`, `model: "llama-3.3-70b-versatile"` yap.

### 3. YouTube yükleme izni (tek seferlik)
1. https://console.cloud.google.com → yeni proje.
2. **APIs & Services → Library → "YouTube Data API v3" → Enable**.
3. **OAuth consent screen**: External, uygulama adı ver, **Test users**'a kendi Gmail'ini ekle.
4. **Credentials → Create credentials → OAuth client ID → Desktop app** → JSON'u indir, adını `client_secret.json` yap ve proje köküne koy.
5. Kendi bilgisayarında:
   ```bash
   pip install google-auth-oauthlib
   python tools/get_youtube_token.py
   ```
   Tarayıcı açılır, kanalın hesabıyla onay ver. Terminale 3 değer yazdırır.

> `client_secret.json` dosyasını repoya **koyma** (.gitignore'da zaten).

### 4. GitHub Secrets
Repo → **Settings → Secrets and variables → Actions → New repository secret**:

| İsim | Değer |
|---|---|
| `GEMINI_API_KEY` | AI Studio anahtarı |
| `YT_CLIENT_ID` | adım 3 çıktısı |
| `YT_CLIENT_SECRET` | adım 3 çıktısı |
| `YT_REFRESH_TOKEN` | adım 3 çıktısı |

### 5. İlk deneme
Repo → **Actions → "Günlük Short" → Run workflow** → `deneme: true` işaretle.
Video yüklenmez, iş bitince sayfanın altındaki **Artifacts**'tan `.mp4` indirip izlersin.
Beğenirsen `deneme` işaretsiz tekrar çalıştır; artık her gün 13:00'te kendi kendine çalışır.

---

## Yerel test (isteğe bağlı)

```bash
pip install -r requirements.txt
export GEMINI_API_KEY=...
python main.py --deneme          # üretir, yüklemez -> cikti/bolum_0001/
python main.py --bolum 5 --deneme # belirli bölümü zorla
```
macOS'ta ffmpeg gerekir: `brew install ffmpeg`

---

## Ayarlar — `config.yaml`

- `seri.konsept` — anlatıcı karakter ve dünyanın kuralları. Kanalı değiştirmek istersen sadece burayı değiştir.
- `seri.gorsel_stil` — tüm görsellerin ortak görünümü.
- `video.sahne_sayisi` / `hedef_saniye` — video uzunluğu (45-58 sn tatlı nokta).
- `ses.voice` — `tr-TR-AhmetNeural` veya `tr-TR-EmelNeural`. Tüm liste: `edge-tts --list-voices | grep tr-TR`
- `altyazi.*` — punto, renk, ekrandaki kelime sayısı, alt boşluk.
- `youtube.gizlilik` — ilk günlerde `unlisted` yapıp sonucu izlemeni öneririm.
- `video.muzik` — `assets/muzik.mp3` koyarsan arkaya karışır. Telifsiz kaynak: YouTube Audio Library, Pixabay Music.

Günde 2 video istersen workflow'daki cron'a ikinci satır ekle: `- cron: "0 16 * * *"` (19:00 TR).

---

## Önemli: YouTube politikası

YouTube 2026'da "inauthentic content" kuralını sertleştirdi. Hedef yapay zekâ değil, **şablonlaşma**:
aynı ses + aynı kalıp + sıfır insan katkısıyla seri yükleme yapan kanallar demonetize ediliyor,
Ocak 2026'da bu gerekçeyle 16 büyük kanal kapatıldı.

Riski düşürmek için:
- Videoları yayınlamadan önce **gözden geçir** (ilk 2 hafta `unlisted` + elle kontrol iyi bir alışkanlık).
- YouTube Studio'da videoyu **"Altered or synthetic content"** olarak işaretle (bu alan API'de yok, Studio'dan yapılır). Açıklamaya not zaten otomatik ekleniyor.
- Ara ara formatı kır: kendi sesinle bir bölüm, farklı sahne sayısı, farklı görsel stili.
- Aynı hikâyeyi tekrar ettirme; `state.db` sürekliliği bunun için var.

## Sorun giderme

| Belirti | Çözüm |
|---|---|
| `403 quotaExceeded` | Günlük 10.000 birim doldu, ertesi gün sıfırlanır |
| `invalid_grant` | Refresh token iptal olmuş; adım 3'ü tekrarla (test user olarak eklenmemiş hesaplarda 7 günde bir düşebilir — consent screen'i "In production"a al) |
| Görseller degrade çıkıyor | Pollinations o an cevap vermemiş; `config.yaml`'da `saglayici: gemini` dene |
| Altyazıda Türkçe karakter bozuk | Runner'da `fonts-dejavu-core` kurulu olmalı (workflow'da var) |
