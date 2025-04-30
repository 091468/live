import socket
from urllib.parse import urlparse


def is_ipv4(address):
    """检查是否是IPv4地址"""
    try:
        socket.inet_pton(socket.AF_INET, address)
        return True
    except (socket.error, ValueError):
        return False


def is_ipv6(address):
    """检查是否是IPv6地址"""
    try:
        socket.inet_pton(socket.AF_INET6, address)
        return True
    except (socket.error, ValueError):
        return False


import re
from urllib.parse import urlparse

def extract_host_from_url(url):
    """从URL中提取主机名/IP部分"""
    # 处理没有协议的URL
    if '://' not in url:
        url = '//' + url

    parsed = urlparse(url)
    hostname = parsed.netloc or parsed.path.split('/')[0]
    #print(f"原始hostname: {hostname}")

    # 使用正则匹配IPv6地址（可能带端口号）
    ipv6_match = re.match(r'^\[([^]]+)\](?::\d+)?$', hostname)
    if ipv6_match:
        hostname = ipv6_match.group(1)  # 提取IPv6地址部分
        print(f"解析后IPv6地址: {hostname}")
        return hostname

    # 处理普通hostname的端口号（兼容IPv4和域名）
    hostname = hostname.split(':', 1)[0]  # 只分割第一个冒号
    print(f"处理后hostname: {hostname}")
    return hostname



def get_dns_info(host):
    """
    获取URL的DNS解析信息

    返回:
        dict: {
            'host': 原始主机名/IP,
            'is_ipv4': bool,
            'is_ipv6': bool,
            'ipv4_addresses': list[str],  # IPv4地址列表
            'ipv6_addresses': list[str],  # IPv6地址列表
            'is_resolvable': bool  # 是否可解析
        }
    """
    result = {
        'hostname': host,
        'is_ipv4': '',
        'is_ipv6': '',
        'ipv4_addresses': "",
        'ipv6_addresses': ""
    }

    # 检查是否是直接IP地址
    if is_ipv4(host):
        result['is_ipv4'] = True
        result['is_ipv6'] = False
        result['ipv4_addresses'] = host
        return result
    if is_ipv6(host):
        result['is_ipv4'] = False
        result['is_ipv6'] = True
        result['ipv6_addresses'] = host
        return result

    # 如果是域名，查询DNS记录
    try:
        # 获取所有地址信息
        addrinfo = socket.getaddrinfo(host, None)
        for info in addrinfo:
            addr = info[4][0]  # 获取IP地址
            if info[0] == socket.AF_INET6:
                if addr not in result['ipv6_addresses']:
                    result['ipv6_addresses'] = addr
            elif info[0] == socket.AF_INET:
                if addr not in result['ipv4_addresses']:
                    result['ipv4_addresses'] = addr
        result['is_ipv4'] = len(result['ipv4_addresses']) > 0
        result['is_ipv6'] = len(result['ipv6_addresses']) > 0
    except socket.gaierror:
        pass  # DNS解析失败
    return result


# 测试示例
if __name__ == "__main__":
    test_cases = [
        "http://39.134.67.108/PLTV/88888888/224/3221225799/1.m3u8",
        "http://quan2018.mycloudnas.com:51888/play/a015/index.m3u8",
        "http://yc.myds.me:35455/gaoma/cctv1.m3u8",
        "http://[2409:8087:1:20:20::2c]/otttv.bj.chinamobile.com/PLTV/88888888/224/3221226458/1.m3u8?GuardEncType=2&accountinfo=%7E%7EV2.0%7Em70vyfVI_MkrcLYjHWnqOA%7E_eNUbgU9sJGUcVVduOMKhafLvQUgE_zlz_7pvDimJNNlS0O1LA8iGydXPYujpRue%2CEND",
        "http://qjrhc.jydjd.top:2911/udp/224.1.100.138:11111",
        "https://gcalic.v.myalicdn.com/gc/zjwzlxt_1/index.m3u8",
    ]
    url = "http://[2409:8087:8:21::16]:6610/otttv.bj.chinamobile.com/PLTV/88888888/224/3221226554/1.m3u8?accountinfo=~~V2.0~N0sbBMpQv4sLsW5foy3YfA~_eNUbgU9sJGUcVVduOMKhafLvQUgE_zlz_7pvDimJNNg3bzRax0E9tLmO9xgXVx8,END&GuardEncType=2&IASHttpSessionId=OTT3037420250428085405471191"
    extract_host_from_url(url)
    exit()
    for url in test_cases:
        info = get_dns_info(url)
        print(f"\nURL: {url}")
        print(f"主机名/IP: {info['host']}")
        print(f"是IPv4: {'是' if info['is_ipv4'] else '否'}")
        if info['is_ipv4']:
            print(f"IPv4地址: {', '.join(info['ipv4_addresses'])}")
        print(f"是IPv6: {'是' if info['is_ipv6'] else '否'}")
        if info['is_ipv6']:
            print(f"IPv6地址: {', '.join(info['ipv6_addresses'])}")
        print(f"可解析: {'是' if info['is_resolvable'] else '否'}")
