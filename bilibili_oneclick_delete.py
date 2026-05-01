#!/usr/bin/env python3
"""Bilibili 评论和动态一键删除脚本（支持 AICU 导出 JSON 数据）

使用方法:
  1. 安装 Python 3
  2. 安装 requests: pip install requests
  3. 运行: python bilibili_oneclick_delete.py

脚本支持两种评论删除方式：
  1. 使用 AICU 导出的 JSON 数据删除评论
  2. 直接从 B 站评论历史获取并删除评论（若接口受限可能失败）

删除动态仍然使用 B 站接口。
"""

import json
import os
import sys
import time
from typing import Any, Dict, List, Optional, Set

import requests


COMMENT_HISTORY_URL = "https://api.bilibili.com/x/v2/reply/history"
COMMENT_DELETE_URL = "https://api.bilibili.com/x/v2/reply/del"
DYNAMIC_LIST_URL = "https://api.vc.bilibili.com/dynamic_svr/v1/dynamic_svr/space_history"
DYNAMIC_DELETE_URL = "https://api.vc.bilibili.com/dynamic_svr/v1/dynamic_svr/del"


class BilibiliCleaner:
    def __init__(self, sessdata: str, bili_jct: str, dede_uid: str):
        self.sessdata = sessdata.strip()
        self.bili_jct = bili_jct.strip()
        self.dede_uid = dede_uid.strip()
        self.session = requests.Session()
        self.session.headers.update({
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/126.0.0.0 Safari/537.36",
            "Referer": "https://t.bilibili.com/",
            "Origin": "https://t.bilibili.com",
            "Accept": "application/json, text/plain, */*",
            "Accept-Language": "zh-CN,zh;q=0.9",
        })
        self.session.cookies.update({
            "SESSDATA": self.sessdata,
            "bili_jct": self.bili_jct,
            "DedeUserID": self.dede_uid,
        })

    def _check_response(self, resp: requests.Response) -> Dict[str, Any]:
        try:
            data = resp.json()
        except ValueError:
            raise RuntimeError(
                f"无法解析响应 JSON，HTTP {resp.status_code}，内容前缀：{resp.text[:400]!r}"
            )

        if data.get("code") != 0:
            raise RuntimeError(f"请求失败: {data.get('code')} {data.get('message', data)}")
        return data

    def _delete_comment(self, rpid: str, comment_type: str, oid: str) -> None:
        data = {
            "type": str(comment_type),
            "oid": str(oid),
            "rpid": str(rpid),
            "csrf": self.bili_jct,
        }
        resp = self.session.post(COMMENT_DELETE_URL, data=data, timeout=15)
        self._check_response(resp)

    def delete_comments(self) -> None:
        print("开始删除评论历史...")
        page = 1
        total_deleted = 0

        while True:
            params = {"pn": page, "ps": 20, "type": 1}
            resp = self.session.get(COMMENT_HISTORY_URL, params=params, timeout=15)
            data = self._check_response(resp)
            replies = data.get("data", {}).get("list", [])
            if not replies:
                print("评论历史已遍历完成。")
                break

            print(f"第 {page} 页：{len(replies)} 条评论")
            for item in replies:
                rpid = item.get("rpid") or item.get("rpid_str") or item.get("rid")
                comment_type = item.get("type")
                oid = item.get("oid")
                if not rpid or comment_type is None or oid is None:
                    print(f"跳过评论，缺少必要参数：rpid={rpid} type={comment_type} oid={oid}")
                    continue
                try:
                    self._delete_comment(rpid, comment_type, oid)
                    total_deleted += 1
                    print(f"已删除评论 rpid={rpid} type={comment_type} oid={oid}")
                except RuntimeError as exc:
                    print(f"删除评论失败 rpid={rpid} type={comment_type} oid={oid}: {exc}")
                time.sleep(0.4)

            page += 1
            time.sleep(0.8)

        print(f"评论删除完成，总计删除 {total_deleted} 条评论。")

    def delete_comments_from_aicu(self, json_path: str = None, auto_uid: str = None) -> None:
        import requests as _requests
        import tempfile
        import os
        if auto_uid:
            url = f"https://api.aicu.cc/api/v3/search/getreply?uid={auto_uid}&pn=1&ps=500&mode=0"
            print(f"自动请求 AICU: {url}")
            resp = _requests.get(url, timeout=30)
            if resp.status_code != 200:
                raise RuntimeError(f"AICU 查询失败，HTTP {resp.status_code}")
            with tempfile.NamedTemporaryFile(delete=False, suffix='.json', mode='w', encoding='utf-8') as f:
                f.write(resp.text)
                json_path = f.name
            print(f"AICU 数据已自动下载到: {json_path}")
        elif not json_path:
            raise RuntimeError("未指定 AICU JSON 路径且未提供 UID")
        print(f"开始从 AICU JSON 导出文件删除评论：{json_path}")
        references = self._load_comment_references_from_aicu(json_path)
        print(f"已解析到 {len(references)} 条评论引用。开始逐条删除。")

        total_deleted = 0
        for info in references:
            try:
                self._delete_comment(info["rpid"], info["type"], info["oid"])
                total_deleted += 1
                print(f"已删除评论 rpid={info['rpid']} type={info['type']} oid={info['oid']}")
            except RuntimeError as exc:
                print(f"删除评论失败 rpid={info['rpid']} type={info['type']} oid={info['oid']}: {exc}")
            time.sleep(0.5)

        print(f"AICU 评论删除完成，总计删除 {total_deleted} 条评论。")

    def _load_comment_references_from_aicu(self, json_path: str) -> List[Dict[str, str]]:
        if not os.path.exists(json_path):
            raise RuntimeError(f"文件不存在：{json_path}")

        with open(json_path, "r", encoding="utf-8") as f:
            raw = json.load(f)

        if isinstance(raw, dict) and raw.get("data") and isinstance(raw["data"], dict) and "replies" in raw["data"]:
            reply_dicts = raw["data"]["replies"]
        else:
            reply_dicts = self._collect_reply_dicts(raw)

        references: List[Dict[str, str]] = []
        seen: Set[str] = set()

        for item in reply_dicts:
            if not isinstance(item, dict):
                continue

            rpid = (
                item.get("rpid")
                or item.get("rpid_str")
                or item.get("rid")
                or item.get("comment_id")
                or item.get("id")
            )
            dyn = item.get("dyn") if isinstance(item.get("dyn"), dict) else None
            comment_type = None
            oid = None
            if dyn:
                comment_type = dyn.get("type")
                oid = dyn.get("oid")
            if comment_type is None:
                comment_type = item.get("type") or item.get("comment_type")
            if oid is None:
                oid = item.get("oid")

            if not rpid or comment_type is None or oid is None:
                continue

            key = (str(comment_type), str(oid), str(rpid))
            if key in seen:
                continue
            seen.add(key)
            references.append(
                {
                    "rpid": str(rpid),
                    "type": str(comment_type),
                    "oid": str(oid),
                }
            )

        if not references:
            raise RuntimeError(
                "未从 AICU JSON 中提取到有效评论引用，请检查导出文件是否包含 dyn.type/dyn.oid/rpid。"
            )

        return references

    def _collect_reply_dicts(self, node: Any) -> List[Dict[str, Any]]:
        items: List[Dict[str, Any]] = []
        if isinstance(node, dict):
            if any(key in node for key in ("rpid", "rpid_str", "rid", "comment_id", "id")):
                items.append(node)
            for value in node.values():
                items.extend(self._collect_reply_dicts(value))
        elif isinstance(node, list):
            for value in node:
                items.extend(self._collect_reply_dicts(value))
        return items

    def delete_dynamics(self) -> None:
        print("开始删除动态帖子...")
        offset_id = "0"
        total_deleted = 0

        while True:
            params = {
                "host_uid": self.dede_uid,
                "offset_dynamic_id": offset_id,
                "type": 0,
                "need_top": 1,
                "platform": "web",
            }
            resp = self.session.get(DYNAMIC_LIST_URL, params=params, timeout=15)
            data = self._check_response(resp)
            cards = data.get("data", {}).get("cards", [])
            if not cards:
                print("动态列表已遍历完成。")
                break

            print(f"获取到 {len(cards)} 条动态")
            last_id = offset_id
            for card in cards:
                desc = card.get("desc", {})
                dynamic_id = (
                    desc.get("dynamic_id_str")
                    or desc.get("dynamic_id")
                    or desc.get("rid")
                )
                if not dynamic_id:
                    continue
                if dynamic_id == last_id:
                    continue
                try:
                    self._delete_dynamic(dynamic_id)
                    total_deleted += 1
                    print(f"已删除动态 dynamic_id={dynamic_id}")
                except RuntimeError as exc:
                    print(f"删除动态失败 dynamic_id={dynamic_id}: {exc}")
                last_id = dynamic_id
                time.sleep(0.6)

            if last_id == offset_id or last_id == "0":
                break
            offset_id = last_id
            time.sleep(1)

        print(f"动态删除完成，总计删除 {total_deleted} 条动态。")

    def _delete_dynamic(self, dynamic_id: str) -> None:
        data = {"dynamic_id": str(dynamic_id), "csrf_token": self.bili_jct}
        resp = self.session.post(DYNAMIC_DELETE_URL, data=data, timeout=15)
        self._check_response(resp)


