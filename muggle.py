# -*- coding: utf-8 -*-
# Time       : 2022/11/2 16:01
# Author     : QIN2DIM
# Github     : https://github.com/QIN2DIM
# Description:
import functools
import json
import logging
import os
import re
import sys
import time
import typing
from dataclasses import dataclass
from uuid import uuid4

# 阻止 python2 及非 linux 系统运行
if sys.version_info[0] < 3 or sys.platform != "linux":
    sys.exit()
os.system("clear")

GUIDER_PANEL = """ -------------------------------------------
|**********        muggle          **********|
|**********    Author: QIN2DIM     **********|
|**********     Version: 0.1.0     **********|
 -------------------------------------------
Tips:
.............................................

############################### 

..................... 
1)  部署 Hysteria(sing-box)
2)  卸载 
..................... 
3)  启动 
4)  暂停 
5)  重载 
6)  运行状态 
..................... 
7)  查看当前配置 
8)  重新配置
..................... 
9)  更新 sing-box

############################### 



0)退出 
............................................. 
请选择: """

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    datefmt="%Y/%m/%d %H:%M:%S",
)


class Env:
    singbox_config = "/usr/local/etc/sing-box/config.json"
    workspace = "/usr/local/etc/sing-box/"
    path_v2rayn_custom_config = os.path.join(workspace, "v2rayn_client.json")
    path_sharelink = os.path.join(workspace, "sharelink.txt")
    path_server_config = os.path.join(workspace, "hysteriaInbound.json")

    remote_muggle = "https://raw.githubusercontent.com/QIN2DIM/singbox-muggle/main/muggle.py"
    local_script = "/home/sing-box/muggle.py"


SHELL_MUGGLE = f"""
if [ ! -f "{Env.local_script}" ]; then
    echo "Local script is missing, trying to sync upstream content"
    wget -qO {Env.local_script} {Env.remote_muggle}
fi
python3 {Env.local_script}
"""


def check_singbox(func):
    @functools.wraps(func)
    def wrapped(*args, **kwargs):
        if not os.path.isfile(Env.singbox_config) or not os.path.getsize(Env.singbox_config):
            logging.error(f"sing-box 未初始化，請先執行「敏捷部署」 - func={func.__name__}")
        else:
            return func(*args, **kwargs)

    return wrapped


def skip_recompile(func):
    @functools.wraps(func)
    def wrapped(*args, **kwargs):
        if os.path.isfile(Env.singbox_config) and os.path.getsize(Env.singbox_config):
            logging.error(f"sing-box 已编译，如需修改参数请执行「重新配置」 - func={func.__name__}")
        else:
            return func(*args, **kwargs)

    return wrapped


