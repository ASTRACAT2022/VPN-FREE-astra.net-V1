import pybase64
import requests
import binascii
import os
import yaml
import geoip2.database
from urllib.parse import urlparse, parse_qs

TIMEOUT = 20

# Карта эмодзи флагов
COUNTRY_FLAGS = {
    "CA": "🇨🇦", "US": "🇺🇸", "RU": "🇷🇺", "GB": "🇬🇧", "DE": "🇩🇪", "FR": "🇫🇷",
    "CN": "🇨🇳", "JP": "🇯🇵", "KR": "🇰🇷", "BR": "🇧🇷", "AU": "🇦🇺", "IN": "🇮🇳"
}

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
                print(f"Успешно декодировано: {link}")
            else:
                print(f"Нет данных: {link}")
        except requests.RequestException as e:
            print(f"Ошибка загрузки {link}: {e}")
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
                print(f"Успешно загружено: {link}")
            else:
                print(f"Нет данных: {link}")
        except requests.RequestException as e:
            print(f"Ошибка загрузки {link}: {e}")
    return decoded_dir_links

def get_country_emoji(ip):
    try:
        reader = geoip2.database.Reader('website/GeoLite2-Country.mmdb')
        response = reader.country(ip)
        country_code = response.country.iso_code
        return COUNTRY_FLAGS.get(country_code, "🌍")
    except Exception as e:
        print(f"Ошибка GeoIP для {ip}: {e}")
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
    except Exception as e:
        print(f"Ошибка парсинга VLess URL {vless_url}: {e}")
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
            print(f"Добавлен прокси: {proxy['name']}")
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
    for item in data:
        lines = item.splitlines()
        for line in lines:
            if "vless" in line:
                vless_configs.append(line)
    print(f"Найдено {len(vless_configs)} VLess-конфигураций")
    return vless_configs

def ensure_directories_exist():
    output_folder = os.path.abspath("./configs")
    if not os.path.exists(output_folder):
        os.makedirs(output_folder)
        print(f"Создана папка: {output_folder}")
    else:
        print(f"Папка существует: {output_folder}")
    return output_folder

def process_raw_configs():
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
    vless_configs = filter_vless(combined_data)

    # Сохранить YAML
    yaml_config = format_vless_yaml(vless_configs)
    output_filename = os.path.join(output_folder, "raw_configs.yaml")
    if os.path.exists(output_filename):
        os.remove(output_filename)
        print(f"Удален старый файл: {output_filename}")
    with open(output_filename, "w") as f:
        yaml.dump(yaml_config, f, allow_unicode=True, sort_keys=False)
    print(f"Сохранен YAML в {output_filename}")

if __name__ == "__main__":
    process_raw_configs()
    print("Генерация сырого конфига завершена")
