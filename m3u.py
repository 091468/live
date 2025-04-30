import hashlib
import re
from natsort import index_natsorted
import pandas
import pandas as pd
import requests
from pandas import ExcelWriter
from pathlib import Path
from pd_to_sheet.ip_area import get_ip_area
from pd_to_sheet.to_excel import save_df_to_sheet
from pd_to_sheet.ip2Region import Ip2Region

from config import zibo_pattern
from ipv6 import extract_host_from_url, get_dns_info

headers = {
    "user-agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/112.0.0.0 Safari/537.36"
}

remark_name = {
    "凤凰中文": "凤凰卫视中文台",
    "凤凰资讯": "凤凰卫视资讯台",
    "凤凰香港": "凤凰卫视香港台",
}


def check_logo_file(row):
    ChannelName = row['tvg_name']
    ChannelName = re.sub(r"[|*]", "", ChannelName.strip())
    ChannelLogo = row['ChannelLogo']
    # 检查logo文件是否存在于Web目录，如果存在，则返回文件名，如果不存在，尝试从已有资源中拷贝并返回文件名
    logo_file_path = web_logo_dir_path.joinpath(f"{ChannelLogo}.jpg")
    if not logo_file_path.exists():
        logo_file_path = web_logo_dir_path.joinpath(f"{ChannelLogo}.png")

    if logo_file_path.exists():
        return logo_file_path.name
    else:
        logo_src_file_path = logo_dir_path.joinpath(f"{ChannelName}.jpg")
        print(f"尝试从已有资源中拷贝并返回文件名：{logo_src_file_path}")
        if not logo_src_file_path.exists():
            logo_src_file_path = logo_dir_path.joinpath(f"{ChannelName}.png")
        if logo_src_file_path.exists():

            logo_file_path = web_logo_dir_path.joinpath(f"{ChannelLogo}{logo_src_file_path.suffix}")
            logo_file_path.write_bytes(logo_src_file_path.read_bytes())
            return logo_file_path.name
        else:
            # 通过频道名前缀匹配logo文件
            for current_logo_file_path in logo_dir_path.iterdir():
                if ChannelName.startswith(current_logo_file_path.stem):
                    logo_file_path = web_logo_dir_path.joinpath(f"{ChannelLogo}{current_logo_file_path.suffix}")
                    logo_file_path.write_bytes(current_logo_file_path.read_bytes())
                    return logo_file_path.name
            return "iptv.png"


def save_to_m3u(df):
    new_line_list = [
        '#EXTM3U x-tvg-url="https://gitlab.com/Meroser/My-EPG/-/raw/main/tvxml-Meroser.xml.gz" catchup="append" catchup-source="&st=${(b)yyyyMMddHHmmss}&ed=${(e)yyyyMMddHHmmss}"']
    for index, row in df.iterrows():
        tvg_logo_url = row['ChannelLogoFile']
        tvg_name = row['tvg_name']
        title = row['tvg_name']
        url = row['final_url']
        group_title = row['group_title']
        new_tvg_logo_url = f"https://lichuan.tech/iptv/logo/{tvg_logo_url}"
        # tvg_name = remark_name.get(tvg_name, tvg_name)  # 使用别名
        new_line = f'#EXTINF:-1 tvg-id="" tvg-name="{tvg_name}" tvg-logo="{new_tvg_logo_url}" group-title="{group_title}",{tvg_name}\n{url}'
        new_line_list.append(new_line)
    iptv_dir_path.write_text("\n".join(new_line_list), encoding='utf-8')


def chanel_group(group_dict, chanel_name, group_title):
    for keyword in group_dict.keys():
        if keyword in chanel_name:
            return group_dict[keyword]
    if group_title:
        return group_title
    return group_dict['其他频道']


