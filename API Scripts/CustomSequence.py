
import sys, os
import string, math
import json, time, shutil, glob
from datetime import datetime
import numpy as np
import pandas as pd
import tkinter as tk
from tkinter import filedialog

user = os.getlogin()
sys.path.append('C:/Users/%s/Dropbox/Instruments cloud/Robotics/Unchained BK/AS Scripts/API Scripts' % user)

from CustomService import *


#######################################################################################################################

class CustomSequence:

    def __init__(self, exp = None):

        self.exp = None
        self.farm = None
        self.log = None
        self.t0 = {}
        self.c0 = {}
        self.user = os.getlogin()
        self.exp_path = r"Z:\RESULTS"
        self.unit = "mM"

        if exp: 
            self.exp = exp
            print("\n>> Experiment folder = %s" % exp)
            try: 
                self.results = os.path.join(exp, "Results")
                print(">> Results folder = %s" % self.results)
                os.makedirs(self.results, exist_ok=True)
            except: 
                pass
        else:
            self.select_dir()

        try:
            f = os.path.join(self.exp, "cell farm.csv")
            self.farm = pd.read_csv(f)
            print("\n>> Found cell farm %s\n\n%s\n" % (f, self.farm))
        except:
            print("\n>> Cannot find cell farm %s, abort" % f)
            sys.exit(0)


