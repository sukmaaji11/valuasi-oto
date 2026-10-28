import streamlit as st
import cloudscraper
from bs4 import BeautifulSoup
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
from datetime import datetime
from reportlab.lib.pagesizes import A4
from reportlab.lib import colors
from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle, HRFlowable
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
import hashlib

# ==================== KODE RAHASIA DEVELOPER ====================
SECRET_SALT = "VALUASIOTO_149K_SEKALI_BELI_2026"
NOMOR_WA_PENJUAL = "6281234567890"  # Ganti dengan nomor WhatsApp kamu (format 62)

def verify_license_key(input_key, nama_pemilik):
    if not input_key or not nama_pemilik:
        return False
    clean_name = nama_pemilik.strip().upper()
    raw_str = f"{clean_name}_{SECRET_SALT}"
    hashed_str = hashlib.sha256(raw_str.encode()).hexdigest().upper()[:8]
    expected_key = f"VALUASI-{clean_name.replace(' ', '')[:6]}-{hashed_str}"
    return input_key.strip().upper() == expected_key

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
is_unlocked = verify_license_key(st.session_state.user_key, st.session_state.user_pemilik)

# ==================== HALAMAN AKTIVASI MOBILE-FIRST (LAYAR UTAMA) ====================
if not is_unlocked:
    st.markdown("""
        <div style="text-align: center; padding: 10px 0 20px 0;">
            <div style="background: linear-gradient(135deg, #FF6B00, #FF8E53); width: 64px; height: 64px; border-radius: 18px; display: inline-flex; align-items: center; justify-content: center; font-size: 32px; color: white; margin-bottom: 12px; box-shadow: 0 6px 18px rgba(255, 107, 0, 0.35);">
                ⚡
            </div>
            <h1 style="font-size: 1.8rem; font-weight: 800; color: #0F172A; margin: 0; letter-spacing: -0.5px;">ValuasiOto.id</h1>
            <p style="font-size: 0.9rem; color: #64748B; margin-top: 4px;">B2B Market Intelligence & Walk-Away Price Engine</p>
        </div>
    """, unsafe_allow_html=True)

    col_box1, col_box2, col_box3 = st.columns([1, 2, 1])
    with col_box2:
        with st.container(border=True):
            st.markdown("<h3 style='margin-top:0; text-align:center;'>🔑 Aktivasi Aplikasi</h3>", unsafe_allow_html=True)
            st.caption("Masukkan Nama & Kode Lisensi yang kamu terima setelah pembelian Rp 149.000.")
            
            input_nama = st.text_input("Nama Terdaftar / Showroom", value=st.session_state.user_pemilik, placeholder="contoh: Budi Trader").strip()
            input_key = st.text_input("Kode Lisensi (License Key)", value=st.session_state.user_key, type="password", placeholder="VALUASI-XXXXXX-XXXXXXXX").strip()
            
            if st.button("🔓 Aktivasi & Buka Aplikasi", type="primary", use_container_width=True):
                if verify_license_key(input_key, input_nama):
                    st.session_state.user_pemilik = input_nama
                    st.session_state.user_key = input_key
                    st.query_params["name"] = input_nama
                    st.query_params["key"] = input_key
                    st.success("✅ Aktivasi Berhasil! Membuka aplikasi...")
                    st.rerun()
                else:
                    st.error("❌ Nama atau Kode Lisensi tidak cocok/salah!")

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

# ==================== SETELAH TER-UNLOCK ====================
# Tampilkan status lisensi aktif di sidebar secara elegan
st.sidebar.markdown(f"""
    <div style="background-color: #ECFDF5; border: 1px solid #A7F3D0; border-radius: 8px; padding: 10px; margin-bottom: 15px;">
        <span style="color: #065F46; font-size: 0.8rem; font-weight: 700;">🔓 LISENSI SEKALIKAN BELI AKTIF</span><br/>
        <span style="color: #047857; font-size: 0.85rem;">Pemilik: <b>{st.session_state.user_pemilik}</b></span>
    </div>
""", unsafe_allow_html=True)

# ==================== KONFIGURASI HALAMAN & BRANDING ====================
NAMA_PRODUK = "ValuasiOto.id"
TAGLINE = "B2B Market Intelligence & Walk-Away Price Engine"

