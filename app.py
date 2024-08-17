import streamlit as st
from pymongo import MongoClient
from datetime import datetime, timedelta
import pandas as pd
import numpy as np
from sklearn.model_selection import train_test_split
from sklearn.linear_model import LinearRegression
import paho.mqtt.client as mqtt
import json
from streamlit_chat import message
import requests

# Set the background image
background_image = """
<style>
[data-testid="stAppViewContainer"] > .main {
    background-image: url("https://c4.wallpaperflare.com/wallpaper/315/39/662/waterdrop-droplet-water-drop-wallpaper-preview.jpg");
    background-size: 100vw 100vh;  # This sets the size to cover 100% of the viewport width and height
    background-position: center;  
    background-repeat: no-repeat;
    opacity: 0.9;
}
</style>
"""

st.markdown(background_image, unsafe_allow_html=True)

# MongoDB settings
MONGO_URI = "mongodb+srv://savaqua:12345@cluster0.duspxwp.mongodb.net/?retryWrites=true&w=majority&appName=Cluster0"
client = MongoClient(MONGO_URI)
db = client.data_sensor
water_flow_collection = db.water_flow
master_data_collection = db.master_data
activity_collection = db.activities
history_collection = db.history

# MQTT settings
MQTT_BROKER = "c0ae257fb0f1403bb96d10c278d890ee.s1.eu.hivemq.cloud"
MQTT_PORT = 8883
MQTT_TOPIC_VALVE = "waterflow/valve"
MQTT_USERNAME = "savaqua"
MQTT_PASSWORD = "Savaqua123"

mqtt_client = mqtt.Client(mqtt.CallbackAPIVersion.VERSION2)
mqtt_client.username_pw_set(MQTT_USERNAME, MQTT_PASSWORD)
mqtt_client.tls_set()
mqtt_client.connect(MQTT_BROKER, MQTT_PORT, 60)
mqtt_client.loop_start()

# Initial state variables
valve_state = False

# Set IP ESP32 
ESP32_IP = 'https://a31a-36-68-30-79.ngrok-free.app/'

# Fetch total volume from MongoDB (from history collection)
def fetch_total_volume():
    total_volume_data = history_collection.find_one(sort=[("timestamp", -1)], projection={"_id": 0, "total_volume": 1})
    return total_volume_data['total_volume'] if total_volume_data else 0.0

# Fetch all data from history collection in MongoDB
def fetch_all_data():
    return pd.DataFrame(list(history_collection.find({}, {"_id": 0})))

# Fetch master data settings from MongoDB
def fetch_master_data():
    master_data = master_data_collection.find_one()
    if master_data:
        return (
            master_data.get("price_per_liter", 1.0),
            master_data.get("tank_size", 1000.0)
        )
    return 1.0, 1000.0

# Update master data settings in MongoDB
def update_master_data(price_per_liter, tank_size):
    master_data_collection.update_one(
        {},
        {"$set": {"price_per_liter": price_per_liter,"tank_size": tank_size}},
        upsert=True
    )

# Preprocess data
def preprocess_data(data):
    # Convert timestamp to datetime format
    data['timestamp'] = pd.to_datetime(data['timestamp'])
    
    # Extract features for regression
    data['day_of_week'] = data['timestamp'].dt.dayofweek
    data['hour_of_day'] = data['timestamp'].dt.hour
    data['total_volume'] = data['total_volume'].astype(float)

    return data

# Train regression model
def train_regression_model(data):
    X = data[['day_of_week', 'hour_of_day']]
    y = data['total_volume']
    
    X_train, X_test, y_train, y_test = train_test_split(X, y, test_size=0.2, random_state=42)
    
    model = LinearRegression()
    model.fit(X_train, y_train)
    
    return model, X_test, y_test

# Predict usage category based on volume
def predict_usage_category(model, X_test):
    y_pred = model.predict(X_test)
    return np.where(y_pred >= np.mean(y_pred), 'Boros', 'Hemat')

