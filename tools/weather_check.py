import requests
from pydantic import Field
from configs.setting import TIME_OUT, WEATHER_API_KEY


class WeatherCheck:
    city: str = Field(description="City name, include city and country")

    def __init__(self, api_key):
        self.api_key = api_key

    def run(self, city):
        city = city.split('\n')[0]
        if not self.api_key:
            return "weather check 工具未配置 WEATHER_API_KEY，无法查询天气（请在 .env 中配置）"
        url = f"https://api.seniverse.com/v3/weather/now.json?key={self.api_key}&location={city}&language=zh-Hans&unit=c"
        response = requests.get(url, timeout=TIME_OUT)
        if response.status_code == 200:
            data = response.json()
            Weather = data['results'][0]['now']['text']
            temperature = data['results'][0]['now']['temperature']
            return f"{city}的天气是{Weather},温度为{temperature}摄氏度"
        else:
            return f"错误码：{response.status_code},无法获取{city}的天气信息"


# 密钥来自 .env / 环境变量 WEATHER_API_KEY，不再硬编码在源码里
weather_check = WeatherCheck(WEATHER_API_KEY)
