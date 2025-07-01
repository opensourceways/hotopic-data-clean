import logging
from urllib.parse import urlparse

import requests
from abc import ABC, abstractmethod


class BaseValidator(ABC):
    def __init__(self):
        self._session = requests.Session()
        self._session.headers.update({'User-Agent': 'Mozilla/5.0'})

    @abstractmethod
    def validate(self, target: str) -> bool:
        pass

    def _common_request(self, url: str, headers=None) -> requests.Response:
        try:
            return self._session.get(url, headers=headers, timeout=30)
        except requests.exceptions.RequestException:
            return None


class IssueValidator(BaseValidator):
    def validate(self, url: str) -> bool:
        if "gitcode.com" in url:
            parsed = urlparse(url)
            path_segments = [p for p in parsed.path.split('/') if p]
            owner, repo = path_segments[:2]
            api_url = (
                f"https://web-api.gitcode.com/api/v2/projects/{owner}%2F{repo}"
                f"?repoId={owner}%252F{owner}&statistics=true&view=all"
            )
            response = self._common_request(api_url, {"Referer": "https://gitcode.com"})
        elif "gitee.com" in url:
            response = self._common_request(url.split('/issues')[0])
        else:
            return False

        return response and response.status_code == 200


def GetForumValidator(community: str):
    if community == "openubmc":
        return OpenUBMCForumValidator()
    elif community == "cann":
        return CANNForumValidator()
    elif community == "opengauss":
        return None
    elif community == "mindspore":
        return MindSporeForumValidator()
    else:
        raise ValueError(f"不支持的社区: {community}")


class OpenUBMCForumValidator(BaseValidator):
    def validate(self, post_url: str) -> bool:
        response = self._common_request(post_url)
        return response and response.status_code == 200


class CANNForumValidator(BaseValidator):
    def validate(self, post_url: str) -> bool:
        from config.settings import settings
        try:
            # 提取topic_id
            topic_id = post_url.split('-')[1].split('/')[0]

            # 调用论坛详情接口
            response = self._session.get(
                settings.forum_topic_detail_api,
                params={"topicId": topic_id},
                timeout=30
            )

            # 解析响应数据
            if response.status_code == 200:
                resp_data = response.json()
                if (data := resp_data.get("data")) and data.get("error_code") == "HD.65120026":
                    return False
                return True
            return False
        except Exception as e:
            logging.error(f"CANN论坛验证异常: {str(e)}")
            return False


class MindSporeForumValidator(OpenUBMCForumValidator):
    def validate(self, post_url: str) -> bool:
        if "discuss.mindspore.cn" in post_url:
            return super().validate(post_url)
        hi_ascend_validator = CANNForumValidator()
        return hi_ascend_validator.validate(post_url)


class MailValidator(BaseValidator):
    def validate(self, email: str) -> bool:
        return True
