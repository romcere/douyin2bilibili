# Copyright (C) biliup
# Modified by Romcere (2026)
"""
B站视频上传脚本
基于 biliup 项目源码提取的独立上传工具

使用方法:
  1. 先登录，生成 cookies.json:
       python bilibili_upload.py login

  2. 上传视频:
       python bilibili_upload.py upload --file 视频.mp4 --title "视频标题" --tid 21 --tags 标签1 标签2

依赖安装:
  pip install requests aiohttp
"""

import asyncio
import hashlib
import json
import math
import os
import sys
import time
import urllib.parse
from dataclasses import asdict, dataclass, field, InitVar
from os.path import splitext, basename
from threading import Lock
from typing import Optional, List, Any, Union

import aiohttp
import requests
import requests.utils
from requests.adapters import HTTPAdapter, Retry


# ──────────────────────────────────────────────
# 常量
# ──────────────────────────────────────────────

_TV_APP_KEY  = '4409e2ce8ffd12b8'
_TV_APP_SEC  = '59b43e04ad6965f34319062b478f83dd'
_PROBE_URL   = 'https://member.bilibili.com/preupload?r=probe'
_PREUPLOAD_URL = 'https://member.bilibili.com/preupload'
_SUBMIT_URL  = 'https://member.bilibili.com/x/vu/web/add'
_NAV_URL     = 'https://api.bilibili.com/x/web-interface/nav'
_COVER_URL   = 'https://member.bilibili.com/x/vu/web/cover/up'

# CDN 线路名称到查询参数的映射
_CDN_MAP = {
    'bda':  'upcdnbda',
    'bda2': 'upcdnbda2',
    'ws':   'upcdnws',
    'qn':   'upcdnqn',
    'tx':   'upcdntx',
    'txa':  'upcdntxa',
}


# ──────────────────────────────────────────────
# 数据模型
# ──────────────────────────────────────────────

@dataclass
class VideoMeta:
    """
    投稿元数据

    字段说明：
      copyright   : 1=自制, 2=转载
      source      : 转载来源（copyright=2 时填写）
      tid         : 分区 ID（默认 21=日常）
      cover       : 封面 URL（由平台返回）
      title       : 稿件标题（最多 80 字）
      desc        : 稿件简介
      dynamic     : 动态文字
      tag         : 标签，逗号分隔字符串
      videos      : 已上传的分 P 列表
      dtime       : 定时发布时间戳（None 表示立即发布）
      open_subtitle: 是否开启字幕（InitVar，不序列化）
      subtitle    : 字幕配置（由 open_subtitle 生成）
    """
    copyright:     int       = 1
    source:        str       = ''
    tid:           int       = 21
    cover:         str       = ''
    title:         str       = ''
    desc_format_id: int      = 0
    desc:          str       = ''
    dynamic:       str       = ''
    tag:           Union[list, str] = ''
    videos:        list      = field(default_factory=list)
    dtime:         Any       = None
    open_subtitle: InitVar[bool] = False
    subtitle:      dict      = field(init=False)

    def __post_init__(self, open_subtitle: bool):
        self.subtitle = {'open': int(open_subtitle), 'lan': ''}
        # 统一 tag 为逗号分隔字符串
        if isinstance(self.tag, list):
            self.tag = ','.join(str(t) for t in self.tag)

    def set_tags(self, tags: List[str]) -> None:
        """设置标签列表（自动转为逗号字符串）"""
        self.tag = ','.join(str(t) for t in tags)

    def append_part(self, part: dict) -> None:
        """追加一个已上传分 P"""
        self.videos.append(part)

    def to_dict(self) -> dict:
        """序列化为 API 提交所需字典，自动剔除 None 字段"""
        raw = asdict(self)
        return {k: v for k, v in raw.items() if v is not None}


# ──────────────────────────────────────────────
# 登录模块（单一职责：只负责鉴权）
# ──────────────────────────────────────────────

