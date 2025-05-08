import glob
import json
import os
import shutil
from datetime import datetime

import pandas as pd

from CustomSequence import CustomSequence
from CustomService import CustomLS10

#######################################################################################################################

# red side is the sample collection side of the permeation cells, it is *1 and *2
# green side is the feed side of the permeation cells, it is *3 and *4


class AMEWS:
    def __init__(self):
        self.verbose = 0
        self.cont = False  # continue a previous run

        self.path = os.getcwd()
        self.user = os.getlogin()
    # ================================ json serialization =================================

    

   
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

        self.ld.add_param("Delay", "Time", "min")
        self.ld.add_param("StirRate", "Stir Rate", "rpm")
        self.ld.add_param("Pause", "Text", "")
        self.ld.get_params()

        # making a substrate library
        self.ld.pt.add("source1", "Rack 2x4 20mL Vial", "Deck 10-11 Position 2")
        self.ld.pt.add(
            "plate1", "Rack 3x4 six Kaufmann H-cells", "Deck 12-13 Heat-Cool-Stir 1"
        )

        if "fill" not in name:
            if self.rack == 90:
                self.ld.pt.add("ICP1", "Rack 6x15 ICP robotic", "Deck 16-17 Waste 1")
            if self.rack == 60:
                self.ld.pt.add("ICP1", "Rack 5x12 ICP robotic", "Deck 16-17 Waste 1")

        # adding all plates
        self.ld.add_all_plates()

        # adding off deck and plate sources
        self.ld.add_chem(None, "solvent")

        self.ld.add_chem(
            None, "standard", elements=["Y"], concentrations=[self.std_conc]
        )

        # making the transfer map
        if self.verbose:
            print("\n ==== map from ==== ")
        self.ld.tm.add_from(
            self.ld.pt, "plate1", cells, 0
        )  # by column  red compartments
        self.ld.tm.report_from()

        # input from a CSV file
        f = os.path.join(self.path, self.sources)
        self.ld.log_input(f)  # input from a CSV table

        self.ld.Stir("plate1", 500)  # rpm

        for c in self.cells:
            self.ld.dispense_chem(
                "standard",
                "plate1",  # substrate
                c,  # red (sample)
                self.volume_sample,  # added fake volume
                "skip",  # skip dispensing
            )

            self.ld.dispense_chem(
                "standard",
                "plate1",  # substrate
                self.cell2counter(c),  # green (feed)
                self.volume_feed,  # added fake volume
                "skip",  # skip dispensing
            )

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
        # print(self.ld.tracker.samples)

    def LS_copy(self, s, opt=0):
        files = glob(os.path.join(self.ld.dir, s))
        if files:
            for f in files:
                if opt:
                    q = f.split(".")
                    g = "%s_%d.%s" % (q[0], self.ld.ID, q[1])
                    g = os.path.basename(g)
                    g = os.path.join(self.exp, g)
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
        self.LS_copy("fill*.json")
        self.LS_copy("transfer*.csv", 1)
        self.LS_copy("*.lsr")

        return self.ld.ID

    ################################################## experiment sequence ###########################################################################

    def LS_blank(self):  # collection of blank samoles from the red side
        if not self.blank:
            return 0

        self.LS_open(self.cells_list, "sample blanks")
        self.LS_to()

        # print(self.ld.tracker.samples)
        # transfer from source to cell compartments, red is "symbolic" transfer

        self.prep += self.num_cells
        self.ld.tm.mapping = self.ld.tm.mapping[0 : self.num_cells]
        self.ld.tm.to_df()

        # transferring using the transfer map
        self.ld.transfer_replace_mapping(
            self.volume,  # volume
            self.chaser,  # chaser volume
            "1tip",
        )

        # self.ld.Pause("plate1", 20) # message

        self.ld.finish()  # writing into the database and creating log files and xml files for AS

        c = self.ld.make_container("ICP1", "blank")

        self.prep_container = self.ld.update_container(self.prep_container, c)
        self.ld.save_container(self.prep_container, image=False)

        return self.LS_finish()

    # =============================================================================================================

    def LS_fill(self):
        self.LS_open(self.counters_list, "fill cells")

        # input from a CSV file for a map of fills
        f = ""
        if self.fills:
            f = os.path.join(self.path, self.fills)

        if os.path.exists(f):
            print("\n>> Found fill file %s" % f)
            try:
                # self.ld.fill_by_source(f)
                self.ld.fill_by_well(f)

                self.ld.finish()  # writing into the database and creating log files and xml files for AS

                c = self.ld.make_container("plate1", "feed")
                self.ld.save_container(c, image=False)

                return self.LS_finish()

            except:
                return None

        else:
            i = 0
            for plate, well, _ in self.ld.tm.lib_from:
                self.ld.dispense_chem(
                    self.ld.input_names[i],
                    plate,
                    well,
                    self.fill,  # added volume
                    "1tip",  # "1tip", # actual addition
                    True,  # add to sourcing log
                )
                i += 1

            self.ld.finish()  # writing into the database and creating log files and xml files for AS

            c = self.ld.make_container("plate1", "uniform feed")
            self.ld.save_container(c, image=False)

            return self.LS_finish()

    # =============================================================================================================

    def LS_calibrate(self):
        if len(self.aliquots) == 0:
            return 0

        self.LS_open(self.counters_list, "calibration sampling")
        self.LS_to()

        # print(self.ld.tracker.samples)
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

        # transferring using the transfer map

        volumes = []
        i = 0
        for a in self.aliquots:
            for c in self.counters:
                if i < len(self.ld.tm.mapping):
                    volumes.append(a)
                    i += 1

        self.prep += i
        self.ld.tm.mapping = self.ld.tm.mapping[0:i]
        self.ld.tm.to_df()

        self.ld.transfer_replace_general(
            volumes,  # volumes
            self.chaser,  # chaser volume
            "1tip",
        )

        # self.ld.Pause("plate1", 20) # message
        # self.ld.Stir("plate1", 0) # rpm

        self.ld.finish()  # writing into the database and creating log files and xml files for AS

        c = self.ld.make_container("ICP1", "calibration")
        self.prep_container = self.ld.update_container(c, self.prep_container)
        self.ld.save_container(self.prep_container, image=False)

        return self.LS_finish()

    # =============================================================================================================

    def LS_sample(self, lap):
        self.LS_open(self.cells_list, "rack%d" % (lap + 1))
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

        self.ld.finish()  # writing into the database and creating log files and xml files for AS

        c = self.ld.make_container("ICP1", "analyte")
        if self.prep:
            c = self.ld.update_container(c, self.prep_container)
        self.ld.save_container(c)
        self.last_container = c

        self.null_prep()

        return self.LS_finish()

    ###########################################################################################################################

    def AS_execute(
        self, category, rename_container=False
    ):  # general execurtion and logging routine
        self.category = category
        flag = 0
        self.start = self.ld.tstamp()
        if self.AS:
            flag = (
                self.ld.as_prep()
            )  # 1 is succeeded, -1 door not interlocked, 0 failed
            if flag == 1:
                self.ld.as_run()
                self.ld.as_finish()

        self.housekeeping(category, rename_container)

        return flag

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

        return c

    def renew_AS_log(self):
        f = os.path.join(self.exp, "AS_sequence_log.csv")
        df = pd.DataFrame(self.master_log)
        df.to_csv(f, index=False)
        print("\n>> Saved master log in %s\n" % f)
        print(df)

    def AS_start(self):  # start sequence
        self.start_sequence()
        return self.to_json()

    def AS_blank(self, j=None):  # collect blanks
        if j:
            self.from_json(j)
        self.LS_blank()
        self.AS_execute("blank1")
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

    def AS_sample(self, j=None, lap=0):  # collect samples to complete the first rack
        if j:
            self.from_json(j)
        self.LS_sample(lap)
        self.save_samples("sample_rack%d" % (lap + 1))
        self.AS_execute("rack%d" % (lap + 1))
        return self.to_json()

    def full_sequence(
        self, info=None
    ):  # example of the full sequence without external calls
        if not self.cont:
            info = self.AS_start()
            info = self.AS_blank(info)
            info = self.AS_fill(info)
            info = self.AS_calibrate(info)

        if info:
            laps = info.get("laps", 3)

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
    info = x1.full_sequence()

    # x1.full_sequence()

    # x1.exp = os.path.join(x1.path, "Experiments", "run6_20250308_190911")

    # BK_consolidate()

    # x1.AS_fill()
    # x1.LS_sample()

#  short sampling protocol for testing
# x1.ICP_area = "A1:A6"
# x1.AS_sample_first()
