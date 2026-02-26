from char import IChar
from logger import Logger
from pather import Location, Pather
from item.pickit import PickIt
import template_finder
from town.town_manager import TownManager
from utils.misc import wait
from utils.run_timer import RunTimer
from ui import loading

class Pindle:

    name = "run_pindle"

    def __init__(
        self,
        pather: Pather,
        town_manager: TownManager,
        char: IChar,
        pickit: PickIt,
        runs: list[str]
    ):
        self._pather = pather
        self._town_manager = town_manager
        self._char = char
        self._pickit = pickit
        self.runs = runs

    def approach(self, start_loc: Location) -> bool | Location:
        # Go through Red Portal in A5
        Logger.info("Run Pindle")
        t = RunTimer.get()
        t.start("go_to_act5")
        loc = self._town_manager.go_to_act(5, start_loc)
        t.stop("go_to_act5")
        if not loc:
            return False
        t.start("traverse_to_portal")
        if not self._pather.traverse_nodes((loc, Location.A5_NIHLATHAK_PORTAL), self._char):
            t.stop("traverse_to_portal")
            return False
        t.stop("traverse_to_portal")
        wait(0.5, 0.6)
        t.start("enter_portal")
        found_loading_screen_func = lambda: loading.wait_for_loading_screen(2.0)
        if not self._char.select_by_template("A5_RED_PORTAL", found_loading_screen_func, telekinesis=False):
            t.stop("enter_portal")
            return False
        t.stop("enter_portal")
        return Location.A5_PINDLE_START

    def battle(self, do_pre_buff: bool) -> bool | tuple[Location, bool]:
        t = RunTimer.get()
        # Kill Pindle
        t.start("detect_pindle")
        if not template_finder.search_and_wait(["PINDLE_0", "PINDLE_1"], threshold=0.65, timeout=20).valid:
            t.stop("detect_pindle")
            return False
        t.stop("detect_pindle")
        if do_pre_buff:
            t.start("pre_buff")
            self._char.pre_buff()
            t.stop("pre_buff")
        # move to pindle
        t.start("traverse_to_pindle")
        if self._char.capabilities.can_teleport_natively:
            self._pather.traverse_nodes_fixed("pindle_safe_dist", self._char)
        else:
            if not self._pather.traverse_nodes((Location.A5_PINDLE_START, Location.A5_PINDLE_SAFE_DIST), self._char):
                t.stop("traverse_to_pindle")
                return False
        t.stop("traverse_to_pindle")
        t.start("combat")
        self._char.kill_pindle()
        t.stop("combat")
        t.start("post_kill_wait")
        wait(0.5, 0.8)
        t.stop("post_kill_wait")
        t.start("looting")
        picked_up_items = self._pickit.pick_up_items(self._char)
        t.stop("looting")
        return (Location.A5_PINDLE_END, picked_up_items)