class BiliAuth:
    """
    B 站登录与凭证管理

    职责：
      - 从文件加载 / 保存 Cookie
      - TV 端二维码扫码登录
      - 向 session 注入已登录状态
    """

    def __init__(self, session: requests.Session):
        self._session = session
        self.cookies: dict = {}
        self.access_token: Optional[str] = None
        self.bili_jct: Optional[str] = None

    # ── 公共接口 ──────────────────────────────

    def load_or_login(self, cookie_file: str = 'cookies.json') -> None:
        """
        优先从文件恢复登录态；
        文件不存在或 Cookie 已失效时自动发起扫码登录。
        """
        if os.path.isfile(cookie_file):
            print(f'[INFO] 读取 Cookie 文件: {cookie_file}')
            self._load_file(cookie_file)
            try:
                self._apply_to_session()
                return
            except Exception as e:
                print(f'[WARN] Cookie 登录失败: {e}，尝试扫码登录')
        print('[INFO] 未找到有效 Cookie，启动扫码登录...')
        self.qrcode_login(cookie_file)

    def qrcode_login(self, cookie_file: str = 'cookies.json') -> None:
        """TV 端二维码扫码登录，成功后保存 Cookie 到文件"""
        auth_code, qr_url = self._request_qrcode()
        self._print_qrcode(qr_url)
        self._poll_qrcode(auth_code, cookie_file)

    # ── 私有：文件读写 ─────────────────────────

    def _load_file(self, cookie_file: str) -> None:
        with open(cookie_file) as f:
            self.cookies = json.load(f)
        self.access_token = self.cookies.get('token_info', {}).get('access_token')

    def _save_file(self, cookie_file: str) -> None:
        with open(cookie_file, 'w') as f:
            json.dump(self.cookies, f, ensure_ascii=False, indent=2)
        print(f'[INFO] Cookie 已保存至 {cookie_file}')

    # ── 私有：Session 注入 ────────────────────

    def _apply_to_session(self) -> None:
        """将已加载的 Cookie 注入 session，并校验登录态"""
        cookies_list = self.cookies.get('cookie_info', {}).get('cookies', [])
        cookies_dict = {c['name']: c['value'] for c in cookies_list}
        requests.utils.add_dict_to_cookiejar(self._session.cookies, cookies_dict)
        self.bili_jct = cookies_dict.get('bili_jct')

        r = self._session.get(_NAV_URL, timeout=5).json()
        if r['code'] != 0:
            raise Exception(r)
        uname = r.get('data', {}).get('uname', '未知')
        print(f'[INFO] 登录成功，用户: {uname}')

    # ── 私有：二维码登录流程 ───────────────────

    @staticmethod
    def _tv_sign(params: dict) -> str:
        """生成 TV 端 API 签名"""
        qs = urllib.parse.urlencode(params)
        return hashlib.md5(f'{qs}{_TV_APP_SEC}'.encode()).hexdigest()

    def _request_qrcode(self) -> tuple[str, str]:
        """向服务器申请二维码，返回 (auth_code, qr_url)"""
        params = {
            'appkey': _TV_APP_KEY,
            'local_id': '0',
            'ts': int(time.time()),
        }
        params['sign'] = self._tv_sign(params)
        r = self._session.post(
            'http://passport.bilibili.com/x/passport-tv-login/qrcode/auth_code',
            data=params, timeout=5
        ).json()
        if r['code'] != 0:
            raise Exception(f'获取二维码失败: {r}')
        return r['data']['auth_code'], r['data']['url']

    @staticmethod
    def _print_qrcode(url: str) -> None:
        print(f'\n请用 B 站 APP 扫描以下二维码登录:\n{url}\n')
        try:
            import qrcode
            qr = qrcode.QRCode()
            qr.add_data(url)
            qr.print_ascii(invert=True)
        except ImportError:
            print('（安装 qrcode 库可在终端显示二维码: pip install qrcode）')

    def _poll_qrcode(self, auth_code: str, cookie_file: str, timeout: int = 240) -> None:
        """轮询扫码结果，成功后保存 Cookie"""
        params = {
            'appkey': _TV_APP_KEY,
            'auth_code': auth_code,
            'local_id': '0',
            'ts': int(time.time()),
        }
        params['sign'] = self._tv_sign(params)

        for elapsed in range(0, timeout, 2):
            time.sleep(2)
            resp = self._session.post(
                'http://passport.bilibili.com/x/passport-tv-login/qrcode/poll',
                data=params, timeout=5
            ).json()
            if resp['code'] == 0:
                self.cookies = resp['data']
                self.access_token = resp['data']['token_info']['access_token']
                self._save_file(cookie_file)
                # 重新加载以统一格式，再注入 session
                self._load_file(cookie_file)
                self._apply_to_session()
                return
            if resp['code'] == 86038:
                raise Exception('二维码已过期')
            print(f'\r[INFO] 等待扫码... ({elapsed}s)', end='', flush=True)
        raise Exception('扫码超时')


# ──────────────────────────────────────────────
# 线路探测模块（单一职责：只负责选线）
# ──────────────────────────────────────────────

