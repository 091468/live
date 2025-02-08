import hashlib
import re
from pathlib import Path

import pandas as pd
import requests
from opencc import OpenCC

from config import src_url_list
from concurrent.futures import ThreadPoolExecutor, as_completed

headers = {
    "user-agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/112.0.0.0 Safari/537.36"
}

# 初始化繁体转简体转换器
cc = OpenCC('t2s')


def process_value(value):
    # 处理CCTV的名称
    if 'CCTV' in value:
        # 保留数字和字母
        value = re.sub(r'[^A-Za-z0-9]', '', value)
        value = re.sub(r'_', '-', value)
    return value


def read_m3u_file(src_m3u_url):
    try:
        response = requests.get(src_m3u_url, headers=headers, timeout=10)
    except:
        return pd.DataFrame()
    response.encoding = 'utf-8'  # 显式设置编码为UTF-8
    status_code = response.status_code
    if status_code == 200:
        print("获取成功")
        lines = response.text.splitlines()
    else:
        lines = ''
        print("获取失败")
    data = []

    for line in lines:
        line = line.strip()
        if line.startswith('#EXTINF:'):
            metadata = line.split(',')
            title = metadata[-1]
            group_title_match = re.search(r'group-title="(.*?)"', line)
            group_title = group_title_match.group(1) if group_title_match else ''
            tvg_logo_match = re.search(r'tvg-logo="(.*?)"', line)
            tvg_logo = tvg_logo_match.group(1) if tvg_logo_match else ''
            tvg_name_match = re.search(r'tvg-name="(.*?)"', line)
            tvg_name = tvg_name_match.group(1) if tvg_name_match else title
            tvg_id_match = re.search(r'tvg-id="(.*?)"', line)
            tvg_id = tvg_id_match.group(1) if tvg_id_match else ''
        elif line and line.startswith('http'):
            url = line
            data.append({
                'title': title,
                'url': url,
                'group_title': group_title,
                'tvg_logo': tvg_logo,
                'tvg_name': tvg_name,
                'tvg_id': tvg_id
            })
    # 创建DataFrame
    df = pd.DataFrame(data)
    df['title'] = df['title'].apply(cc.convert)
    df['tvg_name'] = df['tvg_name'].apply(cc.convert)
    df['group_title'] = df['group_title'].apply(cc.convert)
    return df
    # df.query('tvg_name.str.contains(r"(?:CCTV\d+[\+K]?$)|(?:^[^巴]{2,3}卫视)|(?:^凤凰.+)")', inplace=True)


def creat_m3u(df):
    # 下载tvg-logo并重命名
    new_line_list = ['#EXTM3U x-tvg-url="http://epg.51zmt.top:8000/e.xml" catchup="append" catchup-source="?playseek=${(b)yyyyMMddHHmmss}-${(e)yyyyMMddHHmmss}"']
    for index, row in df.iterrows():
        tvg_logo_url = row['tvg_logo']
        logo_extension = Path(tvg_logo_url).suffix
        tvg_name = row['tvg_name']
        title = row['title']
        tvg_id = row['tvg_id']
        url = row['url']
        group_title = row['group_title']
        # 先检查本地目录内是否存在同名png文件
        logo_path = logo_dir_path.joinpath(f'{tvg_name}.png')
        if not logo_path.exists():
            # 检查本地目录内是否存在同名jpg文件
            logo_path = logo_dir_path.joinpath(f'{tvg_name}.jpg')
        if not logo_path.exists():
            # 通过频道名前缀匹配logo文件
            for current_logo_file_path in logo_dir_path.iterdir():
                if tvg_name.startswith(current_logo_file_path.stem):
                    logo_path = current_logo_file_path
                    break
        if not logo_path.exists():
            logo_path = logo_dir_path.joinpath("iptv.jpg")

        new_tvg_logo_url = f"https://live.lichuan.tech/images/{logo_path.name}"
        # tvg_name = remark_name.get(tvg_name, tvg_name)  # 使用别名
        new_line = f'#EXTINF:-1 tvg-id="{tvg_id}" tvg-name="{tvg_name}" tvg-logo="{new_tvg_logo_url}" group-title="{group_title}",{tvg_name}\n{url}'
        new_line_list.append(new_line)
    new_m3u_path = iptv_dir_path.joinpath("tv", "iptv.m3u")
    new_m3u_path.write_text("\n".join(new_line_list), encoding='utf-8')


def get_group_name(title, group_title):
    for key, value in keywords_to_keep.items():
        if key in title:
            return value
    return group_title


