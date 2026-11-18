"""Banka hesap hareketlerini ve kredi kartı ekstrelerini okuyup kurallar.csv ile kategoriler.

Kullanım:  py -I arac/ekstre_oku.py <çıktı adı> <dosya veya klasör> [...]
Çıktı:     veri/hareketler_<çıktı adı>.csv
Desteklenen:
  Ziraat hesap hareketleri (.xlsx, hücre konumsuz XML; "Hesap Listesi" dosyası atlanır)
  Garanti BBVA hesap hareketleri (.xls)
  Ziraat Bankkart kredi kartı ekstresi (.pdf, pymupdf ile)
Aynı hareket birden çok dosyada gelirse bir kez sayılır.
"""
import csv, hashlib, re, sys, zipfile, pathlib, xml.etree.ElementTree as ET
import pandas as pd

KOK = pathlib.Path(__file__).resolve().parent.parent
M = '{http://schemas.openxmlformats.org/spreadsheetml/2006/main}'
BOM = bytes([0xef, 0xbb, 0xbf])


def ziraat_oku(yol):
    # Ziraat'in xlsx'i openpyxl'in açamadığı bir stil tablosu taşıyor; hücreleri sırayla oku.
    z = zipfile.ZipFile(yol)
    if 'xl/worksheets/sheet.xml' not in z.namelist():
        return                                    # Hesap Listesi vb. hareket dosyası değil
    hesap = '?'
    for r in ET.fromstring(z.read('xl/worksheets/sheet.xml').lstrip(BOM)).iter(M + 'row'):
        h = [(c.findtext(M + 'v') or '') for c in r.findall(M + 'c')]
        if h and h[0] == 'Hesap Numarası':
            hesap = 'Ziraat ' + re.search(r'-(\d{4})\s', h[-1]).group(1)
        if len(h) >= 5 and re.match(r'\d\d\.\d\d\.\d{4}$', h[0]):
            yield dict(hesap=hesap, tarih=pd.to_datetime(h[0], format='%d.%m.%Y'),
                       aciklama=h[2].strip(), tutar=float(h[3]), bakiye=float(h[4]))


def garanti_oku(yol):
    hesap = '?'
    for _, r in pd.read_excel(yol, header=None, engine='xlrd').iterrows():
        if str(r[0]).strip() == 'Hesap':
            hesap = 'Garanti ' + str(r[1]).split(' TL')[0].replace(' ', '')
        if re.match(r'\d\d/\d\d/\d{4}$', str(r[0])):
            yield dict(hesap=hesap, tarih=pd.to_datetime(str(r[0]), format='%d/%m/%Y'),
                       aciklama=str(r[1]).strip(), tutar=float(r[3]), bakiye=float(r[4]))


TUTAR = re.compile(r'^[\d.]+,\d\d\+?$')


def kart_oku(yol):
    """Bankkart ekstresi. Harcama eksi, ödeme/iade (+ işaretli) artı yazılır.

    Kelimeler PDF'teki konumlarıyla okunur ve aynı yükseklikteki kelimeler bir satır sayılır.
    pdftotext -layout kullanılmıyor: tarih ile tutarı farklı satırlara kaydırıyordu
    (ör. 14 Mayıs'taki 1.200 TL, 30 Mayıs'ta 0 TL görünüyordu)."""
    import pymupdf
    with pymupdf.open(yol) as belge:
        for sayfa in belge:
            satirlar = []
            for w in sorted(sayfa.get_text('words'), key=lambda w: (w[1], w[0])):
                if satirlar and abs(w[1] - satirlar[-1][0]) < 3:
                    satirlar[-1][1].append(w)
                else:
                    satirlar.append((w[1], [w]))
            for _, kelimeler in satirlar:
                kelimeler.sort(key=lambda w: w[0])
                yazi = [w[4] for w in kelimeler]
                if not re.match(r'\d\d\.\d\d\.\d{4}$', yazi[0]):
                    continue
                # İlk tutar sütunu işlem tutarıdır; sağındaki sütunlar (puan vb.) alınmaz.
                i = next((k for k in range(1, len(yazi)) if TUTAR.match(yazi[k])), None)
                if i is None:
                    continue
                aciklama = ' '.join(yazi[1:i]).replace('\u00ad', '-')   # yumuşak tire
                if not aciklama or aciklama.startswith('KART NO'):
                    continue
                t = yazi[i]
                tutar = float(t.rstrip('+').replace('.', '').replace(',', '.'))
                yield dict(hesap='Ziraat Bankkart', tarih=pd.to_datetime(yazi[0], format='%d.%m.%Y'),
                           aciklama=aciklama, tutar=tutar if t.endswith('+') else -tutar, bakiye=None)


def dosya_oku(yol):
    yol = pathlib.Path(yol)
    uz = yol.suffix.lower()
    if uz == '.xlsx':
        return list(ziraat_oku(yol))
    if uz == '.xls':
        return list(garanti_oku(yol))
    if uz == '.pdf':
        return list(kart_oku(yol))
    return []


def hepsini_oku(yollar):
    dosyalar = []
    for y in map(pathlib.Path, yollar):
        dosyalar += sorted(p for p in y.rglob('*') if p.is_file()) if y.is_dir() else [y]
    hareket, gorulen_pdf = [], set()
    for f in dosyalar:
        if f.suffix.lower() == '.pdf':
            # Kart ekstresinde aynı gün aynı tutarlı iki gerçek harcama olabilir;
            # bu yüzden tekrar ayıklaması satır değil dosya içeriği düzeyinde.
            h = hashlib.sha256(f.read_bytes()).hexdigest()
            if h in gorulen_pdf:
                continue
            gorulen_pdf.add(h)
        hareket += [dict(r, dosya=f.name) for r in dosya_oku(f)]
    df = pd.DataFrame(hareket)
    kart = df[df.bakiye.isna()]
    return pd.concat([dosyalar_arasi_tekille(df[df.bakiye.notna()]),
                      dosyalar_arasi_tekille(kart, anahtar='aciklama')]) \
             .sort_values(['tarih', 'hesap']).reset_index(drop=True)


