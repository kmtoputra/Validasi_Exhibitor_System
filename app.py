import io
import re
from datetime import datetime
from typing import Callable, Optional

import pandas as pd
import requests
import streamlit as st

try:
    import pycountry
    HAS_PYCOUNTRY = True
except ImportError:
    HAS_PYCOUNTRY = False


st.set_page_config(
    page_title="GPI Exhibitor Data Validator",
    page_icon="✅",
    layout="centered",
)

EMAIL_REGEX = re.compile(r"^[A-Za-z0-9._%+\-]+@[A-Za-z0-9.\-]+\.[A-Za-z]{2,}$")

COMPANY_COL_CANDIDATES = ["nama perusahaan", "nama_perusahaan", "company", "company name"]
COMPANY_COL_CONTAINS = ["nama perusahaan", "company", "exhibitor", "organisasi", "organization"]

EMAIL_COL_CANDIDATES = ["email", "e-mail", "email address"]
EMAIL_COL_CONTAINS = ["email", "e-mail"]

COUNTRY_COL_CANDIDATES = ["negara", "country", "negara asal", "country name", "country/region"]
COUNTRY_COL_CONTAINS = ["negara", "country"]

SECTOR_COL_CANDIDATES = [
    "sektor", "sektor perusahaan", "sector", "industry", "industri",
    "bidang usaha", "bidang", "sub sektor", "sub-sektor",
]
SECTOR_COL_CONTAINS = [
    "sektor", "industri", "industry", "sector", "bidang", "product category",
    "kategori", "category",
]

STATUS_VALID = "Valid"
STATUS_INVALID = "Invalid"
STATUS_DUPLICATE = "Duplikat"

REASON_INVALID_EMAIL = "Format email salah"
REASON_DUPLICATE = "Data duplikat berdasarkan Nama Perusahaan/Email"
REASON_MISSING_EMAIL = "Kolom Email kosong"
REASON_INVALID_COUNTRY = "Negara tidak dikenali"
REASON_MISSING_COUNTRY = "Kolom Negara kosong"

REL_TINGGI = "Tinggi"
REL_RENDAH = "Rendah"
REL_REVIEW = "Perlu Ditinjau"

SECTOR_COL_OUT = "Sektor Perusahaan"
RELEVANCE_COL_OUT = "Keterkaitan dengan GPI"
RELEVANCE_REASON_COL_OUT = "Alasan Keterkaitan"
ONLINE_INFO_COL_OUT = "Info dari Internet"
ONLINE_SOURCE_COL_OUT = "Sumber Riset"

TAVILY_SEARCH_URL = "https://api.tavily.com/search"
ONLINE_MODE_HEMAT = "Hemat kredit (hanya yang tidak teridentifikasi)"
ONLINE_MODE_SEMUA = "Semua baris (lebih akurat, lebih boros kredit)"


SECTOR_KEYWORDS = [
    ("Mining / Pertambangan", [
        "tambang", "mining", "nikel", "nickel", "batu bara", "coal", "mineral",
        "smelter", "tambang emas", "gold mining", "bauksit", "bauxite",
    ]),
    ("Cement / Semen", ["semen", "cement"]),
    ("Steel / Baja", ["baja", "steel", "besi & baja", "iron & steel", "metal", "logam"]),
    ("Petrochemical / Petrokimia", ["petrokimia", "petrochemical", "petrochemicals"]),
    ("Chemical / Kimia", ["kimia", "chemical", "chemicals"]),
    ("Oil & Gas / Migas", [
        "migas", "minyak", "oil", "gas bumi", "oil & gas", "oil and gas", "o&g",
        "lng", "lpg", "pertamina", "petroleum", "upstream", "downstream",
        "offshore", "onshore",
    ]),
    ("Power Generation / Pembangkit Listrik", [
        "power generation", "power plant", "pembangkit listrik", "power",
        "electricity", "kelistrikan", "pln", "genset", "gas turbine",
    ]),
    ("Carbon Capture (CCS/CCUS)", [
        "carbon capture", "ccs", "ccus", "carbon capture and storage",
        "carbon capture, utilization and storage", "penangkapan karbon",
    ]),
    ("Food & Beverage (F&B)", [
        "makanan", "minuman", "food", "beverage", "f&b", "food & beverage",
        "food and beverage", "susu", "dairy", "minuman ringan",
    ]),
    ("Healthcare / Kesehatan", [
        "rumah sakit", "hospital", "klinik", "clinic", "medis", "medical",
        "farmasi", "pharma", "kesehatan", "healthcare",
    ]),
    ("Wastewater Treatment / Pengolahan Air Limbah", [
        "limbah", "wastewater", "air limbah", "water treatment",
        "pengolahan air", "ipal",
    ]),
    ("Renewable Energy / Energi Terbarukan", [
        "energi terbarukan", "renewable energy", "renewables", "renewable",
        "tenaga surya", "solar power", "solar", "tenaga angin", "wind power",
        "wind", "geothermal", "panas bumi", "pltb", "plts",
    ]),
    ("Green Hydrogen", ["hidrogen hijau", "green hydrogen", "hydrogen"]),
    ("HVO/Biofuel", ["biofuel", "biodiesel", "hvo", "bioenergi", "bahan bakar nabati"]),
    ("Data Center", ["data center", "pusat data", "datacenter", "cloud computing"]),
    ("Manufacturing / Manufaktur", ["manufaktur", "manufacturing", "pabrik", "industri", "factory"]),
]

