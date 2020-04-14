import unittest
import requests
from parser import SiteMap, Parser


class TestParser(unittest.TestCase):
    def test_download_page(self):
        url = 'https://python.org'
        response = requests.get(url).text
        parser = Parser(url)
        site = SiteMap(url)
        parser.queue.append(site)
        result = parser._download_page(site)
        self.assertEqual(response, result[1])

    def test_parse(self):
        with open('test.html', 'r') as file:
            text = file.read()
            site = SiteMap('test.html')
            parser = Parser('https://python.org')
            parser._parse(site, text)
        links = ['https://python.org/']
        assert len(site.leaves_links) == len(links)
        for link in links:
            assert link in site.leaves_links

    def test_find_leaf(self):
        url = 'https://python.org'
        site = SiteMap(url)
        parser = Parser('https://google.com')
        parser.leaves.extend([SiteMap('https://yandex.ru'), site, SiteMap('https://yandex.ru')])
        founded = parser._find_site(url)
        self.assertEqual(site, founded)

    def test_breadth(self):
        sites = [SiteMap('https://python.org'), SiteMap('https://pypi.org'), SiteMap('https://google.com'),
                 SiteMap('https://yandex.ru')]
        site = sites[0]
        site_inner = sites[1]
        site_inner.leaves.append(sites[2])
        site.leaves.extend([site_inner, sites[3]])
        breadth_cons = [sites[0], sites[1], sites[3], sites[2]]
        parser = Parser('https://github.com/')
        parser.site_map = site
        breadth = parser.breadth()
        for result, cur in zip(breadth, breadth_cons):
            assert result.url == cur.url

    def test_deep(self):
        sites = [SiteMap('https://python.org'), SiteMap('https://pypi.org'), SiteMap('https://google.com'),
                 SiteMap('https://yandex.ru')]
        site = sites[0]
        site_inner = sites[1]
        site_inner.leaves.append(sites[2])
        site.leaves.extend([site_inner, sites[3]])
        deep_cons = [sites[0], sites[1], sites[2], sites[3]]
        parser = Parser('https://github.com/')
        parser.site_map = site
        deep = parser.deep()
        for result, cur in zip(deep, deep_cons):
            assert result.url == cur.url


if __name__ == '__main__':
    unittest.main()
