from typing import Optional
import pandas as pd
from pydantic import BaseModel
import string
class LiquidStep(BaseModel):
    type: str
    location: str
    row: Optional[str]
    column : Optional[int] 
    timestamp: str
    volume: float

def read_logs(log_file: str):
    log_data = pd.read_csv(log_file, sep="\t")
    log_data = log_data.fillna("")
    test = log_data[(log_data["Action"] == "Move Arm To Substrate") | ( log_data["Parameter Name"].str.contains("Output : Volume" ))]
    test2 = log_data[( log_data["Parameter Name"].str.contains("Output : Volume" ))]
    current_location = None
    current_row = None
    current_column = None
    steps = []
    for index, row in log_data.iterrows():
        if row["Action"] == "Move Arm To Substrate":
            if row["Parameter Name"] == "Input : Substrate":
                current_location = row["Parameter Value"]
            if row["Parameter Name"] == "Input : Well Row":
                if row["Parameter Value"] is not "":
                    current_row = string.ascii_uppercase[int(row["Parameter Value"])  - 1]
                else:
                    current_row = None
            if row["Parameter Name"] == "Input : Well Column":
                if row["Parameter Value"] is not "":
                    current_column = row["Parameter Value"]
                else:
                    current_column = None
        elif row["Parameter Name"] == "Output : Volume Filld" or row["Parameter Name"] == "Output : Volume Dispensed":
            steps.append(LiquidStep(type="dispense", location=current_location, row=current_row, column=current_column, timestamp=row["Time"], volume=row["Parameter Value"]))
        elif row["Parameter Name"] == "Output : Volume Aspirated":
            steps.append(LiquidStep(type="aspirate", location=current_location, row=current_row, column=current_column, timestamp=row["Time"], volume=row["Parameter Value"]))
        return steps

        

        