GPI_TARGET_SECTORS = {name for name, _ in SECTOR_KEYWORDS}

SECTOR_TO_GPI_REASON: dict[str, str] = {
    "Mining / Pertambangan": (
        "Tambang butuh N2 untuk inertisasi gudang penyimpanan batu bara/mineral "
        "(mencegah swabakar) dan purging conveyor — cocok dengan Nitrogen Generator GPI."
    ),
    "Cement / Semen": (
        "Pabrik semen bisa memanfaatkan O2 untuk pengayaan udara pembakaran kiln "
        "(efisiensi energi) — sesuai Oxygen Generator GPI."
    ),
    "Steel / Baja": (
        "Industri baja adalah pengguna utama O2 untuk basic oxygen furnace, cutting, "
        "dan welding — cocok dengan Oxygen Generator GPI."
    ),
    "Petrochemical / Petrokimia": (
        "Petrokimia butuh N2 dalam jumlah besar untuk purging & blanketing reaktor/tangki, "
        "serta H2 untuk proses hydrogenation — sesuai lini Nitrogen & Hydrogen Generator GPI."
    ),
    "Chemical / Kimia": (
        "Industri kimia memakai N2 untuk inertisasi proses & penyimpanan bahan reaktif "
        "— cocok dengan Nitrogen Generator GPI."
    ),
    "Oil & Gas / Migas": (
        "Sektor migas memakai N2 untuk purging pipa & blanketing tangki, serta booster "
        "compressor untuk gas processing — sesuai lini produk inti GPI."
    ),
    "Power Generation / Pembangkit Listrik": (
        "Pembangkit listrik memakai H2 untuk pendinginan generator turbin besar & "
        "dual-fuel diesel-hidrogen, serta N2 untuk purging — sesuai Hydrogen & Nitrogen "
        "Generator GPI."
    ),
    "Carbon Capture (CCS/CCUS)": (
        "Proses CCS/CCUS sering memakai O2 untuk oxy-fuel combustion & N2 untuk purging "
        "sistem — berpotensi memakai Oxygen/Nitrogen Generator GPI."
    ),
    "Food & Beverage (F&B)": (
        "Industri F&B memakai N2 untuk modified atmosphere packaging (MAP) & pengawetan "
        "produk — cocok dengan Nitrogen Generator GPI."
    ),
    "Healthcare / Kesehatan": (
        "Sektor kesehatan adalah pengguna utama O2 medis — cocok dengan Oxygen Generator GPI."
    ),
    "Wastewater Treatment / Pengolahan Air Limbah": (
        "Pengolahan limbah memakai O2 untuk proses aerasi biologis — cocok dengan Oxygen "
        "Generator GPI."
    ),
    "Renewable Energy / Energi Terbarukan": (
        "Proyek energi terbarukan (elektrolisis air) menghasilkan H2 & O2 sebagai bagian "
        "dari prosesnya — selaras dengan lini Hydrogen & Oxygen Generator GPI."
    ),
    "Green Hydrogen": (
        "Proyek green hydrogen secara langsung relevan dengan Hydrogen Generator GPI "
        "(prinsipal Teledyne) — potensi kerja sama sangat tinggi."
    ),
    "HVO/Biofuel": (
        "Produksi HVO/biofuel butuh H2 untuk proses hydrotreating/hydrocracking — sesuai "
        "Hydrogen Generator GPI."
    ),
    "Data Center": (
        "Data center memakai N2 untuk sistem fire suppression & inert gas — cocok dengan "
        "Nitrogen Generator GPI."
    ),
    "Manufacturing / Manufaktur": (
        "Manufaktur umum sering butuh N2/O2 untuk purging, cutting, atau welding tergantung "
        "proses spesifiknya — berpotensi cocok dengan produk gas industri GPI."
    ),
}


