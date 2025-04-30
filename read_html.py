import hashlib

import pandas as pd
import requests
from bs4 import BeautifulSoup

from iptv import creat_m3u, check_urls_in_dataframe

url = 'https://mp.weixin.qq.com/s/MHAF-r1GoeoL_AFz6zYoJw'
html_content = requests.get(url).text
# 创建BeautifulSoup对象
soup = BeautifulSoup(html_content, 'html.parser')

# 查找class为rich_media_content的div元素
rich_media_div = soup.find('div', class_='rich_media_content')
# 查找rich_media_div内部所有的p标签
p_tags = rich_media_div.find_all('p')
# 遍历每个p标签并提取文本内容
data = []
for p in p_tags:
    line = p.get_text(strip=True)
    metadata = line.split(',')
    if len(metadata) < 2:
        continue
    title = metadata[0].replace("-", "")
    group_title = "百视通移动"
    tvg_logo = ''
    tvg_name = title
    tvg_id = ''
    # 计算tvg_name的MD5值作为logo_id
    logo_id = hashlib.md5(tvg_name.encode()).hexdigest()
    url = metadata[1]
    data.append([title, url, group_title, tvg_logo, tvg_name, tvg_id, logo_id])
# 创建DataFrame
columns = ['title', 'url', 'group_title', 'tvg_logo', 'tvg_name', 'tvg_id', 'logo_id']
df = pd.DataFrame(data, columns=columns)
print(df)
df = check_urls_in_dataframe(df, url_column='url', max_redirects=10, max_workers=10)
creat_m3u(df)