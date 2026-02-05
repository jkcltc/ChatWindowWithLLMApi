import json
import queue
import re
import os
import threading
from typing import Any, Dict, List, Tuple,Optional
from urllib.parse import quote
from PyQt6.QtWidgets import *
from PyQt6.QtCore import *
from PyQt6.QtGui import *
from PyQt6.QtSvg import *
import openai, requests
from requests.adapters import HTTPAdapter
from requests.exceptions import RequestException
from lxml import etree
from bs4 import BeautifulSoup

from utils.preset_data import WebRagPresetVars
from config import APP_SETTINGS

#爬虫组件
class bing_search:
    def __init__(self):
        self.BING_SEARCH_URL = "https://www.bing.com/search?q="
    def get_search_results(self,query: str) -> List[Dict[str, Any]]:
        session = requests.Session()
        # 重试机制
        adapter = HTTPAdapter(max_retries=3)
        session.mount('http://', adapter)
        session.mount('https://', adapter)
    
        headers = {
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/133.0.0.0 Safari/537.36 Edg/133.0.0.0'
        }
        
        try:
            response = session.get(self.BING_SEARCH_URL + quote(query)+'&ensearch=1', headers=headers, timeout=10)
            response.raise_for_status()
            response.encoding = 'utf-8'  # 确保使用正确的编码
        except RequestException as e:
            return []
    
        soup = BeautifulSoup(response.text, 'html.parser')
        results = []
        # 处理普通搜索结果
        for result in soup.select('#b_results .b_algo'):
            link_tag = result.find('a', class_='tilk')
            title_tag = result.find('h2')
            content_tag = result.find('p')
            
            link = link_tag.get('href') if link_tag else ''
            title = title_tag.get_text(strip=True) if title_tag else ''
            content = content_tag.get_text(strip=True) if content_tag else ''
            
            if link and title and content:
                results.append({
                    'title': title,
                    'link': link,
                    'content': content
                })
    
        # 处理新闻结果
        for news in soup.select('.b_nwsAns'):
            link_tag = news.find('a', class_='itm_link')
            title_tag = news.find(class_='na_t_news_caption')
            content_tag = news.find(class_='itm_spt_news_caption')
            
            link = link_tag.get('href') if link_tag else ''
            title = title_tag.get_text(strip=True) if title_tag else ''
            content = content_tag.get_text(strip=True) if content_tag else ''
            
            if link and title and content:
                results.append({
                    'title': title,
                    'link': link,
                    'content': content,
                    '_source': 'Bing News'
                })
        for img in soup.select('.imgpt'):
            img_link = img.find('a', class_='iusc')
            img_meta = img.find('div', class_='img_info')
            img_tag = img.find('img')
            
            # 解析JSON数据获取高清图片URL
            if img_link and 'm' in img_link.attrs:
                import json
                try:
                    img_data = json.loads(img_link['m'])
                    full_size_url = img_data.get('murl', '')
                except:
                    full_size_url = ''
            
            results.append({
                'title': img_tag.get('alt', '') if img_tag else '',
                'link': full_size_url,
                'thumbnail': img_tag.get('src', '') if img_tag else '',
                'dimensions': img_meta.get_text(' ') if img_meta else '',
                '_source': 'Bing Images'
            })
        
        
        # 知识面板
        knowledge_panel = soup.find('div', class_='b_knowledge')
        if knowledge_panel:
            title_tag = knowledge_panel.find('h2')
            content_tag = knowledge_panel.find('div', class_='b_snippet')
            
            results.append({
                'title': title_tag.get_text(strip=True) if title_tag else '',
                'content': content_tag.get_text(strip=True) if content_tag else '',
                '_source': 'Bing Knowledge'
            })
        
        # 相关搜索
        for related in soup.select('.b_rs'):
            related_link = related.find('a')
            results.append({
                'query': related_link.get_text(strip=True),
                'link': related_link.get('href'),
                '_source': 'Bing Related'
            })
        return results

