import abc
import argparse
import sys
import random
import time
from typing import Optional
from pathlib import Path
import os

from loguru import logger
from common import SwipeAction

from events import catch_swipe_by_network_request
from session import PersistentSession
from storage import ProfileStore, record_geomatch

from timer import catchtime
from tinderbotz.helpers.geomatch import Geomatch
from tinderbotz.helpers.geomatch_helper import GeomatchHelper
from tinderbotz.session import Session


logger.remove()


AUTH_FILE = "auth.txt"
USER_SESSION_FILE = ".session.json"

parser = argparse.ArgumentParser(
    prog="tinder_auto",
    description="What the program does",
)
parser.add_argument(
    "mode",
    choices=["training", "auto"],
    help="script running mode. if training is selected, script "
    "will launch tinder session and wait to receive swipe input. "
    "currently only programmatic input is supported (i.e. via Selenium send_keys) "
    "if no action is supplied for a --timeout, script will exit",
)
parser.add_argument(
    "--debug",
    action="store_const",
    const="DEBUG",
    default="INFO",
    dest="log_level",
    help="set logging level to DEBUG",
)
parser.add_argument(
    "--auth_type",
    choices=["phone", "facebook", "google"],
    required=True,
    help="which login method to use",
)
parser.add_argument(
    "--auth_file",
    type=Path,
    default=AUTH_FILE,
    metavar="FILEPATH",
    help="path to file with the auth credentials separeted by semicolon (:)",
)
parser.add_argument(
    "--out",
    type=Path,
    default="output",
    help="folder where to output swipe data",
    metavar="PATH",
)
parser.add_argument(
    "--timeout",
    type=int,
    default=300,
    help="how many seconds to wait for a user input action when in training mode",
    metavar="SECONDS",
)


class Matchmaker(abc.ABC):
    @abc.abstractmethod
    def decide(self, profile: Geomatch) -> SwipeAction:
        pass


class RandomMatchmaker(Matchmaker):
    def __init__(self, ratio: int) -> None:
        super().__init__()

        if not 0 < ratio < 100:
            raise ValueError("ratio must be between 1 and 99%")

        self.threshold = ratio / 100

    def decide(self, *args, **kwargs):
        if random.random() < self.threshold:
            return SwipeAction.Like
        else:
            return SwipeAction.Dislike


def get_geomatch(session: Session) -> Geomatch:
    with catchtime("parsing profile"):
        geomatch: Optional[Geomatch] = session.get_geomatch(quickload=True)

    logger.info(
        f"Profile data parsed for {geomatch.name}, got {len(geomatch.image_urls)} image urls"
    )
    if not geomatch or not (geomatch.name and geomatch.image_urls):
        raise ValueError("geomatch doesn't have name or images")

    return geomatch


class Trainer:
    def __init__(
        self, *, session: Session, storage: ProfileStore, idle_timeout: int = 300
    ) -> None:
        self.session = session
        self.storage = storage
        self.idle_timeout = idle_timeout

        self.helper = GeomatchHelper(browser=session.browser)
        self.match = None

    def next(self, action: SwipeAction | None):
        logger.debug(f"[SCRIPT] process pid: {os.getpid()}, parent pid: {os.getppid()}")
        logger.info("getting geomatch")

        match action:
            case SwipeAction.Like:
                self.helper.like()
            case SwipeAction.Dislike:
                self.helper.dislike()
            case _:
                pass

        if action is not None:
            event = catch_swipe_by_network_request(self.session, self.idle_timeout)

            # store swipe and profile data
            record_geomatch(
                storage,
                event,
                geomatch=self.match,
            )

            # let the page update after swipe before parsing next match
            time.sleep(2)
            self.match = get_geomatch(self.session)
        elif not self.match:
            self.match = get_geomatch(self.session)

        yield self.match


def launch_training(storage, session, idle_timeout):
    """"""
    # loop until exited or times out
    while True:
        logger.debug(f"[SCRIPT] process pid: {os.getpid()}, parent pid: {os.getppid()}")
        logger.info("getting geomatch")
        try:
            geomatch = get_geomatch(session)
        except ValueError as e:
            logger.error(f"failed to get geomatch info: {e}")
            input("press enter to continue")
            continue

        # wait for the user action to happen, and get the action type (like/dislike/superlike)
        logger.info("waiting for swipe event")
        # action = catch_swipe_by_js_events(session, idle_timeout)
        event = catch_swipe_by_network_request(session, idle_timeout)

        # store swipe and profile data
        record_geomatch(
            storage,
            event,
            geomatch=geomatch,
        )

        # let the page update after swipe before parsing next match
        time.sleep(2)


def run_auto(
    session, storage, max_runtime: Optional[int] = 15, n_profiles: Optional[int] = None
):
    """
    max_runtime: int = default 15, amount of time in minutes for which
                       the agent is allowed ro run.
    """
    if n_profiles:
        logger.info(
            "Number of profiles set as target for the agent. \
                     max_runtime value will be ignored"
        )
        max_runtime = None

        if n_profiles > 100:
            logger.warning(
                "Warning! Is it really a good idea to parse more than 100 \
                            profiles in one session?"
            )

    if max_runtime and max_runtime > 120:
        logger.warning(
            "Warning! Is it really a good idea to let the agent run for \
                        more than 2 hours?"
        )

    profiles_swiped = 0
    while (n_profiles and (profiles_swiped <= n_profiles)) or (
        max_runtime and True
    ):  # todo: update to check conditions above
        geomatch = get_geomatch(session)

        action: SwipeAction = RandomMatchmaker(ratio=70).decide(geomatch)
        helper = GeomatchHelper(browser=session.browser)

        match action:
            case SwipeAction.Superlike:
                # todo: handle out of superlikes
                helper.superlike()
            case SwipeAction.Like:
                helper.like()
            case SwipeAction.Dislike:
                helper.dislike()
        # i wanted to do "getattr(helper, action.value)()" but its probably too unreadable :P

        profiles_swiped += 1
        # todo: save profile

        # todo: sleep for random amount of time


def init(out: Path, log_level: str = "INFO", session_kwargs: dict | None = None):
    if not session_kwargs:
        session_kwargs = {}

    logger.add(sys.stderr, level=log_level)
    storage = ProfileStore(out)
    # launch selenium driver, try to login with stored sesssion if exists, otherwise use user credentials
    session = PersistentSession(session_file=Path(USER_SESSION_FILE), **session_kwargs)
    while not session._is_logged_in():
        session.login(auth_file=args.auth_file, auth_mode=args.auth_type)
    return storage, session


if __name__ == "__main__":
    args = parser.parse_args()

    storage, session = init(out=args.out, log_level=args.log_level)

    if args.mode == "training":
        launch_training(
            session=session,
            storage=storage,
            idle_timeout=args.timeout,
        )
    elif args.mode == "auto":
        raise NotImplementedError