def build_relevance_reason(
    relevance: str,
    canonical_sector: Optional[str],
    display_sector: str,
) -> str:
    if relevance == REL_TINGGI:
        return SECTOR_TO_GPI_REASON.get(
            canonical_sector,
            f"Sektor '{display_sector}' termasuk salah satu target industri GPI.",
        )
    if relevance == REL_RENDAH:
        if display_sector and display_sector != "Tidak Teridentifikasi":
            return (
                f"Sektor '{display_sector}' teridentifikasi, tapi berada di luar fokus target "
                "industri GPI saat ini (bukan migas, energi, manufaktur berat, kesehatan, F&B, dsb)."
            )
        return (
            "Berdasarkan info yang ditemukan, perusahaan ini tidak bergerak di salah satu "
            "target industri GPI (migas, energi, manufaktur berat, kesehatan, F&B, dsb)."
        )
    return (
        "Sektor perusahaan belum berhasil diidentifikasi (dari data maupun riset internet) "
        "— perlu verifikasi manual oleh tim BD."
    )


_ID_MARKERS = [
    " yang ", " dan ", " di ", " ke ", " dari ", " dengan ", " untuk ", " pada ",
    " ini ", " itu ", " adalah ", " merupakan ", " perusahaan ", " bergerak ",
    " sektor ", " industri ", " juga ", " serta ", " atau ", " tidak ", " dapat ",
]
_EN_MARKERS = [
    " the ", " and ", " of ", " in ", " to ", " for ", " this ", " company ",
    " that ", " are ", " with ", " as ", " is ", " based ", " provides ",
    " offers ", " which ", " its ",
]


def looks_indonesian(text: str) -> bool:
    if not text or not text.strip():
        return False
    padded = f" {text.lower()} "
    id_score = sum(1 for m in _ID_MARKERS if m in padded)
    en_score = sum(1 for m in _EN_MARKERS if m in padded)
    return id_score > 0 and id_score >= en_score


_SECTOR_NEGATION_WORDS = ["bukan", "tidak", "tanpa", "not", "no longer", "does not", "n't"]
_NEGATION_WINDOW = 25


def detect_sector_from_text(text: str) -> str | None:
    if not isinstance(text, str) or text.strip() == "":
        return None
    lowered = text.lower()
    for canonical, keywords in SECTOR_KEYWORDS:
        for kw in keywords:
            start = 0
            while True:
                idx = lowered.find(kw, start)
                if idx == -1:
                    break
                window = lowered[max(0, idx - _NEGATION_WINDOW):idx]
                if not any(neg in window for neg in _SECTOR_NEGATION_WORDS):
                    return canonical
                start = idx + 1
    return None


COUNTRY_ALIASES = {
    "indonesia": "Indonesia",
    "amerika": "United States",
    "amerika serikat": "United States",
    "usa": "United States",
    "u.s.a": "United States",
    "us": "United States",
    "inggris": "United Kingdom",
    "uk": "United Kingdom",
    "britania raya": "United Kingdom",
    "korea selatan": "Korea, Republic of",
    "korsel": "Korea, Republic of",
    "south korea": "Korea, Republic of",
    "korea utara": "Korea, Democratic People's Republic of",
    "north korea": "Korea, Democratic People's Republic of",
    "jepang": "Japan",
    "cina": "China",
    "tiongkok": "China",
    "singapura": "Singapore",
    "vietnam": "Vietnam",
    "filipina": "Philippines",
    "belanda": "Netherlands",
    "jerman": "Germany",
    "perancis": "France",
    "prancis": "France",
    "uni emirat arab": "United Arab Emirates",
    "uea": "United Arab Emirates",
    "arab saudi": "Saudi Arabia",
    "rusia": "Russia",
    "swiss": "Switzerland",
    "taiwan": "Taiwan",
    "hong kong": "Hong Kong",
}