@dataclass
class HysteriaInbound:
    domain: str = ""
    listen_port: typing.Union[int, str] = 10030
    up_mbps: typing.Union[int, str] = 20
    down_mbps: typing.Union[int, str] = 175
    obfs: str = "xplus"
    auth_str: str = ""

    def __post_init__(self):
        self.auth_str = self.auth_str or uuid4().hex

    def get_server_inbound_config(self) -> dict:
        return {
            "log": {"level": "info"},
            "dns": {"servers": [{"tag": "Cloudflare", "address": "https://1.1.1.1/dns-query"}]},
            "inbounds": [
                {
                    "type": "hysteria",
                    "tag": "hysteria-in",
                    "listen": "::",
                    "listen_port": int(self.listen_port),
                    "up_mbps": int(self.up_mbps),
                    "down_mbps": int(self.down_mbps),
                    "obfs": self.obfs,
                    "auth_str": self.auth_str,
                    "tls": {
                        "enabled": True,
                        "server_name": self.domain,
                        "acme": {"domain": self.domain, "email": f"muggle@{self.domain}"},
                    },
                }
            ],
            "outbounds": [{"type": "direct"}, {"type": "dns", "tag": "dns-out"}],
            "route": {"rules": [{"protocol": "dns", "outbound": "dns-out"}]},
        }

    def get_sharelink(self):
        """
        hysteria://host:port?protocol=udp&auth=123456&peer=sni.domain&insecure=1&upmbps=100&downmbps=100&alpn=hysteria&obfs=xplus&obfsParam=123456#remarks

        - host: hostname or IP address of the server to connect to (required)
        - port: port of the server to connect to (required)
        - protocol: protocol to use ("udp", "wechat-video", "faketcp") (optional, default: "udp")
        - auth: authentication payload (string) (optional)
        - peer: SNI for TLS (optional)
        - insecure: ignore certificate errors (optional)
        - upmbps: upstream bandwidth in Mbps (required)
        - downmbps: downstream bandwidth in Mbps (required)
        - alpn: QUIC ALPN (optional)
        - obfs: Obfuscation mode (optional, empty or "xplus")
        - obfsParam: Obfuscation password (optional)
        - remarks: remarks (optional)
        :return:
        """
        sharelink = (
            f"hysteria://{self.domain}:{self.listen_port}?protocol=udp"
            f"&auth={self.auth_str}"
            f"&peer={self.domain}"
            f"&insecure=0"
            f"&upmbps={self.up_mbps}"
            f"&downmbps={self.down_mbps}"
            f"&obfs={self.obfs}"
            f"#remarks={self.domain}"
        )
        return sharelink

    def get_v2rayn_custom_config(self) -> dict:
        v2rayn_client = {
            "server": f"{self.domain}:{self.listen_port}",
            "protocol": "udp",
            "up_mbps": int(self.up_mbps),
            "down_mbps": int(self.down_mbps),
            "retry": 3,
            "retry_interval": 5,
            "quit_on_disconnect": False,
            "handshake_timeout": 10,
            "idle_timeout": 60,
            "socks5": {
                "listen": "127.0.0.1:10808",
                "timeout": 300,
                "disable_udp": False,
            },
            "http": {
                "listen": "127.0.01:10809",
                "timeout": 300,
                "disable_udp": False,
            },
            "obfs": self.obfs,
            "auth_str": self.auth_str,
            "alpn": "hysteria",
            "server_name": self.domain,
            "insecure": False,
            "recv_window_conn": 15728640,
            "recv_window": 67108864,
            "disable_mtu_discovery": False,
            "resolver": "https://223.5.5.5:443/dns-query",
            "resolve_preference": "64"
        }
        return v2rayn_client

    def refresh_localcache(self, drop=False):
        """刷新 sing-box 配置，更新客戶端配置文件"""
        localcache = {
            "v2rayn_custom_config": self.get_v2rayn_custom_config(),
            "sharelink": self.get_sharelink(),
        }
        with open(Env.path_v2rayn_custom_config, "w", encoding="utf8") as file:
            json.dump(self.get_v2rayn_custom_config(), file)
        with open(Env.path_sharelink, "w", encoding="utf8") as file:
            file.write(f"{self.get_sharelink()}\n")
        with open(Env.path_server_config, "w", encoding="utf8") as file:
            json.dump(self.__dict__, file, indent=4)
        with open(Env.singbox_config, "w", encoding="utf8") as file:
            json.dump(self.get_server_inbound_config(), file)

        if drop:
            print(" ↓ ↓ V2RayN ↓ ↓ ".center(50, "="))
            print(localcache.get("v2rayn_custom_config"))
            print(" ↓ ↓ NekoRay & Matsuri & SagerNet & shadowrocket ↓ ↓ ".center(50, "="))
            print(f'\n{localcache.get("sharelink")}\n')


