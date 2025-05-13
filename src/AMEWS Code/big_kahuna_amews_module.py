from datetime import datetime
from pathlib import Path
from typing import Annotated, Any, Optional

from madsci.common.types.action_types import (
    ActionResult,
    ActionSucceeded
)
from madsci.common.types.admin_command_types import AdminCommandResponse
from madsci.common.types.node_types import RestNodeConfig
from madsci.node_module.helpers import action
from madsci.node_module.rest_node_module import RestNode
import json
from BK_AMEWS_6cells import AMEWS
import os



class BigKahunaConfig(RestNodeConfig):
    """Configuration for a Big Kahuna Node"""

    


class BigKahunaNode(RestNode):
    """Node Module Implementation for the Big Kahuna Instruments"""

    config_model = BigKahunaConfig


    @action
    def blank(
        self,
    ) -> ActionResult:
        """Copy results for the current container to storage"""
        amews = AMEWS()
        new_info = amews.AS_blank(amews.to_json())
        log_file = os.path.join(amews.ld.dir, amews.ld.as10.log)
        excerpt_file_name = "%s.csv" % amews.ld.as10.asl.excerpt_name
        excerpt_file = os.path.join(amews.ld.dir, excerpt_file_name)
        digest_vols_name = amews.ld.as10.asl.digest_vol_name
        digest_vols =  os.path.join(amews.ld.dir, digest_vols_name)
        return ActionSucceeded(data={"info": new_info}, files={
                                        "raw_log": log_file, 
                                        "excerpt_log": excerpt_file, 
                                        "digest_vols": digest_vols})
    @action
    def fill(
        self,
        info: Annotated[Any, "the json info to run the function"],
    ) -> ActionResult:
        """Copy results for the current container to storage"""
        amews = AMEWS()
        if type(info) == str:
            info = json.loads(info)
        new_info = amews.AS_fill(info)
        log_file = os.path.join(amews.ld.dir, amews.ld.as10.log)
        excerpt_file_name = "%s.csv" % amews.ld.as10.asl.excerpt_name
        excerpt_file = os.path.join(amews.ld.dir, excerpt_file_name)
        digest_vols_name = amews.ld.as10.asl.digest_vol_name
        digest_vols =  os.path.join(amews.ld.dir, digest_vols_name)
        return ActionSucceeded(data={"info": new_info}, files={
                                        "raw_log": log_file, 
                                        "excerpt_log": excerpt_file, 
                                        "digest_vols": digest_vols})
    
    @action
    def calibrate(
        self,
        info: Annotated[Any, "the json info to run the function"],
    ) -> ActionResult:
        """Copy results for the current container to storage"""
        amews = AMEWS()
        new_info = amews.AS_calibrate(info)
        log_file = os.path.join(amews.ld.dir, amews.ld.as10.log)
        excerpt_file_name = "%s.csv" % amews.ld.as10.asl.excerpt_name
        excerpt_file = os.path.join(amews.ld.dir, excerpt_file_name)
        digest_vols_name = amews.ld.as10.asl.digest_vol_name
        digest_vols =  os.path.join(amews.ld.dir, digest_vols_name)
        return ActionSucceeded(data={"info": new_info}, files={
                                        "raw_log": log_file, 
                                        "excerpt_log": excerpt_file, 
                                        "digest_vols": digest_vols})
    @action
    def sample(
        self,
        info: Annotated[Any, "the json info to run the function"],
        lap: Annotated[int, "the sample lap of the function"]
    ) -> ActionResult:
        """Copy results for the current container to storage"""
        amews = AMEWS()
        new_info = amews.AS_sample(info, lap)
        log_file = os.path.join(amews.ld.dir, amews.ld.as10.log)
        excerpt_file_name = "%s.csv" % amews.ld.as10.asl.excerpt_name
        excerpt_file = os.path.join(amews.ld.dir, excerpt_file_name)
        digest_vols_name = amews.ld.as10.asl.digest_vol_name
        digest_vols =  os.path.join(amews.ld.dir, digest_vols_name)
        return ActionSucceeded(data={"info": new_info}, files={
                                        "raw_log": log_file, 
                                        "excerpt_log": excerpt_file, 
                                        "digest_vols": digest_vols})


   




if __name__ == "__main__":
    big_kahuna_node = BigKahunaNode()
    big_kahuna_node.start_node()