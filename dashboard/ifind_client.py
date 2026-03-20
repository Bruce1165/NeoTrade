"""
iFinD HTTP API Client
同花顺 HTTP API 客户端封装
"""
import requests
import json
import yaml
import logging
from pathlib import Path
from typing import Dict, Any, Optional

# 配置日志
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


class IfindConfig:
    """配置管理"""
    
    def __init__(self, config_path: str = None):
        if config_path is None:
            # Use the config from pilot-ifind
            config_path = Path.home() / "pilot-ifind" / "config" / "config.yaml"
        
        with open(config_path, 'r', encoding='utf-8') as f:
            self.config = yaml.safe_load(f)
    
    @property
    def refresh_token(self) -> str:
        token = self.config['auth']['refresh_token']
        if token == "YOUR_REFRESH_TOKEN_HERE":
            raise ValueError("请在 config/config.yaml 中填写 refresh_token")
        return token
    
    @property
    def base_url(self) -> str:
        return self.config['auth']['base_url']
    
    @property
    def db_path(self) -> str:
        return self.config['storage']['db_path']


class IfindAuth:
    """Token 管理"""
    
    GET_TOKEN_URL = "https://quantapi.51ifind.com/api/v1/get_access_token"
    
    def __init__(self, refresh_token: str):
        self.refresh_token = refresh_token
        self.access_token = None
        
    def get_access_token(self) -> str:
        """获取 access_token（有效期7天）"""
        headers = {
            "Content-Type": "application/json",
            "refresh_token": self.refresh_token
        }
        
        try:
            response = requests.post(
                url=self.GET_TOKEN_URL,
                headers=headers,
                timeout=10
            )
            response.raise_for_status()
            data = response.json()
            
            if 'data' in data and 'access_token' in data['data']:
                self.access_token = data['data']['access_token']
                logger.info("✅ Access token 获取成功")
                return self.access_token
            else:
                logger.error(f"❌ Token 响应异常: {data}")
                raise ValueError("无法获取 access_token")
                
        except requests.exceptions.RequestException as e:
            logger.error(f"❌ 请求失败: {e}")
            raise


class IfindClient:
    """HTTP API 客户端基类"""
    
    def __init__(self, config: IfindConfig = None):
        self.config = config or IfindConfig()
        self.auth = IfindAuth(self.config.refresh_token)
        self.access_token = None
        self._ensure_token()
    
    def _ensure_token(self):
        """确保 token 有效"""
        if self.access_token is None:
            self.access_token = self.auth.get_access_token()
    
    def _get_headers(self) -> Dict[str, str]:
        """获取请求头"""
        self._ensure_token()
        return {
            "Content-Type": "application/json",
            "access_token": self.access_token
        }
    
    def post(self, endpoint: str, params: Dict[str, Any]) -> Dict[str, Any]:
        """
        发送 POST 请求
        
        Args:
            endpoint: API 端点（如 'real_time_quotation'）
            params: 请求参数
            
        Returns:
            API 响应数据
        """
        url = f"{self.config.base_url}/{endpoint}"
        headers = self._get_headers()
        
        try:
            logger.debug(f"POST {url}")
            logger.debug(f"Params: {params}")
            
            response = requests.post(
                url=url,
                json=params,
                headers=headers,
                timeout=30
            )
            response.raise_for_status()
            data = response.json()
            
            # 检查业务错误
            if data.get('errorcode') != 0:
                error_msg = data.get('errmsg', 'Unknown error')
                logger.error(f"❌ API 错误: {error_msg}")
                raise ValueError(f"API Error: {error_msg}")
            
            return data
            
        except requests.exceptions.HTTPError as e:
            if response.status_code == 401:
                logger.warning("Token 过期，尝试刷新...")
                self.access_token = self.auth.get_access_token()
                return self.post(endpoint, params)  # 重试
            raise
        except requests.exceptions.RequestException as e:
            logger.error(f"❌ 请求失败: {e}")
            raise