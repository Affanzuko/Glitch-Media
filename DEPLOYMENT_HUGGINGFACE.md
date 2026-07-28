# Panduan Deployment Glitch Media (Gratis via Hugging Face Spaces)

Hugging Face Spaces (Docker) adalah alternatif yang sangat baik untuk Render. Space gratis (CPU basic) akan terus menyala dan baru akan *sleep* jika tidak ada aktivitas selama 48 jam. Karena berbasis Docker, background thread (`threading.Thread`) akan berjalan normal.

---

## Tahap 1: Siapkan Database MySQL Gratis (Aiven)
Sama seperti Render, Hugging Face tidak menyediakan database.
1. Daftar di [Aiven.io](https://aiven.io/).
2. Buat project baru, pilih **MySQL** (Free Plan).
3. Dapatkan **Service URI** (Connection String).
4. Formatnya: `mysql+pymysql://user:password@host:port/defaultdb`. Simpan URL ini.

---

## Tahap 2: Persiapan Kode
Kode sudah disiapkan. Pastikan:
1. File `Dockerfile` sudah ada di root project.
2. `gunicorn` sudah ada di `requirements.txt`.

---

## Tahap 3: Buat Space di Hugging Face
1. Daftar/Login ke [Hugging Face](https://huggingface.co/).
2. Klik foto profil di kanan atas > **New Space**.
3. Isi form:
   - **Space name**: `glitch-media` (atau nama lain).
   - **License**: Pilih sesuai keinginan (misal: MIT).
   - **Select the Space SDK**: Pilih **Docker**.
   - **Choose a Docker template**: Pilih **Blank**.
   - **Space hardware**: Pilih **CPU basic - 2 vCPU · 16 GB · Free**.
   - **Visibility**: Pilih **Private** (sangat disarankan agar kode dan data aman).
4. Klik **Create Space**.

---

## Tahap 4: Upload Kode ke Hugging Face
Hugging Face Space pada dasarnya adalah Git repository. Kamu bisa upload kode dengan dua cara:

### Cara A: Via Browser (Mudah)
1. Di halaman Space kamu, klik tab **Files**.
2. Klik **Add file** > **Upload files**.
3. Upload semua file dan folder proyekmu (kecuali `.venv`, `__pycache__`, `.git`, dan `.env`).
4. Pastikan `Dockerfile` dan `requirements.txt` ada di root.

### Cara B: Via Git CLI (Direkomendasikan)
1. Clone repository Space kamu:
   ```bash
   git clone https://huggingface.co/spaces/username/glitch-media
   ```
2. Copy semua file proyekmu ke dalam folder hasil clone tersebut.
3. Commit dan push:
   ```bash
   git add .
   git commit -m "Initial commit"
   git push
   ```

---

## Tahap 5: Konfigurasi Environment Variables (Secrets)
Jangan pernah meng-upload file `.env` ke Hugging Face. Gunakan fitur Secrets.
1. Di halaman Space kamu, klik tab **Settings**.
2. Scroll ke bawah ke bagian **Variables and secrets**.
3. Klik **New secret** dan tambahkan semua variabel dari `.env` kamu satu per satu:
   - `DATABASE_URL` = (URL dari Aiven di Tahap 1)
   - `LLM_PROVIDER` = `cloud`
   - `DASHSCOPE_API_KEY` = (Key kamu)
   - `DASHSCOPE_BASE_URL` = `https://ws-g7x89ret3ana07j0.ap-southeast-1.maas.aliyuncs.com/compatible-mode/v1`
   - `IMAGE_GEN_API_KEY` = (Key kamu)
   - `IMAGE_GEN_DASHSCOPE_URL` = `https://ws-g7x89ret3ana07j0.ap-southeast-1.maas.aliyuncs.com/api/v1/services/aigc/image-generation/generation`
   - `X_OAUTH_REDIRECT_URI` = `https://username-glitch-media.hf.space/callback/x`
   - `IG_OAUTH_REDIRECT_URI` = `https://username-glitch-media.hf.space/callback/ig`
   - *(Masukkan juga API Key Twitter, IG, Reddit, dll)*

*Catatan: URL aplikasi Hugging Face biasanya berformat `https://username-spacename.hf.space`.*

---

## Tahap 6: Build & Run
1. Setelah kode di-upload dan Secrets diatur, Hugging Face akan otomatis mem-build Docker image.
2. Kamu bisa melihat prosesnya di tab **Build**.
3. Jika berhasil, status akan berubah menjadi **Running**.
4. Buka URL Space kamu (biasanya ada tombol "App" atau URL langsung di atas).

---

## Tahap 7: Update OAuth Redirect URI
Setelah aplikasi live:
1. Buka **Twitter Developer Portal**, ubah Callback URI menjadi `https://username-glitch-media.hf.space/callback/x`.
2. Buka **Facebook/Instagram Developer**, ubah Valid OAuth Redirect URIs menjadi `https://username-glitch-media.hf.space/callback/ig`.

---

## Catatan Penting (Limitasi Hugging Face Spaces)
1. **Ephemeral Storage:** Sama seperti Render, file gambar di `data/images/` akan terhapus setiap kali Space restart atau bangun dari tidur. Gambar akan berhasil di-upload ke IG, tapi thumbnail di menu History mungkin akan hilang (broken link) setelah restart.
2. **Port:** Hugging Face Spaces secara default mengekspos port `7860`. Ini sudah diatur di dalam `Dockerfile`.
