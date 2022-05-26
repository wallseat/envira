import subprocess
from pathlib import Path

from envira.environment import EXEC_INFO


class GitLoader:
    def __init__(self, repo_url: str) -> None:
        self.repo_url = repo_url

        self._git_status = self._check_git_is_available()
        self._is_cloned = False

    @staticmethod
    def _check_git_is_available() -> bool:
        try:
            proc = subprocess.Popen(
                ["git", "--version"],
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL,
            )
            proc.communicate()

            if proc.returncode != 0:
                return False

        except OSError:
            return False

        return True

    def clone(self) -> None:
        if not self._git_status:
            print("Git is unavailable!")

        if not EXEC_INFO.cache_path.exists():
            EXEC_INFO.cache_path.mkdir(parents=True, exist_ok=True)

        print(f"Start cloning from {self.repo_url}")

        proc = subprocess.Popen(
            ["git", "clone", self.repo_url, self.folder_path],
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
        )

        _, err = proc.communicate()

        if proc.returncode != 0:
            print(f"Error while cloning remote repo: {err}")
            return

        print("Cloned successfully!")

        self._is_cloned = True

    @property
    def folder_path(self) -> Path:
        return EXEC_INFO.cache_path / "remote"

    @property
    def is_cloned(self) -> bool:
        return self._is_cloned
