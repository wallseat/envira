import os
import shutil
import subprocess
from pathlib import Path
from typing import Dict, List, Optional, Union

from pydantic import Field, constr, validator

from envira.environment import EXEC_INFO, SYS_INFO, Environment
from envira.providers._base import (
    BasePattern,
    BaseProvider,
    ProviderOperationResult,
    provider_cmd_error,
)


class EnvCopyPattern(BasePattern):
    source: Path
    dest: Path
    as_link: bool = False


class EnvDirTreeSubtreePattern(BasePattern):
    name: str
    mode: constr(min_length=1, max_length=4) = "755"  # type: ignore
    nested: List["EnvDirTreeSubtreePattern"] = Field(default_factory=list)

    @validator("mode")
    def validate_privileges(cls, v: str) -> str:
        if "8" in v or "9" in v:
            raise ValueError("Privileges code must be in range 0-7!")

        if not v.startswith("0") and len(v) == 4:
            raise ValueError("Privileges code must start with 0!")

        if len(v) < 3:
            v = v.rjust(3 - len(v), "0")

        if len(v) == 4:
            v = v[1:]

        return v


class EnvExecPattern(BasePattern):
    cmd: Optional[str]
    script: Optional[Path]
    shell: str = SYS_INFO.default_shell
    as_root: bool = False
    envs: Dict[str, Union[str, int, float]] = Field(default_factory=dict)

    @validator("cmd", always=True)
    def check_cmd_or_script(cls, cmd: str, values: Dict):
        if not values.get("script") and not cmd or values.get("script") and cmd:
            raise ValueError("Either only cmd or script path is required!")
        return cmd


class EnvDirTreePattern(BasePattern):
    root: Path = Path("~/")
    tree: List[EnvDirTreeSubtreePattern] = Field(default_factory=list)


class EnvPattern(BasePattern):
    copy_: Optional[List[EnvCopyPattern]] = Field(alias="copy")
    dirtree: Optional[EnvDirTreePattern]
    exec_: Optional[List[EnvExecPattern]] = Field(alias="exec")


class EnvProvider(BaseProvider[EnvPattern]):
    section_key = "env"
    priority = 2

    def apply(self, *, force: bool = False, env: Environment = None, **kwgs) -> None:  # type: ignore
        if env is None:
            print("Environment not provided!")
            return 1

        if self.section_obj.copy_:
            for copy_ in self.section_obj.copy_:
                print(
                    ("Linking " if copy_.as_link else "Copying ")
                    + f"'{copy_.source}' "
                    + "to "
                    + f"'{copy_.dest}'"
                )
                res = self._apply_copy(env, copy_, force)
                if res.err:
                    provider_cmd_error(res)

        if self.section_obj.dirtree:
            section = self.section_obj.dirtree

            print("Building dir tree")
            res = self._apply_dirtree(section)
            if res.err:
                provider_cmd_error(res)
                return 1

            print("Directory structure builded!")

        if self.section_obj.exec_:
            print("Run scripts")
            for exec_ in self.section_obj.exec_:
                res = self._apply_exec(env, exec_)
                if res.err or res.exit_code != 0:
                    provider_cmd_error(res)
                    return 1

            print("All scripts are executed!")

    @staticmethod
    def _path_relative(env: Environment, path: Path) -> bool:
        """
        Check that the path is in the current environment

        Args:
            env (Environment): Current environment
            path (Path): Path

        Returns:
            bool: Is in the current environment
        """
        if not path.is_absolute():
            path = path.expanduser().absolute()

        if env.folder_path not in path.parents:
            return False

        return True

    def _apply_copy(
        self, env: Environment, section: EnvCopyPattern, force: bool = False
    ) -> ProviderOperationResult:
        source = env.folder_path / section.source
        dest = section.dest.absolute()

        if not self._path_relative(env, source):
            return ProviderOperationResult(
                err=f"Attempt to access a file outside of environment folder"
            )

        if not source.exists():
            return ProviderOperationResult(err=f"File {source.name} does not exist")

        if not section.as_link:
            if dest.exists() and not force:
                return ProviderOperationResult(
                    err=f"File {dest} already exists! Use -f/--force to overwrite!"
                )

            try:
                shutil.copy(source, dest)
            except shutil.SameFileError:
                pass
            except OSError as e:
                return ProviderOperationResult(err=str(e))

        else:
            if (
                dest.exists()
                and (
                    not dest.is_symlink()
                    or (dest.is_symlink() and dest.resolve() != source)
                )
                and not force
            ):
                return ProviderOperationResult(
                    err=f"File {dest} already exists! Use -f/--force to overwrite!"
                )

            if dest.is_symlink() and dest.resolve() == source:
                return ProviderOperationResult()

            os.symlink(source, dest)

        return ProviderOperationResult()

    def _apply_dirtree(self, section: EnvDirTreePattern) -> ProviderOperationResult:
        def _walk(trees: List[EnvDirTreeSubtreePattern], cur_path: Path) -> None:
            for tree in trees:
                new_cur_path = cur_path / tree.name
                if not new_cur_path.exists():
                    new_cur_path.mkdir(mode=int(tree.mode, base=8))

                if tree.nested:
                    _walk(tree.nested, new_cur_path)

        try:
            _walk(section.tree, section.root.expanduser().absolute())
        except Exception as e:
            return ProviderOperationResult(err=str(e))

        return ProviderOperationResult()

    def _apply_exec(
        self, env: Environment, section: EnvExecPattern
    ) -> ProviderOperationResult:
        if section.script:
            if not self._path_relative(env, section.script):
                return ProviderOperationResult(
                    err="Attempt to access a file outside of environment folder"
                )

            cmd = section.script.absolute().as_posix()

        else:
            cmd = section.cmd

        kwargs = {"env": {}, "shell": True}

        if not section.as_root:
            kwargs["user"] = EXEC_INFO.uid

        if section.envs:
            kwargs["env"] = section.envs

        if section.shell != SYS_INFO.default_shell:
            abs_shell_path = shutil.which(section.shell)
            if not abs_shell_path:
                return ProviderOperationResult(err=f"Unknown shell '{section.shell}'!")

            kwargs["env"]["SHELL"] = abs_shell_path

        proc = subprocess.Popen(
            cmd, **kwargs, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True
        )

        out, err = proc.communicate()

        if proc.returncode != 0 and not err:
            err = out

        return ProviderOperationResult(
            cmd=cmd, err=err, operation_log=out, exit_code=proc.returncode
        )