def _build_valid_country_names() -> set[str]:
    names = set()
    if HAS_PYCOUNTRY:
        for c in pycountry.countries:
            for attr in ("name", "official_name", "common_name"):
                val = getattr(c, attr, None)
                if val:
                    names.add(val.strip().lower())
    names.update(COUNTRY_ALIASES.keys())
    names.update(v.lower() for v in COUNTRY_ALIASES.values())
    return names


VALID_COUNTRY_NAMES = _build_valid_country_names()


def validate_country(value) -> bool:
    if pd.isna(value) or not isinstance(value, str) or value.strip() == "":
        return False
    key = value.strip().lower()
    return key in VALID_COUNTRY_NAMES


@st.cache_data(show_spinner=False, ttl=60 * 60 * 24)
def _tavily_search_cached(api_key: str, query: str, max_results: int = 3) -> dict:
    resp = requests.post(
        TAVILY_SEARCH_URL,
        headers={
            "Authorization": f"Bearer {api_key}",
            "Content-Type": "application/json",
        },
        json={
            "query": query,
            "search_depth": "basic",
            "max_results": max_results,
            "include_answer": "basic",
        },
        timeout=20,
    )
    resp.raise_for_status()
    return resp.json()


def research_company_online(api_key: str, company_name: str) -> dict:
    query = (
        f"Dalam Bahasa Indonesia, jelaskan singkat perusahaan {company_name}: "
        "bergerak di sektor/industri apa dan apa produk atau layanan utamanya?"
    )
    try:
        data = _tavily_search_cached(api_key, query)
    except requests.exceptions.HTTPError as e:
        status = e.response.status_code if e.response is not None else None
        if status in (401, 403):
            return {"ok": False, "answer": "", "sources": [], "quota_exceeded": False,
                     "error": "API key Tavily tidak valid/ditolak."}
        if status in (429, 432):
            return {"ok": False, "answer": "", "sources": [], "quota_exceeded": True,
                     "error": "Kuota Tavily bulan ini sudah habis."}
        return {"ok": False, "answer": "", "sources": [], "quota_exceeded": False,
                 "error": f"HTTP error {status}"}
    except requests.exceptions.RequestException as e:
        return {"ok": False, "answer": "", "sources": [], "quota_exceeded": False,
                 "error": f"Gagal terhubung ke internet: {e}"}

    answer = (data.get("answer") or "").strip()
    results = data.get("results", []) or []
    if not answer:
        answer = " ".join(r.get("content", "") for r in results[:2]).strip()
    sources = [r.get("url", "") for r in results[:3] if r.get("url")]

    return {"ok": True, "answer": answer, "sources": sources, "quota_exceeded": False, "error": None}


def find_column(
    df: pd.DataFrame,
    candidates: list[str],
    contains_keywords: list[str] | None = None,
) -> str | None:
    normalized = {str(c).strip().lower(): c for c in df.columns}
    for cand in candidates:
        if cand in normalized:
            return normalized[cand]
    if contains_keywords:
        for norm_name, orig_name in normalized.items():
            for kw in contains_keywords:
                if kw in norm_name:
                    return orig_name
    return None


def load_input_file(uploaded_file) -> pd.DataFrame:
    name = uploaded_file.name.lower()
    if name.endswith(".csv"):
        df = pd.read_csv(uploaded_file, dtype=str, keep_default_na=True)
    elif name.endswith(".xlsx") or name.endswith(".xls"):
        df = pd.read_excel(uploaded_file, dtype=str)
    else:
        raise ValueError("Format file tidak didukung. Gunakan .xlsx atau .csv.")
    return df


