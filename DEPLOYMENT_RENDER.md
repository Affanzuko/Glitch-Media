# Panduan Deployment Glitch Media (Gratis via Render + Aiven)

Arsitektur aplikasi ini menggunakan `threading.Thread` dan butuh waktu eksekusi panjang untuk LLM. Oleh karena itu, platform Serverless (Vercel/Netlify) **tidak cocok**. Solusi gratis terbaik adalah **Render (Web Service)** dikombinasikan dengan **Aiven (MySQL)**.

---

## Tahap 1: Siapkan Database MySQL Gratis (Aiven)
1. Daftar di [Aiven.io](https://aiven.io/).
2. Buat project baru, pilih **MySQL**.
3. Pilih plan **Free** (tersedia di region tertentu).
4. Setelah database dibuat, cari **Service URI** (Connection String).
5. Formatnya: `mysql+pymysql://user:password@host:port/defaultdb`. Simpan URL ini.

---

## Tahap 2: Persiapan Kode
Kode sudah disiapkan. Pastikan:
1. `gunicorn` sudah ada di `requirements.txt`.
2. File `render.yaml` sudah ada di root project.
3. Push semua kode ke GitHub (pastikan `.env` tidak ikut ter-push).

---

## Tahap 3: Deploy ke Render
1. Daftar/Login ke [Render.com](https://render.com/) menggunakan akun GitHub.
2. Klik **New** > **Web Service**.
3. Hubungkan repository GitHub `glitch-media` kamu.
4. Konfigurasi (jika tidak otomatis terdeteksi):
   - **Name**: glitch-media
   - **Environment**: Python 3
   - **Build Command**: `pip install -r requirements.txt`
   - **Start Command**: `gunicorn backend.app:app --bind 0.0.0.0:$PORT --timeout 120`
   - **Instance Type**: Free
5. Buka bagian **Environment Variables** dan masukkan isi `.env` kamu:
   - `DATABASE_URL` = (URL dari Aiven di Tahap 1)
   - `LLM_PROVIDER` = `cloud`
   - `DASHSCOPE_API_KEY` = (Key kamu)
   - `DASHSCOPE_BASE_URL` = `https://ws-g7x89ret3ana07j0.ap-southeast-1.maas.aliyuncs.com/compatible-mode/v1`
   - `IMAGE_GEN_API_KEY` = (Key kamu)
   - `IMAGE_GEN_DASHSCOPE_URL` = `https://ws-g7x89ret3ana07j0.ap-southeast-1.maas.aliyuncs.com/api/v1/services/aigc/image-generation/generation`
   - `X_OAUTH_REDIRECT_URI` = `https://glitch-media.onrender.com/callback/x`
   - `IG_OAUTH_REDIRECT_URI` = `https://glitch-media.onrender.com/callback/ig`
   - *(Masukkan juga API Key Twitter, IG, Reddit, dll)*
6. Klik **Create Web Service**. Tunggu proses build selesai.

---

## Tahap 4: Update OAuth Redirect URI
Setelah aplikasi live di `https://glitch-media.onrender.com`:
1. Buka **Twitter Developer Portal**, ubah Callback URI menjadi `https://glitch-media.onrender.com/callback/x`.
2. Buka **Facebook/Instagram Developer**, ubah Valid OAuth Redirect URIs menjadi `https://glitch-media.onrender.com/callback/ig`.

---

## Catatan Penting (Limitasi Free Tier Render)
1. **Sleep Mode:** Server akan "tidur" jika tidak ada traffic selama 15 menit. Saat diakses kembali, butuh waktu ~50 detik untuk bangun.
2. **Ephemeral Storage:** File gambar di `data/images/` akan terhapus setiap kali server restart/tidur. Gambar akan berhasil di-upload ke IG, tapi thumbnail di menu History mungkin akan hilang (broken link) setelah server restart.