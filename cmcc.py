import json
import re
from pathlib import Path
from urllib.parse import urlparse, parse_qs

import requests

# 使用Session保持Cookies和连接
session = requests.Session()
# 公共请求头
base_headers = {
    'User-Agent': 'webkit;Resolution(PAL,720P,1080P);Ranger:width=1280&height=720',
    'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,*/*;q=0.8',
    'Accept-Language': 'zh-CN,en-US;q=0.8',
    'X-Requested-With': 'net.sunniwell.app.iptv',
    'Pragma': 'no-cache',
    'Cache-Control': 'no-cache',
    'Upgrade-Insecure-Requests': '1',
}
# 节点的地址
base_url = "http://111.47.124.165:33200"


def validate_authentication():
    post_data = {
        'UserID': 'F7188847284A01',
        'Authenticator': 'A7E9F5F55EF15FC2607852D4FB9B1EE5DF401A3DD25528C196066CCDB42B55A9793CA87AAE7D8CAA7AD39E96EE8BC178867400FFD97D10905F14DC3E4EC6AB78D59278B7DED055FD51D494578FB094B36C7F8132F943B533CBC478FD1E2B66A70EE32940861A5D841837894C73274B774064CA13C9AEDB6DDFE61384FFD05EB137C12FD75EC23261'
    }
    response = session.post(
        f"{base_url}/EPG/jsp/ValidAuthenticationHWCTC.jsp",
        data=post_data,
        headers={
            **base_headers,
            'Origin': base_url,
            'Referer': f"{base_url}/EPG/jsp/authLoginHWCTC.jsp",
            'Content-Type': 'application/x-www-form-urlencoded',
        }
    )
    # 获取并保存 cookies
    cookies_dict = response.cookies.get_dict()
    if cookies_dict:
        cookies_file_path.write_text(json.dumps(cookies_dict))
    # 打印 cookies
    for cookie in cookies:
        print(f'{cookie.name}: {cookie.value}')


def get_channels():
    # 第四步：POST /EPG/jsp/getchannellistHWCTC.jsp
    post_data = {
        'UserID': 'F7188847284A01'
    }
    response = session.post(
        f"{base_url}/EPG/jsp/getchannellistHWCTC.jsp",
        data=post_data,
        headers={
            **base_headers,
            'Origin': base_url,
            'Referer': f"{base_url}/EPG/jsp/ValidAuthenticationHWCTC.jsp",
            'Content-Type': 'application/x-www-form-urlencoded',
        },
        cookies=cookies
    )
    print(f"第四步 POST 响应状态码: {response.status_code}")
    if response.status_code == 200:
        channel_file_path.write_text(response.text, encoding='utf-8-sig')


def read_channels():
    channels = channel_file_path.read_text(encoding='utf-8-sig')
    # 定义正则表达式模式
    pattern = r'ChannelName="([^"]+)",.*?ChannelURL="([^"]+)"'
    match = re.findall(pattern, channels)
    channel_list = []
    for name, url in match:
        channel_list.append(f"{name},{url}")
    channel_list_path.write_text("\n".join(channel_list), encoding='utf-8-sig')


if __name__ == '__main__':
    current_path = Path(__file__).parent
    channel_file_path = current_path.joinpath("channel.txt")
    channel_list_path = current_path.joinpath("iptv", "HBIPTV.txt")
    cookies_file_path = current_path.joinpath("cookies.json")
    cookies = json.loads(cookies_file_path.read_text())
    # validate_authentication(session, base_url, base_headers)
    get_channels()
    read_channels()
