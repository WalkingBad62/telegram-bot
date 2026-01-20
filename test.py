import requests
token = "8316979565:AAHqIOE5TR51qGLic5Y6XQ_wh9S_6xybiS4"
url = f"https://api.telegram.org/bot{token}/getMe"
print(requests.get(url).text)