# Calculate predicted total bill based on predicted volume and price per liter
def predict_total_bill(predicted_volume, price_per_liter):
    return predicted_volume * price_per_liter

# Predict future water usage
def predict_future_usage(model, days=7):
    future_dates = [datetime.now() + timedelta(days=i) for i in range(1, days + 1)]
    future_data = pd.DataFrame({
        'day_of_week': [date.weekday() for date in future_dates],
        'hour_of_day': [12 for _ in future_dates]  # Assuming predictions are for the average hour of the day
    })
    future_volumes = model.predict(future_data)
    return future_dates, future_volumes

# Dashboard page (updated to fetch the correct number of values from master data)
def dashboard_page():
    global valve_state
    st.title(":blue[Water] Flow :droplet: Monitor - Dashboard")
    st.write("## Daily and Monthly Usage Summary")

    data = fetch_all_data()
    
    if data.empty:
        st.write("No data available.")
        return
    
    processed_data = preprocess_data(data)
    
    price_per_liter, tank_size = fetch_master_data()
    
    # Calculate daily and monthly totals
    today = pd.Timestamp(datetime.now().date())
    month_start = today.replace(day=1)
    
    daily_data = processed_data[processed_data['timestamp'].dt.date == today.date()]
    monthly_data = processed_data[processed_data['timestamp'] >= month_start]
    
    total_daily_volume = daily_data['total_volume'].sum()
    total_monthly_volume = monthly_data['total_volume'].sum()
    
    total_daily_bill = total_daily_volume * price_per_liter
    total_monthly_bill = total_monthly_volume * price_per_liter
    
    container = st.container()
    container.write(f"### Total Water Used Today: {total_daily_volume:.2f} L")
    container.write(f"### Total Bill for Today: {total_daily_bill:.2f} IDR")
    container.write(f"### Total Water Used This Month: {total_monthly_volume:.2f} L")
    container.write(f"### Estimated Bill for This Month: {total_monthly_bill:.2f} IDR")
    
    # Display water usage data in a table
    st.write("## Water Usage Data")
    data['bill'] = data['total_volume'] * price_per_liter
    st.table(data[['timestamp', 'total_volume', 'bill']])
    
    # Display water usage data in a line chart
    st.write("## Water Usage Chart")
    st.line_chart(data.set_index('timestamp')[['total_volume']])

    # Predict future usage
    if not data.empty:
        processed_data = preprocess_data(data)
        model, X_test, y_test = train_regression_model(processed_data)
        usage_category = predict_usage_category(model, X_test)
        future_dates, future_volumes = predict_future_usage(model, days=7)
        future_usage_df = pd.DataFrame({
            'Date': future_dates,
            'Predicted Volume (L)': future_volumes,
            'Usage Category': np.where(future_volumes >= np.mean(future_volumes), 'Boros', 'Hemat')
        })

        st.write("## Future Water Usage Predictions")
        st.table(future_usage_df[['Date', 'Predicted Volume (L)', 'Usage Category']])

def history_page():
    st.title("Water Usage History")
    st.write("## History")
    st.write("### Table of Water Usage History")

    price_per_liter, tank_size = fetch_master_data()
    data = fetch_all_data()

    if not data.empty:
        data['bill'] = data['total_volume'] * price_per_liter
        st.table(data)

        total_volume = data['total_volume'].sum()
        total_bill = data['bill'].sum()

        st.write(f"### Total Volume Used: {total_volume:.2f} L")
        st.write(f"### Total Bill: {total_bill:.2f} IDR")

        st.write("## Edit/Delete Record")
        record_to_edit = st.selectbox("Select Record to Edit/Delete", options=data['timestamp'].astype(str).tolist())
        record_index = data[data['timestamp'].astype(str) == record_to_edit].index[0]

        new_total_volume = st.number_input("New Total Volume (L)", min_value=0.0, step=1.0, value=float(data.loc[record_index, 'total_volume']))
        new_bill = new_total_volume * price_per_liter

        if st.button("Update Record"):
            history_collection.update_one(
                {"timestamp": data.loc[record_index, 'timestamp']},
                {"$set": {"total_volume": new_total_volume, "bill": new_bill}}
            )
            st.success(f"Record at {record_to_edit} updated to {new_total_volume} L, {new_bill} IDR")

        if st.button("Delete Record"):
            history_collection.delete_one({"timestamp": data.loc[record_index, 'timestamp']})
            st.success(f"Record at {record_to_edit} deleted")
    else:
        st.write("No data available")