class baidu_search:
    def __init__(self):
        self.TOTAL_SEARCH_RESULTS = 10  # 假设默认搜索结果数量

    def clean_url(self,url: str) -> str:
        """清理 URL 结尾的斜杠"""
        return url.rstrip('/')

    def get_search_results(self,query: str) -> List[Dict]:
        """本地百度搜索实现"""
        try:
            url = f"https://www.baidu.com/s?wd={quote(query)}&tn=json&rn={self.TOTAL_SEARCH_RESULTS}"
            headers = {
                "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36"
            }
            
            response = requests.get(url, headers=headers, timeout=10)
            response.raise_for_status()
            
            data = response.json()
            entries = data.get("feed", {}).get("entry", [])
            
            results = []
            for entry in entries:
                result = {
                    "title": entry.get("title", ""),
                    "link": entry.get("url", ""),
                    "content": entry.get("abs", "")
                }
                if result["link"]:
                    results.append(result)
                    
            return results
        
        except Exception as e:
            print(f"Search error: {e}")
            return []

class WebScraper:
    def __init__(self):
        # 初始化一个requests的Session对象，方便管理请求
        self.session = requests.Session()

    def fetch_response(self, url):
        """
        发送HTTP GET请求并返回响应内容。
        """
        try:
            response = self.session.get(url)
            response.raise_for_status()  # 检查请求是否成功
            return response
        except requests.exceptions.RequestException as e:
            print(f"请求出现错误: {e}")
            return None
 
    def extract_link_from_script(self, html_content):
        """
        从HTML内容中提取<script>标签中嵌入的链接。
        """
        soup = BeautifulSoup(html_content, 'html.parser')
        script_content = soup.find('script').string  # 假设目标链接在第一个<script>标签中

        if not script_content:
            print("未找到<script>标签内容")
            return None

        # 使用正则表达式查找链接
        pattern = r'var u = "(https?://[^"]+)";'
        match = re.search(pattern, script_content)

        if match:
            link = match.group(1)
            print("已提取链接")
            return link
        else:
            print("未找到链接")
            return None

    def get_webpage_content(self, url):
        """
        获取网页的主要文本内容。
        """
        try:
            response = self.session.get(url)
            response.raise_for_status()  # 检查请求是否成功

            # 解析HTML内容
            
            try:
                html = response.text
                html = html.encode("ISO-8859-1")
                html = html.decode("utf-8")
                
                # 解析HTML
                tree = etree.HTML(html)
                body_text = tree.xpath('//body//text()')
                full_text = ' '.join(body_text)
            except Exception as e:
                try:
                    html = response.text
                    html = html.encode("gb2312")
                    html = html.decode("utf-8")
                    
                    # 解析HTML
                    tree = etree.HTML(html)
                    body_text = tree.xpath('//body//text()')
                    full_text = ' '.join(body_text)
                except:
                    soup = BeautifulSoup(response.text, 'html.parser')
                    full_text = soup.body.get_text(strip=True)
            # 提取网页正文内容
            
            return full_text

        except Exception as e:
            print(f"请求出现错误: {e}")
            return None

    def run(self, initial_url):
        """
        主流程逻辑：从初始URL中提取目标链接，并获取目标网页内容。
        """
        # Step 1: 获取初始URL的响应
        response = self.fetch_response(initial_url)
        if not response:
            print("无法获取初始URL的响应")
            return None

        # Step 2: 从响应HTML中提取链接
        if 'bing' in initial_url:
            link = self.extract_link_from_script(response.text)
        else:
            print('链接地址获取完成')
            return response.text
        if not link :
            print("无法提取链接，流程终止")
            return None
        
        # Step 3: 获取提取链接对应网页的内容
        content = self.get_webpage_content(link)
        if content:
            print("目标网页内容提取成功:")
            return content
        else:
            print("目标网页内容提取失败")
            return None

