import requests
import sys
from concurrent import futures
from urllib.parse import urlparse

import networkx as nx
import matplotlib.pyplot as plt
from bs4 import BeautifulSoup

from constants import LINKS_START_WITH, STATUS_CODE_REDIRECT, STATUS_CODE_OK, STATUS_CODE_TOO_MANY_REQUESTS, \
    MAX_ATTEMPTS

sys.setrecursionlimit(20000)


class SiteMap:
    """Структурный элемент графа"""

    def __init__(self, url, visited_links=None):
        """Конструктор класса
        :param str url: url сайта
        :param visited_links: список url предшедствующих попаданию на данный url
        """
        if visited_links is None:
            visited_links = []
        self.url = url
        self.visited_links = visited_links
        self.leaves_links = []
        self.leaves = []

    def __str__(self):
        return self.url


class Parser:
    """Класс, используемый для создания карты сайта"""

    def __init__(self, url):
        """
        Конструктор класса
        :param str url: url страницы
        """
        if url[-1] != '/':  # если ссылка не оканчивается на '/', добавляем '/'
            url += '/'
        self.url = url
        self.site_map = SiteMap(url)
        self.leaves = [self.site_map]
        self.visited_links = []
        self.domain = urlparse(url)[0] + '://' + urlparse(url)[1] + '/'
        self.queue = [self.site_map]
        self.deep_visited = []

    def _find_site(self, url):
        """Функция поиска элемента по его ссылке
        :param str url: ссылка для поиска
        :return: SiteMap ссылки либо None, если не найдено
        """
        for leaf in self.leaves:
            if leaf.url == url:
                return leaf
        return

    def breadth(self):
        """Генератор для обхода структуры в ширину
        :return:
        """
        breadth_queue = [self.site_map]
        breadth_visited = []
        for element in breadth_queue:
            breadth_visited.append(element)
            breadth_visited.append(element)
            yield element
            for leaf in element.leaves:
                if leaf not in breadth_visited:
                    breadth_queue.append(leaf)

    def deep(self, site=None):
        """Генератор для обхода структуры в глубину
        :param SiteMap site: текущая структура
        :return:
        """
        if site is None:
            site = self.site_map
        if site not in self.deep_visited:
            yield site
            self.deep_visited.append(site)
            for leaf in site.leaves:
                yield from self.deep(leaf)

    def _download_page(self, site):
        """Функция загрузки страницы
        :param SiteMap site: структура, для которой нужно скачать страницу
        :return: кортеж из струтуры SiteMap и текста страницы
        """
        while True:
            try:
                response = requests.get(site.url)
                if response.status_code == STATUS_CODE_OK:
                    self.queue.remove(site)
                    return site, response.text
            except requests.ConnectionError:
                self.queue.remove(site)
                return

    def start(self):
        """Функция для старта построения карты
        :return:
        """
        executor = futures.ThreadPoolExecutor(max_workers=4)
        while self.queue:
            results = executor.map(self._download_page, self.queue)
            for result in results:  # site, response.text
                self._parse(result[0], result[1])

    def _get_content_type(self, link):
        """Возвращает content-type страницы
        :param str link: url страницы
        :return: content-type
        """
        attempt = 0
        content_type = ''
        while attempt < MAX_ATTEMPTS:
            try:
                response = requests.head(link)
                if response.status_code in STATUS_CODE_REDIRECT:
                    link = response.headers['Location']
                    attempt += 1
                    continue
                if response.status_code == STATUS_CODE_TOO_MANY_REQUESTS:
                    attempt += 1
                else:
                    content_type = response.headers['content-type']
                if content_type:
                    return content_type
            except requests.ConnectionError:
                attempt += 1

    def _parse(self, site, text):
        """Функция для поиска ссылок в текущем документе и добаления их в очередь для скачивания
        :param SiteMap site: структура, для которой требуется провести поиск
        :param str text: текст текущей страницы
        :return:
        """
        print(site.url)
        soup = BeautifulSoup(text, 'html.parser')

        site.visited_links.append(site.url)
        for link in soup.find_all('a'):
            link = link.get('href')
            if not link:
                continue
            if any(link.startswith(word) for word in LINKS_START_WITH) or '#' in link:
                continue
            if link[-1] != '/':
                link += '/'

            link_domain = ''
            link_parts = urlparse(link)
            if link_parts[0] and link_parts[1]:
                link_domain = link_parts[0] + '://' + link_parts[1] + '/'
            if not link_parts[0] and link_parts[1]:
                continue
            if link_domain and link_domain != self.domain:
                continue
            if not link_domain:
                link = self.domain[:-1] + link
            if link in site.leaves_links:
                continue

            founded_site = self._find_site(link)
            if founded_site:
                site.leaves.append(founded_site)
                site.leaves_links.append(link)
            else:
                content_type = self._get_content_type(link)
                if 'text/html' in content_type:
                    new_site = SiteMap(link, site.visited_links[:])
                    site.leaves.append(new_site)
                    site.leaves_links.append(link)
                    self.leaves.append(new_site)
                    self.queue.append(new_site)
        if site.url not in self.visited_links:
            self.visited_links.append(site.url)

    def save_graph(self, name):
        """Сохраняет изображение графа
        :param str name: имя файла
        :return:
        """
        graph = nx.Graph()
        graph.add_nodes_from(self.leaves)
        for leaf in self.leaves:
            for child_leaf in leaf.leaves:
                graph.add_edge(leaf, child_leaf)
        plt.figure(figsize=(10, 10))
        nx.draw(graph, node_color='red', node_size=300, length=10, with_labels=True)
        plt.savefig(name)
