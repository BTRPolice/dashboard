# This code requires Streamlit to be installed. To install, run: pip install streamlit
import streamlit as st
import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
import folium
from folium.plugins import MarkerCluster
from streamlit_folium import folium_static
from datetime import datetime, timedelta

st.set_page_config(
    page_title="Bastar Police Crime Dashboard",  # Title shown in browser tab
    page_icon="https://i.imgur.com/nbeOUY1.jpeg",
    layout="centered"
)

# --- Google Sheets Config ---
SHEET_URL = "https://docs.google.com/spreadsheets/d/1m1K7kwXxiLClu4dPbb3YgpnCTok6sGoJarjZkIV_1gE/export?format=csv"

# --- Load Data ---
@st.cache_data
def load_data():
    data = pd.read_csv(SHEET_URL)
    data.columns = data.columns.str.strip().str.lower().str.replace(" ", "_")
    date_cols = ['date_reported', 'arrest_date', 'chargesheet_date']
    for col in date_cols:
        if col in data.columns:
            data[col] = pd.to_datetime(data[col], errors='coerce')
    return data

# --- Load & Preprocess ---
df = load_data()

st.sidebar.markdown(
    """
    <div style="text-align: center; padding-bottom: 10px;">
        <img src="https://i.imgur.com/nbeOUY1.jpeg" 
             width="120" style="border-radius: 50%;">
        <h4 style="margin-top:10px;">Bastar Police</h4>
    </div>
    """,
    unsafe_allow_html=True
)



# --- Sidebar Filters ---
st.sidebar.header("🔎 Filters")




# Date range filter
min_date, max_date = df['date_reported'].min(), df['date_reported'].max()
date_range = st.sidebar.date_input("Select Date Range", [min_date, max_date], min_value=min_date, max_value=max_date)

# Station filter
stations = df['police_station'].dropna().unique().tolist()
selected_stations = st.sidebar.multiselect("Select Police Stations", stations, default=stations)

# Crime type filter
crime_types = df['crime_type'].dropna().unique().tolist()
selected_crimes = st.sidebar.multiselect("Select Crime Types", crime_types, default=crime_types)

# FIR search
search_fir = st.sidebar.text_input("🔍 Search by FIR Number")

# Chargesheet Due Filter
show_due = st.sidebar.button("📋 Chargesheet Soon")

# NEW: Accused Not Arrested Filter
show_unarrested = st.sidebar.button("🚨 Accused Not Arrested (45+ days)")

if search_fir:
    search_result = df[df['fir_number'].astype(str).str.contains(search_fir, case=False, na=False)]
    st.title(f"🔎 FIR Search Result: {search_fir}")
    st.write(search_result)
    st.stop()

if show_due:
    st.title("⚠️ Chargesheet Due Soon")
    today = datetime.now()
    df['cs_due'] = df['date_reported'] + pd.to_timedelta(60, unit='d')
    df['days_left'] = (df['cs_due'] - today).dt.days
    due_soon_df = df[(df['chargesheet_filed'].astype(str).str.lower() != 'yes') & (df['days_left'] <= 10) & (df['days_left'] >= 0)]

    for idx, row in due_soon_df.iterrows():
        with st.expander(f"Case ID: {row['case_id']} | FIR: {row['fir_number']}"):
            st.write(row.drop(labels=['cs_due', 'days_left']))

    if st.button("🔙 Back to Dashboard"):
        st.experimental_rerun()

    st.stop()

if show_unarrested:
    st.title("🚨 Accused Not Arrested Beyond 45 Days")
    today = datetime.now()
    unarrested_df = df[
        (df['accused_arrested'].astype(str).str.lower() != 'yes') &
        ((today - df['date_reported']).dt.days > 45)
    ]

    for idx, row in unarrested_df.iterrows():
        with st.expander(f"Case ID: {row['case_id']} | FIR: {row['fir_number']}"):
            st.write(row.drop(labels=['cs_due', 'days_left'], errors='ignore'))

    if st.button("🔙 Back to Dashboard"):
        st.experimental_rerun()

    st.stop()

# Apply filters
filtered_df = df[
    (df['date_reported'] >= pd.to_datetime(date_range[0])) &
    (df['date_reported'] <= pd.to_datetime(date_range[1])) &
    (df['police_station'].isin(selected_stations)) &
    (df['crime_type'].isin(selected_crimes))
]

# --- Dashboard Title ---
st.title("📊 Bastar Police Crime Dashboard")

# --- Summary Metrics ---
with st.container():
    st.subheader("🔍 Key Metrics")
    col1, col2, col3, col4 = st.columns(4)
    col1.metric("Total Cases", len(filtered_df))
    col2.metric("FIR Numbers", filtered_df['fir_number'].notnull().sum())
    col3.metric("Arrests Made", filtered_df['accused_arrested'].astype(str).str.lower().eq('yes').sum())
    col4.metric("Charge Sheets Filed", filtered_df['chargesheet_filed'].astype(str).str.lower().eq('yes').sum())

    filtered_df['fir_to_arrest'] = (filtered_df['arrest_date'] - filtered_df['date_reported']).dt.days
    avg_fir_arrest = filtered_df['fir_to_arrest'].mean()
    filtered_df['arrest_to_chargesheet'] = (filtered_df['chargesheet_date'] - filtered_df['arrest_date']).dt.days
    avg_arrest_cs = filtered_df['arrest_to_chargesheet'].mean()

    col5, col6 = st.columns(2)
    col5.metric("Avg FIR → Arrest", f"{avg_fir_arrest:.1f} days")
    col6.metric("Avg Arrest → Chargesheet", f"{avg_arrest_cs:.1f} days")

