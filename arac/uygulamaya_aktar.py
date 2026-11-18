"""Kategorili hareketleri Gelir Gider uygulamasının "Ekstre verisini içe aktar" dosyasına çevirir.

Kullanım:  py -I arac/uygulamaya_aktar.py <ad>     (veri/hareketler_<ad>.csv okunur)
Çıktı:     veri/uygulama_<ad>.json  → uygulamada Ayarlar → Ekstre verisini içe aktar

Kendi hesapların arası virmanlar ve kredi kartı borç ödemeleri aktarılmaz (gelir/gider değil,
uygulamada yalnızca gürültü olur). Birikim / yatırım hareketleri (aracı kurum, fon, hisse...) "transfer" olarak gider.
Her satırın kalıcı bir extId'si var: aynı dosya ya da örtüşen dönem tekrar içe aktarılırsa
uygulama zaten olanları atlar.
"""
import hashlib, json, pathlib, sys
import pandas as pd

KOK = pathlib.Path(__file__).resolve().parent.parent
BASLANGIC_GUNU = 1   # ekstre_oku.DONEM_GUNU ile aynı: dönem takvim ayı

GIDER = {   # motor kategorisi -> uygulama kategori kimliği
    'Market': 'market', 'Yemek & kahve': 'yemek', 'Telefon & fatura': 'fatura',
    'Ulaşım': 'ulasim', 'Giyim & bakım': 'giyim', 'Sosyal': 'eglence',
    'Dijital & üyelik': 'dijital', 'Okul & gelişim': 'okul', 'Ev & ihtiyaç': 'ev',
    'Nakit': 'nakit', 'Faiz & banka masrafı': 'faiz', 'Kredi kartı (detaysız)': 'kart',
    'Sağlık': 'saglik', 'Vergi': 'vergi', 'Diğer': 'diger', 'TANINMADI': 'diger',
}
TRANSFER = {'Birikim / yatırım': 'birikim'}   # aracı kurum, fon, halka arz, hisse: araç adı 'name'de


def ext_id(r, sira):
    # Hesap hareketinde açıklama kimliğe girmez: Garanti aynı satırı farklı indirmelerde
    # farklı yazabiliyor. Kart satırında bakiye yok, açıklama gerekir.
    if pd.notna(r.bakiye):
        anahtar = f'{r.hesap}|{r.tarih}|{r.tutar:.2f}|{r.bakiye:.2f}|{sira}'
    else:
        anahtar = f'{r.hesap}|{r.tarih}|{r.tutar:.2f}|{r.aciklama}|{sira}'
    return hashlib.sha1(anahtar.encode('utf-8')).hexdigest()[:16]


def ad_bul(r):
    s = str(r.satici).strip()
    return (s if s and s != 'nan' else str(r.aciklama))[:60]


def islemlere_cevir(df):
    df = df.copy()
    # Kimlik anahtarıyla aynı alanlarla say: aynı gün, aynı tutar ve bakiyeli iki gerçek virman olabiliyor.
    df['sira'] = df.groupby(['hesap', 'tarih', 'tutar', 'bakiye'], dropna=False).cumcount()
    islemler, atlanan = [], 0
    for r in df.itertuples():
        tutar = round(abs(r.tutar), 2)
        if tutar == 0:
            atlanan += 1
            continue
        x = dict(extId=ext_id(r, r.sira), date=r.tarih, amount=tutar, name=ad_bul(r),
                 hesap=r.hesap)
        if r.tur == 'gider':
            x.update(type='expense', category=GIDER.get(r.kategori, 'diger'))
            if r.tutar > 0:
                x['iade'] = True        # iade: o kategoriden düşülür
        elif r.tur == 'gelir':
            x.update(type='income', category=r.kategori)
        elif r.kategori in TRANSFER:
            x.update(type='transfer', category=TRANSFER[r.kategori],
                     yon='giris' if r.tutar > 0 else 'cikis')
        else:
            atlanan += 1            # kendi hesaplar arası, kart ödemesi
            continue
        islemler.append(x)
    return islemler, atlanan


if __name__ == '__main__':
    ad = sys.argv[1]
    df = pd.read_csv(KOK / 'veri' / f'hareketler_{ad}.csv', encoding='utf-8-sig')
    islemler, atlanan = islemlere_cevir(df)
    cikti = KOK / 'veri' / f'uygulama_{ad}.json'
    # Kapsam: her hesabın bu dosyada kapsadığı tarih aralığı. Uygulama bu aralıkta olup dosyada artık
    # olmayan (ekstreden gelmiş, elle düzenlenmemiş) kayıtları kaldırır: düzeltilen okuma hatası,
    # silinen çift kayıt telefonda kalmasın.
    kapsam = {h: {'ilk': g.tarih.min(), 'son': g.tarih.max()} for h, g in df.groupby('hesap')}
    cikti.write_text(json.dumps({'uygulama': 'gelirgider-aktarim', 'surum': 2,
                                 'baslangicGunu': BASLANGIC_GUNU, 'kapsam': kapsam, 'islemler': islemler},
                                ensure_ascii=False, indent=1), encoding='utf-8')
    sayim = pd.Series([i['type'] for i in islemler]).value_counts().to_dict()
    print(f'{len(islemler)} işlem -> {cikti}  {sayim}  (aktarılmayan transfer/sıfır: {atlanan})')
    if len({i["extId"] for i in islemler}) != len(islemler):
        sys.exit('HATA: extId çakışması var')
