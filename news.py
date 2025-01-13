import requests
import json

API_KEY = "pub_652377e6fa74ef3c46089bbc855cb020d2769"  # Замените на ваш реальный API ключ
BASE_URL = "https://newsdata.io/api/1/news"

params = {
    "apiKey": API_KEY,
    # Дополнительные параметры (необязательно)
    # "language": "ru",
    # "country": "ru",
    # "category": "technology",
}

try:
    response = requests.get(BASE_URL, params=params)
    response.raise_for_status()  # Вызовет исключение в случае ошибки HTTP

    data = response.json()

    if data["status"] == "success":
        for article in data["results"]:
            print(f"Заголовок: {article.get('title')}")
            print(f"URL: {article.get('link')}")
            print(f"Источник: {article.get('source_id')}")
            print("-" * 20)
    else:
        print(f"Ошибка при получении новостей: {data.get('message')}")

except requests.exceptions.RequestException as e:
    print(f"Ошибка подключения: {e}")
except json.JSONDecodeError:
    print("Ошибка декодирования JSON ответа.")