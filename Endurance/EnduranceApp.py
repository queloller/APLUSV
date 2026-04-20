import streamlit as st
import numpy as np
import pandas as pd
import plotly.graph_objects as go

# PAGE CONFIGURATION
st.set_page_config(page_title="APLUSV Range Optimizer", layout="wide")
st.title("APLUSV Range & Optimal Speed Calculator")
st.markdown("Calculate optimal survey speed and maximum track distance for APLUSV.")

# CONSTANTS
rho_w = 1000 # kg/m^3
num_thrusters = 2
v_pitch = 3.94 # m/s
MAX_MOTOR_POWER_TOTAL = 2100 # Hardware limit (W)
hotel_power_baseline = 14.8 # Pixhawk + Comms (W)

# Empirical ApisQueen Curve Coefficients
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

# Callbacks: When one changes, explicitly overwrite the other's key
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
st.sidebar.header("Battery Parameters")
voltage = st.sidebar.number_input("Battery Voltage (V)", min_value=12.0, max_value=60.0, value=25.6, step=0.1)
capacity = st.sidebar.number_input("Battery Capacity (Ah)", min_value=10.0, max_value=500.0, value=100.0, step=1.0)

# Allowable Discharge UI
st.sidebar.markdown("**Allowable Discharge (%)**")
col_d1, col_d2 = st.sidebar.columns([3, 1])
with col_d1:
    st.slider("Discharge Slider", min_value=10, max_value=100, step=5, 
              key="discharge_slider", on_change=sync_discharge, args=('slider',), 
              label_visibility="collapsed")
with col_d2:
    st.number_input("Discharge Num", min_value=10, max_value=100, step=5, 
                    key="discharge_num", on_change=sync_discharge, args=('num',), 
                    label_visibility="collapsed")

st.sidebar.header("Mission Parameters")

# Payload Weight UI
st.sidebar.markdown("**Payload Weight (lbs)**")
col1, col2 = st.sidebar.columns([3, 1])
with col1:
    st.slider("Payload Slider", min_value=0, max_value=180, step=2, 
              key="payload_slider", on_change=sync_payload, args=('slider',), 
              label_visibility="collapsed")
with col2:
    st.number_input("Payload Num", min_value=0, max_value=180, step=2, 
                    key="payload_num", on_change=sync_payload, args=('num',), 
                    label_visibility="collapsed")

# Active Sensor Draw UI
st.sidebar.markdown("**Payload Power Draw (W)**")
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

# CdA Extrapolation
if payload < 24:
    cda = -0.00001649 * (payload**2) + 0.0009375 * payload + 0.0726
else:
    cda = 0.0856 + 0.0001458 * (payload - 24.0)

speeds = np.arange(0.1, 1.55, 0.01) # High resolution sweep
valid_speeds = []
ranges = []

for v in speeds:
    drag = 0.5 * rho_w * cda * (v**2)
    t_req = drag / (1 - (v / v_pitch))
    t_single = t_req / num_thrusters
    
    # Apply empirical power curve
    p_motor_single = (EMP_A * (t_single**2)) + (EMP_B * t_single) + EMP_C
    total_motor_power = p_motor_single * num_thrusters
    
    # Cutoff: USV cannot reach this speed
    if total_motor_power > MAX_MOTOR_POWER_TOTAL:
        break
        
    total_power = total_motor_power + total_hotel_power
    endurance_hrs = usable_energy_wh / total_power
    range_km = v * endurance_hrs * 3.6
    
    valid_speeds.append(v)
    ranges.append(range_km)

# Find Peak Performance
if ranges:
    max_range = max(ranges)
    opt_speed = valid_speeds[ranges.index(max_range)]
    max_endurance = max_range/opt_speed*1000/3600
    max_end_hrs = int(max_endurance)
    
    # [BUG FIX HERE] Multiply by 60 to get minutes
    max_end_mins = int((max_endurance - max_end_hrs) * 60)
else:
    max_range = 0
    opt_speed = 0
    max_end_hrs = 0
    max_end_mins = 0

# DASHBOARD DISPLAY
col1, col2, col3, col4 = st.columns(4)
col1.metric(label="Maximum Track Distance", value=f"{max_range:.1f} km")
col2.metric(label="Maximum Endurance", value=f"{max_end_hrs}h {max_end_mins:02d}m")
col3.metric(label="Optimal Survey Speed", value=f"{opt_speed:.2f} m/s")
col4.metric(label="Total Usable Energy", value=f"{usable_energy_wh:.0f} Wh")

st.markdown("---")

# Plotly Interactive Chart
fig = go.Figure()
fig.add_trace(go.Scatter(
    x=valid_speeds, 
    y=ranges, 
    mode='lines', 
    name='Range Profile',
    line=dict(color='#1976D2', width=3)
))

# Highlight the optimal point
fig.add_trace(go.Scatter(
    x=[opt_speed], 
    y=[max_range], 
    mode='markers', 
    name='Optimal Cruise',
    marker=dict(color='#D32F2F', size=10, symbol='star')
))

fig.update_layout(
    title="Mission Range vs. Speed",
    xaxis_title="Survey Speed (m/s)",
    yaxis_title="Total Range (km)",
    hovermode="x unified",
    template="plotly_white",
    showlegend=False
)

st.plotly_chart(fig, use_container_width=True)
