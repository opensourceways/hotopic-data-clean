import logging
import time
from datetime import datetime, timedelta
import requests
from bs4 import BeautifulSoup
from config.settings import settings
from abc import ABC, abstractmethod
from typing import List, Dict, Optional
from app.data_collect_clean import validator


class BaseCollector(ABC):
    def __init__(self):
        self._session = requests.Session()
        self._session.headers.update({
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/137.0.0.0 Safari/537.36',
        })
        self._validator = self._get_validator()

    def _get_validator(self):
        pass

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
            logging.error(f"Request failed: {e}")
            return None

    @abstractmethod
    def collect(self, start_date: datetime) -> List[Dict]:
        pass

    @property
    @abstractmethod
    def source_name(self) -> str:
        pass

    @abstractmethod
    def _is_valid(self, url: str) -> bool:
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
            logging.error(f"Login failed: {e}")
            return None


class BaseDataStatCollect(BaseCollector, OneIDAPIMixin):
    @property
    def source_name(self) -> str:
        pass

    def _is_valid(self, url: str) -> bool:
        pass

    def __init__(self, community: str, dws_name: str):
        super().__init__()
        self.community = community
        self.dws_name = dws_name
        self._session.headers.update({
            'Referer': 'https://beta.datastat.osinfra.cn/index-dict'
        })

    def _get_filters(self, start_time: datetime) -> List[Dict]:
        return []

    def _get_dim(self) -> List[str]:
        return []

    def _get_valid_page_data(self, page_data):
        return [d for d in page_data if self._is_valid(d['html_url'])]

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
                    "dim": self._get_dim(),
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
            if not page_data:
                break
            all_data.extend(self._get_valid_page_data(page_data))
            page += 1
            time.sleep(0.5)  # 添加请求间隔防止被封
        logging.info(f"共有{len(all_data)}条数据")
        return all_data


class IssueCollector(BaseDataStatCollect):

    def __init__(self, community: str, dws_name: str):
        super().__init__(community, dws_name)

    def _get_validator(self):
        return validator.IssueValidator()

    @property
    def source_name(self) -> str:
        return "issue"

    def _get_filters(self, start_time: datetime) -> List[Dict]:
        return [
            {"column": "is_issue", "operator": "=", "value": "1"},
            {"column": "updated_at", "operator": ">", "value": start_time.strftime("%Y-%m-%d %H:%M:%S")},
            # {"column": "created_at", "operator": ">", "value": start_time.strftime("%Y-%m-%d %H:%M:%S")},
            # {"column": "state", "operator": "=", "value": "open"},
            {"column": "private", "operator": "=", "value": 'false'},
        ]

    def _get_dim(self) -> List[str]:
        return ["uuid", "html_url", "title", "body", "created_at", "updated_at", "state"]

    def collect(self, start_time: datetime) -> List[Dict]:
        raw_data = super().collect(start_time)
        processed_data = []
        for item in raw_data:
            processed_data.append({
                "id": item.get("uuid", "").split('-')[-1],
                "url": item.get("html_url", ""),
                "source_id": item.get("email_id", ""),
                "title": item.get("title", ""),
                "created_at": item.get("created_at", ""),
                "updated_at": item.get("updated_at", ""),
                "body": item.get("body", ""),
                "state": item.get("state", "")
            })
        return processed_data


    def _is_valid(self, url) -> bool:
        return self._validator.validate(url)


class MailCollector(BaseDataStatCollect):
    def __init__(self, community: str, dws_name: str):
        super().__init__(community, dws_name)

    def _get_validator(self):
        return validator.MailValidator()

    @property
    def source_name(self) -> str:
        return "mail"

    def _get_filters(self, start_time: datetime) -> List[Dict]:
        return [
            {"column": "created_at", "operator": ">", "value": start_time.strftime("%Y-%m-%d %H:%M:%S")}
        ]

    def _get_dim(self) -> List[str]:
        return ["uuid", "email_id", "subject", "created_at", "content", "message_id_hash", "list_name", "parent_id"]

    def _get_valid_page_data(self, page_data):
        return [d for d in page_data if self._is_valid(d['uuid'])]

    def collect(self, start_time: datetime) -> List[Dict]:
        raw_data = super().collect(start_time)
        email_id_map = {item["email_id"]: item for item in raw_data}

        processed_data = []
        for item in raw_data:
            parent_id = item.get("parent_id")
            list_name = item.get("list_name", "")
            message_id_hash = item.get("message_id_hash", "")

            if parent_id and (parent := email_id_map.get(parent_id)):
                list_name = parent.get("list_name", "")
                message_id_hash = parent.get("message_id_hash", "")
            url = f"https://mailweb.{settings.community}.org/archives/list/{list_name}/thread/{message_id_hash}"
            processed_data.append({
                "url": url,
                "id": item.get("email_id", ""),
                "title": item.get("subject", ""),
                "created_at": item.get("created_at", ""),
                "body": item.get("content", "")
            })
        return processed_data

    def _is_valid(self, uuid) -> bool:
        return self._validator.validate(uuid)


