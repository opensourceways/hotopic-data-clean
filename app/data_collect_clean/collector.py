import time
from datetime import datetime, timedelta
import requests
from bs4 import BeautifulSoup
from config.settings import settings
from abc import ABC, abstractmethod
from typing import List, Dict, Optional


class BaseCollector(ABC):
    def __init__(self):
        self._session = requests.Session()
        self._session.headers.update({
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/137.0.0.0 Safari/537.36',
        })

    def _request(self, method: str, url: str, **kwargs) -> Optional[requests.Response]:
        try:
            response = self._session.request(
                method,
                url,
                timeout=30,
                **kwargs
            )
            response.raise_for_status()
            return response
        except requests.exceptions.RequestException as e:
            print(f"Request failed: {e}")
            return None

    @abstractmethod
    def collect(self, start_date: datetime) -> List[Dict]:
        pass

    @property
    @abstractmethod
    def source_name(self) -> str:
        pass


class OneIDAPIMixin:
    def _login(self) -> Optional[str]:
        try:
            response = self._session.post(
                settings.one_id_api,
                json={
                    "permission": "sigRead",
                    "account": settings.account,
                    "client_id": settings.client_id,
                    "accept_term": 0,
                    "password": settings.password,
                })
            return response.cookies.get('_U_T_', '')
        except Exception as e:
            print(f"Login failed: {e}")
            return None


class BaseDataStatCollect(BaseCollector, OneIDAPIMixin):
    def __init__(self, community: str, dws_name: str):
        super().__init__()
        self.community = community
        self.dws_name = dws_name
        self._session.headers.update({
            'Referer': 'https://beta.datastat.osinfra.cn/index-dict'
        })

    def _get_filters(self, start_time: datetime) -> List[Dict]:
        return []

    def collect(self, start_time: datetime) -> List[Dict]:
        token = self._login()
        if not token:
            raise ValueError("登录失败")

        all_data = []
        page = 1
        while True:
            response = self._request(
                'POST',
                settings.data_api.format(community=self.community),
                headers={'token': token},
                params={"page": page, "page_size": 100},
                json={
                    "community": self.community,
                    "dim": [],
                    "name": self.dws_name,
                    "page": page,
                    "page_size": 100,
                    "filters": self._get_filters(start_time),
                    "conditonsLogic": "AND",
                    "order_field": "uuid",
                    "order_dir": "ASC"
                }
            )
            if not response:
                break

            response_data = response.json()
            page_data = response_data.get('data', [])
            all_data.extend(page_data)

            # 判断是否还有下一页
            total = response_data.get('total', 0)
            if page * 100 >= total:
                break
            page += 1
            time.sleep(1)  # 添加请求间隔防止被封

        return all_data


class IssueCollector(BaseDataStatCollect):

    @property
    def source_name(self) -> str:
        return "issue"

    def _get_filters(self, start_time: datetime) -> List[Dict]:
        return [
            {"column": "is_issue", "operator": "=", "value": "1"},
            {"column": "created_at", "operator": ">", "value": start_time.strftime("%Y-%m-%d %H:%M:%S")}
        ]


class MailCollect(BaseDataStatCollect):
    @property
    def source_name(self) -> str:
        return "mail"

    def _get_filters(self, start_time: datetime) -> List[Dict]:
        return [
            {"column": "created_at", "operator": ">", "value": start_time.strftime("%Y-%m-%d %H:%M:%S")}
        ]


def get_forum_collector(community: str) -> BaseCollector:
    if community == 'cann':
        return CANNForumCollector()
    elif community == 'openubmc':
        return OpenUBMCForumCollector()
    else:
        raise ValueError(f"Unsupported community: {community}")


