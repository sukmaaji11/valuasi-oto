import streamlit as st
import cloudscraper
from bs4 import BeautifulSoup
from html import escape
import re
import json
import numpy as np
import pandas as pd
import concurrent.futures
from playwright.sync_api import sync_playwright
import os
import subprocess
import sys
import io
import tempfile
from datetime import date, datetime, timezone
from reportlab.lib.pagesizes import A4
from reportlab.lib import colors
from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle, HRFlowable
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from license_utils import (
    LICENSE_SESSION_COOKIE,
    create_activation_link,
    generate_license,
    verify_license_key,
    verify_license_session,
)
from pilot_data import PILOT_CSV_COLUMNS, parse_mileage_range, parse_pilot_csv
from scraper_utils import (
    extract_card_location,
    extract_mileage_range,
    extract_vehicle_schema_listings,
    parse_listing_price,
)
from supabase_data import (
    authenticate_admin,
    create_database_clients,
    deduplicate_listings,
    get_fresh_listings,
    save_listings,
)

# ==================== KODE RAHASIA DEVELOPER ====================
NOMOR_WA_PENJUAL = "6289633414555"  # Ganti dengan nomor WhatsApp kamu (format 62)
NAMA_PRODUK = "ValuasiOto.id"
TAGLINE = "B2B Market Intelligence & Walk-Away Price Engine"
LOGO_PATH = os.path.join(
    os.path.dirname(os.path.abspath(__file__)),
    "assets",
    "valuasioto-mark.svg",
)


def fmt_km(minimum, maximum=None):
    if minimum is None or pd.isna(minimum):
        return "Tidak tercantum"
    maximum = minimum if maximum is None or pd.isna(maximum) else maximum
    min_text = f"{int(minimum):,}".replace(",", ".")
    max_text = f"{int(maximum):,}".replace(",", ".")
    if int(minimum) == int(maximum):
        return f"{min_text} km"
    return f"{min_text}–{max_text} km"


def listing_mileage_bounds(record):
    minimum = record.get("mileage_min_km")
    maximum = record.get("mileage_max_km")
    if minimum is None and maximum is None and record.get("mileage_km") is not None:
        return parse_mileage_range(record["mileage_km"])
    return minimum, maximum


st.set_page_config(
    page_title=f"{NAMA_PRODUK} — Valuasi & Margin Mobil Bekas",
    page_icon=LOGO_PATH,
    layout="wide",
    initial_sidebar_state="expanded",
)

def get_supabase_clients():
    config = {}
    for key in (
        "SUPABASE_URL",
        "SUPABASE_ANON_KEY",
        "SUPABASE_SERVICE_ROLE_KEY",
    ):
        value = os.environ.get(key)
        if not value:
            try:
                value = st.secrets.get(key)
            except Exception as error:
                raise RuntimeError(
                    "Konfigurasi Supabase belum tersedia. Tambahkan kredensial "
                    "ke Streamlit secrets atau environment variables."
                ) from error
        config[key] = value
    return create_database_clients(config)


def get_app_setting(key, default):
    value = os.environ.get(key)
    if value:
        return value
    try:
        return st.secrets.get(key, default)
    except Exception:
        return default


def render_admin_panel():
    st.title("ValuasiOto Admin")
    st.caption("Kelola listing pasar, dataset valuasi, dan lisensi.")
    try:
        auth_client, db_client = get_supabase_clients()
    except Exception as error:
        st.error(f"Koneksi Supabase belum siap: {error}")
        st.info(
            "Jalankan supabase_schema.sql di SQL Editor Supabase, lalu atur "
            "SUPABASE_URL, SUPABASE_ANON_KEY, dan SUPABASE_SERVICE_ROLE_KEY."
        )
        return

    identity = st.session_state.get("admin_identity")
    if not identity:
        if st.button("← Kembali ke halaman aktivasi"):
            st.query_params.pop("admin", None)
            st.rerun()
        with st.form("admin_login"):
            email = st.text_input("Email admin")
            password = st.text_input("Password", type="password")
            login_clicked = st.form_submit_button("Masuk ke panel admin")
        if login_clicked:
            try:
                st.session_state.admin_identity = authenticate_admin(
                    auth_client, db_client, email.strip(), password
                )
                st.rerun()
            except PermissionError as error:
                st.error(str(error))
            except Exception as error:
                st.error(f"Login admin gagal: {error}")
        return

    try:
        admin_check = (
            db_client.table("admin_users")
            .select("user_id")
            .eq("user_id", identity["id"])
            .maybe_single()
            .execute()
        )
        if admin_check.data is None:
            del st.session_state.admin_identity
            st.error("Akses admin akun ini sudah dicabut. Silakan login kembali.")
            return
    except Exception as error:
        st.error(f"Gagal memverifikasi hak admin: {error}")
        return

    with st.container(border=True):
        user_col, back_col, logout_col = st.columns([5, 1, 1], vertical_alignment="center")
        with user_col:
            st.caption(f"ADMIN  ·  {identity['email']}")
        with back_col:
            if st.button("Kembali", use_container_width=True):
                st.query_params.pop("admin", None)
                st.rerun()
        with logout_col:
            if st.button("Keluar", use_container_width=True):
                auth_client.auth.sign_out()
                del st.session_state.admin_identity
                st.rerun()

    try:
        listing_result = (
            db_client.table("vehicle_listings")
            .select(
                "source,make,model,year,mileage_min_km,mileage_max_km,price,location,url,collected_at",
                count="exact",
            )
            .order("collected_at", desc=True)
            .limit(100)
            .execute()
        )
        recent = listing_result.data or []
        total_listings = listing_result.count or len(recent)
    except Exception as error:
        st.error(f"Gagal memuat ringkasan listing: {error}")
        recent = []
        total_listings = 0

    st.markdown("## Ringkasan dataset")
    metric_cols = st.columns(3)
    metric_cols[0].metric("Total listing", f"{total_listings:,}".replace(",", "."))
    metric_cols[1].metric(
        "Listing ditampilkan",
        f"{len(recent):,}".replace(",", "."),
        help="Panel menampilkan maksimal 100 listing terbaru.",
    )
    metric_cols[2].metric(
        "Wilayah tercatat",
        len({row["location"] for row in recent if row.get("location")}),
        help="Jumlah wilayah berbeda pada 100 listing terbaru.",
    )

    overview_tab, add_tab, import_tab, license_tab = st.tabs(
        ["📋 Dataset", "➕ Tambah listing", "📥 Impor CSV", "🔑 Lisensi"]
    )

    with overview_tab:
        st.subheader("Listing terbaru")
        st.caption("Menampilkan hingga 100 data terakhir yang masuk.")
        if recent:
            recent_df = pd.DataFrame(recent)
            recent_df["Kilometer"] = recent_df.apply(
                lambda row: fmt_km(*listing_mileage_bounds(row)),
                axis=1,
            )
            recent_df = recent_df.drop(
                columns=["mileage_min_km", "mileage_max_km", "mileage_km"],
                errors="ignore",
            )
            st.dataframe(
                recent_df,
                hide_index=True,
                use_container_width=True,
                column_config={
                    "Kilometer": st.column_config.TextColumn(),
                    "price": st.column_config.NumberColumn(
                        "Harga iklan", format="Rp %d"
                    ),
                    "url": st.column_config.LinkColumn(
                        "Listing asli", display_text="Buka listing"
                    ),
                    "collected_at": st.column_config.TextColumn("Dicatat"),
                },
            )
        else:
            st.info(
                "Dataset masih kosong. Tambahkan listing manual atau impor CSV "
                "dari tab di atas."
            )
        if st.button("↻ Muat ulang dataset"):
            st.rerun()

    with add_tab:
        st.subheader("Tambah satu listing")
        st.caption(
            "Masukkan detail kendaraan dan sumber. Listing tanpa wilayah yang "
            "akurat tidak dapat dipakai untuk valuasi berdasarkan kota."
        )
        with st.form("add_listing"):
            st.markdown("**Identitas kendaraan**")
            vehicle_cols = st.columns(3)
            with vehicle_cols[0]:
                make = st.text_input("Merek", placeholder="Toyota")
            with vehicle_cols[1]:
                model = st.text_input("Model", placeholder="Avanza")
            with vehicle_cols[2]:
                variant = st.text_input("Varian", placeholder="G 1.3 AT")

            title = st.text_input(
                "Judul pada listing",
                placeholder="Toyota Avanza G 1.3 AT 2019",
            )
            detail_cols = st.columns(2)
            with detail_cols[0]:
                year = st.number_input(
                    "Tahun kendaraan",
                    min_value=1980,
                    max_value=date.today().year + 1,
                    value=2019,
                )
                price = st.number_input(
                    "Harga iklan (Rp)",
                    min_value=30_000_001,
                    value=175_000_000,
                    step=1_000_000,
                    format="%d",
                    help="Masukkan angka Rupiah penuh, misalnya 175000000.",
                )
                mileage_input = st.text_input(
                    "Kilometer (opsional)",
                    placeholder="Contoh: 85000 atau 95000-100000",
                    help="Isi satu angka atau rentang. Contoh: 85000 atau 95000-100000.",
                )
            with detail_cols[1]:
                location = st.text_input(
                    "Wilayah listing",
                    placeholder="Jakarta Selatan",
                )
                source = st.text_input(
                    "Sumber data",
                    value="Input manual",
                    placeholder="Facebook Marketplace",
                )

            url = st.text_input(
                "URL listing",
                placeholder="https://...",
            )
            collected_at = st.date_input(
                "Tanggal listing dicatat",
                value=date.today(),
            )
            add_clicked = st.form_submit_button(
                "Simpan listing",
                type="primary",
                use_container_width=True,
            )

        if add_clicked:
            record = {
                "source": source,
                "make": make,
                "model": model,
                "variant": variant,
                "title": title,
                "year": int(year),
                "mileage_km": mileage_input,
                "price": int(price),
                "location": location,
                "url": url,
                "collected_at": datetime.combine(
                    collected_at, datetime.min.time(), tzinfo=timezone.utc
                ).isoformat(),
            }
            try:
                if not all(
                    (
                        source.strip(),
                        make.strip(),
                        model.strip(),
                        title.strip(),
                        location.strip(),
                        url.strip(),
                    )
                ):
                    st.error(
                        "Lengkapi sumber, merek, model, judul, wilayah, dan URL."
                    )
                else:
                    saved = save_listings(db_client, [record])
                    st.success(
                        "Listing berhasil disimpan."
                        if saved
                        else "URL listing ini sudah ada; data lama tidak ditimpa."
                    )
            except Exception as error:
                st.error(f"Gagal menyimpan listing: {error}")

    with import_tab:
        st.subheader("Impor banyak listing")
        st.caption(
            "Impor CSV adalah alat internal admin. Pengguna ValuasiOto tidak "
            "perlu mencari atau mengunggah listing sendiri."
        )
        st.download_button(
            "Unduh template CSV",
            data=",".join(PILOT_CSV_COLUMNS) + "\n",
            file_name="template_listing_admin.csv",
            mime="text/csv",
        )
        st.caption(
            "Kolom `mileage_km` opsional. Isi angka tunggal atau rentang "
            "(contoh 85000 atau 95000-100000); kosongkan jika tidak diketahui."
        )
        uploaded_csv = st.file_uploader(
            "Pilih file CSV",
            type=["csv"],
            key="admin_listing_csv",
        )
        if uploaded_csv:
            records, errors, duplicate_count = parse_pilot_csv(
                uploaded_csv.getvalue()
            )
            st.info(
                f"{len(records)} listing valid · {duplicate_count} URL duplikat "
                "dilewati · "
                f"{len(errors)} baris bermasalah"
            )
            if records:
                st.dataframe(
                    pd.DataFrame(records),
                    hide_index=True,
                    use_container_width=True,
                )
            if errors:
                with st.expander("Lihat baris yang perlu diperbaiki"):
                    st.write(errors)
            if records and st.button(
                "Impor listing valid",
                type="primary",
                key="import_valid_listings",
            ):
                try:
                    saved = save_listings(db_client, records)
                    st.success(f"{saved} listing baru berhasil disimpan.")
                    st.rerun()
                except Exception as error:
                    st.error(f"Gagal mengimpor CSV: {error}")

    with license_tab:
        st.subheader("Buat lisensi pelanggan")
        st.caption(
            "Kunci lisensi dibuat dengan format yang sama dengan aktivasi aplikasi. "
            "Simpan nama dan kunci pelanggan untuk referensi internal."
        )
        with st.form("generate_license_form"):
            customer_name = st.text_input(
                "Nama pembeli / showroom",
                placeholder="Contoh: Budi Motor",
            )
            generate_clicked = st.form_submit_button(
                "Generate lisensi",
                type="primary",
            )

        if generate_clicked:
            try:
                app_url = get_app_setting("PUBLIC_APP_URL", None)
                license_key, magic_link = generate_license(
                    customer_name,
                    app_url=app_url,
                )
                st.session_state.generated_license = {
                    "name": customer_name.strip(),
                    "key": license_key,
                    "link": magic_link,
                }
            except ValueError as error:
                st.error(str(error))

        generated = st.session_state.get("generated_license")
        if generated:
            st.success("Lisensi berhasil dibuat.")
            st.text_input(
                "Nama terdaftar",
                value=generated["name"],
                disabled=True,
            )
            st.code(generated["key"], language=None)
            st.text_input(
                "Magic link aktivasi",
                value=generated["link"],
                disabled=True,
            )
            message = (
                f"Halo Kak {generated['name']}! Terima kasih atas pembayarannya "
                "Rp 149.000 untuk ValuasiOto.id.\n\n"
                "Berikut data akses aplikasi Kakak:\n"
                f"Nama Terdaftar: {generated['name']}\n"
                f"Kode Lisensi: {generated['key']}\n\n"
                "Silakan buka link aktivasi berikut:\n"
                f"{generated['link']}\n\n"
                "Selamat menggunakan ValuasiOto.id!"
            )
            st.text_area(
                "Pesan siap dikirim ke pelanggan",
                value=message,
                height=220,
            )
            st.download_button(
                "Unduh detail lisensi",
                data=message,
                file_name=f"lisensi_{generated['name'].strip().replace(' ', '_')}.txt",
                mime="text/plain",
            )