# Master data page
def master_data_page():
    st.title("Master Data")
    st.write("## Pricing, and Tank Size")

    price_per_liter,  tank_size = fetch_master_data()

    new_price_per_liter = st.number_input("Set Price per Liter (IDR)", min_value=0.0, step=1.0, value=price_per_liter)
    new_tank_size = st.number_input("Set Tank Size (L)", min_value=0.0, step=1.0, value=tank_size)

    if st.button("Save"):
        update_master_data(new_price_per_liter,  new_tank_size)
        st.success(f"New price per liter set to {new_price_per_liter} IDR")
        st.success(f"New tank size set to {new_tank_size} L")

# Control page (updated to fetch the correct number of values from master data)
# Control page with data collection and storage to history_collection
def control_page():
    global valve_state
    st.title("Water Control")
    st.write("## Calculate Required Water Volume")
    number_of_people = st.number_input("Number of People", min_value=1, step=1, value=1)
    
    st.write("## Select Activities")
    activities = list(activity_collection.find({}, {"_id": 0}))
    
    total_volume = 0  # Initialize total_volume to 0
    if activities:
        selected_activities = st.multiselect("Select Activities", options=[activity["name"] for activity in activities])
        total_volume = sum([activity["amount(L)"] for activity in activities if activity["name"] in selected_activities]) * number_of_people
        price_per_liter, tank_size = fetch_master_data()
        estimated_cost = total_volume * price_per_liter
        
        st.write(f"### Total Water Volume Required: {total_volume:.2f} L")
        st.write(f"### Estimated Cost: {estimated_cost:.2f} IDR")
    else:
        st.write("No activities found.")
    
    # Form untuk mengatur volume air
    st.header("Set Water Volume")
    volume = st.number_input("Enter water volume (liters):", min_value=0.0, format="%.2f", value=float(total_volume))
    if st.button("Set Volume"):
        response = requests.post(f"{ESP32_IP}/setVolume", data={'volume': volume})
        if response.status_code == 303:
            st.error("Failed to set volume")
        else:
            st.success(f"Target volume set to: {volume} L")

    # Tombol untuk memulai dan menghentikan dispensing air
    st.header("Control Dispensing")
    
    if st.button("Start"):
        response = requests.get(f"{ESP32_IP}/start")
        if response.status_code == 303:
            st.error("Failed to start dispensing")
        else:
            st.success("Dispensing started...")
            st.session_state['dispensing'] = True
            st.session_state['start_time'] = datetime.now()
            st.session_state['total_volume'] = 0  # Initialize total volume
    
    if st.button("Stop"):
        response = requests.get(f"{ESP32_IP}/stop")
        if response.status_code == 303:
            st.error("Failed to stop dispensing")
        else:
            st.success("Dispensing stopped...")
            st.session_state['dispensing'] = False
            
            # Calculate total volume and bill
            end_time = datetime.now()
            duration = (end_time - st.session_state['start_time']).total_seconds()
            total_volume = st.session_state['total_volume']  # You need to fetch this from your sensor
            price_per_liter, tank_size = fetch_master_data()
            total_bill = total_volume * price_per_liter
            
            # Save to history
            history_data = {
                "timestamp": end_time,
                "total_volume": total_volume,
                "bill": total_bill
            }
            history_collection.insert_one(history_data)
            st.success(f"Dispensing data saved: {total_volume} L, {total_bill} IDR")