class CANNForumCollector(BaseCollector):
    SECTION_IDS = ['0106101385921175004', '0163125572293226003']

    def __init(self):
        super().__init__()
        self._session.headers.update({'Referer': 'https://www.hiascend.com'})

    @property
    def source_name(self) -> str:
        return "forum"

    def collect(self, start_date: datetime):
        all_data = []
        for section_id in self.SECTION_IDS:
            first_page_response = self._fetch_page(section_id, 1)
            if not first_page_response:
                print(f"获取第一页数据失败")
                continue

            first_page_data = first_page_response.json().get('data', {})
            total_count = first_page_data.get('totalCount', 0)
            total_pages = (total_count + 99) // 100

            all_data.extend(self._process_page(first_page_data, start_date))

            for page in range(2, total_pages + 1):
                if page_data := self._fetch_page(section_id, page):
                    all_data.extend(self._process_page(page_data.json().get('data', {}), start_date))
                time.sleep(1)  # 防止请求过于频繁被封禁
        return all_data

    def _fetch_page(self, section_id: str, page: int) -> Optional[requests.Response]:
        return self._request(
            'GET',
            settings.cann_forum_api,
            params={
                'sectionId': section_id,
                'filterCondition': '1',
                'pageIndex': page,
                'pageSize': 100,
            }
        )

    def _process_page(self, page_data: dict, start_date: datetime) -> List[Dict]:
        return [self._parse_topic(t) for t in page_data.get('resultList', [])
                if t.get('solved') != 1 and self._is_valid_time(t['createTime'], start_date)]

    def _is_valid_time(self, create_time: str, start_date: datetime) -> bool:
        return datetime.strptime(create_time, "%Y%m%d%H%M%S") > start_date

    def _parse_topic(self, topic: dict) -> Dict:
        topicId = topic['topicId']
        return {
            'id': topicId,
            'title': topic['title'],
            'url': f'https://www.hiascend.com/forum/thread-{topicId}-1-1.html',
            'body': self._get_topic_content(topicId),
            'created_at': datetime.strptime(topic['createTime'], "%Y%m%d%H%M%S").strftime('%Y-%m-%d %H:%M:%S'),
            'type': 'forum',
        }

    def _get_topic_content(self, topic_id: str) -> str:
        response = self._request('GET', settings.cann_forum_topic_detail_api, params={'topicId': topic_id})
        return response.json().get('data', {}).get('result', {}).get('content', '') if response else ''


class OpenUBMCForumCollector(BaseCollector):
    def __init__(self):
        super().__init__()

    @property
    def source_name(self) -> str:
        return "forum"

    def collect(self, start_date) -> List[Dict]:
        all_topics = []
        page = 1
        while data := self._fetch_page(page):
            all_topics.extend(self._process_page(data, start_date))
            if len(data.get('topics', [])) < 30:
                break
            page += 1
        return all_topics

    def _fetch_page(self, page: int) -> Optional[dict]:
        response = self._request(
            'GET',
            settings.openubmc_forum_api,
            params={'page': page, 'no_definitions': True}
        )
        return response.json().get('topic_list', {}) if response else None

    def _process_page(self, page_data: dict, start_date: datetime) -> List[Dict]:
        return [self._parse_topic(t) for t in page_data.get('topics', [])
                if not self._is_excluded_category(t) and self._is_valid_time(t, start_date)]

    def _is_excluded_category(self, topic: dict) -> bool:
        return topic.get('category_id') == 40

    def _is_valid_time(self, topic: dict, start_date: datetime) -> bool:
        created_at = datetime.strptime(topic['created_at'], '%Y-%m-%dT%H:%M:%S.%fZ')
        return start_date <= created_at

    def _parse_topic(self, topic: dict) -> Dict:
        return {
            'id': topic['id'],
            'title': topic['title'],
            'created_at': datetime.strptime(topic['created_at'], '%Y-%m-%dT%H:%M:%S.%fZ').strftime('%Y-%m-%d %H:%M:%S'),
            'body': self._get_topic_body(topic['id']),
            'url': self._get_topic_url(topic['id']),
            'type': 'forum'
        }

    def _get_topic_body(self, topic_id: int) -> str:
        print(topic_id)
        response = self._request('GET', settings.openubmc_forum_topic_detail_api.format(topic_id=topic_id))
        if not response:
            return ''

        post_data = response.json()
        if post_stream := post_data.get('post_stream'):
            first_post = post_stream['posts'][0]
            return BeautifulSoup(first_post.get('cooked', ''), 'html.parser').get_text(separator=' ', strip=True)
        return ''

    def _get_topic_url(self, topic_id: int) -> str:
        response = self._request('GET', settings.openubmc_forum_topic_detail_api.format(topic_id=topic_id))
        if not response:
            return ''

        post_data = response.json()
        if post_stream := post_data.get('post_stream'):
            post_url = post_stream["posts"][0].get("post_url", "")
            return f'https://discuss.openubmc.cn/{post_url}'
        return ''
