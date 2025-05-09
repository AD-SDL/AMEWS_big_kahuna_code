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


class LS10:  # LS API wrapper calls
    def __init__(self):
        # general settings
        self.path = os.getcwd()
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
        self.sources = []  # source dictionary
        self.chem = {}  # chemicals dictionary
        self.utils = CustomUtils()
        self.status = 0  # database addition status
        self.error_message = ""  # LS API error messages
        self.verbose = CustomVerbosity()  # verbosity of this class
        self.transfer = 1  # transfer msp or tansfers counter
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
            name, self.project, "", "", "", "", "", "created on %s" % str(datetime.now())
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

    def to_tag(self, tags):  # tag code word to a full tag
        tag_string  = ""
        for tag in tags:
            tag_string += (tag.value)
            if tag != tags[-1]:
                tag_string += ","
        return tag_string

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


    def add_library(self, name: str, rows: int, columns: int, color: int):  # add substrate
            status = self.ls.AddLibrary(
            name,
            nRows=rows,
            nCols=columns,
            color=color,
            )
            self.HandleStatus(status)
            self.lib_count += 1

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

    def add_plate_source(
            self,
            source_plate,
            chemical_name,
            mode="factory setting|ADT"
    ):
        self.AddSource(source_plate.name, chemical_name, source_plate.type, source_plate.deck_position, 0, 0, 0, -1)
        self.chemfile.AddChemical(chemical_name, mode)

    def add_chemical(
        self,
        source_plate,
        chemical_name,
        row=0,
        col=0,
        color=0x000000,
        volume=-1,  # if -1 indefinite volume
        mode="factory setting|ADT",  # dispense mode # adds a new chemical with a source,
    ):
            self.ls.AddChemical(chemical_name, color, self.units)
            if source_plate is not None:
                self.promptsfile.AddInitialSourceState(source_plate.deck_position, "None")  # not covered
                # self.tracker.report(ID)

    
                self.AddSource(source_plate.name, chemical_name, source_plate.type, source_plate.deck_position, color, row, col, volume)
            else: 
                self.promptsfile.AddInitialSourceState(None, "None")  # not covered
                # self.tracker.report(ID)

    
                self.AddSource(None, chemical_name, None, None, color, row, col, volume)
            self.chemfile.AddChemical(chemical_name, mode)

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
        tags=[],
        opt=False,  # adds to mapped chemicals for chemfile
        layerIdx=-1,  # if positive edits the map
    ):
        wells = self.utils.WellRangeFromString(range_str)
        values = self.utils.UniformValues(wells.Count, volume)
        tag = self.to_tag(tags)
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
        tags=[],
        layerIdx=-1,
        plates = None
    ):  
        if source_plate not in self.sources:
            self.sources.append(source_plate)
            full_plate = plates[source_plate]
            print(full_plate)
            self.add_plate_source(full_plate, source_plate)
        
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
                self.to_tag(tags),
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
                self.to_tag(tags),
                layerIdx,
                1,
            )

        self.HandleStatus(status)


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
        self, isnew, plates
    ):  # adds to database and uses library IDs to complete records
        self.ID = self.to_db(isnew)
        print(self.ID)
        if self.ID < 0:
            self.HandleStatus(self.ID)
            print("\nCAUTION: fakes ID's to complete xml records for AS\n")
            self.fake_lib(10, plates)
        else:
            if self.verbose:
                print("\nsaved library %s with ID = %d\n" % (self.name, self.ID))
            self.save_library_to_database(plates)

    def save_library_to_database(self, plates):
        self.to_db(False)

        libs = self.ls.GetLibraries()
        if libs:
            for lib in libs:
                ID = lib.ID
                plate = plates[lib.Name]
                self.chemfile.AddLibrary(
                    ID, lib.Name, lib.Rows, lib.Columns, plate.type, plate.deck_position
                )
                self.promptsfile.AddInitialLibraryState(ID, "None")
               

    def fake_lib(self, fake_ID, plates):  # uses fake IDs  to complete records
        self.ID = fake_ID
        for name, plate in plates.items():
            self.chemfile.AddLibrary(fake_ID, name, plate.rows, plate.columns, plate.type, plate.deck_position)
            self.promptsfile.AddInitialLibraryState(fake_ID, "None")
            fake_ID += 1

    def write_json(self, s, name):  # export json formatted data to work directory
        u = os.path.join(self.dir, "%s_%s.json" % (name, self.ID))
        with open(u, "w") as f:
            json.dump(s, f, indent=4)

    def finish(self, plates):  # finish design
        self.finish_lib(True, plates)  # adds to database with a new ID and completes records
        self.finish_files()
        if self.error_message:
            return 0

        
        return self.ID

    def ID_folder(self):
        if self.ID:
            self.dir = os.path.join(self.path, str(self.ID))
            if not os.path.exists(self.dir):
                os.makedirs(self.dir)

    def xml(self, type):  # name xml files
        return "%s_%s.xml" % (type, self.tstamp())

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
        return self.as_state

    def as_prep(
        self,
    ):  # prepare for run, return 1 if ok, -1 if door is not interlocked, 0 if error
        # check door state
        #self.door = check_BK_door()
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

   
    def as_run(self):  # run the standard experiment, ignore pauses
        self.as_state = self.as10.run(self.ID, self._prompts, self._chem)
        return self.as_state


    def as_finish(self):  # stop SiLA client
        self.as10.CloseAS()

    def as_restart(self):  # attempt to restart SiLA client
        self.as_finish()
        self.as_prep()

   