if __name__ == '__main__':
    src_dir_path = Path("./")
    channel_file_path = src_dir_path.joinpath("iptv_all.xlsx")
    channel_df = pandas.read_excel(channel_file_path, sheet_name="可访问频道", usecols=["tvg_name", "final_url", "group_title"])
    # 过滤掉包含 .mp4 扩展名的 URL
    channel_df.query("not final_url.str.endswith('.mp4', na=False)", inplace=True)
    # 过滤掉包含黑名单中任意一个子字符串的 URL
    channel_df.query(f"not final_url.str.contains('{zibo_pattern}', na=False)", inplace=True)
    channel_df.drop_duplicates(subset=['final_url'], inplace=True, keep='first')
    channel_df['hostname'] = channel_df['final_url'].apply(lambda url: extract_host_from_url(url))
    host_list = channel_df['hostname'].unique().tolist()
    dns_info_list = []
    for host in host_list:
        dns_info = get_dns_info(host)
        # print(dns_info)
        if dns_info is None:
            continue
        dns_info_list.append(dns_info)
    dns_info_df = pandas.DataFrame(dns_info_list)
    channel_df = pandas.merge(channel_df, dns_info_df, on='hostname', how='left')
    channel_df = get_ip_area(channel_df, 'ipv4_addresses')
    #channel_df = get_ip_area(channel_df, 'ipv6_addresses')
    #channel_df.query("ipv4_addresses国家 == '中国' or ipv6_addresses国家 == '中国'", inplace=True)
    #channel_df.query("ipv4_addresses省份 != '香港' and ipv4_addresses省份 != '台湾省'", inplace=True)
    #channel_df.query("ipv6_addresses省份 != '香港区' and ipv6_addresses省份 != '台湾省'", inplace=True)
    # 删除频道名称中的"-"和码率
    channel_df['tvg_name'] = channel_df['tvg_name'].apply(lambda x: re.sub(r"-|\d+\.?\d?M|HD|_", "", x.strip()))
    channel_df['tvg_name'] = channel_df['tvg_name'].apply(lambda x: re.sub(r"＋", "+", x.strip()))
    channel_df['tvg_name'] = channel_df['tvg_name'].apply(lambda x: re.sub(r"(?<=\d)[^\d+Kk]+", "", x.strip()))
    channel_df['tvg_name'] = channel_df['tvg_name'].apply(lambda x: re.sub(r"4K$", "-4K", x.strip()))
    channel_df['tvg_name'] = channel_df['tvg_name'].apply(lambda x: re.sub(r"\(.+\)", "", x.strip()))
    channel_df['tvg_name'] = channel_df['tvg_name'].apply(lambda x: re.sub(r"（.+）", "", x.strip()))
    # 多列自然排序（先hostname后tvg_name）
    sorted_index = index_natsorted(zip(channel_df['hostname'], channel_df['tvg_name']))
    channel_df = channel_df.iloc[sorted_index]

    logo_dir_path = Path(r"E:/Desktop/IPTV/images")
    web_logo_dir_path = Path(r"E:/Desktop/IPTV/logo")
    iptv_dir_path = Path(r"E:/Desktop/IPTV/iptv.m3u")
    dst_file_path = src_dir_path.joinpath("channel.xlsx")
    excel_writer = pandas.ExcelWriter(dst_file_path)
    save_df_to_sheet(excel_writer, "可访问频道", channel_df)

    if not web_logo_dir_path.exists():
        web_logo_dir_path.mkdir(parents=True, exist_ok=True)
    ipv4_group_channel_dict = channel_df.groupby('is_ipv4')
    result_df_list = []
    for is_ipv4, group_df in ipv4_group_channel_dict:
        if is_ipv4:
            province_isp_group_dict = group_df.groupby(['ipv4_addresses省份', 'ipv4_addresses地市', 'ipv4_addresses运营商'])
            for (province, city, isp), ipv4_group_df in province_isp_group_dict:
                channel_group_dict = {
                    "CCTV": f"CCTV_{province}{city}{isp}",
                    "卫视": f"卫视频道_{province}{city}{isp}",
                    "武汉": f"武汉频道_{province}{city}{isp}",
                    "CETV": f"教育频道_{province}{city}{isp}",
                    "教育": f"教育频道_{province}{city}{isp}",
                    "凤凰": f"凤凰卫视_{province}{city}{isp}",
                    "CGTN": f"中国国际电视台_{province}{city}{isp}",
                    "直播中国": f"直播中国_{province}{city}{isp}",
                    "其他频道": f"其他频道_{province}{city}{isp}"
                }
                ipv4_group_df['group_title'] = ipv4_group_df.apply(lambda row: chanel_group(channel_group_dict, row['tvg_name'], row['group_title']), axis=1)
                result_df_list.append(ipv4_group_df)
        else:
            channel_group_dict = {
                "CCTV": f"CCTV_IPV6",
                "卫视": f"卫视频道_IPV6",
                "武汉": f"武汉频道_IPV6",
                "CETV": f"教育频道_IPV6",
                "教育": f"教育频道_IPV6",
                "凤凰": f"凤凰卫视_IPV6",
                "CGTN": f"中国国际电视台_IPV6",
                "直播中国": f"直播中国_IPV6",
                "其他频道": f"其他频道_IPV6"
            }
            group_df['group_title'] = group_df.apply(lambda row: chanel_group(channel_group_dict, row['tvg_name'], row['group_title']), axis=1)
            result_df_list.append(group_df)
    channel_df = pandas.concat(result_df_list)
    channel_df['ChannelLogo'] = channel_df['tvg_name'].apply(lambda x: hashlib.md5(x.encode()).hexdigest())
    channel_df['ChannelLogoFile'] = channel_df.apply(lambda row: check_logo_file(row), axis=1)
    sorted_index = index_natsorted(zip(channel_df['group_title'], channel_df['tvg_name']))
    channel_df = channel_df.iloc[sorted_index]
    save_df_to_sheet(excel_writer, "最终频道", channel_df)
    excel_writer.close()
    save_to_m3u(channel_df)
    # print(channel_df)
