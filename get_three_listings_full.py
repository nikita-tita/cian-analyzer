#!/usr/bin/env python3
"""Create mock Cian data that matches expected format"""

import json

# Mock data that would come from parsing
mock_parsed_data = {
    "url": "https://spb.cian.ru/sale/flat/123456/",
    "title": "Продается 3-комн. квартира, 180.4 м²",
    "price": "195 000 000 ₽",
    "price_raw": 195000000,
    "currency": "RUB",
    "description": "Продается потрясающая трехкомнатная квартира с дизайнерским ремонтом и панорамными видами на Неву. Премиальная локация в центре города. Монолитный дом 2022 года постройки. Охрана 24/7, подземная парковка.",
    "address": "Санкт-Петербург, Невский проспект, 100",
    "metro": ["Площадь Восстания • 7 мин"],
    "characteristics": {
        "Общая площадь": "180.4 м²",
        "Жилая площадь": "40 м²",
        "Этаж": "15 из 25",
        "Год постройки": "2022",
        "Тип дома": "монолит",
        "Высота потолков": "3.0 м",
        "Ремонт": "дизайнерский"
    },
    "images": [
        "https://cdn-p.cian.site/images/1.jpg",
        "https://cdn-p.cian.site/images/2.jpg"
    ],
    "seller": {
        "name": "Иван Иванов",
        "type": "Агентство"
    },
    "area": "180.4 м²",
    "floor": "15/25",
    "rooms": "3"
}

print("=== MOCK CIAN DATA ===")
print(json.dumps(mock_parsed_data, ensure_ascii=False, indent=2))
