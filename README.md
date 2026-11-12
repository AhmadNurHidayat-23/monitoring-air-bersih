# Monitoring Air Bersih

Pemantauan fasilitas penyediaan air bersih. Prototipe portofolio independen, bukan aplikasi resmi pemerintah.

## Fitur utama

- CRUD lokasi/fasilitas, kategori sumur/pompa/reservoir/jaringan distribusi, kapasitas beserta satuan, arsip/pemulihan.
- Inspeksi operasional bertanggal, riwayat gangguan, progres perbaikan tercatat dan riwayat pemeliharaan.
- Jadwal rutin, status pelaksanaan/tanggal selesai aktual, pencarian/filter dan CSV pemantauan.
- Admin mengelola inventaris serta jadwal; Admin/Petugas mencatat inspeksi, gangguan dan perbaikan. Status operasional bukan pernyataan air aman diminum.

## Teknologi

Python 3.13, FastAPI, Jinja2, Uvicorn, SQLite, HTML, CSS, JavaScript.

## Cara instalasi

~~~powershell
cd C:\laragon\www\monitoring-air-bersih
py -3.13 -m venv .venv
.venv\Scripts\python -m pip install -r requirements.txt
.venv\Scripts\python -m core.users --role Admin
~~~

Ulangi dengan --role Petugas. Kata sandi melalui prompt; tidak ada akun bawaan.

## Cara menjalankan

~~~powershell
.venv\Scripts\python run.py
~~~

Buka http://127.0.0.1:5501. SQLite instance/app.sqlite dibuat otomatis dan aman diinisialisasi ulang. APP_INSTANCE mengganti lokasi; SECURE_COOKIE=1 untuk HTTPS. Tes: .venv\Scripts\python -m pytest -q. Tanggal mengikuti WIB. Status inspeksi dan perbaikan mengikuti tanggal terbaru lalu urutan catatan. Perbaikan 100% menutup gangguan, tetapi tidak mengubah hasil inspeksi atau menyatakan kualitas air. Aplikasi tidak memuat hasil laboratorium. Gunakan data demonstrasi.