# ==================== MAGIC LINK & SESSION STATE LISENSI ====================
# Ambil otomatis dari URL (Magic Link dari WhatsApp)
query_params = st.query_params
qp_name = query_params.get("name", "")
qp_key = query_params.get("key", "")

if "user_pemilik" not in st.session_state:
    st.session_state.user_pemilik = qp_name
if "user_key" not in st.session_state:
    st.session_state.user_key = qp_key

# Cek Verifikasi Lisensi
license_session_secret = get_app_setting("LICENSE_SESSION_SECRET", "")
session_cookie = st.context.cookies.get(LICENSE_SESSION_COOKIE, "")
session_owner = verify_license_session(session_cookie, license_session_secret)
admin_mode = query_params.get("admin", "") == "1"
if session_owner:
    st.session_state.user_pemilik = session_owner
    st.session_state.user_key = ""
legacy_license_is_valid = verify_license_key(
    st.session_state.user_key,
    st.session_state.user_pemilik,
)
if legacy_license_is_valid and not session_owner and not admin_mode:
    st.session_state.pending_license_activation = {
        "name": st.session_state.user_pemilik,
        "key": st.session_state.user_key,
    }
    st.session_state.user_key = ""
    if qp_name or qp_key:
        st.query_params.pop("name", None)
        st.query_params.pop("key", None)
        st.rerun()
is_unlocked = bool(session_owner)

# ==================== HALAMAN AKTIVASI MOBILE-FIRST (LAYAR UTAMA) ====================
if not is_unlocked and not admin_mode:
    activation_logo_cols = st.columns([1, 1, 1])
    with activation_logo_cols[1]:
        st.image(LOGO_PATH, width=72)
    st.markdown("""
        <div style="text-align: center; padding: 10px 0 20px 0;">
            <h1 style="font-size: 1.8rem; font-weight: 800; color: #0F172A; margin: 0; letter-spacing: -0.5px;">ValuasiOto.id</h1>
            <p style="font-size: 0.9rem; color: #64748B; margin-top: 4px;">B2B Market Intelligence & Walk-Away Price Engine</p>
        </div>
    """, unsafe_allow_html=True)

    col_box1, col_box2, col_box3 = st.columns([1, 2, 1])
    with col_box2:
        with st.container(border=True):
            st.markdown("<h3 style='margin-top:0; text-align:center;'>🔑 Aktivasi Aplikasi</h3>", unsafe_allow_html=True)
            st.caption("Masukkan Nama & Kode Lisensi yang kamu terima setelah pembelian Rp 149.000.")
            
            pending_activation = st.session_state.get("pending_license_activation")
            if not pending_activation:
                input_nama = st.text_input("Nama Terdaftar / Showroom", value=st.session_state.user_pemilik, placeholder="contoh: Budi Trader").strip()
                input_key = st.text_input("Kode Lisensi (License Key)", value=st.session_state.user_key, type="password", placeholder="VALUASI-XXXXXX-XXXXXXXX").strip()
                if st.button("🔓 Aktivasi & Buka Aplikasi", type="primary", use_container_width=True):
                    if verify_license_key(input_key, input_nama):
                        st.session_state.pending_license_activation = {
                            "name": input_nama,
                            "key": input_key,
                        }
                        st.rerun()
                    else:
                        st.error("❌ Nama atau Kode Lisensi tidak cocok/salah!")
            else:
                activation_url = create_activation_link(
                    pending_activation["name"],
                    pending_activation["key"],
                    app_url=get_app_setting("PUBLIC_APP_URL", None),
                )
                st.success("Lisensi valid. Simpan sesi aman untuk membuka aplikasi.")
                st.link_button(
                    "Simpan sesi & buka aplikasi",
                    activation_url,
                    type="primary",
                    use_container_width=True,
                )

            st.divider()
            
            st.markdown(f"""
                <div style="text-align: center; font-size: 0.88rem; color: #475569;">
                    <b>Belum memiliki lisensi?</b><br/>
                    Dapatkan akses penuh selamanya (6 Platform + PDF Export) hanya:
                    <h3 style="color: #FF6B00; margin: 6px 0;">Rp 149.000 <span style="font-size: 0.8rem; color: #64748B; font-weight: normal;">(Sekali Beli Putus)</span></h3>
                </div>
            """, unsafe_allow_html=True)
            
            wa_url = f"https://wa.me/{NOMOR_WA_PENJUAL}?text=Halo%20saya%20mau%20beli%20lisensi%20ValuasiOto.id%20Rp%20149.000"
            st.link_button("💬 Beli Lisensi via WhatsApp", wa_url, use_container_width=True)
    # Hentikan eksekusi dashboard jika belum ter-unlock
    st.stop()

