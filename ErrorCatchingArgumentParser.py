from argparse import ArgumentParser
from typing import NoReturn


class ErrorCatchingArgumentParser(ArgumentParser):
    def exit(self, status: int = 0, message: str | None = None) -> NoReturn:
        if status:
            raise Exception(message)
        exit(status)
