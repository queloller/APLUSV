import streamlit as st
import numpy as np
import pandas as pd
import plotly.graph_objects as go

st.set_page_config(page_title="APLUSV Track Length Optimizer", layout="wide")

st.markdown(
    """
    <style>
    [data-testid="stSidebar"] p {
        font-size: 16px !important;
    }
    [data-testid="stSidebar"] input {
        font-size: 16px !important;
        font-weight: bold !important;
    }
    .sidebar-ribbon {
        background-color: #004B87; 
        color: white;
        padding: 10px 15px;
        border-radius: 5px;
        font-weight: bold;
        font-size: 18px;
        margin-top: 15px;
        margin-bottom: 25px; /* FIXED: Increased from 10px to push the first label down */
        box-shadow: 1px 1px 3px rgba(0,0,0,0.2);
    }
    .sidebar-label {
        font-size: 16px; 
        font-weight: 700; 
        color: #333; 
        margin-bottom: 5px; 
    }
    </style>
    """,
    unsafe_allow_html=True
)

st.title("APLUSV Track Length & Optimal Speed Calculator")

st.markdown(
    """
    <p style='font-size: 24px; font-weight: bold; color: #4A4A4A;'>
    Calculate optimal survey speed and maximum traverse for APLUSV.
    </p>
    """, 
    unsafe_allow_html=True
)

# make top metrics pop more
def draw_flashy_card(title, value, bottom_text=""):
    st.markdown(
        f"""
        <div style="
            background-color: #f8f9fa;
            border-left: 5px solid #004B87;
            padding: 20px;
            border-radius: 5px;
            box-shadow: 2px 2px 5px rgba(0,0,0,0.1);
        ">
            <p style="margin: 0; font-size: 18px; font-weight: bold; color: #555;">{title}</p>
            <p style="margin: 0; font-size: 36px; font-weight: 900; color: #111;">{value}</p>
            <p style="margin: 0; font-size: 14px; color: #888;">{bottom_text}</p>
        </div>
        """,
        unsafe_allow_html=True
    )

# CONSTANTS
rho_w = 1000 # kg/m^3
num_thrusters = 2
v_pitch = 3.94 # m/s
MAX_CURRENT_TOTAL = 60 # Hardware fuse limit (30A per circuit x 2)
hotel_power_baseline = 14.8 # Pixhawk + Comms + Nav (W)

# Empirical coefficients based on Apisqueen U92 thruster data
EMP_A = 0.046405
EMP_B = 1.854865
EMP_C = 1.837475

# SESSION STATE INITIALIZATION
# Initialize the widget keys directly
if 'discharge_slider' not in st.session_state:
    st.session_state.discharge_slider = 80
if 'discharge_num' not in st.session_state:
    st.session_state.discharge_num = 80
    
if 'payload_slider' not in st.session_state:
    st.session_state.payload_slider = 24
if 'payload_num' not in st.session_state:
    st.session_state.payload_num = 24
    
if 'sensor_slider' not in st.session_state:
    st.session_state.sensor_slider = 50
if 'sensor_num' not in st.session_state:
    st.session_state.sensor_num = 50

# When one widget change, override the other
def sync_discharge(source):
    if source == 'slider':
        st.session_state.discharge_num = st.session_state.discharge_slider
    else:
        st.session_state.discharge_slider = st.session_state.discharge_num

def sync_payload(source):
    if source == 'slider':
        st.session_state.payload_num = st.session_state.payload_slider
    else:
        st.session_state.payload_slider = st.session_state.payload_num

def sync_sensor(source):
    if source == 'slider':
        st.session_state.sensor_num = st.session_state.sensor_slider
    else:
        st.session_state.sensor_slider = st.session_state.sensor_num

# SIDEBAR INPUTS

# Battery voltage
st.sidebar.markdown('<div class="sidebar-ribbon">🔋 Battery Parameters</div>', unsafe_allow_html=True)
st.sidebar.markdown('<p class="sidebar-label">Battery Voltage (V)</p>', unsafe_allow_html=True) 
voltage = st.sidebar.number_input("Battery Voltage", min_value=12.0, max_value=60.0, value=25.6, step=0.1, label_visibility="collapsed")

