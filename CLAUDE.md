# CLAUDE.md

Proje: `histposts` — telifsiz, eski siyah-beyaz tarihi fotoğrafları bulup Instagram (4:5) ve TikTok/Reels (9:16)
için paylaşıma hazır, Türkçe metinli görsellere dönüştüren Python aracı.

## Komutlar

```bash
pip install -e ".[dev]"
export HISTPOSTS_CONTACT="ornek@eposta.com"        # Wikimedia User-Agent için
histposts search "konu" --before 1950               # aday + contact.jpg (renkli fotoğraflar elenir)
histposts check posts.yaml                          # lisans raporu
histposts verify posts.yaml                         # kanıta dayalı hak doğrulaması (yalnızca verified üretilir)
histposts facts facts.yaml                          # metin iddialarını Wikipedia ile kontrol et
histposts doctor posts.yaml                         # yayın öncesi kontrol listesi
histposts build posts.yaml [--only ad ...] [--strict]   # -> paylasima-hazir/NN-ad/
ruff check src tests && ruff format --check src tests && pytest
```

macOS'ta `histposts` "No module named histposts" derse: `chflags -R nohidden .venv` veya
`PYTHONPATH=src python -m histposts ...`.

## Yapı

- `posts.yaml`: her post için `name`, `file` (Commons dosya adı), `year`, `title`, `place`, `info` (görselde,
  3-5 satır), `story` (caption.txt için uzun metin), `tags`, isteğe bağlı `crop` ve `focus`.
- `src/histposts/compose.py`: tasarım. Tam kadraj fotoğraf + alt gradyan, harf aralıklı üst etiket
  (`TARİHTEN KARELER · YER`), Playfair Display büyük harf başlık, Lato gövde. Yatay/dikey uyumsuz fotoğraflar
  bulanık zemin üzerinde bütün olarak gösterilir. Türkçe büyük harf için `turkish_upper` kullan.
- `photocheck.py`: fotoğraf olmayanları ve renkli fotoğrafları (`is_monochrome`) eler.
- `licensing.py`: `safe` / `review` / `blocked`; kanıt `license_evidence.json` içinde.
- `enhance.py`: sadık iyileştirme (renklendirme, yüz onarımı, inpainting YOK).
- `paylasima-hazir/`, `output/`, `.histposts-cache/`, `tools/`: üretilen/indirilen, Git'e girmez.

## Kurallar

- Yalnızca siyah-beyaz veya sepya, tercihen 1950 öncesi belgesel fotoğraflar. Renkli fotoğraf ekleme.
- Yalnızca `verified` postlar üretilir: kamu malı şablonu + yazarın ölümünden 70 yıl geçmiş (Wikidata) ya da 126 yıldan eski anonim eser + ABD'de kamu malı. `us-only`/`unverified` olanı ekleme.
- Metindeki her olgu kaynak metadata'sına (Commons açıklaması, kurum kaydı) dayanmalı. Doğrulanamayan bilgiyi yazma;
  emin değilsen "kayıt … diyor" biçiminde belirt. Fotoğraftan çıkarım yapma.
- Bilgi metni kısa ve akıcı; `story` 400-800 karakter, sonda kaynak, lisans ve "dijital olarak iyileştirilmiştir".
- Görsele metin sığmazsa `ComposeWarning` verir; metni kısalt, sessizce kesme.
- Araç hiçbir şeyi kendisi paylaşmaz; Instagram/TikTok'a yükleme kullanıcı onayı olmadan yapılmaz.
- Değişiklikten sonra çıktıyı görsel olarak incele (taşma, Türkçe karakterler, kesilen yüzler, güvenli alan).
