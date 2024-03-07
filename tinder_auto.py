import argparse
import enum
import json
import re
import sys
from typing import Literal, Optional
from pathlib import Path
import requests

import time
from loguru import logger

from selenium.webdriver.common.by import By
from selenium.webdriver.support.wait import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC

from tinderbotz.session import Session
from tinderbotz.helpers.geomatch import Geomatch
from tinderbotz.helpers.xpaths import content


logger.remove()


AUTH_FILE = "auth.txt"
USER_SESSION_FILE = ".session.json"

X_PROFILE_PATH = f"{content}/div/div[1]/div/main/div[1]/div/div/div[1]/div[1]/div/div[2]/div[1]/div/div[1]/div/h1"

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


class SwipeAction(str, enum.Enum):
    Like = "like"
    Dislike = "dislike"
    Superlike = "superlike"


class PersistentSession(Session):
    def __init__(self, session_file: Optional[Path] = None, *args, **kwargs):
        self.session_data = session_file
        super().__init__(*args, **kwargs)

    def login(self, auth_file: Path, auth_mode: Literal["phone", "facebook", "google"]):
        self.browser.get("https://tinder.com/")
        time.sleep(3)

        # try to login with session data
        with open("session.json", "r") as f:
            session_data = json.loads(f.read())
            self.set_local_storage(**session_data["localStorage"])
            self.set_indexed_db(**session_data["db"])

        time.sleep(3)

        self.browser.refresh()
        if self._is_logged_in():
            return

        # try logging in manually
        auth_data = auth_file.read_text().strip().split(":")

        if not len(auth_data) == 2:
            raise ValueError("invalid authentication data provided")

        auth_func = None
        match auth_mode:
            case "phone":
                auth_func = self.login_using_sms
            case "facebook":
                auth_func = self.login_using_facebook
            case "google":
                auth_func = self.login_using_google
            case _:
                raise NotImplementedError

        auth_func(*auth_data)

        # todo: save session after authorization
        # self.save_session()

    def set_local_storage(self, **kwargs):
        for key, value in kwargs.items():
            self.browser.execute_script(
                "window.localStorage.setItem(arguments[0], arguments[1]);", key, value
            )

    def set_indexed_db(self, **kwargs):
        """
        Connect to Tinder's storage in IndexedDB
        and set session data to reuse login
        """
        sessionValues = "\n".join(
            [
                f"await server.keyval.put({{key: {json.dumps(key)}, item: {json.dumps(value)}}});"
                for key, value in kwargs.items()
            ]
        )

        script = f"""
            (async () => {{
            const onDbLoad = async () => {{
                    const server = await db.open({{server: "keyval-store"}});
                    {sessionValues}
            }}

            const script = document.createElement("script")
            script.type = "text/javascript"
            script.src = "https://rawcdn.githack.com/aaronpowell/db.js/11b4b071573e571389655927f8574b2b89723b04/dist/db.min.js"
            script.addEventListener("load", onDbLoad)
            document.getElementsByTagName("head")[0].appendChild(script);
            }})();
        """

        self.browser.execute_script(script)

    def save_session(self):
        """
        Dump session data from local storage
        to reuse when logging in
        """
        raise NotImplementedError


def catch_swipe_by_js_events(session, timeout) -> SwipeAction:
    event_catch_script = Path("swipeEventListener.js").read_text()
    session.browser.execute_script(event_catch_script)

    logger.info("You can swipe now!")

    user_swipe_event_element = WebDriverWait(
        session.browser, timeout=timeout, poll_frequency=0.1
    ).until(
        EC.presence_of_element_located((By.CSS_SELECTOR, '[class^="userSwipeAction"]'))
    )

    swipe_event = user_swipe_event_element.get_attribute("value")
    logger.debug(
        f"Swipe Event element was located, got event: {swipe_event}"
    )

    logger.info(f"Swipe catched -- {swipe_event}")
    logger.info("Please wait while the profile is being processed...")

    # remove event element
    session.browser.execute_script(
        """
                                   var eventDivs = document.getElementsByClassName("userSwipeAction");
                                   while (eventDivs[0]) {
                                    eventDivs[0].parentNode.removeChild(eventDivs[0]);
                                   }
                                   """
    )

    logger.debug("Waiting for the event element to be removed")
    user_swipe_event_element = WebDriverWait(
        session.browser, timeout=timeout, poll_frequency=0.1
    ).until_not(
        EC.presence_of_element_located((By.CSS_SELECTOR, '[class^="userSwipeAction"]'))
    )
    logger.debug("Event element removed")

    return SwipeAction(swipe_event)


