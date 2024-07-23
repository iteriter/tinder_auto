# src: https://stackoverflow.com/questions/33987060/python-context-manager-that-measures-time

from time import perf_counter

from loguru import logger


class catchtime:
    def __init__(self, message: str) -> None:
        self.msg = message

    def __enter__(self):
        self.start = perf_counter()
        return self

    def __exit__(self, type, value, traceback):
        self.time = perf_counter() - self.start

        self.readout = f"{self.msg} took: {self.time:.3f} seconds"
        logger.debug(self.readout)