def strip_whitespace(df: pd.DataFrame) -> pd.DataFrame:
    df = df.copy()
    for col in df.columns:
        df[col] = df[col].apply(
            lambda v: re.sub(r"\s+", " ", v.strip()) if isinstance(v, str) else v
        )
    return df


def is_row_empty(row: pd.Series) -> bool:
    for v in row:
        if pd.isna(v):
            continue
        if isinstance(v, str) and v.strip() == "":
            continue
        return False
    return True


def validate_email_format(value) -> bool:
    if pd.isna(value):
        return False
    if not isinstance(value, str) or value.strip() == "":
        return False
    return bool(EMAIL_REGEX.match(value.strip()))


def process_dataframe(
    df: pd.DataFrame,
    enable_online: bool = False,
    tavily_api_key: Optional[str] = None,
    online_mode: str = ONLINE_MODE_HEMAT,
    progress_callback: Optional[Callable[[int, int], None]] = None,
) -> tuple[pd.DataFrame, dict]:
    stats = {
        "total_input_rows": len(df),
        "empty_rows_removed": 0,
        "valid": 0,
        "invalid": 0,
        "duplicate": 0,
        "relevansi_tinggi": 0,
        "relevansi_rendah": 0,
        "relevansi_review": 0,
        "online_researched": 0,
        "online_failed": 0,
        "online_quota_exceeded": False,
    }

    df = strip_whitespace(df)

    empty_mask = df.apply(is_row_empty, axis=1)
    stats["empty_rows_removed"] = int(empty_mask.sum())
    df = df.loc[~empty_mask].reset_index(drop=True)

    company_col = find_column(df, COMPANY_COL_CANDIDATES, COMPANY_COL_CONTAINS)
    email_col = find_column(df, EMAIL_COL_CANDIDATES, EMAIL_COL_CONTAINS)
    country_col = find_column(df, COUNTRY_COL_CANDIDATES, COUNTRY_COL_CONTAINS)
    sector_col = find_column(df, SECTOR_COL_CANDIDATES, SECTOR_COL_CONTAINS)

    status_list = []
    sector_out_list = []
    relevance_list = []
    relevance_reason_list = []
    online_info_list = []
    online_source_list = []


    seen_companies = set()
    seen_emails = set()

    online_ready = bool(enable_online and tavily_api_key)
    quota_exceeded = False
    total_rows = len(df)

    for row_idx, (_, row) in enumerate(df.iterrows()):
        is_duplicate = False

        company_val = None
        if company_col is not None:
            company_val = row[company_col]
            if isinstance(company_val, str) and company_val.strip() != "":
                key = company_val.strip().lower()
                if key in seen_companies:
                    is_duplicate = True
                else:
                    seen_companies.add(key)

        email_val = None
        if email_col is not None:
            email_val = row[email_col]
            if isinstance(email_val, str) and email_val.strip() != "":
                key = email_val.strip().lower()
                if key in seen_emails:
                    is_duplicate = True
                else:
                    seen_emails.add(key)

        email_ok = True
        if email_col is not None:
            if pd.isna(email_val) or (isinstance(email_val, str) and email_val.strip() == ""):
                email_ok = False
            elif not validate_email_format(email_val):
                email_ok = False

        country_ok = True
        if country_col is not None:
            country_val = row[country_col]
            if pd.isna(country_val) or (isinstance(country_val, str) and country_val.strip() == ""):
                country_ok = False
            elif not validate_country(country_val):
                country_ok = False

        raw_sector_val = row[sector_col] if sector_col is not None else None
        has_raw_sector = isinstance(raw_sector_val, str) and raw_sector_val.strip() != ""

        detected_canonical = None
        if has_raw_sector:
            final_sector = raw_sector_val.strip()
            detected_canonical = detect_sector_from_text(raw_sector_val)
        else:
            detected_canonical = detect_sector_from_text(company_val) if company_val else None
            final_sector = detected_canonical if detected_canonical else "Tidak Teridentifikasi"

        online_info = ""
        online_sources = ""
        has_company_name = isinstance(company_val, str) and company_val.strip() != ""

        should_research = (
            online_ready
            and not quota_exceeded
            and has_company_name
            and (online_mode == ONLINE_MODE_SEMUA or detected_canonical is None)
        )

        got_online_info = False
        if should_research:
            company_display = company_val.strip()
            result = research_company_online(tavily_api_key, company_display)
            if result["ok"]:
                stats["online_researched"] += 1
                online_sources = "; ".join(result["sources"])
                raw_answer = result["answer"]
                online_detected = detect_sector_from_text(raw_answer)
                if online_detected is not None:
                    detected_canonical = online_detected
                    if not has_raw_sector:
                        final_sector = online_detected

                if raw_answer and looks_indonesian(raw_answer):
                    online_info = raw_answer[:400]
                    got_online_info = True
                elif online_detected is not None:
                    online_info = (
                        f"Berdasarkan riset internet, {company_display} teridentifikasi "
                        f"bergerak di sektor terkait {online_detected}."
                    )
                    got_online_info = True
                elif raw_answer:
                    online_info = (
                        "Ditemukan informasi terkait perusahaan ini di internet, namun "
                        "sektornya belum bisa dipastikan otomatis — silakan cek sumber."
                    )
                    got_online_info = True
                else:
                    online_info = "Tidak ditemukan informasi relevan di internet untuk perusahaan ini."
                    got_online_info = False
            else:
                stats["online_failed"] += 1
                if result["quota_exceeded"]:
                    quota_exceeded = True
                    stats["online_quota_exceeded"] = True
                    online_info = "(Riset internet dihentikan: kuota Tavily bulan ini habis)"
                else:
                    online_info = f"(Riset internet gagal: {result['error']})"

        online_info_list.append(online_info)
        online_source_list.append(online_sources)
        sector_out_list.append(final_sector)

        has_sector_info = has_raw_sector or got_online_info
        if detected_canonical is not None and detected_canonical in GPI_TARGET_SECTORS:
            relevance = REL_TINGGI
            stats["relevansi_tinggi"] += 1
        elif has_sector_info:
            relevance = REL_RENDAH
            stats["relevansi_rendah"] += 1
        else:
            relevance = REL_REVIEW
            stats["relevansi_review"] += 1
        relevance_list.append(relevance)
        relevance_reason_list.append(
            build_relevance_reason(relevance, detected_canonical, final_sector)
        )

        if is_duplicate:
            status = STATUS_DUPLICATE
            stats["duplicate"] += 1
        elif not email_ok or not country_ok:
            status = STATUS_INVALID
            stats["invalid"] += 1
        else:
            status = STATUS_VALID
            stats["valid"] += 1

        status_list.append(status)

        if progress_callback is not None:
            progress_callback(row_idx + 1, total_rows)

    df = df.copy()
    sector_target_col = sector_col if sector_col is not None else SECTOR_COL_OUT
    df[sector_target_col] = sector_out_list
    if online_ready:
        df[ONLINE_INFO_COL_OUT] = online_info_list
        df[ONLINE_SOURCE_COL_OUT] = online_source_list
    df[RELEVANCE_COL_OUT] = relevance_list
    df[RELEVANCE_REASON_COL_OUT] = relevance_reason_list
    df["Status"] = status_list

    return df, stats


