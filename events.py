from pathlib import Path
from pprint import pformat

from loguru import logger
from selenium.webdriver.common.by import By
from selenium.webdriver.support import expected_conditions as EC
from selenium.webdriver.support.wait import WebDriverWait

from common import SwipeAction, SwipeEvent


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
    logger.debug(f"Swipe Event element was located, got event: {swipe_event}")

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


class swipe_request_caught(object):
    def __init__(self):
        pass

    def __call__(self, driver):
        if driver.swipe_event is not None:
            driver.listening = False
            return driver.swipe_event
        else:
            return False


def catch_swipe_by_network_request(session, timeout) -> SwipeEvent:
    logger.info("You can swipe now!")
    logger.info("will be listening to network events")

    session.browser.listening = True

    swipe_event = WebDriverWait(
        session.browser, timeout=timeout, poll_frequency=0.1
    ).until(swipe_request_caught())

    session.browser.swipe_event = None

    logger.info(f"got swipe event from network: {pformat(swipe_event)}")

    return SwipeEvent(**swipe_event)