class LineProber:
    """
    上传线路探测

    职责：
      - 根据用户指定的 CDN 直接构造线路信息
      - 或通过测速自动选择最优线路
    """

    def __init__(self, session: requests.Session):
        self._session = session

    def resolve(self, lines: str = 'AUTO') -> dict:
        """
        返回线路信息字典，结构：
          {'os': str, 'query': str, 'probe_url': str}
        """
        cdn = _CDN_MAP.get(lines.lower())
        if cdn:
            return {
                'os': 'upos',
                'query': f'upcdn={cdn}&probe_version=20221109',
                'probe_url': f'//{cdn}.bilivideo.com/OK',
            }
        print('[INFO] 自动探测最优线路...')
        return self._probe()

    def _probe(self) -> dict:
        ret = self._session.get(_PROBE_URL, timeout=5).json()
        method = 'get' if ret['probe'].get('get') else 'post'
        probe_data = bytes(int(1024 * 0.1 * 1024)) if method == 'post' else None

        best, min_cost = None, float('inf')
        for line in ret['lines']:
            start = time.perf_counter()
            resp = self._session.request(
                method, f"https:{line['probe_url']}", data=probe_data, timeout=30
            )
            cost = time.perf_counter() - start
            if resp.status_code == 200 and cost < min_cost:
                best, min_cost = line, cost

        if best is None:
            raise Exception('所有线路探测失败')
        best['cost'] = min_cost
        print(f"[INFO] 选定线路: os={best['os']} cost={min_cost:.3f}s")
        return best


# ──────────────────────────────────────────────
# 文件上传模块（单一职责：只负责分片上传）
# ──────────────────────────────────────────────

class UposUploader:
    """
    UPOS 分片上传器

    职责：
      - 申请上传凭证
      - 并发上传分片（线程安全的文件读取）
      - 合并分片并返回分 P 信息
    """

    def __init__(self, session: requests.Session, line_info: dict):
        self._session = session
        self._line    = line_info

    def upload(self, filepath: str, tasks: int = 3) -> dict:
        """
        上传文件，返回分 P 信息字典：
          {'title': str, 'filename': str, 'desc': str}
        """
        if self._line['os'] != 'upos':
            raise NotImplementedError(f"暂不支持 {self._line['os']} 线路")

        total_size = os.path.getsize(filepath)
        with open(filepath, 'rb') as f:
            ret = self._preupload(f.name, total_size)
            return asyncio.run(self._async_upload(f, total_size, ret, tasks))

    # ── 私有：预上传申请 ──────────────────────

    def _preupload(self, filename: str, total_size: int) -> dict:
        query = {
            'r':       'upos',
            'profile': 'ugcupos/bup',
            'ssl':     0,
            'version': '2.8.12',
            'build':   2081200,
            'name':    os.path.basename(filename),
            'size':    total_size,
        }
        resp = self._session.get(
            f'{_PREUPLOAD_URL}?{self._line["query"]}',
            params=query, timeout=5
        )
        return resp.json()

    # ── 私有：异步分片上传 ─────────────────────

    async def _async_upload(self, file, total_size: int, ret: dict, tasks: int) -> dict:
        chunk_size = ret['chunk_size']
        auth       = ret['auth']
        endpoint   = ret['endpoint']
        biz_id     = ret['biz_id']
        upos_uri   = ret['upos_uri']
        url        = f"https:{endpoint}/{upos_uri.replace('upos://', '')}"
        headers    = {'X-Upos-Auth': auth}

        # 申请 upload_id
        upload_id = self._session.post(
            f'{url}?uploads&output=json', timeout=15, headers=headers
        ).json()['upload_id']

        chunks     = math.ceil(total_size / chunk_size)
        parts: list = []
        read_lock  = Lock()  # 保证多 worker 串行读取文件
        chunk_idx  = [-1]    # 使用列表以便闭包内修改
        start_time = time.perf_counter()

        async def upload_one_chunk(session: aiohttp.ClientSession) -> None:
            """单个 worker：循环读取并上传分片，直到文件读完"""
            while True:
                with read_lock:
                    data = file.read(chunk_size)
                    if not data:
                        return
                    chunk_idx[0] += 1
                    idx = chunk_idx[0]

                size  = len(data)
                start = idx * chunk_size
                end   = start + size
                params = {
                    'uploadId':   upload_id,
                    'chunks':     chunks,
                    'total':      total_size,
                    'chunk':      idx,
                    'size':       size,
                    'partNumber': idx + 1,
                    'start':      start,
                    'end':        end,
                }
                # 单片重试最多 10 次
                for attempt in range(10):
                    try:
                        async with session.put(
                            url, params=params, data=data,
                            headers=headers, raise_for_status=True
                        ):
                            elapsed = time.perf_counter() - start_time
                            parts.append({'partNumber': idx + 1, 'eTag': 'etag'})
                            sys.stdout.write(
                                f"\r[上传] {end / 1e6 / elapsed:.2f} MB/s  "
                                f"{idx + 1}/{chunks} ({(idx + 1) / chunks:.0%})"
                            )
                            sys.stdout.flush()
                            break
                    except (asyncio.TimeoutError, aiohttp.ClientError) as e:
                        print(f'\n[WARN] chunk{idx} 第 {attempt + 1} 次重试: {e}')
                else:
                    raise Exception(f'chunk{idx} 超过最大重试次数，上传失败')

        async with aiohttp.ClientSession() as session:
            await asyncio.gather(*[upload_one_chunk(session) for _ in range(tasks)])

        cost = time.perf_counter() - start_time
        print()

        # 合并分片（最多重试 5 次）
        parts.sort(key=lambda p: p['partNumber'])  # 确保顺序正确
        merge_params = {
            'name':     file.name,
            'uploadId': upload_id,
            'biz_id':   biz_id,
            'output':   'json',
            'profile':  'ugcupos/bup',
        }
        for attempt in range(5):
            try:
                r = self._session.post(
                    url, params=merge_params,
                    json={'parts': parts}, headers=headers, timeout=15
                ).json()
                if r.get('OK') == 1:
                    print(f'[INFO] 上传完成，平均速度: {total_size / 1e6 / cost:.2f} MB/s')
                    return {
                        'title':    splitext(os.path.basename(file.name))[0],
                        'filename': splitext(basename(upos_uri))[0],
                        'desc':     '',
                    }
                raise IOError(r)
            except IOError:
                print(f'\n[WARN] 合并分片失败，第 {attempt + 1}/5 次重试...')
                time.sleep(15)
        raise Exception('上传失败：分片合并超过最大重试次数')


