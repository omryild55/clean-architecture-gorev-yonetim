# Clean Architecture Tabanlı Görev Yönetim Sistemi

Saf **Clean Architecture (Temiz Mimari)** ve **SOLID** prensiplerine tam uyumlu olarak Python 3.11+ ve FastAPI ile geliştirilmiş, kalıcılık mekanizmasından tamamen bağımsız (**Persistence Agnostic**) kurumsal görev yönetim uygulaması.

## Projenin Amacı ve Temel Özellikler

- **Katı Bağımlılık Kuralı (Dependency Rule):** İç halkalar (`domain/` ve `application/`) dış dünyayı (`infrastructure/`, `presentation/`, FastAPI, SQLAlchemy, Pydantic) kesinlikle bilmez ve import etmez.
- **Zengin Domain Modeli (Rich Domain Model):** Tüm iş kuralları (geçmiş tarih engeli, durum makinesi, tamamlanmış görev kilidi, kritik görev silme koruması, başlık doğrulaması) doğrudan `Gorev` varlığı ve değer nesneleri içerisinde korunur.
- **Çift Repository Desteği (`REPO_TYPE`):** Tek bir ortam değişkeniyle (`REPO_TYPE=sqlite` veya `REPO_TYPE=memory`) uygulama birebir aynı API ve iş kuralı davranışıyla hem SQLite (SQLAlchemy ORM) hem de Bellek İçi (In-Memory) depo üzerinde çalışır.
- **Modern Web Arayüzü & Swagger UI:** `/` adresinde Kanban/Liste görünümlü tek sayfalık modern görev yönetim paneli (HTML5 + Tailwind CSS + Vanilla JS), `/docs` adresinde otomatik OpenAPI (Swagger) dokümantasyonu sunar.
- **Otomatik Mimari Denetimi:** `tests/architecture/` altındaki AST tabanlı testler, `domain/` katmanının sıfır dış bağımlılığa sahip olduğunu her test koşumunda otomatik doğrular.

---

## Klasör Yapısı

```text
yazilim/
├── domain/                                   # 1. Halka: Saf İş Kuralları (Sıfır Dış Bağımlılık)
│   ├── __init__.py
│   ├── entities/
│   │   ├── __init__.py
│   │   └── gorev.py                          # Zengin Domain Varlığı (Gorev)
│   ├── value_objects/
│   │   ├── __init__.py
│   │   ├── gorev_durumu.py                   # GorevDurumu Enum ve geçiş matrisi
│   │   ├── gorev_onceligi.py                 # GorevOnceligi Enum
│   │   └── tarih_dogrulama.py                # GorevBasligi ve BitisTarihi değer nesneleri
│   ├── exceptions/
│   │   ├── __init__.py
│   │   └── domain_hatalari.py                # HTTP/DB bağımsız özel Domain hataları
│   └── repositories/
│       ├── __init__.py
│       └── gorev_repository_arayuzu.py       # Soyut depo sözleşmesi (ABC)
├── application/                              # 2. Halka: Kullanım Senaryoları (Use Cases)
│   ├── __init__.py
│   ├── dtos/
│   │   ├── __init__.py
│   │   └── gorev_dto.py                      # Katmanlar arası saf dataclass DTO'lar
│   └── use_cases/
│       ├── __init__.py
│       ├── gorev_olustur.py                  # GorevOlusturUseCase
│       ├── gorev_listele.py                  # GorevListeleUseCase
│       ├── gorev_getir.py                    # GorevGetirUseCase
│       ├── gorev_guncelle.py                 # GorevGuncelleUseCase
│       ├── gorev_durum_degistir.py           # GorevDurumDegistirUseCase
│       └── gorev_sil.py                      # GorevSilUseCase
├── infrastructure/                           # 3. Halka: Dış Dünya Adaptörleri
│   ├── __init__.py
│   ├── persistence/
│   │   ├── __init__.py
│   │   ├── in_memory_gorev_repository.py     # Bellek içi thread-safe adaptör
│   │   └── sqlite_gorev_repository.py        # SQLAlchemy + SQLite adaptör
│   └── config/
│       ├── __init__.py
│       └── ayarlar.py                        # Ortam ayarları ve DI Konteyneri
├── presentation/                             # 4. Halka: Sunum ve API Katmanı
│   ├── __init__.py
│   ├── api/
│   │   ├── __init__.py
│   │   ├── semalar.py                        # Pydantic istek/yanıt şemaları
│   │   └── gorev_router.py                   # FastAPI uç noktaları ve Global Exception Handler
│   └── web/
│       └── index.html                        # Modern SPA Görev Yönetim Paneli
├── tests/                                    # Kapsamlı Test Paketi (Pytest)
│   ├── __init__.py
│   ├── conftest.py                           # memory & sqlite parametreli fikstürler
│   ├── unit/
│   │   ├── __init__.py
│   │   ├── test_value_objects.py             # Başlık ve tarih sınır testleri
│   │   ├── test_durum_makinesi.py            # 4x4 durum geçiş matrisi testleri
│   │   └── test_gorev_varligi.py             # Zengin varlık iş kuralları testleri
│   ├── integration/
│   │   ├── __init__.py
│   │   ├── test_use_cases.py                 # Use Case entegrasyon testleri
│   │   └── test_gorev_api.py                 # Uçtan uca REST API testleri
│   └── architecture/
│       ├── __init__.py
│       └── test_bagimlilik_kurallari.py      # AST ile mimari sınır denetimi
├── docs/
│   └── MIMARI_DOKUMANTASYON.md               # C4/Katman/Durum diyagramları ve SOLID tablosu
├── main.py                                   # Composition Root ve FastAPI giriş noktası
├── requirements.txt
├── pytest.ini
├── Dockerfile
├── docker-compose.yml
├── .gitignore
├── .dockerignore
└── README.md
```

