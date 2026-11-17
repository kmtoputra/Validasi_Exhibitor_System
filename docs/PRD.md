# Product Requirements Document (PRD)

## Nimble Vibe Prospecting System (MVP Edition)

- **Perusahaan:** PT Generator Pasifik Indonesia (GPI)
- **Fokus dokumen:** Minimum Viable Product (MVP), core flow

## 1. Ringkasan Eksekutif

Dokumen ini mendefinisikan spesifikasi untuk Nimble Vibe Prospecting System versi MVP. Fokus utama sistem ini adalah menyediakan alat yang sangat praktis dengan prinsip kerja: **"Masuk data mentah, keluar data bersih."** Sistem menghilangkan proses manual dengan mengotomatisasi pembersihan dan validasi data eksibitor tanpa perlu navigasi yang rumit.

## 2. Alur Pengguna Inti (Core User Journey)

Sistem dirancang dengan alur tiga langkah linier yang sangat cepat:

1. **Drop File:** Pengguna menarik dan melepaskan (drag-and-drop) file .xlsx atau .csv berisi daftar prospek mentah ke area unggah di halaman utama sistem.
2. **Automated Processing:** Begitu file dijatuhkan, sistem langsung membaca file dan menjalankan algoritma di latar belakang untuk mendeteksi duplikat, memvalidasi email, dan merapikan format data (tanpa perlu intervensi pengguna).
3. **Download Hasil:** Segera setelah pemrosesan selesai, sistem langsung menampilkan tombol unduh. Pengguna mengklik tombol tersebut untuk mendapatkan file Excel baru yang sudah divalidasi dan siap pakai.

## 3. Kebutuhan Fungsional (Functional Requirements)

- **Modul Unggah Sederhana:** Komponen UI tunggal di tengah layar yang secara eksklusif menerima format Excel/CSV.
- **Mesin Validasi Otomatis:**
  - Menghapus baris yang kosong (null).
  - Mengidentifikasi duplikasi prospek berdasarkan kolom "Nama Perusahaan" atau "Email" di dalam file tersebut.
  - Memvalidasi format email standar menggunakan Regex.
- **Modul Unduh Instan:** Menghasilkan file keluaran Excel yang persis seperti input awal, namun dengan tambahan dua kolom ekstra: "Status" (Valid/Invalid/Duplikat) dan "Keterangan" (alasan kenapa invalid, misal: 'Format email salah').

## 4. Transformasi Data (Input ke Output)

| Kolom Input Wajib | Pemeriksaan Sistem (Blackbox) | Hasil pada File Output |
|---|---|---|
| Nama Perusahaan | Cek duplikasi internal di dalam file. | Data tetap ada. Jika ganda, baris kedua ditandai 'Duplikat' pada kolom Status. |
| Email | Cek struktur penulisan (harus mengandung @ dan domain yang sah). | Data tetap ada. Jika salah penulisan, ditandai 'Invalid' pada kolom Status. |
| (Semua Kolom Lainnya) | Tidak ada validasi khusus, hanya dirapikan spasi berlebihnya. | Dipertahankan persis seperti aslinya agar konteks data tidak hilang. |

Catatan tambahan: website validasi.

## 5. Spesifikasi Teknis (Tech Stack)

Untuk memastikan proses validasi berjalan cepat (kurang dari 10 detik per file) dan mudah diimplementasikan, sistem MVP ini akan dibangun menggunakan:

- **Antarmuka (Frontend):** Streamlit, yang sangat ideal untuk membangun UI drag-and-drop file dan menyediakan tombol unduh interaktif dengan cepat.
- **Logika Pemrosesan (Backend):** Python, dengan mengandalkan fungsi manipulasi data dari pustaka Pandas. Pandas mampu melakukan validasi regex, penghapusan baris kosong, dan pengecekan duplikat dalam hitungan sepersekian detik (vektorisasi data).
