from pathlib import Path
import time
from fastapi.concurrency import asynccontextmanager
from fastapi.responses import HTMLResponse
from jinja2 import Environment, PackageLoader, select_autoescape
from common import SwipeAction
from fastapi import FastAPI, Request
from fastapi.templating import Jinja2Templates

from tinder_auto import Trainer, init


@asynccontextmanager
async def lifespan(app: FastAPI):
    # instantiate a global async httpx client to be used by all requests
    # will be automatically closed upon the app shutting down
    storage, session = init(
        out=Path("output"),
        # session_kwargs={"headless": True}
    )
    app.trainer: Trainer = Trainer(storage=storage, session=session)
    yield


app = FastAPI(lifespan=lifespan)
templates = Jinja2Templates(directory="templates")


@app.post("/login")
def login(method: str):
    pass


env = Environment(loader=PackageLoader("web_service"), autoescape=select_autoescape())


def next_match(action: SwipeAction | None = None):
    geomatch = next(app.trainer.next(action=action))
    uuid = "test"
    name = geomatch.name
    img = geomatch.image_urls[0]
    return {"uuid": uuid, "name": name, "img": img}


@app.get("/test")
def test():
    time.sleep(10)
    return "123"


@app.get("/", response_class=HTMLResponse)
def home():
    profile = env.get_template("profile.html")
    base_template = env.get_template("base.html")
    geomatch = next_match()
    return base_template.render(profile=profile, **geomatch)


@app.post("/swipe/{action}", response_class=HTMLResponse)
def swipe(request: Request, action: SwipeAction):
    return templates.TemplateResponse(
        request=request, name="profile.html", context=next_match(action=action)
    )