STATUS_CELL_COLORS = {
    STATUS_VALID: ("C6EFCE", "006100"),
    STATUS_INVALID: ("FFC7CE", "9C0006"),
    STATUS_DUPLICATE: ("FFEB9C", "9C6500"),
}
RELEVANCE_CELL_COLORS = {
    REL_TINGGI: ("C6EFCE", "006100"),
    REL_RENDAH: ("E7E6E6", "3A3A3A"),
    REL_REVIEW: ("FFEB9C", "9C6500"),
}
WRAP_COLUMNS = {ONLINE_INFO_COL_OUT, ONLINE_SOURCE_COL_OUT, RELEVANCE_REASON_COL_OUT}


def to_excel_bytes(df: pd.DataFrame) -> bytes:
    from openpyxl.styles import Alignment, Font, PatternFill
    from openpyxl.utils import get_column_letter

    buffer = io.BytesIO()
    sheet_name = "Hasil Validasi"
    with pd.ExcelWriter(buffer, engine="openpyxl") as writer:
        df.to_excel(writer, index=False, sheet_name=sheet_name)
        ws = writer.sheets[sheet_name]
        n_rows = len(df)

        header_fill = PatternFill(start_color="1F4E78", end_color="1F4E78", fill_type="solid")
        header_font = Font(bold=True, color="FFFFFF")
        header_align = Alignment(vertical="center", horizontal="center", wrap_text=True)
        wrap_align = Alignment(wrap_text=True, vertical="top")
        top_align = Alignment(vertical="top")

        for col_idx, col_name in enumerate(df.columns, start=1):
            col_letter = get_column_letter(col_idx)

            header_cell = ws.cell(row=1, column=col_idx)
            header_cell.font = header_font
            header_cell.fill = header_fill
            header_cell.alignment = header_align

            is_wrap_col = col_name in WRAP_COLUMNS
            if is_wrap_col:
                width = 45
            else:
                values_len = [len(str(v)) for v in df[col_name].astype(str).tolist()] or [0]
                width = min(max(len(str(col_name)), max(values_len)) + 2, 32)
            ws.column_dimensions[col_letter].width = width

            color_map = None
            if col_name == "Status":
                color_map = STATUS_CELL_COLORS
            elif col_name == RELEVANCE_COL_OUT:
                color_map = RELEVANCE_CELL_COLORS

            body_align = wrap_align if is_wrap_col else top_align
            for row_idx in range(2, n_rows + 2):
                cell = ws.cell(row=row_idx, column=col_idx)
                cell.alignment = body_align
                if color_map is not None:
                    fill_hex, font_hex = color_map.get(cell.value, (None, None))
                    if fill_hex:
                        cell.fill = PatternFill(start_color=fill_hex, end_color=fill_hex, fill_type="solid")
                        cell.font = Font(color=font_hex)

        ws.freeze_panes = "A2"
        ws.auto_filter.ref = ws.dimensions
        ws.row_dimensions[1].height = 28

    return buffer.getvalue()


