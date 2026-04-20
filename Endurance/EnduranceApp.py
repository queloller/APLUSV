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

# SIDEBAR INPUTS
st.sidebar.header("Battery Parameters")
voltage = st.sidebar.number_input("Battery Voltage (V)", min_value=12.0, max_value=60.0, value=25.6, step=0.1)
capacity = st.sidebar.number_input("Battery Capacity (Ah)", min_value=10.0, max_value=500.0, value=100.0, step=1.0)
discharge = st.sidebar.slider("Allowable Discharge (%)", min_value=10, max_value=100, value=80, step=5)

st.sidebar.header("Mission Parameters")
payload = st.sidebar.slider("Payload Weight (lbs)", min_value=0, max_value=180, value=24, step=2)
payload_draw = st.sidebar.slider("Payload Power Draw (W)", min_value=0, max_value=500, value=50, step=5)

# CALCULATIONS
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
    max_end_mins = int((max_endurance-max_end_hrs)/60)
else:
    max_range = 0
    opt_speed = 0
    max_end_hrs = 0
    max_end_mins = 0

# DASHBOARD DISPLAY
col1, col2, col3, col4 = st.columns(4)
col1.metric(label="Maximum Track Distance", value=f"{max_range:.1f} km")
col2.metric(label="Maximum Endurance", value=f"{hours}h {minutes:02d}m")
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