def get_forum_collector(community: str) -> BaseCollector:
    if community == 'cann':
        return CANNForumCollector()
    elif community == 'openubmc':
        return OpenUBMCForumCollector()
    elif community == 'mindspore':
        return MindSporeForumCollector()
    else:
        raise ValueError(f"Unsupported community: {community}")


class CANNForumCollector(BaseCollector):
    SECTION_IDS = ['0106101385921175004', '0163125572293226003']

    def __init__(self):
        super().__init__()
        self._session.headers.update({'Referer': 'https://www.hiascend.com'})

    def _get_validator(self):
        return validator.CANNForumValidator()

    @property
    def source_name(self) -> str:
        return "forum"

    def collect(self, start_date: datetime):
        all_data = []
        for section_id in self.SECTION_IDS:
            first_page_response = self._fetch_page(section_id, 1)
            if not first_page_response:
                logging.error(f"获取第一页数据失败")
                continue
            logging.info(self._session.headers)
            first_page_data = first_page_response.json().get('data', {})
            total_count = first_page_data.get('totalCount', 0)
            total_pages = (total_count + 99) // 100
            all_data.extend(self._process_page(first_page_data, start_date))

            for page in range(2, total_pages + 1):
                if page_data := self._fetch_page(section_id, page):
                    all_data.extend(self._process_page(page_data.json().get('data', {}), start_date))
                time.sleep(0.5)  # 防止请求过于频繁被封禁
        logging.info(f"共有 {len(all_data)} 个主题")
        return all_data

    def _fetch_page(self, section_id: str, page: int) -> Optional[requests.Response]:
        return self._request(
            'GET',
            settings.forum_api,
            params={
                'sectionId': section_id,
                'filterCondition': '1',
                'pageIndex': page,
                'pageSize': 100,
            }
        )

    def _process_page(self, page_data: dict, start_date: datetime) -> List[Dict]:
        # return [self._parse_topic(t) for t in page_data.get('resultList', [])
        #         if self._is_valid_time(t['createTime'], start_date)]
        return [self._parse_topic(t) for t in page_data.get('resultList', [])
                if self._is_valid_time(t['lastPostTime'], start_date)]

    def _is_valid_time(self, create_time: str, start_date: datetime) -> bool:
        return start_date <= datetime.strptime(create_time, "%Y%m%d%H%M%S")

    def _is_closed(self, topic: dict) -> bool:
        return topic.get('solved', '') == 1

    def _parse_topic(self, topic: dict) -> Dict:
        topicId = topic['topicId']
        return {
            'id': topicId,
            'title': topic['title'],
            'url': f'https://www.hiascend.com/forum/thread-{topicId}-1-1.html',
            'body': self._get_topic_content(topicId),
            'created_at': datetime.strptime(topic['createTime'], "%Y%m%d%H%M%S").strftime('%Y-%m-%d %H:%M:%S'),
            'updated_at': datetime.strptime(topic['lastPostTime'], "%Y%m%d%H%M%S").strftime('%Y-%m-%d %H:%M:%S'),
            'type': 'forum',
            'state': 'closed' if self._is_closed(topic) else 'open',
        }

    def _get_topic_content(self, topic_id: str) -> str:
        response = self._request('GET', settings.forum_topic_detail_api, params={'topicId': topic_id})
        return response.json().get('data', {}).get('result', {}).get('content', '') if response else ''

    def _is_valid(self, url: str) -> bool:
        return self._validator.validate(url)


