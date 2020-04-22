# -*- coding: utf-8 -*-
import requests
import sys
import argparse
from concurrent import futures
from urllib.parse import urlparse, urljoin, urlunparse

import networkx as nx
import matplotlib.pyplot as plt
from bs4 import BeautifulSoup

from constants import LINKS_START_WITH, STATUS_CODE_OK, STATUS_CODE_TOO_MANY_REQUESTS, \
    MAX_ATTEMPTS, MAX_DEEP

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
        self.link_parts = urlparse(url)

    def __str__(self):
        return self.url


class BadUrl(Exception):
    """Исключение, вызываемое при неподходящем url"""
    pass


class Parser:
    """Класс, используемый для создания карты сайта"""

    def __init__(self, url):
        """
        Конструктор класса
        :param str url: url страницы
        """
        if url[-1] != '/':  # если ссылка не оканчивается на '/', добавляем '/'
            url += '/'
        self.link_parts = urlparse(url)
        self.url = url
        if not self.link_parts[0] or not self.link_parts[1]:
            raise BadUrl('В url должны быть протокол и домен')
        try:
            response = requests.head(self.url, timeout=namespace.mt)
            if response.status_code != 200:
                raise BadUrl('url недоступен')
        except (requests.ConnectionError, requests.exceptions.TooManyRedirects, requests.exceptions.Timeout):
            raise BadUrl('url недоступен')
        self.site_map = SiteMap(url)
        self.leaves = [self.site_map]
        self.visited_links = []
        self.queue = [self.site_map]
        self.deep_visited = []
        self.next_queue = []

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
        for _ in range(namespace.ma):
            try:
                response = requests.get(site.url)
                if response.status_code == STATUS_CODE_OK:
                    return site, response.text
            except requests.ConnectionError:
                print('Connection error for', site)
                return
            except requests.exceptions.TooManyRedirects:
                print('Too many redirects for', site)
                return
            except requests.exceptions.Timeout:
                print('Timeout for', site)
                return
        return None

    def start(self):
        """Функция для старта построения карты
        :return:
        """
        executor = futures.ThreadPoolExecutor(max_workers=4)
        while self.queue:
            results = executor.map(self._download_page, self.queue)
            for result in results:  # site, response.text
                if result is None:
                    continue
                self._parse(result[0], result[1])
            self.queue = self.next_queue[:]
            self.next_queue = []

    def _get_content_type(self, link):
        """Возвращает content-type страницы
        :param str link: url страницы
        :return: content-type
        """
        content_type = ''
        for _ in range(namespace.ma):
            try:
                response = requests.head(link, timeout=namespace.mt)
                if response.status_code == STATUS_CODE_TOO_MANY_REQUESTS:
                    continue
                if 200 <= response.status_code < 400:
                    if urlparse(response.url)[1] != self.link_parts[1]:
                        continue
                    if 'Content-Type' in response.headers.keys():
                        content_type = response.headers['content-type']
                if content_type:
                    return content_type
            except requests.ConnectionError:
                return
            except requests.exceptions.TooManyRedirects:
                return
            except requests.exceptions.Timeout:
                return

    def _parse(self, site, text):
        """Функция для поиска ссылок в текущем документе и добаления их в очередь для скачивания
        :param SiteMap site: структура, для которой требуется провести поиск
        :param str text: текст текущей страницы
        :return:
        """
        if len(site.visited_links) >= namespace.md:
            return
        print('parsing', site)
        soup = BeautifulSoup(text, 'html.parser')

        site.visited_links.append(site.url)
        for link in soup.find_all('a'):
            link = link.get('href')
            if not link:
                continue
            if any(link.startswith(word) for word in LINKS_START_WITH) or '#' in link or '@' in link:
                continue

            link_parts = urlparse(link)
            if link_parts[0] and link_parts[0] not in ['http', 'https']:
                continue
            if link_parts[1] and link_parts[1] != self.link_parts[1]:
                continue
            if not link_parts[0] and not link_parts[1]:
                link = urljoin(site.url, link)
            if not link_parts[0] and link_parts[1]:
                link = urlunparse(
                    (site.link_parts[0], link_parts[1], link_parts[2], link_parts[3], link_parts[4], link_parts[5]))
            if link in site.leaves_links:
                continue
            founded_site = self._find_site(link)
            if founded_site:
                site.leaves.append(founded_site)
                site.leaves_links.append(link)
            else:
                content_type = self._get_content_type(link)
                if content_type and 'text/html' in content_type:
                    new_site = SiteMap(link, site.visited_links[:])
                    site.leaves.append(new_site)
                    site.leaves_links.append(link)
                    self.leaves.append(new_site)
                    self.next_queue.append(new_site)
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
        size = namespace.s / 100
        plt.figure(figsize=(size, size))
        nx.draw(graph, node_color='red', node_size=300, length=10, with_labels=True, font_color='blue')
        plt.savefig(name)


if __name__ == '__main__':
    argparser = argparse.ArgumentParser(description='Parser')
    argparser.add_argument('link', type=str, help='Input link')
    argparser.add_argument('output', type=str, help='Pic path')
    argparser.add_argument('-size', '--s', type=int, default=1000, help='Pic resolution in px')
    argparser.add_argument('-max_attempt', '--ma', type=int, default=MAX_ATTEMPTS, help='Max requests attempts')
    argparser.add_argument('-max_deep', '--md', type=int, default=MAX_DEEP, help='Max deep for parsing')
    argparser.add_argument('-max_timeout', '--mt', type=int, default=1, help='Max timeout for response')
    namespace = argparser.parse_args()
    try:
        parser = Parser(namespace.link)
        parser.start()
        parser.save_graph(namespace.output)
    except BadUrl as e:
        print(e)
