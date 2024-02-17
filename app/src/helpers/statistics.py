import requests

url = "http://127.0.0.1:5000/statistics"

response = requests.get(url)

if response.status_code == 200:
    try:
        statistics = response.json()
        print("Statistics:")
        print(statistics)
    except Exception as e:
        print(f"An exception occurred: {e}")
else:
    print(f"Failed to retrieve statistics. Status code: {response.status_code}")
    print(response.text)