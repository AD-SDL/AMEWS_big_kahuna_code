import sys
import os

user = os.getlogin()
sys.path.append(
    "C:/Users/%s/Dropbox/Instruments cloud/Robotics/Unchained BK/AS Scripts/API Scripts"
    % user
)

from CustomService import *


def basics_test():  # a test of basic plate and transfer map methods
    pt = CustomPlateManager()
    tm = CustomTransferMap()

    pt.add("plate1", "Rack 3x4 six Kaufmann H-cells", "Deck 12-13 Heat-Cool-Stir 1")
    pt.add("ICP1", "Rack 6x15 ICP robotic", "Deck 16-17 Waste 1")

    print("\n ==== map from ==== ")
    tm.add_from(pt, "plate1", "A1,B1", 0)  # by column
    tm.report_from()

    print("\n ==== map to ==== ")
    tm.add_to(pt, "ICP1", "full", 1)  # 90 tube rack,  1 by row
    tm.report_to()

    tm.map(1)  # no randomization of sampling
    tm.to_df()
    tm.to_csv_stamped()


#############################################################################################


def LS_only_test():
    ld = CustomLS10()
    ld.create_lib("demo 2cells 6x15 full")

    ld.add_param("Delay", "Time", "min")
    ld.add_param("StirRate", "Stir Rate", "rpm")
    ld.add_param("Pause", "Text", "")
    ld.get_params()

    # print(self.units_list())
    # ld.test_van_der_corput()

    # making a substrate library
    ld.pt.add("source1", "Rack 2x4 20mL Vial", "Deck 10-11 Position 2")
    ld.pt.add("plate1", "Rack 3x4 six Kaufmann H-cells", "Deck 12-13 Heat-Cool-Stir 1")
    ld.pt.add("ICP1", "Rack 6x15 ICP robotic", "Deck 16-17 Waste 1")

    # adding all plates
    ld.add_all_plates()

    # adding off deck and plate sources
    ld.add_chem(None, "solvent")

    # making the transfer map
    if ld.verbose:
        print("\n ==== map from ==== ")
    ld.tm.add_from(ld.pt, "plate1", "A1:B1", 0)  # by column  red compartments
    ld.tm.report_from()

    if ld.verbose:
        print("\n ==== map to ==== ")
    # ld.tm.add_to(ld.pt,"ICP1","full",1) # 90 tube rack,  1 by row
    ld.tm.add_to(ld.pt, "ICP1", "A*", 1)  # 90 tube rack,  1 by row
    ld.tm.report_to()

    ld.tm.map(0)  # no randomization of sampling
    ld.tm.to_df()

    sys.exit(0)

    ld.Stir("plate1", 500)  # rpm

    # dummy fill of the cells
    ld.dummy_fill("plate1", 5e4)  # 50 mL
    #    ld.dummy_fill("plate1", 5e4, "offdeck") # 50 mL

    ld.Pause("plate1", "prep finished")  # message

    # sourcing and dispensing chemicals

    source = ld.tm.full_plate(ld.pt, "source1", 1)

    # input from a CSV file
    f = os.path.join(os.getcwd(), "input_example.csv")
    ld.log_input(f)  # input from a CSV table

    # print(ld.tracker.samples)

    # transfer from source to cell compartments, red is "symbolic" transfer

    for i in range(ld.tm.n_from):
        j = i + 1
        plate, well, _ = ld.tm.lib_from[i]
        row, col = ld.tm.well2tuple(well)
        well_green = ld.tm.tuple2well(row, col + 2)  # into green compartments
        well_red = ld.tm.tuple2well(row, col)  # into red compartments

        ld.dispense_chem(
            "mixture%d" % j,
            plate,
            well_green,
            1000,  # added volume
            "skip",  # "1tip", # actual addition
            True,  # add to sourcing log
        )

        ld.dispense_chem(
            "mixture%d" % j,
            plate,
            well_red,
            0.1,  # added volume, just to indicate a mixture and pass constitution
            "skip",  # skip addition
            False,  # add to sourcing log
        )

    ld.Pause("plate1", "")  # message

    # transferring using the transfer map
    ld.transfer_replace_mapping(
        250,  # volume
        2000,  # chaser volume
        "1tip",
        0.0,  # 0.01 # min
    )

    ld.Pause("plate1", "stirring off")  # message
    ld.Stir("plate1", 0)  # rpm

    ld.finish()  # writing into the database and creating log files and xml files for AS

    ICP = ld.make_container("ICP1")
    ld.save_container(ICP)
    # supply = ld.supply_request("ICP1")
    # ld.save_container(supply)

    return ld


###########################################################################################################################+


