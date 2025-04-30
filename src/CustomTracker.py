import os
import json
import pandas as pd
import numpy as np
from datetime import datetime
from collections import Counter


class CustomTracker:
    def __init__(self):
        self.verbose = 1  # verbosity
        self.samples = {}  # json object with pedigree
        self.sample = None  # one sample
        self.user = os.getlogin()
        self.dir = (
            "C:/Users/%s/Dropbox/Instruments cloud/Robotics/composition tracker"
            % self.user
        )
        self.json = None  # pathname for json file
        self.sources = []  # list of primary sources
        self.unit = "mM"  # unit of concentrations

    def load_json(self, name):
        self.json = os.path.join(self.dir, "%s.json" % name)
        with open(self.json, "r") as f:
            self.samples = json.load(f)

    def write_json(self, name="default"):
        self.json = os.path.join(self.dir, "%s.json" % name)
        with open(self.json, "w") as f:
            json.dump(self.samples, f, indent=4)

    def stamp(self):
        now = datetime.now()
        stamp = now.strftime("%Y%m%d_%H%M%S")
        return stamp

    def update_samples(self):
        self.update_volumes()
        self.update_compositions()

    def update_compositions(self):
        for ID in self.samples:
            self.update_composition(ID)

    def update_volumes(self):
        for ID in self.samples:
            self.update_volume(ID)

    def update_composition(self, ID):
        s = self.samples[ID]

        c = self.get_composition(ID)
        s["composition"] = c

        q = self.get_constitution(ID)
        s["constitution"] = q

        if self.verbose:
            print("\nSample: %s" % ID)
            print("  Timestamp: %s" % s["timestamp"])
            print("  Type: %s" % s["type"])
            if s["name"]:
                print("  Name: %s" % s["name"])
            print("  Composition:")
            for compound, proportion in c.items():
                print("      %s\t\t%.1f%%" % (compound, 100 * proportion))
            if q:
                print("  Constitution:")
                for element, concentration in q.items():
                    print("      %s\t\t%.2f %s" % (element, concentration, self.unit))
            if s["volume"]:
                print("  Volume, uL: %s" % s["volume"])
            if len(s["parents"]):
                print("  Parents: %s" % s["parents"])
                print("  Parent volumes, uL: %s" % s["parent_volumes"])
            print("-" * 40)

        self.samples[ID] = s

    def update_volume(self, ID):  # volume
        self.samples[ID]["volume"] = 0

        if "parent_volumes" in self.samples[ID]:
            v = self.samples[ID]["parent_volumes"]
            if len(v):
                self.samples[ID]["volume"] = sum(v)

    def get_composition(self, ID):  # composition in primary compounds
        self.sample = self.samples[ID]

        if len(self.sample["parents"]) == 0:  #  source
            return self.sample["composition"]

        tv = sum(self.sample["parent_volumes"])  # total volume
        composition = {}

        for p, v in zip(self.sample["parents"], self.sample["parent_volumes"]):
            c = self.get_composition(p)

            for r, f in c.items():  # source reagents and volume fractions
                if r not in composition:
                    composition[r] = 0

                composition[r] += f * v / tv  # volume fractions

        for r, c in composition.items():
            composition[r] = round(c, 4)

        return composition

    def return_composition(self, ID):
        c = self.samples[ID]["composition"].copy()
        c["volume"] = self.samples[ID]["volume"]
        return c

    def return_constitution(self, ID):
        c = self.samples[ID]["constitution"].copy()
        return c

    def add_composition(
        self, ID, component_ID, volume
    ):  # composition in primary compounds after addition
        v1 = self.samples[ID]["volume"]
        tv = v1 + volume
        f1 = v1 / tv
        f2 = 1 - f1  # volumes and volume fractions

        composition = self.samples[ID]["composition"]

        for r, f in composition.items():
            composition[r] = f * f1

        for r, f in self.samples[component_ID]["composition"].items():
            if r not in composition:
                composition[r] = 0
            composition[r] += f * f2

        return composition

    def source_constitution(
        self, elements, concentrations
    ):  # "element" constitution in unirs
        constitution = {}
        if len(elements):
            for e, m in zip(elements, concentrations):
                if e not in constitution:
                    constitution[e] = 0

                constitution[e] += m

        return constitution

    def get_constitution(self, ID):  # "elemental" constitution
        self.sample = self.samples[ID]

        if len(self.sample["parents"]) == 0:  #  source
            return self.sample["constitution"]

        tv = sum(self.sample["parent_volumes"])  # total volume
        constitution = {}

        for p, v in zip(self.sample["parents"], self.sample["parent_volumes"]):
            c = self.get_constitution(p)
            if c:
                for e, m in c.items():  # "elements" and unit concentrations
                    if e not in constitution:
                        constitution[e] = 0

                    constitution[e] += m * v / tv  # unit concentration

        return constitution

    def add_constitution(self, ID, component_ID, volume):  # "elemental" constitution
        v1 = self.samples[ID]["volume"]
        tv = v1 + volume
        f1 = v1 / tv
        f2 = 1 - f1  # volumes and volume fractions

        constitution = self.samples[ID]["constitution"]

        for e, m in constitution.items():
            constitution[e] = m * f1

        for e, m in self.samples[component_ID]["constitution"].items():
            if e not in constitution:
                constitution[e] = 0
            constitution[e] += m * f2

        return constitution

    def all_sources(self):  # lists of sources
        self.sources = []
        for ID in self.samples:
            if self.samples[ID]["type"] != "sample":
                self.sources.append(self.samples[ID]["name"])

        self.sources.sort()

    def get_sources(self, obj):  # list of sources for a specific json object
        sources = []
        for ID in obj:
            for c in obj[ID]["composition"]:
                if c not in sources:
                    sources.append(c)

        return sources

    def ID_container(self, ID):
        if "NMR" in ID:
            return "NMR tube"
        if "ICP" in ID:
            return "ICP tube"
        return "glass vial"

    def null(self, ID):
        dt = datetime.now()
        self.samples[ID] = self.new_sample()
        self.samples[ID]["container"] = self.ID_container(ID)
        self.samples[ID]["timestamp"] = str(dt)

    def new_sample(self):  # template for a new sample
        return {
            "composition": {},
            "constitution": {},
            "unit": self.unit,
            "volume": 0,
            "timestamp": "",
            "parents": [],
            "parent_volumes": [],
            "type": "sample",
            "container": "",
            "name": "",
        }

    def add(
        self,
        ID,
        component_ID=None,  # a component, put None for a source
        volume=0,  # component volume, uL; put  for a source
        name="",  # mandatory for a source, optional for a sample
        elements=[],  # "elemental" composition for mixed reagents
        concentrations=[],  # "elemental" concentrations in unuts
    ):
        flag = 0

        if component_ID:
            if component_ID in self.samples:
                if ID not in self.samples:
                    self.samples[ID] = self.new_sample()
                    self.samples[ID]["container"] = self.ID_container(ID)
                self.samples[ID]["parents"].append(component_ID)
                self.samples[ID]["parent_volumes"].append(volume)
                self.samples[ID]["timestamp"] = self.stamp()  # last addition
                self.samples[ID]["composition"] = self.add_composition(
                    ID, component_ID, volume
                )
                self.samples[ID]["constitution"] = self.add_constitution(
                    ID, component_ID, volume
                )
                self.samples[ID]["type"] = "sample"
                self.samples[ID]["volume"] += volume
                flag = 1
            else:
                print("ID = %s: non existing component %s, ignore" % (ID, component_ID))
                return
        else:
            if name:
                if ID not in self.samples:
                    self.samples[ID] = self.new_sample()
                self.samples[ID]["composition"] = {name: 1.0}
                self.samples[ID]["volume"] = volume
                self.sources.append(name)
                if "solvent" in name:
                    self.samples[ID]["type"] = "solvent"
                else:
                    self.samples[ID]["type"] = "source"
                self.samples[ID]["constitution"] = self.source_constitution(
                    elements, concentrations
                )
                flag = 1
            else:
                print("ID = %s, Source name is mandatory, ignore" % ID)
                return

        if flag:
            self.samples[ID]["name"] = name

    def aliquot(self, ID, volume):
        if ID in self.samples:
            if self.samples[ID]["type"] == "source":
                if self.verbose == 2:
                    print("*** Ignores aliquoting from ID = %s as it is a source" % ID)
                return

            v = self.samples[ID]["volume"]
            if v:  # if finite source
                r = v - volume

                if r <= 0:
                    print(
                        "*** Improbably large aliquote for ID = %s, volume=%.2f uL, requested %.2f uL => skip"
                        % (ID, v, volume)
                    )
                    return

                f = r / v
                self.samples[ID]["parent_volumes"] = [
                    x * f for x in self.samples[ID]["parent_volumes"]
                ]
                self.samples[ID]["volume"] = r

    def report(self, ID):
        print("%s = %s" % (ID, self.samples[ID]))

    ########################################## itemization ####################################################

    def extract_substrate(
        self, name, category=""
    ):  # create a bill of items on a substrate by plate name and category
        s = {}
        for ID in self.samples:
            plate, _, _ = ID.rpartition(":")
            t = self.samples[ID]["type"]
            if name == plate and t != "solvent":
                if category and t != category:
                    continue
                s[ID] = self.samples[ID]
        return s

    def redefine_type(self, s, new_type):
        print("\n>> Redefines non-solvents as type %s" % new_type)
        for ID in s:
            if s[ID]["type"] != "solvent":
                s[ID]["type"] = new_type
        return s

    def waste_bill(self, obj):
        suffix = ", %"
        u = []
        vs = {}
        sources = [x + suffix for x in self.get_sources(obj)]
        exclude = ["solvent", "source"]

        for ID in obj:
            if obj[ID]["type"] not in exclude:
                c = {}
                c["container"] = obj[ID]["container"]
                for x, f in obj[ID]["composition"].items():
                    f = round(f, 2)
                    x += suffix
                    if f:
                        c[x] = f
                t = tuple(sorted(c.items()))
                u.append(t)
                v = obj[ID]["volume"]
                if t not in vs:
                    vs[t] = 0
                vs[t] += v

        u = Counter(u)
        l = [
            "container",
            "container count",
            "total volume, mL",
        ] + sources
        rows = []

        for c, count in u.items():
            row = {}
            row["container count"] = count
            row["total volume, mL"] = round(vs[c] * 1e-3, 1)

            c = dict(c)
            row["container"] = c["container"]

            for x in sources:
                if x in c:
                    row[x] = round(100 * c[x], 2)
                else:
                    row[x] = np.nan
            rows.append(row)

        bill = pd.DataFrame(rows, columns=l)
        bill.index = range(1, len(bill) + 1)

        print("\n\n>> Generated waste bill\n%s\n" % bill)

        return bill

    def compositions2df(
        self, data, suffix
    ):  # takes a list of compositions and makes a table of it
        df = pd.DataFrame(data)
        df = df.reindex(columns=df.columns.union(df.columns), fill_value=np.nan)
        df = df.astype(float)
        s = sorted(df.columns.difference(["volume"]))
        s.append("volume")
        df = df[s]
        if suffix:
            suffix = " (%s)" % suffix
            df.columns = [col + suffix for col in df.columns]
        return df

    def constitutions2df(
        self, data
    ):  # takes a list of  concentrations and makes a table of it
        df = pd.DataFrame(data)
        df = df.reindex(columns=df.columns.union(df.columns), fill_value=np.nan)
        df.columns = ["%s, %s" % (col, self.unit) for col in df.columns]
        return df


def example():
    co = CustomTracker()
    # co.load_json("pedigree")
    # co.update_json()
    co.add("source1", name="solvent")
    co.add(
        "source2",
        name="reagent1",
        elements=["Li", "Na", "Ca"],
        concentrations=[10, 5, 8],
    )  # mM default
    co.add(
        "source3",
        name="reagent2",
        elements=["Li", "Fe", "Cr"],
        concentrations=[2, 1, 0.6],
    )
    co.add("plate1:A1", "source1", 200)
    co.add("plate1:A1", "source2", 200)
    co.add("plate2:B4", "plate1:A1", 200)
    co.add("plate2:B4", "source3", 100)
    # print(co.samples)
    co.write_json()
    co.waste_bill(co.samples)


if __name__ == "__main__":
    example()