class WebSearchTool:
    def __init__(self, search_engine, scraper,model_map,default_apis):
        """
        初始化工具类。
        
        :param search_engine: 搜索引擎实例，需要实现 `get_search_results(query)` 方法。
        :param scraper: 网页抓取器实例，需要实现 `run(url)` 方法。
        """
        self.search_engine = search_engine
        self.scraper = scraper
        self.search_results = {}
        self.query=''
        self.model_map=model_map
        self.default_apis=default_apis
 
    def search_and_scrape(self, query):
        """
        使用多线程执行搜索和抓取操作。
        
        :param query: 搜索查询字符串。
        :return: 格式化后的搜索结果字符串。
        """
        # 获取搜索结果
        self.query=query
        results = self.search_engine.get_search_results(query)
        
        # 创建线程安全的队列和锁
        task_queue = queue.Queue()

        # 准备队列任务（添加索引i保持顺序）
        for i, result in enumerate(results, start=1):
            task_queue.put((i, result))

        # 定义工作线程函数
        def worker():
            while True:
                try:
                    # 获取任务（非阻塞方式）
                    i, result = task_queue.get(block=False)
                    link = result.get("link")
                    content = self.scraper.run(link)

                    if content:
                        # 线程安全的打印操作

                        # 直接按索引存储结果（天然线程安全，因为i是唯一的）
                        self.search_results[i] = {
                            "title": result.get("title", "No Title"),
                            "link": link,
                            "abstract": result.get("content", "No Abstract"),
                            "content": content
                        }
                    else:
                        self.search_results[i] = {
                            "title": result.get("title", "No Title"),
                            "link": link,
                            "abstract": result.get("content", "No Abstract"),
                            "content": result.get("content", "No Abstract")
                        }
                    
                    # 标记任务完成
                    task_queue.task_done()
                except queue.Empty:
                    break

        # 创建并启动工作线程
        threads = []
        for _ in range(5):
            t = threading.Thread(target=worker)
            t.start()
            threads.append(t)

        # 等待所有任务完成
        task_queue.join()

        # 等待所有线程结束
        for t in threads:
            t.join()
        sorted_results = {k: self.search_results[k] for k in sorted(self.search_results)}
        self.search_results=sorted_results
        return self.search_results
 
    def format_results(self,abstracter=True,useable_list=[]):
        """
        格式化搜索结果。
        
        :return: 格式化后的搜索结果字符串。
        """
        web_reference = ''
        for key, value in self.search_results.items():
            if not key in useable_list and not abstracter:
                continue
            web_reference += '\n Result ' + str(key)
            web_reference += '\n Title: ' +value['title']
            web_reference += '\n Link: ' +value['link']
            if abstracter:
                web_reference += '\n Abstract: ' + value['abstract']
            elif len(value['content'])<10000 :
                web_reference += '\n content: ' + value['content']

            web_reference += '\n' + ("-" * 10)
        if len(str(web_reference))<15000:
            return web_reference
        else:
            return str(web_reference)[:12000]

    def online_rag(self,api_key,rag_provider_link,rag_model):
        def extract_all_json(ai_response):
            json_pattern = r'\{[\s\S]*?\}'
            matches = re.findall(json_pattern, ai_response)
            
            valid_json_objects = []
            for match in matches:
                try:
                    json_obj = json.loads(match)
                    valid_json_objects.append(json_obj)
                except json.JSONDecodeError:
                    continue
            
            if valid_json_objects:
                return valid_json_objects
            else:
                print("未找到有效的JSON部分")
                print(ai_response)
                return None
        if self.search_results == {}:
            print("no search results,returning None")
            return None
        client = openai.Client(
            api_key=api_key,
            base_url=rag_provider_link
        )
        user_input=WebRagPresetVars.prefix+self.query+WebRagPresetVars.subfix+self.format_results()
        message=[{"role":"user","content":user_input}]
        print(user_input)
        params={'model':rag_model,
                'messages':message,
                'stream':False,  # 设置为 True 可启用流式输出
                'temperature':0
            }
        try:
            response = client.chat.completions.create(**params)
            return_message = response.choices[0].message.content
            result=extract_all_json(return_message)
            print(result)
            if not result:
                return 'Result: Rag模型报告没有有效的搜索结果'
            if result[0]["enough_intel"]==True or result[0]["enough_intel"]=='True':
                return self.format_results(abstracter=True)
            elif result[0]["enough_intel"]==False or result[0]["enough_intel"]=='False':
                return self.format_results(abstracter=False,useable_list=result[0]["useful_result"])
            elif (result[0]["enough_intel"]==False or result[0]["enough_intel"]=='False') and result[0]["useful_result"]=='':
                return 'Result: Rag模型报告没有有效的搜索结果'

        except Exception as e:
            print(result)
            print("online rag failed,Error code:",e)
            return ''