# Battery capacity
st.sidebar.markdown('<p class="sidebar-label">Battery Capacity (Ah)</p>', unsafe_allow_html=True)
capacity = st.sidebar.number_input("Battery Capacity", min_value=10.0, max_value=500.0, value=100.0, step=1.0, label_visibility="collapsed")

# Allowable discharge
st.sidebar.markdown('<p class="sidebar-label">Allowable Discharge (%)</p>', unsafe_allow_html=True)
col_d1, col_d2 = st.sidebar.columns([3, 1])
with col_d1:
    st.slider("Discharge Slider", min_value=10, max_value=100, step=5, 
              key="discharge_slider", on_change=sync_discharge, args=('slider',), 
              label_visibility="collapsed")
with col_d2:
    st.number_input("Discharge Num", min_value=10, max_value=100, step=5, 
                    key="discharge_num", on_change=sync_discharge, args=('num',), 
                    label_visibility="collapsed")

st.sidebar.markdown('<div class="sidebar-ribbon">🛥️ Mission Parameters</div>', unsafe_allow_html=True)

# Payload weight
st.sidebar.markdown('<p class="sidebar-label">Payload Weight (lbs)</p>', unsafe_allow_html=True)
col1, col2 = st.sidebar.columns([3, 1])
with col1:
    st.slider("Payload Slider", min_value=0, max_value=180, step=2, 
              key="payload_slider", on_change=sync_payload, args=('slider',), 
              label_visibility="collapsed")
with col2:
    st.number_input("Payload Num", min_value=0, max_value=180, step=2, 
                    key="payload_num", on_change=sync_payload, args=('num',), 
                    label_visibility="collapsed")

# Active sensor draw / payload power draw
st.sidebar.markdown('<p class="sidebar-label">Payload Power Draw (W)</p>', unsafe_allow_html=True)
col3, col4 = st.sidebar.columns([3, 1])
with col3:
    st.slider("Sensor Slider", min_value=0, max_value=500, step=5, 
              key="sensor_slider", on_change=sync_sensor, args=('slider',), 
              label_visibility="collapsed")
with col4:
    st.number_input("Sensor Num", min_value=0, max_value=500, step=5, 
                    key="sensor_num", on_change=sync_sensor, args=('num',), 
                    label_visibility="collapsed")

# CALCULATIONS
discharge = st.session_state.discharge_slider
payload = st.session_state.payload_slider
payload_draw = st.session_state.sensor_slider

usable_energy_wh = voltage * capacity * (discharge / 100.0)
total_hotel_power = hotel_power_baseline + payload_draw

# Max allowable motor power
max_motor_power_total = MAX_CURRENT_TOTAL * voltage

# Empirical CdA extrapolation based on hull shape
# Derived directly from Triadelphia Reservoir Telemetry

dyn_A = -0.00002147
dyn_B = 0.00120930
dyn_C = 0.09135618
dyn_slope = 0.00017872
cda_24 = 0.10801256

if payload < 24:
    # Parabolic curve fit for light loads (0 to 24 lbs)
    cda = (dyn_A * payload**2) + (dyn_B * payload) + dyn_C
else:
    # Linear extrapolation for heavy payloads (24+ lbs)
    cda = cda_24 + dyn_slope * (payload - 24.0)

# Expanded sweep to 2.50 m/s so it can find true limit
speeds = np.arange(0.1, 2.50, 0.01) 
valid_speeds = []
ranges = []
endurances_formatted = []
powers = []

for v in speeds:
    drag = 0.5 * rho_w * cda * (v**2)
    t_req = drag / (1 - (v / v_pitch))
    t_single = t_req / num_thrusters
    
    # Apply empirical power curve
    p_motor_single = (EMP_A * (t_single**2)) + (EMP_B * t_single) + EMP_C
    total_motor_power = p_motor_single * num_thrusters
    
    # Cutoff: USV hits the 60A fuse limit
    if total_motor_power > max_motor_power_total:
        break
        
    total_power = total_motor_power + total_hotel_power
    endurance_hrs = usable_energy_wh / total_power
    range_km = v * endurance_hrs * 3.6
    
    # Format the endurance into an "xxh xxm" string
    e_hrs = int(endurance_hrs)
    e_mins = int((endurance_hrs - e_hrs) * 60)
    formatted_time = f"{e_hrs}h {e_mins:02d}m"
    
    valid_speeds.append(v)
    ranges.append(range_km)
    endurances_formatted.append(formatted_time)
    powers.append(total_power)

