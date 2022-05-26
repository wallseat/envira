import os
import shutil
from pathlib import Path
from typing import Any, Dict, List

from pydantic import Field

from envira.environment import Environment
from envira.providers._base import (
    BasePattern,
    BaseProvider,
    ProviderOperationResult,
    provider_cmd_error,
)


class EnvCopyPattern(BasePattern):
    source: str
    dest: str
    as_link: bool = False


_T_DirTree = Dict[str, "_T_DirTree"]  # type: ignore


class EnvDirTreePattern(BasePattern):
    root: Path = Path("~/")
    tree: Dict[str, Any] = Field(default_factory=dict)


class EnvPattern(BasePattern):
    copy_: List[EnvCopyPattern] = Field(alias="copy", default_factory=list)
    dirtree: EnvDirTreePattern


class EnvProvider(BaseProvider[EnvPattern]):
    section_key = "env"
    priority = 2

    def apply(self, *, force: bool = False, env: Environment = None, **kwgs) -> None:  # type: ignore
        if env is None:
            print("Environment not provided!")
            return

        if self.section_obj.copy_:
            for copy_ in self.section_obj.copy_:
                print(
                    ("Linking " if copy_.as_link else "Copying ")
                    + f"'{copy_.source}' "
                    + "to "
                    + f"'{copy_.dest}'"
                )
                res = self._env_copy(
                    env, Path(copy_.source), Path(copy_.dest), copy_.as_link, force
                )
                if res.err:
                    provider_cmd_error(res)

        if self.section_obj.dirtree:
            section = self.section_obj.dirtree

            self._build_dirtree(section.root.expanduser().absolute(), section.tree)

    def _env_copy(
        self, env: "Environment", source: Path, dest: Path, as_link: bool, force: bool
    ) -> ProviderOperationResult:
        source = env._folder_path / source
        dest = dest.absolute()

        if not env._folder_path == source.parents[0]:
            return ProviderOperationResult(
                err=f"Attempt to access a file outside of environment folder"
            )

        if not source.exists():
            return ProviderOperationResult(err=f"File {source.name} does not exist")

        if not as_link:
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

    def _build_dirtree(self, root: Path, dir_tree: _T_DirTree) -> None:
        def _walk(sub_tree: _T_DirTree, cur_path: Path) -> None:
            for folder in sub_tree:
                new_cur_path = cur_path / folder
                if not new_cur_path.exists():
                    new_cur_path.mkdir()

                if sub_tree[folder]:
                    _walk(sub_tree[folder], new_cur_path)

        _walk(dir_tree, root)

        print("Directory structure builded!")
