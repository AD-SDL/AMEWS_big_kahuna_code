import sys, os
import string, math, re, random
import json, time
from glob import glob
from datetime import datetime
import numpy as np
import pandas as pd

user = os.getlogin()
sys.path.append('C:/Users/%s/Dropbox/Instruments cloud/Robotics/Unchained BK/AS Scripts/API Scripts' % user)

from a10_sila import CustomAS10 
from CustomService import *

def basics_test():  # a test of basic plate and transfer map methods
     
        pt = CustomPlateManager()
        tm = CustomTransferMap()  
        
        pt.add("plate1","Rack 3x4 six Kaufmann H-cells","Deck 12-13 Heat-Cool-Stir 1")
        pt.add("ICP1","Rack 5x12 ICP robotic","Deck 16-17 Waste 1")
        pt.add("ICP2","Rack 5x12 ICP robotic","Deck 16-17 Waste 1")           
              
        print("\n ==== map from ==== ")
        tm.add_from(pt,"plate1","A2:C2,A4:C4",0) # by column
        tm.report_from()
         
        print("\n ==== map to ==== ")
        tm.add_to(pt,"ICP1","full",1) # 60 tube rack,  1 by row
        tm.add_to(pt,"ICP2","full",1) # 60 tube rack,  1 by row
        # tm.add_to(pt,"ICP1","full",1) # 90 tube rack,  1 by row
        # tm.add_from("NMR1","full",1)  1 by row
        # tm.add_from("NMR2","full",1)  1 by row
        tm.report_to()
        
        tm.map(1)   # no randomization of sampling     
        tm.to_df()
        tm.to_csv_stamped()
        

def LS_only_test():
    
    ld = CustomLS10()
    ld.create_lib("test")
    
    ld.add_param("Delay","Time","min")
    ld.add_param("StirRate","Stir Rate","rpm")
    ld.add_param("Pause","Text","")
    ld.get_params() 
    
    #print(self.units_list())
    #ld.test_van_der_corput()
    
    # making a substrate library
    ld.pt.add("source1","Rack 2x4 20mL Vial","Deck 10-11 Position 2")
    ld.pt.add("plate1","Rack 3x4 six Kaufmann H-cells","Deck 12-13 Heat-Cool-Stir 1")
    ld.pt.add("plate2","Rack 3x4 six Kaufmann H-cells","Deck 14-15 Heat-Stir 1")  # to stir all six cells
    ld.pt.add("ICP1","Rack 5x12 ICP robotic","Deck 16-17 Waste 1")    
    #ld.pt.add("ICP1","Rack 12x5 ICP manual","Deck 16-17 Waste 1") 
    #ld.pt.add("NMR1","Rack 8x3 NMR bin","Deck 16-17 Waste 1") 
    #ld.pt.add("NMR2","Rack 8x3 NMR bin","Deck 16-17 Waste 2")  
    
    # adding all plates 
    ld.add_all_plates()
    
    # adding off deck and plate sources
    ld.add_chem(None,"solvent")
    
    # making the transfer map
    if ld.verbose: print("\n ==== map from ==== ")
    ld.tm.add_from(ld.pt,"plate1","A1:C1",0) # by column  red compartments
    ld.tm.report_from()
   
    if ld.verbose: print("\n ==== map to ==== ")
    ld.tm.add_to(ld.pt,"ICP1","full",1) # 60 tube rack,  1 by row
    #ld.tm.add_to(ld.pt,"NMR1","full",0) # 1 by row
    #ld.tm.add_to(ld.pt,"NMR2","full",0) # 1 by row
    ld.tm.report_to()
    
    ld.tm.map(0)   # no randomization of sampling     
    ld.tm.to_df()
    
    ld.Stir("plate1", 500) # rpm
    ld.Stir("plate2", 500) # rpm
    ld.dummy_fill("plate1", 1e5) # 100 mL
    ld.dummy_fill("plate2", 1e5) # 100 mL
    
    ld.Pause("plate1", "prep finished") # message
    
    # sourcing and dispensing chemicals
    
    source = ld.tm.full_plate(ld.pt, "source1", 1)
    

    if 0:  # input from command lines
    
        for i in range(ld.tm.n_from):   
            r, c = ld.tm.well2tuple(source[i])
            ld.add_chem("source1",
                        "mixture%d" % (i+1),
                        r, # row
                        c, # col
                        volume = 5000 # uL
                        ) 
    
    else: # input from a CSV file
        f = os.path.join(os.getcwd(), "input_example.csv")
        ld.log_input(f) # input from a CSV table
        print(ld.tracker.samples)
    
    # transfer from source to cell compartments, red is "symbolic" transfer
    
    for i in range(ld.tm.n_from):   
        j = i+1
        plate, well, _ = ld.tm.lib_from[i]
        row, col = ld.tm.well2tuple(well)
        
        well_green = ld.tm.tuple2well(row, col+2)    # into green compartments
        well_red = ld.tm.tuple2well(row, col)        # into red compartments
        
        ld.dispense_chem("mixture%d" % j,
                         plate,
                         well_green,
                         1000, # added volume
                         "1tip", # actual addition
                         True # add to sourcing log
                         )
        
        ld.dispense_chem("mixture%d" % j,
                         plate,
                         well_red,
                         1, # added volume, just to indicate a mixture and pass constitution
                         "skip", # skip addition
                         False # add to sourcing log
                         )
    
    ld.Pause("plate1", "mixtures in green compartments A3:C4") # message
    
    # transferring using the transfer map
    ld.transfer_replace_mapping(200, # volume
                                2000, # chaser volume
                                "1tip",
                                0.01 # min
                                ) 
       
    ld.Pause("plate1", "stirring off") # message
    
    ld.Stir("plate1", 0) # rpm
    ld.Stir("plate2", 0) # rpm
   
    ld.finish()       # writing into the database and creating log files and xml files for AS  
    
    ICP = ld.make_container("ICP1")
    ld.save_container(ICP)
    supply = ld.supply_request("ICP1")
    ld.save_container(supply)

    return ld
    
            
