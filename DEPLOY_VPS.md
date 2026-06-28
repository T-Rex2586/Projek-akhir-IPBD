# 🚀 Panduan Lengkap Deploy Crypto Pipeline ke VPS

Panduan ini akan membantu Anda memindahkan seluruh proyek *Bitcoin Analytics Pipeline* dari komputer lokal ke VPS (Virtual Private Server) agar bisa berjalan 24/7 tanpa henti.

## 📋 1. Kebutuhan Sistem VPS
- **OS**: Ubuntu 22.04 LTS / 24.04 LTS (Direkomendasikan)
- **RAM**: Minimal 2GB (Sangat direkomendasikan 4GB karena kita menggunakan PostgreSQL & Kafka)
- **CPU**: Minimal 2 Core

---

## 🛠️ 2. Persiapan Server (Install Dependencies)
Masuk ke VPS Anda melalui SSH, lalu jalankan perintah-perintah berikut untuk menginstal hal-hal yang dibutuhkan:

```bash
# 1. Update sistem
sudo apt update && sudo apt upgrade -y

# 2. Install Python 3.11, Git, dan tools dasar
sudo apt install software-properties-common -y
sudo add-apt-repository ppa:deadsnakes/ppa -y
sudo apt update
sudo apt install python3.11 python3.11-venv python3.11-dev python3-pip git curl -y

# 3. Install Docker & Docker Compose
sudo apt install docker.io docker-compose -y
sudo systemctl enable --now docker
sudo usermod -aG docker $USER

# 4. Install Node.js (Untuk build dashboard) & PM2 (Untuk menjaga script tetap hidup)
curl -fsSL https://deb.nodesource.com/setup_20.x | sudo -E bash -
sudo apt install nodejs -y
sudo npm install -g pm2
```

---

## 📥 3. Clone Repository & Setup
Ambil kode Anda dari GitHub (karena sudah kita push sebelumnya):

```bash
# Clone repo (Ganti URL dengan link repo GitHub Anda)
git clone https://github.com/T-Rex2586/Projek-akhir-IPBD.git
cd Projek-akhir-IPBD

# Buat Virtual Environment Python 3.11
python3.11 -m venv venv
source venv/bin/activate

# Install requirements Python
pip install -r requirements.txt

# Copy .env dan isi dengan Token Telegram Anda
cp .env.example .env
nano .env # Edit file ini, masukkan TELEGRAM_BOT_TOKEN dan TELEGRAM_CHAT_ID
```

---

## 🏗️ 4. Nyalakan Database & Backend
Sekarang kita mulai menyalakan mesin utamanya:

```bash
# 1. Nyalakan Docker (PostgreSQL, Kafka, MinIO)
docker-compose up -d

# 2. Inisialisasi Tabel Database
python -c "from storage.db_models import init_db; init_db()"
```

---

## 🖥️ 5. Build Dashboard React (Frontend)
Alih-alih menggunakan `npm run dev` yang memakan banyak memori, di VPS kita harus mem-build React menjadi file statis agar sangat ringan.

```bash
cd dashboard
npm install
npm run build
cd ..
```

---

## 🏃 6. Jalankan Semua Script dengan PM2
Agar script Python (scraper, websocket, API) tidak mati saat Anda menutup terminal SSH, kita gunakan **PM2**.

```bash
# Pastikan Anda berada di root folder proyek (Projek-akhir-IPBD)
# dan pastikan virtual environment aktif: source venv/bin/activate

# 1. Jalankan API Server (FastAPI)
pm2 start "python -m api.main" --name "crypto-api"

# 2. Jalankan Data Ingestion (WebSocket Binance)
pm2 start "python ingestion/binance_websocket.py" --name "binance-ws"

# 3. Jalankan Gold Processor (Untuk Divergence & Aggregation)
pm2 start "python processing/gold_processor.py" --name "gold-processor"

# 4. Jalankan Telegram Bot
pm2 start "python start_telegram_bot.py" --name "telegram-bot"

# 5. Jalankan RSS News Scraper
pm2 start "python ingestion/rss_batch.py --mode continuous" --name "news-scraper"

# 6. Serve Dashboard React di port 5173
pm2 start "npx serve -s dashboard/dist -l 5173" --name "dashboard-ui"

# 7. Simpan konfigurasi PM2 agar otomatis nyala kalau VPS di-restart
pm2 save
pm2 startup
```

---

## 🎯 7. Cara Mengakses Aplikasi Anda
Aplikasi Anda sekarang sudah online! Anda bisa mengaksesnya melalui IP VPS Anda:

- **Dashboard UI**: `http://<IP_VPS_ANDA>:5173`
- **API Docs**: `http://<IP_VPS_ANDA>:8001/docs`

> [!TIP] 
> Jika halaman tidak bisa dibuka, pastikan **Firewall (UFW)** atau **Security Group** (jika pakai AWS/DigitalOcean) di VPS Anda sudah mengizinkan koneksi masuk (*Inbound Rules*) untuk port **5173** dan **8001**.
> Cara buka port di Ubuntu (UFW):
> `sudo ufw allow 5173/tcp`
> `sudo ufw allow 8001/tcp`

## 🕹️ Command PM2 yang Berguna
- `pm2 status` : Melihat status semua script yang berjalan.
- `pm2 logs` : Melihat log/output dari semua script.
- `pm2 logs telegram-bot` : Melihat log khusus telegram bot.
- `pm2 restart all` : Merestart semua script.

Selamat! Proyek Anda sekarang sepenuhnya online 24/7 dan bot Telegram Anda akan siap mengirimi notifikasi Whale Trade kapan saja! 🚀
