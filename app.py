import streamlit as st
import cdsapi
import math
import os

# =========================
# ERA5 grid snapping logic
# (3-decimal resolution)
# =========================
def get_ecmwf_area(lat, lon, grid_size=0.001):
    lat_floor = math.floor(lat * 1000) / 1000
    lat_south = lat_floor
    lat_north = lat_floor + grid_size

    lon_floor = math.floor(lon * 1000) / 1000
    lon_west = lon_floor
    lon_east = lon_floor + grid_size

    return [
        round(lat_north, 3),  # North
        round(lon_west, 3),   # West
        round(lat_south, 3),  # South
        round(lon_east, 3),   # East
    ]

# =========================
# Streamlit UI
# =========================
st.set_page_config(layout="centered")
st.title("ERA5 Point Downloader (Yearly – Manual Submit)")

st.info(
    "Identical to Colab behavior:\n"
    "- ONE year per request\n"
    "- ERA5 native grid point\n"
    "- Manual submit\n"
    "- 3-decimal snapped area"
)

# =========================
# Inputs
# =========================
st.subheader("🔑 CDS API")
cds_url = st.text_input(
    "CDS API URL",
    "https://cds.climate.copernicus.eu/api",
)
cds_key = st.text_input("CDS API Key", type="password")

st.subheader("📍 Location")
lat = st.number_input("Latitude", value=-8.405187, format="%.6f")
lon = st.number_input("Longitude", value=119.660916, format="%.6f")

st.subheader("📅 Year")
year = st.number_input("Year to download", value=2013, step=1)

# =========================
# Variables (UNCHANGED)
# =========================
VARIABLES = [
    "10m_u_component_of_wind",
    "10m_v_component_of_wind",
    "mean_wave_direction",
    "mean_wave_period",
    "significant_height_of_combined_wind_waves_and_swell",
]

st.subheader("🧪 Variables")
selected_vars = []
for v in VARIABLES:
    if st.checkbox(v, value=True):
        selected_vars.append(v)

# =========================
# Output folder
# =========================
OUTPUT_DIR = "era5_output"
os.makedirs(OUTPUT_DIR, exist_ok=True)

# =========================
# Submit logic
# =========================
def submit_year(c, area, year, variables):
    request = {
        "product_type": "reanalysis",
        "variable": variables,
        "year": str(year),
        "month": [f"{m:02d}" for m in range(1, 13)],
        "day": [f"{d:02d}" for d in range(1, 32)],
        "time": [f"{h:02d}:00" for h in range(24)],
        "area": area,   # N, W, S, E
        "format": "netcdf4",
    }

    outfile = f"{OUTPUT_DIR}/era5_{year}.nc"

    c.retrieve(
        "reanalysis-era5-single-levels",
        request,
        outfile,
    )

# =========================
# Submit button
# =========================
if st.button("🚀 Submit THIS YEAR"):
    if not cds_key.strip():
        st.error("CDS API key is required")
        st.stop()

    if not selected_vars:
        st.error("Select at least one variable")
        st.stop()

    area = get_ecmwf_area(lat, lon)
    st.write("ERA5 snapped area [N, W, S, E]:", area)

    c = cdsapi.Client(
        url=cds_url,
        key=cds_key,
        quiet=False,
    )

    st.warning(f"Submitting ERA5 request for year {year}")
    st.warning("Do NOT click again until finished")

    try:
        submit_year(c, area, year, selected_vars)
    except Exception as e:
        st.error(f"Submission failed: {e}")
        st.stop()

    st.success(f"ERA5 {year} download completed")
