from dataclasses import dataclass, field
from pathlib import Path
import ipaddress
import os
from urllib.parse import urlparse

ROOT = Path(__file__).resolve().parent.parent


def local_endpoint(value: str) -> str:
    """Prevent original-image transport to a public provider, including redirects."""
    if not value:
        return ""
    p = urlparse(value)
    if p.scheme not in ("http", "https") or p.username or p.password or p.query or p.fragment:
        raise ValueError("视觉服务地址必须是无用户信息的 http(s) 地址")
    host = p.hostname or ""
    if host != "localhost":
        try:
            ip = ipaddress.ip_address(host)
            networks = [ipaddress.ip_network(n) for n in ("10.0.0.0/8", "172.16.0.0/12", "192.168.0.0/16", "fc00::/7")]
            if not (ip.is_loopback or any(ip in n for n in networks if ip.version == n.version)):
                raise ValueError()
        except ValueError:
            raise ValueError("视觉模型只接受回环或私网 IP；远程 Spark 请使用 SSH 隧道") from None
    return value.rstrip("/")


@dataclass
class Settings:
    data_dir: Path = field(default_factory=lambda: Path(os.getenv("CZ_DATA_DIR", str(ROOT / "runtime"))).resolve())
    knowledge_dir: Path = field(default_factory=lambda: ROOT / "knowledge")
    model_url: str = field(default_factory=lambda: os.getenv("CZ_MODEL_BASE_URL", ""))
    model: str = field(default_factory=lambda: os.getenv("CZ_MODEL_NAME", ""))
    model_key: str = field(default_factory=lambda: os.getenv("CZ_MODEL_KEY", ""))
    model_timeout: float = field(default_factory=lambda: float(os.getenv("CZ_MODEL_TIMEOUT", "85")))
    job_timeout: float = field(default_factory=lambda: float(os.getenv("CZ_JOB_TIMEOUT", "260")))
    access_token: str = field(default_factory=lambda: os.getenv("CZ_ACCESS_TOKEN", ""))
    enable_online: bool = field(default_factory=lambda: os.getenv("CZ_ENABLE_ONLINE", "false").lower() == "true")
    cloud_text: bool = field(default_factory=lambda: os.getenv("CZ_ALLOW_CLOUD_TEXT", "false").lower() == "true")
    text_url: str = field(default_factory=lambda: os.getenv("CZ_TEXT_BASE_URL", ""))
    text_model: str = field(default_factory=lambda: os.getenv("CZ_TEXT_MODEL", ""))
    text_key: str = field(default_factory=lambda: os.getenv("CZ_TEXT_KEY", ""))

    def __post_init__(self):
        self.model_url = local_endpoint(self.model_url)
        self.data_dir = Path(self.data_dir).resolve()
        self.knowledge_dir = Path(self.knowledge_dir).resolve()
        self.data_dir.mkdir(parents=True, exist_ok=True)

    @property
    def model_configured(self):
        return bool(self.model_url and self.model)