if admin_mode:
    render_admin_panel()
    st.stop()

# ==================== SETELAH TER-UNLOCK ====================

# Custom CSS: Mengurangi padding atas TANPA menghilangkan tombol toggle sidebar
# Tambahkan CSS ini di bagian st.markdown CSS atas file app.py kamu
st.markdown("""
    <style>
        /* Responsive Viewport Adjustments */
        .block-container {
            padding-top: 1.8rem !important;
            padding-bottom: 2rem !important;
            padding-left: 1rem !important;
            padding-right: 1rem !important;
        }
        
        /* Touch Friendly Buttons for Mobile */
        .stButton > button {
            border-radius: 8px !important;
            height: 3rem !important;
            font-size: 1rem !important;
            font-weight: 700 !important;
        }

        .brand-header {
            min-height: 96px;
            padding: 16px 22px;
            border: 1px solid #dbe3ee;
            border-radius: 18px;
            background: linear-gradient(115deg, #ffffff 0%, #f8fafc 68%, #eff6ff 100%);
            display: flex;
            align-items: center;
            gap: 18px;
            box-shadow: 0 8px 24px rgba(15, 23, 42, 0.06);
            margin-bottom: 1.25rem;
        }
        .brand-logo {
            width: 62px;
            height: 62px;
            flex: 0 0 62px;
        }
        .brand-logo svg {
            display: block;
            width: 100%;
            height: 100%;
        }
        .brand-kicker {
            color: #c2410c;
            font-size: 0.62rem;
            font-weight: 800;
            letter-spacing: 0.15em;
        }
        .brand-title {
            color: #0f172a;
            font-size: 1.45rem;
            font-weight: 800;
            letter-spacing: -0.035em;
            line-height: 1.25;
        }
        .brand-badge {
            display: inline-block;
            margin-left: 8px;
            padding: 2px 7px;
            border: 1px solid #fed7aa;
            border-radius: 999px;
            background: #fff7ed;
            color: #c2410c;
            font-size: 0.58rem;
            letter-spacing: 0.08em;
            vertical-align: middle;
        }
        .brand-subtitle {
            color: #64748b;
            font-size: 0.77rem;
            margin-top: 2px;
        }
        .filter-count {
            padding-top: 0.55rem;
            color: #64748b;
            font-size: 0.78rem;
            font-weight: 700;
            text-align: right;
        }
        .market-card {
            margin: 0.7rem 0 1rem;
            padding: 20px 22px 16px;
            border: 1px solid #dbe3ee;
            border-radius: 16px;
            background: linear-gradient(135deg, #ffffff 0%, #f8fafc 72%, #eff6ff 100%);
            box-shadow: 0 8px 24px rgba(15, 23, 42, 0.05);
        }
        .market-card-top {
            display: flex;
            align-items: center;
            justify-content: space-between;
            gap: 8px;
        }
        .market-eyebrow, .market-sample, .market-median-label,
        .price-range-labels small, .walkaway-card span {
            font-size: 0.65rem;
            font-weight: 800;
            letter-spacing: 0.08em;
        }
        .market-eyebrow {
            color: #c2410c;
        }
        .market-sample {
            padding: 5px 9px;
            border-radius: 999px;
            background: #e2e8f0;
            color: #334155;
            letter-spacing: 0;
        }
        .market-car {
            margin: 8px 0 0;
            color: #0f172a;
            font-size: 1.3rem;
            font-weight: 800;
            letter-spacing: -0.025em;
            line-height: 1.25;
        }
        .market-context, .market-card-foot {
            color: #64748b;
            font-size: 0.76rem;
        }
        .market-context {
            margin-top: 4px;
        }
        .market-median-label {
            margin-top: 20px;
            color: #64748b;
        }
        .market-median-value {
            margin-top: 2px;
            color: #0f172a;
            font-size: clamp(1.7rem, 5vw, 2.45rem);
            font-weight: 850;
            letter-spacing: -0.045em;
            line-height: 1.15;
        }
        .price-range {
            position: relative;
            height: 18px;
            margin: 12px 4px 4px;
        }
        .price-range-track {
            position: absolute;
            top: 7px;
            right: 0;
            left: 0;
            height: 5px;
            border-radius: 999px;
            background: linear-gradient(90deg, #cbd5e1, #fdba74 50%, #f97316);
        }
        .price-range-marker {
            position: absolute;
            top: 1px;
            width: 17px;
            height: 17px;
            transform: translateX(-50%);
            border: 3px solid #ffffff;
            border-radius: 50%;
            background: #c2410c;
            box-shadow: 0 0 0 2px #c2410c, 0 2px 6px rgba(15, 23, 42, 0.2);
        }
        .price-range-labels {
            display: flex;
            justify-content: space-between;
            gap: 8px;
        }
        .price-range-labels span {
            display: flex;
            flex-direction: column;
            gap: 2px;
        }
        .price-range-labels small {
            color: #94a3b8;
            font-size: 0.56rem;
        }
        .price-range-labels strong {
            color: #334155;
            font-size: 0.78rem;
        }
        .price-range-caption {
            align-self: center;
            color: #94a3b8;
            font-size: 0.65rem;
        }
        .price-range-right {
            text-align: right;
        }
        .market-card-foot {
            margin-top: 13px;
            padding-top: 10px;
            border-top: 1px solid #e2e8f0;
        }
        .market-cache-note {
            margin-top: 5px;
            color: #475569;
            font-size: 0.7rem;
        }
        .walkaway-card {
            display: flex;
            flex-direction: column;
            gap: 5px;
            margin: 4px 0 14px;
            padding: 15px 17px;
            border: 1px solid #86efac;
            border-left: 5px solid #059669;
            border-radius: 12px;
            background: #ecfdf5;
        }
        .walkaway-card span {
            color: #047857;
        }
        .walkaway-card strong {
            color: #065f46;
            font-size: clamp(1.55rem, 5vw, 2rem);
            font-weight: 850;
            letter-spacing: -0.04em;
            line-height: 1.2;
        }
        .walkaway-card small {
            color: #047857;
            font-size: 0.74rem;
        }
        @media (max-width: 520px) {
            .brand-header {
                min-height: 78px;
                gap: 12px;
                padding: 12px;
                border-radius: 14px;
            }
            .brand-logo {
                width: 50px;
                height: 50px;
                flex-basis: 50px;
            }
            .brand-title {
                font-size: 1.2rem;
            }
            .brand-subtitle {
                font-size: 0.7rem;
            }
            .market-card {
                padding: 16px 15px 13px;
                border-radius: 14px;
            }
            .market-car {
                font-size: 1.15rem;
            }
            .price-range-caption {
                display: none;
            }
        }
        
        /* Mobile Metric Card Styling */
        @media (max-width: 768px) {
            [data-testid="column"] {
                width: 100% !important;
                flex: 1 1 100% !important;
                margin-bottom: 10px !important;
            }
            div[data-testid="stMetricValue"] {
                font-size: 1.4rem !important;
            }
        }
    </style>
""", unsafe_allow_html=True)# Tambahkan CSS ini di bagian st.markdown CSS atas file app.py kamu
st.markdown("""
    <style>
        /* Responsive Viewport Adjustments */
        .block-container {
            padding-top: 1.8rem !important;
            padding-bottom: 2rem !important;
            padding-left: 1rem !important;
            padding-right: 1rem !important;
        }
        
        /* Touch Friendly Buttons for Mobile */
        .stButton > button {
            border-radius: 8px !important;
            height: 3rem !important;
            font-size: 1rem !important;
            font-weight: 700 !important;
        }
        
        /* Mobile Metric Card Styling */
        @media (max-width: 768px) {
            [data-testid="column"] {
                width: 100% !important;
                flex: 1 1 100% !important;
                margin-bottom: 10px !important;
            }
            div[data-testid="stMetricValue"] {
                font-size: 1.4rem !important;
            }
        }
    </style>
""", unsafe_allow_html=True)
st.markdown("""
    <style>
        .block-container {
            padding-top: 2.5rem !important;
            padding-bottom: 1rem !important;
        }
        [data-testid="stHeader"] {
            background-color: rgba(0, 0, 0, 0) !important;
        }
    </style>
""", unsafe_allow_html=True)

