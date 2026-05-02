import os
import re
import time
import random
import threading
import json
from pathlib import Path
from typing import Optional, Dict, Any, Set
from curl_cffi import requests
from utils import config as cfg

_OUTLOOK_EMAIL_PLUS_LOCK = threading.Lock()
_OUTLOOK_EMAIL_PLUS_LAST_REQ_TIME = 0.0
_OUTLOOK_EMAIL_PLUS_REQ_INTERVAL = 1.0
_REGISTERED_EMAILS_FILE = os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))), "已注册邮箱.txt")


class OutlookEmailPlusService:
    """本地 Outlook Email Plus 邮箱池服务"""
    
    def __init__(self, api_key: str, base_url: str, proxies: dict = None):
        if not api_key:
            raise ValueError("OutlookEmailPlus API_KEY 不能为空！请检查配置。")
        if not base_url:
            raise ValueError("OutlookEmailPlus BASE_URL 不能为空！请检查配置。")

        self.api_key = api_key
        self.base_url = base_url.rstrip("/")
        self.proxies = proxies
        self._registered_emails = self._load_registered_emails()
        self._caller_id = f"wenfxl_{int(time.time())}_{random.randint(1000, 9999)}"
        
    def _load_registered_emails(self) -> Set[str]:
        """加载已注册邮箱列表"""
        registered = set()
        try:
            if os.path.exists(_REGISTERED_EMAILS_FILE):
                with open(_REGISTERED_EMAILS_FILE, "r", encoding="utf-8") as f:
                    for line in f:
                        email = line.strip().lower()
                        if email and "@" in email:
                            registered.add(email)
                print(f"[{cfg.ts()}] [OutlookEmailPlus] 已加载 {len(registered)} 个已注册邮箱到排除列表")
        except Exception as e:
            print(f"[{cfg.ts()}] [WARNING] 加载已注册邮箱文件失败: {e}")
        return registered

    def _add_to_registered(self, email: str):
        """将邮箱添加到已注册列表"""
        try:
            email = email.strip().lower()
            if email and email not in self._registered_emails:
                with _OUTLOOK_EMAIL_PLUS_LOCK:
                    with open(_REGISTERED_EMAILS_FILE, "a", encoding="utf-8") as f:
                        f.write(f"{email}\n")
                    self._registered_emails.add(email)
        except Exception as e:
            print(f"[{cfg.ts()}] [WARNING] 写入已注册邮箱文件失败: {e}")

    def _check_email_registered(self, email: str) -> bool:
        """检查邮箱是否已注册"""
        return email.strip().lower() in self._registered_emails

    def _make_headers(self) -> dict:
        return {
            "X-API-Key": self.api_key,
            "Content-Type": "application/json"
        }

    def _make_request(self, method: str, path: str, **kwargs) -> dict:
        """发送API请求"""
        url = f"{self.base_url}{path}"
        headers = self._make_headers()
        
        global _OUTLOOK_EMAIL_PLUS_LAST_REQ_TIME
        
        with _OUTLOOK_EMAIL_PLUS_LOCK:
            now = time.time()
            elapsed = now - _OUTLOOK_EMAIL_PLUS_LAST_REQ_TIME
            if elapsed < _OUTLOOK_EMAIL_PLUS_REQ_INTERVAL:
                time.sleep(_OUTLOOK_EMAIL_PLUS_REQ_INTERVAL - elapsed)
            _OUTLOOK_EMAIL_PLUS_LAST_REQ_TIME = time.time()

        max_retries = 3
        for attempt in range(max_retries):
            try:
                if method.upper() == "GET":
                    resp = requests.get(url, headers=headers, proxies=self.proxies, timeout=30, impersonate="chrome110")
                else:
                    resp = requests.post(url, headers=headers, json=kwargs.get("json", {}), proxies=self.proxies, timeout=30, impersonate="chrome110")
                
                if resp.status_code in [429, 502, 503, 504]:
                    print(f"[{cfg.ts()}] [OutlookEmailPlus] 网关限流 ({resp.status_code})，正在进行第 {attempt + 1} 次重试...")
                    time.sleep(2 * (attempt + 1))
                    continue

                res_data = resp.json()
                return res_data
                
            except Exception as e:
                if attempt == max_retries - 1:
                    raise Exception(f"OutlookEmailPlus API请求异常 (已重试{max_retries}次): {e}")
                time.sleep(1.5)

    def health_check(self) -> bool:
        """检查服务健康状态"""
        try:
            result = self._make_request("GET", "/api/external/health")
            return result.get("success", False)
        except Exception as e:
            print(f"[{cfg.ts()}] [OutlookEmailPlus] 健康检查失败: {e}")
            return False

    def get_capabilities(self) -> dict:
        """获取服务能力"""
        try:
            return self._make_request("GET", "/api/external/capabilities")
        except Exception as e:
            print(f"[{cfg.ts()}] [OutlookEmailPlus] 获取能力失败: {e}")
            return {}

    def claim_random_email(self, task_id: str = None) -> Optional[Dict[str, Any]]:
        """从邮箱池领取随机邮箱"""
        if not task_id:
            task_id = f"task_{int(time.time())}_{random.randint(1000, 9999)}"

        payload = {
            "caller_id": self._caller_id,
            "task_id": task_id,
            "provider": "outlook"
        }

        max_attempts = 10
        for attempt in range(max_attempts):
            try:
                result = self._make_request("POST", "/api/external/pool/claim-random", json=payload)
                
                if result.get("success"):
                    email = result.get("data", {}).get("email", "").strip().lower()
                    
                    if self._check_email_registered(email):
                        print(f"[{cfg.ts()}] [OutlookEmailPlus] 邮箱 {email} 已在排除列表中，释放并重新领取...")
                        account_id = result.get("data", {}).get("account_id")
                        claim_token = result.get("data", {}).get("claim_token")
                        if account_id and claim_token:
                            self.release_email(account_id, claim_token, task_id)
                        continue
                    
                    print(f"[{cfg.ts()}] [OutlookEmailPlus] 成功领取邮箱: {email}")
                    return {
                        "email": email,
                        "account_id": result.get("data", {}).get("account_id"),
                        "claim_token": result.get("data", {}).get("claim_token"),
                        "task_id": task_id,
                        "caller_id": self._caller_id
                    }
                else:
                    code = result.get("code", "")
                    if code == "no_available_account":
                        print(f"[{cfg.ts()}] [OutlookEmailPlus] 邮箱池中没有可用邮箱")
                        return None
                    else:
                        print(f"[{cfg.ts()}] [OutlookEmailPlus] 领取邮箱失败: {result.get('message', '未知错误')}")
                        return None
                        
            except Exception as e:
                print(f"[{cfg.ts()}] [OutlookEmailPlus] 领取邮箱异常 (第{attempt + 1}次): {e}")
                if attempt == max_attempts - 1:
                    return None
                time.sleep(2)

        return None

    def release_email(self, account_id: int, claim_token: str, task_id: str = None) -> bool:
        """释放邮箱"""
        if not task_id:
            task_id = f"task_{int(time.time())}_{random.randint(1000, 9999)}"

        payload = {
            "account_id": account_id,
            "claim_token": claim_token,
            "caller_id": self._caller_id,
            "task_id": task_id,
            "reason": "manual_release"
        }

        try:
            result = self._make_request("POST", "/api/external/pool/claim-release", json=payload)
            if result.get("success"):
                print(f"[{cfg.ts()}] [OutlookEmailPlus] 成功释放邮箱 account_id: {account_id}")
                return True
            else:
                print(f"[{cfg.ts()}] [OutlookEmailPlus] 释放邮箱失败: {result.get('message', '未知错误')}")
                return False
        except Exception as e:
            print(f"[{cfg.ts()}] [OutlookEmailPlus] 释放邮箱异常: {e}")
            return False

    def complete_email(self, account_id: int, claim_token: str, task_id: str, result: str = "success", detail: str = "") -> bool:
        """完成邮箱使用"""
        payload = {
            "account_id": account_id,
            "claim_token": claim_token,
            "caller_id": self._caller_id,
            "task_id": task_id,
            "result": result,
            "detail": detail
        }

        try:
            resp = self._make_request("POST", "/api/external/pool/claim-complete", json=payload)
            if resp.get("success"):
                print(f"[{cfg.ts()}] [OutlookEmailPlus] 成功完成邮箱 account_id: {account_id}")
                return True
            else:
                print(f"[{cfg.ts()}] [OutlookEmailPlus] 完成邮箱失败: {resp.get('message', '未知错误')}")
                return False
        except Exception as e:
            print(f"[{cfg.ts()}] [OutlookEmailPlus] 完成邮箱异常: {e}")
            return False

    def get_verification_code(self, email: str, code_length: int = None, timeout_seconds: int = 30) -> Optional[str]:
        """获取验证码"""
        params = {
            "email": email,
            "timeout_seconds": timeout_seconds
        }
        if code_length:
            params["code_length"] = code_length

        try:
            url = f"{self.base_url}/api/external/verification-code"
            headers = self._make_headers()
            
            resp = requests.get(url, headers=headers, params=params, proxies=self.proxies, timeout=timeout_seconds + 10, impersonate="chrome110")
            result = resp.json()
            
            if result.get("success"):
                code = result.get("data", {}).get("code", "")
                if code:
                    print(f"[{cfg.ts()}] [OutlookEmailPlus] 成功获取验证码: {code}")
                    return code
                else:
                    print(f"[{cfg.ts()}] [OutlookEmailPlus] 未找到验证码")
                    return None
            else:
                print(f"[{cfg.ts()}] [OutlookEmailPlus] 获取验证码失败: {result.get('message', '未知错误')}")
                return None
        except Exception as e:
            print(f"[{cfg.ts()}] [OutlookEmailPlus] 获取验证码异常: {e}")
            return None

    def get_verification_link(self, email: str, timeout_seconds: int = 30) -> Optional[str]:
        """获取验证链接"""
        params = {
            "email": email,
            "timeout_seconds": timeout_seconds
        }

        try:
            url = f"{self.base_url}/api/external/verification-link"
            headers = self._make_headers()
            
            resp = requests.get(url, headers=headers, params=params, proxies=self.proxies, timeout=timeout_seconds + 10, impersonate="chrome110")
            result = resp.json()
            
            if result.get("success"):
                link = result.get("data", {}).get("link", "")
                if link:
                    print(f"[{cfg.ts()}] [OutlookEmailPlus] 成功获取验证链接: {link}")
                    return link
                else:
                    print(f"[{cfg.ts()}] [OutlookEmailPlus] 未找到验证链接")
                    return None
            else:
                print(f"[{cfg.ts()}] [OutlookEmailPlus] 获取验证链接失败: {result.get('message', '未知错误')}")
                return None
        except Exception as e:
            print(f"[{cfg.ts()}] [OutlookEmailPlus] 获取验证链接异常: {e}")
            return None

    def wait_for_message(self, email: str, timeout_seconds: int = 30, poll_interval: int = 5) -> Optional[Dict[str, Any]]:
        """等待新邮件"""
        params = {
            "email": email,
            "timeout_seconds": timeout_seconds,
            "poll_interval": poll_interval
        }

        try:
            url = f"{self.base_url}/api/external/wait-message"
            headers = self._make_headers()
            
            resp = requests.get(url, headers=headers, params=params, proxies=self.proxies, timeout=timeout_seconds + 10, impersonate="chrome110")
            result = resp.json()
            
            if result.get("success"):
                message = result.get("data", {})
                print(f"[{cfg.ts()}] [OutlookEmailPlus] 成功获取新邮件")
                return message
            else:
                print(f"[{cfg.ts()}] [OutlookEmailPlus] 等待邮件超时或失败: {result.get('message', '未知错误')}")
                return None
        except Exception as e:
            print(f"[{cfg.ts()}] [OutlookEmailPlus] 等待邮件异常: {e}")
            return None

    def get_pool_stats(self) -> Optional[Dict[str, Any]]:
        """获取邮箱池统计信息"""
        try:
            result = self._make_request("GET", "/api/external/pool/stats")
            if result.get("success"):
                return result.get("data", {})
            return None
        except Exception as e:
            print(f"[{cfg.ts()}] [OutlookEmailPlus] 获取池统计失败: {e}")
            return None

    def check_account_status(self, email: str) -> Optional[Dict[str, Any]]:
        """检查账号状态"""
        try:
            params = {"email": email}
            url = f"{self.base_url}/api/external/account-status"
            headers = self._make_headers()
            
            resp = requests.get(url, headers=headers, params=params, proxies=self.proxies, timeout=30, impersonate="chrome110")
            result = resp.json()
            
            if result.get("success"):
                return result.get("data", {})
            return None
        except Exception as e:
            print(f"[{cfg.ts()}] [OutlookEmailPlus] 检查账号状态异常: {e}")
            return None

    def mark_email_used(self, email: str):
        """标记邮箱为已使用"""
        self._add_to_registered(email)

    def get_email_and_token(self, task_id: str = None) -> tuple:
        """获取邮箱和token，兼容主流程接口"""
        claim_result = self.claim_random_email(task_id)
        if not claim_result:
            return None, None

        email = claim_result["email"]
        token_data = json.dumps({
            "account_id": claim_result["account_id"],
            "claim_token": claim_result["claim_token"],
            "task_id": claim_result["task_id"],
            "caller_id": claim_result["caller_id"]
        }, ensure_ascii=False)

        return email, token_data

    def get_code(self, email: str, timeout_seconds: int = 60) -> str:
        """获取验证码，兼容主流程接口"""
        code = self.get_verification_code(email, timeout_seconds=timeout_seconds)
        return code or ""

    def get_link(self, email: str, timeout_seconds: int = 60) -> str:
        """获取验证链接，兼容主流程接口"""
        link = self.get_verification_link(email, timeout_seconds=timeout_seconds)
        return link or ""