---

## Kurulum ve Çalıştırma

### 1. Localhost Üzerinde Kurulum (Python 3.11+)

```bash
# 1. Sanal ortam oluşturun ve etkinleştirin (Windows PowerShell)
python -m venv .venv
.\.venv\Scripts\Activate.ps1

# (Linux / macOS için)
# python3 -m venv .venv && source .venv/bin/activate

# 2. Bağımlılıkları yükleyin
pip install -r requirements.txt
```

### 2. Repository Değiştirme ve Uygulamayı Başlatma

Sistem varsayılan olarak `REPO_TYPE=sqlite` modunda `./gorevler.db` dosyasını kullanır. Tek bir ortam değişkeni ile depo motorunu değiştirebilirsiniz:

#### Windows PowerShell
```powershell
# Seçenek A: SQLite (Kalıcı veritabanı) ile başlatma
$env:REPO_TYPE="sqlite"
$env:SQLITE_DB_PATH="./gorevler.db"
uvicorn main:uygulama --reload --host 127.0.0.1 --port 8000

# Seçenek B: In-Memory (Bellek içi geçici depo) ile başlatma
$env:REPO_TYPE="memory"
uvicorn main:uygulama --reload --host 127.0.0.1 --port 8000
```

#### Linux / macOS (Bash)
```bash
# Seçenek A: SQLite ile başlatma
REPO_TYPE=sqlite SQLITE_DB_PATH=./gorevler.db uvicorn main:uygulama --reload --host 127.0.0.1 --port 8000

# Seçenek B: In-Memory ile başlatma
REPO_TYPE=memory uvicorn main:uygulama --reload --host 127.0.0.1 --port 8000
```

Uygulama ayağa kalktıktan sonra tarayıcıdan erişebilirsiniz:
- **Web Paneli (UI):** `http://127.0.0.1:8000/`
- **Swagger UI:** `http://127.0.0.1:8000/docs`
- **ReDoc:** `http://127.0.0.1:8000/redoc`

### 3. Docker ve Docker Compose ile Tek Komutta Çalıştırma

```bash
# Varsayılan (SQLite + kalıcı volume) modunda çalıştırma
docker compose up --build

# In-Memory modunda çalıştırma (PowerShell)
$env:REPO_TYPE="memory"; docker compose up --build

# In-Memory modunda çalıştırma (Linux/macOS)
REPO_TYPE=memory docker compose up --build
```

---

## REST API Uç Noktaları

| HTTP Metodu | Uç Nokta | Açıklama | Başarı Kodu |
| :--- | :--- | :--- | :---: |
| `GET` | `/` | Tek sayfalık Görev Yönetim Web Paneli | `200` |
| `GET` | `/docs` | Otomatik Swagger UI dokümantasyonu | `200` |
| `GET` | `/api/v1/sistem` | Aktif repository tipi ve sistem sağlığı | `200` |
| `POST` | `/api/v1/gorevler` | Yeni görev oluşturur | `201` |
| `GET` | `/api/v1/gorevler` | Görevleri listeler (`durum`, `oncelik`, `arama` filtreli) | `200` |
| `GET` | `/api/v1/gorevler/{gorev_id}` | Tekil görev detayını getirir | `200` |
| `PUT` | `/api/v1/gorevler/{gorev_id}` | Görev bilgilerini günceller (tamamlanmışsa `400`) | `200` |
| `PATCH` | `/api/v1/gorevler/{gorev_id}/durum` | Durum makinesi kurallarıyla durum değiştirir | `200` |
| `DELETE` | `/api/v1/gorevler/{gorev_id}` | Görevi siler (`KRITIK` + `DEVAM_EDIYOR` ise `400`) | `204` |

---

## Testlerin Çalıştırılması

```bash
# Tüm test paketini çalıştır (Birim + Entegrasyon [Memory & SQLite] + Mimari)
python -m pytest -v

# Yalnızca Domain birim testleri
python -m pytest tests/unit -v

# Yalnızca Use Case ve API entegrasyon testleri (hem memory hem sqlite)
python -m pytest tests/integration -v

# Yalnızca AST Mimari Bağımlılık denetimi
python -m pytest tests/architecture -v
```

Ayrıntılı katman diyagramları, C4 bileşen şemaları, SOLID kanıt tablosu ve durum makinesi açıklamaları için [Mimari Dokümantasyon](docs/MIMARI_DOKUMANTASYON.md) dosyasını inceleyin.
