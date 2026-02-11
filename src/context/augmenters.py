import datetime
from abc import ABC, abstractmethod
import importlib
from typing import Dict, Optional


class AbsAugmenter(ABC):
    def __init__(self, name, **kwargs):
        self.extra_info = None
        self.name = name

    async def augment(self, context, **kwargs):
        context.system_prompt = context.system_prompt + '\n' + self.build_extraInfo()
        return context

    @abstractmethod
    def build_extraInfo(self):
        pass


class TimeAugmenter(AbsAugmenter):
    def __init__(self, **kwargs):
        super().__init__("time_augmenter", **kwargs)

    def build_extraInfo(self):
        return f'当前时间: {datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")}'


class ScheduleAugmenter(AbsAugmenter):
    def __init__(self, schedule: str, **kwargs):
        super().__init__("schedule_augmenter", **kwargs)
        self.schedule = schedule

    def build_extraInfo(self):
        return self.schedule + " 请根据日程表调整你的回复"

    async def augment(self, context, **kwargs):
        context.schedule = self.schedule
        return context


class MotionAugmenter(AbsAugmenter):
    def __init__(self, **kwargs):
        super().__init__("motion_augmenter", **kwargs)
        self.motion = [
            "ActionAttentionSeeking.bvh", "ActionCrawling.bvh", "ActionGaming.bvh", "ActionGreeting.bvh",
            "ActionGreeting1.bvh",
            "ActionJog.bvh", "ActionJump.bvh", "ActionLaydown.bvh", "ActionPat.bvh", "ActionPickingup.bvh",
            "ActionRun.bvh", "ActionStandup.bvh", "ActionWalk.bvh", "Couch.bvh", "Dance1.bvh", "Dance2.bvh",
            "DanceBackup.bvh", "DanceDab.bvh", "DanceGangnamStyle.bvh", "DanceHeaddrop.bvh", "DanceMarachinostep.bvh",
            "DanceNorthernSoulSpin.bvh", "DanceOntop.bvh", "DancePushback.bvh", "DanceRumba.bvh",
            "ExerciseCrunch.bvh", "ExerciseCrunches.bvh", "ExerciseJogging.bvh", "ExerciseJumpingJacks.bvh",
            "HitareaButt.bvh",
            "HitareaChest.bvh", "HitareaFoot.bvh", "HitareaGroin.bvh", "HitareaHands.bvh", "HitareaHead.bvh",
            "HitareaLeg.bvh", "NeutralIdle.bvh", "NeutralIdle2.bvh", "ReactionGroinhit.bvh", "ReactionHeadshot.bvh",
            "admiration.bvh", "admiration2.bvh", "admiration3.bvh", "amusement.bvh", "amusement2.bvh", "amusement3.bvh",
            "anger.bvh",
            "anger2.bvh", "anger3.bvh", "annoyance.bvh", "annoyance1.bvh", "approval.bvh",
            "approval2.bvh", "approval3.bvh", "caring.bvh", "caring1.bvh",
            "confusion.bvh", "confusion2.bvh", "confusion3.bvh", "curiosity.bvh", "curiosity2.bvh",
            "curiosity3.bvh", "desire.bvh", "desire1.bvh", "desire2.bvh", "disappointment.bvh",
            "disappointment2.bvh", "disapproval.bvh", "disaproval1.bvh", "disgust.bvh", "disgust1.bvh",
            "disgust2.bvh", "embarrassment.bvh", "excitement.bvh", "excitement2.bvh", "excitement3.bvh",
            "fear.bvh", "fear2.bvh", "fear3.bvh", "gratitude.bvh", "grief.bvh", "joy.bvh", "joy2.bvh",
            "joy3.bvh", "love.bvh", "love2.bvh", "love3.bvh", "nervousnes3.bvh", "nervousness.bvh",
            "nervousness2.bvh", "neutral.bvh", "neutral2.bvh", "neutral3.bvh", "neutral4.bvh",
            "optimism.bvh", "pride.bvh", "pride2.bvh", "realization.bvh", "relief.bvh", "relief1.bvh",
            "remorse.bvh", "remorse2.bvh", "remorse3.bvh", "sadness.bvh", "sadness2.bvh", "sit.bvh", "sit2.bvh",
            "surprise.bvh",
            "surprise2.bvh"
        ]

    def build_extraInfo(self):
        return "你可以在回复中使用 “[name: + 动作名称]” 来触发动作, 例如 [name:ActionJump] \n 可用动作有: " + ", ".join(self.motion) + "但你一次回复当中只能触发至多1个动作"


REGISTRY: Dict[str, type] = {
    "time_augmenter": TimeAugmenter,
    "schedule_augmenter": ScheduleAugmenter,
    "motion_augmenter": MotionAugmenter,
}


def resolve_augmenter_class(name: str) -> Optional[type]:
    if name in REGISTRY:
        return REGISTRY[name]
    if "." in name:
        try:
            module_path, cls_name = name.rsplit(".", 1)
            module = importlib.import_module(module_path)
            return getattr(module, cls_name, None)
        except Exception:
            return None
    return None


def create_augmenter(name: str, params: Optional[dict] = None):
    cls = resolve_augmenter_class(name)
    if not cls:
        return None
    params = params or {}
    try:
        return cls(**params)
    except Exception:
        return None
