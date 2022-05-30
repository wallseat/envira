import argparse
from typing import Dict, Type

import tomli

from envira.environment import EXEC_INFO, SYS_INFO, Environment, set_config_file
from envira.git import GitLoader
from envira.providers import BaseProvider, get_providers
from envira.utils import is_path, is_url


class Configurator:
    env: Environment
    providers: Dict[str, Type[BaseProvider]]

    def __init__(self, env: Environment) -> None:
        self.env = env

        self._prepare_providers()

    def load(self, force: bool = False):
        with open(self.env.config_path, "r") as f:  # type: ignore
            prepared_raw_data = self._unfold_macro(f.read())
            conf_obj = tomli.loads(prepared_raw_data)

        for section in self.providers:
            if section in conf_obj:
                provider = self.providers[section](conf_obj[section])

                if provider.apply(force=force, env=self.env):
                    return

    def _prepare_providers(self) -> None:
        self.providers = {
            provider.section_key: provider
            for provider in sorted(get_providers(), key=lambda x: x.priority)  # type: ignore
        }

    @staticmethod
    def _unfold_macro(raw_data: str):
        return (
            raw_data.replace("${distr_name}", SYS_INFO.id_)
            .replace("${distr_ver}", SYS_INFO.version)
            .replace("${user}", EXEC_INFO.uname)
            .replace("${home}", EXEC_INFO.uhome)
        )


def prepare_args() -> argparse.Namespace:
    argparser = argparse.ArgumentParser(prog="envira")

    argparser.add_argument(
        "path_or_url",
        type=str,
        help="Path to folder or remote repository with configuration",
    )

    argparser.add_argument(
        "-c", "--config-name", type=str, help="Set envira config file name"
    )

    argparser.add_argument(
        "-f",
        "--force",
        action="store_true",
        default=False,
        help="Allow envira fix and overwrite dirs and files",
    )

    return argparser.parse_args()


def main() -> int:
    if EXEC_INFO.euid != 0:
        print(
            "You need to have root privileges to run this script.\n"
            "Please try again, this time using 'sudo'. Exiting."
        )
        return 1

    if SYS_INFO.os != "linux":
        print(f"Platform {SYS_INFO.os} not currently supported!")
        return 1

    args = prepare_args()

    if args.config_name:
        set_config_file(args.config_name)

    if is_url(args.path_or_url):
        git_loader = GitLoader(args.path_or_url)
        git_loader.clone()

        if not git_loader.is_cloned:
            print("Cloning failed!")
            return 1

        path = git_loader.folder_path

    elif is_path(args.path_or_url):
        path = EXEC_INFO.exc_path / args.path_or_url

    else:
        print("Invalid URL or path!")
        return 1

    environment = Environment(path)

    if environment.prepared:
        configurator = Configurator(environment)
        configurator.load(force=args.force)

    else:
        print("Failed to prepare an environment!")
        return 1

    return 0


if __name__ == "__main__":
    import sys

    sys.exit(main())