# ==================== EXPORT PDF ====================
def generate_pdf_deal_sheet(nama_showroom, info_search, tahun_range, filter_tipe, total_sampel,
                             median_price, min_price, max_price, 
                             biaya_pajak, biaya_cat, biaya_mesin, biaya_salon, 
                             target_margin, walk_away_price, total_pr, total_modal):
    buffer = io.BytesIO()
    doc = SimpleDocTemplate(
        buffer, 
        pagesize=A4, 
        rightMargin=36, 
        leftMargin=36, 
        topMargin=36, 
        bottomMargin=36
    )
    
    styles = getSampleStyleSheet()
    
    # Custom Styles
    style_title = ParagraphStyle(
        'DocTitle',
        parent=styles['Heading1'],
        fontSize=20,
        leading=24,
        textColor=colors.HexColor('#0F172A'),
        fontName='Helvetica-Bold'
    )
    style_body = ParagraphStyle(
        'Body',
        parent=styles['Normal'],
        fontSize=8.5,
        leading=12.5,
        textColor=colors.HexColor('#334155')
    )
    style_heading = ParagraphStyle(
        'SecHeading',
        parent=styles['Heading2'],
        fontSize=11,
        leading=15,
        textColor=colors.HexColor('#0F172A'),
        fontName='Helvetica-Bold',
        spaceBefore=10,
        spaceAfter=6
    )

    story = []

    # 1. HEADER BRANDING & SHOWROOM
    waktu_cetak = datetime.now().strftime("%d %B %Y, %H:%M WIB")
    header_data = [
        [
            Paragraph("<b>ValuasiOto.id</b><br/><font size=8 color='#64748B'>B2B Market Intelligence Platform</font>", style_title),
            Paragraph(f"<b>LEMBAR PENAWARAN RESMI</b><br/><font size=8 color='#64748B'>Showroom: <b>{nama_showroom}</b><br/>Tanggal: {waktu_cetak}</font>", ParagraphStyle('RightText', alignment=2, parent=style_body))
        ]
    ]
    t_header = Table(header_data, colWidths=[260, 260])
    t_header.setStyle(TableStyle([('VALIGN', (0,0), (-1,-1), 'MIDDLE')]))
    story.append(t_header)
    
    story.append(Spacer(1, 8))
    story.append(HRFlowable(width="100%", thickness=1.5, color=colors.HexColor('#FF6B00'), spaceBefore=4, spaceAfter=12))

    # 2. DETAIL UNIT & RINGKASAN PASAR (LENGKAP SPESIFIKASI QUERY)
    story.append(Paragraph("📌 <b>1. Spesifikasi Unit & Intelijen Data Pasar</b>", style_heading))
    
    min_yr, max_yr = tahun_range
    year_display = (
        "Semua tahun"
        if min_yr == 1980 and max_yr == date.today().year + 1
        else f"{min_yr} – {max_yr}"
    )
    variabel_tipe = filter_tipe if filter_tipe else "Semua Varian/Tipe"
    
    unit_info = (
        f"<b>Merek & Model:</b> {info_search.get('merek')} {info_search.get('model')}<br/>"
        f"<b>Tahun Pembuatan:</b> {year_display}<br/>"
        f"<b>Wilayah:</b> {info_search.get('location', 'Tidak ditentukan')}<br/>"
        f"<b>Varian / Spesifikasi:</b> {variabel_tipe}<br/>"
        f"<b>Sampel Analisis:</b> {total_sampel} Unit Valid<br/>"
        f"<b>Sumber Data:</b> "
        f"{'Input manual/CSV' if info_search.get('mode') == 'csv' else 'Listing marketplace'}"
    )
    
    market_table_data = [
        ["Spesifikasi Parameter Pencarian", "Harga Terendah", "Harga Pasar (Median)", "Harga Tertinggi"],
        [
            Paragraph(unit_info, style_body),
            f"Rp {min_price:,.0f}".replace(",", "."),
            f"Rp {median_price:,.0f}".replace(",", "."),
            f"Rp {max_price:,.0f}".replace(",", ".")
        ]
    ]
    t_market = Table(market_table_data, colWidths=[210, 95, 105, 110])
    t_market.setStyle(TableStyle([
        ('BACKGROUND', (0,0), (-1,0), colors.HexColor('#F1F5F9')),
        ('TEXTCOLOR', (0,0), (-1,0), colors.HexColor('#0F172A')),
        ('FONTNAME', (0,0), (-1,0), 'Helvetica-Bold'),
        ('FONTSIZE', (0,0), (-1,-1), 8.5),
        ('ALIGN', (1,0), (-1,-1), 'CENTER'),
        ('VALIGN', (0,0), (-1,-1), 'MIDDLE'),
        ('GRID', (0,0), (-1,-1), 0.5, colors.HexColor('#CBD5E1')),
        ('TOPPADDING', (0,0), (-1,-1), 6),
        ('BOTTOMPADDING', (0,0), (-1,-1), 6),
    ]))
    story.append(t_market)

    story.append(Spacer(1, 12))

    # 3. RINCIAN ESTIMASI BIAYA PEMBENAHAN (PR)
    story.append(Paragraph("🛠️ <b>2. Rincian Estimasi Biaya Pembenahan & Perbaikan (PR)</b>", style_heading))
    
    pr_data = [
        ["Komponen Pembenahan", "Estimasi Biaya (Rp)"],
        ["Tunggakan Pajak / Mutasi Surat", f"Rp {biaya_pajak:,.0f}".replace(",", ".")],
        ["Perbaikan Bodi & Cat", f"Rp {biaya_cat:,.0f}".replace(",", ".")],
        ["Perbaikan Mesin & Kaki-kaki", f"Rp {biaya_mesin:,.0f}".replace(",", ".")],
        ["Detailing & Salon Mobil", f"Rp {biaya_salon:,.0f}".replace(",", ".")],
        ["TOTAL ESTIMASI PERBAIKAN (PR)", f"Rp {total_pr:,.0f}".replace(",", ".")]
    ]
    t_pr = Table(pr_data, colWidths=[340, 180])
    t_pr.setStyle(TableStyle([
        ('BACKGROUND', (0,0), (-1,0), colors.HexColor('#F1F5F9')),
        ('FONTNAME', (0,0), (-1,0), 'Helvetica-Bold'),
        ('FONTNAME', (0,-1), (-1,-1), 'Helvetica-Bold'),
        ('BACKGROUND', (0,-1), (-1,-1), colors.HexColor('#FEF3C7')),
        ('ALIGN', (1,0), (1,-1), 'RIGHT'),
        ('GRID', (0,0), (-1,-1), 0.5, colors.HexColor('#CBD5E1')),
        ('TOPPADDING', (0,0), (-1,-1), 5),
        ('BOTTOMPADDING', (0,0), (-1,-1), 5),
    ]))
    story.append(t_pr)

    story.append(Spacer(1, 12))

    # 4. HIGHLIGHT REKOMENDASI BELI (WALK-AWAY PRICE)
    story.append(Paragraph("💡 <b>3. Valuasi Penawaran Resmi (Walk-Away Price)</b>", style_heading))
    
    summary_box_data = [
        [
            Paragraph("<b>REKOMENDASI HARGA BELI MAKSIMAL:</b>", ParagraphStyle('W1', parent=style_body, fontSize=10.5, textColor=colors.HexColor('#1E293B'))),
            Paragraph(f"<b>Rp {walk_away_price:,.0f}</b>".replace(",", "."), ParagraphStyle('W2', parent=style_body, fontSize=15, textColor=colors.HexColor('#B91C1C'), alignment=2))
        ],
        [
            Paragraph(f"Target Untung/Margin Showroom: <b>Rp {target_margin:,.0f}</b> | Total Modal Investasi: <b>Rp {total_modal:,.0f}</b>".replace(",", "."), style_body),
            ""
        ]
    ]
    t_summary = Table(summary_box_data, colWidths=[300, 220])
    t_summary.setStyle(TableStyle([
        ('SPAN', (0,1), (1,1)),
        ('BACKGROUND', (0,0), (-1,-1), colors.HexColor('#FEE2E2')),
        ('BOX', (0,0), (-1,-1), 1.5, colors.HexColor('#EF4444')),
        ('PADDING', (0,0), (-1,-1), 8),
        ('VALIGN', (0,0), (-1,-1), 'MIDDLE'),
    ]))
    story.append(t_summary)

    story.append(Spacer(1, 16))
    
    # FOOTER & DISCLAIMER
    disclaimer_text = (
        "<i>Dokumen ini dihasilkan otomatis berdasarkan data harga iklan yang "
        "dimasukkan atau dikumpulkan dari listing marketplace. Harga iklan "
        "bukan harga transaksi dan perlu diverifikasi terhadap kondisi unit.</i>"
    )
    story.append(Paragraph(disclaimer_text, ParagraphStyle('Disc', parent=style_body, fontSize=7.5, textColor=colors.HexColor('#94A3B8'))))

    doc.build(story)
    buffer.seek(0)
    return buffer