def prompt_value(prompt_text: str) -> str:
    value = input(prompt_text).strip()
    if not value:
        print("值不能为空，请重新运行脚本并提供必要参数。")
        sys.exit(1)
    return value


def parse_cookie_string(cookie_string: str) -> Dict[str, str]:
    cookies: Dict[str, str] = {}
    normalized = cookie_string.replace("\n", ";").replace("\r", ";")
    for item in normalized.split(";"):
        if "=" not in item:
            continue
        name, value = item.split("=", 1)
        cookies[name.strip()] = value.strip()
    return cookies


def choose_cookie_input() -> Dict[str, str]:
    cookie_text = input(
        "可直接粘贴完整 Cookie 字符串（包括 SESSDATA、bili_jct、DedeUserID），或留空按回车手动输入：\n"
    ).strip()

    if cookie_text:
        cookies = parse_cookie_string(cookie_text)
        sessdata = cookies.get("SESSDATA", "")
        bili_jct = cookies.get("bili_jct", "")
        dede_uid = cookies.get("DedeUserID", "")
        missing = [
            name
            for name, value in (("SESSDATA", sessdata), ("bili_jct", bili_jct), ("DedeUserID", dede_uid))
            if not value
        ]
        if missing:
            print(
                f"\n提示：Cookie 字符串中缺少以下字段：{', '.join(missing)}。将要求手动补充。\n"
            )
            if not sessdata:
                sessdata = prompt_value("请输入 SESSDATA: ")
            if not bili_jct:
                bili_jct = prompt_value("请输入 bili_jct (csrf): ")
            if not dede_uid:
                dede_uid = prompt_value("请输入 DedeUserID: ")
    else:
        sessdata = prompt_value("请输入 SESSDATA: ")
        bili_jct = prompt_value("请输入 bili_jct (csrf): ")
        dede_uid = prompt_value("请输入 DedeUserID: ")

    return {"SESSDATA": sessdata, "bili_jct": bili_jct, "DedeUserID": dede_uid}


