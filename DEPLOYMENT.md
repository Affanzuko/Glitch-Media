# Panduan Deployment Glitch Media ke cPanel via Git

Panduan ini menjelaskan cara melakukan deployment aplikasi Glitch Media (Flask + MySQL) ke cPanel menggunakan fitur **Git Version Control**.

---

## Tahap 1: Persiapan Database di cPanel (MySQL)

1. Login ke cPanel.
2. Buka menu **MySQL® Databases**.
3. Buat database baru (misal: `u1234567_glitch_media`).
4. Buat user MySQL baru beserta passwordnya (misal: `u1234567_glitch_user`).
5. Tambahkan user tersebut ke database yang baru dibuat, dan centang **ALL PRIVILEGES**.
6. Simpan informasi nama database, username, dan password ini untuk file `.env` nanti.

---

## Tahap 2: Setup Git Repository di cPanel

1. Di cPanel, cari menu **Git Version Control**.
2. Klik tombol **Create**.
3. Isi form berikut:
   - **Clone URL**: Masukkan URL repository Git kamu (misal: `https://github.com/username/glitch-media.git`).
   - **Repository Path**: Isi dengan path folder di luar `public_html` untuk keamanan. Misal: `glitch-media`.
   - **Repository Name**: Bebas, misal `Glitch Media Repo`.
4. Klik **Create**. cPanel akan mengkloning repository kamu ke server.

---

## Tahap 3: Setup Python App (Phusion Passenger)

1. Di cPanel, cari menu **Setup Python App**.
2. Klik **Create Application**.
3. Isi form konfigurasi:
   - **Python version**: Pilih versi `3.10` atau yang lebih baru.
   - **Application root**: Isi dengan nama folder repository tadi (misal: `glitch-media`).
   - **Application URL**: Pilih domain atau subdomain tempat aplikasi akan diakses.
   - **Application startup file**: Isi dengan `passenger_wsgi.py`.
   - **Application Entry point**: Isi dengan `application`.
4. Klik **Create**.

---

## Tahap 4: Konfigurasi Environment Variables (`.env`)

Karena file `.env` biasanya di-ignore oleh Git, kamu harus membuatnya secara manual di server.

1. Buka menu **File Manager** di cPanel.
2. Masuk ke folder repository kamu (`/home/username/glitch-media`).
3. Buat file baru bernama `.env`.
4. Copy isi dari `.env.example` di lokal kamu, lalu paste ke file `.env` di server.
5. **Ubah konfigurasi penting berikut di `.env` server:**
   
   ```dotenv
   # 1. Database URL (Ganti dengan info dari Tahap 1)
   DATABASE_URL=mysql+pymysql://u1234567_glitch_user:password_kamu@localhost:3306/u1234567_glitch_media

   # 2. LLM Provider (Pastikan menggunakan cloud)
   LLM_PROVIDER=cloud

   # 3. API Keys (Isi dengan key asli)
   DASHSCOPE_API_KEY=sk-xxxxxx
   IMAGE_GEN_API_KEY=sk-xxxxxx

   # 4. OAuth Redirect URIs (Ganti localhost dengan domain kamu)
   X_OAUTH_REDIRECT_URI=https://domainkamu.com/callback/x
   IG_OAUTH_REDIRECT_URI=https://domainkamu.com/callback/ig
   ```
6. Simpan file `.env`.

---

## Tahap 5: Install Dependencies (Requirements)

1. Kembali ke menu **Setup Python App**.
2. Edit aplikasi yang baru kamu buat.
3. Scroll ke bagian **Configuration files**.
4. Di kolom "Add another file", ketik `requirements.txt` lalu klik **Add**.
5. Klik tombol **Run Pip Install**.
6. Tunggu hingga proses instalasi selesai (mungkin memakan waktu beberapa menit).

---

## Tahap 6: Restart & Testing

1. Di halaman **Setup Python App**, klik tombol **Restart** pada aplikasimu.
2. Buka domain/subdomain kamu di browser.
3. Aplikasi Glitch Media seharusnya sudah berjalan.
4. Database tabel akan otomatis terbuat saat aplikasi pertama kali dijalankan (karena ada perintah `Base.metadata.create_all(bind=engine)` di `backend/app.py`).

---

## Cara Update Kode (Deployment Lanjutan)

Jika kamu melakukan perubahan kode di lokal dan sudah di-push ke GitHub/GitLab:

1. Buka menu **Git Version Control** di cPanel.
2. Klik tombol **Manage** pada repository kamu.
3. Klik tab **Pull or Deploy**.
4. Klik tombol **Update from Remote**.
5. Buka menu **Setup Python App** dan klik **Restart** pada aplikasimu.