# ──────────────────────────────────────────────
# 封面上传模块（单一职责：只负责封面处理）
# ──────────────────────────────────────────────

class CoverUploader:
    """
    封面图片上传器

    职责：
      - 将本地图片上传至 B 站并返回封面 URL
    """

    def __init__(self, session: requests.Session, bili_jct: str):
        self._session  = session
        self._bili_jct = bili_jct

    def upload(self, cover_path: str) -> str:
        """上传封面，返回去除协议头的 URL（//...）"""
        with open(cover_path, 'rb') as f:
            mime = self._guess_mime(cover_path)
            r = self._session.post(
                f'{_COVER_URL}?csrf={self._bili_jct}',
                files={'cover': (os.path.basename(cover_path), f, mime)},
                timeout=15
            ).json()
        if r['code'] != 0:
            raise Exception(f'封面上传失败: {r}')
        url: str = r['data']['url']
        return url.replace('http:', '').replace('https:', '')

    @staticmethod
    def _guess_mime(path: str) -> str:
        ext = os.path.splitext(path)[-1].lower()
        return {'jpg': 'image/jpeg', '.jpeg': 'image/jpeg',
                '.png': 'image/png', '.gif': 'image/gif',
                '.webp': 'image/webp'}.get(ext, 'image/jpeg')


# ──────────────────────────────────────────────
# 投稿提交模块（单一职责：只负责提交稿件）
# ──────────────────────────────────────────────

class SubmitClient:
    """
    稿件提交客户端

    职责：
      - 调用 Web API 提交投稿
    """

    def __init__(self, session: requests.Session, bili_jct: str):
        self._session  = session
        self._bili_jct = bili_jct

    def submit(self, meta: VideoMeta) -> dict:
        """提交投稿，返回原始 API 响应"""
        # 触发极验预检（降低风控概率）
        self._session.get('https://member.bilibili.com/x/geetest/pre/add', timeout=5)

        payload = meta.to_dict()
        r = self._session.post(
            f'{_SUBMIT_URL}?csrf={self._bili_jct}',
            json=payload, timeout=5
        ).json()
        if r['code'] != 0:
            raise Exception(f'投稿失败: {r}')
        return r


# ──────────────────────────────────────────────
# 会话工厂（统一创建共享 Session）
# ──────────────────────────────────────────────

def _make_session() -> requests.Session:
    """创建带重试策略和默认请求头的 Session"""
    session = requests.Session()
    session.mount('https://', HTTPAdapter(
        max_retries=Retry(total=5, backoff_factor=0.5,
                          status_forcelist=[500, 502, 503, 504])
    ))
    session.headers.update({
        'user-agent': 'Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 Chrome/63.0.3239.108',
        'referer':    'https://www.bilibili.com/',
    })
    return session


# ──────────────────────────────────────────────
# 高级封装（门面函数，对外唯一接口）
# ──────────────────────────────────────────────

