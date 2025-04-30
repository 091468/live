import hashlib
import logging
import re
import time
from pathlib import Path
from urllib.parse import urlparse

import pandas
import pandas as pd
import requests
from opencc import OpenCC
from pd_to_sheet.to_excel import save_df_to_sheet

from config import m3u_url_list, txt_url_list, zibo_pattern
from concurrent.futures import ThreadPoolExecutor, as_completed

from m3u import save_to_m3u

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
    return value


def read_txt_url(txt_url):
    try:
        response = requests.get(txt_url, headers=headers, timeout=10, verify=False)
    except:
        raise
        return pd.DataFrame()
    response.encoding = 'utf-8'  # 显式设置编码为UTF-8
    status_code = response.status_code
    if status_code == 200:
        print("获取成功")
        lines = response.text.splitlines()
    else:
        lines = ''
        print("获取失败")
    channel_list = []
    for line in lines:
        try:
            attr_item_list = line.strip().split(',')
            channel_dict = {
                "tvg_name": attr_item_list[0],
                "url": attr_item_list[1],
            }
            channel_list.append(channel_dict)
        except:
            print(line, "读取出错")
    channel_df = pd.DataFrame(channel_list)
    channel_df['tvg_name'] = channel_df['tvg_name'].apply(cc.convert)
    return channel_df


def read_m3u_url(src_m3u_url):
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
        elif line.startswith('http'):
            url = line
            data.append([title, url, group_title, tvg_logo, tvg_name])
    # 创建DataFrame
    columns = ['title', 'url', 'group_title', 'tvg_logo', 'tvg_name']
    df = pd.DataFrame(data, columns=columns)
    df['title'] = df['title'].apply(cc.convert)
    df['tvg_name'] = df['tvg_name'].apply(cc.convert)
    return df


# 配置日志格式
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
    datefmt='%Y-%m-%d %H:%M:%S'
)


def trace_redirects(url, timeout=10, max_redirects=30):
    """
    追踪URL跳转并检查响应状态码
    返回: 包含详细请求信息的字典（仅成功请求保留完整数据）
    """
    result = {
        'url': url,
        'success': False,
        'status_code': None,
        'final_url': url,
        'redirect_count': 0,
        'redirect_chain': [],
        'error': None,
        'response_time': 0
    }
    start_time = time.time()

    try:
        logging.info(f"开始请求: {url}")
        # 解析 URL
        parsed_url = urlparse(url)
        if parsed_url.scheme in ['rtsp']:
            result['status_code'] = 200
            result['final_url'] = url
            result['success'] = True
            return result
        response = requests.get(url, allow_redirects=True, timeout=timeout, headers=headers, stream=True)
        response.close()
        # 记录请求耗时
        result['response_time'] = round(time.time() - start_time, 2)
        result['status_code'] = response.status_code
        result['final_url'] = response.url
        result['redirect_chain'] = [r.url for r in response.history]
        result['redirect_count'] = len(response.history)
        # 判断请求是否成功 (2xx/3xx状态码视为成功)
        if response.status_code == 200:
            result['success'] = True
            logging.info(f"请求成功: {url} → 最终URL: {response.url} (状态码: {response.status_code}, 跳转: {result['redirect_count']}次, 耗时: {result['response_time']}s)")
        else:
            result['error'] = f"HTTP错误状态码: {response.status_code}"
            logging.warning(f"请求失败: {url} (状态码: {response.status_code})")

    except requests.TooManyRedirects as e:
        result['error'] = f"超过最大跳转限制({max_redirects})"
        logging.error(f"跳转过多: {url} - {str(e)}")
    except requests.RequestException as e:
        result['error'] = str(e)
        logging.error(f"请求异常: {url} - {str(e)}")
    except Exception as e:
        result['error'] = f"未知错误: {str(e)}"
        logging.error(f"系统错误: {url} - {str(e)}", exc_info=True)
    return result


def process_urls(url_list, max_workers=5, timeout=10):
    """
    多线程处理URL列表，仅返回成功请求的结果
    返回: 成功请求的结果列表（保持原始顺序）
    """
    successful_results = []
    with ThreadPoolExecutor(max_workers=max_workers) as executor:
        future_to_index = {
            executor.submit(trace_redirects, url, timeout, max_redirects=30): i
            for i, url in enumerate(url_list)
        }
        # 初始化占位列表
        temp_results = [None] * len(url_list)

        for future in as_completed(future_to_index):
            index = future_to_index[future]
            try:
                result = future.result()
                temp_results[index] = result
                if result['success']:
                    successful_results.append(result)
            except Exception as e:
                logging.error(f"处理异常: {url_list[index]} - {str(e)}", exc_info=True)
    # 按原始顺序返回成功结果
    return [r for r in temp_results if r and r['success']]


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
    url_list = df[url_column].tolist()
    results = process_urls(url_list, max_workers=20, timeout=3)
    # 将结果整合为新的 DataFrame
    result_df = pd.DataFrame(results)
    # 合并原始数据与新数据
    df = df.merge(result_df, on=url_column)
    return df


if __name__ == '__main__':
    iptv_dir_path = Path(__file__).parent
    logo_dir_path = iptv_dir_path.joinpath('logo')
    df_list = []
    dst_file_path = iptv_dir_path.joinpath("iptv_all.xlsx")
    excel_writer = pandas.ExcelWriter(dst_file_path)
    for url in m3u_url_list:
        print("正在从链接获取直播源", url)
        tmp_df = read_m3u_url(url)
        df_list.append(tmp_df)

    # IPV4地址的正则表达式
    for url in txt_url_list:
        print("正在从链接获取直播源", url)
        tmp_df = read_txt_url(url)
        df_list.append(tmp_df)
    df = pd.concat(df_list)
    # 过滤掉包含 .mp4 扩展名的 URL
    df.query("not url.str.endswith('.mp4', na=False)", inplace=True)
    # 过滤掉包含黑名单中任意一个子字符串的 URL
    df = df.query(f"not url.str.contains('{zibo_pattern}', na=False)")
    df.drop_duplicates(subset=['url'], inplace=True, keep='first')
    save_df_to_sheet(excel_writer, "全部频道", df)
    new_df = check_urls_in_dataframe(df)
    if "group_title" not in new_df.columns:
        new_df.insert(0, column="group_title", value="")
    save_df_to_sheet(excel_writer, "可访问频道", new_df)
    excel_writer.close()