# ==================== PREMIUM HEADER ====================
with open(LOGO_PATH, "r", encoding="utf-8") as logo_file:
    logo_svg = logo_file.read()

st.markdown(
    f"""
        <div class="brand-header">
            <div class="brand-logo">{logo_svg}</div>
            <div class="brand-copy">
            <div class="brand-kicker">USED CAR MARKET INTELLIGENCE</div>
            <div class="brand-title">{NAMA_PRODUK}<span class="brand-badge">B2B</span></div>
            <div class="brand-subtitle">Data pasar yang lebih jelas untuk keputusan beli yang lebih yakin.</div>
            </div>
        </div>
    """,
    unsafe_allow_html=True,
)

# Helper Format Rupiah
def fmt_rp(val):
    return f"Rp {val:,.0f}".replace(",", ".")


# ==================== INISIALISASI SESSION STATE ====================
if "data_searched" not in st.session_state:
    st.session_state.data_searched = False
if "raw_data" not in st.session_state:
    st.session_state.raw_data = []
if "search_info" not in st.session_state:
    st.session_state.search_info = {}

# ==================== HELPER FUNCTION PARSING & FILTERING ====================
def clean_price_int(price_str):
    price = parse_listing_price(price_str)
    if price is None and price_str:
        print(f"⚠️ Harga listing diabaikan karena tidak valid atau di luar batas: {price_str}")
        return 0
    return price or 0

def extract_year_from_text(text):
    match = re.search(r'\b(20[0-2][0-9]|19[8-9][0-9])\b', str(text))
    return int(match.group(1)) if match else None

# HELPER KUNCI: Validasi Wajib Merek DAN Model
def matches_merek_model(title_text, merek_car, model_car):
    if not title_text:
        return False
    t_low = title_text.lower()
    m_clean = merek_car.lower().strip()
    model_keywords = [w for w in model_car.lower().split() if len(w) >= 2]
    
    merek_match = m_clean in t_low
    model_match = any(kw in t_low for kw in model_keywords) if model_keywords else True
    return merek_match and model_match

# ==================== SCRAPER ENGINES ====================
# 1. SUBPROCESS BRIDGE OLX ENGINE (DENGAN FILE EXCHANGE)
def scrape_olx_id(merek_car, model_car):
    try:
        app_dir = os.path.dirname(os.path.abspath(__file__))
        script_path = os.path.join(app_dir, "test_olx.py")
        with tempfile.TemporaryDirectory(prefix="valuasi-olx-") as temp_dir:
            temp_json_file = os.path.join(temp_dir, "results.json")
            process = subprocess.run(
                [
                    sys.executable,
                    script_path,
                    merek_car,
                    model_car,
                    temp_json_file,
                ],
                capture_output=True,
                text=True,
                timeout=40,
                cwd=app_dir,
            )

            if os.path.exists(temp_json_file):
                with open(temp_json_file, "r", encoding="utf-8") as result_file:
                    return json.load(result_file)
            print(f"⚠️ Stderr OLX Process: {process.stderr}")
            
    except Exception as e:
        print(f"⚠️ Subprocess OLX Error: {e}")
        
    return []

# 2. ICAR PLATFORMS (Mobil123 & Carmudi) - FIXED MODEL FILTER
def scrape_icar_platform(site_name, domain_url, merek_car, model_car, scraper):
    data_list = []
    merek_clean = merek_car.lower().strip()
    model_clean = model_car.lower().strip().replace(" ", "-") if model_car else ""
    
    urls = []
    if model_clean:
        urls.append(f"{domain_url}/mobil-dijual/{merek_clean}/{model_clean}/indonesia")
    urls.append(f"{domain_url}/mobil-dijual/{merek_clean}/indonesia")
    urls.append(f"{domain_url}/mobil-dijual/indonesia?q={merek_car}+{model_car}".strip("+"))
    
    for url in urls:
        try:
            res = scraper.get(url, timeout=8)
            if res.status_code == 200:
                soup = BeautifulSoup(res.text, 'html.parser')
                structured_listings = []
                for script in soup.find_all("script", type="application/ld+json"):
                    try:
                        structured_listings.extend(
                            extract_vehicle_schema_listings(
                                json.loads(script.string or script.get_text()),
                                site_name,
                            )
                        )
                    except (json.JSONDecodeError, TypeError, ValueError):
                        continue

                structured_listings = [
                    item
                    for item in structured_listings
                    if matches_merek_model(
                        item["title"], merek_car, model_car
                    )
                ]
                if structured_listings:
                    return structured_listings

                articles = soup.find_all(['article', 'div'], class_=re.compile(r'listing|card|item', re.I))
                for article in articles:
                    title_elem = article.find(['h2', 'h3', 'h4', 'a'], class_=re.compile(r'title|link|name', re.I))
                    price_elem = article.find(string=re.compile(r'Rp\s*[\d\.,]+', re.I))
                    link_elem = article.find('a', href=True)
                    
                    if title_elem and price_elem:
                        title_text = title_elem.get_text(strip=True)
                        
                        # FILTER PRESISI: Wajib Merek DAN Model
                        if not matches_merek_model(title_text, merek_car, model_car):
                            continue
                            
                        price_val = clean_price_int(price_elem)
                        if price_val > 30000000:
                            url_link = link_elem['href'] if link_elem else ""
                            if url_link and not url_link.startswith("http"):
                                url_link = domain_url + url_link

                            mileage_min_km, mileage_max_km = extract_mileage_range(
                                f"{title_text} {article.get_text(' ', strip=True)}"
                            )
                            listing = {
                                "source": site_name,
                                "title": title_text,
                                "price": price_val,
                                "year": extract_year_from_text(title_text),
                                "url": url_link if url_link else domain_url,
                                "mileage_min_km": mileage_min_km,
                                "mileage_max_km": mileage_max_km,
                                "location": extract_card_location(article),
                            }
                            data_list.append(listing)
                if len(data_list) > 0:
                    break
        except Exception:
            continue
    return data_list

# 3. OTO.COM ENGINE - FIXED MODEL FILTER
def scrape_oto_com(merek_car, model_car, scraper):
    data_list = []
    query = f"{merek_car} {model_car}".strip()
    url = f"https://www.oto.com/mobil-bekas/search/{query.replace(' ', '+')}"
    try:
        res = scraper.get(url, timeout=8)
        if res.status_code == 200:
            soup = BeautifulSoup(res.text, 'html.parser')
            json_scripts = soup.find_all('script', type='application/ld+json')
            for script in json_scripts:
                try:
                    js_data = json.loads(script.string)
                    items = js_data if isinstance(js_data, list) else js_data.get('itemListElement', [js_data])
                    for item in items:
                        curr = item.get('item', item)
                        name = curr.get('name') or curr.get('title')
                        offers = curr.get('offers', {})
                        price = offers.get('price') or offers.get('lowPrice')
                        url_link = curr.get('url', 'https://www.oto.com')
                        
                        if name and price and matches_merek_model(name, merek_car, model_car):
                            price_val = clean_price_int(price)
                            if price_val > 30000000:
                                data_list.append({
                                    "source": "Oto.com",
                                    "title": name,
                                    "price": price_val,
                                    "year": extract_year_from_text(name),
                                    "url": url_link if url_link.startswith("http") else "https://www.oto.com" + url_link
                                })
                except Exception:
                    continue
    except Exception:
        pass
    return data_list

