"""Aylık işlem tek komutta: klasördeki tüm ekstreler -> kategorili hareketler -> uygulama dosyası.

Kullanım:  AYI-ISLE.bat'a çift tıkla (İndirilenler'deki en yeni "Ekstre..." klasörünü alır)
           ya da klasörü AYI-ISLE.bat'ın üstüne sürükle-bırak.
Çıktı:     veri/uygulama_<klasör adı>.json  -> telefonda Ayarlar -> Banka Ekstresinden Aktar
           Tanınmayan satır varsa veri/taninmayan_<ad>.txt; o satırlar kurallar.csv'ye eklenince yeniden çalıştır.

Eşleme, tekilleştirme ve kategorileme bu bilgisayarda çalışır; Claude gerekmez.
Claude'a yalnız tanınmayan satırlar ya da yeni bir banka biçimi için gelinir.
"""
import os, pathlib, re, subprocess, sys
import pandas as pd

KOK = pathlib.Path(__file__).resolve().parent.parent
INDIRILENLER = pathlib.Path.home() / 'Downloads'


def klasor_sec():
    if len(sys.argv) > 1:
        return pathlib.Path(sys.argv[1])
    adaylar = [p for p in INDIRILENLER.iterdir() if p.is_dir() and p.name.lower().startswith('ekstre')]
    if not adaylar:
        sys.exit(f'İndirilenler içinde adı "Ekstre" ile başlayan klasör yok ({INDIRILENLER}).\n'
                 'Dökümleri örneğin "Ekstre-Ekim" adlı bir klasöre koy ya da klasörü bu dosyanın üstüne sürükle.')
    return max(adaylar, key=lambda p: p.stat().st_mtime)


def calistir(betik, *arg):
    r = subprocess.run([sys.executable, '-I', '-X', 'utf8', str(KOK / 'arac' / betik), *arg],
                       env={**os.environ, 'PYTHONUTF8': '1'})
    if r.returncode:
        sys.exit(f'\n{betik} hata verdi; yukarıdaki mesaja bak.')


if __name__ == '__main__':
    klasor = klasor_sec()
    if not klasor.is_dir():
        sys.exit(f'Klasör bulunamadı: {klasor}')
    ad = re.sub(r'[^\w-]+', '_', klasor.name).strip('_') or 'ay'
    print(f'Klasör: {klasor}\n')
    calistir('ekstre_oku.py', ad, str(klasor))
    print()
    calistir('uygulamaya_aktar.py', ad)

    hareket = pd.read_csv(KOK / 'veri' / f'hareketler_{ad}.csv')
    tanin = hareket[hareket.kategori == 'TANINMADI']
    tanin = tanin[tanin.tutar != 0]
    rapor = KOK / 'veri' / f'taninmayan_{ad}.txt'
    if len(tanin):
        rapor.write_text(tanin[['hesap', 'tarih', 'tutar', 'aciklama']].to_string(index=False), encoding='utf-8')
        print(f'\nTanınmayan {len(tanin)} satır ("Diğer" olarak aktarıldı): {rapor}')
        print('Bu dosyayı Claude\'a gönder ya da kurallar.csv\'ye satıcı ekleyip yeniden çalıştır.')
    else:
        rapor.unlink(missing_ok=True)
        print('\nTanınmayan satır yok.')

    json_yolu = KOK / 'veri' / f'uygulama_{ad}.json'
    print(f'\nHAZIR: {json_yolu}\nTelefonda: Ayarlar -> Banka Ekstresinden Aktar ile bu dosyayı seç.')
    if os.name == 'nt' and not os.environ.get('AYI_ISLE_SESSIZ'):   # denemede pencere açılmasın
        subprocess.run(['explorer', '/select,', str(json_yolu)])