class ProfileStore:
    def __init__(self, folder: Path) -> None:
        # init file for recording profile/image ids

        if folder.exists() and folder.is_file():
            raise ValueError("output path should point to a folder")

        folder.mkdir(
            parents=True, exist_ok=True
        )  # create output folder if doesn't exist
        self.outfile = folder / "out.txt"
        self.outfile.touch()

        # init folder for storing images
        (folder / "images").mkdir(exist_ok=True)
        self.image_folder = folder / "images"

        self.last_entry_id = 0

        # update last entry id if there is some data already
        with open(self.outfile, "r+") as f:
            if len((lines := f.readlines()) and lines[-1]) > 0:
                max_existing_id = int(lines[-1].split(":")[0])
                self.last_entry_id = max_existing_id + 1

    def save_profile(self, action: str, image_urls: list[str]):
        image_path = self.image_folder / f"{self.last_entry_id}.jpg"
        for url in image_urls:
            matched = re.match(r'url\("(.+)"\)', url)

            if not matched:
                continue
            url = matched.group(1)

            try:
                r = requests.get(url)
            except Exception as e:
                logger.error(f"error getting an image from url: {url}")
                logger.error(e)
                continue
            if not 200 <= r.status_code <= 299:
                logger.error(f"got error code {r.status_code} for url: {url}")
                continue

            # ext = os.path.splitext(url)[-1]
            logger.debug(f"saving image to {image_path}")

            with open(image_path, "wb") as f:
                f.write(r.content)

            # we only want to store one image
            break

        # record swipe for the profile
        with open(self.outfile, "a") as profiles:
            profiles.write(f"{self.last_entry_id}:{action}\n")

        self.last_entry_id += 1


def record_geomatch(storage: ProfileStore, geomatch: Optional[Geomatch], action: str):
    if not geomatch:
        logger.error("faled to get a Geomatch informatin")
        return False

    name, images = geomatch.name, geomatch.image_urls
    if not name or not images:
        logger.info("Geomatch is missing name or images, skipping...")
        return False

    # save profile image and record swipe action
    logger.info(f"Saving match record for {name}")
    storage.save_profile(action, images)

    return True


def launch_training(auth_file, auth_mode, idle_timeout, out_folder):
    """"""
    storage = ProfileStore(out_folder)

    # launch selenium driver, try to login with stored sesssion if exists, otherwise use user credentials
    session = PersistentSession(session_file=Path(USER_SESSION_FILE))
    session.login(auth_file=auth_file, auth_mode=auth_mode)

    # loop until exited or times out
    while True:
        geomatch: Optional[Geomatch] = session.get_geomatch(quickload=True)

        logger.info(
            f"Profile data parsed for {geomatch.name}, got {len(geomatch.image_urls)} image urls"
        )

        # wait for the user action to happen, and get the action type (like/dislike/superlike)
        action = catch_swipe_by_js_events(session, idle_timeout)

        # map action to the required output values
        # todo: get mapper implementation dynamically,
        #       or implement mapping as part of the storage interface
        action_code = "no" if action == SwipeAction.Dislike else "yes"

        # store swipe and profile data
        record_geomatch(storage, geomatch, action_code)

        # let the page update after swipe before parsing next match
        time.sleep(2)


if __name__ == "__main__":
    args = parser.parse_args()

    logger.add(sys.stderr, level=args.log_level)

    if args.mode == "training":
        launch_training(
            auth_file=args.auth_file,
            auth_mode=args.auth_type,
            idle_timeout=args.timeout,
            out_folder=args.out,
        )
    elif args.mode == "auto":
        raise NotImplementedError
