import tkinter as tk
from tkinter import messagebox
import requests
from requests.auth import HTTPBasicAuth
import datetime
import time

# --- Meteomatics API credentials ---
USERNAME = "college_ks_shreelakshmi"
PASSWORD = "8Lh3U6i5HjxwF7yr22i2"

# --- Updated emoji + condition mapping (Meteomatics extended) ---
WEATHER_EMOJIS = {
    100: "☀️", 101: "🌙",
    102: "🌤", 103: "🌤",
    104: "🌤", 105: "☁️",
    106: "☁️", 107: "🌫",
    108: "🌦", 109: "🌧", 110: "🌧",
    111: "⛈", 112: "🌨", 113: "❄️",
    114: "❄️", 115: "🌧",
    116: "🌨", 117: "🌨", 118: "🌦", 119: "🌧❄️"
}

WEATHER_MAP = {
    100: "Clear Sky (Day)", 101: "Clear Sky (Night)",
    102: "Mainly Clear (Day)", 103: "Mainly Clear (Night)",
    104: "Partly Cloudy (Day)", 105: "Partly Cloudy (Night)",
    106: "Overcast", 107: "Fog",
    108: "Light Rain Showers", 109: "Moderate Rain Showers",
    110: "Heavy Rain Showers", 111: "Thunderstorm",
    112: "Light Snow Showers", 113: "Moderate Snow Showers",
    114: "Heavy Snow Showers", 115: "Rain",
    116: "Snow", 117: "Sleet", 118: "Drizzle", 119: "Freezing Rain"
}

# --- Background colors ---
BACKGROUND_COLORS = {
    "Clear Sky (Day)": "#87ceeb",
    "Clear Sky (Night)": "#2c3e50",
    "Mainly Clear (Day)": "#b0c4de",
    "Mainly Clear (Night)": "#34495e",
    "Partly Cloudy (Day)": "#d3d3d3",
    "Partly Cloudy (Night)": "#708090",
    "Overcast": "#a9a9a9",
    "Fog": "#c0c0c0",
    "Light Rain Showers": "#5f9ea0",
    "Moderate Rain Showers": "#4682b4",
    "Heavy Rain Showers": "#4169e1",
    "Thunderstorm": "#778899",
    "Light Snow Showers": "#f0f8ff",
    "Moderate Snow Showers": "#e0ffff",
    "Heavy Snow Showers": "#b0e0e6",
    "Rain": "#00ced1",
    "Snow": "#f0ffff",
    "Sleet": "#e6e6fa",
    "Drizzle": "#87cefa",
    "Freezing Rain": "#b0c4de",
    "Unknown": "#87ceeb"
}

# --- Helper: try Open-Meteo geocoding first, fallback to Nominatim ---
def get_coordinates(city):
    # try Open-Meteo geocoding
    try:
        params = {"name": city, "count": 1}
        resp = requests.get("https://geocoding-api.open-meteo.com/v1/search", params=params, timeout=6)
        data = resp.json()
        if "results" in data and len(data["results"]) > 0:
            r = data["results"][0]
            return r["latitude"], r["longitude"], f"{r.get('name','')}, {r.get('country','')}"
    except Exception as e:
        print("Open-Meteo geocoding error:", e)

    # fallback: Nominatim (OpenStreetMap)
    try:
        headers = {"User-Agent": "weather-app-example/1.0 (+https://example.com)"}
        params = {"q": city, "format": "json", "limit": 1}
        resp = requests.get("https://nominatim.openstreetmap.org/search", params=params, headers=headers, timeout=6)
        results = resp.json()
        if results:
            r = results[0]
            lat = float(r["lat"])
            lon = float(r["lon"])
            display = r.get("display_name", city)
            return lat, lon, display
    except Exception as e:
        print("Nominatim geocoding error:", e)

    messagebox.showerror("Error", f"City not found: {city}")
    return None

# --- Helper: round down to hour string 'YYYY-MM-DDTHH:00:00Z' ---
def utc_hour_string(dt=None):
    if dt is None:
        dt = datetime.datetime.utcnow()
    dt = dt.replace(minute=0, second=0, microsecond=0)
    return dt.strftime("%Y-%m-%dT%H:%M:%SZ")

