import sys
import os
import string
import math
import re
import random
import json
import clr
import shutil
import zipfile
from glob import glob
from datetime import datetime
import xml.etree.ElementTree as ET
from lxml import etree

from System.Reflection import Assembly, ReflectionTypeLoadException  # type: ignore
import System  # type: ignore
import System.Collections.Generic  # type: ignore

clr.AddReference("System.Drawing")
from System.Drawing import Point  # type: ignore


from a10_sila import CustomAS10


def CustomVerbosity():  # 1 for verbose script
    return 1


class CustomUtils:  # common LS handling utilities
    def __init__(self):
        self.wells = []
        self.values = []

    def well2tuple(self, well):
        letter = well[0].upper()
        col = int(well[1:])
        row = ord(letter) - ord("A") + 1
        return (row, col)

    def well2point(self, well):
        row, col = self.well2tuple(well)
        return Point(row, col)

    def tuple2well(self, row, col):
        return "%s%d" % (chr(64 + row), col)

    def invert_well(self, well):
        row, col = self.well2tuple(well)
        return self.tuple2well(col, row)

    def WellRangeFromString(self, range_string):  # defines and fills rectangular range
        cells = range_string.split(":")
        (start_row, start_col) = self.well2tuple(cells[0])

        if len(cells) == 1:
            return self.WellRange(start_row, start_col, 1, 1)

        (last_row, last_col) = self.well2tuple(cells[1])

        if last_row < start_row:
            t = start_row
            start_row = last_row
            last_row = t

        if last_col < start_col:
            t = start_col
            start_col = last_col
            last_col = t

        row_count = last_row - start_row + 1
        col_count = last_col - start_col + 1

        return self.WellRange(start_row, start_col, row_count, col_count)

    def WellRange(self, row, col, row_count, col_count):  # fills rectangular range
        n = row_count * col_count
        self.wells = []
        retval = System.Collections.Generic.List[
            System.Tuple[System.Int32, System.Int32]
        ](n)
        for r in range(row, row + row_count):
            for c in range(col, col + col_count):
                retval.Add(System.Tuple[System.Int32, System.Int32](r, c))
                self.wells.append((r, c))
        return retval

    def UniformValues(self, count, value):  # creates uniform dicrete map of doubles
        self.values = []
        retval = System.Collections.Generic.List[System.Double](count)
        for i in range(count):
            retval.Add(value)
            self.values.append(value)
        return retval

    def UniformObjects(
        self, count, value
    ):  # creates uniform dicrete map of object  - use them in parameter maps
        self.values = []
        retval = System.Collections.Generic.List[System.Object](count)
        for i in range(count):
            retval.Add(value)
            self.values.append(value)
        return retval

    def report_wells_values(self):  # reports well and discrete map ranges
        ws = ";".join([str(t) for t in self.wells])
        vs = ";".join([str(t) for t in self.values])
        return (ws, vs)


class PromptsFile:  # prompt xml file === initial state of well is either "None" or "Covered"-
    def __init__(self):
        self.prompts = ""
        self.plates = ""
        self.sources = ""
        self.positions = []

    def PromptsPart1(self):  # replacement in the exemplar prompt xml file
        with open(r"promptspart1.xml", "r") as file:
            data = file.read()
            data = data.replace("<!-- Initial library states -->", self.plates[:-1])
            data = data.replace("<!-- Initial source states -->", self.sources[:-1])
        return data

    def AddInitialLibraryState(
        self, library_id, state="None"
    ):  # adds ID's of plate libraries with their initial states
        self.plates += "[%d:%s];" % (library_id, state)

    def AddInitialSourceState(
        self,  # adds source positions
        position,
        state="None",  # None or Covered
        check=True,  # check if position is in positions already
    ):
        if not position:
            return

        if check:
            check = position in self.positions

        if not check:
            self.sources += "[%s:%s];" % (position, state)
            self.positions.append(position)

    def Write(self, path):  # writes into the prompt xml file
        self.prompts = self.PromptsPart1()
        with open(path, "w") as file:
            file.write(self.prompts)


class ChemFile:  # chemcial manager xml file, consists of four sections that are put together
    def __init__(self):
        self.chem_part_1 = ""
        self.chem_part_2 = ""
        self.chem_part_3 = ""
        self.chem_part_4 = ""
        self.verbose = CustomVerbosity()

    def ChemPart1(self, chemicals, libs, dispense):  # combines three sections
        with open("chempart1.xml", "r") as file:
            data = file.read()
            data = data.replace("<!-- Chemicals Part -->", chemicals)
            data = data.replace("<!-- Libraries Part -->", libs)
            data = data.replace("<!-- Dispense modes part -->", dispense)
        return data

    def ChemPart2(self):  # add as a chemical
        with open("chempart2.xml", "r") as file:
            data = re.sub(r"^\s*<\?xml.*?\?>\s*", "", file.read())
            root = etree.fromstring(data)
            data = etree.tostring(root, pretty_print=True).decode("utf-8")
            if self.verbose:
                # print(data)
                pass
            return data

    def ChemPart3(
        self, library_id, name, rows, cols, kind, position
    ):  # add ID'd substrate library
        with open("chempart3.xml", "r") as file:
            data = file.read()
            data = data.replace("<!-- LibraryID -->", str(library_id))
            data = data.replace("<!-- Name -->", name)
            data = data.replace("<!-- NumOfRows -->", str(rows))
            data = data.replace("<!-- NumOfCols -->", str(cols))
            data = data.replace("<!-- SubstrateType -->", kind)
            data = data.replace("<!-- SubstratePosition -->", position)
        return data

    def ChemPart4(self, name, mode):  # add dispense modes for chemicals
        with open("chempart4.xml", "r") as file:
            data = file.read()
            data = data.replace("%%Chemical Name%%", name)
            data = data.replace("%%Dispense Mode%%", mode)
        return data

    def AddChemical(self, name, mode):  # adds a chemical
        self.chem_part_2 += self.ChemPart2()
        self.chem_part_4 += self.ChemPart4(name, mode)

    def AddLibrary(
        self, library_id, name, rows, cols, kind, position
    ):  # adds a library
        self.chem_part_3 += self.ChemPart3(library_id, name, rows, cols, kind, position)

    def Write(self, path: str):  # writes into chemical manager xml file
        self.chem_part_1 = self.ChemPart1(
            self.chem_part_2, self.chem_part_3, self.chem_part_4
        )
        with open(path, "w") as file:
            file.write(self.chem_part_1)
        os.remove("chempart2.xml")


