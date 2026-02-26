from char import IChar
from logger import Logger
from pather import Location, Pather
from item.pickit import PickIt
import template_finder
from town.town_manager import TownManager
from utils.misc import wait
from utils.run_timer import RunTimer
from ui import waypoint

class ShenkEld:

    name = "run_shenk"

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
        self._runs = runs

    def approach(self, start_loc: Location) -> bool | Location:
        Logger.info("Run Eldritch")
        # Go to Frigid Highlands
        t = RunTimer.get()
        t.start("open_wp")
        if not self._town_manager.open_wp(start_loc):
            t.stop("open_wp")
            return False
        t.stop("open_wp")
        wait(0.4)
        t.start("use_wp")
        if waypoint.use_wp("Frigid Highlands"):
            t.stop("use_wp")
            return Location.A5_ELDRITCH_START
        t.stop("use_wp")
        return False

    def battle(self, do_shenk: bool, do_pre_buff: bool, game_stats) -> bool | tuple[Location, bool]:
        t = RunTimer.get()
        # Eldritch
        game_stats.update_location("Eld")
        t.start("detect_eldritch")
        if not template_finder.search_and_wait(["ELDRITCH_0", "ELDRITCH_0_V2", "ELDRITCH_0_V3", "ELDRITCH_START", "ELDRITCH_START_V2"], threshold=0.65, timeout=20).valid:
            t.stop("detect_eldritch")
            return False
        t.stop("detect_eldritch")
        if do_pre_buff:
            t.start("pre_buff")
            self._char.pre_buff()
            t.stop("pre_buff")
        t.start("traverse_eldritch")
        if self._char.capabilities.can_teleport_natively:
            self._pather.traverse_nodes_fixed("eldritch_safe_dist", self._char)
        else:
            if not self._pather.traverse_nodes((Location.A5_ELDRITCH_START, Location.A5_ELDRITCH_SAFE_DIST), self._char, force_move=True):
                t.stop("traverse_eldritch")
                return False
        t.stop("traverse_eldritch")
        t.start("combat_eldritch")
        self._char.kill_eldritch()
        t.stop("combat_eldritch")
        loc = Location.A5_ELDRITCH_END
        wait(0.2, 0.3)
        t.start("looting_eldritch")
        picked_up_items = self._pickit.pick_up_items(self._char)
        t.stop("looting_eldritch")

        # Shenk
        if do_shenk:
            Logger.info("Run Shenk")
            game_stats.update_location("Shk")
            self._curr_loc = Location.A5_SHENK_START
            # No force move, otherwise we might get stuck at stairs!
            t.start("traverse_shenk")
            if not self._pather.traverse_nodes((Location.A5_SHENK_START, Location.A5_SHENK_SAFE_DIST), self._char):
                t.stop("traverse_shenk")
                return False
            t.stop("traverse_shenk")
            t.start("combat_shenk")
            self._char.kill_shenk()
            loc = Location.A5_SHENK_END
            wait(1.9, 2.4) # sometimes merc needs some more time to kill shenk...
            t.stop("combat_shenk")
            t.start("looting_shenk")
            picked_up_items |= self._pickit.pick_up_items(self._char)
            t.stop("looting_shenk")

        return (loc, picked_up_items)
