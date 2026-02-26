from char import IChar
from logger import Logger
from pather import Location, Pather
from item.pickit import PickIt
import template_finder
from town.town_manager import TownManager
from utils.misc import wait
from utils.run_timer import RunTimer

from ui import waypoint

class Trav:

    name = "run_trav"

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
        # Go to Travincal via waypoint
        Logger.info("Run Trav")
        t = RunTimer.get()
        t.start("open_wp")
        if not self._town_manager.open_wp(start_loc):
            t.stop("open_wp")
            return False
        t.stop("open_wp")
        wait(0.4)
        t.start("use_wp")
        if waypoint.use_wp("Travincal"):
            t.stop("use_wp")
            return Location.A3_TRAV_START
        t.stop("use_wp")
        return False

    def battle(self, do_pre_buff: bool) -> bool | tuple[Location, bool]:
        t = RunTimer.get()
        # Kill Council
        t.start("detect_trav")
        if not template_finder.search_and_wait(["TRAV_0", "TRAV_1", "TRAV_20"], threshold=0.65, timeout=20).valid:
            t.stop("detect_trav")
            return False
        t.stop("detect_trav")
        if do_pre_buff:
            t.start("pre_buff")
            self._char.pre_buff()
            t.stop("pre_buff")
        t.start("traverse")
        if self._char.capabilities.can_teleport_natively:
            self._pather.traverse_nodes_fixed("trav_safe_dist", self._char)
        else:
            if not self._pather.traverse_nodes((Location.A3_TRAV_START, Location.A3_TRAV_CENTER_STAIRS), self._char, force_move=True):
                t.stop("traverse")
                return False
        t.stop("traverse")
        t.start("combat")
        self._char.kill_council()
        t.stop("combat")
        t.start("looting")
        picked_up_items = self._pickit.pick_up_items(self._char)
        wait(0.2, 0.3)
        # If we can teleport we want to move back inside and also check loot there
        if self._char.capabilities.can_teleport_natively or self._char.capabilities.can_teleport_with_charges:
            if not self._pather.traverse_nodes([229], self._char, timeout=2.5, use_tp_charge=self._char.capabilities.can_teleport_natively):
                self._pather.traverse_nodes([228, 229], self._char, timeout=2.5, use_tp_charge=True)
            picked_up_items |= self._pickit.pick_up_items(self._char)
        t.stop("looting")
        # If travincal run is not the last run
        if self.name != self._runs[-1]:
            # Make sure we go back to the center to not hide the tp
            self._pather.traverse_nodes([230], self._char, timeout=2.5)
        return (Location.A3_TRAV_CENTER_STAIRS, picked_up_items)
