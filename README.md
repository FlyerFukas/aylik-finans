# Aylık Finans

Banka dökümlerini okuyup her hareketi kategoriye ayıran, sonucu [Gelir Gider](https://github.com/FlyerFukas/gelir-gider) uygulamasına aktarılacak dosyaya çeviren küçük yerel motor. Her şey bu bilgisayarda çalışır; veri hiçbir sunucuya gitmez, yapay zekâ gerekmez.

*Reads Turkish bank statements, categorises every transaction with plain rules and exports a file the offline [Gelir Gider](https://github.com/FlyerFukas/gelir-gider) app can import. Runs locally; no data leaves the machine.*

## Ne yapar

1. **Okur:** Ziraat hesap hareketleri (.xlsx), Garanti BBVA hesap hareketleri (.xls), Ziraat Bankkart kredi kartı ekstresi (.pdf).
2. **Tekilleştirir:** aynı hareket birden çok dosyada gelirse bir kez sayılır.
3. **Kategoriler:** `kurallar.csv` satırları sırayla denenir, ilk eşleşen kazanır. Kendi hesapların arası virmanlar ve kart borcu ödemesi gelir ya da gider sayılmaz.
4. **Düzeltir:** kuralın bilemeyeceği tek seferlik bilgi `duzeltmeler.csv`'ye tarih ve tutarla yazılır.
5. **Aktarır:** `veri/uygulama_<ad>.json` üretir. Her satırın kalıcı kimliği var; aynı dönem iki kez aktarılırsa uygulama tekrarları atlar.

Tanınmayan satırlar `veri/taninmayan_<ad>.txt` dosyasına düşer. O satırlar için `kurallar.csv`'ye bir kural ekleyip yeniden çalıştırmak yeter.

## Kullanım

Gereken: Python 3.12+, `pandas`, kredi kartı PDF'i için `pymupdf`, Garanti .xls için `xlrd`.

```bash
pip install pandas pymupdf xlrd
```

Dökümleri `Ekstre-Ocak` gibi `Ekstre` ile başlayan bir klasöre koy, sonra `AYI-ISLE.bat`'a çift tıkla ya da klasörü üstüne sürükle. Komut satırından:

```bash
py -I -X utf8 arac/ayi_isle.py "C:/Users/<sen>/Downloads/Ekstre-Ocak"
```

`kurallar.csv` ve `duzeltmeler.csv` örnektir; `AD SOYAD` yerine kendi adını, desenlere kendi bankanın açıklama metinlerini yaz. Gerçek döküm ve çıktılar `.gitignore` ile depo dışında kalır.

## Lisans

Kişisel, eğitim ve kâr amacı gütmeyen kullanım için ücretsiz (PolyForm Noncommercial 1.0.0). Ticari kullanım için [COMMERCIAL.md](COMMERCIAL.md).
