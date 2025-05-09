from datetime import datetime
from pathlib import Path
from typing import Annotated, Any, Optional

from madsci.common.types.action_types import (
    ActionResult,
    ActionSucceeded,
    ActionFailed
)
from madsci.common.types.admin_command_types import AdminCommandResponse
from madsci.common.types.node_types import RestNodeConfig
from madsci.node_module.helpers import action
from madsci.node_module.rest_node_module import RestNode
from madsci.common.types.auth_types import OwnershipInfo
from madsci.common.types.resource_types.definitions import (
    ContainerResourceDefinition,
    SlotResourceDefinition,
)

from madsci.common.types.resource_types import ContinuousConsumable
from madsci.common.types.resource_types.definitions import ContinuousConsumableResourceDefinition
from big_kahuna_protocol_types import BigKahunaPlate, BigKahunaProtocol, BigKahunaAction
from madsci.client.resource_client import ResourceClient
from CustomServiceNew import LS10
import os



class BigKahunaConfig(RestNodeConfig):
    """Configuration for a Big Kahuna Node"""
    # directory: str
    # resource_server_url: Optional[str]
    # deck_locations: Optional[list[str]]
    # chemical_sources:   Optional[list[ContinuousConsumableResourceDefinition]]

    


class BigKahunaNode(RestNode):
    """Node Module Implementation for the Big Kahuna Instruments"""

    config_model = BigKahunaConfig
    def startup_handler(self):
        pass
        # if self.config.resource_server_url:
        #     self.resource_client = ResourceClient(self.config.resource_server_url)
        #     self.resource_owner = OwnershipInfo(node_id=self.node_definition.node_id)
        #     for location in self.config.deck_locations:
        #         rec_def = SlotResourceDefinition(
        #             resource_name= self.config.node_name + "_" + location,
        #             owner=self.resource_owner,
        #         )

        #         self.resource_client.init_resource(rec_def)
        #     for source in self.config.chemical_sources:
        #         source.owner = self.resource_owner
        #         self.resource_client.init_resource(source)
            
    @action
    def run_protocol(
        self,
        protocol: BigKahunaProtocol,
    ) -> ActionResult:
        """generate a library studio protocol"""
        protocol = BigKahunaProtocol.model_validate(protocol)
        library_studio = LS10()
        library_studio.create_lib(protocol.name)
        library_studio.units = protocol.units
        for parameter in protocol.parameters:
            library_studio.add_param(parameter.name, parameter.type, parameter.unit)
        for name, library in protocol.plates.items():
            library_studio.add_library(library.name, library.rows, library.columns, library.color)
        for chemical in protocol.chemicals:
            if chemical.source_plate is not None:
                plate =  protocol.plates[chemical.source_plate]
            else:
                plate = None
            library_studio.add_chemical(plate, chemical.name, chemical.row, chemical.column, chemical.color, chemical.volume)
        for protocol_action in protocol.actions:
            self.add_step(protocol_action, library_studio, protocol.plates)
        library_studio.finish(protocol.plates)
        library_studio.as_prep()
        success = library_studio.as_execute()
        if success and self.resource_client:
            for action in protocol.actions:
                try:
                    self.process_resource(action, protocol)
                except Exception as e:
                    self.logger.error(str(e))
        return ActionSucceeded()
        # else: 
        #     return ActionFailed()
        


   
    def add_step(self, action: BigKahunaAction, library_studio: LS10, plates: dict[str, BigKahunaPlate]):
        if action.action_type == "transfer":
            library_studio.single_well_transfer(action.source_plate, action.target_plate, action.source_well, action.target_well, action.volume, action.tags, -1,  plates)
        elif action.action_type == "dispense":
            library_studio.dispense_chem(action.source_chemical, action.target_plate, action.target_well, action.volume, action.tags)
        elif action.action_type == "pause":
            library_studio.Pause(action.target_plate, action.code)
        elif action.action_type == "delay":
            library_studio.Delay(action.target_plate, action.delay)
        elif action.action_type == "stir":
            library_studio.Stir(action.target_plate, action.rate)
   
    def process_resource(self, action, protocol):
        if action.action_type == "transfer":
            target_plate_location = self.deck_locations[protocol.plates[action.target_plate].deck_location]
            source_plate_location = self.deck_locations[protocol.plates[action.source_plate].deck_location]
            target_well_resource = self.resource_client.get_child(self.resource_client.get_child(target_plate_location, 0).resource_id, action.target_well).resource_id
            source_well_resource = self.resource_client.get_child(self.resource_client.get_child(source_plate_location, 0).resource_id, action.source_well).resource_id
            self.resource_client.set_child(target_well_resource, action.target_plate, ContinuousConsumable(resource_name=action.source_plate, quantity=action.volume))
            self.resource_client.change_quantity_by(source_well_resource, -action.volume)
        elif action.action_type == "dispense":
            if "SkipDispense" not in action.tags:
                target_plate_location = self.deck_locations[protocol.plates[action.target_plate].deck_location]
                source_chemical = self.chemical_sources[action.source_chemical]
                target_well_resource = self.resource_client.get_child(self.resource_client.get_child(target_plate_location, 0).resource_id, action.target_well).resource_id
                self.resource_client.set_child(target_well_resource, action.target_plate, ContinuousConsumable(resource_name=action.source_chemical, quantity=action.volume))
                self.resource_client.change_quantity_by(source_chemical, -action.volume)

if __name__ == "__main__":
    big_kahuna_node = BigKahunaNode()
    big_kahuna_node.start_node()