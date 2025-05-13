import sys
import os
import math
import json
import time
import shutil
import glob
from datetime import datetime
import pandas as pd

from CustomService import CustomLS10
from CustomSequence import CustomSequence


#######################################################################################################################

# red side is the sample collection side of the permeation cells, it is A* and B*
# green side is the feed side of the permeation cells, it is C* and D*


class AMEWS:
    def __init__(self):
        self.verbose = 1
        self.cont = False  # continue a previous run

        self.path = os.getcwd()
        self.user = os.getlogin()
        self.num_cells = 4

        self.cells = ["A1", "A2", "B1", "B2"]  # red/sample compartments in each cell
        self.counters = [
            self.cell2counter(x) for x in self.cells
        ]  # green/feed compartments in each cell
        print("\n>> Cells, sample compartments (rewd): %s" % self.cells)
        print(">> Cells, feed compartments (green): %s\n" % self.counters)
        self.cell_rack = "Rack 4x2 Mina H-cell"
        self.cell_map = {
            "plate1": "Deck 12-13 Heat-Cool-Stir 1",
            "plate2": "Deck 12-13 Heat-Stir 2",
            "plate3": "Deck 12-13 Heat-Stir 3",
            "plate4": "Deck 14-15 Heat-Stir 1",
            "plate5": "Deck 14-15 Heat-Stir 2",
            "plate6": "Deck 14-15 Heat-Stir 3",
        }

        self.farm = None  # complete map of cells

        self.ICP_area = "*"  # first row fill, use "*" or "full" for full rack
        self.sources = "BK_AMEWS_24cell_input.csv"
        self.fills = "BK_AMEWS_24cell_fill.csv"  # put None for default filling
        self.exp_path = r"Z:\RESULTS"
        self.AS = False  # run AS
        self.rack = 90  # 90 tube rack
        self.blank = True  # collect red side blanks first
        self.load = True  # load solvent into cells
        self.load_delay = 0  # delay after loading, hours
        self.volume = 100  # ul sampling of the red side
        self.fill = 500  # uL if there is no fill map, 0 to ignore
        self.volume_sample = 31.5e3  # uL volume of the cell on the sample side  (red)
        self.volume_feed = 18.7e3  # uL volume of the cell on the feed side (green)
        self.chaser = 2300  # uL chaser
        self.delay = 0.10  # minutes to wait after each sampling
        self.laps = 3  # laps of sample collection
        self.calibrate = 100  # uL aliquots for calibrations - adjust
        self.last_container = {}  # sample container
        self.std_conc = 20  # concentration of the standard (yittrium)
        self.unit = "ppm"  # concentration unit
        self.category = "start"  # category of the experimental step
        self.farm = None  # cell farm

        self.check_volumes()
        self.null_prep()
        self.ld = CustomLS10()
        self.ld.verbose = self.verbose

    def check_volumes(self):
        self.syringe6 = 1000  # uL the volume of syringe 6
        self.syringe7 = 2500  # uL the volume of syringe 7

        if self.fill > self.syringe6:
            self.fill = self.syringe6
            print(">> Adjusted fill volume to %.1f ul\n\n" % self.fill)

        if self.volume > self.syringe6:
            self.volume = self.syringe6
            print(">> Adjusted fill volume to %.1f ul, no chaser\n\n" % self.volume)

        if self.chaser > self.syringe7:
            self.chaser = self.syringe7
            print(">> Adjusted chaser volume to %.1f ul\n\n" % self.chaser)

    def cell2counter(self, c):
        if len(c) > 1:
            return "%s%s" % (chr(ord(c[0]) + 2), c[1:])
        else:
            return ""

    def counter2cell(self, c):
        if len(c) > 1:
            return "%s%s" % (chr(ord(c[0]) - 2), c[1:])
        else:
            return ""

    def index2cell(self, cells, i):
        n = len(cells)
        j = i % self.num_cells
        p = math.floor(j / n)
        c = j - p * n
        return "plate%d" % (p + 1), c

    def cell2index(self, cells, plate, well):
        p = int(plate.replace("plate", ""))
        return (p - 1) * len(cells) + cells.index(well)

    def find_last_cell(self):
        _, plate, well, _, _, _, _ = self.ld.tm.mapping[-1]
        self.last_cell = self.cell2index(self.cells, plate, well)
        print(
            ">> Last probed cell is %s, %s => index %d"
            % (plate, well, 1 + self.last_cell)
        )
        self.last_cell += 1

    def null_prep(self):
        self.prep = 0  # holds the initial fill tm.mapping offset
        self.prep_container = {}  # prep container

    def start_sequence(self):  # start a sequence of experiments
        self.category = "start"
        if self.cont:
            return 0
        now = datetime.now()
        stamp = now.strftime("%Y%m%d_%H%M%S")
        self.exp = os.path.join(self.exp_path, "BK_run24_%s" % stamp)
        if self.exp:
            os.makedirs(self.exp, exist_ok=True)
        self.master_log = []
        self.null_prep()
        self.COUNT = 0  # counter of LS calls
        self.last_cell = 0  # offset of the first cell to fill

        # make cell maps

        rs = []

        for i in range(self.num_cells):
            plate, c = self.index2cell(self.cells, i)
            r = {}
            r["label"] = "%s-%s-IN" % (plate, self.cells[c])
            r["cell"] = i + 1
            r["address"] = "%s:%s" % (plate, self.cells[c])
            rs.append(r)
            r = {}
            r["label"] = "%s-%s-OUT" % (plate, self.counters[c])
            r["cell"] = i + 1
            r["address"] = "%s:%s" % (plate, self.counters[c])
            rs.append(r)

        self.farm = pd.DataFrame(rs)
        f = os.path.join(self.exp, "cell farm.csv")
        self.farm.to_csv(f, index=False)
        print("\n>> Cell farm of %d cells:\n%s\n" % (self.num_cells, self.farm))

        return 1

    # ================================ json serialization =================================

    def to_json(self):
        now = datetime.now()
        stamp = now.strftime("%Y%m%d_%H%M%S")
        j = {
            # specific to 24-cell experiment
            "category": self.category,  # category of the step in sequence
            "load": self.load,  # whether to fill the cells with solvent
            "load equilibration": self.load_delay,  # equilibration time after loading, hours
            "cells": self.cells,  # cells in a plate
            "farm": self.farm.to_json(orient="records", lines=False),  # cell farm
            "counters": self.counters,  # cell counterparts in a plate
            "cell number": self.num_cells,  # total number of cells
            "last cell": self.last_cell,  # used to continue runs
            "standard concentration": self.std_conc,  # ICP standard (yittriun) concentration
            "unit concentration": self.unit,  # unit of concentration
            "continue": self.cont,  # continue a run
            "sources": self.sources,  # name of the input source file
            "ICP area": self.ICP_area,  # ICP rack area, deafualt is full
            "fills": self.fills,  # name of the input fill file
            "path": self.path,  # work directory
            "experiment": self.exp,  # experiment (sequence) grab bag folder
            "calibrate": self.calibrate,
            "rack": self.rack,
            "blank": self.blank,
            "fill": self.fill,
            "volume": self.volume,
            "volume cell sample": self.volume_sample,
            "volume cell feed": self.volume_feed,
            "chaser": self.chaser,
            "delay": self.delay,
            "laps": self.laps,
            "do AS": self.AS,
            "prep": self.prep,  # last rack offset
            "prep_container": self.prep_container,  # prep container
            "last_container": self.last_container,  # last sample container
            "master log": self.master_log,
            "last ID": self.ld.ID,  # last library ID
            "COUNT": self.COUNT,  # last experiment count
            # ld attributes
            "prompts": self.ld._prompts,  # last prompt input file
            "chem": self.ld._chem,  # last chem library input file
            "code": self.ld.last_code,  # last container code
            "AS pause": self.ld.as_pause,  # AS pause message
            "AS state": self.ld.as_state,  # AS state
            "rack barcode": self.ld.last_barcode,  # barcode
            "door interlock": self.ld.door,  # if 0 not interlocked
        }

        u = os.path.join(self.exp, "%s_%s.json" % (self.category, stamp))
        with open(u, "w") as f:
            json.dump(j, f, indent=4)
        return j

    def from_json(self, j):
        # Populate the class instance from the JSON data (dictionary)

        now = datetime.now()
        stamp = now.strftime("%Y%m%d_%H%M%S")

        # folders
        if self.verbose == 2:
            print("\n>> JSON input: %s\n" % j)

        self.farm = None
        u = j.get("farm", None)
        if u:
            self.farm = pd.read_json(u)

        self.cont = j.get("continue", False)  # resume previous run
        self.category = j.get("category", None)
        self.path = j.get("path", os.getcwd())
        self.exp = j.get("experiment", None)
        if not self.exp:
            self.exp = os.path.join(self.exp_path, "Experiments", "run24_%s" % stamp)
        os.makedirs(self.exp, exist_ok=True)

        # cell information
        self.load = j.get("load", False)
        self.load_delay = j.get("load equilibration", 2)
        self.cells = j.get("cells")
        self.counters = j.get("counters")
        self.num_cells = j.get("cell number", 2)
        self.last_cell = j.get("last cell", 0)

        self.ICP_area = j.get("ICP area", "full")
        self.sources = j.get("sources")
        self.fills = j.get("fills")

        self.volume = j.get("volume", 250)
        self.volume_sample = j.get("volume cell sample", 3e4)
        self.volume_feed = j.get("volume cell feed", 2e4)
        self.calibrate = j.get("calibrate", self.volume / 2)
        self.std_conc = j.get("standard concentration", 10)
        self.unit = j.get("unit concentration", "mM")
        self.rack = j.get("rack", 90)
        self.blank = j.get("blank", True)
        self.fill = j.get("fill", 1000)
        self.chaser = j.get("chaser", 2500)
        self.delay = j.get("delay", 0)
        self.laps = j.get("laps", 2)
        self.AS = j.get("do AS", False)
        self.prep = j.get("prep", 0)
        self.last_container = j.get("last_container", {})
        self.prep_container = j.get("prep_container", {})
        self.master_log = j.get("master log", [])
        self.COUNT = j.get("COUNT", 0)

        # setting ld attributes
        self.ld.ID = j.get("last ID", 0)
        self.ld.ID_folder()
        self.ld._prompts = j.get("prompts", "")
        self.ld._chem = j.get("chem", "")
        self.ld.last_code = j.get("code", "")
        self.ld.tracker.unit = self.unit

    def save_samples(self, name):
        u = os.path.join(self.exp, "%s.json" % name)
        with open(u, "w") as f:
            json.dump(self.ld.tracker.samples, f, indent=4)

    ##########################################  the common opening steps #####################################################

    def LS_open(self, cells, name="sampling"):
        self.ld = CustomLS10()
        self.ld.tracker.unit = self.unit

        self.ld.create_lib(name)
        self.ld.disp.COUNT = self.COUNT
        self.COUNT += 1

        print("\n\n")
        print("#" * 80)
        print("#\t\tAMEWS %s" % name.upper())
        print("#" * 80)
        print("\n\n")

        n = len(self.cells)

        self.ld.add_param("Delay", "Time", "min")
        self.ld.add_param("StirRate", "Stir Rate", "rpm")
        self.ld.add_param("Pause", "Text", "")
        self.ld.get_params()

        self.ld.pt.add("source1", "Rack 2x4 20mL Vial", "Deck 10-11 Position 2")

        # adding cell plates
        np = math.ceil(self.num_cells / n)
        for p in range(np):
            plate = "plate%d" % (p + 1)
            print(">> Added cell plate %s" % plate)
            self.ld.pt.add(plate, self.cell_rack, self.cell_map[plate])

        if self.rack == 90:
            self.ld.pt.add("ICP1", "Rack 6x15 ICP robotic", "Deck 16-17 Waste 1")

        if self.rack == 60:
            self.ld.pt.add("ICP1", "Rack 5x12 ICP robotic", "Deck 16-17 Waste 1")

        self.ld.add_all_plates()

        # adding off deck and plate sources
        self.ld.add_chem(None, "solvent")

        self.ld.add_chem(
            None, "standard", elements=["Y"], concentrations=[self.std_conc]
        )

        # making the transfer map
        if self.verbose:
            print("\n ==== map from ==== ")

        if "load" in name:
            code = "Etip_WS"  # "Etip" for cell filling with the solvent
        else:
            code = "skip"  # all other LS methods

        for i in range(self.num_cells):
            plate, c = self.index2cell(cells, i + self.last_cell)

            self.ld.Stir(plate, 500)  # rpm

            if "load" not in name:
                self.ld.tm.add_from(self.ld.pt, plate, cells[c], 0)

            self.ld.dispense_chem(
                "standard",
                plate,  # substrate
                self.counters[c],  # feed (green) compartments
                self.volume_feed,  # added fake volume
                code,
            )

            self.ld.dispense_chem(
                "standard",
                plate,  # substrate
                self.cells[c],  # red (sample) compartments
                self.volume_sample,  # added fake volume
                code,
            )

        if "load" not in name:
            self.ld.tm.report_from()

            # input from a CSV file for a map of sources
            f = os.path.join(self.path, self.sources)
            self.ld.log_input(f)  # input from a CSV table

            # sourcing and dispensing chemicals
            source = self.ld.tm.full_plate(self.ld.pt, "source1", 1)

    def LS_to(self):
        if self.verbose:
            print("\n ==== map to ==== ")
            print("\n>> ICP rack offset = %d\n" % self.prep)

        self.ld.tm.add_to(
            self.ld.pt, "ICP1", self.ICP_area, 1, self.prep
        )  # tube rack, 1 by row, self.prep is offset
        self.ld.tm.report_to()

        self.ld.tm.map(0)  # no randomization of sampling

        self.ld.tm.to_df()

    def LS_copy(self, s, opt=0):
        files = glob(os.path.join(self.ld.dir, s))
        if files:
            for f in files:
                if opt:
                    q = f.split(".")
                    g = "%s_%d.%s" % (q[0], self.ld.ID, q[1])
                    g = os.path.basename(g)
                    g = os.path.join(self.exp, g)
                    shutil.copy2(f, g)
                else:
                    shutil.copy(f, self.exp)

    def LS_finish(self):
        # copy input and fill files from current directory

        if self.sources:
            f = os.path.join(self.ld.dir, self.sources)
            shutil.copy(os.path.join(self.path, self.sources), f)

        if self.fills:
            f = os.path.join(self.ld.dir, self.fills)
            shutil.copy(os.path.join(self.path, self.fills), f)

        # copy files to experiment grab bag folder

        self.LS_copy("*_input.csv")
        self.LS_copy("*_fill.csv")
        self.LS_copy("waste*.csv")
        self.LS_copy("Active*.json")
        self.LS_copy("transfer*.csv", 1)
        self.LS_copy("*.lsr")

        return self.ld.ID

    ################################################## experiment sequence ###########################################################################

    def LS_load(self):  # loading cells with a standard
        self.LS_open(self.cells, "standard load")

        if (
            self.ld.finish() == 0
        ):  # writing into the database and creating log files and xml files for AS
            sys.exit(0)

        self.LS_finish()

    # --------------------------------------------------------------------------------------------------------------

    def LS_blank(self):  # collection of blank samoles from the red side
        if not self.blank:
            return 0

        self.LS_open(self.cells, "sample blanks")
        self.LS_to()

        # transfer from source to cell compartments, red is "symbolic" transfer

        self.ld.tm.mapping = self.ld.tm.mapping[0 : self.num_cells]
        self.ld.tm.to_df()

        # transferring using the transfer map
        self.ld.transfer_replace_mapping(
            self.volume,  # volume
            self.chaser,  # chaser volume
            "1tip",
        )

        self.prep += self.num_cells

        # self.ld.Pause("plate1", 20) # message

        if (
            self.ld.finish() == 0
        ):  # writing into the database and creating log files and xml files for AS
            sys.exit(0)

        c = self.ld.make_container("ICP1", "blank")
        self.prep_container = self.ld.update_container(self.prep_container, c)
        self.ld.save_container(self.prep_container, image=False)

        return self.LS_finish()

    # =============================================================================================================

    def LS_fill_calibrate(self):
        self.LS_open(self.counters, "fill and calibrate cells")
        self.LS_to()

        # transfer from source to cell compartments, red is "symbolic" transfer

        i = 0
        for plate, well, _ in self.ld.tm.lib_from:
            self.ld.dispense_chem(
                self.ld.input_names[i],
                plate,
                well,
                self.fill,  # added volume
                "skip",  # "1tip", # actual addition
                True,  # add to sourcing log
            )
            i += 1

        if self.fills:
            f = os.path.join(self.path, self.fills)
            if os.path.exists(f):
                print("\n>> Found fill file %s" % f)
            else:
                print("\n>> Cannot find a fill file, abort")
                sys.exit(0)
        else:
            print("\n>> Requires a fill file, abort")
            sys.exit(0)

        df = pd.read_csv(f)
        df = df.fillna(0)
        u = df[["plate", "well"]].drop_duplicates().values.tolist()

        i = 0
        for plate, well in u:
            total = 0
            cell = "%s-%s-OUT" % (plate, well)
            if cell not in self.farm["label"].values:
                continue

            print(
                "\n -------------- Dispensing to %s, %s ---------------\n"
                % (plate, well)
            )
            for col in df.columns:
                if col in self.ld.input_names:
                    for _, row in df.iterrows():
                        volume = float(row[col])
                        if (
                            volume
                            and plate == row["plate"].strip()
                            and well == row["well"].strip()
                        ):
                            total += volume

                            self.ld.dispense_chem(
                                col,  # cell fill
                                plate,
                                well,
                                volume,  # added volume
                                "1tip",  # "1tip", # actual addition
                                True,  # add to sourcing log
                            )

                            print(" +++ added %.1f uL to cell %s" % (volume, cell))

            if total:
                print("\n>> Total volume %.1f uL for  %s, %s\n" % (total, plate, well))

            if self.calibrate:
                self.ld.Pause(plate, 60)  # 1 min pause for stirring

                add_to, well_to, _ = self.ld.tm.lib_to[i]

                self.ld.transfer_replace_well(  # calibration transfer
                    plate, add_to, well, well_to, self.calibrate, self.chaser, "1tip"
                )

                print(
                    "\n>> Transfered calibration volume %1.f uL and %.1f uL chaser to ICP1 well %s"
                    % (self.calibrate, self.chaser, well_to)
                )

            i += 1

        self.prep += i

        if (
            self.ld.finish() == 0
        ):  # writing into the database and creating log files and xml files for AS
            sys.exit(0)

        c = self.ld.make_container("ICP1", "calibration")
        self.prep_container = self.ld.update_container(c, self.prep_container)
        self.ld.save_container(self.prep_container, image=False)

        return self.LS_finish()

    # ===============================================================================================================

    def LS_fill(self):
        self.LS_open(self.counters, "fill cells")

        # input from a CSV file for a map of fills
        f = ""
        if self.fills:
            f = os.path.join(self.path, self.fills)

        if os.path.exists(f):
            print("\n>> Found fill file %s" % f)
            try:
                # self.ld.fill_by_source(f)
                self.ld.fill_by_well(f)

                if (
                    self.ld.finish() == 0
                ):  # writing into the database and creating log files and xml files for AS
                    sys.exit(0)

                for plate in self.ld.pt.plates:  # save compositions
                    if "plate" in plate:
                        print(">> Saves feed container for %s" % plate)
                        c = self.ld.make_container(plate, "feed")
                        self.ld.save_container(c, image=False)

                return self.LS_finish()

            except:
                return None

    # =============================================================================================================

    def LS_calibrate(self):
        if self.calibrate == 0:
            return 0

        self.LS_open(self.counters, "calibration sampling")
        self.LS_to()

        # transfer from source to cell compartments, red is "symbolic" transfer

        i = 0
        for plate, well, _ in self.ld.tm.lib_from:
            self.ld.dispense_chem(
                self.ld.input_names[i],
                plate,
                well,
                self.fill,  # added volume
                "skip",  # "1tip", # actual addition
                True,  # add to sourcing log
            )
            i += 1

        # transferring using the transfer map

        self.ld.tm.mapping = self.ld.tm.mapping[0 : self.num_cells]
        self.ld.tm.to_df()

        self.ld.transfer_replace_mapping(
            self.calibrate,  # volumes
            self.chaser,  # chaser volume
            "1tip",
        )

        self.prep += self.num_cells

        # self.ld.Pause("plate1", 20) # message
        # self.ld.Stir("plate1", 0) # rpm

        if (
            self.ld.finish() == 0
        ):  # writing into the database and creating log files and xml files for AS
            sys.exit(0)

        c = self.ld.make_container("ICP1", "calibration")
        self.prep_container = self.ld.update_container(c, self.prep_container)
        self.ld.save_container(self.prep_container, image=False)

        return self.LS_finish()

    # =============================================================================================================

    def LS_sample(self, lap):
        self.LS_open(self.cells, "rack%d" % (lap + 1))
        self.LS_to()

        # transferring using the transfer map
        self.ld.transfer_replace_mapping(
            self.volume,  # volume
            self.chaser,  # chaser volume
            "1tip",
            self.delay,  # delay in min
        )

        # self.ld.Pause("plate1", 20) # code for stirring off
        # self.ld.Pause("plate1", 1100) # remove and replace rack
        # self.ld.Stir("plate1", 0) # rpm

        if (
            self.ld.finish() == 0
        ):  # writing into the database and creating log files and xml files for AS
            sys.exit(0)

        c = self.ld.make_container("ICP1", "analyte")
        if self.prep:
            c = self.ld.update_container(c, self.prep_container)
        self.ld.save_container(c)
        self.last_container = c

        self.null_prep()
        self.find_last_cell()

        return self.LS_finish()

    ###########################################################################################################################

    def AS_execute(
        self, category, rename_container=False
    ):  # general execurtion and logging routine
        self.category = category
        flag = 0
        self.start = self.ld.tstamp()
        if self.AS:
            flag = self.ld.as_prep()
            if flag == 1:
                self.ld.as_run()
                self.ld.as_finish()

        self.housekeeping(category, rename_container)

        return flag  # 1 if succeeded to prep, 0 if failed to prep, -1 if the door interlock failed

    def housekeeping(self, category, rename_container=False):
        self.stop = self.ld.tstamp()
        dt = datetime.strptime(self.stop, "%Y%m%d_%H%M%S")
        dt -= datetime.strptime(self.start, "%Y%m%d_%H%M%S")
        dt = round(dt.total_seconds() / 60, 2)

        c = self.last_container
        if rename_container and c:
            c = self.ld.timestamp_container(c)  # use the same
            self.ld.save_container(c)

        r = {
            "ID": self.ld.ID,
            "category": category,
            "container": self.ld.last_code,
            "barcode": self.ld.last_barcode,
            "AS log": None,
            "start": self.start,
            "stop": self.stop,
            "tmin": dt,
        }

        try:
            r["AS log"] = self.ld.as10.log
        except:
            pass

        self.master_log.append(r)
        self.renew_AS_log()
        self.LS_copy("ASDigest*.csv")

    def renew_AS_log(self):
        f = os.path.join(self.exp, "AS_sequence_log.csv")
        df = pd.DataFrame(self.master_log)
        df.to_csv(f, index=False)
        print("\n>> Saved master log in %s\n" % f)
        print(df)

    def AS_start(self):  # start sequence
        self.start_sequence()
        self.aliquots = [self.volume / 2]
        return self.to_json()

    def AS_load(self, j=None):  # collect blanks
        if j:
            self.from_json(j)
        self.LS_load()
        self.AS_execute("load1")
        return self.to_json()

    def AS_blank(self, j=None):  # collect blanks
        if j:
            self.from_json(j)
        self.LS_blank()
        self.AS_execute("blank1")
        return self.to_json()

    def AS_fill_calibrate(self, j=None, index=1):  # collect feeds
        if j:
            self.from_json(j)
        self.LS_fill_calibrate()
        self.save_samples("fill%d" % index)
        self.AS_execute("fill%d" % index)
        return self.to_json()

    def AS_fill(self, j=None, index=1):  # collect feeds
        if j:
            self.from_json(j)
        self.LS_fill()
        self.save_samples("fill%d" % index)
        self.AS_execute("fill%d" % index)
        return self.to_json()

    def AS_calibrate(self, j=None):  # fill feed sides
        if j:
            self.from_json(j)
        if self.LS_calibrate():
            self.AS_execute("calibrate1")
        return self.to_json()

    def AS_sample(self, j, lap):  # collect samples to complete the first rack
        if j:
            self.from_json(j)
        self.LS_sample(lap)
        self.save_samples("samples_rack%d" % (lap + 1))
        self.AS_execute("rack%d" % (lap + 1))
        return self.to_json()

    def full_sequence(
        self, info=None
    ):  # example of the full sequence without external calls
        if not self.cont:
            info = self.AS_start()

        if self.load:  # optional loading of the cells with the solvent
            info = self.AS_load(info)  # load
            time.sleep(3600 * self.load_delay)  # delay after load

        info = self.AS_blank(info)
        info = self.AS_fill_calibrate(info)

        if info:
            laps = info.get("laps", 1)

            for lap in range(laps):
                print(
                    "\n\n################################# Sampling lap %d ######################################\n\n"
                    % (lap + 1)
                )
                info = self.AS_sample(info, lap)
            seq = CustomSequence(self.exp)
            seq.consolidate_BK_records()
            return 1
        else:
            print(">> No info json file to start laps, abort")
            return 0


###############################################################################################################################


def BK_consolidate():
    seq = CustomSequence()
    seq.consolidate_BK_records()


if __name__ == "__main__":
    x1 = AMEWS()
    x1.ICP_area = "*"
    x1.full_sequence()

    # BK_consolidate()
