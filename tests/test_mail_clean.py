import re

def basic_clean(text):
    """
    对输入的文本进行基础清理。

    在清理过程中，去除邮件内容中的发件人、发送日期和收件人等信息，
    以及其他HTML标签和不需要的特殊字符。

    参数:
        text (str): 需要清理的原始文本。

    返回:
        str: 清理后的文本。
    """
    # 去除邮件头中的发件人、发送日期和收件人信息（注意去除整行，包括前后空白）
    text = re.sub(r"(?m)^\s*发件人：.*$", "", text)
    text = re.sub(r"(?m)^\s*发送日期：.*$", "", text)
    text = re.sub(r"(?m)^\s*收件人：.*$", "", text)

    # 去除HTML标签
    text = re.sub(r"<.*?>", "", text)

    # 保留中文、英文、数字和部分中文标点，其他替换为空格
    text = re.sub(r"[^\u4e00-\u9fa5a-zA-Z0-9，。！？；：、]", " ", text)

    # 多个空格合并为一个空格
    text = re.sub(r"\s+", " ", text)

    # 去除多余空白
    return text.strip()

def test_basic_clean():
    test_str = """
    -------- 转发邮件信息 --------
    发件人："张驰" <zhangchi_ming@163.com>
    发送日期：2025-02-08 22:17:47
    收件人：contact@opengauss.org
    主题：openGauss 6.0.0安装扩展失败

    openGauss 6.0.0版如何安装tablefunc扩展或者如何使用postgres里面的crosstab函数。
    目前执行CREATE EXTENSION tablefunc;报错ERROR: could not open extension control file: No such file or directory能否提供技术支持？
    """

    result = basic_clean(test_str)
    print("清理后的文本内容：\n")
    print(result)

if __name__ == "__main__":
    test_basic_clean()
