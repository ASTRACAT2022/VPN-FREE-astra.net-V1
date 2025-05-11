from fastapi import FastAPI, Request
from fastapi.responses import HTMLResponse
import pybase64
import requests
import binascii
import os
import json
import yaml
import geoip2.database
from jinja2 import Environment, BaseLoader
from urllib.parse import urlparse, parse_qs

app = FastAPI()

# HTML-шаблон
INDEX_HTML = """
<!DOCTYPE html>
<html lang="ru">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>ASTRACAT ShereVPN</title>
    <script src="https://cdn.tailwindcss.com"></script>
    <!-- Yandex.Metrika counter -->
    <script type="text/javascript" >
       (function(m,e,t,r,i,k,a){m[i]=m[i]||function(){(m[i].a=m[i].a||[]).push(arguments)};
       m[i].l=1*new Date();
       for (var j = 0; j < document.scripts.length; j++) {if (document.scripts[j].src === r) { return; }}
       k=e.createElement(t),a=e.getElementsByTagName(t)[0],k.async=1,k.src=r,a.parentNode.insertBefore(k,a)})
       (window, document, "script", "https://mc.yandex.ru/metrika/tag.js", "ym");

       ym(100530848, "init", {
            clickmap:true,
            trackLinks:true,
            accurateTrackBounce:true,
            webvisor:true
       });
    </script>
    <noscript><div><img src="https://mc.yandex.ru/watch/100530848" style="position:absolute; left:-9999px;" alt="" /></div></noscript>
    <!-- /Yandex.Metrika counter -->
    <style>
        .card {
            transition: transform 0.2s;
        }
        .card:hover {
            transform: scale(1.05);
        }
        #toast {
            display: none;
            position: fixed;
            bottom: 20px;
            right: 20px;
            background-color: #10b981;
            color: white;
            padding: 10px 20px;
            border-radius: 5px;
            z-index: 1000;
        }
    </style>
    <script>
        function filterStats() {
            const protocol = document.getElementById('protocol').value;
            window.location.href = `/?protocol=${protocol}`;
        }
        function copyLink() {
            const url = window.location.origin + '/public/configs/vless_configs.yaml';
            navigator.clipboard.writeText(url).then(() => {
                const toast = document.getElementById('toast');
                toast.style.display = 'block';
                setTimeout(() => { toast.style.display = 'none'; }, 2000);
            });
        }
    </script>
</head>
<body class="bg-gray-900 text-white">
    <header class="bg-gray-800 p-4 shadow-md">
        <nav class="container mx-auto flex justify-between items-center">
            <h1 class="text-2xl font-bold">ASTRACAT ShereVPN</h1>
            <ul class="flex space-x-4">
                <li><a href="/" class="hover:text-blue-400">Главная</a></li>
                <li><a href="https://github.com/ASTRACAT2022/apiV2ray" class="hover:text-blue-400">GitHub</a></li>
            </ul>
        </nav>
    </header>
    <main class="container mx-auto p-4">
        <h1 class="text-4xl font-bold text-center mb-8">ASTRACAT ShereVPN</h1>
        <p class="text-center mb-8">Бесплатные VLess-конфигурации с актуальной статистикой</p>
        <div class="mb-8 text-center">
            <label for="protocol" class="mr-2">Выберите протокол:</label>
            <select id="protocol" onchange="filterStats()" class="bg-gray-800 text-white p-2 rounded">
                {% for proto in protocols %}
                    <option value="{{ proto }}" {% if proto == selected_protocol %}selected{% endif %}>
                        {{ proto|capitalize }}
                    </option>
                {% endfor %}
            </select>
        </div>
        <div class="grid grid-cols-1 md:grid-cols-3 gap-4">
            {% for protocol, count in stats.items() %}
                <div class="bg-gray-800 p-4 rounded-lg shadow-lg card">
                    <h2 class="text-xl font-semibold">{{ protocol|upper }}</h2>
                    <p class="text-2xl">{{ count }} конфигураций</p>
                </div>
            {% endfor %}
        </div>
        <div class="text-center mt-8">
            <button onclick="copyLink()" class="bg-blue-600 hover:bg-blue-700 text-white font-bold py-2 px-4 rounded">
                Копировать ссылку
            </button>
        </div>
        <div id="toast">Ссылка скопирована!</div>
    </main>
    <footer class="bg-gray-800 p-4 mt-8 text-center">
        <p>Создано <a href="https://github.com/ASTRACAT2022/apiV2ray" class="text-blue-400">ASTRACAT2022</a></p>
        <p>Telegram: <a href="https://t.me/astracatui" class="text-blue-400">@astracatui</a></p>
    </footer>
</body>
</html>
"""

