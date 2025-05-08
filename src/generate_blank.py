from big_kahuna_protocol_types import BigKahunaProtocol, BigKahunaDispense, BigKahunaPlate, BigKahunaChemical, BigKahunaParameter, BigKahunaStir, BigKahunaTransfer
import string
def generate_blank_protocol():
    input_wells=["A1", "A2", "B1", "B2", "C1", "C2"]
    counter_wells=["A3", "A4", "B3", "B4", "C3", "C4"]
    tube_rack_wells = [] 
    for i in range(0, 6):
        for j in range(1, 16):
            tube_rack_wells.append(string.ascii_uppercase(i) + str(j))
    sample_volume = 1e5
    chaser_volume = 2200
            
    protocol = BigKahunaProtocol(
                                name="AMEWS 6 cell blank",
                                units="ul",
                                parameters=[
                                     BigKahunaParameter(name="Delay", type="Time", units="min"),
                                     BigKahunaParameter(name="StirRate", type="Stir Rate", units="rpm"),
                                     BigKahunaParameter(name="Pause", type="Text", units="")

                                 ],
                                 plates=[
                                     BigKahunaPlate(name="source1", type="Rack 2x4 20mL Vial", rows=2, columns=4, deck_position="Deck 10-11 Position 2"),
                                     BigKahunaPlate(name="cell_plate_1", type="Rack 3x4 six Kaufmann H-cells", rows=3, columns=4, deck_position="Deck 12-13 Heat-Cool-Stir 1"),
                                     BigKahunaPlate(name="ICP_rack", type="Rack 6x15 ICP robotic", rows=6, columns=15, deck_position="Deck 16-17 Waste 1")
                                 ],
                                 chemicals=[
                                     BigKahunaChemical(name="solvent"),
                                     BigKahunaChemical(name="standard")
                                 ]
    

                                
                                 )
    protocol.actions.append(
        BigKahunaStir(target_plate="cell_plate_1", rate=500)
    )
    for well in input_wells:
        protocol.actions.append(
            BigKahunaDispense(source_chemical="standard", target_plate="cell_plate_1", target_well=well, volume=sample_volume, tags=["SkipDispense"])
        )
    for well in counter_wells:
         protocol.actions.append(
            BigKahunaDispense(source_chemical="standard", target_plate="cell_plate_1", target_well=well, volume=sample_volume, tags=["SkipDispense"])
        )
    target_well_index = 0
    for well in input_wells:
        target_well = tube_rack_wells[target_well_index]
        protocol.actions.append(
            BigKahunaDispense(source_chemical="solvent", target_plate="ICP_rack", target_well=target_well, volume=chaser_volume, tags=["SyringePump","SingleTip"])
        )
        protocol.actions.append(
            BigKahunaTransfer(source_plate="cell_plate_1", target_plate="ICP_rack", source_well=well, target_well=target_well, volume=sample_volume, tags=["SyringePump","SingleTip"])
        )
        protocol.actions.append(
            BigKahunaDispense(source_chemical="solvent", target_plate="cell_plate_1", target_well=well, volume=250, tags=["SyringePump","SingleTip"])
        )
        target_well_index += 1