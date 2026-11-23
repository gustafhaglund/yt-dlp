#!/usr/bin/env python3

# Allow direct execution
import os
import sys
import unittest
from unittest.mock import patch

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))


from test.helper import FakeYDL
from yt_dlp.extractor.svt import SVTBaseIE, SVTPlayIE, SVTSeriesIE

API_URL = 'https://api.svt.se/videoplayer-api/video/{}'
WEBPAGE = (
    '<meta property="og:description" content="Page description">'
    '<meta property="og:image" content="https://www.svtstatic.se/image/test.jpg">')


class TestSVTPlayIE(unittest.TestCase):
    def _make_ie(self, webpage=None):
        ie = SVTPlayIE(FakeYDL())
        self.requested_json, self.requested_webpages = [], []

        def download_json(url, video_id, **kwargs):
            self.requested_json.append((url, video_id))
            return {'title': 'Test title', 'videoReferences': []}

        def download_webpage(url, video_id, **kwargs):
            if webpage is None:
                self.fail(f'{url} must not be downloaded as a webpage')
            self.requested_webpages.append(url)
            return webpage

        ie._download_json = download_json
        ie._download_webpage = download_webpage
        return ie

    def test_internal_svt_url_uses_video_api(self):
        # https://github.com/yt-dlp/yt-dlp/issues/17352
        info = self._make_ie().extract('svt:abc123')

        self.assertEqual(info['id'], 'abc123')
        self.assertEqual(info['title'], 'Test title')
        self.assertEqual(self.requested_json, [(API_URL.format('abc123'), 'abc123')])

    def test_web_url_with_svt_id_keeps_page_metadata(self):
        for url, svt_id in (
            ('https://www.svtplay.se/video/30479064/husdrommar/x?modalId=8zVbDPA', '8zVbDPA'),
            ('https://www.svt.se/barnkanalen/barnplay/kar/eWv5MLX/', 'eWv5MLX'),
        ):
            with self.subTest(url=url):
                info = self._make_ie(webpage=WEBPAGE).extract(url)

                self.assertEqual(info['id'], svt_id)
                self.assertEqual(info['description'], 'Page description')
                self.assertEqual(info['thumbnail'], 'https://www.svtstatic.se/image/test.jpg')
                self.assertEqual(self.requested_webpages, [url])
                self.assertEqual(self.requested_json, [(API_URL.format(svt_id), svt_id)])


class TestSVTSeriesIE(unittest.TestCase):
    def test_series_entries_resolve_through_svtplay(self):
        # The online SVTSeriesIE tests run with extract_flat='in_playlist' and so never
        # resolve the svt: entries; drive the full series -> url_result -> SVTPlayIE path.
        # Webpage requests are left unmocked so the real network layer would reject svt:
        series = {'data': {'listablesBySlug': [{
            'id': 'jSERIES', 'name': 'Series', 'shortDescription': 'Description',
            'associatedContent': [{'id': 'season-1', 'name': 'Season 1', 'items': [
                {'item': {'videoSvtId': 'abc123'}}, {'item': {'videoSvtId': 'def456'}}]}],
        }]}}
        requested = []

        def download_json(ie, url, video_id, *args, **kwargs):
            requested.append(url)
            if url == 'https://api.svt.se/contento/graphql':
                return series
            return {'title': f'Episode {video_id}', 'videoReferences': [
                {'url': 'https://example.com/video.mp4', 'format': 'mp4'}]}

        ydl = FakeYDL({'simulate': True})
        ydl.add_info_extractor(SVTSeriesIE())
        ydl.add_info_extractor(SVTPlayIE())
        with patch.object(SVTBaseIE, '_download_json', download_json):
            info = ydl.extract_info('https://www.svtplay.se/series', download=False)

        self.assertEqual([e['id'] for e in info['entries']], ['abc123', 'def456'])
        self.assertEqual([e['title'] for e in info['entries']], ['Episode abc123', 'Episode def456'])
        self.assertEqual(requested, [
            'https://api.svt.se/contento/graphql',
            API_URL.format('abc123'), API_URL.format('def456')])


if __name__ == '__main__':
    unittest.main()