def upload_video(
        file_path:   str,
        title:       str,
        tid:         int            = 21,
        tags:        Optional[List[str]] = None,
        desc:        str            = '',
        copyright:   int            = 1,
        source:      str            = '',
        cover_path:  Optional[str]  = None,
        lines:       str            = 'AUTO',
        threads:     int            = 3,
        cookie_file: str            = 'cookies.json',
) -> dict:
    """
    上传视频到 B 站（门面函数）

    :param file_path:   本地视频文件路径
    :param title:       视频标题（最多 80 字）
    :param tid:         分区 ID，默认 21（日常）
    :param tags:        标签列表
    :param desc:        视频简介
    :param copyright:   1=自制, 2=转载
    :param source:      转载来源（copyright=2 时填写）
    :param cover_path:  封面图片本地路径（可选）
    :param lines:       上传线路：AUTO / bda / bda2 / ws / qn / tx / txa
    :param threads:     并发上传线程数
    :param cookie_file: Cookie 文件路径
    :return:            B 站 API 原始响应字典
    """
    # ── 构建元数据（在此处统一赋值，避免 dataclass 默认值覆盖问题）──
    meta = VideoMeta(
        title     = title[:80],
        tid       = tid,          # 直接通过构造函数传入，确保赋值生效
        desc      = desc,
        copyright = copyright,
        source    = source,
    )
    if tags:
        meta.set_tags(tags)

    session = _make_session()
    try:
        # ── 登录 ──────────────────────────────
        auth = BiliAuth(session)
        auth.load_or_login(cookie_file)

        # ── 上传视频文件 ──────────────────────
        print(f'[INFO] 开始上传: {file_path}')
        line_info = LineProber(session).resolve(lines)
        part      = UposUploader(session, line_info).upload(file_path, tasks=threads)
        part['title'] = part['title'][:80]
        meta.append_part(part)

        # ── 上传封面（可选）──────────────────
        if cover_path:
            print(f'[INFO] 上传封面: {cover_path}')
            meta.cover = CoverUploader(session, auth.bili_jct).upload(cover_path)

        # ── 提交投稿 ──────────────────────────
        print('[INFO] 提交投稿...')
        ret  = SubmitClient(session, auth.bili_jct).submit(meta)
        bvid = ret.get('data', {}).get('bvid', '未知')
        print(f'[SUCCESS] 投稿成功！BV号: {bvid}')
        return ret
    finally:
        session.close()


# ──────────────────────────────────────────────
# CLI 入口
# ──────────────────────────────────────────────

def main() -> None:
    import argparse

    parser = argparse.ArgumentParser(description='B 站视频上传工具')
    sub    = parser.add_subparsers(dest='cmd')

    # ── 登录子命令 ────────────────────────────
    login_p = sub.add_parser('login', help='扫码登录并保存 Cookie')
    login_p.add_argument('--cookie', default='cookies.json', help='Cookie 保存路径')

    # ── 上传子命令 ────────────────────────────
    up_p = sub.add_parser('upload', help='上传视频')
    up_p.add_argument('--file',      required=True,         help='视频文件路径')
    up_p.add_argument('--title',     required=True,         help='视频标题')
    up_p.add_argument('--tid',       type=int, default=21,  help='分区 ID（默认 21=日常）')
    up_p.add_argument('--tags',      nargs='*', default=[], help='标签列表')
    up_p.add_argument('--desc',      default='',            help='视频简介')
    up_p.add_argument('--copyright', type=int, default=1,   help='1=自制  2=转载')
    up_p.add_argument('--source',    default='',            help='转载来源')
    up_p.add_argument('--cover',     default=None,          help='封面图片路径')
    up_p.add_argument('--lines',     default='AUTO',        help='上传线路')
    up_p.add_argument('--threads',   type=int, default=3,   help='并发线程数')
    up_p.add_argument('--cookie',    default='cookies.json', help='Cookie 文件路径')

    args = parser.parse_args()

    if args.cmd == 'login':
        session = _make_session()
        try:
            BiliAuth(session).qrcode_login(args.cookie)
        finally:
            session.close()

    elif args.cmd == 'upload':
        if not os.path.isfile(args.file):
            print(f'[ERROR] 文件不存在: {args.file}')
            sys.exit(1)
        upload_video(
            file_path   = args.file,
            title       = args.title,
            tid         = args.tid,
            tags        = args.tags,
            desc        = args.desc,
            copyright   = args.copyright,
            source      = args.source,
            cover_path  = args.cover,
            lines       = args.lines,
            threads     = args.threads,
            cookie_file = args.cookie,
        )
    else:
        parser.print_help()


if __name__ == '__main__':
    main()