# 4. CARSOME ENGINE - FIXED MODEL FILTER
def scrape_carsome_id(merek_car, model_car, scraper):
    data_list = []
    q_str = f"{merek_car}+{model_car}".strip("+")
    url = f"https://www.carsome.id/buy-car?keyword={q_str}"
    try:
        res = scraper.get(url, timeout=8)
        if res.status_code == 200:
            soup = BeautifulSoup(res.text, 'html.parser')
            cards = soup.find_all(['div', 'article'], class_=re.compile(r'card|car|item', re.I))
            for card in cards:
                t_elem = card.find(['h2', 'h3', 'p', 'div'], class_=re.compile(r'title|name', re.I))
                p_elem = card.find(string=re.compile(r'Rp\s*[\d\.,]+', re.I))
                l_elem = card.find('a', href=True)
                if t_elem and p_elem:
                    title_text = t_elem.get_text(strip=True)
                    if matches_merek_model(title_text, merek_car, model_car):
                        price_val = clean_price_int(p_elem)
                        if price_val > 30000000:
                            u_link = l_elem['href'] if l_elem else "https://www.carsome.id"
                            if not u_link.startswith("http"):
                                u_link = "https://www.carsome.id" + u_link
                            data_list.append({
                                "source": "Carsome",
                                "title": title_text,
                                "price": price_val,
                                "year": extract_year_from_text(title_text),
                                "url": u_link
                            })
    except Exception:
        pass
    return data_list

# 5. CARRO ENGINE - FIXED MODEL FILTER
def scrape_carro_id(merek_car, model_car, scraper):
    data_list = []
    q_str = f"{merek_car}+{model_car}".strip("+")
    url = f"https://carro.co.id/buy-car?q={q_str}"
    try:
        res = scraper.get(url, timeout=8)
        if res.status_code == 200:
            soup = BeautifulSoup(res.text, 'html.parser')
            cards = soup.find_all(['div', 'article'], class_=re.compile(r'card|car|item', re.I))
            for card in cards:
                t_elem = card.find(['h2', 'h3', 'p', 'div'], class_=re.compile(r'title|name', re.I))
                p_elem = card.find(string=re.compile(r'Rp\s*[\d\.,]+', re.I))
                l_elem = card.find('a', href=True)
                if t_elem and p_elem:
                    title_text = t_elem.get_text(strip=True)
                    if matches_merek_model(title_text, merek_car, model_car):
                        price_val = clean_price_int(p_elem)
                        if price_val > 30000000:
                            u_link = l_elem['href'] if l_elem else "https://carro.co.id"
                            if not u_link.startswith("http"):
                                u_link = "https://carro.co.id" + u_link
                            data_list.append({
                                "source": "Carro",
                                "title": title_text,
                                "price": price_val,
                                "year": extract_year_from_text(title_text),
                                "url": u_link
                            })
    except Exception:
        pass
    return data_list
# ==================== PARALLEL SOURCE FETCH ====================
def fetch_all_sources_parallel(merek_car, model_car):
    scraper = cloudscraper.create_scraper(
        browser={'browser': 'chrome', 'platform': 'windows', 'desktop': True}
    )
    with concurrent.futures.ThreadPoolExecutor(max_workers=6) as executor:
        f_olx = executor.submit(scrape_olx_id, merek_car, model_car)
        f_m123 = executor.submit(scrape_icar_platform, "Mobil123", "https://www.mobil123.com", merek_car, model_car, scraper)
        f_carmudi = executor.submit(scrape_icar_platform, "Carmudi", "https://www.carmudi.co.id", merek_car, model_car, scraper)
        f_oto = executor.submit(scrape_oto_com, merek_car, model_car, scraper)
        f_carsome = executor.submit(scrape_carsome_id, merek_car, model_car, scraper)
        f_carro = executor.submit(scrape_carro_id, merek_car, model_car, scraper)
        
        data_olx = f_olx.result()
        data_m123 = f_m123.result()
        data_carmudi = f_carmudi.result()
        data_oto = f_oto.result()
        data_carsome = f_carsome.result()
        data_carro = f_carro.result()
        
    total_data = data_olx + data_m123 + data_carmudi + data_oto + data_carsome + data_carro
    counts = {
        "OLX": len(data_olx),
        "Mobil123": len(data_m123),
        "Carmudi": len(data_carmudi),
        "Oto.com": len(data_oto),
        "Carsome": len(data_carsome),
        "Carro": len(data_carro)
    }
    return total_data, counts


# ==================== PENCARIAN SIDEBAR & HALAMAN AWAL ====================
merek_list = [
    "Toyota",
    "Honda",
    "Daihatsu",
    "Mitsubishi",
    "Suzuki",
    "Nissan",
    "Hyundai",
    "Wuling",
    "Lainnya",
]

with st.sidebar:
    st.image(LOGO_PATH, width=58)
    st.markdown("### Pencarian pasar")
    st.caption("Cari listing pembanding dari beberapa marketplace.")
    with st.form("sidebar_market_search_form"):
        sidebar_merek = st.selectbox(
            "Merek mobil",
            merek_list,
            key="sidebar_make",
        )
        sidebar_model = st.text_input(
            "Model / kata kunci",
            value="Avanza",
            placeholder="Contoh: Brio, Avanza, Innova",
            key="sidebar_model",
        ).strip()
        sidebar_location = (
            st.text_input(
                "Wilayah pencarian",
                value="Semua wilayah",
                placeholder="Contoh: Jakarta Selatan",
                key="sidebar_location",
                help="Kosongkan atau gunakan Semua wilayah untuk pencarian nasional.",
            ).strip()
            or "Semua wilayah"
        )
        sidebar_force_scrape = st.checkbox(
            "Ambil data terbaru (abaikan cache)",
            key="sidebar_force_scrape",
            help="Abaikan cache Supabase dan jalankan scraper kembali.",
        )
        btn_cari_sidebar = st.form_submit_button(
            "🔍 Cari Data Pasar",
            type="primary",
            use_container_width=True,
        )

btn_cari_body = False
if not st.session_state.data_searched:
    st.markdown("### Mulai pencarian valuasi")
    st.caption(
        "Pilih kendaraan dan wilayah. Hasil pembanding akan ditampilkan "
        "setelah pencarian selesai."
    )
    with st.container(border=True):
        with st.form("landing_market_search_form"):
            landing_cols = st.columns([1, 1.4, 1.4])
            with landing_cols[0]:
                landing_merek = st.selectbox(
                    "Merek mobil",
                    merek_list,
                    key="landing_make",
                )
            with landing_cols[1]:
                landing_model = st.text_input(
                    "Model / kata kunci",
                    value="Avanza",
                    placeholder="Contoh: Brio, Avanza, Innova",
                    key="landing_model",
                ).strip()
            with landing_cols[2]:
                landing_location = (
                    st.text_input(
                        "Wilayah pencarian",
                        value="Semua wilayah",
                        placeholder="Contoh: Jakarta Selatan",
                        key="landing_location",
                    ).strip()
                    or "Semua wilayah"
                )
            landing_force_scrape = st.checkbox(
                "Ambil data terbaru (abaikan cache)",
                key="landing_force_scrape",
                help="Abaikan cache Supabase dan jalankan scraper kembali.",
            )
            btn_cari_body = st.form_submit_button(
                "🔍 Cari Data Pasar",
                type="primary",
                use_container_width=True,
            )

if btn_cari_body:
    merek = landing_merek
    model_input = landing_model
    lokasi_input = landing_location
    force_scrape = landing_force_scrape
    btn_cari = True
elif btn_cari_sidebar:
    merek = sidebar_merek
    model_input = sidebar_model
    lokasi_input = sidebar_location
    force_scrape = sidebar_force_scrape
    btn_cari = True
else:
    btn_cari = False