# ====================================== consolidate log files  ===============================================


    def select_dir(self): # select directory by cursor

        root = tk.Tk()
        root.withdraw()  # Hide the root window
        self.exp = filedialog.askdirectory(initialdir=self.exp_path, 
                                           title="Select an experiment")
        print("\n>> Experiment folder = %s" % self.exp)

        self.results = os.path.join(self.exp, "Results")
        print("\n>> Results folder = %s" % self.results)
        os.makedirs(self.results, exist_ok=True)

    def consolidate_BK_records(self): # consolidate all records
        try:
            if self.exp: 
                self.consolidate_waste_logs()
                self.combine_AS_digests()
                self.add_ICP_records()
        except Exception as e:
           print(">> Cannot consolidate BK records, error = %s" % e)

    def consolidate_PAL_records(self): # consolidate all records
        try:
            if self.exp: 
                self.consolidate_waste_logs()
                self.add_ICP_records(log="sequence_log", digest="extended_time_log")
        except Exception as e:
            print(">> Cannot consolidate PAL records, error = %s" % e)

    def consolidate_waste_logs(self):  # consolidate waste logs and remove individual logs

        files = glob(os.path.join(self.exp, "waste*.csv"))
        dfs = []

        print(">> Found %d waste files to consolidate" % len(files))

        for f in files:
            if "combined" not in f:
                ID = f.replace('.csv', '').split('_')[-1]
                print("+++ processing waste from library %s" % ID)
                try:
                    df = pd.read_csv(f)
                    df.insert(0, "library", int(ID))
                    df = df[~df['container'].str.contains('glass', case=False, na=False)]
                    if len(df): 
                        dfs.append(df)
                    #os.remove(f)
                except: pass

        if len(dfs):
            waste = pd.concat(dfs, ignore_index=True)
            waste = waste.sort_values(by="library", ascending=True)
            waste = waste.drop(columns=['Unnamed: 0'])
            f = os.path.join(self.exp, "waste_ICP_combined.csv")
            waste.to_csv(f, index=False)

    def find_rack_container(self, i):
        for _, r in self.log[i:].iterrows():
            if 'rack' in r['category']:
                return r['container']
        self.log.loc[i, 'container']

    def find_cell(self, mask):
        for _, r in self.farm.iterrows():
            if mask in r['label']:
                return r['cell']
        return None

    def index2name(self, c):
        for _, r in self.farm.iterrows():
            q = r['label'].split('-')
            if q[2]=="IN" and r['cell']==c:
                return "%s-%s-%d" % (q[0].lower(),q[1].upper(),c)
        return None

    def find_counter_well(self, c):
        for _, r in self.farm.iterrows():
            q = r['label'].split('-')
            if q[2]=="OUT" and r['cell']==c:
                return r['address']
        return None

    def combine_AS_digests(self, log="AS_sequence_log", digest="ASDigest_vols_combined"):

        self.last_digest = None
        self.log = None
        self.t0 = {}
        self.fill = ""

        try: 
            self.log = pd.read_csv(os.path.join(self.exp, "%s.csv" % log))
        except:
            print(">> Cannot find sequence log file, abort")
            return 0

        print("\n\n>> Using %s.csv file to consolidate AS digests\n" % log)
        self.log['AS log'] = self.log['AS log'].fillna("")

        j=-1

        self.log['barcode'] = pd.to_numeric(self.log['barcode'], errors='coerce')
        self.log['barcode'] = self.log['barcode'].fillna(0).astype(int)

        dfs = []
        for i, r in self.log.iterrows():
            ID = r["ID"]
            category = r["category"]
            container = self.find_rack_container(i)
            barcode = r["barcode"]
            f = r["AS log"]
            if f:
                f = f.replace("ASMain","ASDigest_vols")
                f = f.replace(".log",".csv")
                g = os.path.join(self.exp, f)
                df = pd.read_csv(g)
                # print("+++ processing digest %s" % g)
                if "fill" in category:
                    if category != self.fill:
                        self.fill = category

                if len(df):
                    print(">> Processed %s : ID=%d, container=%s, barcode=%d, category=%s" % (f, ID, container, barcode, category))
                    df.insert(0, "library", ID)
                    df.insert(1, "container", container)
                    df.insert(2, "barcode", barcode)
                    df.insert(3, "category", category)
                    if self.fill: 
                        df.insert(4, "feed", self.fill)
                    else:
                        df.insert(4, "feed", "fill1")
                    dfs.append(df)

        if len(dfs):
            self.last_digest = pd.concat(dfs, ignore_index=True)
            del dfs
            self.last_digest['sample'] = None
            self.last_digest.insert(0, 'sample', self.last_digest.pop('sample'))

            for i, r in self.last_digest.iterrows(): # zero times from the first fill
                c = self.find_cell("%s-%s" % (r['plate from'], r['well from']))
                self.last_digest.loc[i, 'index'] = c
                if "load" in r['category']:
                    c = self.find_cell("%s-%s" % (r['plate to'], r['well to']))
                    self.last_digest.loc[i, 'index'] = c
                elif "fill" in r['category']:
                    if "source" in r["plate from"]: 
                        dt = datetime.strptime(r["datetime"], "%m/%d/%Y %H:%M:%S")
                        c = self.find_cell("%s-%s" % (r['plate to'], r['well to']))
                        self.last_digest.loc[i, 'index'] = c
                        if c: self.t0[c] = dt
                    else:
                        self.last_digest.loc[i, 'category'] = r['category'].replace["fill","calibrate"]
                else: 
                    self.last_digest.loc[i, 'sample'] = "%s-BK-%s" % (r['container'], r['well to'])
                print(c)

            print("\n\n>> Took t0 from cell fill record")
            print(self.t0)
            for c, dt in self.t0.items():
                print("--- t0 for cell well %s = %s" % (c, dt))

            self.last_digest["th"] = np.nan
            self.last_digest['well from'] = self.last_digest['well from'].fillna('')

            for i,r in self.last_digest.iterrows():
                    c = r["index"]
                    if c: 
                        dt = datetime.strptime(r["datetime"], "%m/%d/%Y %H:%M:%S")
                        dt -= self.t0[c]
                        self.last_digest.loc[i, 'th'] = dt.total_seconds()/3600

            f = os.path.join(self.exp,"%s.csv" % digest)

            try: 
                self.last_digest.to_csv(f, index=False)
                print("\n>> Combined digest files to %s" % f)
            except Exception as e:
                print("\n>> Cannot combine files, error = %s" % e)
            return 1
        else:
            print("\n>> Did not find digests to consolidate, abort")

        return 0


    def add_ICP_records(self, log="AS_sequence_log", digest="ASDigest_vols_combined"):

        os.makedirs(self.exp, exist_ok=True)
        os.makedirs(self.results, exist_ok=True)

        try: 
            self.last_digest = pd.read_csv(os.path.join(self.exp, "%s.csv" % digest))
            self.log = pd.read_csv(os.path.join(self.exp, "%s.csv" % log))
        except:
            print("\n>> Cannot find combined digest and/or sequence log files, abort")
            return 0

        print("\n\n>> Using %s file to add ICP records to digests\n" % log)

        flag=0

        for _, r in self.log.iterrows():
            container = r["container"]
            if "rack" in r["category"]:
                files = glob(os.path.join(self.exp,"run_%s_*_converted.csv" % container))
                if files:
                    print("\n>> Processing container %s: %d file(s))" % (container,len(files)))
                    for f in files:
                        print(">> add record from %s" % os.path.basename(f))
                        df = pd.read_csv(f)
                        df['Date'] += ' ' + df['Time']
                        df.rename(columns={'Date': 'analyzed'}, inplace=True)
                        df.drop(columns=['Time'], inplace=True)
                        if flag==0:
                            flag=1
                            for col in df.columns:
                                if col != 'Sample' and col not in self.last_digest.columns:
                                    self.last_digest[col] = None

                        for _, row in df.iterrows():
                            sample = row['Sample']
                            c = (self.last_digest['sample'] == sample)
                            m = self.last_digest[c].shape[0]

                            if m: 
                                if m==1:  print(sample, m)
                                else: print(sample, m, " ***** ")

                                for col in df.columns:
                                    if col != 'Sample': 
                                        self.last_digest.loc[c, col] = row[col]

        if flag==0: 
            print("\n>> No ICP analysis files to add, will only split data")
        else: 
            print("\n>> added ICP records")
        
        self.last_digest = self.last_digest.rename(columns={'index': 'cell'})
        f = os.path.join(self.exp,"%s_w_ICP.csv" % digest)
        self.last_digest.to_csv(f, index=False)

        self.last_digest = self.last_digest[~self.last_digest['category'].str.contains('fill|load', case=False, na=False)]
        self.last_digest = self.last_digest.drop(columns = ["datetime", "container", "library",
                                            "plate from", "well from", "plate to", "well to"])

        if any("address" in col for col in self.last_digest.columns):
               self.last_digest = self.last_digest.drop(columns = ["address from", "address to"])

        print("\n>> Grouping by cells")
        grouped = self.last_digest.groupby(['cell'])
        feeds = self.last_digest['feed'].unique()

        self.c0 = {}

        for q in feeds: # for each cell fill, add estimated feed concentrations
            print("+++ adding concentrations from %s" % q)
            f= os.path.join(self.exp, "%s.json" % q)
            with open(f, 'r') as j:
                  self.c0[q]=json.load(j)

        for (c,), group in grouped:
            ID = self.find_counter_well(c)
            f= os.path.join(self.results, "%s.csv" % self.index2name(c))
            if ID:
                print("+++ Extracted cell %d, counter address %s" % (c, ID))
                for q in self.c0:
                    if ID in self.c0[q]:
                        u = self.c0[q][ID]
                        if "unit" in u:
                            self.unit = u["unit"]
                        if "constitution" in u:
                            for el, conc in u["constitution"].items():
                                label = "%s, %s" % (el, self.unit)
                                if label not in group.columns:
                                    group[label] = None
                                group.loc[group['feed'] == q, label] = conc

            group['feed'] = pd.factorize(group['feed'])[0]

            if "analyze" in group.columns: 
                group = group.dropna(subset=['kind'])
                group = group.drop(columns=["analyzed", "method"])
            group = group.drop(columns=["cell"])
            group.insert(0, 'th', group.pop('th'))
            group.to_csv(f, index=False)

        return 1

if __name__ == "__main__":
    seq  = CustomSequence()

