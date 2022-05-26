import os
import shutil
from pathlib import Path
from typing import List, Optional

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


class EnvPattern(BasePattern):
    copy_: Optional[List[EnvCopyPattern]] = Field(alias="copy", default_factory=list)


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
