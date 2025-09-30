# sidebar61.py
import streamlit as st
from tariff import TARIFF_BANDS

def draw_sidebar(usage_key: str) -> None:
    with st.sidebar:
        st.header("Tariffs & Overheads")
        st.markdown("← Set tariff and overhead rates here")

        if usage_key not in TARIFF_BANDS:
            usage_key = "low"
        band = TARIFF_BANDS[usage_key]

        # initialise if missing
        if "electricity_rate" not in st.session_state:
            st.session_state["electricity_rate"] = float(band["rates"]["elec_unit"])
        if "gas_rate" not in st.session_state:
            st.session_state["gas_rate"] = float(band["rates"]["gas_unit"])
        if "water_rate" not in st.session_state:
            st.session_state["water_rate"] = float(band["rates"]["water_unit"])
        if "admin_monthly" not in st.session_state:
            st.session_state["admin_monthly"] = float(band["rates"]["admin_monthly"])
        if "maint_rate_per_m2_y" not in st.session_state:
            st.session_state["maint_rate_per_m2_y"] = float(band["intensity_per_year"]["maint_gbp_per_m2"])
        if "maint_method" not in st.session_state:
            st.session_state["maint_method"] = "£/m² per year (industry standard)"

        # Electricity
        st.markdown("**Electricity**")
        st.number_input("Unit rate (£/kWh)", min_value=0.0, step=0.0001, format="%.4f", key="electricity_rate")
        st.number_input("Daily charge (£/day)", min_value=0.0, step=0.001, format="%.3f", key="elec_daily")

        # Gas
        st.markdown("**Gas**")
        st.number_input("Unit rate (£/kWh)", min_value=0.0, step=0.0001, format="%.4f", key="gas_rate")
        st.number_input("Daily charge (£/day)", min_value=0.0, step=0.001, format="%.3f", key="gas_daily")

        # Water
        st.markdown("**Water**")
        st.number_input("Unit rate (£/m³)", min_value=0.0, step=0.10, format="%.2f", key="water_rate")

        # Maintenance
        st.markdown("**Maintenance / Depreciation**")
        st.number_input("Maintenance rate (£/m²/year)", min_value=0.0, step=0.5, key="maint_rate_per_m2_y")

        # Administration
        st.markdown("**Administration**")
        st.number_input("Admin (monthly £)", min_value=0.0, step=25.0, key="admin_monthly")