class OpenUBMCForumCollector(BaseCollector):
    def __init__(self):
        super().__init__()

    def _get_validator(self):
        return validator.OpenUBMCForumValidator()

    @property
    def source_name(self) -> str:
        return "forum"

    def collect(self, start_date) -> List[Dict]:
        all_topics = []
        page = 0
        while data := self._fetch_page(page):
            all_topics.extend(self._process_page(data, start_date))
            if len(data.get('topics', [])) < 30:
                break
            page += 1
        logging.info(f"共有 {len(all_topics)} 个主题")
        return all_topics

    def _fetch_page(self, page: int) -> Optional[dict]:
        response = self._request(
            'GET',
            settings.forum_api,
            params={'page': page, 'no_definitions': True}
        )
        return response.json().get('topic_list', {}) if response else None

    def _process_page(self, page_data: dict, start_date: datetime) -> List[Dict]:
        return [self._parse_topic(t) for t in page_data.get('topics', [])
                if not self._is_excluded_category(t) and self._is_valid_time(t, start_date)]

    def _is_excluded_category(self, topic: dict) -> bool:
        return topic.get('category_id') == 40

    def _is_valid_time(self, topic: dict, start_date: datetime) -> bool:
        # created_at = datetime.strptime(topic['created_at'], '%Y-%m-%dT%H:%M:%S.%fZ')
        # return start_date <= created_at
        last_post_at = datetime.strptime(topic['last_posted_at'], '%Y-%m-%dT%H:%M:%S.%fZ')
        return start_date <= last_post_at

    def _is_closed(self, topic: dict) -> bool:
        return topic.get('has_accepted_answer', False)

    def _parse_topic(self, topic: dict) -> Dict:
        return {
            'id': topic['id'],
            'title': topic['title'],
            'created_at': datetime.strptime(topic['created_at'], '%Y-%m-%dT%H:%M:%S.%fZ').strftime('%Y-%m-%d %H:%M:%S'),
            'updated_at': datetime.strptime(topic['last_posted_at'], '%Y-%m-%dT%H:%M:%S.%fZ').strftime(
                '%Y-%m-%d %H:%M:%S'),
            'body': self._get_topic_body(topic['id']),
            'url': self._get_topic_url(topic['id']),
            'type': 'forum',
            'state': 'closed' if self._is_closed(topic) else 'open'
        }

    def _get_topic_body(self, topic_id: int) -> str:
        response = self._request('GET', settings.forum_topic_detail_api.format(topic_id=topic_id))
        if not response:
            return ''

        post_data = response.json()
        if post_stream := post_data.get('post_stream'):
            first_post = post_stream['posts'][0]
            return BeautifulSoup(first_post.get('cooked', ''), 'html.parser').get_text(separator=' ', strip=True)
        return ''

    def _get_topic_url(self, topic_id: int) -> str:
        response = self._request('GET', settings.forum_topic_detail_api.format(topic_id=topic_id))
        if not response:
            return ''

        post_data = response.json()
        if post_stream := post_data.get('post_stream'):
            post_url = post_stream["posts"][0].get("post_url", "")
            return self._get_forum_url_format().format(post_url=post_url)
        return ''

    def _get_forum_url_format(self):
        return 'https://discuss.openubmc.cn{post_url}'

    def _is_valid(self, url: str) -> bool:
        return self._validator.validate(url)


class MindSporeForumCollector(OpenUBMCForumCollector):
    def __init__(self):
        super().__init__()

    def _get_validator(self):
        return validator.MindSporeForumValidator()

    def _process_page(self, page_data: dict, start_date: datetime) -> List[Dict]:
        return [self._parse_topic(t) for t in page_data.get('topics', [])
                if not self._is_excluded_category(t) and self._is_valid_time(t, start_date)]

    def _fetch_page(self, page: int) -> Optional[dict]:
        response = self._request(
            'GET',
            settings.forum_api,
            params={'page': page, 'no_definitions': True}
        )
        return response.json().get('topic_list', {}) if response else None

    def _is_valid_time(self, topic: dict, start_date: datetime) -> bool:
        # created_at = datetime.strptime(topic['created_at'], '%Y-%m-%dT%H:%M:%S.%fZ')
        # return start_date <= created_at
        last_post_at = datetime.strptime(topic['last_posted_at'], '%Y-%m-%dT%H:%M:%S.%fZ')
        return start_date <= last_post_at

    def _get_forum_url_format(self):
        return 'https://discuss.mindspore.cn{post_url}'