st.title("✅ GPI Exhibitor Data Validator")
st.caption(
    "PT Generator Pasifik Indonesia — Nimble Vibe Prospecting System (MVP+). "
    "Masuk data mentah, keluar data bersih + insight relevansi ke GPI."
)

st.markdown(
    "**Langkah:** 1) Drop file → 2) Sistem otomatis memproses → 3) Download hasil."
)

if not HAS_PYCOUNTRY:
    st.warning(
        "⚠️ Pustaka 'pycountry' belum terpasang — validasi negara akan memakai "
        "daftar alias terbatas saja. Jalankan `pip install -r requirements.txt` "
        "untuk hasil validasi negara yang lebih lengkap."
    )

with st.sidebar:
    st.header("🔎 Riset Internet (Opsional)")
    st.caption(
        "Cari profil sektor/industri perusahaan langsung dari internet memakai "
        "**Tavily Search API** — gratis 1.000 kredit/bulan, tanpa kartu kredit."
    )
    enable_online = st.toggle("Aktifkan riset internet", value=False)

    try:
        _default_key = st.secrets.get("TAVILY_API_KEY", "")
    except Exception:
        _default_key = ""

    tavily_api_key = st.text_input(
        "Tavily API Key",
        value=_default_key,
        type="password",
        placeholder="tvly-xxxxxxxxxxxxxxxx",
        disabled=not enable_online,
        help="Daftar gratis di app.tavily.com/home lalu salin API key-nya ke sini "
             "(lihat README bagian 'Riset Internet' untuk langkah lengkap).",
    )
    online_mode = st.radio(
        "Mode riset",
        options=[ONLINE_MODE_HEMAT, ONLINE_MODE_SEMUA],
        index=0,
        disabled=not enable_online,
        help="'Hemat kredit' hanya meriset baris yang gagal dikenali dari nama "
             "perusahaan/kolom sektor. 'Semua baris' meriset setiap baris (lebih "
             "akurat tapi memakai kredit jauh lebih banyak).",
    )
    if enable_online and not tavily_api_key:
        st.warning("⚠️ Masukkan Tavily API Key untuk mengaktifkan riset internet.")
    st.caption(
        "Catatan: kalau kuota bulanan habis di tengah proses, sistem otomatis "
        "kembali ke deteksi offline untuk sisa baris — proses tidak akan gagal."
    )