# ==================== PROSES PENCARIAN ====================
if btn_cari:
    st.session_state["vehicle_year_filter"] = "Semua tahun"
    if not model_input:
        st.error("Isi model mobil sebelum mencari.")
    elif not lokasi_input:
        st.error("Isi wilayah pencarian atau gunakan 'Semua wilayah'.")
    else:
        try:
            _, db_client = get_supabase_clients()
            freshness_hours = int(get_app_setting("CACHE_FRESHNESS_HOURS", "24"))
            minimum_samples = int(get_app_setting("CACHE_MIN_LISTINGS", "5"))
            max_search_year = date.today().year + 1
            cached_data = deduplicate_listings(
                get_fresh_listings(
                    db_client,
                    merek,
                    model_input,
                    1980,
                    max_search_year,
                    lokasi_input,
                    freshness_hours=freshness_hours,
                )
            )
            if (
                len(cached_data) >= minimum_samples
                and not force_scrape
            ):
                raw_data = cached_data
                counts = {}
                for item in raw_data:
                    counts[item["source"]] = counts.get(item["source"], 0) + 1
                mode = "cache"
                st.session_state.cache_message = (
                    f"Data Supabase diperbarui dalam {freshness_hours} jam terakhir."
                )
            else:
                cache_status = (
                    "Scrape ulang diminta."
                    if force_scrape
                    else f"Cache belum cukup ({len(cached_data)}/{minimum_samples} listing)."
                )
                with st.spinner(
                    f"{cache_status} Mengambil data dari sumber yang tersedia..."
                ):
                    scraped_data, counts = fetch_all_sources_parallel(
                        merek, model_input
                    )

                collected_at = datetime.now(timezone.utc).isoformat()
                raw_data = []
                stored_records = []
                for item in scraped_data:
                    enriched = {
                        **item,
                        "make": merek.casefold(),
                        "model": model_input.casefold(),
                        "variant": "",
                        "mileage_min_km": item.get("mileage_min_km"),
                        "mileage_max_km": item.get("mileage_max_km"),
                        "location": item.get("location"),
                        "collected_at": collected_at,
                    }
                    raw_data.append(enriched)
                    if enriched.get("price", 0) > 30_000_000:
                        stored_records.append(enriched)
                raw_data = deduplicate_listings(raw_data)
                saved_count = save_listings(db_client, stored_records)
                mode = "scrape"
                located_count = sum(bool(item.get("location")) for item in raw_data)
                mileage_count = sum(
                    item.get("mileage_min_km") is not None
                    for item in raw_data
                )
                st.session_state.cache_message = (
                    f"{cache_status} {saved_count} listing disimpan; "
                    f"{located_count} memiliki lokasi dan {mileage_count} memiliki kilometer."
                )

            st.session_state.data_searched = True
            st.session_state.raw_data = raw_data
            st.session_state.search_info = {
                "merek": merek,
                "model": model_input,
                "counts": counts,
                "mode": mode,
                "location": lokasi_input,
            }
            st.rerun()
        except Exception as error:
            st.error(f"Pencarian Supabase gagal: {error}")

