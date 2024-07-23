import enum


class SwipeAction(str, enum.Enum):
    Like = "like"
    Dislike = "dislike"
    Superlike = "superlike"


class SwipeEvent:
    def __init__(self, profile_uuid: str, action: SwipeAction):
        self.profile_uuid = profile_uuid
        self.action = action
