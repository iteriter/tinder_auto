import json
import re
import time
from pathlib import Path
from typing import Literal, Optional

from loguru import logger

from tinderbotz.session import Session


class PersistentSession(Session):
    def __init__(self, session_file: Optional[Path] = None, *args, **kwargs):
        # self.auth_session_data = session_file
        super().__init__(*args, **kwargs)

        self.browser.listening = False
        self.browser.swipe_event = None

        def log_request_event(event):
            # print(f'[DRIVER] process pid: {os.getpid()}, parent pid: {os.getppid()}')
            # time.sleep(5)
            # logger.debug(pformat(event))
            target = event.get("params", {}).get("documentURL", "")
            # logger.info(target)

            # previous result has not been processed yet
            if not self.browser.listening:
                return

            if swipe_request := re.search(
                "api.gotinder.com/(?P<action>pass|like|superlike)/(?P<uuid>[a-z0-9]+)\?",
                target,
            ):
                logger.debug("action: " + swipe_request.group("action"))
                logger.debug("profile uuid: " + swipe_request.group("uuid"))
                self.browser.swipe_event = {
                    "action": (
                        "dislike"
                        if swipe_request.group("action") == "pass"
                        else swipe_request.group("action")
                    ),
                    "profile_uuid": swipe_request.group("uuid"),
                }
                logger.debug(self.browser.swipe_event)
                # self.browser.listening = False

        self.browser.add_cdp_listener("Network.requestWillBeSent", log_request_event)

    def login(self, auth_file: Path, auth_mode: Literal["phone", "facebook", "google"]):
        self.browser.get("https://tinder.com/")
        time.sleep(3)

        if self._is_logged_in():
            logger.debug("user already logged in")
            return

        # try to login with session data
        # with open("session.json", "r") as f:
        #     logger.debug("loading session data")
        #     auth_session_data = json.loads(f.read())
        #     self.set_local_storage(**auth_session_data["localStorage"])
        #     self.set_indexed_db(**auth_session_data["db"])

        time.sleep(3)
        self.browser.refresh()

        logger.debug(
            f"logged in with session data: {(logged_in := self._is_logged_in())}"
        )
        if logged_in:
            return

        # try logging in manually
        logger.debug("manually logging in")
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

        logger.debug("logging in using " + auth_mode)
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