# ==================== FILTERING DINAMIS & DASHBOARD ====================
if st.session_state.data_searched:
    raw_data = st.session_state.raw_data
    info = st.session_state.search_info

    with st.container(border=True):
        filter_title, filter_count = st.columns([3, 1])
        with filter_title:
            st.markdown("#### Filter listing")
        with filter_count:
            st.markdown(
                f"<div class='filter-count'>{len(raw_data)} listing ditemukan</div>",
                unsafe_allow_html=True,
            )
        st.caption("Persempit hasil berdasarkan tahun, varian, atau kilometer.")
        filter_cols = st.columns([1, 1.5])
        with filter_cols[0]:
            year_options = ["Semua tahun"] + list(
                range(date.today().year + 1, 1979, -1)
            )
            selected_year = st.selectbox(
                "Tahun kendaraan",
                options=year_options,
                format_func=lambda value: str(value),
                help="Pilih satu tahun tertentu atau lihat semua tahun.",
                key="vehicle_year_filter",
            )
        with filter_cols[1]:
            filter_tipe = st.text_input(
                "Varian / spesifikasi",
                placeholder="Contoh: RS, Satya, CVT",
                help="Cari kata yang ada pada judul iklan.",
            ).strip()
        filter_mileage = st.checkbox(
            "Batasi kilometer",
            help="Listing tanpa informasi kilometer tidak akan ditampilkan.",
        )
        mileage_range = st.slider(
            "Rentang kilometer",
            min_value=0,
            max_value=1_000_000,
            value=(0, 300_000),
            step=10_000,
            disabled=not filter_mileage,
        )
    if selected_year == "Semua tahun":
        tahun_range = (1980, date.today().year + 1)
        year_display = "Semua tahun"
        selected_year_value = None
    else:
        selected_year_value = int(selected_year)
        tahun_range = (selected_year_value, selected_year_value)
        year_display = str(selected_year_value)
    min_mileage_km, max_mileage_km = mileage_range

    filtered_data = []
    for item in raw_data:
        if info.get("location", "").casefold() not in (
            "",
            "semua wilayah",
            "seluruh indonesia",
        ):
            location_filter = info["location"].casefold()
            if location_filter not in (item.get("location") or "").casefold():
                continue

        if selected_year_value is not None and item.get("year") != selected_year_value:
            continue

        if filter_mileage:
            mileage_min, mileage_max = listing_mileage_bounds(item)
            if (
                mileage_min is None
                or mileage_max is None
                or mileage_min > max_mileage_km
                or mileage_max < min_mileage_km
            ):
                continue
                
        if filter_tipe:
            if filter_tipe.lower() not in item["title"].lower():
                continue
                
        filtered_data.append(item)
    prices = [item["price"] for item in filtered_data]
    counts = info.get("counts", {})

    if prices:
        filtered_counts = {}
        for item in filtered_data:
            filtered_counts[item["source"]] = (
                filtered_counts.get(item["source"], 0) + 1
            )
        source_summary = ", ".join(
            f"{source}: {count}"
            for source, count in sorted(filtered_counts.items())
        )
        mileage_min_values = [
            listing_mileage_bounds(item)[0]
            for item in filtered_data
            if listing_mileage_bounds(item)[0] is not None
        ]
        mileage_max_values = [
            listing_mileage_bounds(item)[1]
            for item in filtered_data
            if listing_mileage_bounds(item)[1] is not None
        ]
        harga_median = int(np.median(prices))
        harga_min = min(prices)
        harga_max = max(prices)
        median_position = (
            50
            if harga_max == harga_min
            else (harga_median - harga_min) / (harga_max - harga_min) * 100
        )
        median_position = max(3, min(97, median_position))
        car_title = escape(
            f"{info['merek']} {info['model']} · {year_display}"
        )
        location_label = escape(info.get("location") or "Semua wilayah")
        source_label = escape(source_summary) if source_summary else ""
        mileage_summary = (
            f"Median kilometer {fmt_km(np.median(mileage_min_values), np.median(mileage_max_values))}"
            f" · {len(mileage_min_values)}/{len(filtered_data)} mencantumkan kilometer"
            if mileage_min_values
            else "Kilometer belum tercatat pada listing"
        )
        cache_summary = st.session_state.get("cache_message")
        cache_note = (
            f"<div class='market-cache-note'>{escape(cache_summary)}</div>"
            if cache_summary
            else ""
        )
        st.markdown(
            f"""
            <section class="market-card">
                <div class="market-card-top">
                    <span class="market-eyebrow">RINGKASAN PASAR</span>
                    <span class="market-sample">{len(filtered_data)} listing</span>
                </div>
                <h2 class="market-car">{car_title}</h2>
                <div class="market-context">{location_label}{f" · {source_label}" if source_label else ""}</div>
                <div class="market-median-label">MEDIAN HARGA IKLAN</div>
                <div class="market-median-value">{fmt_rp(harga_median)}</div>
                <div class="price-range">
                    <div class="price-range-track"></div>
                    <div class="price-range-marker" style="left: {median_position:.2f}%"></div>
                </div>
                <div class="price-range-labels">
                    <span><small>TERENDAH</small><strong>{fmt_rp(harga_min)}</strong></span>
                    <span class="price-range-caption">Rentang harga iklan</span>
                    <span class="price-range-right"><small>TERTINGGI</small><strong>{fmt_rp(harga_max)}</strong></span>
                </div>
                <div class="market-card-foot">
                    <div>{escape(mileage_summary)}</div>
                    {cache_note}
                </div>
            </section>
            """,
            unsafe_allow_html=True,
        )

        with st.container(border=True):
            st.markdown("#### Simulasi keputusan beli")
            st.caption(
                "Hitung batas harga beli berdasarkan biaya unit dan target margin."
            )
            with st.expander(
                "🧮 1 · Biaya unit & target margin",
                expanded=False,
            ):
                use_calculator = st.checkbox(
                    "Aktifkan perhitungan walk-away price",
                    key="enable_valuation_calculator",
                )
                if use_calculator:
                    st.caption(
                        "Masukkan estimasi biaya pembenahan unit sebelum dijual kembali."
                    )
                    col_input1, col_input2 = st.columns(2)
                    with col_input1:
                        biaya_pajak = st.number_input(
                            "Estimasi Tunggakan Pajak (Rp)",
                            min_value=0,
                            value=0,
                            step=500000,
                            key="valuation_tax_cost",
                        )
                        biaya_cat = st.number_input(
                            "Estimasi Perbaikan Bodi/Cat (Rp)",
                            min_value=0,
                            value=1500000,
                            step=500000,
                            key="valuation_body_cost",
                        )
                        biaya_mesin = st.number_input(
                            "Estimasi Perbaikan Mesin/Kaki-kaki (Rp)",
                            min_value=0,
                            value=1000000,
                            step=500000,
                            key="valuation_engine_cost",
                        )
                    with col_input2:
                        biaya_salon = st.number_input(
                            "Biaya Detailing/Salon (Rp)",
                            min_value=0,
                            value=500000,
                            step=100000,
                            key="valuation_detailing_cost",
                        )
                        target_margin = st.number_input(
                            "Target Untung / Margin Kamu (Rp)",
                            min_value=0,
                            value=10000000,
                            step=1000000,
                            key="valuation_target_margin",
                        )
                else:
                    st.caption(
                        "Aktifkan perhitungan untuk melihat hasil pada panel "
                        "Walk-away price di bawah."
                    )

            with st.expander(
                "🎯 2 · Walk-away price & ekspor PDF",
                expanded=False,
            ):
                if use_calculator:
                    total_pr = biaya_pajak + biaya_cat + biaya_mesin + biaya_salon
                    harga_beli_maksimal = harga_median - total_pr - target_margin
                    total_modal_investasi = harga_beli_maksimal + total_pr
                    persen_diskon = (
                        (harga_median - harga_beli_maksimal) / harga_median
                    ) * 100
                    st.markdown(
                        f"""
                        <div class="walkaway-card">
                            <span>BATAS MAKSIMAL HARGA BELI</span>
                            <strong>{fmt_rp(harga_beli_maksimal)}</strong>
                            <small>Berdasarkan median pasar {fmt_rp(harga_median)}</small>
                        </div>
                        """,
                        unsafe_allow_html=True,
                    )
                    result_cols = st.columns(3)
                    result_cols[0].metric("Biaya unit", fmt_rp(total_pr))
                    result_cols[1].metric("Modal total", fmt_rp(total_modal_investasi))
                    result_cols[2].metric(
                        "Target margin",
                        fmt_rp(target_margin),
                        delta=f"{persen_diskon:.1f}% di bawah median",
                    )
                    st.caption(
                        f"Rincian biaya: pajak {fmt_rp(biaya_pajak)} · "
                        f"bodi/cat {fmt_rp(biaya_cat)} · "
                        f"mesin {fmt_rp(biaya_mesin)} · "
                        f"detailing {fmt_rp(biaya_salon)}."
                    )
                    st.markdown("##### Ekspor lembar penawaran")
                    nama_showroom_input = st.text_input(
                        "Nama showroom / trader",
                        "Auto Jaya Motor",
                        key="valuation_showroom_name",
                    )
                    pdf_bytes = generate_pdf_deal_sheet(
                        nama_showroom=nama_showroom_input,
                        info_search=st.session_state.search_info,
                        tahun_range=tahun_range,
                        filter_tipe=filter_tipe,
                        total_sampel=len(filtered_data),
                        median_price=harga_median,
                        min_price=harga_min,
                        max_price=harga_max,
                        biaya_pajak=biaya_pajak,
                        biaya_cat=biaya_cat,
                        biaya_mesin=biaya_mesin,
                        biaya_salon=biaya_salon,
                        target_margin=target_margin,
                        walk_away_price=harga_beli_maksimal,
                        total_pr=total_pr,
                        total_modal=total_modal_investasi,
                    )
                    safe_merek = str(
                        st.session_state.search_info.get("merek", "Mobil")
                    ).replace(" ", "_")
                    safe_model = str(
                        st.session_state.search_info.get("model", "Model")
                    ).replace(" ", "_")
                    file_pdf_name = (
                        f"Valuasi_{safe_merek}_{safe_model}_"
                        f"{datetime.now().strftime('%Y%m%d')}.pdf"
                    )
                    st.download_button(
                        label="📥 Unduh PDF penawaran",
                        data=pdf_bytes,
                        file_name=file_pdf_name,
                        mime="application/pdf",
                        type="primary",
                        use_container_width=True,
                    )
                else:
                    st.info("Buka panel **Biaya unit & target margin** dan aktifkan kalkulator untuk melihat hasil.")
        st.divider()
        
        # Sub-judul Sampel Data Pasar yang Lebih Proporsional
        st.markdown(f"<p style='font-size: 0.95rem; font-weight: 700; color: #0F172A; margin-bottom: 10px;'>📊 Sampel Harga Iklan ({len(filtered_data)} Listing)</p>", unsafe_allow_html=True)
        
        tab_table, tab_cards = st.tabs(["📋 Tabel Interaktif dengan Link Listing", "🎴 Tampilan Kartu (Cards)"])
        
        with tab_table:
            df = pd.DataFrame(filtered_data)
            df["No"] = range(1, len(df) + 1)
            df["Kilometer"] = df.apply(
                lambda row: fmt_km(*listing_mileage_bounds(row)),
                axis=1,
            )
            
            columns = [
                "No",
                "source",
                "title",
                "year",
                "Kilometer",
                "price",
                "url",
            ]
            labels = [
                "No",
                "Sumber Data",
                "Nama / Varian Mobil",
                "Tahun",
                "Kilometer",
                "Harga Pasar",
                "Link Listing",
            ]
            columns.extend(["location", "collected_at"])
            labels.extend(["Wilayah", "Tanggal Dicatat"])
            df = df.drop(
                columns=["mileage_min_km", "mileage_max_km", "mileage_km"],
                errors="ignore",
            )
            df_display = df[columns].copy()
            df_display.columns = labels
            
            st.dataframe(
                df_display,
                column_config={
                    "Sumber Data": st.column_config.TextColumn("Platform"),
                    "Link Listing": st.column_config.LinkColumn("Buka URL", display_text="🔗 Lihat Iklan Asli"),
                    "Harga Pasar": st.column_config.NumberColumn(format="Rp %d"),
                    "Tahun": st.column_config.NumberColumn(format="%d"),
                    "Kilometer": st.column_config.TextColumn(),
                },
                hide_index=True,
                use_container_width=True
            )

        with tab_cards:
            for idx, item in enumerate(filtered_data, 1):
                with st.container(border=True):
                    c1, c2 = st.columns([3, 1])
                    with c1:
                        st.markdown(f"#### {idx}. {item['title']} `[{item['source']}]`")
                        mileage_min, mileage_max = listing_mileage_bounds(item)
                        detail = (
                            f"Tahun: {item['year'] if item['year'] else 'Tidak tercantum'}"
                            f" | Kilometer: {fmt_km(mileage_min, mileage_max)}"
                            if mileage_min is not None
                            else f"Tahun: {item['year'] if item['year'] else 'Tidak tercantum'}"
                            " | Kilometer: Tidak tercantum"
                        )
                        detail += (
                            f" | Wilayah: {item.get('location') or 'Tidak diketahui'}"
                            f" | Dicatat: {item.get('collected_at', 'Tidak diketahui')}"
                        )
                        st.caption(detail)
                    with c2:
                        st.subheader(fmt_rp(item['price']))
                        st.link_button(f"🔗 Buka di {item['source']}", item["url"])

    else:
        if filter_mileage:
            st.warning(
                "Tidak ada listing dengan data kilometer dalam rentang "
                f"{fmt_km(min_mileage_km, max_mileage_km)} yang cocok. "
                "Matikan filter kilometer untuk melihat listing yang "
                "kilometernya belum tercantum."
            )
        elif info.get("location", "").casefold() not in (
            "",
            "semua wilayah",
            "seluruh indonesia",
        ):
            if raw_data and not any(item.get("location") for item in raw_data):
                st.warning(
                    "Listing ditemukan, tetapi scraper belum memperoleh "
                    f"wilayah terverifikasi untuk {info['model']}. "
                    "Listing tanpa wilayah tidak digunakan untuk valuasi kota."
                )
            else:
                st.warning(
                    f"Tidak ada listing dengan lokasi terverifikasi yang cocok "
                    f"untuk {info['model']} di {info['location']} pada tahun "
                    f"{year_display}."
                )
        elif raw_data:
            st.warning(
                f"Ada listing hasil pencarian, tetapi tidak ada yang cocok "
                f"dengan tahun {year_display}"
                + (" dan tipe yang dipilih." if filter_tipe else ".")
            )
        else:
            st.warning(
                "Cache dan sumber scraper tidak menghasilkan listing yang "
                "bisa digunakan untuk pencarian ini."
            )
else:
    st.info(
        "Form pencarian sudah siap di atas. Pilih merek, model, dan wilayah, "
        "lalu tekan **Cari Data Pasar**. Filter tahun, varian, dan kilometer "
        "akan tersedia setelah listing ditemukan."
    )

st.markdown("---")
with st.container(border=True):
    license_cols = st.columns([3, 1, 1])
    with license_cols[0]:
        st.markdown("#### 🔐 Lisensi ValuasiOto")
        st.caption(
            f"Akses premium aktif atas nama {st.session_state.user_pemilik}. "
            "Terima kasih telah menggunakan ValuasiOto."
        )
    with license_cols[1]:
        st.success("Aktif", icon="✅")
    with license_cols[2]:
        st.link_button(
            "Keluar",
            "/license/logout",
            use_container_width=True,
        )

# Watermark Footer Branding
st.caption(f"© 2026 **{NAMA_PRODUK}** — Automated Used Car Valuation Engine for Professional Traders.")