def check_urls_in_dataframe(df, url_column='url', max_redirects=20, max_workers=10):
    """
    检查DataFrame中的URL列是否可访问，并记录最终重定向后的URL。

    参数:
    df (pd.DataFrame): 包含要检查的URL的数据框
    url_column (str): URL列的名称
    max_redirects (int): 允许的最大重定向次数
    max_workers (int): 最大线程数

    返回:
    pd.DataFrame: 添加了最终URL和可访问性标志的DataFrame
    """
    # 定义正则表达式
    ipv4_pattern = re.compile(r'(\b\d{1,3}\.){3}\d{1,3}\b')
    mp4_pattern = re.compile(r'\.mp4$', re.IGNORECASE)
    zibo_pattern = re.compile("douyu|huya|bilibili|mobaibox|iHOT|NewTV|BesTV", re.IGNORECASE)

    def check_url(url):
        # 检查是否包含IPv4地址或以.mp4结尾
        if mp4_pattern.search(url) or zibo_pattern.search(url):
            print("直接跳过测试：", url)
            return None, None
        # if not is_ipv6(url):
        #     print("这不是一个IPV6地址：", url)
        #     return None, None
        try:
            response = requests.get(url, allow_redirects=True, timeout=10)
            if response.history and len(response.history) > max_redirects:
                print(f"重定向次数超过 {max_redirects}：", url)
                return None, None
            else:
                print(f"重定向次数 {len(response.history)}：", url)
                return response.url, response.status_code == 200
        except requests.RequestException:
            return None, None

    # 使用线程池多线程处理
    with ThreadPoolExecutor(max_workers=max_workers) as executor:
        future_to_url = {executor.submit(check_url, url): url for url in df[url_column]}
        results = []
        for future in as_completed(future_to_url):
            original_url = future_to_url[future]
            try:
                final_url, accessible = future.result()
                results.append((original_url, final_url, accessible))
                # 实时输出检查结果
                if accessible:
                    print(f"URL {original_url} 链接有效，最终地址: {final_url}")
                else:
                    print(f"URL {original_url} 链接无效或者重定向次数过多.")
            except Exception as exc:
                print(f'URL {original_url} 访问出错: {exc}')
                results.append((original_url, None, None))
    # 将结果整合为新的 DataFrame
    result_df = pd.DataFrame(results, columns=[url_column, 'final_url', 'accessible'])
    # 合并原始数据与新数据
    df = df.merge(result_df, on=url_column)
    # 删除不可访问或重定向超限的记录
    df = df[df['accessible'] & df['final_url'].notnull()]
    # 删除中间步骤用的辅助列
    df.drop(columns=['accessible'], inplace=True)
    return df


if __name__ == '__main__':
    iptv_dir_path = Path(__file__).parent
    logo_dir_path = iptv_dir_path.joinpath('images')
    if not logo_dir_path.exists():
        logo_dir_path.mkdir(exist_ok=True, parents=True)
    df_list = []
    for url in src_url_list:
        print("正在从链接获取直播源", url)
        tmp_df = read_m3u_file(url)
        df_list.append(tmp_df)
    df = pd.concat(df_list)
    df.drop_duplicates(subset=['url'], inplace=True, keep='first')
    # IPV4地址的正则表达式
    ipv4_pattern = r'\b(?:[0-9]{1,3}\.){3}[0-9]{1,3}\b'
    # 处理 "title" 和 "tvg_name" 列，并转换繁体为简体
    # df.to_excel(iptv_dir_path.joinpath("iptv_all.xlsx"))
    keywords_to_keep = {
        "CCTV": "CCTV",
        "凤凰": "香港频道",
        "香港": "香港频道",
        "iHOT": "iHOT",
        "卫视": "卫视频道",
        "NewTv": "NewTv",
        "恩施": "恩施本地",
        "咪咕": "咪咕直播",
        "半岛新闻「英文」": "国际频道",
        "半岛新闻「阿拉伯」": "国际频道",
        "亚洲新闻": "国际频道",
        "俄罗斯中文": "国际频道",
        "4K": "4K节目",
        "教育": "教育频道",
        "直播中国": "直播中国"
    }
    condition = df['title'].str.contains('|'.join(keywords_to_keep.keys()))
    new_df = df.loc[condition].reset_index(drop=True)
    new_df['group_title'] = new_df.apply(lambda row: get_group_name(row['title'], row['group_title']), axis=1)
    new_df = check_urls_in_dataframe(new_df)
    creat_m3u(new_df)