# Find peak performance
if ranges:
    max_range = max(ranges)
    opt_speed = valid_speeds[ranges.index(max_range)]
    opt_power = powers[ranges.index(max_range)]
    max_endurance = max_range/opt_speed*1000/3600
    max_end_hrs = int(max_endurance)
    max_end_mins = int((max_endurance - max_end_hrs) * 60)
else:
    max_range = 0
    opt_speed = 0
    opt_power = 0
    max_end_hrs = 0
    max_end_mins = 0

# NEW: Combine Endurance and Power into a single 2D array for Plotly
custom_data_main = list(zip(endurances_formatted, powers))
custom_data_peak = [[f"{max_end_hrs}h {max_end_mins:02d}m", opt_power]]

# Metrics
col1, col2, col3, col4 = st.columns(4)

with col1:
    draw_flashy_card("Max Track Distance", f"{max_range:.1f} km")

with col2:
    draw_flashy_card("Max Endurance", f"{max_end_hrs}h {max_end_mins:02d}m")

with col3:
    draw_flashy_card("Optimal Survey Speed", f"{opt_speed:.2f} m/s")

with col4:
    draw_flashy_card("Total Usable Energy", f"{usable_energy_wh:.0f} Wh")

st.markdown("---")

# Plotly interactive chart
fig = go.Figure()

# The main Blue Line
fig.add_trace(go.Scatter(
    x=valid_speeds, 
    y=ranges, 
    mode='lines', 
    name='Range Profile',
    line=dict(color='#1976D2', width=3),
    customdata=custom_data_main, # Feed the 2D array here
    hovertemplate=(
        "<b>Speed:</b> %{x:.2f} m/s<br>"
        "<b>Track:</b> %{y:.1f} km<br>"
        "<b>Endurance:</b> %{customdata[0]}<br>"   # Index 0 is the endurance string
        "<b>Power Draw:</b> %{customdata[1]:.1f} W" # Index 1 is the power float
        "<extra></extra>"
    )
))

# Highlight the optimal point (The Red Star)
fig.add_trace(go.Scatter(
    x=[opt_speed], 
    y=[max_range], 
    mode='markers', 
    name='Optimal Cruise',
    marker=dict(color='#D32F2F', size=12, symbol='star'),
    customdata=custom_data_peak, # Feed the peak 2D array here
    hovertemplate=(
        "<b>OPTIMAL CRUISE</b><br>"
        "<b>Speed:</b> %{x:.2f} m/s<br>"
        "<b>Track:</b> %{y:.1f} km<br>"
        "<b>Endurance:</b> %{customdata[0]}<br>"
        "<b>Power Draw:</b> %{customdata[1]:.1f} W"
        "<extra></extra>"
    )
))

fig.update_layout(
    # 1. Enlarge and bold the Main Title
    title=dict(
        text="<b>Track Length vs. Speed</b>",
        font=dict(size=30, color="#111") # High-contrast black
    ),
    
    # 2. Enlarge and bold the X-Axis label, plus bump up the tick numbers
    xaxis=dict(
        title=dict(
            text="<b>Survey Speed (m/s)</b>", 
            font=dict(size=24, color="#333")
        ),
        tickfont=dict(size=18, color="#222", weight="bold"), # Makes the numbers bigger/bolder
        dtick=0.1, 
        range=[0.1, max(valid_speeds) if valid_speeds else 1.5]
    ),
    
    # 3. Enlarge and bold the Y-Axis label, plus bump up the tick numbers
    yaxis=dict(
        title=dict(
            text="<b>Total Track Length (km)</b>", 
            font=dict(size=24, color="#333")
        ),
        tickfont=dict(size=18, color="#222", weight="bold"),
    ),
    
    hovermode="x",
    template="plotly_white",
    showlegend=False,
    
    # Optional: Adds a little breathing room around the bigger text
    margin=dict(l=70, r=30, t=70, b=70) 
)

st.plotly_chart(fig, use_container_width=True)