def LS_AS_test(): # a test of LS functions - a cyclical walk through plate1 mapping it on ICP1 rack
    
   
    ld = LS_only_test()
    
    if ld.as_prep(): sys.exit(0)    # run the standard experiment    
    ld.as_run_paused()
    print("\n\n********************  CONTROL BACK *******************************\n\n")
    ld.as_run_resume(False) # ignore other pauses
    ld.as_finish()
    #ld.make_container("ICP1")
    #ld.save_container()
    ld.smtp.alert("run %d finished with state %s" % (ld.ID, ld.as_state))

def LS_iterative(): # a test of LS functions - a cyclical walk through plate1 mapping it on ICP1 rack

    ld = CustomLS10()     
    if ld.as_prep(): sys.exit()
        
    ld.create_lib("test_simple")    
    ld.add_param("Delay","Time","min")
    ld.add_param("StirRate","Stir Rate","rpm")
    ld.get_params() 
    
    ld.pt.add("plate1","Rack 3x4 six Kaufmann H-cells","Deck 12-13 Heat-Cool-Stir 1")
    ld.pt.add("ICP1","Rack 5x12 ICP robotic","Deck 16-17 Waste 1") 
   
    # making the transfer map
    if ld.verbose: print("\n ==== map from ==== ")
    ld.tm.add_from(ld.pt,"plate1","A1:C2",0) # by column
    ld.tm.report_from()
   
    if ld.verbose: print("\n ==== map to ==== ")
    ld.tm.add_to(ld.pt,"ICP1","A1:A6",0) # 60 tube rack,  1 by row
    
    ld.tm.df['volume'] = pd.NA
    ld.tm.df['chaser'] = pd.NA
    ld.tm.df['stamp'] = ""
   
    ld.tm.report_to()
    
    ld.tm.map(0)   # no randomization of sampling     
    ld.tm.to_df()
    
    ld.add_all_plates()
    ld.Stir("plate1",500) # rpm
    
    ld.add_chem(None,"solvent") 
    ld.add_chem("plate1",None)  
    ld.dummy_fill("plate1")
    
    ID = ld.finish()
    promptsfile = ld.prompts
    chemfile = ld.chem
   
    i, t = 0, -1
    volume = 50 # uL
    chaser = 2000 # uL
    flag = 1
    n = len(ld.tm.mapping)
    
    for _, add_from, well_from, _, add_to, well_to, _ in ld.tm.mapping: 
        
        print("\n********************** STEP %d **************************\n" % (i+1))
        
        if ld.from_db(ID): break
        ld.transfer = i+1

        t = ld.transfer_replace_well(add_from, 
                                  add_to, 
                                  well_from, 
                                  well_to, 
                                  volume, 
                                  chaser, 
                                  "1tip", 
                                  0., # no delay
                                  t) # index
         

        ld.finish_iterative()  
        
        now = datetime.now()
        
        ld.as_run()
        
        if ld.as_state == "aborted":  
            ld.smtp.alert("aborted run %d, step %d" % (ld.ID,i+1),importance="High")
            flag=0
            break
        
        ld.tm.df.loc[i,'volume'] = volume
        ld.tm.df.loc[i,'chaser'] = chaser
        ld.tm.df.loc[i,'stamp'] = now.strftime('%m-%d-%Y %H:%M:%S')
        
        ld.tm.to_csv("transfer_log",ld.stamp) # save the transfer map
        
        i+=1   
        
    ld.as_finish()
    if flag: ld.smtp.alert("run %d completed" % (ld.ID))
    
    if i: 
        ld.tm.df = ld.tm.df.loc[:i]
        print("\nTIME STAMPED TRANSFER MAP\n%s\n" % (ld.tm.df))   
        ld.tm.to_csv("transfer_log",ld.stamp) # save the final transfer map
    
    ld.crunch()




def LS_once(): # a test of AddArrayMap()

    ld = CustomLS10()  
        
    ld.create_lib("test_array")  
    ld.pt.add("plate1","Rack 3x4 six Kaufmann H-cells","Deck 12-13 Heat-Cool-Stir 1")
    ld.pt.add("ICP1","Rack 5x12 ICP robotic","Deck 16-17 Waste 1")
      
    ld.add_all_plates()
    ld.add_chem(None,"solvent") 
    ld.add_chem("plate1",None)  
    ld.dummy_fill("plate1")   
    
    ld.single_well_transfer("plate1", "ICP1", "A1","A1", 200)
      
    ld.finish()
    
    ld.as_execute()
    ld.smtp.alert("run %d %s" % (ld.ID,ld.as_state))
    
#LS_test() # running the test     
#

#LS_iterative()

def run_tests():
     ld = CustomLS10()  
     
     #if "no-go" in ld.as_execute_noDC(739,0): sys.exit()
     if "no-go" in ld.as_execute_wDC(739): sys.exit()

if __name__ == "__main__":
    LS_only_test()   
