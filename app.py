import streamlit as st
import cdsapi
import math
import threading
import time
import io
import pandas as pd

# ─────────────────────────────────────────────
# PAGE CONFIG
# ─────────────────────────────────────────────
st.set_page_config(layout="centered", page_title="ERA5 Toolkit", page_icon="🌊")

st.markdown("""
<style>
    .module-header {
        background: linear-gradient(90deg, #0f3460 0%, #16213e 100%);
        color: white;
        padding: 0.6rem 1.2rem;
        border-radius: 8px;
        margin-bottom: 1rem;
        font-size: 1.1rem;
        font-weight: 600;
        letter-spacing: 0.5px;
    }
    .stTabs [data-baseweb="tab-list"] {
        gap: 8px;
    }
    .stTabs [data-baseweb="tab"] {
        background-color: #f0f4f8;
        border-radius: 6px 6px 0 0;
        padding: 8px 20px;
        font-weight: 600;
        color: #000000 !important;
    }
    .stTabs [data-baseweb="tab"] p {
        color: #000000 !important;
    }
</style>
""", unsafe_allow_html=True)

st.title("🌊 ERA5 Toolkit")
st.caption("Module 1: Submit CDS requests · Module 2: Extract .nc → .csv")

tab1, tab2 = st.tabs(["📡 Module 1 — CDS Downloader", "📂 Module 2 — NC Extractor"])


# ═══════════════════════════════════════════════════════════════
# MODULE 1 — ERA5 Fire-and-Forget Downloader (original, intact)
# ═══════════════════════════════════════════════════════════════
with tab1:
    st.markdown('<div class="module-header">📡 Module 1 — ERA5 Point Downloader (Yearly, Fire-and-Forget)</div>', unsafe_allow_html=True)
    st.info(
        "Colab-equivalent behavior:\n"
        "- ONE year per request\n"
        "- netcdf4 format\n"
        "- ERA5 native grid point\n"
        "- Submit → break → click next year"
    )

    # ── ERA5 grid snapping ──
    def get_ecmwf_area(lat, lon, grid_size=0.05):
        lat_floor = math.floor(lat * 1000) / 1000
        lon_floor = math.floor(lon * 1000) / 1000
        return [
            round(lat_floor + grid_size, 3),
            round(lon_floor, 3),
            round(lat_floor, 3),
            round(lon_floor + grid_size, 3),
        ]

    # ── Session state ──
    for key, default in [
        ("current_year", None),
        ("locked", False),
        ("prev_start_year", None),
    ]:
        if key not in st.session_state:
            st.session_state[key] = default

    # ── Inputs ──
    st.subheader("🔑 CDS API")
    cds_url = st.text_input("CDS API URL", "https://cds.climate.copernicus.eu/api", key="m1_url")
    cds_key = st.text_input("CDS API Key", type="password", key="m1_key")

    st.subheader("📍 Location")
    lat = st.number_input("Latitude", value=-8.405187, format="%.6f", key="m1_lat")
    lon = st.number_input("Longitude", value=119.660916, format="%.6f", key="m1_lon")

    st.subheader("📅 Year range")
    start_year = st.number_input("Start year", value=2013, step=1, key="m1_sy")
    end_year   = st.number_input("End year",   value=2022, step=1, key="m1_ey")

    if st.session_state.prev_start_year != start_year:
        st.session_state.current_year    = start_year
        st.session_state.prev_start_year = start_year

    VARIABLES = [
        "10m_u_component_of_wind",
        "10m_v_component_of_wind",
        "mean_wave_direction",
        "mean_wave_period",
        "significant_height_of_combined_wind_waves_and_swell",
    ]

    st.subheader("🧪 Variables")
    selected_vars = [v for v in VARIABLES if st.checkbox(v, value=True, key=f"var_{v}")]

    all_done = (st.session_state.current_year or start_year) > end_year - 1

    def submit_year_blocking(area, year, variables, url, key):
        c = cdsapi.Client(url=url, key=key, quiet=False)
        request = {
            "product_type": "reanalysis",
            "variable": variables,
            "year": str(year),
            "month": [f"{m:02d}" for m in range(1, 13)],
            "day":   [f"{d:02d}" for d in range(1, 32)],
            "time":  [f"{h:02d}:00" for h in range(24)],
            "area":  area,
            "format": "netcdf4",
        }
        c.retrieve("reanalysis-era5-single-levels", request, "era5_request_placeholder.nc")

    if st.button("🚀 Submit CURRENT YEAR", disabled=st.session_state.locked or all_done, key="m1_submit"):
        if not cds_key.strip():
            st.error("CDS API key is required")
            st.stop()
        if not selected_vars:
            st.error("Select at least one variable")
            st.stop()

        year = st.session_state.current_year
        area = get_ecmwf_area(lat, lon)

        st.write("ERA5 snapped area [N, W, S, E]:", area)
        st.warning(f"Submitting ERA5 request for year {year}")
        st.session_state.locked = True

        threading.Thread(
            target=submit_year_blocking,
            args=(area, year, selected_vars, cds_url, cds_key),
            daemon=True,
        ).start()

        time.sleep(6)
        st.success(f"✅ Request for {year} submitted to CDS")
        st.session_state.current_year += 1
        st.session_state.locked = False

    st.markdown("---")
    if all_done:
        st.success("🎉 All requested years have been submitted.")
        st.write("✅ Last submitted year:", end_year)
    else:
        st.write("🟢 Next year to submit:", st.session_state.current_year)


