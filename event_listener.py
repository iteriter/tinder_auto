from loguru import logger

from selenium.webdriver.common.keys import Keys
from selenium.webdriver.support.abstract_event_listener import AbstractEventListener
from selenium.webdriver.support.event_firing_webdriver import EventFiringWebDriver

from tinderbotz.session import Session
from .common import SwipeAction


class SwipeListener(AbstractEventListener):
    # def after
    # action = ActionChains(self.browser)
    # action.send_keys(Keys.ARROW_LEFT).perform()

    # def after_change_value_of(self, element, driver) -> None:
    #     print("value changed:")
    #     print(element)

    def after_send_keys(self, *keys):
        # ignore key combinations
        if not len(keys) == 1:
            return

        match (key := keys[0]):
            case Keys.ARROW_RIGHT:
                logger.info("liked")
            case Keys.ARROW_LEFT:
                logger.info("disliked")
            case Keys.ENTER:
                logger.info("superliked")
            case _:
                return


def catch_swipe_by_presence(session, timeout) -> SwipeAction:
    raise NotImplementedError

    # wait until the current profile is removed from screen
    current_profile = session.browser.find_element(By.XPATH, X_PROFILE_PATH)
    session.browser.implicitly_wait(1)

    WebDriverWait(session.browser, timeout=timeout, poll_frequency=0.1).until(
        EC.staleness_of(current_profile)
    )

    # todo: intercept network request to get swipe action and target profile uuid

    return


def catch_swipe_request(request) -> Literal["like", "pass"]:
    """
    Check outgoing requests to see if a swipe has occured
    """
    pass


def catch_swipe_event():
    """
    Check if a swipe event has occured in DOM
    """
    pass


class EventFiringSession(Session):
    def __init__(
        self, headless=False, store_session=True, proxy=None, user_data=False
    ):
        super().__init__(headless, store_session, proxy, user_data)
        self.browser = EventFiringWebDriver(self.browser, SwipeListener())