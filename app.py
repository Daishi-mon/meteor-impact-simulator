import os
import json
import requests
from flask import Flask, jsonify, request
from flask_cors import CORS
import numpy as np
from flask import send_from_directory



# Optional: use dotenv if available
try:
    from dotenv import load_dotenv, set_key
    load_dotenv()
    HAS_DOTENV = True
except ImportError:
    HAS_DOTENV = False

# =====================================================
# 🌍 Flask setup
# =====================================================
app = Flask(__name__)
CORS(app, resources={r"/*": {"origins": "*"}}, supports_credentials=True)

@app.route("/<path:path>")
def serve_static(path):
    return send_from_directory("static", path)

NASA_API_KEY = os.getenv("NASA_API_KEY")

if not NASA_API_KEY:
    print("\n⚠️  NASA_API_KEY not found in your environment.")
    NASA_API_KEY = input("🔑 Please enter your NASA API key: ").strip()

    if not NASA_API_KEY:
        raise RuntimeError("❌ No API key provided. Exiting.")

    # Optionally save it for next time
    if HAS_DOTENV:
        env_path = ".env"
        set_key(env_path, "NASA_API_KEY", NASA_API_KEY)
        print(f"✅ Saved NASA_API_KEY to {env_path}")
    else:
        print("ℹ️  Install python-dotenv if you want to auto-save keys next time (pip install python-dotenv).")

IMPACT_FILE = "impacts.json"  # store user-simulated impacts

# =====================================================
# 🧩 API Index
# =====================================================
@app.route("/", methods=["GET"])
def index():
    """List all available API routes and their purpose."""
    routes = {
        "/": "API index - lists all routes and their purpose.",
        "/get_impacts": "GET historical + user-simulated impacts.",
        "/simulate_impact": "POST: Simulate an asteroid impact and save it.",
        "/nasa_asteroids": "GET: Fetch live asteroid data from NASA’s NEO API.",
        "/delete_impact/<id>": "DELETE: Remove a saved simulation by ID.",
    }
    return jsonify({
        "api_name": "🌌 Asteroid Impact Simulation API",
        "description": "Simulate asteroid impacts, view NASA asteroid data, and manage saved simulations.",
        "routes": routes
    })


# =====================================================
# 🧠 Data Management (Load / Save)
# =====================================================
def load_impacts():
    if os.path.exists(IMPACT_FILE):
        with open(IMPACT_FILE, "r") as f:
            try:
                return json.load(f)
            except json.JSONDecodeError:
                return []
    return []

def save_impact(impact):
    impacts = load_impacts()
    impacts.append(impact)
    with open(IMPACT_FILE, "w") as f:
        json.dump(impacts, f, indent=2)


# =====================================================
# 🌋 Historical Impact Data
# =====================================================
HISTORICAL_IMPACTS = [
    {"id": "chicxulub", "name": "Chicxulub (66Mya)", "size": 10, "speed": 20, "lat": 21.4, "lon": -89.0},
    {"id": "tunguska", "name": "Tunguska (1908)", "size": 0.05, "speed": 16, "lat": 60.9, "lon": 101.9},
    {"id": "chelyabinsk", "name": "Chelyabinsk (2013)", "size": 0.02, "speed": 19, "lat": 54.9, "lon": 61.1},
]


@app.route("/get_impacts", methods=["GET"])
def get_impacts():
    """Return both historical and user-simulated impacts"""
    simulated = load_impacts()
    combined = HISTORICAL_IMPACTS + simulated
    return jsonify(combined)


# =====================================================
# 💥 Hazard Calculations
# =====================================================
def asteroid_kinetic_energy(diameter_m, velocity_km_s, density=3000):
    radius = diameter_m / 2
    volume = 4 / 3 * np.pi * radius ** 3
    mass = density * volume
    velocity = velocity_km_s * 1000
    energy_joules = 0.5 * mass * velocity ** 2
    return energy_joules / 4.184e15  # megatons


def impact_radius_km(megatons):
    return 1.5 * (megatons) ** (1 / 3)


def population_affected(pop_density_per_km2, radius_km):
    area_km2 = np.pi * radius_km ** 2
    return int(area_km2 * pop_density_per_km2)


def impact_earthquake_magnitude(megatons):
    E_joules = megatons * 4.184e15
    magnitude = 0.67 * np.log10(E_joules) - 10.7
    return round(max(0, magnitude), 1)


# =====================================================
# ☄️ NASA NEO API Integration
# =====================================================
@app.route("/nasa_asteroids", methods=["GET"])
def get_nasa_asteroids():
    """Fetches asteroid dataset from NASA NEO API"""
    url = f"https://api.nasa.gov/neo/rest/v1/neo/browse?api_key={NASA_API_KEY}"
    try:
        resp = requests.get(url)
        resp.raise_for_status()
        data = resp.json()
        asteroids = []
        for neo in data["near_earth_objects"]:
            est_diam = neo["estimated_diameter"]["meters"]["estimated_diameter_max"]
            rel_vel = (
                float(neo["close_approach_data"][0]["relative_velocity"]["kilometers_per_second"])
                if neo["close_approach_data"]
                else 20
            )
            asteroids.append({
                "id": neo["id"],
                "name": neo["name"],
                "diameter_m": round(est_diam, 2),
                "velocity_km_s": round(rel_vel, 2),
                "hazardous": neo["is_potentially_hazardous_asteroid"]
            })
        return jsonify({"count": len(asteroids), "asteroids": asteroids})
    except Exception as e:
        print("NASA API error:", e)
        return jsonify({"error": "Failed to fetch from NASA API"}), 500


# =====================================================
# 🌠 Simulate + Save Impact
# =====================================================
@app.route("/simulate_impact", methods=["POST"])
def simulate_impact():
    data = request.json
    diameter = data.get("diameter_m", 50)
    velocity = data.get("velocity_km_s", 20)
    lat = data.get("latitude")
    lon = data.get("longitude")
    pop_density = data.get("pop_density_per_km2", 1000)

    energy_mt = asteroid_kinetic_energy(diameter, velocity)
    radius_km = impact_radius_km(energy_mt)
    population = population_affected(pop_density, radius_km)
    earthquake_mag = impact_earthquake_magnitude(energy_mt)

    result = {
        "id": f"sim_{np.random.randint(10000,99999)}",
        "name": f"Simulated Impact ({round(lat,2)}, {round(lon,2)})",
        "latitude": lat,
        "longitude": lon,
        "diameter_m": diameter,
        "velocity_km_s": velocity,
        "energy_megatons": round(energy_mt, 2),
        "impact_radius_km": round(radius_km, 2),
        "population_affected": population,
        "earthquake_magnitude": earthquake_mag
    }

    save_impact(result)
    return jsonify(result)


# =====================================================
# 🗑️ Delete Impact
# =====================================================
@app.route("/delete_impact/<impact_id>", methods=["DELETE"])
def delete_impact(impact_id):
    """Delete a saved simulation by ID"""
    impacts = load_impacts()
    new_impacts = [i for i in impacts if i["id"] != impact_id]
    if len(new_impacts) == len(impacts):
        return jsonify({"error": "Impact not found"}), 404
    with open(IMPACT_FILE, "w") as f:
        json.dump(new_impacts, f, indent=2)
    return jsonify({"message": f"Impact {impact_id} deleted"})


# =====================================================
# 🚀 Run the app
# =====================================================
if __name__ == "__main__":
    app.run(debug=True)
