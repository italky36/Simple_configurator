from typing import Dict, List

import requests
from urllib.parse import quote


class SeafileClient:
    def __init__(self, server: str, repo_id: str, token: str):
        self.server = server
        self.repo_id = repo_id
        self.token = token
        self.base_url = f"https://{server}/api2"

    def _headers(self) -> dict:
        return {"Authorization": f"Token {self.token}"}

    def list_directory(self, path: str = "/") -> List[Dict]:
        url = f"{self.base_url}/repos/{self.repo_id}/dir/"
        params = {"p": path}
        response = requests.get(url, headers=self._headers(), params=params, timeout=15)
        response.raise_for_status()
        return response.json()

    def get_file_download_link(self, file_path: str) -> str:
        url = f"{self.base_url}/repos/{self.repo_id}/file/"
        if not file_path.startswith("/"):
            file_path = "/" + file_path
        params = {"p": file_path, "reuse": "1"}
        response = requests.get(url, headers=self._headers(), params=params, timeout=15)
        response.raise_for_status()
        # Seafile возвращает прямую ссылку текстом (может быть в кавычках)
        link = response.text.strip().strip('"')
        return link

    def list_file_links(self, folder_path: str) -> List[str]:
        """Вернуть прямые ссылки на все файлы в указанной папке."""
        if not folder_path.startswith("/"):
            folder_path = "/" + folder_path
        items = self.list_directory(folder_path)
        links: List[str] = []
        for item in items:
            if item.get("type") != "file":
                continue
            file_path = item.get("path") or f"{folder_path.rstrip('/')}/{item.get('name')}"
            links.append(self.get_file_download_link(file_path))
        return links
