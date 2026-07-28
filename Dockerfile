# Gunakan image Python resmi
FROM python:3.10-slim

# Set working directory
WORKDIR /app

# Install dependensi sistem yang mungkin dibutuhkan
RUN apt-get update && apt-get install -y \
    build-essential \
    && rm -rf /var/lib/apt/lists/*

# Copy requirements dan install
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy seluruh kode aplikasi
COPY . .

# Buat folder data jika belum ada
RUN mkdir -p data/images data/captions data/checkpoints data/filtered data/raw logs

# Set environment variable untuk port (Hugging Face Spaces menggunakan port 7860 secara default)
ENV PORT=7860
EXPOSE 7860

# Jalankan aplikasi menggunakan Gunicorn
CMD ["gunicorn", "backend.app:app", "--bind", "0.0.0.0:7860", "--timeout", "120"]