st.set_page_config(
    page_title=f"{NAMA_PRODUK} — Valuasi & Margin Mobil Bekas", 
    page_icon="⚡", 
    layout="wide"
)

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
    variabel_tipe = filter_tipe if filter_tipe else "Semua Varian/Tipe"
    
    unit_info = (
        f"<b>Merek & Model:</b> {info_search.get('merek')} {info_search.get('model')}<br/>"
        f"<b>Tahun Pembuatan:</b> {min_yr} – {max_yr}<br/>"
        f"<b>Varian / Spesifikasi:</b> {variabel_tipe}<br/>"
        f"<b>Sampel Analisis:</b> {total_sampel} Unit Valid<br/>"
        f"<b>Sumber Data:</b> 6 Platform Real-Time"
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
    disclaimer_text = "<i>Dokumen ini dihasilkan secara otomatis oleh ValuasiOto.id Engine berdasarkan analisis data komparatif dari 6 platform marketplace otomotif utama di Indonesia. Penawaran bersifat mengikat sesuai kondisi pembenahan yang tertera.</i>"
    story.append(Paragraph(disclaimer_text, ParagraphStyle('Disc', parent=style_body, fontSize=7.5, textColor=colors.HexColor('#94A3B8'))))

    doc.build(story)
    buffer.seek(0)
    return buffer

# ==================== HEADER UTAMA ====================
st.markdown(f"""
    <div style="display: flex; align-items: center; gap: 12px; margin-bottom: 15px;">
        <div style="background: linear-gradient(135deg, #FF6B00, #FF8E53); width: 42px; height: 42px; border-radius: 10px; display: flex; align-items: center; justify-content: center; font-size: 22px; color: white; box-shadow: 0 4px 10px rgba(255, 107, 0, 0.25);">
            ⚡
        </div>
        <div>
            <div style="display: flex; align-items: center; gap: 8px;">
                <h2 style="margin: 0; padding: 0; font-size: 1.6rem; font-weight: 800; letter-spacing: -0.5px; color: #0F172A;">{NAMA_PRODUK}</h2>
                <span style="background-color: #EFF6FF; color: #1D4ED8; font-size: 0.72rem; font-weight: 700; padding: 2px 8px; border-radius: 6px; border: 1px solid #BFDBFE;">B2B ENTERPRISE</span>
            </div>
            <p style="margin: 2px 0 0 0; padding: 0; font-size: 0.85rem; color: #64748B;">
                <b>{TAGLINE}</b> &bull; Real-Time Aggregator 6 Platform (OLX, Mobil123, Carmudi, Oto.com, Carsome, Carro)
            </p>
        </div>
    </div>
""", unsafe_allow_html=True)

st.divider()

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

# ==================== SIDEBAR BRANDING & FILTER ====================
st.sidebar.markdown(
    f"""
    <div style="display: flex; align-items: center; gap: 10px; margin-bottom: 12px; padding-bottom: 10px; border-bottom: 1px solid #E2E8F0;">
        <div style="background: linear-gradient(135deg, #FF6B00, #FF8E53); width: 34px; height: 34px; border-radius: 8px; display: flex; align-items: center; justify-content: center; font-size: 18px; color: white; box-shadow: 0 2px 6px rgba(255, 107, 0, 0.25);">
            ⚡
        </div>
        <div>
            <h3 style="margin: 0; padding: 0; font-size: 1.1rem; font-weight: 800; color: #0F172A; letter-spacing: -0.3px;">{NAMA_PRODUK}</h3>
            <p style="margin: 0; padding: 0; font-size: 0.72rem; color: #64748B; font-weight: 600; text-transform: uppercase; letter-spacing: 0.5px;">Panel Kontrol Trader</p>
        </div>
    </div>
    """, 
    unsafe_allow_html=True
)

st.sidebar.markdown("<div style='font-size: 0.82rem; font-weight: 700; color: #475569; text-transform: uppercase; letter-spacing: 0.5px; margin-top: 8px; margin-bottom: 6px;'>🔍 Pencarian Utama Mobil</div>", unsafe_allow_html=True)

merek_list = ["Toyota", "Honda", "Daihatsu", "Mitsubishi", "Suzuki", "Nissan", "Hyundai", "Wuling", "Lainnya"]
merek = st.sidebar.selectbox("Merek Mobil", merek_list, index=0)
model_input = st.sidebar.text_input(
    "Model / Kata Kunci Mobil", 
    "Kijang Innova", 
    help="Isi nama model (misal: Brio, Jazz, Kijang Innova, Avanza, HRV)"
).strip()

st.sidebar.markdown("<div style='margin-top: 10px;'></div>", unsafe_allow_html=True)

st.sidebar.markdown("<hr style='margin: 15px 0; border: none; border-top: 1px solid #E2E8F0;' />", unsafe_allow_html=True)

st.sidebar.markdown("<div style='font-size: 0.82rem; font-weight: 700; color: #475569; text-transform: uppercase; letter-spacing: 0.5px; margin-bottom: 6px;'>🎯 Filter Varian & Rentang Tahun</div>", unsafe_allow_html=True)

tahun_range = st.sidebar.slider(
    "Rentang Tahun Pembuatan",
    min_value=2005,
    max_value=2026,
    value=(2016, 2023)
)

filter_tipe = st.sidebar.text_input(
    "Tipe / Spesifikasi Khusus", 
    "", 
    placeholder="misal: Reborn, Venturer, G, V, Satya, RS"
).strip()

st.sidebar.markdown("<hr style='margin: 15px 0; border: none; border-top: 1px solid #E2E8F0;' />", unsafe_allow_html=True)

st.sidebar.markdown(
    """
    <div style="background-color: #F8FAFC; border: 1px solid #E2E8F0; border-left: 3px solid #FF6B00; border-radius: 6px; padding: 10px 12px; font-size: 0.78rem; color: #334155;">
        <strong style="color: #0F172A;">💡 Tips Trader:</strong><br/>
        Tetapkan Target Margin min. 8–10% dari harga median pasar untuk mengamankan biaya operasional tak terduga.
    </div>
    """,
    unsafe_allow_html=True
)

# ==================== HELPER FUNCTION PARSING & FILTERING ====================
def clean_price_int(price_str):
    if not price_str:
        return 0
    clean = re.sub(r'[^\d]', '', str(price_str))
    return int(clean) if clean else 0

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
    temp_json_file = f"olx_temp_{merek_car}_{model_car}.json".replace(" ", "_").lower()
    
    # Hapus file temporary lama jika ada
    if os.path.exists(temp_json_file):
        try:
            os.remove(temp_json_file)
        except Exception:
            pass

    try:
        # Panggil test_olx.py via Subprocess
        process = subprocess.run(
            [sys.executable, "test_olx.py", merek_car, model_car, temp_json_file],
            capture_output=True,
            text=True,
            timeout=40
        )
        
        # Baca hasil dari file temporary JSON
        if os.path.exists(temp_json_file):
            with open(temp_json_file, "r", encoding="utf-8") as f:
                data = json.load(f)
            
            # Hapus file temp setelah dibaca
            try:
                os.remove(temp_json_file)
            except Exception:
                pass
                
            return data
        else:
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
                                
                            data_list.append({
                                "source": site_name,
                                "title": title_text,
                                "price": price_val,
                                "year": extract_year_from_text(title_text),
                                "url": url_link if url_link else domain_url
                            })
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
# ==================== PARALLEL EXECUTION ENGINE (WITH AUTOMATIC CACHE) ====================
# Cache otomatis berlaku 30 menit & otomatis menyesuaikan saat kata kunci merek/model berubah
@st.cache_data(ttl=1800, show_spinner=False)
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


# ==================== SIDEBAR CONTROL (CLEAN & SIMPLE) ====================
st.sidebar.markdown("<div style='margin-top: 10px;'></div>", unsafe_allow_html=True)

# Cukup 1 Tombol Utama Tanpa Perlu Tombol Clear Cache
btn_cari = st.sidebar.button("🔍 Cari Data Pasar (6 Platform)", type="primary", use_container_width=True)

if btn_cari:
    with st.spinner(f"⚡ Menyiapkan Intelijen Data Pasar '{merek} {model_input}'..."):
        raw_data, counts = fetch_all_sources_parallel(merek, model_input)

    st.session_state.data_searched = True
    st.session_state.raw_data = raw_data
    st.session_state.search_info = {
        "merek": merek,
        "model": model_input if model_input else "Semua Model",
        "counts": counts
    }

# ==================== PARALLEL EXECUTION ENGINE (6 PLATFORM) ====================
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

# ==================== PROSES PENCARIAN ====================
if btn_cari:
    with st.spinner(f"Memindai data 6 platform real-time via {NAMA_PRODUK}..."):
        raw_data, counts = fetch_all_sources_parallel(merek, model_input)

    st.session_state.data_searched = True
    st.session_state.raw_data = raw_data
    st.session_state.search_info = {
        "merek": merek,
        "model": model_input if model_input else "Semua Model",
        "counts": counts
    }

# ==================== FILTERING DINAMIS & DASHBOARD ====================
if st.session_state.data_searched:
    raw_data = st.session_state.raw_data
    
    filtered_data = []
    min_yr, max_yr = tahun_range
    for item in raw_data:
        if item["year"]:
            if not (min_yr <= item["year"] <= max_yr):
                continue
                
        if filter_tipe:
            if filter_tipe.lower() not in item["title"].lower():
                continue
                
        filtered_data.append(item)

    prices = [item["price"] for item in filtered_data]
    info = st.session_state.search_info
    counts = info.get("counts", {})

    if prices:
        st.info(
            f"🌐 **Intelijen Data Pasar (`{info['merek']} {info['model']}`):** "
            f"**OLX ({counts.get('OLX',0)})** | Mobil123 ({counts.get('Mobil123',0)}) | Carmudi ({counts.get('Carmudi',0)}) | "
            f"Oto.com ({counts.get('Oto.com',0)}) | Carsome ({counts.get('Carsome',0)}) | Carro ({counts.get('Carro',0)}) | "
            f"**Hasil Valid setelah Filter Rentang ({min_yr}–{max_yr}): {len(filtered_data)} unit**"
        )
        
        harga_median = int(np.median(prices))
        harga_min = min(prices)
        harga_max = max(prices)
        
        col1, col2, col3 = st.columns(3)
        col1.metric("Harga Pasaran Reliable (Median)", fmt_rp(harga_median))
        col2.metric("Harga Terendah Pasar", fmt_rp(harga_min))
        col3.metric("Harga Tertinggi Pasar", fmt_rp(harga_max))
        
        st.divider()
        
        st.subheader("🛠️ Kalkulator Valuasi & Estimasi Perbaikan (PR)")
        
        col_input1, col_input2 = st.columns(2)
        with col_input1:
            biaya_pajak = st.number_input("Estimasi Tunggakan Pajak (Rp)", value=0, step=500000)
            st.caption(f"💰 Nominal: **{fmt_rp(biaya_pajak)}**")
            
            biaya_cat = st.number_input("Estimasi Perbaikan Bodi/Cat (Rp)", value=1500000, step=500000)
            st.caption(f"💰 Nominal: **{fmt_rp(biaya_cat)}**")
            
            biaya_mesin = st.number_input("Estimasi Perbaikan Mesin/Kaki-kaki (Rp)", value=1000000, step=500000)
            st.caption(f"💰 Nominal: **{fmt_rp(biaya_mesin)}**")
            
        with col_input2:
            biaya_salon = st.number_input("Biaya Detailing/Salon (Rp)", value=500000, step=100000)
            st.caption(f"💰 Nominal: **{fmt_rp(biaya_salon)}**")
            
            target_margin = st.number_input("Target Untung / Margin Kamu (Rp)", value=10000000, step=1000000)
            st.caption(f"💰 Nominal: **{fmt_rp(target_margin)}**")

        total_pr = biaya_pajak + biaya_cat + biaya_mesin + biaya_salon
        harga_beli_maksimal = harga_median - total_pr - target_margin
        total_modal_investasi = harga_beli_maksimal + total_pr
        persen_diskon = ((harga_median - harga_beli_maksimal) / harga_median) * 100
        
        st.markdown("---")
        
        st.success(f"### 💡 **Rekomendasi Beli Maksimal (Walk-Away Price):** {fmt_rp(harga_beli_maksimal)}")
        
        with st.expander("📊 **Rincian Detail Analisis Anggaran & Margin Trader**", expanded=True):
            r1, r2, r3, r4 = st.columns(4)
            r1.metric("1. Target Jual Pasar", fmt_rp(harga_median))
            r2.metric("2. Total Pembenahan (PR)", fmt_rp(total_pr))
            r3.metric("3. Total Modal Dikeluarkan", fmt_rp(total_modal_investasi))
            r4.metric("4. Target Margin Net", fmt_rp(target_margin), delta=f"{persen_diskon:.1f}% di bawah pasar")
            
            st.markdown(
                f"""
                **Panduan Eksekusi Trader:**
                * **Batas Tawaran Teratas:** Jangan beli unit ini di atas **{fmt_rp(harga_beli_maksimal)}**.
                * **Rincian PR:** Pajak ({fmt_rp(biaya_pajak)}) + Cat ({fmt_rp(biaya_cat)}) + Mesin ({fmt_rp(biaya_mesin)}) + Salon ({fmt_rp(biaya_salon)}) = **{fmt_rp(total_pr)}**.
                * **Target Diskon Pembelian:** Minimal **{persen_diskon:.1f}% di bawah harga pasar median** untuk mengamankan margin **{fmt_rp(target_margin)}**.
                """
            )
        # Tambahkan kode ini tepat di bawah expander "📊 Rincian Detail Analisis Anggaran & Margin Trader" di app.py:
        st.markdown("### 📄 Export Lembar Penawaran (PDF Deal Sheet)")

        col_pdf1, col_pdf2 = st.columns([2, 1])
        with col_pdf1:
            nama_showroom_input = st.text_input("Nama Showroom / Trader (Untuk Header PDF)", "Auto Jaya Motor")

        with col_pdf2:
            st.markdown("<div style='margin-top: 28px;'></div>", unsafe_allow_html=True)
            
            # Generate PDF Buffer dengan Parameter Query Lengkap
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
                total_modal=total_modal_investasi
            )
            
            safe_merek = str(st.session_state.search_info.get('merek', 'Mobil')).replace(" ", "_")
            safe_model = str(st.session_state.search_info.get('model', 'Model')).replace(" ", "_")
            file_pdf_name = f"Valuasi_{safe_merek}_{safe_model}_{datetime.now().strftime('%Y%m%d')}.pdf"

            st.download_button(
                label="📥 Download PDF Penawaran",
                data=pdf_bytes,
                file_name=file_pdf_name,
                mime="application/pdf",
                type="primary",
                use_container_width=True
            )
        st.divider()
        
        st.subheader(f"📊 Sampel Data Pasar Real-Time ({len(filtered_data)} Unit Ditemukan)")
        
        tab_table, tab_cards = st.tabs(["📋 Tabel Interaktif dengan Link Listing", "🎴 Tampilan Kartu (Cards)"])
        
        with tab_table:
            df = pd.DataFrame(filtered_data)
            df["No"] = range(1, len(df) + 1)
            
            df_display = df[["No", "source", "title", "year", "price", "url"]].copy()
            df_display.columns = ["No", "Sumber Data", "Nama / Varian Mobil", "Tahun", "Harga Pasar", "Link Listing"]
            
            st.dataframe(
                df_display,
                column_config={
                    "Sumber Data": st.column_config.TextColumn("Platform"),
                    "Link Listing": st.column_config.LinkColumn("Buka URL", display_text="🔗 Lihat Iklan Asli"),
                    "Harga Pasar": st.column_config.NumberColumn(format="Rp %d"),
                    "Tahun": st.column_config.NumberColumn(format="%d"),
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
                        st.caption(f"Tahun Pembuatan: **{item['year'] if item['year'] else 'Tidak Tercantum'}** | Sumber: **{item['source']}**")
                    with c2:
                        st.subheader(fmt_rp(item['price']))
                        st.link_button(f"🔗 Buka di {item['source']}", item["url"])

    else:
        st.warning(f"⚠️ Tidak ada unit yang cocok dengan filter spesifik '{filter_tipe}' pada rentang tahun {min_yr}–{max_yr}.")
else:
    st.info(f"👈 Masukkan Merek & Model di Sidebar, lalu klik **'🔍 Cari Data Pasar (6 Platform)'** untuk memulai penarikan data.")

# Watermark Footer Branding
st.markdown("---")
st.caption(f"© 2026 **{NAMA_PRODUK}** — Automated Used Car Valuation Engine for Professional Traders.")