class SingBoxService:
    remote_repo = "https://github.com/SagerNet/sing-box"
    dir_git_local = "/home/sing-box/"
    NAME = "sing-box"
    path_sh_install = os.path.join(dir_git_local, "release", "local", "install.sh")
    path_sh_enable = os.path.join(dir_git_local, "release", "local", "enable.sh")
    path_sh_update = os.path.join(dir_git_local, "release", "local", "update.sh")
    path_sh_uninstall = os.path.join(dir_git_local, "release", "local", "uninstall.sh")

    @staticmethod
    def load_hysteria_inbound() -> HysteriaInbound:
        try:
            with open(Env.path_server_config, "r", encoding="utf8") as file:
                return HysteriaInbound(**json.load(file))
        except (FileNotFoundError, KeyError, TypeError):
            return HysteriaInbound()

    def install(self):
        os.system("clear")
        logging.info("Check snap, wget, port80 and port443")
        os.system("apt install -y snapd wget >/dev/null 2>&1")
        os.system("nginx -s stop >/dev/null 2>&1")

        logging.info("Check go1.18.7+")
        os.system("apt remove golang-go -y >/dev/null 2>&1")
        os.system("snap install go --classic >/dev/null 2>&1")

        logging.info(f"Git clone sing-box from GitHub {self.remote_repo}")
        os.system(f"git clone {self.remote_repo} {self.dir_git_local} >/dev/null 2>&1")

        logging.info("Downloading sing-box")
        os.system(f"export PATH=$PATH:/snap/bin && {self.path_sh_install} >/dev/null 2>&1")

    @check_singbox
    def start(self):
        os.system(f"systemctl start {self.NAME}")
        logging.info(f"Start the {self.NAME}")

    @check_singbox
    def stop(self):
        os.system(f"systemctl stop {self.NAME}")
        logging.info(f"Stop the {self.NAME}")

    @check_singbox
    def reload(self):
        os.system(f"systemctl reload-or-restart {self.NAME}")
        logging.info(f"Reload the {self.NAME}")

    @check_singbox
    def check_status(self):
        logging.info(f"Check service status of the {self.NAME}")
        os.system(f"systemctl status {self.NAME}")

    @check_singbox
    def delete(self):
        os.system(f"{self.path_sh_uninstall} >/dev/null 2>&1")
        logging.info(f"Delete the {self.NAME}")

    @check_singbox
    def update(self):
        logging.info("Synchronizing upstream features")
        os.system(f"{self.path_sh_update}")


class Alias:
    BIN_NAME: str = "muggle"

    def register(self):
        for path_bin in [f"/usr/bin/{self.BIN_NAME}", f"/usr/sbin/{self.BIN_NAME}"]:  # unnecessary
            if not os.path.isfile(path_bin):
                with open(path_bin, "w", encoding="utf8") as file:
                    file.write(SHELL_MUGGLE)
                os.system(f"chmod +x {path_bin}")

    def remove(self):
        os.system(f"rm /usr/bin/{self.BIN_NAME}")
        os.system(f"rm /usr/sbin/{self.BIN_NAME}")

    def update(self):
        logging.info("Updating script ...")
        time.sleep(1)
        bak = f"{Env.local_script}.bak"
        os.system(f"wget -qO {bak} {Env.remote_muggle}")
        if os.path.isfile(bak) and os.path.getsize(bak):
            os.system(f"mv {bak} {Env.local_script}")
        os.system(self.BIN_NAME)


