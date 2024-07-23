import re
from pathlib import Path

import requests
from typing import Optional
from loguru import logger

from common import SwipeEvent
from tinderbotz import Geomatch


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
        # with open(self.outfile, "r+") as f:
        #     if len((lines := f.readlines()) and lines[-1]) > 0:
        #         max_existing_id = int(lines[-1].split(":")[0])
        #         self.last_entry_id = max_existing_id + 1

    def save_profile(
        self, uuid: str, action: str, image_urls: list[str], name: Optional[str]
    ):
        image_path = self.image_folder / f"{uuid}.jpg"
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
            profiles.write(f"{uuid}:{name}:{action}\n")

        self.last_entry_id += 1


def record_geomatch(
    storage: ProfileStore, event: SwipeEvent, *, geomatch: Optional[Geomatch]
):
    if not geomatch:
        logger.error("faled to get a Geomatch informatin")
        return False

    if not (geomatch.name and geomatch.image_urls):
        logger.error("Geomatch is missing name or images, skipping...")
        return False

    # save profile image and record swipe action
    logger.info(f"Saving match record for {geomatch.name}")
    storage.save_profile(
        event.profile_uuid, event.action, geomatch.image_urls, geomatch.name
    )

    return True