class CustomLS10:  # LS API wrapper calls
    def __init__(self):
        # general settings
        self.path = "."
        print("writes ChemicalManager and prompt XML files in %s" % self.path)
        self.chemfile = ChemFile()
        self.promptsfile = PromptsFile()
        self._prompts = os.path.join(
            self.path, "promptsWithDC.xml"
        )  # default for using Design Creator
        self._chem = ""  # default for using Design creator

        # LS API settings
        self.units = (
            "ul"  # units - must be in lower case unless capitalized in the unit table
        )
        self.map_count = 1  # map counter
        self.map_substrates = {}
        self.lib_count = 0  # library counter
        self.project = "auto"  # default project name
        self.name = ""  # default name
        self.ID = 0  # database ID for the design
        self.sources = {}  # source dictionary
        self.chem = {}  # chemicals dictionary
        self.sdf = pd.DataFrame()
        self.utils = CustomUtils()
        self.status = 0  # database addition status
        self.error_message = ""  # LS API error messages
        self.verbose = CustomVerbosity()  # verbosity of this class
        self.transfer = 1  # transfer msp or tansfers counter
        self.pt = CustomPlateManager()
        self.tm = CustomTransferMap()
        self.dir = self.path  # directory for LS design and all related files
        self.chaser = 0  # chaser volume in uL, 0 is chaser is not used
        self.door = 1  # State of the door interlock, 1 - locked

        self.TAGS = {
            "skip": "SkipMap",  # short codes for common LS design tags
            "1tip": "SyringePump,SingleTip",
            "Etip": "SyringePump,ExtSingleTip",
            "chaser": "Chaser",
            "4tip": "4Tip",
        }

        self.PTYPES = [
            "Temperature",
            "Time",
            "Rate",
            "Number",
            "Text",
            "Stir Rate",
            "Temperature Rate",
        ]  # allowed parameter types

        # numerical codes for pause actions
        # code book for text parameter maps => AS Pause messages

        # containers
        # AS relates
        self.a10 = None  # CustomAS10 needs to be clled to initialize
        self.as_state = None  # run state
        self.as_pause = None  # pause message

        # starting LS APIs
        ls_path = "C:/LSAPI/Libs/LSAPI.dll"
        if not os.path.exists(ls_path):
            print("Cannot find assembly LSAPI.dll")
            sys.exit(1)

        try:
            clr.AddReference(ls_path)
        except Exception as e:
            print("cannot add LSAPI.dll")
            print(e)
            sys.exit(1)

        try:
            assembly = Assembly.LoadFile(ls_path)
        except Exception as e:
            print("failed to load assembly LSAPI.dll")
            print(e)
            sys.exit(1)

        # self.inspect_assembly(assembly)   # use to inspect assembly
        import LS_API

        self.ls = LS_API.LibraryStudioWrapper
        self.units = self.units.lower()  # added to prevent using mL etc.

    def inspect_assembly(self, assembly):  # inspect modules in a .NET asssembly
        try:
            print("Types in the assembly:")
            for type in assembly.GetTypes():
                print(type.FullName)
        except ReflectionTypeLoadException as e:
            print("Error loading types from assembly:")
            for loader_exception in e.LoaderExceptions:
                print(loader_exception)
        except Exception as e:
            print("An unexpected error occurred while inspecting the assembly:")
            print(e)

    def create_lib(self, name):  # create a new LS library
        if name is None:
            name = "auto_design"
        if self.verbose:
            print("create design %s in project %s" % (name, self.project))
        status = self.ls.CreateNewDesign(
            name, self.project, "", "", "", "", "", "created on %s" % self.stamp
        )
        self.HandleStatus(status)
        self.name = name

    def van_der_corput(
        self, n, base=6
    ):  # van der Corput sequence in a given base  to pick colors
        vdc, denom = 0, 1
        while n:
            n, remainder = divmod(n, base)
            denom *= base
            vdc += remainder / denom
        return vdc

    def test_van_der_corput(self):  # test of color picking
        c = self.rgb_to_uint(0.5, 0.5, 0.5, 1)
        print("gray: => (128,128,128) %d" % c)
        for n in range(0, 13):
            x = self.van_der_corput(n)
            r, g, b, a = self.cmap(1 - x)
            c = self.rgb_to_uint(r, g, b, a)
            r = int(r * 255)
            g = int(g * 255)
            b = int(b * 255)
            print("%d: %.3f => (R=%d, G=%d, B=%d) %d" % (n, x, r, g, b, c))

    def rgb_to_uint(
        self, r, g, b, a=0
    ):  # RGB to an integer, ignore alpha, 24 bit version, inverted
        R = int(r * 255)
        G = int(g * 255)
        B = int(b * 255)
        return (B << 16) + (G << 8) + R

    def uint_to_RGB(self, uint):  # integer to RGB 0..255 scale
        R = uint & 255
        G = (uint >> 8) & 255
        B = (uint >> 16) & 255
        return (R, G, B)

    def closest_color(self, uint):
        R, G, B = self.uint_to_RGB(uint)
        m = float("inf")
        c = None
        for name, hex in mcolors.CSS4_COLORS.items():
            r, g, b = mcolors.hex2color(hex)
            r, g, b = [int(x * 255) for x in (r, g, b)]
            d = abs(r - R) + abs(g - G) + abs(b - B)
            if d < m:
                m = d
                c = name
        return c

    def index2color(self, index):  # index 0,1....  to (0,1) color scale
        q = self.van_der_corput(index)
        return self.rgb_to_uint(*self.cmap(1 - q))

    def to_tag(self, code):  # tag code word to a full tag
        if "_" in code:
            code = code.split("_")
            key = code[1].upper()
            base = code[0]
        else:
            base = code
            key = ""

        if len(base) == 0:
            base = "Processing"
        if base not in self.TAGS:
            return ""
        else:
            base = self.TAGS[base]
        if "S" in key:
            base += ",Backsolvent"
        if "L" in key:
            base += ",LookAhead"
        if "W" in key:
            base += ",SkipWash"
        if "I" in key:
            base += ",Image"
        return base

    def HandleStatus(self, status):  # error messages
        self.status = status
        self.error_message = None
        if status < 0:
            if status == -1:
                self.error_message = "Unidentified error"
            else:
                self.error_message = self.ls.GetErrorMessage(status)
            print(">> LS ERROR = %d : %s" % (self.status, self.error_message))
            sys.exit(0)

    def tstamp(self):  # datetime stamp
        now = datetime.now()
        return now.strftime("%Y%m%d_%H%M%S")

    def xml(self, type):  # name xml files
        return "%s_%s.xml" % (type, self.stamp)

    def add_plate(self, plate, state="None"):  # add substrate
        kind, position, rows, cols = self.pt.get(plate)
        color = self.index2color(self.lib_count)
        status = self.ls.AddLibrary(
            plate,
            nRows=rows,
            nCols=cols,
            color=color,
        )
        self.HandleStatus(status)
        q = self.closest_color(color)

        if self.verbose:
            print(
                "added %dx%d substrate %s, color = %d (%s)"
                % (rows, cols, plate, color, q)
            )

        self.lib_count += 1

    def plate2json(self, plate):  # adds json record for external plate tracking
        kind, position, rows, cols = self.pt.get(plate)
        self.pt.json[plate] = {}
        self.pt.json[plate]["rows"] = rows
        self.pt.json[plate]["columns"] = cols
        self.pt.json[plate]["position"] = position
        self.pt.json[plate]["kind"] = kind
        if "source" in plate:
            self.pt.json[plate]["type"] = "source"
        else:
            self.pt.json[plate]["type"] = "sample"
        self.pt.json[plate]["status"] = "UsedByBK"

    def add_all_plates(self):  # adds all non-source plates in the plate library
        if self.verbose:
            print("\n>> Adds all plates:")
        for plate in self.pt.plates:
            self.plate2json(plate)
            if "source" not in plate:
                if self.verbose:
                    print("--- adding plate %s" % plate)
                    self.add_plate(plate)

    def AddSource(
        self, source, chem, kind, position, color, row, col, volume=-1
    ):  # adds a new chemical/source to chemical manager file (part 2)
        root = ET.Element("Symyx.AutomationStudio.Core.ChemicalManager.Chemical")

        if chem == "solvent":
            t = "stBackingSolvent"
            row, col = 0, 0
            kind, position = None, None
            vr = "Syringe 1"
            vp = "1"
        else:
            t = "stNormal"
            vr = None
            vp = "0"

        if chem == source:
            row, col = 0, 0
            t = "stPlate"

        if volume < 0:
            u = "undefined"
        else:
            u = self.units

        ET.SubElement(root, "Name").text = chem
        ET.SubElement(root, "AmountLeft").text = str(volume)
        ET.SubElement(root, "Color").text = str(color)
        ET.SubElement(root, "Column").text = str(col)
        ET.SubElement(root, "Columns").text = "0"
        ET.SubElement(root, "Empty").text = "False"
        ET.SubElement(root, "Questionable").text = "False"
        ET.SubElement(root, "Row").text = str(row)
        ET.SubElement(root, "Rows").text = "0"
        if volume < 0:
            ET.SubElement(root, "Size").text = "0"
        else:
            ET.SubElement(root, "Size").text = str(volume * 1.1)
        ET.SubElement(root, "SubstratePosition").text = position
        ET.SubElement(root, "SubstrateType").text = kind
        ET.SubElement(root, "Type").text = t
        ET.SubElement(root, "ValveResource").text = vr
        ET.SubElement(root, "ValvePosition").text = vp
        ET.SubElement(root, "Units").text = u

        tree = ET.ElementTree(root)
        c = os.path.join(self.path, "chempart2.xml")
        with open(c, "wb") as f:
            tree.write(f, encoding="utf-8", xml_declaration=True)

    def add_chem(
        self,
        source,
        chem="solvent",
        row=0,
        col=0,
        volume=-1,  # if -1 indefinite volume
        mode="factory setting|ADT",  # dispense mode # adds a new chemical with a source,
    ):
        if source in self.pt.plates:
            kind, position, rows, cols = self.pt.get(source)
            if row > rows or col > cols:
                print(
                    "\nERROR: %dx%d source %s for chemical %s cannot be in (%d,%d) cell"
                    % (rows, cols, source, chem, row, col)
                )
                return 1
        else:
            kind, position = None, None
            print(
                "\nCAUTION: source %s for chemical %s is not in the plate list, assume off deck source"
                % (source, chem)
            )

        if chem == "solvent":
            color = self.rgb_to_uint(1, 1, 0)  # yellow
        else:
            color = self.index2color(self.lib_count)

        if chem:  # chemical
            if self.verbose:
                print(
                    "adds <%s> to the library, sourced from <%s> (%d,%d)\nat <%s>, color=%d (%s)\n"
                    % (chem, kind, row, col, position, color, self.closest_color(color))
                )
            self.ls.AddChemical(chem, color, self.units)

            if row == 0 or col == 0:
                well = "off deck"
            else:
                well = self.utils.tuple2well(row, col)

            self.promptsfile.AddInitialSourceState(position, "None")  # not covered

            if source:
                ID = "%s:%s" % (source, well)
            else:
                ID = chem

            # self.tracker.report(ID)

        else:  # library substrate
            chem = source
            well, row, col = "", 0, 0

        self.sources[chem] = (source, well)

        self.AddSource(source, chem, kind, position, color, row, col, volume)
        self.chemfile.AddChemical(chem, mode)

        self.lib_count += 1
        return 0

    def rename_chem(self, old, new):  # renames a chemical
        status = self.ls.RenameChemical(old, new)
        self.HandleStatus(status)

    def dispense_chem(
        self,  # dispenses chemical from a source & makes a source map
        chem,  # chemical
        add_to,  # plate to add
        range_str,  # wells
        volume,  # volume
        tag_code="1tip",
        opt=False,  # adds to mapped chemicals for chemfile
        layerIdx=-1,  # if positive edits the map
    ):
        wells = self.utils.WellRangeFromString(range_str)
        values = self.utils.UniformValues(wells.Count, volume)
        tag = self.to_tag(tag_code)
        i = layerIdx

        if layerIdx < 0:
            status = self.ls.AddSourceMap(
                chem,
                "Uniform",
                self.units,
                volume,
                wells,
                values,
                add_to,
                tag,
                self.map_count,
                1,
            )
            i = self.map_count
        else:
            status = self.ls.EditSourceMap(
                chem,
                "Uniform",
                self.units,
                volume,
                wells,
                values,
                add_to,
                tag,
                layerIdx,
                1,
            )

        self.HandleStatus(status)
        if self.verbose:
            print(
                "sourced %d %s of %s :: %s, wells = %s :: %s"
                % (int(volume), self.units, chem, add_to, range_str, tag)
            )

        source, source_well = self.sources[chem]
        self.map_substrates[self.map_count] = [source, add_to]

        if "Chaser" not in tag:
            if source:
                component_ID = "%s:%s" % (source, source_well)
            else:
                component_ID = chem

            for row, col in self.utils.wells:
                well = self.utils.tuple2well(row, col)
                ID = "%s:%s" % (add_to, well)
                self.tracker.add(ID, component_ID, volume)
                # self.tracker.report(ID)

        if opt and layerIdx < 0:
            self.chem[self.map_count] = (
                chem,
                source,
                source_well,
                add_to,
                range_str,
                volume,
            )

        if layerIdx < 0:
            self.map_count += 1

        return i

    def single_well_transfer(
        self,  # single cell transfer between the substrates
        source_plate,  # substrate
        target_plate,  # substrate
        source_well,  # well
        target_well,  # well
        volume,  # volume
        tag_code="1tip",
        layerIdx=-1,
    ):
        
        p_from = self.utils.well2point(source_well)
        p_to = self.utils.well2point(target_well)
        values = self.utils.UniformValues(1, volume)
        i = layerIdx

        if layerIdx < 0:  # new map
            status = self.ls.AddArrayMap(
                source_plate,
                target_plate,
                "Uniform",
                self.units,
                p_from,
                p_from,
                p_to,
                p_to,
                volume,
                values,
                self.to_tag(tag_code),
                self.map_count,
            )
            i = self.map_count
        else:  # edit the existing map
            status = self.ls.EditArrayMap(
                source_plate,
                target_plate,
                "Uniform",
                self.units,
                p_from,
                p_from,
                p_to,
                p_to,
                volume,
                values,
                self.to_tag(tag_code),
                layerIdx,
                1,
            )

        self.HandleStatus(status)

        ID = "%s:%s" % (target_plate, target_well)
        component_ID = "%s:%s" % (source_plate, source_well)

        self.tracker.add(ID, component_ID, volume)


        # self.tracker.report(ID)
        # self.tracker.report(component_ID)

        if layerIdx < 0:
            self.map_count += 1

        return i

    def Pause(self, plate, code):  # sets pause with a coded message, see the codebook
        if isinstance(code, str):
            text = code
            c = sum(ord(x) for x in text)
        else:
            c = code
            text = str(c)

        wells = self.utils.WellRangeFromString("A1")
        values = self.utils.UniformObjects(1, text)

        status = self.ls.AddParameterMap(
            "Pause",
            "Uniform",
            "",
            float(c),
            wells,
            values,
            plate,
            "Processing",
            self.map_count,
            1,
        )
        self.HandleStatus(status)
        self.map_count += 1

    def Delay(self, plate, t):  # sets delay time in min
        wells = self.utils.WellRangeFromString("A1")
        values = self.utils.UniformObjects(1, t)

        status = self.ls.AddParameterMap(
            "Delay",
            "Uniform",
            "min",
            float(t),
            wells,
            values,
            plate,
            "Processing",
            self.map_count,
            1,
        )

        self.HandleStatus(status)
        self.map_count += 1

    def Stir(self, plate, rate):  # sets delay time in min
        wells = self.utils.WellRangeFromString("A1")
        values = self.utils.UniformObjects(1, rate)
        status = self.ls.AddParameterMap(
            "StirRate",
            "Uniform",
            "rpm",
            float(rate),
            wells,
            values,
            plate,
            "Processing",
            self.map_count,
            1,
        )
        self.HandleStatus(status)
        self.map_count += 1
        if self.verbose:
            print("set stirring rate for %s at %g rpm" % (plate, rate))

    def dummy_fill(self, plate, volume=50000, what="solvent"):  # skipped dummy fill
        if self.verbose:
            print("\nFictitious fill of %s with %f uL of %s" % (plate, volume, what))
        if plate in self.pt.plates:
            full = self.tm.full_range(self.pt, plate)
            self.dispense_chem(
                what,
                plate,  # substrate
                full,  # the entire plate
                volume,  # added fake volume
                "skip",  # skip dispensing
            )

    def region_fill(
        self, plate, volume=50000, what="solvent", region="full"
    ):  # skipped dummy fill
        if self.verbose:
            print(
                "\nFictitious fill of %s (%s) with %f uL of %s"
                % (plate, region, volume, what)
            )
        if plate in self.pt.plates:
            if region == "full":
                region = self.tm.full_range(self.pt, plate)

            self.dispense_chem(
                what,
                plate,  # substrate
                region,  # specified region
                volume,  # added fake volume
                "skip",  # skip dispensing
            )

    def modify_tag_code(
        self, code, letter
    ):  # add a letter coded option to the tag code, can be more than one letter
        if "_" in code:
            base, key = code.split("_")
            if letter not in key:
                key += letter
            return "%s_%s" % (base, key)
        else:
            return "%s_%s" % (code, letter)

    def transfer_replace_well(
        self,  # add chaser, aliquot, replace it with solvent & delay
        add_from,
        add_to,
        well_from,
        well_to,
        volume,  # added volume
        chaser,  # added chaser (backsolvent) volume, can be zero
        tag_code="1tip",
        delay=0.0,  # delay in min after addition, can be zero
        layerIdx=-1,
    ):
        if layerIdx >= 0:
            return self.edit_replace_well(
                add_from, add_to, well_from, well_to, volume, chaser, tag_code, layerIdx
            )

        tag = self.to_tag(tag_code)
        self.chaser = 0

        if self.verbose:
            print(
                "\nmap %d :: adds chaser, aliqots, replaces solvent and waits %g min"
                % (self.map_count, delay)
            )

        if chaser > 0:
            self.dispense_chem(
                "solvent", add_to, well_to, chaser, "chaser_S"
            )  # changed 1-30-2025 was _from
            self.chaser = chaser

        i = self.single_well_transfer(
            add_from, add_to, well_from, well_to, volume, tag_code
        )

        self.dispense_chem(
            "solvent",
            add_from,
            well_from,
            volume,
            self.modify_tag_code(tag_code, "S"),  # backsolvent
            # adds _S if it is not there, "SW" for backsolvent + skipwash
        )

        if self.verbose:
            print(
                "transfers %d %s from %s, well = %s -> %s, well = %s :: %s"
                % (int(volume), self.units, add_from, well_from, add_to, well_to, tag)
            )
        if delay > 0:  # delay time in min
            self.Delay(add_to, delay)
        self.log_composition(add_from, add_to, well_from, well_to)
        return i

    def log_composition(self, add_from, add_to, well_from, well_to):
        ID = "%s:%s" % (add_from, well_from)
        c = self.tracker.return_composition(ID)
        self.tm.composition_from.append(c)

        ID = "%s:%s" % (add_to, well_to)
        c = self.tracker.return_composition(ID)
        self.tm.composition_to.append(c)
        c = self.tracker.return_constitution(ID)
        self.tm.constitution_to.append(c)

    def edit_replace_well(
        self,  # add chaser, aliquot, replace it with solvent & delay
        add_from,
        add_to,
        well_from,
        well_to,
        volume,
        chaser,
        tag_code="1tip",
        layerIdx=-1,
    ):
        tag = self.to_tag(tag_code)
        self.chaser = 0

        if self.verbose:
            print(
                "\nedited map %d :: adds chaser, aliqots, replaces solvent" % (layerIdx)
            )
        if chaser > 0:
            self.dispense_chem(
                "solvent", add_to, well_to, chaser, "chaser_S", False, layerIdx - 1
            )
            self.chaser = chaser
        self.single_well_transfer(
            add_from, add_to, well_from, well_to, volume, tag_code, layerIdx
        )
        self.dispense_chem(
            "solvent",
            add_from,
            well_from,
            volume,
            self.modify_tag_code(tag_code, "S"),
            False,
            layerIdx + 1,
        )
        if self.verbose > 0:
            print(
                "transfers %d %s from %s, well = %s -> %s, well = %s :: %s"
                % (int(volume), self.units, add_from, well_from, add_to, well_to, tag)
            )
        self.log_composition(add_from, add_to, well_from, well_to)
        return layerIdx

    def transfer_replace_mapping(
        self, volume, chaser, tag_code="1tip", d=0.0
    ):  # do the transfer sequence for the entire transfer map
        volumes = [volume] * len(self.tm.mapping)
        self.transfer_replace_general(volumes, chaser, tag_code, d)

    def transfer_replace_general(
        self, volumes, chaser, tag_code="1tip", d=0.0
    ):  # do the transfer sequence for the entire transfer map
        i = 0
        self.tm.renew_composition()

        if "volume" not in self.tm.df.columns:
            self.tm.df["volume"] = pd.NA
        if "chaser" not in self.tm.df.columns:
            self.tm.df["chaser"] = pd.NA
        if "map" not in self.tm.df.columns:
            self.tm.df["map"] = pd.NA

        for _, add_from, well_from, _, add_to, well_to, _ in self.tm.mapping:
            self.transfer_replace_well(
                add_from, add_to, well_from, well_to, volumes[i], chaser, tag_code, d
            )
            self.tm.df.loc[i, "volume"] = volumes[i]
            self.tm.df.loc[i, "chaser"] = chaser
            self.tm.df.loc[i, "map"] = self.map_count
            i += 1

        # add compositions of to and from wells AFTER each transfer

        self.log_map()

        if self.verbose:
            print("\nTRANSFER MAP %d\n%s\n" % (self.transfer, self.tm.df))
        self.tm.to_csv(
            "transfer%d" % self.transfer, self.stamp
        )  # save the numbered transfer map
        self.transfer += 1

    def log_map(self):
        c = self.tm.composition_from
        if c:
            d = self.tracker.compositions2df(c, "from")
            self.tm.df = pd.concat([self.tm.df, d], axis=1)
            del d

        c = self.tm.composition_to
        if c:
            d = self.tracker.compositions2df(c, "to")
            self.tm.df = pd.concat([self.tm.df, d], axis=1)
            del d

        c = self.tm.constitution_to
        if c:
            d = self.tracker.constitutions2df(c)
            self.tm.df = pd.concat([self.tm.df, d], axis=1)
            del d

    def from_db(self, lib_ID):  # get the parameter list
        self.design = self.ls.GetDesignFromDatabase(lib_ID, False)
        self.ID = lib_ID
        if self.design:
            if self.verbose:
                print("loaded LS library design %d without attachments" % lib_ID)
                self.project = self.ls.GetProjectName()
                self.name = self.ls.GetLibraryDesign()
                print("project %s, design name %s" % (self.project, self.name))
                self.info_libs()
        else:
            print("ERROR: cannot open LS library design %d" % lib_ID)
            return 1

        return 0

    def add_param(self, pname, ptype, punit):
        from LS_API import Param

        p = Param()
        p.Description = ""
        p.Expression = ""
        p.Name = pname
        p.Type = ptype
        p.DefaultUnit = punit
        if ptype in self.PTYPES:
            self.ls.AddParameter(p)
        else:
            print("ERROR: incorrect parameter type")
            return 1

        return 0

    def get_params(self):  # get the parameter list
        ps = list(self.ls.GetParameters())
        if ps:
            print("\n%d parameters found" % len(ps))
            for p in ps:
                print(
                    "%s :: type = %s, default unit = %s"
                    % (p.Name, p.Type, p.DefaultUnit)
                )
        else:
            print("no parameters found")

    def get_units_types(self):  # get the list of unit types
        self.units_types = list(self.ls.GetAllUnits())

    def get_units(self):  # get the list of units
        self.get_units_types()
        self.units_list = []
        for t in self.units_types:
            u = list(self.ls.GetUnits(t))
            self.units_list.append(u)
            print("type = %s -> unit = %s" % (t, u))


    def to_db(
        self, isnew
    ):  # True - new ID, False - overwrite existing ID in the database
        return self.ls.SaveDesignToDatabase(isnew, True)  #

    def rename(self, name):
        self.ls.SetDesignName(name)
        self.name = name

    def finish_lib(
        self, isnew
    ):  # adds to database and uses library IDs to complete records
        self.ID = self.to_db(isnew)
        if self.ID < 0:
            self.HandleStatus(self.ID)
            print("\nCAUTION: fakes ID's to complete xml records for AS\n")
            self.fake_lib(10)
        else:
            if self.verbose:
                print("\nsaved library %s with ID = %d\n" % (self.name, self.ID))
            self.save_library_to_database()

    def save_library_to_database(self):
        self.to_db(False)

        libs = self.ls.GetLibraries()
        if libs:
            for lib in libs:
                ID = lib.ID
                kind, position, _, _ = self.pt.get(lib.Name)
                self.chemfile.AddLibrary(
                    ID, lib.Name, lib.Rows, lib.Columns, kind, position
                )
                self.promptsfile.AddInitialLibraryState(ID, "None")
               

    def fake_lib(self, fake_ID):  # uses fake IDs  to complete records
        self.ID = fake_ID
        for plate in self.pt.plates:
            if "source" in plate:
                continue
            kind, position, rows, cols = self.pt.get(plate)
            self.chemfile.AddLibrary(fake_ID, plate, rows, cols, kind, position)
            self.promptsfile.AddInitialLibraryState(fake_ID, "None")
            fake_ID += 1

    def write_json(self, s, name):  # export json formatted data to work directory
        u = os.path.join(self.dir, "%s_%s.json" % (name, self.ID))
        with open(u, "w") as f:
            json.dump(s, f, indent=4)

    def finish(self):  # finish design
        self.finish_lib(True)  # adds to database with a new ID and completes records

        if self.error_message:
            return 0

        self.ID_folder()
        self.pt.to_df()

        self.pt.to_csv(
            os.path.join(self.dir, "substrates_%d" % self.ID), self.stamp
        )  # save the substrate map as csv dataframe file

        self.write_json(self.pt.json, "substrates")
        self.write_json(self.map_substrates, "map_substrates")
        self.write_json(
            self.tracker.samples, "samples"
        )  # pedigree of all sources and samples
        self.waste = self.tracker.waste_bill(self.tracker.samples)
        self.waste.to_csv(
            os.path.join(self.dir, "waste_ondeck_%d.csv" % self.ID), index=True
        )

        self.sources_df()
        self.sources_csv()  # save the sourcing map
        self.finish_files()
        self.to_file(
            os.path.join(self.dir, "%s_%d_%s.lsr" % (self.name, self.ID, self.stamp))
        )
        self.move_stamped_files()
        return self.ID

    def ID_folder(self):
        if self.ID:
            self.dir = os.path.join(self.path, str(self.ID))
            if not os.path.exists(self.dir):
                os.makedirs(self.dir)

    def move_stamped_files(self):
        try:
            for f in os.listdir(self.path):
                if self.stamp in f:
                    shutil.move(f, self.dir)
        except:
            pass

    def finish_iterative(self):  # finish design, iterative calls
        self.ID = self.to_db(False)  # overwrite
        if self.ID < 0:
            self.HandleStatus(self.ID)
            print("\nERROR: cannot overwrite the current design into the database\n")
            return 1
        else:
            self.ID_folder()
            if self.verbose:
                print("\nsaved edited design %s with ID = %d\n" % (self.name, self.ID))
            self.to_file(
                os.path.join(
                    self.dir, "%s_%d_step%d.lsr" % (self.name, self.ID, self.transfer)
                )
            )

        return 0

    def finish_files(self):  # write AS files
        self._prompts = os.path.join(self.dir, self.xml("prompts_%d" % self.ID))
        self._chem = os.path.join(self.dir, self.xml("chem_%d" % self.ID))
        self.chemfile.Write(self._chem)  # save the AS chemical manager xml file
        self.promptsfile.Write(self._prompts)  # save the AS prompt xml file

    def to_file(self, path):  # save the current design to a file
        if self.ls.SaveDesignToFile(path):
            print("saved the current LS design to %s" % path)

    def from_file(
        self, path
    ):  # import a design from a file (cannot be loaded into a database)
        base_name = os.path.basename(path)
        name = os.path.splitext(base_name)[0]
        self.design = self.ls.SaveDesignToFile(path)
        status = self.ls.SetDesignName(name)
        self.HandleStatus(status)

    def as_execute(
        self, opt=0
    ):  # 1,3 no reinitialization of AS clients, 0,2 - no finishing
        if opt == 0 or opt == 2:  # initialization of AS clients
            if not self.as_prep():
                return "no-go"  # prepare AS SiLA client
        self.as_state = self.as_run()  # execution with AS SiLA client
        if self.as_state == "notips":
            self.smtp.alert("Out of tips !!!", importance="High")
        else:
            if opt == 0 or opt == 1:  # no stopping of AS clients
                self.as_finish()  # stop the client
        return self.as_state

    def as_prep(
        self,
    ):  # prepare for run, return 1 if ok, -1 if door is not interlocked, 0 if error
        # check door state
        self.door = check_BK_door()
        if self.door == 0:
            print("\n!!!!! BK door is not closed !!!!!\n")
            return -1
        if self.door == 1:
            print(">> BK door interlocked")
        # AS10 preparations
        self.as10 = CustomAS10(self.verbose)
        if self.as10.FindOrStartAS():
            print(">> AS preparations complete")
            return 1  # succeeded
        else:
            return 0  # failed

    def as_execute_wDC(self, lib_ID, opt=0):  # opt as in as_execute
        self.ID = lib_ID
        self.ID_folder()
        self._prompts = os.path.join(self.path, "promptsWithDC.xml")
        self._chem = ""
        return self.as_execute(opt)

    def as_execute_noDC(self, lib_ID, opt=0):  # opt as in as_execute
        self.ID = lib_ID
        self.ID_folder()

        chem = glob(os.path.join(self.dir, "chem_%d_*.xml" % self.ID))
        if chem:
            self._chem = chem[0]
        else:
            print("no chem file for design ID = %d" % self.ID)
            return "no-go"

        prompts = glob(os.path.join(self.dir, "prompts_%d_*.xml" % self.ID))
        if prompts:
            self._prompts = prompts[0]
        else:
            print("no chem file for design ID = %d" % self.ID)
            return "no-go"

        return self.as_execute(opt)

    def as_run(self):  # run the standard experiment, ignore pauses
        self.as_state = self.as10.run(self.ID, self._prompts, self._chem)
        print(">> Returned with AS state = %s" % self.as_state)
        if self.as_state == "notips":
            self.smtp.alert("ALERT: out of tips !!!", importance="High")

        if self.as10.pause_count:
            if self.verbose:
                print("Ignored the total of %d pauses" % self.as10.pause_count)

        return self.as_state

    def as_run_paused(self):  # begin the standard experiment, stop on pauses
        self.as_state = self.as10.run(
            self.ID,
            self._prompts,
            self._chem,
            None,  # tip file
            True,  # until paused
            False,
        )  # begin

        return self.as_handle_pause()

    def as_handle_pause(self):
        self.as_pause = None

        if self.as_state == "completed" or self.as_state == "aborted":
            if self.smtp.when:
                self.smtp.alert("run %s %s" % (self.ID, self.as_state))
            return 1

        if self.as_state == "notips":
            self.smtp.alert("ALERT: out of tips !!!", importance="High")
            return None

        try:
            m = int(self.as_state)
            if m in self.pause_codebook:
                self.as_pause = self.pause_codebook[m]
                if self.verbose:
                    print(">> Prompt map=%d, text=%s" % (m, self.as_pause))
            else:
                if self.verbose:
                    print(">> Prompt map not in the code book")
                    return None
        except:
            print(">> unclassifyable AS state  = %s" % self.as_state)

    def as_run_resume(self, opt):  # resume the experiment, True - until paused
        self.as_state = self.as10.run(
            self.ID,  # does not matter
            self._prompts,  # does not matter
            self._chem,  # does not matter
            None,  # tip file
            opt,  # until paused
            True,
        )  # resume

        if opt:
            self.as_handle_pause()
        return self.as_state

    def as_finish(self):  # stop SiLA client
        self.as10.CloseAS()

    def as_restart(self):  # attempt to restart SiLA client
        self.as_finish()
        self.as_prep()

    def crunch(self):
        try:
            self.combine_files("status_*.log", "status_combined.log")
            self.combine_files("ASMain_*.log", "ASMain_combined.log")
            self.zip_files("*step*.lsr", "LS designs.zip")
        except:
            pass

    def combine_files(
        self, kind, combined
    ):  # combine in the order of creation dates, use wildtypes for kind
        logs = glob(os.path.join(self.dir, kind))
        if logs:
            logs.sort(key=lambda x: os.path.getctime(x))
            n, i, m = 0, 0, len(logs)

            f = os.path.join(self.dir, combined)
            with open(f, "w") as fout:
                for log in logs:
                    with open(log, "r") as fin:
                        fout.write(
                            "\n\n****** STEP %d out of %d ******\n\n" % (i + 1, m)
                        )
                        fout.write(fin.read())
                        n += os.path.getsize(log)
                        i += 1

            if os.path.getsize(f) > n:  # verify writing
                for log in logs:
                    os.remove(log)

            if self.verbose:
                print("%d files %s combined to %s" % (i, kind, combined))

    def zip_files(self, kind, combined):  # zip files, use wildtypes for kind
        logs = glob(os.path.join(self.dir, kind))
        if logs:
            f = os.path.join(self.dir, combined)
            i = 0
            with zipfile.ZipFile(f, "w") as zipf:
                for log in logs:
                    zipf.write(log, os.path.basename(log))
                    os.remove(log)
                    i += 1

            if self.verbose:
                print("%d files %s zipped to %s" % (i, kind, combined))

    ################################## working with containers #####################################################

    def local_container(self, c):
        if c:
            s = c["route"]["type"].capitalize()
            code = c["code"]
            u = os.path.join(self.dir, "%s_%s.json" % (s, code))  # local copy
            with open(u, "w") as f:
                json.dump(c, f, indent=4)

    def save_container(self, c, image=True):
        if c:
            self.local_container(c)
            if image:
                self.disp.save(c)

    def update_container(self, ca, cb):
        if ca:
            if cb:
                for ID in cb["creator"]["content"]:
                    ca["creator"]["content"][ID] = cb["creator"]["content"][ID]
        else:
            ca = cb.copy()
        return ca

    def timestamp_container(self, c):
        dt = datetime.now()
        c["creator"]["datetime"] = str(dt)
        self.last_code = self.disp.datetime2abcd(dt)

        CV = CustomBarcode()  # redo barcode
        self.last_barcode = CV.snap_barcode()

        c["code"] = self.last_code
        c["barcode"] = self.last_barcode

        return c

    def make_container(
        self, plate, new_type=""
    ):  # creates container object for export, json format
        # 'sample" can be redefined to another type
        kind, position, rows, cols = self.pt.get(plate)

        dt = datetime.now()
        self.last_code = self.disp.datetime2abcd(dt)

        CV = CustomBarcode()
        self.last_barcode = CV.snap_barcode()

        c = {"code": self.last_code, "barcode": self.last_barcode}

        items = rows * cols

        rack = {}
        rack["name"] = kind
        rack["type"] = "ICP%d" % items  # dispatcher's code for the rack
        rack["instrument"] = "BK"  # current location
        rack["position"] = position  # current position
        rack["label"] = ""  # visible code
        rack["code"] = None  # bar code, QR code
        rack["holder"] = None  # for movable holders
        rack["items"] = items
        rack["layout"] = "rectangular"
        rack["rows"] = rows
        rack["columns"] = cols

        c["rack"] = rack

        route = {}
        route["ready"] = "no"
        route["type"] = "active"  # cak also be supply or trash, see below
        route["priority"] = (
            "clear"  # will clear the rack to trash if no storage or instrument are available
        )
        route["route"] = [
            "UR5",
            "Storage",
            "UR5",
            "ICP",
            "UR5",
            "Trash",
        ]  # routing of the rack
        route["step"] = 0  # set to start of the route
        route["datetimes"] = []  # datetimes will be added

        c["route"] = route

        creator = {}  # the same, at creation
        creator["location"] = "BK"
        creator["position"] = position
        creator["ID"] = plate
        creator["protocol"] = self.ID
        creator["datetime"] = str(dt)
        s = self.tracker.extract_substrate(plate)
        if new_type:
            s = self.tracker.redefine_type(s, new_type)
        creator["content"] = s

        c["creator"] = creator

        return c

    def supply_request(
        self, plate, rack_type
    ):  # creates request for container object, json format
        kind, position, rows, cols = self.pt.get(plate)
        dt = datetime.now()
        self.last_code = self.disp.datetime2abcd(dt)
        self.last_barcode = ""
        c = {"code": self.last_code, "barcode": ""}

        rack = {}
        rack["name"] = kind
        rack["type"] = rack_type  # for example, ICP90
        rack["instrument"] = "BK"  # pickup location
        rack["position"] = position  # position
        rack["label"] = ""
        rack["code"] = None
        rack["holder"] = None  # for movable holders

        c["rack"] = rack

        route = {}
        route["ready"] = "yes"
        route["type"] = "supply"
        route["priority"] = ""
        route["route"] = ["UR5", "Storage", "UR5", "BK"]
        route["step"] = 0
        route["datetimes"] = []

        c["route"] = route
        c["creator"] = {}

        return c

    def trash_request(
        self, plate, rack_type
    ):  # creates container object for trash, json format
        kind, position, rows, cols = self.pt.get(plate)
        dt = datetime.now()
        self.last_code = self.disp.datetime2abcd(dt)

        CV = CustomBarcode()
        self.last_barcode = CV.snap_barcode()

        c = {"code": self.last_code, "barcode": self.last_barcode}

        rack = {}
        rack["name"] = kind
        rack["type"] = rack_type  # for example, ICP90
        rack["instrument"] = "BK"  # current location
        rack["position"] = position  # current position
        rack["label"] = ""
        rack["code"] = None
        rack["holder"] = None  # for movable holders

        c["rack"] = rack

        route = {}
        route["ready"] = "yes"
        route["type"] = "trash"
        route["priority"] = ""
        route["route"] = ["UR5", "Trash"]
        route["step"] = 0
        route["datetimes"] = []

        c["route"] = route

        creator = {}  # the same, at creation
        creator["location"] = "BK"
        creator["position"] = position
        creator["ID"] = plate
        creator["protocol"] = self.ID
        creator["datetime"] = str(datetime.now())
        creator["content"] = self.tracker.extract_substrate(plate)

        c["creator"] = creator

        return c

    def log_input(self, f):  # tracking for the input file
        if not os.path.isfile(f):
            print(">> Input file %s does not exist, abort" % f)
            sys.exit(0)
        try:
            df = pd.read_csv(f)
            df = df.fillna(0)
            self.input_names = []
            s = [col for col in df.columns if "*" in col]
            elements = [col.replace("*", "") for col in s]
            df.columns = df.columns.str.replace("*", "", regex=False)
            print("\n>> Found input file %s" % f)
            print(">> concentration units %s" % self.tracker.unit)
            print(">> constituion elements: %s\n" % elements)
            for _, row in df.iterrows():
                plate = row["plate"].strip()
                if plate in self.pt.plates and "source" in plate:
                    kind, _, rows, cols = self.pt.get(plate)
                    name = row["name"].strip()
                    if (
                        name in self.input_names
                    ):  # source chemicals need to have unique names
                        print(">> Source chemical name %d is not unique, abort")
                        sys.exit(0)
                    self.input_names.append(name)
                    position = row["source well"].strip()
                    r, c = self.tm.well2tuple(position)
                    if r <= rows and c <= cols:
                        volume = row["volume"]
                        self.add_chem(plate, name, r, c, volume)  # adds source chemical
                        ID = "%s:%s" % (plate, position)
                        for col in elements:
                            if row[col]:
                                self.tracker.samples[ID]["constitution"][col] = row[col]
                    else:
                        print(
                            ">> Impossible well %s for %s, %s, abort"
                            % (position, plate, kind)
                        )
                        print(
                            " --- well (%d,%d) in a %dx%d rack !" % (r, c, rows, cols)
                        )
                        sys.exit(0)
                else:
                    print(">> Does not recognize source plate %s, abort" % plate)
                    sys.exit(0)
            del df
        except Exception as e:
            print(">> Error %s for input file %s, abort" % (e, f))
            sys.exit(0)

    def fill_by_source(self, f):  # dispensing by source categories, df is the fill file
        df = pd.read_csv(f)
        df = df.fillna(0)
        for col in df.columns:
            if col in self.input_names:
                print(
                    "\n -------------- Dispensing chemical %s ---------------\n" % col
                )
                total = 0
                for _, row in df.iterrows():
                    volume = float(row[col])
                    plate = row["plate"].strip()
                    well = row["well"].strip()
                    if volume and self.tm.in_lib(self.tm.lib_from, plate, well):
                        total += volume
                        self.dispense_chem(
                            col,
                            plate,
                            well,
                            volume,  # added volume
                            "1tip",  # "1tip", # actual addition
                            True,  # add to sourcing log
                        )
                if total:
                    print("\n total volume %.1f uL for %s\n" % (total, col))

    def fill_by_well(self, f):  # dispensing by well
        df = pd.read_csv(f)
        df = df.fillna(0)
        u = df[["plate", "well"]].drop_duplicates().values.tolist()
        for plate, well in u:
            total = 0
            if self.tm.in_lib(self.tm.lib_from, plate, well):
                print(
                    "\n -------------- Dispensing to %s, %s ---------------\n"
                    % (plate, well)
                )
                for col in df.columns:
                    if col in self.input_names:
                        for _, row in df.iterrows():
                            volume = float(row[col])
                            if (
                                volume
                                and plate == row["plate"].strip()
                                and well == row["well"].strip()
                            ):
                                total += volume
                                self.dispense_chem(
                                    col,
                                    plate,
                                    well,
                                    volume,  # added volume
                                    "1tip",  # "1tip", # actual addition
                                    True,  # add to sFurcing log
                                )
            if total:
                print("\n total volume %.1f uL for  %s, %s\n" % (total, plate, well))