# 搜索组件
class WebSearchSettingWindows(QObject):
    update_result_ui=pyqtSignal()

    def __init__(self):
        super().__init__()
        self.results_num = 10

        self.search_queue = queue.Queue()

        self.search_settings_widget = QWidget()
        self.search_settings_widget.setWindowTitle("搜索设置")
        self.search_results_widget = QWidget()

        self.tool = None
        self.result = None
        self.finished = False
        self.search_complete_event = threading.Event()

        self.update_result_ui.connect(self.display_results)

        self.create_search_settings()
        self.create_search_results()

    @property
    def model_map(self):
        """实时获取"""
        return APP_SETTINGS.api.model_map

    @property
    def default_apis(self):
        return APP_SETTINGS.api.providers
    
    @property
    def endpoints(self):
        """实时获取"""
        return APP_SETTINGS.api.endpoints

    def create_search_settings(self):
        layout = QVBoxLayout(self.search_settings_widget)
        
        # 搜索引擎选择
        engine_label = QLabel("搜索引擎")
        self.engine_combo = QComboBox()
        self.engine_combo.addItems(["baidu", "bing"])
        self.engine_combo.setCurrentText(APP_SETTINGS.web_search.search_engine)
        layout.addWidget(engine_label)
        layout.addWidget(self.engine_combo)
        
        # 返回结果数
        result_num_label = QLabel("返回结果数")
        self.result_num_edit = QLineEdit()
        self.result_num_edit.setText('10')
        self.result_num_edit.setValidator(QIntValidator())  # 确保输入为整数
        layout.addWidget(result_num_label)
        layout.addWidget(self.result_num_edit)
        
        # RAG相关控件
        self.rag_checkbox = QCheckBox("使用RAG过滤")
        layout.addWidget(self.rag_checkbox)
        
        self.rag_provider_label = QLabel("RAG 过滤器模型提供商")
        self.rag_provider_combo = QComboBox()
        self.rag_provider_combo.addItems(self.model_map.keys())
        layout.addWidget(self.rag_provider_label)
        layout.addWidget(self.rag_provider_combo)
        
        self.rag_model_label = QLabel("RAG过滤模型")
        self.rag_model_combo = QComboBox()
        self.update_rag_models()
        layout.addWidget(self.rag_model_label)
        layout.addWidget(self.rag_model_combo)
        
        # 初始隐藏RAG控件
        self.toggle_rag_controls(False)
        self.rag_checkbox.stateChanged.connect(
            lambda state: self.toggle_rag_controls(state == Qt.CheckState.Checked)
        )
        
        # 确定按钮
        confirm_btn = QPushButton("确定")
        confirm_btn.clicked.connect(self.save_settings)
        layout.addWidget(confirm_btn)
        
        self.search_settings_widget.setLayout(layout)
        
        # 联动模型提供商和模型列表
        self.rag_provider_combo.currentTextChanged.connect(self.update_rag_models)

    def toggle_rag_controls(self, visible):
        """控制RAG相关控件的可见性"""
        self.rag_provider_label.setVisible(visible)
        self.rag_provider_combo.setVisible(visible)
        self.rag_model_label.setVisible(visible)
        self.rag_model_combo.setVisible(visible)

    def update_rag_models(self):
        """更新模型列表"""
        provider = self.rag_provider_combo.currentText()
        self.rag_model_combo.clear()
        self.rag_model_combo.addItems(self.model_map.get(provider, []))
        
    def save_settings(self):
        """保存设置"""
        search_engine = self.engine_combo.currentText()
        results_num = int(self.result_num_edit.text() or 10)  # 默认10条
        APP_SETTINGS.web_search.search_engine = search_engine
        APP_SETTINGS.web_search.search_results_num = results_num

        self.search_settings_widget.hide()
        
    def create_search_results(self):
        layout = QVBoxLayout()
        self.results_list = QListWidget()
        
        # 紧凑列表样式
        self.results_list.setStyleSheet("""
            QListWidget {
                background: transparent;
                border: 1px solid #e0e0e0;
                border-radius: 4px;
                padding: 2px;
                font-family: "Segoe UI";
                outline: 0;
            }
            QListWidget::item {
                margin: 1px;
                padding: 0;
            }
            QListWidget::item:hover {
                background: #f5f5f5;
            }
            QScrollBar:vertical {
                width: 10px;
                background: transparent;
            }
            QScrollBar::handle:vertical {
                background: #d0d0d0;
                border-radius: 3px;
            }
        """)
        
        layout.setContentsMargins(5, 5, 5, 5)  # 减少外层边距
        layout.setSpacing(0)  # 去除布局间距
        layout.addWidget(self.results_list)
        self.search_results_widget.setLayout(layout)
         
    def perform_search(self, query):
        """执行搜索并更新结果（使用线程避免阻塞UI）"""
        # 读取当前UI参数
        self.finished=False
        self.search_complete_event.clear()
        engine = self.engine_combo.currentText()
        results_num = APP_SETTINGS.web_search.search_results_num

        # 启动后台线程执行搜索
        search_thread = threading.Thread(
            target=self._threaded_search,
            args=(query, engine, results_num),
            daemon=True
        )
        search_thread.start()
        search_thread.join()
        print('joined search_thread')

        # 开始检查结果（根据GUI框架调整）
        self.check_search_result()
    
    def _threaded_search(self, query, engine, results_num):
        """后台线程执行的搜索逻辑"""
        # 根据引擎创建搜索器
        if engine == "baidu":
            searcher = baidu_search()
            searcher.TOTAL_SEARCH_RESULTS = results_num
        elif engine == "bing":
            searcher = bing_search()
        
        scraper = WebScraper()
        self.tool = WebSearchTool(searcher, scraper,self.model_map,self.default_apis)
        result = self.tool.search_and_scrape(query)
        
        # 将结果放入队列
        self.search_queue.put(result)

    def check_search_result(self):
        """主线程检查结果队列"""
        try:
            # 非阻塞获取结果
            result = self.search_queue.get_nowait()
            
            # 处理RAG（在主线程操作UI组件）
            if APP_SETTINGS.web_search.use_llm_reformat:
                config = APP_SETTINGS.web_search.reformat_config
                provider_info = APP_SETTINGS.api.providers.get(config.provider)

                if not provider_info:
                    raise ValueError(f"未找到API提供商: {config.provider}")

                self.rag_result = self.tool.online_rag(
                    api_key=provider_info.key,
                    url=provider_info.url,
                    model=config.model
                )

            # 更新结果并显示
            self.result = result
            self.update_result_ui.emit()
        except queue.Empty:
            None
        except Exception as e:
            print(e)

    def display_results(self):
        """展示搜索结果"""
        self.results_list.clear()
        
        # 紧凑按钮样式
        button_style = """
            QPushButton {
                background: white;
                color: #404040;
                border: 1px solid #e0e0e0;
                border-radius: 3px;
                padding: 6px 10px;
                text-align: left;
                font-size: 13px;
                margin: 1px;
                min-width: 240px;
            }
            QPushButton:hover {
                background: #f8f8f8;
                border-color: #c0c0c0;
            }
            QPushButton:pressed {
                background: #f0f0f0;
            }
        """
        
        for idx, item in enumerate(self.result.items(), start=1):
            key, value = item
            btn = QPushButton(f"{key}. {value['title']}")
            btn.setStyleSheet(button_style)
            btn.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Fixed)
            
            # 紧凑尺寸设置
            btn.setFixedHeight(32)  # 减少按钮高度
            btn.setIconSize(QSize(16, 16))  # 缩小图标尺寸
            
            link = value['link']
            btn.clicked.connect(lambda _, l=link: os.startfile(l))

            list_item = QListWidgetItem()
            list_item.setSizeHint(QSize(0, 34))  # 固定行高
            self.results_list.addItem(list_item)
            self.results_list.setItemWidget(list_item, btn)
        self.finished = True
        self.search_complete_event.set()

    def wait_for_search_completion(self, timeout=None):
        """轮询函数，供其他线程阻塞等待"""
        return self.search_complete_event.wait(timeout)

