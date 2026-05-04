# Adıyaman Üniversitesi Yapay Zeka Sohbet Asistanı

Bu proje, Adıyaman Üniversitesi resmi web sitesini (www.adiyaman.edu.tr) RAG mimarisi ile sadece kendi kapsamı dahilinde tarayıp bilgi sunan yapay zeka asistanıdır.

## ✨ Özellikler

* **Kapalı Kapsam (Closed Domain)**: Asistan sadece üniversite hakkında bilgi verir. Spor, siyaset, genel kültür gibi konularda bilgi vermez.
* **Otomatik Crawler**: Recursive crawler algoritması ile siteyi tarar.
* **Akıllı Parçalama**: Metinleri tokenlaştırıp vektör veritabanına atar.
* **Vektör Veritabanı**: FAISS kullanarak hızlı benzerlik algoritmaları çalıştırır.
* **Zamanlanmış Tarama**: APScheduler kullanılarak periyodik site güncellemeleri kontrol edilir.
* **Hızlı API**: Google Gemini 1.5 Flash (en hızlı ve cömert ücretsiz tarifelerden) entegrasyonu kullanır.
* **Şık ve Dinamik Arayüz**: Vanilla CSS, animasyonlar ve Next.js/Vite kullanılarak oluşturulmuş responsive sohbet penceresi.
* **Loglama**: Sorulan sorular arka planda SQLite'da kaydedilir.
* **Admin Kontrolü**: Admin endpointleri üzerinden veritabanı sıfırlanıp site yeniden taranabilir.

---

## 🚀 Kurulum

Projeyi çalıştırmak için aşağıdaki adımları izleyin:

### Backend Kurulumu

1. `backend` dizinine gidin:
   ```bash
   cd backend
   ```

2. Virtual environment oluşturun ve aktif edin:
   ```bash
   python -m venv venv
   # Windows (Powershell):
   .\venv\Scripts\Activate.ps1
   # Mac/Linux:
   source venv/bin/activate
   ```

3. Gerekli kütüphaneleri yükleyin:
   ```bash
   pip install -r requirements.txt
   ```

4. `.env` dosyasını yapılandırın:
   `backend/.env` dosyasına gidin ve ücretsiz olarak edindiğiniz API anahtarını ekleyin. (Örn: Google AI Studio üzerinden aldığınız GEMINI_API_KEY)
   ```env
   GEMINI_API_KEY=your_google_studio_api_key_here
   ```

5. Backend sunucusunu başlatın:
   ```bash
   uvicorn main:app --reload
   ```
   Backend şu adreste çalışır: `http://localhost:8000`

### Ön Uç (Frontend) Kurulumu

1. Yeni bir terminalde `frontend` dizinine gidin:
   ```bash
   cd frontend
   ```

2. Node.js paketlerini yükleyin:
   ```bash
   npm install
   ```

3. Frontend sunucusunu başlatın:
   ```bash
   npm run dev
   ```
   Frontend genellikle şu adreste çalışır: `http://localhost:5173/`

---

## 🛠️ API Kullanımı (Admin İşlemleri)

* **Yeniden Tarama Başlatma (Crawler)**:
  `POST http://localhost:8000/admin/recrawl`

* **Logları Görüntüleme**:
  `GET http://localhost:8000/admin/logs?limit=50`

---

## 📝 Öncelikli Uyarılar
* Crawler default olarak sonsuz bir döngüde çalışmaması için MAX_PAGES ile sınırlandırılmıştır (`scraper.py`). Kendi kullanımınızda gereksiniminize göre sayıyı arttırabilirsiniz.
* Uygulamada TailwindCSS kullanılmamış olup, tamamen Vanilla CSS ile animasyonlar ve tasarım oluşturulmuştur.
