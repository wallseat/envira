import os
import pwd
import sys
from dataclasses import dataclass
from pathlib import Path
from typing import Optional, Union


@dataclass
class SysInfo:
    os: str

    id_: Optional[str]
    version: Optional[str]
    codename: Optional[str]

    default_shell: str = "sh"


@dataclass
class ExecInfo:
    uname: str
    euname: str
    uid: int
    euid: int
    uhome: str

    exc_path: Path
    cache_path: Path
    config_file: Optional[str] = "envira.toml"


def _get_sys_info() -> SysInfo:
    if sys.platform != "linux":
        return SysInfo(os=sys.platform)

    obj = {"os": sys.platform}

    with open("/etc/os-release", "r") as f:
        os_data = f.readlines()

    for line in os_data:
        k, v = (lambda tup: (tup[0].lower(), tup[1].strip('"').strip()))(
            line.split("=")
        )

        if k == "id":
            obj["id_"] = v
        elif k == "version_codename":
            obj["codename"] = v
        elif k == "version_id":
            obj["version"] = v

    obj["default_shell"] = os.environ["SHELL"]

    return SysInfo(**obj)


def _get_exec_info() -> ExecInfo:
    euid = os.geteuid()
    euname = pwd.getpwuid(euid).pw_name

    uname = os.getenv("SUDO_USER", "")
    if uname:
        uid = pwd.getpwnam(uname).pw_uid

    else:
        uid = os.getuid()
        uname = pwd.getpwuid(uid).pw_name

    exc_path = Path(os.path.curdir).absolute()
    cache_path = Path("~/.cache/envira").expanduser().absolute()

    return ExecInfo(
        uname=uname,
        euname=euname,
        uid=uid,
        euid=euid,
        uhome="/home/" + uname,
        exc_path=exc_path,
        cache_path=cache_path,
    )


SYS_INFO = _get_sys_info()
EXEC_INFO = _get_exec_info()


def set_config_file(config_file: str) -> None:
    EXEC_INFO.config_file = config_file


class Environment:
    _folder_path: Path
    _config_path: Path

    _prepared: bool = False

    def __init__(self, provided_path: Union[Path, str]) -> None:
        if isinstance(provided_path, str):
            provided_path = Path(provided_path)

        self._prepare(provided_path)

    def _prepare(self, path: Path) -> None:
        if path.is_dir():
            for path_obj in path.iterdir():
                if path_obj.is_file() and path_obj.name == EXEC_INFO.config_file:
                    self._config_path = path_obj.absolute()
                    self._folder_path = path

                    self._prepared = True
                    break
            else:
                print("Config file not found in provided path!")

        elif path.is_file():
            if path.name == EXEC_INFO.config_file:
                self._config_path = path.absolute()
                self._folder_path = path.absolute().parents[0]

                self._prepared = True

            else:
                print("Provided file name not matching config filename!")

    @property
    def prepared(self) -> bool:
        return self._prepared

    @property
    def config_path(self) -> Optional[Path]:
        if self.prepared:
            return self._config_path
        return None

    @property
    def folder_path(self) -> Optional[Path]:
        if self.prepared:
            return self._folder_path
        return None