class CMDPanel:
    def __init__(self):
        self.singbox = SingBoxService()
        self.hi = self.singbox.load_hysteria_inbound()

        self.alias = Alias()
        self.alias.register()

    @staticmethod
    def _guide_domain(prompt: str):
        pattern = re.compile(r"(?:\w(?:[\w\-]{0,61}\w)?\.)+[a-zA-Z]{2,6}")
        while True:
            domain = input(prompt).strip()
            result = re.findall(pattern, domain)
            if result and result.__len__() == 1:
                return result[0]

    @staticmethod
    def _guide_digital(prompt: str, default: str):
        while True:
            result = input(prompt).strip()
            if not result:
                return default
            if result.isdigit():
                return result

    @check_singbox
    def delete(self):
        if input(">> 卸载「已编译的sing-box服務及缓存數據」[y/n] ").strip().lower().startswith("y"):
            self.alias.remove()
            self.singbox.delete()
            logging.info("Delete cache of the naiveproxy")
        else:
            logging.info(f"Withdraw operation")

    @skip_recompile
    def deploy(self):
        prompt = "[1/5] 输入解析到本机Ipv4的域名[domain] > "
        self.hi.domain = self._guide_domain(prompt)
        prompt = "[2/5] 輸入監聽端口[listen_port](回车随机配置) > "
        self.hi.listen_port = self._guide_digital(prompt, self.hi.listen_port)
        prompt = "[3/5] 输入认证密码[auth_str](回车随机配置) > "
        self.hi.obfs = input(prompt).strip() or self.hi.obfs
        prompt = f"[4/5] 輸入单客户端最大上传速度[up_mbps](默認值： {self.hi.up_mbps}) > "
        self.hi.up_mbps = self._guide_digital(prompt, self.hi.up_mbps)
        prompt = f"[5/5] 輸入单客户端最大下载速度[down_mbps](默認值： {self.hi.down_mbps}) > "
        self.hi.down_mbps = self._guide_digital(prompt, self.hi.down_mbps)

        self.singbox.install()
        if not os.path.isfile(Env.singbox_config):
            logging.error("👻 編譯失敗")
        else:
            logging.info("🎉 编译成功! 按任意键部署 sing-box 系统服务")
            input()
            self.hi.refresh_localcache(drop=True)  # deploy
            self.singbox.start()

    @check_singbox
    def checkout(self):
        self.hi.refresh_localcache(drop=True)  # checkout

    @check_singbox
    def reset(self):
        if input(f">> 是否使用上次配置的域名({self.hi.domain})？[y/n] ").strip().lower().startswith("n"):
            prompt = "[1/5] 输入解析到本机Ipv4的域名[domain] > "
            self.hi.domain = self._guide_domain(prompt)
        if input(">> 是否使用上次配置的监听端口？[y/n] ").strip().lower().startswith("n"):
            prompt = "[2/5] 輸入監聽端口[listen_port]（回车随机配置） > "
            self.hi.listen_port = self._guide_digital(prompt, self.hi.listen_port)
        if input(">> 是否使用上次配置的认证密码？[y/n] ").strip().lower().startswith("n"):
            prompt = "[3/5] 输入认证密码[auth_str]（回车随机配置） > "
            self.hi.obfs = input(prompt).strip() or self.hi.obfs
        if input(">> 是否使用上次配置的单客户端最大上传速度？[y/n]").strip().lower().startswith("n"):
            prompt = f"[4/5] 輸入单客户端最大上传速度[up_mbps]（默認值： {self.hi.up_mbps}） > "
            self.hi.up_mbps = self._guide_digital(prompt, self.hi.up_mbps)
        if input(">> 是否使用上次配置的单客户端最大下载速度？[y/n]").strip().lower().startswith("n"):
            prompt = f"[5/5] 輸入单客户端最大下载速度[down_mbps]（默認值： {self.hi.down_mbps}） > "
            self.hi.down_mbps = self._guide_digital(prompt, self.hi.down_mbps)

        self.hi.refresh_localcache()  # reset
        logging.info("Reset sing-box config")
        self.singbox.reload()

    def upgrade(self):
        logging.info("Updating script ...")
        time.sleep(1)
        self.alias.update()
        self.singbox.update()

    def startup(self):
        if not (item := input(GUIDER_PANEL).strip()):
            return

        if item == "1":
            self.deploy()
        elif item == "2":
            self.delete()
        elif item == "3":
            self.singbox.start()
        elif item == "4":
            self.singbox.stop()
        elif item == "5":
            self.singbox.reload()
        elif item == "6":
            self.singbox.check_status()
        elif item == "7":
            self.checkout()
        elif item == "8":
            self.reset()
        elif item == "9":
            self.singbox.update()


if __name__ == "__main__":
    try:
        CMDPanel().startup()
    except KeyboardInterrupt:
        print("\n")