def dosyalar_arasi_tekille(df, anahtar='bakiye'):
    """Aynı hesabın örtüşen dökümlerini birleştirir. Anahtar (tarih, tutar, bakiye); açıklamaya
    bakılmaz, çünkü Garanti aynı havaleyi farklı indirmelerde farklı yazabiliyor. Bir dosya
    içindeki tekrar gerçektir (aynı gün iki 3.000 ₺ virman, bakiye aynı çıkabiliyor), o yüzden
    her anahtar, en çok hangi dosyada geçiyorsa o kadar kez tutulur.
    Kart ekstresinde bakiye yok: anahtar='aciklama'. Aynı ekstre iki kez indirilince PDF baytları
    farklı çıkabiliyor (oluşturma zamanı), dosya özeti tek başına yetmiyor."""
    df = df.assign(_n=df.groupby(['hesap', 'dosya', 'tarih', 'tutar', anahtar], dropna=False).cumcount())
    return df.drop_duplicates(['hesap', 'tarih', 'tutar', anahtar, '_n']).drop(columns='_n')


def kurallari_yukle():
    satirlar = (s for s in open(KOK / 'kurallar.csv', encoding='utf-8') if not s.startswith('#'))
    return [(re.compile(k['desen'], re.I), k) for k in csv.DictReader(satirlar)]


def satici(aciklama):
    """Açıklamadan okunur satıcı adını çıkarır."""
    m = re.search(r'İŞYERİ:\s*(.+?)\s+MUTABAKAT', aciklama) or re.search(r'SATIŞ-\d+\*\d+-(.+)', aciklama)
    return (m.group(1) if m else aciklama).strip()[:40]


def kategorile(df, kurallar):
    tur, kat, notu = [], [], []
    for a, h in zip(df.aciklama, df.hesap):
        b = (h + ' :: ' + a).upper()
        for desen, k in kurallar:
            if desen.search(b):
                tur.append(k['tur']); kat.append(k['kategori']); notu.append(k['not']); break
        else:
            tur.append('gider'); kat.append('TANINMADI'); notu.append('')
    df = df.assign(satici=df.aciklama.map(satici), tur=tur, kategori=kat, kural_notu=notu)
    return duzeltmeleri_uygula(transferleri_eslestir(df))


def transferleri_eslestir(df):
    """Alıcısı yazmayan bir çıkış (ör. Garanti MOBIL-FAST), başka bir hesabına en çok 1 gün
    içinde aynı tutarla 'kendi adına' giriş olarak düştüyse transfer sayılır."""
    giris = df[(df.kategori == 'Kendi hesapların arası') & (df.tutar > 0)]
    kullanildi = set()
    alicisiz = df.aciklama.str.contains('MOBIL-FAST', regex=False)
    for i, r in df[alicisiz & (df.tutar < 0)].iterrows():
        aday = giris[(giris.hesap != r.hesap) & ((giris.tutar + r.tutar).abs() < 0.005)
                     & ((giris.tarih - r.tarih).dt.days.abs() <= 1) & ~giris.index.isin(kullanildi)]
        if len(aday):
            kullanildi.add(aday.index[0])
            df.loc[i, ['tur', 'kategori', 'kural_notu']] = ['transfer', 'Kendi hesapların arası',
                                                         f'eşleşti: {aday.iloc[0].hesap}']
    return df


def duzeltmeleri_uygula(df):
    """duzeltmeler.csv'deki tarih + tutar eşleşmelerini kuralın üstüne yazar."""
    satirlar = (s for s in open(KOK / 'duzeltmeler.csv', encoding='utf-8') if not s.startswith('#'))
    for d in csv.DictReader(satirlar):
        es = (df.tarih == pd.Timestamp(d['tarih'])) & ((df.tutar - float(d['tutar'])).abs() < 0.005)
        if es.sum() != 1:
            print(f"UYARI: düzeltme {d['tarih']} {d['tutar']} -> {es.sum()} satırla eşleşti")
        df.loc[es, ['tur', 'kategori', 'kural_notu']] = [d['tur'], d['kategori'], d['not']]
    return df


# Dönem takvim ayı: düzenli gelirler ayın ilk günlerinde yatıyorsa dönem 1'inden başlar.
# Ayın 5'i olsaydı erken yatan maaş önceki aya kayardı. uygulamaya_aktar.BASLANGIC_GUNU ile aynı tutulur.
DONEM_GUNU = 1


def donem(t, gun=DONEM_GUNU):
    """Ayın <gun>'ünden sonraki ayın <gun>'üne. gun=1: takvim ayı, 15 Eylül -> '2026-09'."""
    t = pd.Timestamp(t)
    if t.day < gun:
        t = t - pd.DateOffset(months=1)
    return t.strftime('%Y-%m')


if __name__ == '__main__':
    ad, yollar = sys.argv[1], sys.argv[2:]
    df = kategorile(hepsini_oku(yollar), kurallari_yukle())
    df.insert(1, 'donem', df.tarih.map(donem))
    cikti = KOK / 'veri' / f'hareketler_{ad}.csv'
    df.to_csv(cikti, index=False, encoding='utf-8-sig', date_format='%Y-%m-%d')
    print(f'{len(df)} hareket -> {cikti}')
    print(df.groupby('hesap').size().to_string())
    print('Tanınmayan:', (df.kategori == 'TANINMADI').sum())
