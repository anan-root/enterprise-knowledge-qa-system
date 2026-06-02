import requests
def get_city_by_ip(ip: str):
    if ip in ['127.0.0.1', 'localhost']:
        return "本地测试"

    try:
        res = requests.get(f'https://ipapi.co/{ip}/json/', timeout=3)
        data = res.json()
        return {
            'city': data.get('city'),
            'region': data.get('region'),
            'country': data.get('country_name'),
        }
    except:
        return {'未检测到用户所在地'}


if __name__ == '__main__':
    # 获取本机公网 IP
    my_ip = requests.get('https://ifconfig.me', timeout=5).text.strip()
    print(f"公网 IP: {my_ip}")

    # 查询信息
    info = get_city_by_ip(my_ip)
    print(info)