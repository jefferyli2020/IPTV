import requests
from bs4 import BeautifulSoup
from datetime import datetime, timedelta
import xml.etree.ElementTree as ET
import xml.dom.minidom as minidom

CHANNEL_WHITELIST = ["东方卫视", "上视新闻", "上海都市", "生活时尚", "东方影视"]

def get_token(headers):
    r = requests.post("https://www.tvmao.com/servlet/accessToken", data={"p": "channelEpg"}, headers=headers)
    data = r.json()
    return data[1] if isinstance(data, list) and data[0] == 1 else None

def parse_programs_from_html(html, date_str):
    soup = BeautifulSoup(html, "html.parser")
    programs = []
    for div in soup.select("li > div.over_hide"):
        time_tag = div.select_one("span.am") or div.select_one("span.pm")
        title_tag = div.select_one("span.p_show")
        if time_tag and title_tag:
            time = time_tag.get_text(strip=True)
            title = title_tag.get_text(" ", strip=True)
            try:
                dt = datetime.strptime(f"{date_str} {time}", "%Y%m%d %H:%M")
                dt_fmt = dt.strftime("%Y%m%d%H%M%S +0800")
                programs.append((dt, dt_fmt, title))
            except:
                continue
    return programs

def fetch_tvmao_programs():
    headers = {
        "User-Agent": "Mozilla/5.0",
        "Referer": "https://www.tvmao.com/program/SHHAI-SHHAI5-w1.html",
        "X-Requested-With": "XMLHttpRequest"
    }
    token = get_token(headers)
    if not token:
        raise Exception("Token 获取失败")
    all_programs = []
    for i in range(3):
        day = datetime.today() + timedelta(days=i)
        date_str = day.strftime("%Y%m%d")
        w = (day.weekday() + 1)
        url_html = f"https://www.tvmao.com/program/SHHAI-SHHAI5-w{w}.html"
        html = requests.get(url_html, headers=headers).text
        all_programs += parse_programs_from_html(html, date_str)
        payload = {"tc": "SHHAI", "cc": "SHHAI5", "w": str(w), "token": token}
        json_list = requests.post("https://www.tvmao.com/servlet/channelEpg", data=payload, headers=headers).json()
        for frag in json_list:
            if isinstance(frag, str):
                all_programs += parse_programs_from_html(frag, date_str)
    all_programs.sort(key=lambda x: x[0])
    return all_programs

def patch_and_format_xml(e_url, new_programs, output="最终_e.xml"):
    resp = requests.get(e_url)
    old_root = ET.fromstring(resp.content)
    channel_program_map = {name: [] for name in CHANNEL_WHITELIST}
    for prog in old_root.findall("programme"):
        ch = prog.attrib.get("channel")
        if ch in CHANNEL_WHITELIST:
            channel_program_map.setdefault(ch, []).append(prog)
    channel_program_map["五星体育"] = []
    for i in range(len(new_programs)):
        start_dt, start_str, title = new_programs[i]
        stop_dt = new_programs[i + 1][0] if i + 1 < len(new_programs) else start_dt + timedelta(minutes=30)
        stop_str = stop_dt.strftime("%Y%m%d%H%M%S +0800")
        prog = ET.Element("programme", {
            "channel": "五星体育",
            "start": start_str,
            "stop": stop_str
        })
        ET.SubElement(prog, "title", {"lang": "zh"}).text = title
        channel_program_map["五星体育"].append(prog)
    new_root = ET.Element("tv")
    for ch_name in sorted(channel_program_map.keys()):
        ch_elem = ET.SubElement(new_root, "channel", {"id": ch_name})
        ET.SubElement(ch_elem, "display-name", {"lang": "zh"}).text = ch_name
        for prog in channel_program_map[ch_name]:
            new_root.append(prog)
    xml_string = ET.tostring(new_root, encoding="utf-8")
    dom = minidom.parseString(xml_string)
    pretty_xml = dom.toprettyxml(indent="  ", encoding="utf-8")
    with open(output, "wb") as f:
        f.write(pretty_xml)
    print(f"✅ 已生成 XML：{output}")

if __name__ == "__main__":
    programs = fetch_tvmao_programs()
    patch_and_format_xml("https://live.fanmingming.cn/e.xml", programs, output="最终_e.xml")