# Jinja2 окружение
env = Environment(loader=BaseLoader())
template = env.from_string(INDEX_HTML)

# Конфигурация
TIMEOUT = 20
fixed_text = """#profile-title: base64:8J+agCBBU1RSQUNBVCBTaGVyZVZQTiDwn6W3
#profile-update-interval: 1
#subscription-userinfo: upload=29; download=12; total=10737418240000000; expire=2546249531
#support-url: https://github.com/ASTRACAT2022/apiV2ray
#profile-web-page-url: https://github.com/ASTRACAT2022/apiV2ray
"""

# Карта эмодзи флагов по коду страны
COUNTRY_FLAGS = {
    "CA": "🇨🇦", "US": "🇺🇸", "RU": "🇷🇺", "GB": "🇬🇧", "DE": "🇩🇪", "FR": "🇫🇷",
    "CN": "🇨🇳", "JP": "🇯🇵", "KR": "🇰🇷", "BR": "🇧🇷", "AU": "🇦🇺", "IN": "🇮🇳"
}

# Функции обработки конфигураций
def decode_base64(encoded):
    decoded = ""
    for encoding in ["utf-8", "iso-8859-1"]:
        try:
            decoded = pybase64.b64decode(encoded + b"=" * (-len(encoded) % 4)).decode(encoding)
            break
        except (UnicodeDecodeError, binascii.Error):
            pass
    return decoded

def decode_links(links):
    decoded_data = []
    for link in links:
        try:
            response = requests.get(link, timeout=TIMEOUT)
            response.raise_for_status()
            encoded_bytes = response.content
            decoded_text = decode_base64(encoded_bytes)
            if decoded_text:
                decoded_data.append(decoded_text)
        except requests.RequestException as e:
            print(f"Failed to fetch {link}: {e}")
    return decoded_data

def decode_dir_links(dir_links):
    decoded_dir_links = []
    for link in dir_links:
        try:
            response = requests.get(link, timeout=TIMEOUT)
            response.raise_for_status()
            decoded_text = response.text
            if decoded_text:
                decoded_dir_links.append(decoded_text)
        except requests.RequestException as e:
            print(f"Failed to fetch {link}: {e}")
    return decoded_dir_links

def get_country_emoji(ip):
    try:
        reader = geoip2.database.Reader('GeoLite2-Country.mmdb')
        response = reader.country(ip)
        country_code = response.country.iso_code
        return COUNTRY_FLAGS.get(country_code, "🌍")
    except Exception:
        return "🌍"

def parse_vless_url(vless_url):
    try:
        parsed = urlparse(vless_url)
        if parsed.scheme != "vless":
            return None
        user_info = parsed.netloc.split("@")
        if len(user_info) != 2:
            return None
        uuid = user_info[0]
        host_port = user_info[1].split(":")
        if len(host_port) != 2:
            return None
        host, port = host_port
        query = parse_qs(parsed.query)
        return {
            "uuid": uuid,
            "host": host,
            "port": port,
            "params": query,
            "fragment": parsed.fragment
        }
    except Exception:
        return None

def format_vless_yaml(vless_configs):
    proxies = []
    for index, config in enumerate(vless_configs, 1):
        parsed = parse_vless_url(config)
        if parsed:
            country_emoji = get_country_emoji(parsed["host"])
            proxy = {
                "name": f"{country_emoji} ASTRACAT-Tunels-{index}",
                "type": "vless",
                "server": parsed["host"],
                "port": int(parsed["port"]),
                "uuid": parsed["uuid"],
                "cipher": "none",
                "tls": "security" in parsed["params"] and parsed["params"]["security"][0] == "tls",
                "network": parsed["params"].get("type", ["tcp"])[0]
            }
            if proxy["network"] == "ws":
                ws_opts = {"path": parsed["params"].get("path", ["/"])[0]}
                if "host" in parsed["params"]:
                    ws_opts["headers"] = {"Host": parsed["params"]["host"][0]}
                proxy["ws-opts"] = ws_opts
                if proxy["tls"]:
                    proxy["servername"] = parsed["params"].get("sni", [parsed["host"]])[0]
            proxies.append(proxy)
    
    proxy_names = [proxy["name"] for proxy in proxies]
    yaml_config = {
        "port": 7890,
        "socks-port": 7891,
        "allow-lan": False,
        "mode": "rule",
        "log-level": "info",
        "external-controller": "127.0.0.1:9090",
        "proxies": proxies,
        "proxy-groups": [
            {
                "name": "🚀 ASTRACAT-Tunels-Group",
                "type": "select",
                "proxies": proxy_names
            }
        ],
        "rules": ["MATCH,🚀 ASTRACAT-Tunels-Group"],
        "dns": {
            "enable": True,
            "ipv6": False,
            "nameserver": ["85.209.2.112"]
        }
    }
    return yaml_config

