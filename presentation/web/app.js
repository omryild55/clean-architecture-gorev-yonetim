(() => {
  "use strict";

  const kokpitDurumu = {
    aktifSekme: "operasyon",
    gorunumModu: "kanban",
    baypasAktif: false,
    tumGorevler: [],
    gorunenGorevler: [],
    sistemBilgisi: null,
    mimariOzet: null,
    astRaporu: null,
    izKayitlari: [],
    seciliIzId: null,
    logSeviyeFiltresi: "",
    logAramaMetni: "",
    canliIzlemeAcik: true,
    sonIslemIzi: null,
    kuralSonuclari: {},
    seciliKodDosyasi: "domain/entities/gorev.py",
    cekmeceGorevId: null,
    animasyonSayaci: 0,
  };

  function htmlKacis(metin) {
    if (metin === null || metin === undefined) return "";
    return String(metin)
      .replace(/&/g, "&amp;")
      .replace(/</g, "&lt;")
      .replace(/>/g, "&gt;")
      .replace(/"/g, "&quot;")
      .replace(/'/g, "&#39;");
  }

  function tarihBicimle(iso) {
    if (!iso) return "Tarih yok";
    const tarih = new Date(iso);
    if (Number.isNaN(tarih.getTime())) return iso;
    return tarih.toLocaleString("tr-TR", {
      day: "2-digit",
      month: "2-digit",
      year: "numeric",
      hour: "2-digit",
      minute: "2-digit",
    });
  }

  function datetimeLocalFormatla(iso) {
    if (!iso) return "";
    const d = new Date(iso);
    if (Number.isNaN(d.getTime())) return "";
    const dolgu = (n) => String(n).padStart(2, "0");
    return `${d.getFullYear()}-${dolgu(d.getMonth() + 1)}-${dolgu(d.getDate())}T${dolgu(d.getHours())}:${dolgu(d.getMinutes())}`;
  }

  function oncelikRozetiOlustur(oncelik) {
    const siniflar = { KRITIK: "kritik", YUKSEK: "yuksek", ORTA: "orta", DUSUK: "dusuk" };
    return `<span class="rozet ${siniflar[oncelik] || "orta"}">${htmlKacis(oncelik)}</span>`;
  }

  function durumRozetiOlustur(durum) {
    const siniflar = { BEKLEMEDE: "warn", DEVAM_EDIYOR: "info", TAMAMLANDI: "ok", IPTAL_EDILDI: "err" };
    return `<span class="rozet ${siniflar[durum] || "info"}">${htmlKacis(durum)}</span>`;
  }

  function bildirimGoster(baslik, mesaj, tip = "info", izEtiketi = "") {
    const yigin = document.getElementById("bildirim-yigini");
    const kart = document.createElement("div");
    kart.className = `bildirim-kart ${tip}`;
    kart.innerHTML = `
      <div style="display:flex;justify-content:space-between;align-items:center;gap:8px">
        <strong style="font-size:12px">${htmlKacis(baslik)}</strong>
        ${izEtiketi ? `<span class="uuid-tag">${htmlKacis(izEtiketi)}</span>` : ""}
      </div>
      <div style="font-size:11.5px;color:var(--text-muted);margin-top:3px">${htmlKacis(mesaj)}</div>
    `;
    yigin.prepend(kart);
    setTimeout(() => {
      kart.style.opacity = "0";
      kart.style.transition = "opacity 0.2s ease";
      setTimeout(() => kart.remove(), 220);
    }, 4400);
  }

  async function istekGonder(yol, secenekler = {}, pasif = false) {
    const ayar = { ...secenekler };
    let gonderilenGovde = null;
    if (ayar.body !== undefined) {
      gonderilenGovde = ayar.body;
      if (typeof ayar.body !== "string") {
        ayar.headers = {
          "Content-Type": "application/json",
          ...(ayar.headers || {}),
        };
        ayar.body = JSON.stringify(ayar.body);
      }
    }

    const yanit = await fetch(yol, ayar);
    let veri = null;
    if (yanit.status !== 204) {
      const ham = await yanit.text();
      if (ham) {
        try {
          veri = JSON.parse(ham);
        } catch {
          veri = ham;
        }
      }
    }

    const iz = {
      izId: yanit.headers.get("X-Trace-Id") || "—",
      sureMs: parseFloat(yanit.headers.get("X-Process-Time-Ms") || "0") || 0,
      aktifRepo: yanit.headers.get("X-Active-Repository") || "sqlite",
      depoSinifi: yanit.headers.get("X-Active-Repo-Class") || "SqliteGorevRepository",
      useCase: yanit.headers.get("X-Executed-UseCase") || `${ayar.method || "GET"} ${yol}`,
      domainIstisnaSinifi: yanit.headers.get("X-Domain-Exception"),
      domainHataKodu: yanit.headers.get("X-Domain-Error-Code") || veri?.hata_kodu || null,
      durumKodu: yanit.status,
      metot: ayar.method || "GET",
      yol,
      basarili: yanit.ok,
      istekGovdesi: gonderilenGovde,
      veri,
    };

    if (!pasif) {
      kokpitDurumu.sonIslemIzi = iz;
      katmanAkisiniCanlandir(iz);
      Promise.all([sistemBilgisiYukle(), izKayitlariniYukle(false)]).catch(() => {});
    }

    return iz;
  }

  function beklet(ms) {
    return new Promise((resolve) => setTimeout(resolve, ms));
  }

  async function katmanAkisiniCanlandir(iz) {
    const mevcutTur = ++kokpitDurumu.animasyonSayaci;
    document.getElementById("akis-ozet-satir").textContent = `${iz.metot} ${iz.yol} -> ${iz.useCase}`;
    document.getElementById("akis-iz-rozeti").textContent = iz.izId;
    document.getElementById("akis-sure-rozet").textContent = `${iz.sureMs.toFixed(2)} ms`;

    const httpRozet = document.getElementById("akis-http-rozet");
    httpRozet.className = `rozet ${iz.basarili ? "ok" : "err"}`;
    httpRozet.textContent = `HTTP ${iz.durumKodu}${iz.domainHataKodu ? ` · ${iz.domainHataKodu}` : ""}`;

    let zincir;
    if (iz.domainHataKodu) {
      if (iz.domainHataKodu === "GOREV_BULUNAMADI") {
        zincir = [
          { halka: "Presentation", baslik: "4. Presentation: FastAPI Router", bilesen: `${iz.metot} ${iz.yol} · Global Handler`, durum: "ok", etiket: "GEÇTİ" },
          { halka: "Application", baslik: "3. Application: Use Case", bilesen: iz.useCase, durum: "ok", etiket: "GEÇTİ" },
          { halka: "Domain", baslik: "2. Domain: İstisna Fırlatıldı", bilesen: `${iz.domainIstisnaSinifi || "GorevBulunamadiHatasi"}`, durum: "ihlal", etiket: "DURDU" },
          { halka: "Infrastructure", baslik: "1. Infrastructure: Repository", bilesen: `${iz.depoSinifi} (Kayıt Bulunamadı)`, durum: "ok", etiket: "ARANDI" },
        ];
      } else {
        zincir = [
          { halka: "Presentation", baslik: "4. Presentation: FastAPI Router", bilesen: `${iz.metot} ${iz.yol} · Ham İstek Alındı`, durum: "ok", etiket: "GEÇTİ" },
          { halka: "Application", baslik: "3. Application: Use Case", bilesen: iz.useCase, durum: "ok", etiket: "GEÇTİ" },
          { halka: "Domain", baslik: "2. Domain: Gorev İş Kuralı İhlali!", bilesen: `${iz.domainIstisnaSinifi || "DomainHatasi"} (${iz.domainHataKodu})`, durum: "ihlal", etiket: "DURDURDU" },
          { halka: "Infrastructure", baslik: "1. Infrastructure: Repository Adaptörü", bilesen: `${iz.depoSinifi} — Veritabanı Yazımı Engellendi`, durum: "atlandi", etiket: "ENGELLENDİ" },
        ];
      }
    } else if (iz.durumKodu === 422) {
      zincir = [
        { halka: "Presentation", baslik: "4. Presentation: Pydantic Doğrulama", bilesen: "İstek Şeması Uyuşmazlığı (422)", durum: "ihlal", etiket: "RED" },
        { halka: "Application", baslik: "3. Application: Use Case", bilesen: "Çağrılmadı", durum: "atlandi", etiket: "ATLANDI" },
        { halka: "Domain", baslik: "2. Domain: Gorev Entity", bilesen: "Çağrılmadı", durum: "atlandi", etiket: "ATLANDI" },
        { halka: "Infrastructure", baslik: "1. Infrastructure: Repository", bilesen: "Çağrılmadı", durum: "atlandi", etiket: "ATLANDI" },
      ];
    } else {
      zincir = [
        { halka: "Presentation", baslik: "4. Presentation: FastAPI Router", bilesen: `${iz.metot} ${iz.yol}`, durum: "ok", etiket: "OK" },
        { halka: "Application", baslik: "3. Application: Use Case", bilesen: iz.useCase, durum: "ok", etiket: "OK" },
        { halka: "Domain", baslik: "2. Domain: Gorev Entity & İş Kuralı", bilesen: "Tüm iş kuralları ve değişmezler doğrulandı", durum: "ok", etiket: "OK" },
        { halka: "Infrastructure", baslik: "1. Infrastructure: Repository Adaptörü", bilesen: `${iz.depoSinifi} (${iz.aktifRepo})`, durum: "ok", etiket: "YAZILDI/OKUNDU" },
      ];
    }

    const kap = document.getElementById("halka-zincir");
    const okMetinleri = [
      "↓ Pydantic Şema -> UseCase Girdi DTO",
      "↓ UseCase -> Domain Entity / Değer Nesnesi Çağrısı",
      "↓ Soyut GorevRepositoryArayuzu Sözleşmesi (DIP)",
    ];

    kap.innerHTML = zincir
      .map((z, idx) => {
        const kutuHtml = `
          <div class="halka-kutu" id="akis-kutu-${idx}">
            <div class="halka-ust">
              <span class="halka-ad">${htmlKacis(z.baslik)}</span>
              <span class="rozet info" id="akis-rozet-${idx}">BEKLİYOR</span>
            </div>
            <div class="halka-bilesen">${htmlKacis(z.bilesen)}</div>
          </div>
        `;
        return idx < okMetinleri.length
          ? `${kutuHtml}<div class="halka-ok-isaret">${htmlKacis(okMetinleri[idx])}</div>`
          : kutuHtml;
      })
      .join("");

    for (let i = 0; i < zincir.length; i++) {
      if (kokpitDurumu.animasyonSayaci !== mevcutTur) return;
      const kutu = document.getElementById(`akis-kutu-${i}`);
      const rozet = document.getElementById(`akis-rozet-${i}`);
      if (!kutu || !rozet) continue;

      kutu.classList.add("animasyon-aktif");
      await beklet(115);
      if (kokpitDurumu.animasyonSayaci !== mevcutTur) return;

      kutu.classList.remove("animasyon-aktif");
      kutu.classList.add(`durum-${zincir[i].durum}`);
      rozet.className = `rozet ${zincir[i].durum === "ok" ? "ok" : zincir[i].durum === "ihlal" ? "err" : "warn"}`;
      rozet.textContent = zincir[i].etiket;
    }

    const istisnaKutu = document.getElementById("akis-istisna-alani");
    if (!iz.basarili) {
      istisnaKutu.className = "istisna-kutusu";
      istisnaKutu.innerHTML = `
        <div style="display:flex;justify-content:space-between;align-items:center;gap:6px;flex-wrap:wrap">
          <strong style="font-size:12px;color:#fda4af">Domain İstisnası -> Global Exception Handler</strong>
          <span class="rozet err">${htmlKacis(iz.domainIstisnaSinifi || "Doğrulama Hatası")} · HTTP ${iz.durumKodu}</span>
        </div>
        <div style="font-size:12px;color:#ffe4e6;margin-top:5px">${htmlKacis(iz.veri?.mesaj || "İstek Domain kurallarına takıldı.")}</div>
        <pre class="json-pre">${htmlKacis(JSON.stringify(iz.veri, null, 2))}</pre>
      `;
    } else {
      istisnaKutu.className = "istisna-kutusu basari";
      const ozetVeri = Array.isArray(iz.veri)
        ? { listelenen_gorev_sayisi: iz.veri.length, ornek_ilk_kayit: iz.veri[0] || null }
        : iz.veri || { durum: "HTTP 204 No Content (Silindi)" };
      istisnaKutu.innerHTML = `
        <div style="display:flex;justify-content:space-between;align-items:center;gap:6px;flex-wrap:wrap">
          <strong style="font-size:12px;color:#34d399">Başarılı Katman Tamamlaması</strong>
          <span class="rozet ok">HTTP ${iz.durumKodu} · ${htmlKacis(iz.depoSinifi)}</span>
        </div>
        <pre class="json-pre">${htmlKacis(JSON.stringify(ozetVeri, null, 2))}</pre>
      `;
    }
  }

  function sekmeGecisYap(sekmeAdi) {
    kokpitDurumu.aktifSekme = sekmeAdi;
    document.querySelectorAll(".sekme-btn").forEach((btn) => {
      btn.classList.toggle("aktif", btn.dataset.sekme === sekmeAdi);
    });
    document.querySelectorAll(".sekme-paneli").forEach((panel) => {
      panel.classList.toggle("aktif", panel.id === `sekme-${sekmeAdi}`);
    });

    if (sekmeAdi === "kurallar") {
      fsmSayilariniGuncelle();
      durumMatrisiCiz();
      isKurallariKartlariniCiz();
    } else if (sekmeAdi === "mimari") {
      if (!kokpitDurumu.astRaporu) astDenetimiCalistir(false);
      else siralamaDiyagramiCiz();
    } else if (sekmeAdi === "loglar") {
      depoKarsilastirmaCiz();
      izKayitlariniYukle(true);
    }
  }

  async function sistemBilgisiYukle() {
    const iz = await istekGonder("/api/v1/sistem", {}, true);
    if (!iz.basarili || !iz.veri) return;
    const s = iz.veri;
    kokpitDurumu.sistemBilgisi = s;

    document.getElementById("ust-repo-etiket").textContent = String(s.aktif_repository).toUpperCase();
    document.getElementById("ust-depo-sinifi").textContent = `(${s.depo_sinifi || "SqliteGorevRepository"})`;
    document.getElementById("ust-istek-sayisi").textContent = s.toplam_istek;
    document.getElementById("ust-ihlal-sayisi").textContent = s.domain_ihlal_sayisi;
    document.getElementById("ust-calisma-suresi").textContent = `Uptime: ${Math.round(s.calisma_suresi_sn)}s`;

    document.getElementById("dip-sqlite-btn").classList.toggle("aktif", s.aktif_repository === "sqlite");
    document.getElementById("dip-memory-btn").classList.toggle("aktif", s.aktif_repository === "memory");
  }

  async function mimariOzetYukle() {
    const iz = await istekGonder("/api/v1/mimari/ozet", {}, true);
    if (!iz.basarili || !iz.veri) return;
    kokpitDurumu.mimariOzet = iz.veri;

    const t = iz.veri.test_ozeti;
    if (t) {
      document.getElementById("ust-test-ozeti").textContent =
        `${t.test_dosyasi} Dosya / ${t.test_fonksiyonu} Fonksiyon Yeşil`;
    }

    katmanDizinYapisiCiz();
    solidKartlariniCiz();
    isKurallariKartlariniCiz();
    durumMatrisiCiz();
    depoKarsilastirmaCiz();
  }

  async function depoAdaptoruDegistir(hedefRepo) {
    const iz = await istekGonder("/api/v1/sistem/depo-degistir", {
      method: "POST",
      body: { repo_tipi: hedefRepo },
    });
    if (iz.basarili && iz.veri) {
      bildirimGoster("DIP Adaptörü Değiştirildi", iz.veri.mesaj, "ok", iz.izId);
      await Promise.all([gorevleriYukle(false), mimariOzetYukle(), sistemBilgisiYukle()]);
    } else {
      bildirimGoster("Depo Hatası", iz.veri?.mesaj || "Adaptör değiştirilemedi.", "err", iz.izId);
    }
  }

  async function gorevleriYukle(sadeceFiltre = false) {
    const arama = document.getElementById("filtre-arama").value.trim();
    const durumFiltre = document.getElementById("filtre-durum").value;
    const oncelikFiltre = document.getElementById("filtre-oncelik").value;

    const params = new URLSearchParams();
    if (durumFiltre) params.set("durum", durumFiltre);
    if (oncelikFiltre) params.set("oncelik", oncelikFiltre);
    if (arama) params.set("arama", arama);
    const qs = params.toString();

    const tumIz = await istekGonder("/api/v1/gorevler", {}, Boolean(qs) || sadeceFiltre);
    if (tumIz.basarili && Array.isArray(tumIz.veri)) {
      kokpitDurumu.tumGorevler = tumIz.veri;
    }

    if (qs) {
      const filtreIz = await istekGonder(`/api/v1/gorevler?${qs}`, {}, false);
      kokpitDurumu.gorunenGorevler =
        filtreIz.basarili && Array.isArray(filtreIz.veri) ? filtreIz.veri : [];
    } else {
      kokpitDurumu.gorunenGorevler = kokpitDurumu.tumGorevler;
    }

    kpiSayaclariniGuncelle();
    kanbanVeListeCiz();
    fsmSayilariniGuncelle();
    if (kokpitDurumu.cekmeceGorevId) {
      const mevcut = kokpitDurumu.tumGorevler.find((g) => g.id === kokpitDurumu.cekmeceGorevId);
      if (mevcut) gorevDetayCekmecesiAc(mevcut.id, false);
    }
  }

  function kpiSayaclariniGuncelle() {
    const liste = kokpitDurumu.tumGorevler;
    const say = (d) => liste.filter((g) => g.durum === d).length;
    document.getElementById("kpi-toplam").textContent = liste.length;
    document.getElementById("kpi-beklemede").textContent = say("BEKLEMEDE");
    document.getElementById("kpi-devam").textContent = say("DEVAM_EDIYOR");
    document.getElementById("kpi-tamamlandi").textContent = say("TAMAMLANDI");
    document.getElementById("kpi-iptal").textContent = say("IPTAL_EDILDI");
    document.getElementById("sekme-rozet-gorev").textContent = liste.length;
  }

  function gorevKartButonlari(g) {
    const parcalar = [];
    if (g.izinli_gecisler.includes("DEVAM_EDIYOR")) {
      parcalar.push(`<button type="button" class="btn btn-cyan btn-sm" data-islem="durum" data-id="${htmlKacis(g.id)}" data-hedef="DEVAM_EDIYOR">Başlat</button>`);
    }
    if (g.izinli_gecisler.includes("TAMAMLANDI")) {
      parcalar.push(`<button type="button" class="btn btn-emerald btn-sm" data-islem="durum" data-id="${htmlKacis(g.id)}" data-hedef="TAMAMLANDI">Tamamla</button>`);
    }
    if (g.izinli_gecisler.includes("BEKLEMEDE")) {
      parcalar.push(`<button type="button" class="btn btn-amber btn-sm" data-islem="durum" data-id="${htmlKacis(g.id)}" data-hedef="BEKLEMEDE">Beklet</button>`);
    }
    if (g.izinli_gecisler.includes("IPTAL_EDILDI")) {
      parcalar.push(`<button type="button" class="btn btn-sm" data-islem="durum" data-id="${htmlKacis(g.id)}" data-hedef="IPTAL_EDILDI">İptal</button>`);
    }

    if (g.durum === "BEKLEMEDE") {
      parcalar.push(`<button type="button" class="btn btn-amber btn-sm" data-islem="durum" data-id="${htmlKacis(g.id)}" data-hedef="TAMAMLANDI">Atlamayı Dene (400)</button>`);
    }
    if (g.durum === "TAMAMLANDI") {
      parcalar.push(`<button type="button" class="btn btn-amber btn-sm" data-islem="kilit" data-id="${htmlKacis(g.id)}">Kilidi Zorla (400)</button>`);
    }
    if (g.durum === "IPTAL_EDILDI") {
      parcalar.push(`<button type="button" class="btn btn-amber btn-sm" data-islem="durum" data-id="${htmlKacis(g.id)}" data-hedef="DEVAM_EDIYOR">Yeniden Başlat (400)</button>`);
    }

    parcalar.push(`<button type="button" class="btn btn-sm" data-islem="duzenle" data-id="${htmlKacis(g.id)}">Düzenle</button>`);
    const silYazi = g.oncelik === "KRITIK" && g.durum === "DEVAM_EDIYOR" ? "Silmeyi Dene (400)" : "Sil";
    parcalar.push(`<button type="button" class="btn btn-rose btn-sm" data-islem="sil" data-id="${htmlKacis(g.id)}">${silYazi}</button>`);

    return parcalar.join("");
  }

  function kanbanVeListeCiz() {
    const sutunlar = {
      BEKLEMEDE: { kutu: document.getElementById("sutun-beklemede"), sayac: document.getElementById("sutun-say-beklemede") },
      DEVAM_EDIYOR: { kutu: document.getElementById("sutun-devam"), sayac: document.getElementById("sutun-say-devam") },
      TAMAMLANDI: { kutu: document.getElementById("sutun-tamamlandi"), sayac: document.getElementById("sutun-say-tamamlandi") },
      IPTAL_EDILDI: { kutu: document.getElementById("sutun-iptal"), sayac: document.getElementById("sutun-say-iptal") },
    };

    Object.keys(sutunlar).forEach((d) => {
      const gorevler = kokpitDurumu.gorunenGorevler.filter((g) => g.durum === d);
      sutunlar[d].sayac.textContent = gorevler.length;
      if (!gorevler.length) {
        sutunlar[d].kutu.innerHTML = `<div class="bos-sutun">Görev yok</div>`;
        return;
      }

      sutunlar[d].kutu.innerHTML = gorevler
        .map((g) => {
          const koruma =
            g.durum === "TAMAMLANDI"
              ? `<span class="rozet ok">KİLİTLİ</span>`
              : g.oncelik === "KRITIK" && g.durum === "DEVAM_EDIYOR"
              ? `<span class="rozet err">KORUMALI</span>`
              : "";
          return `
            <article class="gorev-karti">
              <div style="display:flex;justify-content:space-between;align-items:center;gap:4px">
                <span class="uuid-tag">#${htmlKacis(g.id.slice(0, 8))}</span>
                <div style="display:flex;gap:4px;flex-wrap:wrap;justify-content:flex-end">
                  ${koruma}
                  ${oncelikRozetiOlustur(g.oncelik)}
                </div>
              </div>
              <h3 class="gorev-baslik" data-islem="detay" data-id="${htmlKacis(g.id)}">${htmlKacis(g.baslik)}</h3>
              <p class="gorev-aciklama">${htmlKacis(g.aciklama || "Açıklama girilmemiş.")}</p>
              <div style="font-family:var(--font-mono);font-size:10.5px;color:var(--text-dim)">Bitiş: ${htmlKacis(tarihBicimle(g.bitis_tarihi))}</div>
              <div class="gorev-butonlar">${gorevKartButonlari(g)}</div>
            </article>
          `;
        })
        .join("");
    });

    const govde = document.getElementById("liste-govde");
    if (!kokpitDurumu.gorunenGorevler.length) {
      govde.innerHTML = `<tr><td colspan="6" style="text-align:center;color:var(--text-dim);padding:24px">Henüz görev yok. Üst bardan "5 Örnek Görev Yükle" veya demo senaryolarını çalıştırabilirsiniz.</td></tr>`;
    } else {
      govde.innerHTML = kokpitDurumu.gorunenGorevler
        .map(
          (g) => `
          <tr>
            <td><span class="uuid-tag">#${htmlKacis(g.id.slice(0, 8))}</span></td>
            <td>
              <strong style="cursor:pointer" data-islem="detay" data-id="${htmlKacis(g.id)}">${htmlKacis(g.baslik)}</strong>
              <div style="font-size:11px;color:var(--text-muted)">${htmlKacis(g.aciklama || "—")}</div>
            </td>
            <td>${durumRozetiOlustur(g.durum)}</td>
            <td>${oncelikRozetiOlustur(g.oncelik)}</td>
            <td style="font-family:var(--font-mono);font-size:11px">${htmlKacis(tarihBicimle(g.bitis_tarihi))}</td>
            <td><div style="display:flex;gap:4px;flex-wrap:wrap">${gorevKartButonlari(g)}</div></td>
          </tr>
        `
        )
        .join("");
    }
  }

  async function hazirDemoCalistir(demoTipi) {
    const simdi = new Date();
    const yarin = new Date(simdi.getTime() + 48 * 3600 * 1000).toISOString();
    const gecmis = new Date(simdi.getTime() - 24 * 3600 * 1000).toISOString();

    if (demoTipi === "olustur_201") {
      const iz = await istekGonder("/api/v1/gorevler", {
        method: "POST",
        body: {
          baslik: "Demo: Katman Akışı Doğrulaması",
          aciklama: "Presentation -> Application -> Domain -> Infrastructure tam başarı kanıtı.",
          oncelik: "YUKSEK",
          bitis_tarihi: yarin,
        },
      });
      if (iz.basarili) {
        bildirimGoster("Demo 1 Başarılı (HTTP 201)", "Geçerli görev tüm katmanları geçip kaydedildi.", "ok", iz.izId);
        await gorevleriYukle(true);
      }
      return;
    }

    if (demoTipi === "gecmis_tarih_422") {
      const iz = await istekGonder("/api/v1/gorevler", {
        method: "POST",
        body: {
          baslik: "Demo: Geçmiş Bitiş Tarihi Denemesi",
          aciklama: "BitisTarihi değer nesnesi geçmiş zamanı reddeder.",
          oncelik: "ORTA",
          bitis_tarihi: gecmis,
        },
      });
      bildirimGoster(
        `Demo 5: Domain Engelledi (HTTP ${iz.durumKodu})`,
        iz.veri?.mesaj || "Geçmiş tarih reddedildi.",
        "err",
        iz.izId
      );
      return;
    }

    if (demoTipi === "sicrama_400") {
      const gecici = await istekGonder("/api/v1/gorevler", {
        method: "POST",
        body: { baslik: "Demo Geçiş Testi Görevi", oncelik: "ORTA", bitis_tarihi: yarin },
      }, true);
      const id = gecici.veri.id;
      const iz = await istekGonder(`/api/v1/gorevler/${id}/durum`, {
        method: "PATCH",
        body: { yeni_durum: "TAMAMLANDI" },
      });
      await istekGonder(`/api/v1/gorevler/${id}`, { method: "DELETE" }, true);
      bildirimGoster(
        `Demo 2: Durum Makinesi Engelledi (HTTP ${iz.durumKodu})`,
        iz.veri?.mesaj || "BEKLEMEDE doğrudan TAMAMLANDI olamaz.",
        "err",
        iz.izId
      );
      return;
    }

    if (demoTipi === "kilit_400") {
      const gecici = await istekGonder("/api/v1/gorevler", {
        method: "POST",
        body: { baslik: "Demo Kilit Testi Görevi", oncelik: "YUKSEK", bitis_tarihi: yarin },
      }, true);
      const id = gecici.veri.id;
      await istekGonder(`/api/v1/gorevler/${id}/durum`, { method: "PATCH", body: { yeni_durum: "DEVAM_EDIYOR" } }, true);
      await istekGonder(`/api/v1/gorevler/${id}/durum`, { method: "PATCH", body: { yeni_durum: "TAMAMLANDI" } }, true);

      const iz = await istekGonder(`/api/v1/gorevler/${id}`, {
        method: "PUT",
        body: { baslik: "Kilitli Görevi Zorla Değiştir" },
      });
      await istekGonder(`/api/v1/gorevler/${id}`, { method: "DELETE" }, true);
      bildirimGoster(
        `Demo 3: Kilit Kuralı Devrede (HTTP ${iz.durumKodu})`,
        iz.veri?.mesaj || "Tamamlanmış görev salt okunurdur.",
        "err",
        iz.izId
      );
      return;
    }

    if (demoTipi === "kritik_sil_400") {
      const gecici = await istekGonder("/api/v1/gorevler", {
        method: "POST",
        body: { baslik: "Demo Kritik Koruma Görevi", oncelik: "KRITIK", bitis_tarihi: yarin },
      }, true);
      const id = gecici.veri.id;
      await istekGonder(`/api/v1/gorevler/${id}/durum`, { method: "PATCH", body: { yeni_durum: "DEVAM_EDIYOR" } }, true);

      const iz = await istekGonder(`/api/v1/gorevler/${id}`, { method: "DELETE" });
      await istekGonder(`/api/v1/gorevler/${id}/durum`, { method: "PATCH", body: { yeni_durum: "IPTAL_EDILDI" } }, true);
      await istekGonder(`/api/v1/gorevler/${id}`, { method: "DELETE" }, true);
      bildirimGoster(
        `Demo 4: Kritik Silme Koruması (HTTP ${iz.durumKodu})`,
        iz.veri?.mesaj || "KRITIK + DEVAM_EDIYOR görev silinemez.",
        "err",
        iz.izId
      );
    }
  }

  function baypasModuGuncelle(aktif) {
    kokpitDurumu.baypasAktif = aktif;
    const kutu = document.getElementById("baypas-kutu");
    const aciklama = document.getElementById("baypas-aciklama");
    const form = document.getElementById("gorev-form");
    const baslikInput = document.getElementById("form-baslik");
    const zehirSerit = document.getElementById("zehirli-payload-seridi");

    kutu.classList.toggle("aktif", aktif);
    if (aktif) {
      aciklama.textContent = "AÇIK: HTML form engelleri kaldırıldı! Kısa başlık veya geçmiş tarih doğrudan API + Domain katmanına yollanır.";
      form.setAttribute("novalidate", "novalidate");
      baslikInput.removeAttribute("minlength");
      baslikInput.removeAttribute("required");
      zehirSerit.style.display = "flex";
    } else {
      aciklama.textContent = "Kapalı: Standart form kontrolleri aktif. Açıldığında tarayıcı doğrulaması kapatılır ve ham veri doğrudan API'ye gider.";
      form.removeAttribute("novalidate");
      baslikInput.setAttribute("minlength", "3");
      baslikInput.setAttribute("required", "required");
      zehirSerit.style.display = "none";
    }
  }

  function gorevModalAc(gorevId = null) {
    const modal = document.getElementById("gorev-modal");
    const temizleSarici = document.getElementById("tarih-temizle-sarici");
    const temizleChk = document.getElementById("form-tarih-temizle");

    if (gorevId) {
      const g = kokpitDurumu.tumGorevler.find((x) => x.id === gorevId);
      if (!g) return;
      document.getElementById("modal-baslik").textContent = "Görevi Düzenle";
      document.getElementById("form-gorev-id").value = g.id;
      document.getElementById("form-baslik").value = g.baslik;
      document.getElementById("form-aciklama").value = g.aciklama || "";
      document.getElementById("form-oncelik").value = g.oncelik;
      document.getElementById("form-bitis").value = datetimeLocalFormatla(g.bitis_tarihi);
      temizleSarici.style.display = "flex";
      temizleChk.checked = false;
    } else {
      document.getElementById("modal-baslik").textContent = "Yeni Görev Oluştur";
      document.getElementById("form-gorev-id").value = "";
      document.getElementById("form-baslik").value = "";
      document.getElementById("form-aciklama").value = "";
      document.getElementById("form-oncelik").value = "ORTA";
      document.getElementById("form-bitis").value = "";
      temizleSarici.style.display = "none";
      temizleChk.checked = false;
    }
    baypasModuGuncelle(kokpitDurumu.baypasAktif);
    modal.classList.add("acik");
  }

  function gorevModalKapat() {
    document.getElementById("gorev-modal").classList.remove("acik");
  }

  async function gorevFormuGonder(e) {
    e.preventDefault();
    const id = document.getElementById("form-gorev-id").value.trim();
    const baslik = document.getElementById("form-baslik").value;
    const aciklama = document.getElementById("form-aciklama").value;
    const oncelik = document.getElementById("form-oncelik").value;
    const hamBitis = document.getElementById("form-bitis").value;
    const bitisIso = hamBitis ? new Date(hamBitis).toISOString() : null;

    if (id) {
      const temizle = document.getElementById("form-tarih-temizle").checked;
      const iz = await istekGonder(`/api/v1/gorevler/${encodeURIComponent(id)}`, {
        method: "PUT",
        body: {
          baslik,
          aciklama,
          oncelik,
          bitis_tarihi: temizle ? null : bitisIso,
          bitis_tarihini_temizle: temizle,
        },
      });
      if (iz.basarili) {
        gorevModalKapat();
        bildirimGoster("Görev Güncellendi", iz.veri.baslik, "ok", iz.izId);
        await gorevleriYukle(false);
      } else {
        bildirimGoster(`Domain Reddetti (${iz.domainHataKodu || iz.durumKodu})`, iz.veri?.mesaj || "Güncelleme engellendi.", "err", iz.izId);
      }
      return;
    }

    const iz = await istekGonder("/api/v1/gorevler", {
      method: "POST",
      body: { baslik, aciklama, oncelik, bitis_tarihi: bitisIso },
    });
    if (iz.basarili) {
      gorevModalKapat();
      bildirimGoster("Görev Oluşturuldu", iz.veri.baslik, "ok", iz.izId);
      await gorevleriYukle(false);
    } else {
      bildirimGoster(`Domain Reddetti (${iz.domainHataKodu || iz.durumKodu})`, iz.veri?.mesaj || "Oluşturma engellendi.", "err", iz.izId);
    }
  }

  function gorevDetayCekmecesiAc(gorevId, acikTut = true) {
    const g = kokpitDurumu.tumGorevler.find((x) => x.id === gorevId);
    if (!g) return;
    kokpitDurumu.cekmeceGorevId = g.id;
    document.getElementById("cekmece-baslik").textContent = g.baslik;
    document.getElementById("cekmece-id").textContent = g.id;
    document.getElementById("cekmece-icerik").innerHTML = `
      <div style="display:flex;gap:8px;flex-wrap:wrap">
        ${durumRozetiOlustur(g.durum)}
        ${oncelikRozetiOlustur(g.oncelik)}
      </div>
      <div style="background:var(--bg-card);border:1px solid var(--border);border-radius:8px;padding:10px;font-size:12.5px">
        ${htmlKacis(g.aciklama || "Açıklama girilmemiş.")}
      </div>
      <div style="display:flex;gap:5px;flex-wrap:wrap">${gorevKartButonlari(g)}</div>
      <div>
        <strong style="font-size:11px;color:var(--text-muted)">GÖREV YANITI (GorevYaniti DTO)</strong>
        <pre class="json-pre">${htmlKacis(JSON.stringify(g, null, 2))}</pre>
      </div>
    `;
    if (acikTut) document.getElementById("gorev-cekmece").classList.add("acik");
  }

  // SEKME 2: İŞ KURALLARI & 4x4 DURUM MATRİSİ
  function fsmSayilariniGuncelle() {
    const liste = kokpitDurumu.tumGorevler;
    const say = (d) => liste.filter((g) => g.durum === d).length;
    document.getElementById("fsm-say-beklemede").textContent = `${say("BEKLEMEDE")} görev`;
    document.getElementById("fsm-say-devam").textContent = `${say("DEVAM_EDIYOR")} görev`;
    document.getElementById("fsm-say-tamamlandi").textContent = `${say("TAMAMLANDI")} görev`;
    document.getElementById("fsm-say-iptal").textContent = `${say("IPTAL_EDILDI")} görev`;
  }

  function isKurallariKartlariniCiz() {
    const kurallar = kokpitDurumu.mimariOzet?.is_kurallari || [];
    const izgara = document.getElementById("is-kurallari-izgara");
    const dogrulanan = Object.values(kokpitDurumu.kuralSonuclari).filter((s) => s && s.basarili).length;
    document.getElementById("lab-durum-sayac").textContent = `${dogrulanan} / ${kurallar.length || 5} Kural Doğrulandı`;

    izgara.innerHTML = kurallar
      .map((k) => {
        const sonuc = kokpitDurumu.kuralSonuclari[k.kural_no];
        const sonucAlani = sonuc
          ? `
            <div style="background:var(--bg-code);border:1px solid var(--border);border-radius:8px;padding:8px;font-family:var(--font-mono);font-size:11px">
              <div style="display:flex;justify-content:space-between;gap:6px;flex-wrap:wrap">
                <span class="rozet ${sonuc.basarili ? "ok" : "err"}">HTTP ${sonuc.durumKodu} · ${htmlKacis(sonuc.hataKodu)}</span>
                <span style="color:var(--cyan)">${htmlKacis(sonuc.izId)} · ${sonuc.sureMs.toFixed(2)} ms</span>
              </div>
              <pre class="json-pre" style="max-height:110px">${htmlKacis(JSON.stringify(sonuc.yanit, null, 2))}</pre>
            </div>
          `
          : `<div style="font-size:11px;color:var(--text-dim);font-family:var(--font-mono)">Beklenen: HTTP ${k.http_kod} ${htmlKacis(k.hata_kodu)}</div>`;

        return `
          <article class="kural-karti">
            <div style="display:flex;justify-content:space-between;align-items:flex-start;gap:8px">
              <strong style="font-size:13px">Kural ${k.kural_no}: ${htmlKacis(k.baslik)}</strong>
              <span class="rozet err">${htmlKacis(k.hata_sinifi)}</span>
            </div>
            <p style="margin:0;font-size:12px;color:var(--text-muted)">${htmlKacis(k.aciklama)}</p>
            <div style="display:flex;justify-content:space-between;align-items:center;gap:8px;flex-wrap:wrap">
              <button type="button" class="btn btn-sm" data-kod-ac="${htmlKacis(k.dosya)}" style="color:var(--cyan)">${htmlKacis(k.dosya)}</button>
              <button type="button" class="btn btn-cyan btn-sm" data-kural-test="${k.kural_no}">Canlı Test Et</button>
            </div>
            ${sonucAlani}
          </article>
        `;
      })
      .join("");
  }

  async function kuralCanliTestEt(kuralNo) {
    const simdi = new Date();
    const yarin = new Date(simdi.getTime() + 48 * 3600 * 1000).toISOString();
    const gecmis = new Date(simdi.getTime() - 24 * 3600 * 1000).toISOString();

    let iz;
    if (kuralNo === 1) {
      iz = await istekGonder("/api/v1/gorevler", {
        method: "POST",
        body: { baslik: "Kural 1 Geçmiş Tarih Testi", bitis_tarihi: gecmis, oncelik: "YUKSEK" },
      });
    } else if (kuralNo === 2) {
      const g = await istekGonder("/api/v1/gorevler", {
        method: "POST",
        body: { baslik: "Kural 2 Durum Sıçrama Testi", bitis_tarihi: yarin },
      }, true);
      iz = await istekGonder(`/api/v1/gorevler/${g.veri.id}/durum`, {
        method: "PATCH",
        body: { yeni_durum: "TAMAMLANDI" },
      });
      await istekGonder(`/api/v1/gorevler/${g.veri.id}`, { method: "DELETE" }, true);
    } else if (kuralNo === 3) {
      const g = await istekGonder("/api/v1/gorevler", {
        method: "POST",
        body: { baslik: "Kural 3 Kilit Testi", bitis_tarihi: yarin },
      }, true);
      const id = g.veri.id;
      await istekGonder(`/api/v1/gorevler/${id}/durum`, { method: "PATCH", body: { yeni_durum: "DEVAM_EDIYOR" } }, true);
      await istekGonder(`/api/v1/gorevler/${id}/durum`, { method: "PATCH", body: { yeni_durum: "TAMAMLANDI" } }, true);
      iz = await istekGonder(`/api/v1/gorevler/${id}`, {
        method: "PUT",
        body: { baslik: "Kilitli Güncelleme Denemesi" },
      });
      await istekGonder(`/api/v1/gorevler/${id}`, { method: "DELETE" }, true);
    } else if (kuralNo === 4) {
      const g = await istekGonder("/api/v1/gorevler", {
        method: "POST",
        body: { baslik: "Kural 4 Kritik Silme Testi", oncelik: "KRITIK", bitis_tarihi: yarin },
      }, true);
      const id = g.veri.id;
      await istekGonder(`/api/v1/gorevler/${id}/durum`, { method: "PATCH", body: { yeni_durum: "DEVAM_EDIYOR" } }, true);
      iz = await istekGonder(`/api/v1/gorevler/${id}`, { method: "DELETE" });
      await istekGonder(`/api/v1/gorevler/${id}/durum`, { method: "PATCH", body: { yeni_durum: "IPTAL_EDILDI" } }, true);
      await istekGonder(`/api/v1/gorevler/${id}`, { method: "DELETE" }, true);
    } else {
      iz = await istekGonder("/api/v1/gorevler", {
        method: "POST",
        body: { baslik: "ab" },
      });
    }

    const kural = (kokpitDurumu.mimariOzet?.is_kurallari || []).find((x) => x.kural_no === kuralNo);
    const basarili = kural && iz.durumKodu === kural.http_kod && iz.domainHataKodu === kural.hata_kodu;

    kokpitDurumu.kuralSonuclari[kuralNo] = {
      basarili: Boolean(basarili),
      durumKodu: iz.durumKodu,
      hataKodu: iz.domainHataKodu || `HTTP_${iz.durumKodu}`,
      izId: iz.izId,
      sureMs: iz.sureMs,
      yanit: iz.veri,
    };

    isKurallariKartlariniCiz();
    bildirimGoster(
      basarili ? `Kural ${kuralNo} Doğrulandı` : `Kural ${kuralNo} Sonucu`,
      `HTTP ${iz.durumKodu} (${iz.domainHataKodu || "—"})`,
      basarili ? "ok" : "err",
      iz.izId
    );
  }

  function durumMatrisiCiz() {
    const hucreler = kokpitDurumu.mimariOzet?.durum_matrisi || [];
    const durumlar = ["BEKLEMEDE", "DEVAM_EDIYOR", "TAMAMLANDI", "IPTAL_EDILDI"];
    const alan = document.getElementById("matris-tablo-alani");
    if (!hucreler.length) {
      alan.innerHTML = `<div style="color:var(--text-dim);font-size:12px">Matris yükleniyor...</div>`;
      return;
    }

    const satirlar = durumlar
      .map((kaynak) => {
        const sutunlar = durumlar
          .map((hedef) => {
            const h = hucreler.find((x) => x.kaynak === kaynak && x.hedef === hedef);
            const sinif = h?.izinli ? "izinli" : "yasak";
            const yazi = h?.izinli ? "İZİNLİ (200)" : "YASAK (400)";
            return `
              <td>
                <button type="button" class="matris-hucre ${sinif}" data-matris-kaynak="${kaynak}" data-matris-hedef="${hedef}" title="${htmlKacis(h?.kural_aciklamasi || "")}">
                  <span style="font-weight:800">${yazi}</span>
                  <span style="font-size:9.5px;opacity:0.85">Canlı Test Et</span>
                </button>
              </td>
            `;
          })
          .join("");
        return `<tr><th>${kaynak}</th>${sutunlar}</tr>`;
      })
      .join("");

    alan.innerHTML = `
      <table class="matris-tablo">
        <thead>
          <tr>
            <th>Kaynak \\ Hedef</th>
            ${durumlar.map((d) => `<th>${d}</th>`).join("")}
          </tr>
        </thead>
        <tbody>${satirlar}</tbody>
      </table>
    `;
  }

  async function matrisHucresiTestEt(kaynak, hedef) {
    const yarin = new Date(Date.now() + 48 * 3600 * 1000).toISOString();
    const gecici = await istekGonder("/api/v1/gorevler", {
      method: "POST",
      body: { baslik: `Matris Testi ${kaynak}->${hedef}`, bitis_tarihi: yarin },
    }, true);
    const id = gecici.veri.id;

    if (kaynak === "DEVAM_EDIYOR") {
      await istekGonder(`/api/v1/gorevler/${id}/durum`, { method: "PATCH", body: { yeni_durum: "DEVAM_EDIYOR" } }, true);
    } else if (kaynak === "TAMAMLANDI") {
      await istekGonder(`/api/v1/gorevler/${id}/durum`, { method: "PATCH", body: { yeni_durum: "DEVAM_EDIYOR" } }, true);
      await istekGonder(`/api/v1/gorevler/${id}/durum`, { method: "PATCH", body: { yeni_durum: "TAMAMLANDI" } }, true);
    } else if (kaynak === "IPTAL_EDILDI") {
      await istekGonder(`/api/v1/gorevler/${id}/durum`, { method: "PATCH", body: { yeni_durum: "IPTAL_EDILDI" } }, true);
    }

    const testIz = await istekGonder(`/api/v1/gorevler/${id}/durum`, {
      method: "PATCH",
      body: { yeni_durum: hedef },
    });
    await istekGonder(`/api/v1/gorevler/${id}`, { method: "DELETE" }, true);

    const kutu = document.getElementById("matris-sonuc-kutusu");
    kutu.innerHTML = `
      <div class="istisna-kutusu ${testIz.basarili ? "basari" : ""}">
        <div style="display:flex;justify-content:space-between;align-items:center;gap:8px;flex-wrap:wrap">
          <strong style="font-size:12px">${htmlKacis(kaynak)} -&gt; ${htmlKacis(hedef)}</strong>
          <span class="rozet ${testIz.basarili ? "ok" : "err"}">HTTP ${testIz.durumKodu} · ${htmlKacis(testIz.domainHataKodu || "BAŞARILI")} · ${testIz.sureMs.toFixed(2)} ms</span>
        </div>
        <pre class="json-pre">${htmlKacis(JSON.stringify(testIz.veri, null, 2))}</pre>
      </div>
    `;
  }

  // SEKME 3: CLEAN ARCHITECTURE, SOLID & CANLI AST
  function katmanDizinYapisiCiz() {
    const harita = kokpitDurumu.mimariOzet?.katman_haritasi || [];
    document.getElementById("katman-dizin-izgara").innerHTML = harita
      .map(
        (k) => `
        <div class="dizin-kart">
          <strong style="font-size:12.5px;color:var(--cyan)">${htmlKacis(k.baslik)}</strong>
          <div style="font-family:var(--font-mono);font-size:11px;color:var(--text-main);margin:6px 0">
            ${k.alt_dizinler.map((d) => `├── ${htmlKacis(k.yol + d)}`).join("<br>")}
          </div>
          <div style="font-size:11px;color:var(--text-muted)">${htmlKacis(k.bagimlilik)}</div>
        </div>
      `
      )
      .join("");
  }

  function solidKartlariniCiz() {
    const solid = kokpitDurumu.mimariOzet?.solid_prensipleri || [];
    document.getElementById("solid-izgara").innerHTML = solid
      .map(
        (s) => `
        <button type="button" class="solid-kart" data-kod-ac="${htmlKacis(s.dosya)}">
          <span class="solid-harf">${htmlKacis(s.harf)}</span>
          <div style="font-size:12px;font-weight:700">${htmlKacis(s.ilke)}</div>
          <div style="font-size:11px;color:var(--cyan);font-family:var(--font-mono);margin-top:3px">${htmlKacis(s.bilesen)}</div>
          <div style="font-size:11px;color:var(--text-muted);margin-top:4px">${htmlKacis(s.aciklama)}</div>
        </button>
      `
      )
      .join("");
  }

  function halkaDosyalariniGoster(katman) {
    const r = kokpitDurumu.astRaporu;
    const kutu = document.getElementById("halka-secim-bilgisi");
    const katmanOzet = r?.katmanlar?.find((x) => x.katman === katman);
    const dosyalar = (r?.dosyalar || []).filter((x) => x.katman === katman);

    kutu.innerHTML = `
      <div style="background:var(--bg-card);border:1px solid var(--border);border-radius:8px;padding:10px">
        <div style="display:flex;justify-content:space-between;align-items:center;margin-bottom:6px">
          <strong style="color:var(--cyan);text-transform:uppercase">${htmlKacis(katman)} Katmanı</strong>
          <span class="rozet ok">${katmanOzet ? `${katmanOzet.dosya_sayisi} dosya · ${katmanOzet.ihlal_sayisi} ihlal` : "Taranıyor"}</span>
        </div>
        <div style="margin-bottom:8px">${htmlKacis(katmanOzet?.kural || "")}</div>
        <div style="display:flex;gap:6px;flex-wrap:wrap">
          ${dosyalar.map((d) => `<button type="button" class="btn btn-sm" data-kod-ac="${htmlKacis(d.dosya)}">${htmlKacis(d.dosya)}</button>`).join("")}
        </div>
      </div>
    `;
  }

  function siralamaDiyagramiCiz() {
    const alan = document.getElementById("siralama-svg-alani");
    const altBaslik = document.getElementById("siralama-alt-baslik");
    const sonIz = kokpitDurumu.sonIslemIzi || kokpitDurumu.izKayitlari[0] || null;

    let ihlal = false;
    let endpoint = "POST /api/v1/gorevler";
    let useCase = "GorevOlusturUseCase";
    let depo = kokpitDurumu.sistemBilgisi?.depo_sinifi || "SqliteGorevRepository";
    let sonucYazi = "HTTP 201 Created";

    if (sonIz) {
      ihlal = Boolean(sonIz.domainHataKodu || sonIz.hata_kodu || !sonIz.basarili && sonIz.seviye !== "BASARILI");
      endpoint = `${sonIz.metot} ${sonIz.yol}`;
      useCase = sonIz.useCase || sonIz.use_case || useCase;
      depo = sonIz.depoSinifi || sonIz.depo_sinifi || depo;
      const kod = sonIz.durumKodu || sonIz.durum_kodu || 200;
      const hKod = sonIz.domainHataKodu || sonIz.hata_kodu;
      sonucYazi = hKod ? `HTTP ${kod} ${hKod}` : `HTTP ${kod}`;
      altBaslik.textContent = `Son İstek İzi (${sonIz.izId || sonIz.iz_id || "CANLI"}): ${endpoint}`;
    }

    const aktorler = ["Web Kokpit", "FastAPI", "UseCase", "Domain", depo];
    const xs = [46, 146, 246, 346, 452];
    const basliklar = aktorler
      .map(
        (ad, i) => `
      <rect x="${xs[i] - 42}" y="12" width="84" height="28" rx="6" fill="#121e36" stroke="#304c80" />
      <text x="${xs[i]}" y="30" text-anchor="middle" fill="#e7eef8" font-size="9" font-weight="700" font-family="monospace">${htmlKacis(ad.slice(0, 14))}</text>
      <line x1="${xs[i]}" y1="40" x2="${xs[i]}" y2="296" stroke="#1e3154" stroke-dasharray="4 4" />
    `
      )
      .join("");

    const altAkis = ihlal
      ? `
        <path d="M ${xs[3]} 176 L ${xs[1]} 176" stroke="#f43f5e" stroke-width="2" marker-end="url(#sOkRed)" />
        <text x="${(xs[3] + xs[1]) / 2}" y="168" text-anchor="middle" fill="#fda4af" font-size="9.5" font-weight="700" font-family="monospace">raise DomainHatasi</text>
        <rect x="${xs[4] - 38}" y="190" width="76" height="30" rx="6" fill="#2c0b16" stroke="#f43f5e" stroke-dasharray="3 3" />
        <text x="${xs[4]}" y="209" text-anchor="middle" fill="#fda4af" font-size="8.5" font-family="monospace">ENGELLENDİ</text>
        <path d="M ${xs[1]} 248 L ${xs[0]} 248" stroke="#f43f5e" stroke-width="2" marker-end="url(#sOkRed)" />
        <text x="${(xs[1] + xs[0]) / 2}" y="240" text-anchor="middle" fill="#fb7185" font-size="9" font-family="monospace">${htmlKacis(sonucYazi)}</text>
      `
      : `
        <path d="M ${xs[3]} 176 L ${xs[2]} 176" stroke="#10b981" stroke-width="1.8" marker-end="url(#sOkGreen)" />
        <text x="${(xs[3] + xs[2]) / 2}" y="168" text-anchor="middle" fill="#6ee7b7" font-size="9" font-family="monospace">Kural OK</text>
        <path d="M ${xs[2]} 214 L ${xs[4]} 214" stroke="#10b981" stroke-width="2" marker-end="url(#sOkGreen)" />
        <text x="${(xs[2] + xs[4]) / 2}" y="206" text-anchor="middle" fill="#34d399" font-size="9" font-family="monospace">Repository Port (ABC)</text>
        <path d="M ${xs[1]} 258 L ${xs[0]} 258" stroke="#10b981" stroke-width="2" marker-end="url(#sOkGreen)" />
        <text x="${(xs[1] + xs[0]) / 2}" y="250" text-anchor="middle" fill="#34d399" font-size="9" font-family="monospace">${htmlKacis(sonucYazi)}</text>
      `;

    alan.innerHTML = `
      <svg viewBox="0 0 510 310" role="img" aria-label="Sıralama Diyagramı">
        <defs>
          <marker id="sOkCyan" markerWidth="7" markerHeight="7" refX="5" refY="3" orient="auto"><path d="M0,0 L0,6 L6,3 z" fill="#22d3ee" /></marker>
          <marker id="sOkGreen" markerWidth="7" markerHeight="7" refX="5" refY="3" orient="auto"><path d="M0,0 L0,6 L6,3 z" fill="#10b981" /></marker>
          <marker id="sOkRed" markerWidth="7" markerHeight="7" refX="5" refY="3" orient="auto"><path d="M0,0 L0,6 L6,3 z" fill="#f43f5e" /></marker>
        </defs>
        ${basliklar}
        <path d="M ${xs[0]} 74 L ${xs[1]} 74" stroke="#22d3ee" stroke-width="2" marker-end="url(#sOkCyan)" />
        <text x="${(xs[0] + xs[1]) / 2}" y="66" text-anchor="middle" fill="#67e8f9" font-size="8.5" font-family="monospace">${htmlKacis(endpoint.slice(0, 18))}</text>
        <path d="M ${xs[1]} 108 L ${xs[2]} 108" stroke="#22d3ee" stroke-width="1.8" marker-end="url(#sOkCyan)" />
        <text x="${(xs[1] + xs[2]) / 2}" y="100" text-anchor="middle" fill="#a5b4fc" font-size="8.5" font-family="monospace">${htmlKacis(useCase.slice(0, 18))}</text>
        <path d="M ${xs[2]} 140 L ${xs[3]} 140" stroke="#f59e0b" stroke-width="1.8" marker-end="url(#sOkCyan)" />
        <text x="${(xs[2] + xs[3]) / 2}" y="132" text-anchor="middle" fill="#fcd34d" font-size="8.5" font-family="monospace">İş Kuralı Denetimi</text>
        ${altAkis}
      </svg>
    `;
  }

  async function astDenetimiCalistir(bildirimVer = true) {
    const iz = await istekGonder("/api/v1/mimari/ast-denetim", {}, !bildirimVer);
    if (!iz.basarili || !iz.veri) return;
    const r = iz.veri;
    kokpitDurumu.astRaporu = r;

    document.getElementById("ust-ast-durum").textContent = r.temiz ? "0 İhlal" : `${r.toplam_ihlal} İhlal`;
    document.getElementById("sekme-rozet-ast").textContent = r.temiz ? "TEMİZ" : "İHLAL";
    document.getElementById("ast-toplam-etiket").textContent = `${r.toplam_ihlal} Dış Bağımlılık İhlali`;
    document.getElementById("ast-rapor-baslik").textContent =
      `AST Bağımlılık Denetimi — ${r.toplam_dosya} Dosya, ${r.toplam_satir} Satır (${r.toplam_ihlal} İhlal)`;
    document.getElementById("ast-rapor-alt").textContent =
      `Python ast.parse taraması ${r.sure_ms} ms içinde tamamlandı.`;

    document.getElementById("ast-katman-ozet-rozetler").innerHTML = (r.katmanlar || [])
      .map((k) => `<span class="rozet ${k.durum === "TEMIZ" ? "ok" : "err"}">${htmlKacis(k.katman)}: ${k.dosya_sayisi} dosya · ${k.ihlal_sayisi} ihlal</span>`)
      .join("");

    document.getElementById("ast-dosya-govde").innerHTML = (r.dosyalar || [])
      .map(
        (d) => `
        <tr>
          <td style="font-family:var(--font-mono);color:var(--cyan)">${htmlKacis(d.dosya)}</td>
          <td><span class="rozet info">${htmlKacis(d.katman)}</span></td>
          <td style="font-family:var(--font-mono)">${d.satir_sayisi}</td>
          <td style="font-family:var(--font-mono);font-size:11px">${htmlKacis([...d.siniflar, ...d.fonksiyonlar].join(", ") || "—")}</td>
          <td style="font-family:var(--font-mono);font-size:11px;color:var(--emerald)">${htmlKacis([...d.ic_importlar, ...d.stdlib_importlar].join(", ") || "—")}</td>
          <td style="font-family:var(--font-mono);font-size:11px">${d.dis_importlar.length ? htmlKacis(d.dis_importlar.join(", ")) : '<span class="rozet ok">0 dış paket</span>'}</td>
          <td>${d.temiz ? '<span class="rozet ok">TEMİZ</span>' : `<span class="rozet err">${htmlKacis(d.ihlaller.join("; "))}</span>`}</td>
          <td><button type="button" class="btn btn-sm" data-kod-ac="${htmlKacis(d.dosya)}">Kodu Aç</button></td>
        </tr>
      `
      )
      .join("");

    const secici = document.getElementById("kod-dosya-secici");
    const yollar = [...(r.dosyalar || []).map((x) => x.dosya), "main.py"];
    secici.innerHTML = yollar.map((y) => `<option value="${htmlKacis(y)}">${htmlKacis(y)}</option>`).join("");
    const hedef = yollar.includes(kokpitDurumu.seciliKodDosyasi) ? kokpitDurumu.seciliKodDosyasi : yollar[0];
    await kaynakKodGoster(hedef, false);
    siralamaDiyagramiCiz();

    if (bildirimVer) {
      bildirimGoster("AST Denetimi Tamamlandı", `${r.toplam_dosya} dosya tarandı, ${r.toplam_ihlal} ihlal bulundu.`, "ok", iz.izId);
    }
  }

  async function kaynakKodGoster(dosyaYolu, sekmeyeGit = false) {
    kokpitDurumu.seciliKodDosyasi = dosyaYolu;
    if (sekmeyeGit) sekmeGecisYap("mimari");
    const secici = document.getElementById("kod-dosya-secici");
    if ([...secici.options].some((o) => o.value === dosyaYolu)) secici.value = dosyaYolu;

    const iz = await istekGonder(`/api/v1/mimari/kaynak-kod?dosya=${encodeURIComponent(dosyaYolu)}`, {}, true);
    if (!iz.basarili || !iz.veri) return;

    document.getElementById("kod-dosya-meta").textContent = `${iz.veri.katman} · ${iz.veri.satir_sayisi} satır`;
    const satirlar = iz.veri.icerik.split(/\r?\n/);
    document.getElementById("kod-satirlar-alani").innerHTML = satirlar
      .map(
        (satir, idx) =>
          `<div class="kod-satir"><span class="satir-no">${idx + 1}</span><span class="satir-kod">${htmlKacis(satir) || " "}</span></div>`
      )
      .join("");

    if (sekmeyeGit) {
      secici.scrollIntoView({ behavior: "smooth", block: "center" });
    }
  }

  // SEKME 4: LSP DEPO KARŞILAŞTIRMA & HTTP/JSON LOG KONSOLU
  function depoKarsilastirmaCiz() {
    const depolar = kokpitDurumu.mimariOzet?.depo_karsilastirma || [];
    const izgara = document.getElementById("lsp-karsilastirma-izgara");
    izgara.innerHTML = depolar
      .map(
        (d) => `
        <article class="lsp-kart ${d.aktif ? "aktif" : ""}">
          <div style="display:flex;justify-content:space-between;align-items:center;gap:8px">
            <strong style="font-size:14px;font-family:var(--font-mono)">${htmlKacis(d.sinif)}</strong>
            <span class="rozet ${d.aktif ? "ok" : "warn"}">${d.aktif ? "AKTİF ADAPTÖR" : "HAZIR BEKLİYOR"}</span>
          </div>
          <div style="font-size:12px;color:var(--text-muted)">Sözleşme: <code>${htmlKacis(d.sozlesme)}</code></div>
          <div style="font-size:12px;color:var(--text-muted)">Mekanizma: ${htmlKacis(d.mekanizma)}</div>
          <div style="font-size:12px;color:var(--text-muted)">Kalıcılık: ${htmlKacis(d.kalicilik)}</div>
          <div style="font-size:12px;color:var(--text-muted)">Eş Zamanlılık: ${htmlKacis(d.es_zamanlilik)}</div>
          <div style="margin-top:4px">
            <button type="button" class="btn ${d.aktif ? "btn-emerald" : "btn-cyan"} btn-sm" data-depo="${htmlKacis(d.repo_tipi)}" ${d.aktif ? "disabled" : ""}>
              ${d.aktif ? "Şu An Kullanımda" : "Bu Adaptöre Geç (DIP)"}
            </button>
          </div>
        </article>
      `
      )
      .join("");
  }

  async function izKayitlariniYukle(ciz = true) {
    const params = new URLSearchParams({ limit: "150" });
    if (kokpitDurumu.logSeviyeFiltresi) params.set("seviye", kokpitDurumu.logSeviyeFiltresi);
    const iz = await istekGonder(`/api/v1/mimari/izler?${params.toString()}`, {}, true);
    if (!iz.basarili || !iz.veri) return;
    kokpitDurumu.izKayitlari = iz.veri.kayitlar || [];
    document.getElementById("sekme-rozet-log").textContent = kokpitDurumu.izKayitlari.length;
    if (ciz || kokpitDurumu.aktifSekme === "loglar") {
      logKonsoluCiz();
    }
    if (kokpitDurumu.aktifSekme === "mimari") {
      siralamaDiyagramiCiz();
    }
  }

  function logKonsoluCiz() {
    const arama = kokpitDurumu.logAramaMetni.trim().toLowerCase();
    const liste = arama
      ? kokpitDurumu.izKayitlari.filter((k) =>
          [k.iz_id, k.yol, k.use_case, k.hata_kodu || "", k.mesaj || "", k.aktif_repository]
            .join(" ")
            .toLowerCase()
            .includes(arama)
        )
      : kokpitDurumu.izKayitlari;

    document.getElementById("log-adet-span").textContent = liste.length;
    const alan = document.getElementById("log-listesi-alani");

    if (!liste.length) {
      alan.innerHTML = `<div class="bos-sutun">Henüz eşleşen HTTP işlem kaydı yok. Yukarıdaki Hazır Demo Senaryolarından birini çalıştırın.</div>`;
      return;
    }

    if (!kokpitDurumu.seciliIzId || !liste.some((x) => x.iz_id === kokpitDurumu.seciliIzId)) {
      kokpitDurumu.seciliIzId = liste[0].iz_id;
    }

    alan.innerHTML = liste
      .map((k) => {
        const secili = k.iz_id === kokpitDurumu.seciliIzId ? "secili" : "";
        const durumRozet =
          k.seviye === "BASARILI"
            ? `<span class="rozet ok">HTTP ${k.durum_kodu}</span>`
            : `<span class="rozet err">HTTP ${k.durum_kodu} · ${htmlKacis(k.hata_kodu || k.seviye)}</span>`;
        return `
          <div class="log-kayit-kart ${secili}" data-iz-sec="${htmlKacis(k.iz_id)}">
            <div style="display:flex;justify-content:space-between;align-items:center;gap:8px;flex-wrap:wrap">
              <div style="display:flex;align-items:center;gap:6px;flex-wrap:wrap">
                <span class="uuid-tag">${htmlKacis(k.iz_id)}</span>
                <span class="metot-rozet metot-${htmlKacis(k.metot)}">${htmlKacis(k.metot)}</span>
                <span style="font-family:var(--font-mono);font-size:11px">${htmlKacis(k.yol)}</span>
              </div>
              <div style="display:flex;align-items:center;gap:6px">
                ${durumRozet}
                <span class="uuid-tag">${k.sure_ms.toFixed(2)} ms</span>
              </div>
            </div>
            <div style="display:flex;justify-content:space-between;font-size:11px;color:var(--text-muted);margin-top:5px;gap:8px;flex-wrap:wrap">
              <span><strong>${htmlKacis(k.use_case)}</strong> — ${htmlKacis(k.mesaj)}</span>
              <span style="font-family:var(--font-mono)">${htmlKacis(k.aktif_repository)} · ${htmlKacis(tarihBicimle(k.zaman))}</span>
            </div>
            <details class="json-detaylar">
              <summary>İstek &amp; Yanıt JSON Gövdesini Göster</summary>
              <div style="margin-top:6px">
                <span style="font-size:10.5px;color:var(--text-dim);font-family:var(--font-mono)">REQUEST BODY:</span>
                <pre class="json-pre">${htmlKacis(k.istek_govdesi ? JSON.stringify(k.istek_govdesi, null, 2) : "—")}</pre>
                <span style="font-size:10.5px;color:var(--text-dim);font-family:var(--font-mono)">RESPONSE BODY:</span>
                <pre class="json-pre">${htmlKacis(k.yanit_ozeti ? JSON.stringify(k.yanit_ozeti, null, 2) : "—")}</pre>
              </div>
            </details>
          </div>
        `;
      })
      .join("");

    seciliIzDetayCiz(kokpitDurumu.seciliIzId);
  }

  function seciliIzDetayCiz(izId) {
    const k = kokpitDurumu.izKayitlari.find((x) => x.iz_id === izId);
    const etiket = document.getElementById("secili-iz-etiket");
    const detay = document.getElementById("secili-iz-detay");
    if (!k) {
      etiket.textContent = "Seçilmedi";
      return;
    }

    etiket.textContent = k.iz_id;
    const adimlarHtml = (k.katman_zinciri || [])
      .map((a) => {
        const cls = a.durum === "OK" ? "ok" : a.durum === "IHLAL" ? "err" : "warn";
        return `
          <div style="display:flex;justify-content:space-between;align-items:center;padding:6px 9px;background:var(--bg-card);border:1px solid var(--border);border-radius:7px">
            <span><strong>${htmlKacis(a.katman)}</strong> · <span style="font-family:var(--font-mono);color:var(--text-muted)">${htmlKacis(a.bilesen)}</span></span>
            <span class="rozet ${cls}">${htmlKacis(a.durum)}</span>
          </div>
        `;
      })
      .join("");

    detay.innerHTML = `
      <div style="display:flex;flex-direction:column;gap:9px">
        <div style="display:flex;gap:6px;flex-wrap:wrap">
          <span class="rozet ${k.seviye === "BASARILI" ? "ok" : "err"}">${htmlKacis(k.seviye)}</span>
          <span class="rozet info">${htmlKacis(k.depo_sinifi)}</span>
          <span class="uuid-tag">${k.sure_ms.toFixed(2)} ms</span>
        </div>
        ${
          k.kaynak_dosya
            ? `<button type="button" class="btn btn-sm" data-kod-ac="${htmlKacis(k.kaynak_dosya)}" style="color:var(--cyan);align-self:flex-start">Kaynak Dosyayı Aç: ${htmlKacis(k.kaynak_dosya)}</button>`
            : ""
        }
        <div style="display:flex;flex-direction:column;gap:5px">${adimlarHtml}</div>
        <div>
          <strong style="font-size:11px;color:var(--text-main)">TAM İSTEK / YANIT JSON</strong>
          <pre class="json-pre">${htmlKacis(JSON.stringify({ istek: k.istek_govdesi, yanit: k.yanit_ozeti }, null, 2))}</pre>
        </div>
      </div>
    `;
  }

  function olaylariBagla() {
    document.querySelectorAll(".sekme-btn").forEach((btn) => {
      btn.addEventListener("click", () => sekmeGecisYap(btn.dataset.sekme));
    });

    document.getElementById("akis-loglara-git-btn").addEventListener("click", () => {
      if (kokpitDurumu.sonIslemIzi?.izId?.startsWith("TR-")) {
        kokpitDurumu.seciliIzId = kokpitDurumu.sonIslemIzi.izId;
      }
      sekmeGecisYap("loglar");
    });

    document.getElementById("baypas-anahtari").addEventListener("change", (e) => {
      baypasModuGuncelle(e.target.checked);
    });

    document.getElementById("ornek-veri-btn").addEventListener("click", async () => {
      const iz = await istekGonder("/api/v1/sistem/ornek-veri-yukle", { method: "POST" });
      if (iz.basarili && iz.veri) {
        bildirimGoster("Demo Verisi Yüklendi", iz.veri.mesaj, "ok", iz.izId);
        await gorevleriYukle(false);
      }
    });

    document.getElementById("yeni-gorev-btn").addEventListener("click", () => gorevModalAc(null));
    document.getElementById("modal-kapat-btn").addEventListener("click", gorevModalKapat);
    document.getElementById("modal-iptal-btn").addEventListener("click", gorevModalKapat);
    document.getElementById("gorev-form").addEventListener("submit", gorevFormuGonder);
    document.getElementById("cekmece-kapat-btn").addEventListener("click", () => {
      kokpitDurumu.cekmeceGorevId = null;
      document.getElementById("gorev-cekmece").classList.remove("acik");
    });

    document.getElementById("zehir-kisa-baslik-btn").addEventListener("click", () => {
      document.getElementById("form-baslik").value = "ab";
      bildirimGoster("Kısa Başlık Dolduruldu", "Şimdi API'ye Gönder'e basarak Domain GecersizBaslikHatasi (422) kanıtını görün.", "info");
    });
    document.getElementById("zehir-gecmis-tarih-btn").addEventListener("click", () => {
      document.getElementById("form-baslik").value = "Geçmiş Tarihli Baypas Görevi";
      const dun = new Date(Date.now() - 48 * 3600 * 1000);
      document.getElementById("form-bitis").value = datetimeLocalFormatla(dun.toISOString());
      bildirimGoster("Geçmiş Tarih Dolduruldu", "API'ye Gönder'e basarak BitisTarihi (422 GECMIS_TARIH) engellemesini görün.", "info");
    });

    let aramaZamanlayici = null;
    document.getElementById("filtre-arama").addEventListener("input", () => {
      clearTimeout(aramaZamanlayici);
      aramaZamanlayici = setTimeout(() => gorevleriYukle(true), 220);
    });
    document.getElementById("filtre-durum").addEventListener("change", () => gorevleriYukle(true));
    document.getElementById("filtre-oncelik").addEventListener("change", () => gorevleriYukle(true));
    document.getElementById("filtre-temizle-btn").addEventListener("click", () => {
      document.getElementById("filtre-arama").value = "";
      document.getElementById("filtre-durum").value = "";
      document.getElementById("filtre-oncelik").value = "";
      gorevleriYukle(false);
    });
    document.getElementById("gorev-yenile-btn").addEventListener("click", () => gorevleriYukle(false));

    document.getElementById("gorunum-kanban-btn").addEventListener("click", () => {
      kokpitDurumu.gorunumModu = "kanban";
      document.getElementById("gorunum-kanban-btn").classList.add("aktif");
      document.getElementById("gorunum-liste-btn").classList.remove("aktif");
      document.getElementById("kanban-alani").style.display = "grid";
      document.getElementById("liste-alani").style.display = "none";
    });
    document.getElementById("gorunum-liste-btn").addEventListener("click", () => {
      kokpitDurumu.gorunumModu = "liste";
      document.getElementById("gorunum-liste-btn").classList.add("aktif");
      document.getElementById("gorunum-kanban-btn").classList.remove("aktif");
      document.getElementById("kanban-alani").style.display = "none";
      document.getElementById("liste-alani").style.display = "block";
    });

    document.getElementById("lab-hepsini-test-et-btn").addEventListener("click", async () => {
      const btn = document.getElementById("lab-hepsini-test-et-btn");
      btn.disabled = true;
      btn.textContent = "Testler Çalıştırılıyor...";
      try {
        for (const no of [1, 2, 3, 4, 5]) {
          await kuralCanliTestEt(no);
        }
      } finally {
        btn.disabled = false;
        btn.textContent = "5 Zorunlu Kuralı Canlı Test Et";
      }
    });

    document.getElementById("ast-denetim-calistir-btn").addEventListener("click", () => astDenetimiCalistir(true));
    document.getElementById("kod-dosya-secici").addEventListener("change", (e) => kaynakKodGoster(e.target.value, false));

    document.querySelectorAll("[data-log-seviye]").forEach((btn) => {
      btn.addEventListener("click", () => {
        kokpitDurumu.logSeviyeFiltresi = btn.dataset.logSeviye;
        document.querySelectorAll("[data-log-seviye]").forEach((b) => b.classList.remove("aktif"));
        btn.classList.add("aktif");
        izKayitlariniYukle(true);
      });
    });

    document.getElementById("log-arama-input").addEventListener("input", (e) => {
      kokpitDurumu.logAramaMetni = e.target.value;
      logKonsoluCiz();
    });
    document.getElementById("log-canli-btn").addEventListener("click", (e) => {
      kokpitDurumu.canliIzlemeAcik = !kokpitDurumu.canliIzlemeAcik;
      e.target.textContent = kokpitDurumu.canliIzlemeAcik ? "Canlı İzleme: AÇIK" : "Canlı İzleme: KAPALI";
      e.target.className = kokpitDurumu.canliIzlemeAcik ? "btn btn-emerald btn-sm" : "btn btn-sm";
    });
    document.getElementById("log-yenile-btn").addEventListener("click", () => izKayitlariniYukle(true));
    document.getElementById("log-temizle-btn").addEventListener("click", async () => {
      const iz = await istekGonder("/api/v1/sistem/loglar", { method: "DELETE" });
      if (iz.basarili) {
        bildirimGoster("Loglar Temizlendi", iz.veri?.mesaj || "Tampon temizlendi.", "info", iz.izId);
        await izKayitlariniYukle(true);
      }
    });
    document.getElementById("log-indir-btn").addEventListener("click", () => {
      const blob = new Blob([JSON.stringify(kokpitDurumu.izKayitlari, null, 2)], { type: "application/json" });
      const url = URL.createObjectURL(blob);
      const a = document.createElement("a");
      a.href = url;
      a.download = `clean_arch_izler_${new Date().toISOString().slice(0, 19).replace(/[:T]/g, "-")}.json`;
      a.click();
      URL.revokeObjectURL(url);
    });

    document.body.addEventListener("click", async (e) => {
      const depoBtn = e.target.closest("[data-depo]");
      if (depoBtn && !depoBtn.disabled) {
        await depoAdaptoruDegistir(depoBtn.dataset.depo);
        return;
      }

      const demoBtn = e.target.closest("[data-demo]");
      if (demoBtn) {
        await hazirDemoCalistir(demoBtn.dataset.demo);
        return;
      }

      const islemBtn = e.target.closest("[data-islem]");
      if (islemBtn) {
        const islem = islemBtn.dataset.islem;
        const id = islemBtn.dataset.id;
        if (islem === "durum") {
          const iz = await istekGonder(`/api/v1/gorevler/${encodeURIComponent(id)}/durum`, {
            method: "PATCH",
            body: { yeni_durum: islemBtn.dataset.hedef },
          });
          if (iz.basarili) {
            bildirimGoster("Durum Değişti", `Yeni durum: ${islemBtn.dataset.hedef}`, "ok", iz.izId);
            await gorevleriYukle(false);
          } else {
            bildirimGoster(`Domain Kuralı (${iz.domainHataKodu || iz.durumKodu})`, iz.veri?.mesaj || "Geçiş engellendi.", "err", iz.izId);
          }
        } else if (islem === "kilit") {
          const iz = await istekGonder(`/api/v1/gorevler/${encodeURIComponent(id)}`, {
            method: "PUT",
            body: { baslik: "Tamamlanmış Görev Değişim Denemesi" },
          });
          bildirimGoster(`Kilit Kuralı (${iz.domainHataKodu || iz.durumKodu})`, iz.veri?.mesaj || "Salt okunur.", "err", iz.izId);
        } else if (islem === "sil") {
          const iz = await istekGonder(`/api/v1/gorevler/${encodeURIComponent(id)}`, { method: "DELETE" });
          if (iz.basarili) {
            bildirimGoster("Görev Silindi", "Kayıt silindi.", "ok", iz.izId);
            await gorevleriYukle(false);
          } else {
            bildirimGoster(`Domain Koruması (${iz.domainHataKodu || iz.durumKodu})`, iz.veri?.mesaj || "Silinemedi.", "err", iz.izId);
          }
        } else if (islem === "duzenle") {
          gorevModalAc(id);
        } else if (islem === "detay") {
          gorevDetayCekmecesiAc(id);
        }
        return;
      }

      const kuralTestBtn = e.target.closest("[data-kural-test]");
      if (kuralTestBtn) {
        await kuralCanliTestEt(Number(kuralTestBtn.dataset.kuralTest));
        return;
      }

      const matrisBtn = e.target.closest("[data-matris-kaynak]");
      if (matrisBtn) {
        await matrisHucresiTestEt(matrisBtn.dataset.matrisKaynak, matrisBtn.dataset.matrisHedef);
        return;
      }

      const halkaEl = e.target.closest("[data-halka-katman]");
      if (halkaEl) {
        halkaDosyalariniGoster(halkaEl.dataset.halkaKatman);
        return;
      }

      const kodBtn = e.target.closest("[data-kod-ac]");
      if (kodBtn) {
        await kaynakKodGoster(kodBtn.dataset.kodAc, true);
        return;
      }

      const izRow = e.target.closest("[data-iz-sec]");
      if (izRow) {
        kokpitDurumu.seciliIzId = izRow.dataset.izSec;
        logKonsoluCiz();
      }
    });
  }

  async function kokpitBaslat() {
    olaylariBagla();
    baypasModuGuncelle(false);
    await Promise.all([
      sistemBilgisiYukle(),
      mimariOzetYukle(),
      gorevleriYukle(false),
      astDenetimiCalistir(false),
      izKayitlariniYukle(false),
    ]);

    setInterval(() => {
      if (kokpitDurumu.canliIzlemeAcik) {
        sistemBilgisiYukle().catch(() => {});
        if (kokpitDurumu.aktifSekme === "loglar") {
          izKayitlariniYukle(true).catch(() => {});
        }
      }
    }, 3500);
  }

  document.addEventListener("DOMContentLoaded", kokpitBaslat);
})();