# --- Fetch weather with robust timestamp and symbol lookup ---
def fetch_weather(lat, lon):
    # try current hour, then fallback to previous hour if no usable data
    attempt_times = []
    now = datetime.datetime.utcnow().replace(minute=0, second=0, microsecond=0)
    attempt_times.append(now)
    attempt_times.append(now - datetime.timedelta(hours=1))

    last_err = None
    for dt in attempt_times:
        time_str = dt.strftime("%Y-%m-%dT%H:%M:%SZ")
        url = f"https://api.meteomatics.com/{time_str}/t_2m:C,relative_humidity_2m:p,wind_speed_10m:ms,weather_symbol_1h:idx/{lat},{lon}/json"
        try:
            resp = requests.get(url, auth=HTTPBasicAuth(USERNAME, PASSWORD), timeout=8)
            data = resp.json()

            # Basic safety checks
            if "data" not in data or not isinstance(data["data"], list) or len(data["data"]) < 1:
                last_err = "No data array in response"
                continue

            # temp/humidity/wind extraction (best-effort)
            def extract_param_by_index(i):
                try:
                    return data["data"][i]["coordinates"][0]["dates"][0]["value"]
                except Exception:
                    return None

            temp = extract_param_by_index(0)
            humidity = extract_param_by_index(1)
            wind = extract_param_by_index(2)

            # Attempt to get weather symbol robustly:
            raw_symbol = None
            # 1) fastest: common index 3
            if len(data["data"]) > 3:
                try:
                    raw_symbol = data["data"][3]["coordinates"][0]["dates"][0]["value"]
                except Exception:
                    raw_symbol = None

            # 2) fallback: search entries for plausible symbol (0-199 or 100-199)
            if raw_symbol is None:
                for entry in data["data"]:
                    try:
                        val = entry["coordinates"][0]["dates"][0]["value"]
                        # plausible meteorological symbol is an int/float in reasonable ranges
                        if isinstance(val, (int, float)) and (0 <= float(val) <= 999):
                            # check if matches known symbol ranges (0-119 or 100-119)
                            if (0 <= int(round(float(val))) <= 119) or (100 <= int(round(float(val))) <= 199):
                                raw_symbol = val
                                break
                    except Exception:
                        continue

            if raw_symbol is None:
                last_err = "No weather symbol found in response"
                continue

            # debug prints
            print("Using timestamp:", time_str, "raw_symbol:", raw_symbol, type(raw_symbol))

            # safe conversion
            try:
                symbol = int(round(float(raw_symbol)))
            except Exception:
                symbol = None

            # condition mapping
            condition = WEATHER_MAP.get(symbol, "Unknown")
            if condition == "Unknown":
                print("⚠️ New or unmapped symbol detected:", symbol)

            return temp, humidity, wind, condition, symbol

        except Exception as e:
            print("Fetch attempt error:", e)
            last_err = str(e)
            time.sleep(0.3)  # small pause before fallback attempt
            continue

    messagebox.showerror("Error", f"Failed to fetch weather. Last error: {last_err}")
    return None

# --- GUI App ---
class WeatherApp:
    def __init__(self, root):
        self.root = root
        self.root.title("🌦️ Weather App")
        self.root.geometry("500x560")
        self.root.resizable(False, False)
        self.city_var = tk.StringVar()

        # Header
        header = tk.Label(root, text="🌦️ Weather App", font=("Helvetica", 20, "bold"))
        header.pack(pady=10)

        # City input
        frame = tk.Frame(root)
        frame.pack(pady=10)
        tk.Entry(frame, textvariable=self.city_var, font=("Helvetica", 14), width=20).pack(side=tk.LEFT, padx=5)
        tk.Button(frame, text="Get Weather", font=("Helvetica", 12), command=self.get_weather).pack(side=tk.LEFT)

        # Weather frame
        self.weather_frame = tk.Frame(root)
        self.weather_frame.pack(pady=20)

        self.city_label = tk.Label(self.weather_frame, text="", font=("Helvetica", 16, "bold"))
        self.city_label.pack(pady=5)

        self.temp_label = tk.Label(self.weather_frame, text="", font=("Helvetica", 14))
        self.temp_label.pack(pady=5)

        self.humidity_label = tk.Label(self.weather_frame, text="", font=("Helvetica", 14))
        self.humidity_label.pack(pady=5)

        self.wind_label = tk.Label(self.weather_frame, text="", font=("Helvetica", 14))
        self.wind_label.pack(pady=5)

        # Clean weather display (big emoji + small condition text)
        self.weather_emoji_label = tk.Label(self.weather_frame, text="", font=("Helvetica", 60))
        self.weather_emoji_label.pack(pady=(20, 0))

        self.weather_text_label = tk.Label(self.weather_frame, text="", font=("Helvetica", 14, "bold"))
        self.weather_text_label.pack(pady=(5, 20))

        # Auto-refresh every 60 seconds
        self.root.after(60000, self.auto_refresh)

    def get_weather(self):
        city = self.city_var.get().strip()
        if city == "":
            messagebox.showwarning("Input Error", "Please enter a city name.")
            return

        coords = get_coordinates(city)
        if not coords:
            return
        lat, lon, city_name = coords
        weather = fetch_weather(lat, lon)
        if not weather:
            return
        temp, humidity, wind, condition, symbol = weather

        # Update labels
        self.city_label.config(text=city_name)
        self.temp_label.config(text=f"🌡️ Temperature: {temp} °C", fg="#ff4500")
        self.humidity_label.config(text=f"💧 Humidity: {humidity} %", fg="#1e90ff")
        self.wind_label.config(text=f"💨 Wind Speed: {wind} m/s", fg="#555555")

        # Separate emoji and text (clean look)
        emoji = WEATHER_EMOJIS.get(symbol, "❓")
        self.weather_emoji_label.config(text=emoji)
        self.weather_text_label.config(text=condition)

        # Background color
        bg_color = BACKGROUND_COLORS.get(condition, "#87ceeb")
        self.root.configure(bg=bg_color)
        self.weather_frame.configure(bg=bg_color)

        # Apply bg to all labels
        for lbl in [self.city_label, self.temp_label, self.humidity_label,
                    self.wind_label, self.weather_emoji_label, self.weather_text_label]:
            lbl.configure(bg=bg_color)

    def auto_refresh(self):
        if self.city_var.get().strip() != "":
            self.get_weather()
        self.root.after(60000, self.auto_refresh)

# --- Run App ---
if __name__ == "__main__":
    root = tk.Tk()
    app = WeatherApp(root)
    root.mainloop()
