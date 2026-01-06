import scrapy
import os
import re


class ArxivSpider(scrapy.Spider):
    name = "arxiv"  # 补充：原代码可能漏了name属性，需确保存在

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        # 读取分类环境变量（原有逻辑）
        categories = os.environ.get("CATEGORIES", "cs.CV")
        self.target_categories = set(map(str.strip, categories.split(",")))
        
        # ========== 核心修改：读取KEYWORDS环境变量 ==========
        # 默认值：空字符串（表示不筛选关键词），也可设默认关键词如 "LLM"
        keywords = os.environ.get("KEYWORDS", "")
        self.target_keywords = set()
        if keywords.strip():  # 避免空值分割出空字符串
            self.target_keywords = set(map(str.strip, keywords.split(",")))
        
        # 构建起始URL（原有逻辑）
        self.start_urls = [
            f"https://arxiv.org/list/{cat}/new" for cat in self.target_categories
        ]

    def parse(self, response):
        # 原有逻辑：提取论文锚点
        anchors = []
        for li in response.css("div[id=dlpage] ul li"):
            href = li.css("a::attr(href)").get()
            if href and "item" in href:
                anchors.append(int(href.split("item")[-1]))

        # 遍历论文详情（核心：增加关键词筛选）
        for paper in response.css("dl dt"):
            paper_anchor = paper.css("a[name^='item']::attr(name)").get()
            if not paper_anchor:
                continue
            paper_id = int(paper_anchor.split("item")[-1])
            if anchors and paper_id >= anchors[-1]:
                continue

            # 提取论文ID（原有逻辑）
            abstract_link = paper.css("a[title='Abstract']::attr(href)").get()
            if not abstract_link:
                continue
            arxiv_id = abstract_link.split("/")[-1]

            # 提取论文分类（原有逻辑）
            paper_dd = paper.xpath("following-sibling::dd[1]")
            subjects_text = paper_dd.css(".list-subjects .primary-subject::text").get() or paper_dd.css(".list-subjects::text").get()
            paper_categories = set(re.findall(r'\(([^)]+)\)', subjects_text)) if subjects_text else set()

            # 1. 先筛选分类（原有逻辑）
            if not paper_categories.intersection(self.target_categories):
                self.logger.debug(f"跳过论文 {arxiv_id}：分类不匹配")
                continue

            # 2. 新增：筛选关键词（如果配置了关键词）
            if self.target_keywords:  # 只有配置了关键词才筛选
                # 提取标题和摘要（统一转小写）
                paper_title = (paper_dd.css("div.list-title::text").get() or "").lower()
                paper_abstract = (paper_dd.css("blockquote::text").get() or "").lower()
                paper_content = paper_title + " " + paper_abstract

                # 检查是否包含任意一个目标关键词（关键词也转小写）
                has_keyword = any(
                    keyword.lower() in paper_content 
                    for keyword in self.target_keywords
                )
                if not has_keyword:
                    self.logger.debug(f"跳过论文 {arxiv_id}：无目标关键词")
                    continue

            # 符合条件的论文，输出数据（原有逻辑）
            yield {
                "id": arxiv_id,
                "categories": list(paper_categories),
                "title": paper_dd.css("div.list-title::text").get(),
                "abstract": paper_dd.css("blockquote::text").get()
            }
            self.logger.info(f"爬取论文 {arxiv_id}：分类匹配 + 关键词匹配（如有）")