def main() -> None:
    print("Bilibili 一键删除脚本")
    print("此脚本可删除当前账号的评论和动态，删除操作不可恢复。")
    print("请准备好 B 站登录 Cookie: SESSDATA、bili_jct、DedeUserID")
    print("如果只想删除评论或动态，请在提示中选择对应选项。\n")

    cookie_info = choose_cookie_input()
    sessdata = cookie_info["SESSDATA"]
    bili_jct = cookie_info["bili_jct"]
    dede_uid = cookie_info["DedeUserID"]

    print("\n已接收 Cookie 信息。请确认以下内容：")
    print(f"  SESSDATA 长度：{len(sessdata)}")
    print(f"  bili_jct 长度：{len(bili_jct)}")
    print(f"  DedeUserID：{dede_uid}")
    print("请确保 Cookie 信息来自已登录的 B 站账号，否则删除请求会失败。\n")

    cleaner = BilibiliCleaner(sessdata, bili_jct, dede_uid)

    print("请选择要执行的删除任务：")
    print("  1 = AICU 导出 JSON 删除评论")
    print("  2 = 直接从 B 站历史删除评论")
    print("  3 = 删除动态")
    print("  4 = 删除评论和动态（推荐先用 AICU JSON 删除评论）")
    choice = input("输入数字 1/2/3/4，并按回车继续: ").strip()

    if choice not in {"1", "2", "3", "4"}:
        print("输入无效，请重新运行脚本并输入 1、2、3 或 4。")
        sys.exit(1)

    json_path: Optional[str] = None
    auto_uid: Optional[str] = None
    if choice in {"1", "4"}:
        auto_mode = input("是否自动用 DedeUserID 查询 AICU 并下载？(y/N): ").strip().lower()
        if auto_mode == "y":
            auto_uid = dede_uid
        else:
            json_path = input("请输入 AICU 导出 JSON 文件路径（例如：comments.json）：\n").strip()
            if not json_path:
                print("AICU JSON 文件路径不能为空。")
                sys.exit(1)

    print("\n请再次确认：该操作将在当前账号下执行，并将永久删除所选内容。")
    confirm = input("确认继续吗？(y/N): ").strip().lower()
    if confirm != "y":
        print("已取消操作。")
        sys.exit(0)

    if choice == "1":
        cleaner.delete_comments_from_aicu(json_path, auto_uid)
    elif choice == "2":
        cleaner.delete_comments()
    elif choice == "3":
        cleaner.delete_dynamics()
    else:
        cleaner.delete_comments_from_aicu(json_path, auto_uid)
        cleaner.delete_dynamics()

    print("操作完成。")


if __name__ == "__main__":
    try:
        main()
    except Exception as exc:
        print(f"发生错误：{exc}")
        sys.exit(1)