def LS_only_calibration():
    cells = ["A3", "B3"]  # green side
    cell_list = ",".join(cells)

    ld = CustomLS10()
    ld.create_lib("calibrations 2cells")

    ld.add_param("Delay", "Time", "min")
    ld.add_param("StirRate", "Stir Rate", "rpm")
    ld.add_param("Pause", "Text", "")
    ld.get_params()

    # making a substrate library
    ld.pt.add("source1", "Rack 2x4 20mL Vial", "Deck 10-11 Position 2")
    ld.pt.add("plate1", "Rack 3x4 six Kaufmann H-cells", "Deck 12-13 Heat-Cool-Stir 1")
    ld.pt.add("ICP1", "Rack 6x15 ICP robotic", "Deck 16-17 Waste 1")

    # adding all plates
    ld.add_all_plates()

    # adding off deck and plate sources
    ld.add_chem(None, "solvent")

    # making the transfer map
    if ld.verbose:
        print("\n ==== map from ==== ")
    ld.tm.add_from(ld.pt, "plate1", cell_list, 0)  # by column green compartments
    ld.tm.report_from()

    if ld.verbose:
        print("\n ==== map to ==== ")
    ld.tm.add_to(ld.pt, "ICP1", "full", 1)  # 90 tube rack,  1 by row
    ld.tm.report_to()

    ld.tm.map(0)  # no randomization of sampling

    ld.Stir("plate1", 500)  # rpm

    # dummy fill of the cells
    ld.dummy_fill("plate1", 5e4)  # 50 mL

    ld.Pause("plate1", "prep finished")  # message

    # sourcing and dispensing chemicals

    source = ld.tm.full_plate(ld.pt, "source1", 1)

    # input from a CSV file
    f = os.path.join(os.getcwd(), "input_example.csv")
    ld.log_input(f)  # input from a CSV table

    # print(ld.tracker.samples)

    # transfer from source to cell compartments, red is "symbolic" transfer

    for i in range(ld.tm.n_from):
        plate, well, _ = ld.tm.lib_from[i]

        ld.dispense_chem(
            "mixture%d" % (i + 1),
            plate,
            well,
            1000,  # added volume
            "skip",  # "1tip", # actual addition
            True,  # add to sourcing log
        )

    ld.Pause("plate1", "")  # message

    # transferring using the transfer map
    volumes = []
    aliquots = [250, 125, 60, 30, 15]  # uL aliquots for calibrations

    j = 0
    for a in aliquots:
        for c in cells:
            if j < len(ld.tm.mapping):
                volumes.append(a)
                j += 1
    ld.tm.mapping = ld.tm.mapping[0:j]
    ld.tm.to_df()

    ld.transfer_replace_general(
        volumes,  # volumes
        2000,  # chaser volume
        "1tip",
        0.0,  # 0.01 # min
    )

    ld.Pause("plate1", "stirring off")  # message
    ld.Stir("plate1", 0)  # rpm

    ld.finish()  # writing into the database and creating log files and xml files for AS

    ICP = ld.make_container("ICP1")
    ld.save_container(ICP)
    # supply = ld.supply_request("ICP1")
    # ld.save_container(supply)

    return ld


###########################################################################################################################


def LS_AS_test():  # a test of LS functions - a cyclical walk through plate1 mapping it on ICP1 rack
    ld = LS_only_test()

    if ld.as_prep():
        sys.exit(0)  # run the standard experiment
    ld.as_run_paused()
    print("\n\n********************  CONTROL BACK *******************************\n\n")
    ld.as_run_resume(False)  # ignore other pauses
    ld.as_finish()
    # ld.make_container("ICP1")
    # ld.save_container()
    ld.smtp.alert("run %d finished with state %s" % (ld.ID, ld.as_state))


def LS_AS_calibration():  # a test of LS functions - a cyclical walk through plate1 mapping it on ICP1 rack
    ld = LS_only_calibration()

    if ld.as_prep():
        sys.exit(0)  # run the standard experiment
    ld.as_run_paused()
    print("\n\n********************  CONTROL BACK *******************************\n\n")
    ld.as_run_resume(False)  # ignore other pauses
    ld.as_finish()
    # ld.make_container("ICP1")
    # ld.save_container()
    ld.smtp.alert("run %d finished with state %s" % (ld.ID, ld.as_state))


def run_tests():
    ld = CustomLS10()

    if "no-go" in ld.as_execute_noDC(808, 0):
        sys.exit()
    # if "no-go" in ld.as_execute_wDC(739): sys.exit()


if __name__ == "__main__":
    # run_tests()

    LS_only_test()
    # LS_AS_test()

    # LS_only_calibration()
    # LS_AS_calibration()
