import streamlit as st
import cdsapi
import math
import threading
import time

# =========================
# ERA5 grid snapping logic
# =========================
def get_ecmwf_area(lat, lon, grid_size=0.001):
    lat_floor = math.floor(lat * 1000) / 1000
    lon_floor = math.floor(lon * 1000) / 1000

    return [
        round(lat_floor + grid_size, 3),  # North
        round(lon_floor, 3),              # West
        round(lat_floor, 3),              # South
        round(lon_floor + grid_size, 3),  # East
    ]

# =========================
# Streamlit UI
# =========================
st.set_page_config(layout="centered")
st.title("ERA5 Point Downloader (Yearly – Manual / Fire-and-Forget)")

st.info(
    "Colab-equivalent behavior:\n"
    "- ONE year per request\n"
    "- netcdf4 format\n"
    "- ERA5 native grid point\n"
    "- Submit → break → click next year"
)

# =========================
# Session state
# =========================
if "current_year" not in st.session_state:
    st.session_state.current_year = None
if "locked" not in st.session_state:
    st.session_state.locked = False
if "prev_start_year" not in st.session_state:
    st.session_state.prev_start_year = None

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

st.subheader("📅 Year range")
start_year = st.number_input("Start year", value=2013, step=1)
end_year = st.number_input("End year", value=2022, step=1)

# =========================
# Sync current_year with start_year
# =========================
if st.session_state.prev_start_year != start_year:
    st.session_state.current_year = start_year
    st.session_state.prev_start_year = start_year

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
# Completion check
# =========================
all_done = st.session_state.current_year > end_year-1

# =========================
# CDS submission
# =========================
def submit_year_blocking(area, year, variables, url, key):
    c = cdsapi.Client(url=url, key=key, quiet=False)

    request = {
        "product_type": "reanalysis",
        "variable": variables,
        "year": str(year),
        "month": [f"{m:02d}" for m in range(1, 13)],
        "day": [f"{d:02d}" for d in range(1, 32)],
        "time": [f"{h:02d}:00" for h in range(24)],
        "area": area,
        "format": "netcdf4",
    }

    # Fire-and-forget: launch request only
    c.retrieve(
        "reanalysis-era5-single-levels",
        request,
        "era5_request_placeholder.nc",
    )

# =========================
# Submit button
# =========================
button_disabled = st.session_state.locked or all_done

if st.button("🚀 Submit CURRENT YEAR", disabled=button_disabled):

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

# =========================
# Status
# =========================
st.markdown("---")

if all_done:
    st.success("🎉 All requested years have been submitted.")
    st.write("✅ Last submitted year:", end_year)
else:
    st.write("🟢 Next year to submit:", st.session_state.current_year)