uploaded_file = st.file_uploader(
    "Tarik & lepas file .xlsx atau .csv daftar prospek di sini",
    type=["xlsx", "xls", "csv"],
    accept_multiple_files=False,
)

if uploaded_file is not None:
    start_time = datetime.now()
    try:
        raw_df = load_input_file(uploaded_file)
    except Exception as e:
        st.error(f"Gagal membaca file: {e}")
        st.stop()

    if raw_df.empty:
        st.warning("File tidak berisi data.")
        st.stop()

    company_col_found = find_column(raw_df, COMPANY_COL_CANDIDATES, COMPANY_COL_CONTAINS)
    email_col_found = find_column(raw_df, EMAIL_COL_CANDIDATES, EMAIL_COL_CONTAINS)
    country_col_found = find_column(raw_df, COUNTRY_COL_CANDIDATES, COUNTRY_COL_CONTAINS)
    sector_col_found = find_column(raw_df, SECTOR_COL_CANDIDATES, SECTOR_COL_CONTAINS)

    if company_col_found is None:
        st.warning(
            "⚠️ Kolom 'Nama Perusahaan' tidak ditemukan — pengecekan duplikat "
            "berdasarkan nama perusahaan akan dilewati."
        )
    if email_col_found is None:
        st.warning(
            "⚠️ Kolom 'Email' tidak ditemukan — validasi format email akan dilewati."
        )
    if country_col_found is None:
        st.info(
            "ℹ️ Kolom 'Negara' tidak ditemukan — validasi negara dilewati."
        )
    if sector_col_found is None:
        st.info(
            "ℹ️ Kolom 'Sektor' tidak ditemukan — sistem akan menebak sektor "
            "otomatis dari nama perusahaan."
        )

    use_online = enable_online and bool(tavily_api_key)

    if use_online:
        progress_bar = st.progress(0.0)
        progress_text = st.empty()

        def _update_progress(done: int, total: int) -> None:
            frac = done / total if total else 1.0
            progress_bar.progress(frac)
            progress_text.caption(f"Memproses baris {done}/{total}...")

        output_df, stats = process_dataframe(
            raw_df,
            enable_online=True,
            tavily_api_key=tavily_api_key,
            online_mode=online_mode,
            progress_callback=_update_progress,
        )
        progress_bar.empty()
        progress_text.empty()
    else:
        with st.spinner("Memproses data..."):
            output_df, stats = process_dataframe(raw_df)

    elapsed = (datetime.now() - start_time).total_seconds()
    st.success(f"Selesai diproses dalam {elapsed:.2f} detik.")

    if use_online:
        if stats["online_quota_exceeded"]:
            st.warning(
                "⚠️ Kuota Tavily bulan ini habis di tengah proses — sisa baris "
                "otomatis memakai deteksi offline (keyword dari nama perusahaan)."
            )
        st.caption(
            f"🔎 Riset internet: {stats['online_researched']} baris berhasil diriset, "
            f"{stats['online_failed']} gagal/dilewati."
        )

    col1, col2, col3, col4 = st.columns(4)
    col1.metric("Total baris input", stats["total_input_rows"])
    col2.metric("Valid", stats["valid"])
    col3.metric("Invalid", stats["invalid"])
    col4.metric("Duplikat", stats["duplicate"])
    if stats["empty_rows_removed"]:
        st.info(f"{stats['empty_rows_removed']} baris kosong telah dihapus otomatis.")

    st.markdown("**Keterkaitan dengan GPI**")
    rcol1, rcol2, rcol3 = st.columns(3)
    rcol1.metric("Tinggi", stats["relevansi_tinggi"])
    rcol2.metric("Rendah", stats["relevansi_rendah"])
    rcol3.metric("Perlu Ditinjau", stats["relevansi_review"])

    st.subheader("Preview Hasil")
    st.dataframe(output_df, use_container_width=True)

    excel_bytes = to_excel_bytes(output_df)
    output_name = re.sub(r"\.(xlsx|xls|csv)$", "", uploaded_file.name, flags=re.IGNORECASE)
    st.download_button(
        label="⬇️ Download Hasil Validasi (Excel)",
        data=excel_bytes,
        file_name=f"{output_name}_validated.xlsx",
        mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        type="primary",
    )
else:
    st.info("Menunggu file diunggah...")
