"""
baostock 0.9.x 适配辅助

新版 baostock(0.9.x) 收紧了访问格式与行为,本模块集中处理三件事:

1. 登录前应用 API Key: 新版 login() 会把 set_API_key 设置的密钥作为 options
   发送给服务端。旧版 0.8.x 无 set_API_key 函数时自动跳过(匿名访问),不报错。
2. 复权类型归一化: baostock 只接受 adjustflag '1'(后复权)/'2'(前复权)/'3'(不复权)。
3. 错误码可读化: 对激活/权限/账号类错误码补充中文可读提示,便于排查。
"""

import os

import baostock as bs


# 需要补充可读提示的错误码(激活/权限/账号类)
_ERROR_HINTS = {
    '10001002': '用户名或密码错误,请检查 BAOSTOCK_API_KEY 配置。',
    '10001005': '账号登录数达到上限,请退出其他会话后重试。',
    '10001006': '用户权限不足,该接口或数据需要更高权限。',
    '10001007': '账号需要激活,请登录 baostock.com 完成激活后重试。',
    '10001011': '账号已被列入黑名单,请联系 baostock 客服。',
}


def normalize_adjustflag(adjust: str) -> str:
    """复权类型归一化为 baostock 接受的 '1'/'2'/'3'。

    'qfq'(前复权)->'2', 'hfq'(后复权)->'1', 其它(含不复权)->'3'。
    """
    if adjust == 'qfq':
        return '2'
    if adjust == 'hfq':
        return '1'
    return '3'


def describe_error(error_code, error_msg) -> str:
    """对激活/权限类错误码补充可读提示。"""
    hint = _ERROR_HINTS.get(str(error_code))
    if hint:
        return f"{error_msg} (错误码{error_code}: {hint})"
    return f"{error_msg} (错误码{error_code})"


def apply_api_key(api_key=None, logger=None):
    """登录前应用 API Key。

    优先使用传入的 api_key,否则读取环境变量 BAOSTOCK_API_KEY。
    密钥为空则不调用(保持匿名访问);旧版 0.8.x 无 set_API_key 时自动跳过。
    """
    key = (api_key or os.getenv('BAOSTOCK_API_KEY', '') or '').strip()
    if not key:
        return

    if not hasattr(bs, 'set_API_key'):
        if logger:
            logger.debug('当前 baostock 版本无 set_API_key,跳过 API Key(匿名访问)')
        return

    try:
        bs.set_API_key(key)
        if logger:
            logger.debug('已应用 BAOSTOCK_API_KEY')
    except Exception as e:
        if logger:
            logger.warning(f'应用 BAOSTOCK_API_KEY 失败,降级匿名访问: {e}')