#######################################################################################################################################################


class CustomPlate:  # plate class for plate manager
    def __init__(self, name, kind, position):
        self.name = name.strip()
        self.kind = kind.strip()
        self.position = position.strip()
        self.rows, self.cols = self.parse_kind()

    def __repr__(self):
        return "Plate = (name=%s, kind=%s, position=%s)" % (
            self.name,
            self.kind,
            self.position,
        )

    def parse_kind(self):  # guesses substrate dimensions from the name
        pattern = r"(\d+)x(\d+)"
        match = re.search(pattern, self.kind)
        if match:
            rows = int(match.group(1))
            cols = int(match.group(2))
            return rows, cols
        else:
            return 1, 1


class CustomPlateManager:  # plate manager
    def __init__(self):
        self.plates = {}
        self.n_plates = 0
        self.verbose = CustomVerbosity()
        self.json = {}

        self.positions = [  # change when updated, any order
            "Deck 8-9 Position 1",
            "Deck 8-9 Position 3",
            "Deck 10-11 Position 2",
            "Deck 10-11 Position 3",
            "Deck 12-13 Heat-Cool-Stir 1",
            "Deck 12-13 Heat-Stir 2",
            "Deck 12-13 Heat-Stir 3",
            "Deck 14-15 Heat-Stir 1",
            "Deck 14-15 Heat-Stir 2",
            "Deck 14-15 Heat-Stir 3",
            "Deck 16-17 Waste 1",
            "Deck 16-17 Waste 2",
            "Deck 16-17 Waste 3",
            "Deck 19-20 Position 1",
            "Deck 19-20 Position 2",
            "Deck 19-20 Position 3",
        ]
        # rows x columns
        self.kinds = [  # change when updated, any order
            "Plate 1x1 Reservoir",
            "Rack 1x2 125mL Vial",
            "Rack 2x4 20mL Vial",
            "Rack 4x6 8mL Vial",
            "Rack 4x6 4mL Vial",
            "Rack 4x6 4mL Shell",
            "Rack 6x8 2mL Vial",
            "Rack Al 8x12 1mL Vial",
            "Rack 8x12 NanoIndentor",
            "Rack Al 8x12 1.2mL Vial",
            "Rack 8x12 1mL Vial",
            "Rack 8x12 1.2mL Vial",
            "Filter 8x12 Aspirate",
            "Filter 8x12 Dispense",
            "8x6 deep 48 well NEST",
            "4x6 deep 24 well NEST",
            "Rack VT54 6x9 2mL Septum Low",
            "Rack 12x5 ICP manual",
            "Rack 15x6 ICP manual",
            "Rack 5x12 ICP robotic",
            "Rack 6x15 ICP robotic",
            "Rack 8x3 NMR bin",
            "Rack 2x1 100mL Kaufmann H-cell",
            "Rack 3x4 six Kaufmann H-cells",
            "Rack 4x2 RedoxMe H-cell",
            "Rack 4x2 Mina H-cell",
        ]

    def add(
        self, name, kind, position
    ):  # add a new plate, by convention all source plates have "source" in their names
        name = name.strip()
        kind = kind.strip()
        position = position.strip()

        if not self.kind_check(kind):
            print("substrate %s in not in substrate list, ignore" % kind)
            return 0

        if not self.pos_check(position):
            print("position %s in not in positions list, ignore" % position)
            return 0

        if name not in self.plates:
            p = CustomPlate(name, kind, position)
            self.plates[name] = (kind, position, p.rows, p.cols)
            self.n_plates += 1
            return 1
        else:
            print("duplicative platename %s, ignore" % name)
            return 0

    def report(self):
        if self.verbose:
            print("%d unique plates" % self.n_plates)

    def get(self, name):  # find plate record
        name = name.strip()
        if name in self.plates:
            return self.plates[name]
        else:
            print("plate %s is not in the plate list" % name)

    def to_df(self):  # make a table of substrate records
        if self.plates:
            self.df = pd.DataFrame.from_dict(
                self.plates,
                orient="index",
                columns=["kind", "position", "rows", "columns"],
            )
            self.df.reset_index(inplace=True)
            self.df.rename(columns={"index": "substrate"}, inplace=True)
            if self.verbose:
                print("\nSUBSTRATE MAP\n%s\n" % self.df)
        else:
            print("no plate dictionary to convert to a dataframe")

    def to_csv_stamped(self):  # save time stamped substrate records to a CSV file
        now = datetime.now()
        stamp = now.strftime("%Y%m%d_%H%M%S")
        self.to_csv("plates", stamp)

    def to_csv(self, name, stamp):  # save substrate records to a CSV plate
        if len(self.df):
            self.df.to_csv("%s_%s.csv" % (name, stamp), index=False)
            if self.verbose:
                print("plate info is written to a time stamped .csv file")
        else:
            print("no dataframe to save in a .csv file")

    def pos_general(self, position):  # checks that positions have the right structure
        position = position.strip()
        digits = re.findall(r"\d+", position)
        pos = int(digits[-1]) if digits else None

        if pos is None or pos > 3:
            print("invalid position number")
            return False

        if "Deck" not in position:
            print("Deck is not given")
            return False

        return True

    def pos_check(
        self, position
    ):  # check the position against the list of allowed positions
        return position.strip() in self.positions

    def kind_check(
        self, kind
    ):  # check the substrate against the list of allowed substrates
        return kind.strip() in self.kinds


