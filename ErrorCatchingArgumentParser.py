from argparse import ArgumentParser


class ErrorCatchingArgumentParser(ArgumentParser):
    def exit(self, status=0, message=None):
        if status:
            raise Exception(message)
        exit(status)
