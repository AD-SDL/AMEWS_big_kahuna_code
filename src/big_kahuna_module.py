from datetime import datetime
from pathlib import Path
from typing import Annotated, Any, Optional

from madsci.common.types.action_types import (
    ActionResult,
)
from madsci.common.types.admin_command_types import AdminCommandResponse
from madsci.common.types.node_types import RestNodeConfig
from madsci.node_module.helpers import action
from madsci.node_module.rest_node_module import RestNode
from BK_AMEWS_6cells import AMEWS
from big_kahuna_protocol_types import BigKahunaProtocol, BigKahunaAction
from CustomServiceGood import CustomLS10
import os



class BigKahunaConfig(RestNodeConfig):
    """Configuration for a Big Kahuna Node"""

    


class BigKahunaNode(RestNode):
    """Node Module Implementation for the Big Kahuna Instruments"""

    config_model = BigKahunaConfig


    @action
    def run_protocol(
        self,
        protocol: BigKahunaProtocol 
    ) -> ActionResult:
        """generate a library studio protocol"""
        library_studio = CustomLS10()
        library_studio.units = protocol.units
        for name, library in protocol.plates.items():
            library_studio.add_library(library.name, library.rows, library.columns, library.color)
        for chemical in protocol.chemicals:
            plate =  protocol.plates[chemical.source_plate]
            library_studio.add_chemical(plate, chemical.name, chemical.row, chemical.column, chemical.color, chemical.volume)
        for action in protocol.actions:
            self.add_step(action, library_studio)
        library_studio.finish()
        library_studio.as_prep()
        library_studio.as_execute()
   
    def add_step(action: BigKahunaAction, library_studio: CustomLS10):
        if action.action_type == "transfer":
            library_studio.single_well_transfer(action.source_plate, action.target_plate, action.source_well, action.target_well, action.volume, action.tag_code)
        elif action.action_type == "dispense":
            library_studio.dispense_chem(action.source_chemical, action.target_plate, action.target_well, action.volume, action.tag_code)
        elif action.action_type == "pause":
            library_studio.Pause(action.target_plate, action.code)
        elif action.action_type == "delay":
            library_studio.Delay(action.target_plate, action.delay)
        elif action.action_type == "stir":
            library_studio.Stir(action.target_plate, action.rate)



if __name__ == "__main__":
    big_kahuna_node = BigKahunaNode()
    big_kahuna_node.start_node()