def filter_vless(data):
    vless_configs = []
    stats = {"vless": 0}
    for item in data:
        lines = item.splitlines()
        for line in lines:
            if "vless" in line:
                vless_configs.append(line)
                stats["vless"] += 1
    return vless_configs, stats

def ensure_directories_exist():
    output_folder = os.path.abspath("./public/configs")
    if not os.path.exists(output_folder):
        os.makedirs(output_folder)
    return output_folder

def process_configs():
    output_folder = ensure_directories_exist()
    links = [
        "https://raw.githubusercontent.com/barry-far/V2ray-Configs/main/All_Configs_Sub.txt",
        "https://raw.githubusercontent.com/yebekhe/TVC/main/subscriptions/xray/base64/mix",
        "https://raw.githubusercontent.com/ALIILAPRO/v2rayNG-Config/main/sub.txt",
        "https://raw.githubusercontent.com/mfuu/v2ray/master/v2ray",
        "https://raw.githubusercontent.com/aiboboxx/v2rayfree/main/v2",
    ]
    dir_links = [
        "https://raw.githubusercontent.com/itsyebekhe/HiN-VPN/main/subscription/normal/mix",
        "https://raw.githubusercontent.com/sarinaesmailzadeh/V2Hub/main/merged",
        "https://raw.githubusercontent.com/freev2rayconfig/V2RAY_SUBSCRIPTION_LINK/main/v2rayconfigs.txt",
        "https://raw.githubusercontent.com/Everyday-VPN/Everyday-VPN/main/subscription/main.txt",
    ]

    decoded_links = decode_links(links)
    decoded_dir_links = decode_dir_links(dir_links)
    combined_data = decoded_links + decoded_dir_links
    vless_configs, stats = filter_vless(combined_data)

    # Save VLess configs as text
    output_filename = os.path.join(output_folder, "All_Configs_Sub.txt")
    if os.path.exists(output_filename):
        os.remove(output_filename)
    with open(output_filename, "w") as f:
        f.write(fixed_text)
        for config in vless_configs:
            f.write(config + "\n")

    # Save VLess configs as YAML
    yaml_config = format_vless_yaml(vless_configs)
    vless_yaml_file = os.path.join(output_folder, "vless_configs.yaml")
    with open(vless_yaml_file, "w") as f:
        yaml.dump(yaml_config, f, allow_unicode=True, sort_keys=False)

    # Save stats
    stats_file = os.path.join(output_folder, "stats.json")
    with open(stats_file, "w") as f:
        json.dump(stats, f, indent=2)

    return stats

# Загрузка статистики
def load_stats():
    stats_file = "public/configs/stats.json"
    if os.path.exists(stats_file):
        with open(stats_file, "r") as f:
            return json.load(f)
    return process_configs()

# FastAPI маршруты
@app.get("/", response_class=HTMLResponse)
async def index(request: Request, protocol: str = None):
    stats = load_stats()
    protocols = ["all", "vless"]
    filtered_stats = stats if protocol is None or protocol == "all" else {protocol: stats.get(protocol, 0)}
    html_content = template.render(
        stats=filtered_stats,
        protocols=protocols,
        selected_protocol=protocol or "all"
    )
    return HTMLResponse(content=html_content)

@app.get("/api/stats")
async def stats_api():
    return load_stats()

@app.get("/public/configs/{filename}")
async def serve_configs(filename: str):
    file_path = os.path.join("public/configs", filename)
    if os.path.exists(file_path):
        with open(file_path, "r") as f:
            content = f.read()
        return HTMLResponse(content=content, media_type="text/yaml" if filename.endswith(".yaml") else "text/plain")
    return {"error": "File not found"}, 404

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)
