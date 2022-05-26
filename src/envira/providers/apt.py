import os
import subprocess
from pathlib import Path
from typing import Dict, List, Optional, Union
from urllib.error import URLError
from urllib.parse import urlparse
from urllib.request import urlopen

from pydantic import Field

from envira.environment import EXEC_INFO, LSB_INFO
from envira.providers._base import (
    BasePattern,
    BaseProvider,
    ProviderOperationResult,
    provider_cmd_error,
)
from envira.utils import is_url


class AptInstallPattern(BasePattern):
    package: str
    version: Optional[str]


class AptRepoPattern(BasePattern):
    repo_url: str
    key_url: Optional[str]
    type_: str = Field(alias="type", default="deb")
    branch: str = "main"
    source_list: str = "envira.list"


class AptPattern(BasePattern):
    update: bool = True
    upgrade: bool = False
    repos: List[Union[str, AptRepoPattern]] = Field(default_factory=list)
    install: List[Union[str, AptInstallPattern]] = Field(default_factory=list)


class AptProvider(BaseProvider[AptPattern]):
    section_key = "apt"
    priority = 1

    def apply(self, *, force: bool = False, **kwgs) -> None:  # type: ignore
        if self.section_obj.repos:
            for repo in self.section_obj.repos:
                if isinstance(repo, str):
                    self._apt_add_repo(repo, force=force)
                else:
                    key_path = ""
                    if repo.key_url:
                        if not is_url(repo.key_url):
                            print(f"Not valid key url '{repo.key_url}'")
                            return

                        res = self._download_key(repo.key_url)
                        if res.err:
                            provider_cmd_error(res)
                            return

                        key_path = res.data  # type: ignore

                    res = self._apt_add_repo(
                        repo.repo_url,
                        repo.type_,
                        repo.branch,
                        key_path,
                        repo.source_list,
                        force,
                    )

                    if res.err:
                        provider_cmd_error(res)
                        return

            print("All repos added successfully")

        if self.section_obj.update:
            res = self._apt_update()
            if res.err:
                provider_cmd_error(res)
                return

            print("Apt repos update successfully")

        if self.section_obj.upgrade:
            res = self._apt_upgrade()
            if res.err:
                provider_cmd_error(res)
                return

            print("Apt packages upgrade successfully")

        if self.section_obj.install:
            if isinstance(self.section_obj.install[0], str):
                for package in self.section_obj.install:
                    res = self._apt_install(package)
                    if res.err:
                        provider_cmd_error(res)
                        return

                    print(f"Successfully installed {package}, version: {res.data}")

            else:
                raise NotImplementedError

    def _download_key(
        self, url: str, key_download_timeout: Union[float, int] = 10
    ) -> ProviderOperationResult:
        key_file_path = EXEC_INFO.cache_path / (
            urlparse(url).path.split("/")[-1] + ".temp.key"
        )
        domain = urlparse(url).netloc
        gpg_key_path = Path(f"/usr/share/keyrings/envira-{domain}-keyring.gpg")

        if gpg_key_path.exists():
            os.remove(gpg_key_path)

        try:
            gpg_bytes = urlopen(url, timeout=key_download_timeout).read()
            with open(key_file_path, "wb") as f:
                f.write(gpg_bytes)

        except URLError as e:
            print(e.reason)

            return ProviderOperationResult(
                cmd=f"urlopen('{url}')",
                exit_code=e.errno,
                err=str(e.reason).split(" ", maxsplit=1)[1],
            )

        cmd = f"gpg --dearmor -o {gpg_key_path} {key_file_path}"

        proc = subprocess.Popen(
            cmd.split(), stdout=subprocess.PIPE, stderr=subprocess.PIPE
        )

        _, err = proc.communicate(gpg_bytes)

        return ProviderOperationResult(
            cmd=cmd,
            exit_code=proc.returncode,
            err=err if proc.returncode != 0 else "",
            data=gpg_key_path.as_posix(),
        )

    def _apt_add_repo(
        self,
        repo_url: str,
        type_: str = "deb",
        branch: str = "main",
        gpg_key_path: str = "",
        source_list: str = "envira.list",
        force: bool = False,
    ) -> ProviderOperationResult:
        source_file_path = Path(f"/etc/apt/sources.list.d/{source_list}")

        repo_row = (
            type_
            + " "
            + ("[signed-by=" + gpg_key_path + "] " if gpg_key_path else "")
            + repo_url
            + " "
            + LSB_INFO.codename
            + " "
            + branch
            + "\n"
        )

        if source_file_path.exists():
            # TODO: если лишнее строчки, то удаляем

            with open(source_file_path, "r") as f:
                file_data = f.read()

            if repo_row in file_data:
                return ProviderOperationResult()

            if repo_url in file_data:
                if not force:
                    return ProviderOperationResult(
                        err=f"Repo '{repo_url}' duplicated! Use -f/--force to fix."
                    )
                else:
                    print(
                        f"Found repo '{repo_url}' duplication, it will be overwritten!"
                    )
                    file_lines = file_data.splitlines()
                    with open(source_file_path, "w") as f:
                        for line in file_lines:
                            if not repo_url in line:
                                f.write(line + "\n")

            with open(source_file_path, "a") as f:
                f.write(repo_row)
        else:
            with open(source_file_path, "w") as f:
                f.write(repo_row)

        return ProviderOperationResult()

    def _apt_update(self) -> ProviderOperationResult:
        cmd = "apt-get update"

        proc = subprocess.Popen(
            cmd.split(),
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
        )

        out, err = proc.communicate()

        return ProviderOperationResult(
            cmd=cmd, exit_code=proc.returncode, err=err, operation_log=out
        )

    def _apt_upgrade(self) -> ProviderOperationResult:
        cmd = "apt-get upgrade -y"

        proc = subprocess.Popen(
            cmd.split(),
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            text=True,
        )

        out, err = proc.communicate()

        return ProviderOperationResult(
            cmd=cmd, exit_code=proc.returncode, err=err, operation_log=out
        )

    def _apt_install(self, package: str) -> ProviderOperationResult:
        cmd = f"apt-get install -y {package}"

        proc = subprocess.Popen(
            cmd.split(), stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True
        )

        _, err = proc.communicate()

        if proc.returncode != 0:
            return ProviderOperationResult(cmd=cmd, exit_code=proc.returncode, err=err)

        cmd = f"apt-cache policy {package}"

        proc = subprocess.Popen(
            cmd.split(), stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True
        )

        out, err = proc.communicate()

        if proc.returncode != 0:
            return ProviderOperationResult(cmd=cmd, exit_code=proc.returncode, err=err)

        version = ""

        for line in out.splitlines():
            if "Installed" in line:
                version = line.strip().split()[1]

        return ProviderOperationResult(
            cmd=cmd, exit_code=proc.returncode, err=err, data=version
        )
