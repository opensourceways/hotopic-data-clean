import logging
from typing import Optional
from urllib.parse import urlparse

import requests
from abc import ABC, abstractmethod


class BaseValidator(ABC):
    def __init__(self):
        self._session = requests.Session()
        self._session.headers.update({"User-Agent": "Mozilla/5.0"})

    @abstractmethod
    def validate(self, target: str) -> bool:
        pass

    def _common_request(self, url: str, headers=None) -> Optional[requests.Response]:
        try:
            return self._session.get(url, headers=headers, timeout=30)
        except requests.exceptions.RequestException:
            return None


class IssueValidator(BaseValidator):
    def validate(self, target: str) -> bool:
        if "gitcode.com" in target:
            parsed = urlparse(target)
            path_segments = [p for p in parsed.path.split("/") if p]
            owner, repo = path_segments[:2]

            api_url = (
                f"https://web-api.gitcode.com/api/v2/projects/{owner}%2F{repo}/simple"
            )
            response = self._common_request(api_url, {"Referer": "https://gitcode.com"})
            if not (response and response.status_code == 200):
                return False
            try:
                data = response.json()
                if data.get("visibility") == "private":
                    return False
            except Exception:
                return False

            # 从url中提取issue_id
            issue_id = None
            for i, segment in enumerate(path_segments):
                if segment == "issues" and i + 1 < len(path_segments):
                    issue_id = path_segments[i + 1]
                    break
            if not issue_id:
                return False

            issue_api_url = (
                f"https://web-api.gitcode.com/issuepr/api/v1/issue/{owner}%2F{repo}/issues/{issue_id}"
            )
            issue_response = self._common_request(issue_api_url, {"Referer": "https://gitcode.com"})
            if not (issue_response and issue_response.status_code == 200):
                return False

            return True

        elif "gitee.com" in target:
            response = self._common_request(target.split("/issues")[0])
        else:
            return False

        return response is not None and response.status_code == 200


def GetForumValidator(community: str):
    if community == "openubmc":
        return OpenUBMCForumValidator()
    elif community == "cann":
        return CANNForumValidator()
    elif community == "opengauss":
        return None
    elif community == "mindspore":
        return MindSporeForumValidator()
    elif community == "openeuler":
        return OpenEulerForumValidator()
    else:
        raise ValueError(f"不支持的社区: {community}")


class OpenUBMCForumValidator(BaseValidator):
    def validate(self, target: str) -> bool:
        response = self._common_request(target)
        return response is not None and response.status_code == 200


class CANNForumValidator(BaseValidator):
    def validate(self, target: str) -> bool:
        from config.settings import settings

        try:
            # 提取topic_id
            topic_id = target.split("-")[1].split("/")[0]

            # 调用论坛详情接口
            response = self._session.get(
                settings.forum_topic_detail_api,
                params={"topicId": topic_id},
                timeout=30,
            )

            # 解析响应数据
            if response.status_code == 200:
                resp_data = response.json()
                if (data := resp_data.get("data")) and data.get(
                    "error_code"
                ) == "HD.65120026":
                    return False
                return True
            return False
        except Exception as e:
            logging.error(f"CANN论坛验证异常: {str(e)}")
            return False


class MindSporeForumValidator(OpenUBMCForumValidator):
    def validate(self, target: str) -> bool:
        if "discuss.mindspore.cn" in target:
            return super().validate(target)
        hi_ascend_validator = CANNForumValidator()
        return hi_ascend_validator.validate(target)


class MailValidator(BaseValidator):
    def validate(self, target: str) -> bool:
        response = self._common_request(target)
        return response is not None and response.status_code == 200


class OpenEulerForumValidator(OpenUBMCForumValidator):
    pass
    