import asyncio
import os
import sys
import time

import httpx
import re
from astrbot import logger
from tenacity import retry, wait_exponential, stop_after_attempt, retry_if_result

from astrbot.core.platform.sources.goofish.goofish_utils import generate_sign


def is_retry_p(value: bool | None) -> bool:
    """Return True if value is None"""
    return not value

class GoofishApis:
    def __init__(self):
        self.url = 'https://h5api.m.goofish.com/h5/mtop.taobao.idlemessage.pc.login.token/1.0/'
        # transport = httpx.AsyncHTTPTransport(retries=3)
        self.session = httpx.AsyncClient()
        self.session.headers.update({
            'accept': 'application/json',
            'accept-language': 'zh-CN,zh;q=0.9',
            'cache-control': 'no-cache',
            'origin': 'https://www.goofish.com',
            'pragma': 'no-cache',
            'priority': 'u=1, i',
            'referer': 'https://www.goofish.com/',
            'sec-ch-ua': '"Not(A:Brand";v="99", "Google Chrome";v="133", "Chromium";v="133"',
            'sec-ch-ua-mobile': '?0',
            'sec-ch-ua-platform': '"Windows"',
            'sec-fetch-dest': 'empty',
            'sec-fetch-mode': 'cors',
            'sec-fetch-site': 'same-site',
            'user-agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/133.0.0.0 Safari/537.36',
        })

        self._is_login = False

    def clear_duplicate_cookies(self):
        """清理重复的cookies"""
        # 创建一个新的CookieJar
        new_jar = httpx.Cookies()

        # 记录已经添加过的cookie名称
        added_cookies = set()

        # 按照cookies列表的逆序遍历（最新的通常在后面）
        cookie_list = self.session.cookies

        for key, val in cookie_list.items():
            # 如果这个cookie名称还没有添加过，就添加到新jar中
            if key not in added_cookies:
                new_jar.set(key, val)
                added_cookies.add(key)

        # 替换session的cookies
        self.session.cookies = new_jar

        # 更新完cookies后，更新.env文件
        self.update_env_cookies()

    def update_env_cookies(self):
        """更新.env文件中的COOKIES_STR"""
        try:
            # 获取当前cookies的字符串形式
            cookie_str = '; '.join([f"{key}={val}" for key, val in self.session.cookies.items()])

            # 读取.env文件
            env_path = os.path.join(os.getcwd(), '.env')
            if not os.path.exists(env_path):
                logger.warning(".env文件不存在，无法更新COOKIES_STR")
                return

            with open(env_path, 'r', encoding='utf-8') as f:
                env_content = f.read()

            # 使用正则表达式替换COOKIES_STR的值
            if 'COOKIES_STR=' in env_content:
                new_env_content = re.sub(
                    r'COOKIES_STR=.*',
                    f'COOKIES_STR={cookie_str}',
                    env_content
                )

                # 写回.env文件
                with open(env_path, 'w', encoding='utf-8') as f:
                    f.write(new_env_content)

                logger.info(f"已更新.env文件中的COOKIES_STR: {new_env_content}")
            else:
                logger.warning(".env文件中未找到COOKIES_STR配置项")
        except Exception as e:
            logger.error(f"更新.env文件失败: {str(e)}")

    @retry(stop=stop_after_attempt(3), wait=wait_exponential(multiplier=1, min=0.2, max=1))
    async def do_login(self) -> bool:
        url = 'https://passport.goofish.com/newlogin/hasLogin.do'
        params = {
            'appName': 'xianyu',
            'fromSite': '77'
        }
        data = {
            'hid': self.session.cookies.get('unb', ''),
            'ltl': 'true',
            'appName': 'xianyu',
            'appEntrance': 'web',
            '_csrf_token': self.session.cookies.get('XSRF-TOKEN', ''),
            'umidToken': '',
            'hsiz': self.session.cookies.get('cookie2', ''),
            'bizParams': 'taobaoBizLoginFrom=web',
            'mainPage': 'false',
            'isMobile': 'false',
            'lang': 'zh_CN',
            'returnUrl': '',
            'fromSite': '77',
            'isIframe': 'true',
            'documentReferer': 'https://www.goofish.com/',
            'defaultView': 'hasLogin',
            'umidTag': 'SERVER',
            'deviceId': self.session.cookies.get('cna', '')
        }

        response = await self.session.post(url, params=params, data=data)
        res_json = response.json()

        if res_json.get('content', {}).get('success'):
            self._is_login = True
            logger.info("Login成功")
            # 清理和更新cookies
            self.clear_duplicate_cookies()
            return True
        else:
            logger.error(f"Login失败: {res_json}")
            self._is_login = False
            return False

    @retry(retry=retry_if_result(is_retry_p))
    async def get_token(self, device_id):
        if not self._is_login:
            logger.warning("获取token失败，尝试重新登陆")
            # 尝试通过hasLogin重新登录
            ret = await self.do_login()
            if ret:
                logger.info("重新登录成功，重新尝试获取token")
                return False
            else:
                logger.error("重新登录失败，Cookie已失效.程序即将退出，请更新.env文件中的COOKIES_STR后重新启动")
                sys.exit(1)  # 直接退出程序

        params = {
            'jsv': '2.7.2',
            'appKey': '34839810',
            't': str(int(time.time()) * 1000),
            'sign': '',
            'v': '1.0',
            'type': 'originaljson',
            'accountSite': 'xianyu',
            'dataType': 'json',
            'timeout': '20000',
            'api': 'mtop.taobao.idlemessage.pc.login.token',
            'sessionOption': 'AutoLoginOnly',
            'spm_cnt': 'a21ybx.im.0.0',
        }
        data_val = '{"appKey":"444e9908a51d1cb236a27862abc769c9","deviceId":"' + device_id + '"}'
        data = {
            'data': data_val,
        }

        # 简单获取token，信任cookies已清理干净
        token = self.session.cookies.get('_m_h5_tk', '').split('_')[0]

        sign = generate_sign(params['t'], token, data_val)
        params['sign'] = sign

        response = await self.session.post('https://h5api.m.goofish.com/h5/mtop.taobao.idlemessage.pc.login.token/1.0/',
                                     params=params, data=data)
        res_json = response.json()

        if isinstance(res_json, dict):
            ret_value = res_json.get('ret', [])
            # 检查ret是否包含成功信息
            if not any('SUCCESS::调用成功' in ret for ret in ret_value):
                logger.error(f"Token API调用失败，错误信息: {ret_value}")
                # 处理响应中的Set-Cookie
                if 'Set-Cookie' in response.headers:
                    logger.debug("检测到Set-Cookie，更新cookie")  # 降级为DEBUG并简化
                    self.clear_duplicate_cookies()
                return False
            else:
                logger.info("Token获取成功!!!")
                return res_json
        else:
            logger.error(f"Token API返回格式异常: {res_json}")
            return False

    @retry(retry=retry_if_result(is_retry_p), stop=stop_after_attempt(3))
    async def get_item_info(self, item_id):
        """获取商品信息，自动处理token失效的情况"""

        params = {
            'jsv': '2.7.2',
            'appKey': '34839810',
            't': str(int(time.time()) * 1000),
            'sign': '',
            'v': '1.0',
            'type': 'originaljson',
            'accountSite': 'xianyu',
            'dataType': 'json',
            'timeout': '20000',
            'api': 'mtop.taobao.idle.pc.detail',
            'sessionOption': 'AutoLoginOnly',
            'spm_cnt': 'a21ybx.im.0.0',
        }

        data_val = '{"itemId":"' + item_id + '"}'
        data = {
            'data': data_val,
        }

        # 简单获取token，信任cookies已清理干净
        token = self.session.cookies.get('_m_h5_tk', '').split('_')[0]

        sign = generate_sign(params['t'], token, data_val)
        params['sign'] = sign

        response = await self.session.post(
            'https://h5api.m.goofish.com/h5/mtop.taobao.idle.pc.detail/1.0/',
            params=params,
            data=data
        )

        res_json = response.json()
        # 检查返回状态
        if isinstance(res_json, dict):
            ret_value = res_json.get('ret', [])
            # 检查ret是否包含成功信息
            if not any('SUCCESS::调用成功' in ret for ret in ret_value):
                logger.warning(f"商品信息API调用失败，错误信息: {ret_value}")
                # 处理响应中的Set-Cookie
                if 'Set-Cookie' in response.headers:
                    logger.debug("检测到Set-Cookie，更新cookie")
                    self.clear_duplicate_cookies()
                time.sleep(0.5)
                return False
            else:
                logger.debug(f"商品信息获取成功: {item_id}")
                return res_json
        else:
            logger.error(f"商品信息API返回格式异常: {res_json}")
            return False