# ═══════════════════════════════════════════════════════════════
# MODULE 2 — NetCDF4 (.nc) → CSV Extractor
# ═══════════════════════════════════════════════════════════════
with tab2:
    st.markdown('<div class="module-header">📂 Module 2 — NetCDF4 → CSV Extractor</div>', unsafe_allow_html=True)
    st.info(
        "Upload one or more ERA5 `.nc` files downloaded from the CDS website. "
        "This module extracts all variables into a flat CSV — the same result you'd get from Ocean Data View, but right here in Python."
    )

    # ── Lazy import xarray (not always installed alongside streamlit) ──
    try:
        import xarray as xr
        import numpy as np
        XARRAY_OK = True
    except ImportError:
        XARRAY_OK = False
        st.error(
            "⚠️ `xarray` and/or `numpy` are not installed. "
            "Run `pip install xarray netcdf4 numpy` in your environment."
        )

    if XARRAY_OK:
        st.subheader("📍 Target coordinate")
        target_lat = st.number_input("Latitude (for nearest grid point)", value=0.0, format="%.6f", key="m2_lat")
        target_lon = st.number_input("Longitude (for nearest grid point)", value=0.0, format="%.6f", key="m2_lon")
        uploaded_files = st.file_uploader(
            "Upload ERA5 .nc file(s)",
            type=["nc"],
            accept_multiple_files=True,
            key="m2_upload",
        )

        if uploaded_files:
            all_dfs = []

            for uf in uploaded_files:
                st.markdown(f"**📄 Processing:** `{uf.name}`")

                # Read bytes → xarray via in-memory buffer
                nc_bytes = uf.read()
                try:
                    # xarray needs a file path or scipy engine for in-memory bytes
                    ds = xr.open_dataset(io.BytesIO(nc_bytes), engine="scipy")
                except Exception:
                    try:
                        # fallback: write temp file
                        import tempfile, os
                        # Windows fix: use mkstemp so we control the fd,
                        # then close it before xarray opens the file,
                        # then use load_dataset (loads into memory) so no
                        # file lock is held when we delete.
                        tmp_fd, tmp_path = tempfile.mkstemp(suffix=".nc")
                        try:
                            with os.fdopen(tmp_fd, "wb") as tmp_f:
                                tmp_f.write(nc_bytes)
                            ds = xr.load_dataset(tmp_path, engine="netcdf4")
                        finally:
                            try:
                                os.unlink(tmp_path)
                            except OSError:
                                pass  # non-critical; temp folder will clean up
                    except Exception as e:
                        st.error(f"Could not open `{uf.name}`: {e}")
                        continue

                # ── Show dataset info ──
                with st.expander(f"📋 Dataset info — {uf.name}", expanded=False):
                    st.write("**Dimensions:**", dict(ds.dims))
                    st.write("**Variables:**", list(ds.data_vars))
                    st.write("**Coordinates:**", list(ds.coords))
                    if hasattr(ds, "attrs") and ds.attrs:
                        st.write("**Global attributes:**", ds.attrs)

                # ── Convert to DataFrame ──
                try:
                    df = ds.to_dataframe().reset_index()
                except Exception as e:
                    st.error(f"Conversion failed for `{uf.name}`: {e}")
                    ds.close()
                    continue

                # ── Drop all-NaN rows (ERA5 often has fill values) ──
                data_cols = [c for c in df.columns if c not in ("latitude", "longitude", "time", "valid_time", "expver")]
                df_clean = df.dropna(subset=data_cols, how="all").copy()

                if "latitude" in df_clean.columns and "longitude" in df_clean.columns:
                    lats = np.array(pd.unique(df_clean["latitude"].values), dtype=float)
                    lons = np.array(pd.unique(df_clean["longitude"].values), dtype=float)
                    if lats.size > 0 and lons.size > 0:
                        nearest_lat = float(lats[np.abs(lats - target_lat).argmin()])
                        nearest_lon = float(lons[np.abs(lons - target_lon).argmin()])
                        df_clean = df_clean[(df_clean["latitude"] == nearest_lat) & (df_clean["longitude"] == nearest_lon)].copy()
                        st.write(f"Nearest grid point used → latitude: {nearest_lat:.6f}, longitude: {nearest_lon:.6f}")

                for col in ["latitude", "longitude"]:
                    if col in df_clean.columns:
                        df_clean[col] = df_clean[col].round(6)

                # ── Tag with source filename ──
                df_clean.insert(0, "source_file", uf.name)

                all_dfs.append(df_clean)
                ds.close()

                # ── Preview ──
                st.write(f"✅ Rows extracted: **{len(df_clean):,}** | Columns: **{list(df_clean.columns)}**")
                st.dataframe(df_clean.head(20), use_container_width=True)

            # ── Merge & Download ──
            if all_dfs:
                st.markdown("---")
                combined = pd.concat(all_dfs, ignore_index=True)

                st.success(f"🎉 Total rows across all files: **{len(combined):,}**")

                # ── Optional column filter ──
                all_cols = list(combined.columns)
                st.subheader("🔧 Column selector (optional)")
                keep_cols = st.multiselect(
                    "Select columns to include in the download (default = all)",
                    options=all_cols,
                    default=all_cols,
                    key="m2_cols",
                )
                export_df = combined[keep_cols] if keep_cols else combined

                # ── Download ──
                csv_buffer = io.StringIO()
                export_df.to_csv(csv_buffer, index=False)
                csv_bytes = csv_buffer.getvalue().encode("utf-8")

                # Suggest filename
                if len(uploaded_files) == 1:
                    suggested_name = uploaded_files[0].name.replace(".nc", ".csv")
                else:
                    suggested_name = "era5_combined.csv"

                st.download_button(
                    label=f"⬇️ Download CSV ({len(export_df):,} rows)",
                    data=csv_bytes,
                    file_name=suggested_name,
                    mime="text/csv",
                    key="m2_download",
                )

                # ── Quick stats ──
                with st.expander("📊 Quick statistics", expanded=False):
                    st.dataframe(export_df.describe(), use_container_width=True)

        else:
            st.markdown("""
            ### How it works
            1. **Upload** one or more `.nc` files from the CDS download page (or from Module 1's output).
            2. The app reads every variable and coordinate (time, lat, lon) and flattens them into rows.
            3. NaN-only rows (ERA5 fill values) are dropped automatically.
            4. **Download** the result as a clean `.csv` — no Ocean Data View needed!

            > 💡 **Tip:** If you downloaded one file per year from Module 1, upload them all at once — they'll be merged into a single CSV automatically.
            """)

    # ── Requirements reminder ──
    st.markdown("---")
    st.caption("Requirements for Module 2: `pip install xarray netcdf4 scipy numpy pandas`")