class CustomTransferMap:  # a class to create transfer maps
    def __init__(self):
        self.lib_from = []
        self.lib_to = []
        self.mapping = []
        self.df = pd.DataFrame()
        self.n_to = 0
        self.n_from = 0
        self.verbose = CustomVerbosity()
        self.renew_composition()

    def renew_composition(self):
        self.composition_from = []
        self.composition_to = []
        self.constitution_to = []

    def sort_labels(self, labels, direction):  # sorting of wells
        def sort_key(label):
            row, col = label[0], int(label[1:])
            if direction:
                return (row, col)
            else:
                return (col, row)

        return sorted(labels, key=sort_key)

    def generate_labels(self, range_str, direction):  # 0 by column, 1 by row
        range_str = range_str.strip()
        if ":" in range_str:
            start, end = range_str.split(":")
            start_row, start_col = start[0], int(start[1:])
            end_row, end_col = end[0], int(end[1:])
            rows = string.ascii_uppercase[
                string.ascii_uppercase.index(start_row) : string.ascii_uppercase.index(
                    end_row
                )
                + 1
            ]
            columns = range(start_col, end_col + 1)
            if direction:
                labels = ["%s%d" % (row, col) for row in rows for col in columns]
            else:
                labels = ["%s%d" % (row, col) for col in columns for row in rows]
            return labels
        else:
            return [range_str]

    def well2tuple(self, well):  # same as in utils
        letter = well[0].upper()
        col = int(well[1:])
        row = ord(letter) - ord("A") + 1
        return (row, col)

    def tuple2well(self, row, col):  # same as in utils
        return "%s%d" % (chr(64 + row), col)

    def well2native(self, pt, plate, well):
        if plate in pt.plates:
            kind, _, rows, cols = pt.get(plate)
            row, col = self.well2tuple(well)
            if "NMR" in kind:
                if rows < cols:
                    return str((row - 1) * cols + col)
                else:
                    return str(rows * (cols - col) + row)
            if "ICP" in kind:
                if rows > cols:
                    return self.tuple2well(col, row)
                else:
                    return self.tuple2well(1 + rows - row, col)
        return well

    def check_well(
        self, well, n_rows, n_cols
    ):  # check that the cell can be on the substrate
        row, col = self.well2tuple(well)
        if row > n_rows or col > n_cols:
            return False
        else:
            return True

    def generate_combined_labels(
        self, pt, plate, ranges_str, direction, offset=0
    ):  # combines and orders well ranges
        # added option offset
        if "full" in ranges_str or ranges_str == "*":  # full rack
            ranges_str = self.full_range(pt, plate)

        range_list = ranges_str.split(",")

        combined = []
        for s in range_list:
            if "*" in s:  # full row or column, like A* or *6 with wildcarts
                labels = self.full_rc(s, pt, plate).split(",")
            else:
                labels = self.generate_labels(s, direction)  # A1:B5 form

            for label in labels:
                if label not in combined:
                    combined.append(label)

        combined = self.sort_labels(combined, direction)
        combined = combined[offset:]

        record = []
        if plate not in pt.plates:
            print(
                "\n>>> CAUTION: plate %s is not in the list of plates, ignore\n" % plate
            )
        else:
            _, _, rows, cols = pt.get(plate)
            if self.verbose:
                print(
                    "%s wells (%s, %dx%d plate) = %s"
                    % (len(combined), plate, rows, cols, combined)
                )
            flag = 0
            for well in combined:
                if self.check_well(well, rows, cols):
                    record.append((plate, well, self.well2native(pt, plate, well)))
                else:
                    flag = 1
            if flag:
                print(
                    "\n>>> CAUTION: plate %s dimensions exceeded, only valid wells added\n"
                    % plate
                )

        return record

    def check_unique(self, list):  # removes duplicates
        unique = []
        for item in list:
            if item not in unique:
                unique.append(item)
        return unique

    def shuffle(
        self, list
    ):  # random shuffle with a checks that the first well is not the same as the previous last well
        last = list[-1]
        u = list[:]
        while True:
            random.shuffle(u)
            if u[0] != last:
                break
        return u

    def full_range(self, pt, plate):  #  full plate
        _, _, rows, cols = pt.get(plate)
        return "A1:%s" % self.tuple2well(rows, cols)

    def full_rc(self, s, pt, plate):  #  full row or column like A* or *5
        _, _, rows, cols = pt.get(plate)
        q = ""
        if s[0] == "*":
            col = int(s[1:])
            for i in range(rows):
                q += "%s," % self.tuple2well(i + 1, col)
        else:
            for i in range(cols):
                q += "%s%d," % (s[0], i + 1)
        return q[:-1]

    def full_plate(
        self, pt, plate, direction
    ):  # 0 by column, 1 by row # a list of wells in the full plate
        range_str = self.full_range(pt, plate)
        return self.generate_labels(range_str, direction)

    def add_from(
        self, pt, plate, reagent_str, direction, offset=0
    ):  # 0 by column, 1 by row # a list of sampled wells
        self.lib_from += self.generate_combined_labels(
            pt, plate, reagent_str, direction, offset
        )
        self.n_from = len(self.lib_from)

    def add_to(
        self, pt, plate, reagent_str, direction, offset=0
    ):  # 0 by column, 1 by row # a list of destination wells
        # added optional offset in the well list
        self.lib_to += self.generate_combined_labels(
            pt, plate, reagent_str, direction, offset
        )
        self.n_to = len(self.lib_to)

    def in_lib(self, lib, plate, well):  # check presence in the add list
        for p, w, _ in lib:
            if p == plate and w == well:
                return 1
        return 0

    def report_from(self):  # reporting
        if self.verbose:
            print("the total of %d wells to map from" % self.n_from)

    def report_to(self):  # reporting
        if self.verbose:
            print("the total of %d wells to map to" % self.n_to)

    def map(
        self, randomize
    ):  # optional randomization on each repeat - making a transfer map
        if self.n_from == 0 or self.n_to == 0:
            return 0
        q, m = 1, 0
        self.mapping = []
        while q:
            u = self.lib_from[:]
            if randomize:
                u = self.shuffle(u)
            for i in range(self.n_from):
                self.mapping.append((m + 1,) + u[i] + self.lib_to[m])
                m += 1
                if m == self.n_to:
                    q = 0
                    break
        if self.verbose:
            print("\n%d full repeats" % math.floor(self.n_to / self.n_from))
        return 1

    def to_df(self):  # converting the transfer map to a dataframe table
        if self.mapping:
            self.df = pd.DataFrame(
                self.mapping,
                columns=[
                    "index",
                    "plate from",
                    "well from",
                    "native_from",
                    "plate to",
                    "well to",
                    "native to",
                ],
            )
            if self.verbose:
                print("\nTRANSFER MAP\n%s\n" % self.df)
        else:
            print("no mapping to convert to a dataframe")

    def to_csv_stamped(self):  # saving the transfer map to a datetime stamped CSV file
        now = datetime.now()
        stamp = now.strftime("%Y%m%d_%H%M%S")
        self.to_csv("mapping", stamp)

    def to_csv(self, name, stamp):  # saving the Nan trimmed transfer map to a CSV file
        if len(self.df):
            self.df.to_csv("%s_%s.csv" % (name, stamp), index=False)
            if self.verbose:
                print("mapping is written to a time stamped .csv file\n")
        else:
            print("no dataframe to save in a .csv file")
