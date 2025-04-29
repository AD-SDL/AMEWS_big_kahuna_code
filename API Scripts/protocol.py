def main(cells_list, rack, prep, path, sources, volume, chaser, fictive, verbose):
    ld = LS_open(cells_list, rack, path, sources, verbose, "sample blanks")
    LS_to(prep, ld)

    #print(self.ld.tracker.samples)
    # transfer from source to cell compartments, red is "symbolic" transfer

    i=0
    for plate, well, _ in ld.tm.lib_from:
        ld.dispense_chem(ld.input_names[i],
                            plate,
                            well,
                            fictive, # added volume
                            "skip", # "1tip", # actual addition
                            True # add to sourcing log
                            )
        i+=1

    prep += i
    ld.tm.mapping = ld.tm.mapping[0:i]
    ld.tm.to_df()

    # transferring using the transfer map
    ld.transfer_replace_mapping(volume, # volume
                                chaser, # chaser volume
                                "1tip",
                                )
    
    #self.ld.Pause("plate1", 20) # message

    ld.finish()       # writing into the database and creating log files and xml files for AS  

    c= ld.make_container("ICP1", "blank")

    prep_container = ld.update_container({}, c)
    ld.save_container(prep_container, image=False)

    return ld, [prep_container]
    #return ld.ID
def LS_open(cells, rack, path, sources, verbose=False, name = "sampling",): 
    from CustomService import CustomLS10
    import os
    ld = CustomLS10()
    ld.create_lib(name)
    COUNT = 0
    ld.disp.COUNT = COUNT
    COUNT+=1

    print("\n\n")
    print("#" * 80)
    print("#\t\tAMEWS %s" % name.upper())
    print("#" * 80)
    print("\n\n")

    ld.add_param("Delay","Time","min")
    ld.add_param("StirRate","Stir Rate","rpm")
    ld.add_param("Pause","Text","")
    ld.get_params() 

    # making a substrate library
    ld.pt.add("source1","Rack 2x4 20mL Vial","Deck 10-11 Position 2")
    ld.pt.add("plate1","Rack 3x4 six Kaufmann H-cells","Deck 12-13 Heat-Cool-Stir 1")

    if 'fill' not in name:
        if rack==90: 
            ld.pt.add("ICP1","Rack 6x15 ICP robotic","Deck 16-17 Waste 1")
        if rack==60:
            ld.pt.add("ICP1","Rack 5x12 ICP robotic","Deck 16-17 Waste 1")

    # adding all plates 
    ld.add_all_plates()

    # adding off deck and plate sources
    ld.add_chem(None,"solvent")

    # making the transfer map
    if verbose: print("\n ==== map from ==== ")
    ld.tm.add_from(ld.pt,"plate1",cells,0) # by column  red compartments
    ld.tm.report_from()

    # input from a CSV file
    f = os.path.join(path, sources)
    ld.log_input(f) # input from a CSV table

    ld.Stir("plate1", 500) # rpm
    ld.dummy_fill("plate1", 1e5) # 100 mL

    # sourcing and dispensing chemicals
    source = ld.tm.full_plate(ld.pt, "source1", 1)
    return ld
def LS_to(prep, ld, verbose=False): 
   
        if verbose: 
            print("\n ==== map to ==== ")
            print("\n>> ICP rack offset = %d\n" % prep)

        ld.tm.add_to(ld.pt, "ICP1", "A1:A6", 1, prep) # tube rack, 1 by row, self.prep is offset
        ld.tm.report_to()
    
        ld.tm.map(0)   # no randomization of sampling 

        ld.tm.to_df()
        #print(self.ld.tracker.samples)