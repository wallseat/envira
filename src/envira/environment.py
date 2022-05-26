import os
import pwd
import subprocess
from pathlib import Path
from typing import Optional, Union

from pydantic import BaseModel


class LsbInfo(BaseModel):
    distr: str
    ver: str
    codename: str


class ExecInfo(BaseModel):
    uname: str
    euname: str
    uid: int
    euid: int
    uhome: str

    exc_path: Path
    cache_path: Path
    config_file: Optional[str] = "envira.toml"


def _get_lsb_info() -> LsbInfo:
    proc = subprocess.Popen(
        ["lsb_release", "-a"], stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True
    )

    out, err = proc.communicate()

    if proc.returncode != 0:
        print(
            f"An error occurred in lsb_release, exit code: {proc.returncode}, reason: {err}"
        )

    obj = {}
    for line in out.splitlines():
        if line.startswith(("Distributor ID", "Release", "Codename")):
            k, v = line.split(":\t")
            k = (
                k.replace("Distributor ID", "distr")
                .replace("Release", "ver")
                .replace("Codename", "codename")
            )
            obj[k] = v.strip().lower()

    return LsbInfo.parse_obj(obj)


def _get_exec_info() -> ExecInfo:
    uid = os.getuid()
    euid = os.geteuid()

    uname = os.getenv("SUDO_USER", "") if euid == 0 else pwd.getpwuid(uid).pw_name
    euname = pwd.getpwuid(euid).pw_name

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


LSB_INFO = _get_lsb_info()
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
