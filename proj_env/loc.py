import requests

def get_location(phone_number):
    # Using a free API (may require registration)
    url = f"https://api.geolocation.com/phone/{phone_number}"
    response = requests.get(url)
    
    if response.status_code == 200:
        data = response.json()
        return {
            "latitude": data["lat"],
            "longitude": data["lon"],
            "accuracy": data["accuracy"]
        }
    else:
        raise Exception("Location lookup failed")

# Usage
try:
    loc = get_location("+918551882080")
    print(f"Location: {loc['latitude']}, {loc['longitude']} (±{loc['accuracy']}m)")
except Exception as e:
    print(f"Error: {e}")