# Track total volume dispensed during dispensing
def track_volume():
    if st.session_state.get('dispensing', False):
        response = requests.get(f"{ESP32_IP}/getVolume")
        if response.status_code == 200:
            current_volume = response.json().get('volume', 0.0)
            st.session_state['total_volume'] = current_volume
        else:
            st.error("Failed to get volume data")
# Activity page
def activity_page():
    st.title("Manage Activities")
    st.write("## Add New Activity")
    activity_name = st.text_input("Activity Name")
    activity_water_amount = st.number_input("Activity Water Amount (L)", min_value=0, step=1, value=0)

    if st.button("Add Activity"):
        if activity_name and activity_water_amount > 0:
            activity_data = {
                "name": activity_name,
                "amount(L)": activity_water_amount
            }
            activity_collection.insert_one(activity_data)
            st.success(f"Activity '{activity_name}' added with {activity_water_amount} L")
        else:
            st.warning("Please provide both activity name and water amount.")
    
    st.write("## Activity List")
    activities = pd.DataFrame(list(activity_collection.find({}, {"_id": 0})))
    
    if not activities.empty:
        st.table(activities)
        
        st.write("## Edit/Delete Activity")
        activity_to_edit = st.selectbox("Select Activity to Edit/Delete", options=activities['name'].tolist())
        new_activity_name = st.text_input("New Activity Name", value=activity_to_edit)
        new_activity_amount = st.number_input("New Activity Water Amount (L)", min_value=0, step=1, value=int(activities[activities['name'] == activity_to_edit]['amount(L)'].values[0]))
        
        if st.button("Update Activity"):
            activity_collection.update_one({"name": activity_to_edit}, {"$set": {"name": new_activity_name, "amount(L)": new_activity_amount}})
            st.success(f"Activity '{activity_to_edit}' updated to '{new_activity_name}' with {new_activity_amount} L")
        
        if st.button("Delete Activity"):
            activity_collection.delete_one({"name": activity_to_edit})
            st.success(f"Activity '{activity_to_edit}' deleted")

# Chatbot page
def chatbot_page():
    st.title("Water Usage Consultation - Chatbot")
    
    # Initialize session state for chatbot
    if 'messages' not in st.session_state:
        st.session_state.messages = []

    user_input = st.text_input("You: ", key="input")
    
    if user_input:
        st.session_state.messages.append({"role": "user", "content": user_input})
        
        # Define typical water usage for activities
        water_usage = {
            "cuci tangan": 2,
            "cuci piring": 15,
            "menyiram tanaman": 10,
            "cuci mobil": 150,
            "memasak": 5,
            "mencuci baju": 50,
            "membersihkan lantai": 20,
            "mengisi kolam renang": 1000,
            "cuci motor": 50,
            "membersihkan kaca": 5,
            "mencuci peralatan makan": 10,
            "mandi" : 20
            
        }
        
        # Bot response logic
        bot_response = "Maaf, saya tidak mengerti. Coba jelaskan aktivitas Anda."
        for activity, usage in water_usage.items():
            if activity in user_input.lower():
                bot_response = f"Untuk {activity}, biasanya diperlukan sekitar {usage} liter air."
                break
        
        st.session_state.messages.append({"role": "bot", "content": bot_response})

    # Display messages
    for message in st.session_state.messages:
        if message["role"] == "user":
            st.write(f"You: {message['content']}")
        else:
            st.write(f"Bot: {message['content']}")

# Streamlit app setup
st.sidebar.title("Navigation")
page = st.sidebar.radio("Go to", ["Dashboard", "History", "Master Data", "Control", "Activity", "Chatbot"])

if page == "Dashboard":
    dashboard_page()
elif page == "History":
    history_page()
elif page == "Master Data":
    master_data_page()
elif page == "Control":
    control_page()
elif page == "Activity":
    activity_page()
elif page == "Chatbot":
    chatbot_page()