# --- Charts in Grid ---
col1, col2 = st.columns([1.8, 1.8])

# Crime Type Chart
with col1:
    st.subheader("📈 Crime Type Distribution")
    if 'crime_type' in filtered_df.columns:
        crime_type_counts = filtered_df['crime_type'].value_counts().reset_index()
        crime_type_counts.columns = ['crime_type', 'count']
        crime_fig = px.bar(crime_type_counts,
                           x='crime_type', y='count',
                           labels={'crime_type': 'Crime Type', 'count': 'Count'},
                           color='crime_type', color_discrete_sequence=px.colors.qualitative.Set2)
        st.plotly_chart(crime_fig, use_container_width=False, width=1176)

# Police Station Chart
with col2:
    st.subheader("📍 Cases per Police Station")
    if 'police_station' in filtered_df.columns:
        ps_counts = filtered_df['police_station'].value_counts().reset_index()
        ps_counts.columns = ['police_station', 'count']
        ps_fig = px.bar(ps_counts,
                        x='police_station', y='count',
                        labels={'police_station': 'Station', 'count': 'Count'},
                        color='police_station', color_discrete_sequence=px.colors.qualitative.Set3)
        st.plotly_chart(ps_fig, use_container_width=False, width=1176)

# Status Pie Chart
st.subheader("⚖️ Case Status Overview")
if 'status' in filtered_df.columns:
    status_counts = filtered_df['status'].value_counts().reset_index()
    status_counts.columns = ['status', 'count']
    status_fig = px.pie(status_counts,
                        names='status', values='count')
    st.plotly_chart(status_fig, use_container_width=True)

# Monthly Crime Trends
st.subheader("📅 Monthly Crime Trend")
filtered_df['month_year'] = filtered_df['date_reported'].dt.to_period("M").astype(str)
monthly_counts = filtered_df.groupby(['month_year', 'crime_type']).size().reset_index(name='count')
trend_fig = px.line(monthly_counts, x='month_year', y='count', color='crime_type', markers=True,
                    labels={'month_year': 'Month-Year', 'count': 'Number of Cases'},
                    title="Crime Trends Over Time")
st.plotly_chart(trend_fig, use_container_width=True)

# Seasonal Analysis
st.subheader("🌤️ Seasonal Crime Analysis")
filtered_df['month'] = filtered_df['date_reported'].dt.month
season_map = {12: 'Winter', 1: 'Winter', 2: 'Winter',
              3: 'Spring', 4: 'Spring', 5: 'Summer',
              6: 'Summer', 7: 'Monsoon', 8: 'Monsoon', 9: 'Monsoon',
              10: 'Autumn', 11: 'Autumn'}
filtered_df['season'] = filtered_df['month'].map(season_map)
season_counts = filtered_df['season'].value_counts().reset_index()
season_counts.columns = ['season', 'count']
season_fig = px.bar(season_counts, x='season', y='count', color='season',
                    labels={'season': 'Season', 'count': 'Number of Crimes'},
                    color_discrete_sequence=px.colors.qualitative.Pastel)
st.plotly_chart(season_fig, use_container_width=True)

# --- Geo Map ---
# Interactive Map
st.subheader("🗺️ Crime Map of Jagdalpur")
crime_map = folium.Map(location=[19.0748, 82.0186], zoom_start=13)
marker_cluster = MarkerCluster().add_to(crime_map)

color_map = {
    'Theft': 'red',
    'Murder': 'black',
    'Assault': 'orange',
    'Drugs': 'green',
    'Cybercrime': 'blue',
    'Other': 'purple'
}

# Loop through rows using 'location' string
for _, row in filtered_df.iterrows():
    location_str = row.get('location')
    if pd.notnull(location_str):
        try:
            lat, lon = map(float, location_str.split(','))
            crime = row.get('crime_type', 'Other')
            color = color_map.get(crime, 'gray')
            popup_content = f"""
            <b>FIR:</b> {row.get('fir_number')}<br>
            <b>Crime:</b> {crime}<br>
            <b>Date:</b> {row.get('date_reported').date() if pd.notnull(row.get('date_reported')) else 'N/A'}<br>
            <b>Location:</b> {location_str}
            """
            folium.Marker(
                location=[lat, lon],
                popup=folium.Popup(popup_content, max_width=300),
                icon=folium.Icon(color=color)
            ).add_to(marker_cluster)
        except:
            continue

# Legend (unchanged)
legend_html = '''
<div style="position: fixed; 
     bottom: 50px; left: 50px; width: 200px; height: 150px; 
     background-color: white; z-index:9999; font-size:14px;
     border:2px solid grey; padding: 10px;">
<b>Crime Type Legend</b><br>
Red: Theft<br>
Black: Murder<br>
Orange: Assault<br>
Green: Drugs<br>
Blue: Cybercrime<br>
Purple: Other<br>
</div>'''
crime_map.get_root().html.add_child(folium.Element(legend_html))
folium_static(crime_map)


# Footer
st.caption("Built for BNSS 2023 Compliance and Real-time Crime Monitoring by CSP Udit ")
