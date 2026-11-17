"""网页正文抓取工具。

web_search 只返回标题/链接/摘要，模型看到链接也拿不到正文，
联网检索的闭环是断的；本工具负责把链接正文取回来。
只用标准库解析 HTML，不额外引入依赖。
"""

import re
from html.parser import HTMLParser

import requests

from configs.setting import TIME_OUT

MAX_CHARS = int(__import__("os").environ.get("FETCH_URL_MAX_CHARS", "4000"))

_HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
        "(KHTML, like Gecko) Chrome/124.0 Safari/537.36"
    ),
    "Accept-Language": "zh-CN,zh;q=0.9,en;q=0.8",
}

# 这些标签里的内容通常不是正文，直接跳过
_SKIP_TAGS = {"script", "style", "noscript", "head", "svg", "form", "iframe"}
_BLOCK_TAGS = {
    "p", "div", "br", "li", "tr", "td", "section", "article",
    "h1", "h2", "h3", "h4", "h5", "h6",
}


class _TextExtractor(HTMLParser):
    """极简正文抽取：跳过脚本样式，块级标签处断行。"""

    def __init__(self):
        super().__init__(convert_charrefs=True)
        self.parts = []
        self._skip_depth = 0

    def handle_starttag(self, tag, attrs):
        if tag in _SKIP_TAGS:
            self._skip_depth += 1
        elif tag in _BLOCK_TAGS and not self._skip_depth:
            self.parts.append("\n")

    def handle_endtag(self, tag):
        if tag in _SKIP_TAGS and self._skip_depth:
            self._skip_depth -= 1

    def handle_data(self, data):
        if not self._skip_depth and data.strip():
            self.parts.append(data.strip() + " ")

    def text(self):
        raw = "".join(self.parts)
        return re.sub(r"\n\s*\n+", "\n", re.sub(r"[ \t]+", " ", raw)).strip()


class FetchUrl:
    inputs: str = "要抓取正文的网页链接"

    def run(self, url):
        url = (url or "").strip().strip('"').strip("'").split("\n")[0].strip()
        if not url:
            return "fetch url 需要输入网页链接"
        if not url.startswith(("http://", "https://")):
            url = "https://" + url

        try:
            response = requests.get(url, headers=_HEADERS, timeout=TIME_OUT)
        except Exception as e:
            return f"抓取网页失败：{e}"

        if response.status_code != 200:
            return f"抓取网页失败，状态码：{response.status_code}"

        content_type = response.headers.get("content-type", "")
        if "html" in content_type.lower() or response.text.lstrip()[:1] == "<":
            parser = _TextExtractor()
            parser.feed(response.text)
            text = parser.text()
        else:
            text = response.text.strip()

        if not text:
            return f"页面抓取成功，但没有提取到正文内容：{url}"

        if len(text) > MAX_CHARS:
            return f"来源: {url}\n正文（已截断到前 {MAX_CHARS} 字）：\n{text[:MAX_CHARS]}"
        return f"来源: {url}\n正文：\n{text}"


fetch_url = FetchUrl()
