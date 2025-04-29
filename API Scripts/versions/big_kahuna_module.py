
"""
REST-based node that interfaces with WEI and provides various fake actions for testing purposes
"""

from re import A
import os
import time
from typing import Annotated, Optional
from zipfile import ZipFile
import shutil
from a10_sila import CustomAS10
from fastapi import UploadFile
from fastapi.datastructures import State
from wei.modules.rest_module import RESTModule
import importlib
from wei.types import StepFileResponse, StepResponse, StepStatus
from wei.types.module_types import (
  
    Location,
    ModuleState,
    ModuleStatus
 
)
from wei.types.step_types import ActionRequest

# * Test predefined action functions


bk_rest_node = RESTModule(
    name="big_kahuna_node",
    description="A module for the big kahuna",
    version="1.0.0",
    resource_pools=[],
    model="big_kahuna",
    actions=[],
)



@bk_rest_node.startup()
def test_node_startup(state: State):
    """Initializes the module"""
    try:
        as10 = CustomAS10("tets")
        state.as10 = as10
        state.as_client = as10.FindOrStartAS()
        if as10.GetState() != "Stopped":
            raise(Exception("Robot not Idle!"))
        state.status[ModuleStatus.IDLE] = True
        state.status[ModuleStatus.INIT] = False
    except Exception:
        state.status = [ModuleStatus.ERROR] = True
        state.status[ModuleStatus.INIT] = False

@bk_rest_node.state_handler()
def state_handler(state: State) -> ModuleState:
    """Handles the state of the module"""
    module_status = state.as10.GetState()
    if module_status == "Stopped":
       state.status[ModuleStatus.IDLE] = True
    elif module_status == "Running":
        state.status[ModuleStatus.BUSY] = True
        state.status[ModuleStatus.IDLE] = False
    else:
         state.status[ModuleStatus.ERROR] = True

    return ModuleState(status=state.status, error=state.error)


@bk_rest_node.action()
def run_experiment(
    state: State,
    action: ActionRequest,
    design_id: Annotated[int, "The experiment design to run"],
    prompts_path: Annotated[str, "The prompts file to use"],
    chem_path: Annotated[str, "The chem file to use"],
    tip_manager_path: Annotated[str, "The chem file to use"] = None,

) -> StepResponse:
    """runs a pre-configured experiment"""
    # Write the temporary files (chemical manager and prompts)
    
    
    # Start the run via AS10 API
    last_state = state.as10.RunAS(design_id, prompts_path, chem_path, tip_manager_path)
    
    print("Run started, waiting for completion")
    
    # Handle changes to the state of the instrument
    while True:
        next_state = state.as10.WaitNextState(last_state, 1)
        if next_state != state.as10.wait_timeout:
            # If "WaitNextState" did not timeout then the state has changed
            last_state = next_state
            
            if last_state == state.as10.no_tips_state:
                print("The instrument is out of tips and needs attention, please check the AS10 user interface")
            elif last_state == state.as10.active_prompt_state:
                # This client could now check what the prompt is and potentially handle it
                prompt_content = state.as10.GetActivePromptMessage(state.as10.GetActivePrompt())
                print(state.as10.GetActivePrompt())
                print("The AS10 user interface has displayed a prompt and needs attention: " + prompt_content)
            elif last_state == state.as10.paused_state:
                print("The user has paused the experiment")
            elif last_state == state.as10.running_state:
                print("The experiment has resumed")
            elif last_state == state.as10.stopped_state:
                break

    final_status = state.as10.GetStatusContent()
    if final_status == "Experiment completed":
        print("The experiment has completed")
        return StepResponse.step_succeeded()
    elif final_status == "Experiment aborted":
        print("The experiment was aborted")
        return StepResponse.step_failed()
    else:
        print("Unexpected final status: " + final_status)
        StepResponse.step_failed()

@bk_rest_node.action()
def run_experiment_to_pause(
    state: State,
    action: ActionRequest,
    design_id: Annotated[int, "The experiment design to run"],
    prompts_path: Annotated[str, "The prompts file to use"],
    chem_path: Annotated[str, "The chem file to use"],
    tip_manager_path: Annotated[str, "The chem file to use"] = None,

) -> StepResponse:
    """runs a pre-configured experiment"""
    # Write the temporary files (chemical manager and prompts)
    
    
    # Start the run via AS10 API
    as_client =state.as_client
    last_state = as10.RunAS(as_client, design_id, prompts_path, chem_path, tip_manager_path)
    
    print("Run started, waiting for completion")
    
    # Handle changes to the state of the instrument
    while True:
        next_state = as10.WaitNextState(as_client, last_state, 1)
        if next_state != as10.wait_timeout:
            # If "WaitNextState" did not timeout then the state has changed
            last_state = next_state
            
            if last_state == as10.no_tips_state:
                print("The instrument is out of tips and needs attention, please check the AS10 user interface")
            elif last_state == as10.active_prompt_state:
                # This client could now check what the prompt is and potentially handle it
                prompt_content = as10.GetActivePromptMessage(as10.GetActivePrompt(as_client))
                print(as10.GetActivePrompt(as_client))
                print("The AS10 user interface has displayed a prompt and needs attention: " + prompt_content)
                break
            elif last_state == as10.paused_state:
                print("The user has paused the experiment")
                break
            elif last_state == as10.running_state:
                print("The experiment has resumed")
            elif last_state == as10.stopped_state:
                break

    final_status = as10.GetStatusContent(as_client)
    return StepResponse.step_succeeded("test")
    if final_status == "Experiment completed":
        print("The experiment has completed")
        return StepResponse.step_succeeded("test")
    elif final_status == "Experiment aborted":
        print("The experiment was aborted")
        return StepResponse.step_failed("test")
    else:
        print("Unexpected final status: " + final_status)
        StepResponse.step_failed("test")
        
@bk_rest_node.action()
def run_or_resume_experiment_to_pause(
    state: State,
    action: ActionRequest,
    design_id: Annotated[int, "The experiment design to run"],
    prompts_path: Annotated[str, "The prompts file to use"],
    chem_path: Annotated[str, "The chem file to use"],
    tip_manager_path: Annotated[str, "The chem file to use"] = None,

) -> StepResponse:
    """runs a pre-configured experiment"""
    # Write the temporary files (chemical manager and prompts)
    
    
    # Start the run via AS10 API
    as_client =state.as_client
    bk_state = as10.GetState(as_client=as_client) 
    if bk_state == as10.stopped_state:
        last_state = as10.RunAS(as_client, design_id, prompts_path, chem_path, tip_manager_path)
    elif bk_state == as10.paused_state:
        as_client.ExperimentStatusService.SetInput("OK")
        print("Run started, waiting for completion")
        last_state = as10.GetState(as_client)
        print("Run started, waiting for completion")
    
    # Handle changes to the state of the instrument
    while True:
        next_state = as10.WaitNextState(as_client, last_state, 1)
        if next_state != as10.wait_timeout:
            # If "WaitNextState" did not timeout then the state has changed
            last_state = next_state
            
            if last_state == as10.no_tips_state:
                print("The instrument is out of tips and needs attention, please check the AS10 user interface")
            elif last_state == as10.active_prompt_state:
                # This client could now check what the prompt is and potentially handle it
                prompt_content = as10.GetActivePromptMessage(as10.GetActivePrompt(as_client))
                print(as10.GetActivePrompt(as_client))
                print("The AS10 user interface has displayed a prompt and needs attention: " + prompt_content)
                break
            elif last_state == as10.paused_state:
                print("The user has paused the experiment")
                break
            elif last_state == as10.running_state:
                print("The experiment has resumed")
            elif last_state == as10.stopped_state:
                break

    final_status = as10.GetStatusContent(as_client)
    return StepResponse.step_succeeded()
        
# Clean up temporary files
@bk_rest_node.action()
def resume(
    state: State,
    action: ActionRequest,

) -> StepResponse:
    """runs a pre-configured experiment"""

    # Start the run via AS10 API
    as_client =state.as_client
    as_client.ExperimentStatusService.SetInput("OK")
    print("Run started, waiting for completion")

    last_state = as10.GetState(as_client)
    # Handle changes to the state of the instrument
    while True:
        next_state = as10.WaitNextState(as_client, last_state, 1)
        if next_state != as10.wait_timeout:
            # If "WaitNextState" did not timeout then the state has changed
            last_state = next_state
            
            if last_state == as10.no_tips_state:
                print("The instrument is out of tips and needs attention, please check the AS10 user interface")
            elif last_state == as10.active_prompt_state:
                # This client could now check what the prompt is and potentially handle it
                prompt_content = as10.GetActivePromptMessage(as10.GetActivePrompt(as_client))
                print(as10.GetActivePrompt(as_client))
                print("The AS10 user interface has displayed a prompt and needs attention: " + prompt_content)
            elif last_state == as10.paused_state:
                print("The user has paused the experiment")
            elif last_state == as10.running_state:
                print("The experiment has resumed")
            elif last_state == as10.stopped_state:
                break

    final_status = as10.GetStatusContent(as_client)
    if final_status == "Experiment completed":
        print("The experiment has completed")
        return StepResponse.step_succeeded("test")
    elif final_status == "Experiment aborted":
        print("The experiment was aborted")
        return StepResponse.step_failed()
    else:
        print("Unexpected final status: " + final_status)
        StepResponse.step_failed()    


@bk_rest_node.action()
def run_experiment_using_python_protocol(
    state: State,
    action: ActionRequest,
    protocol: Annotated[UploadFile, "Protocol File"],
    protocol_args: Annotated[dict, "The the json arguments to library studio"],
    rename_container: Annotated[bool, "Rename container"] # added 3-12-2025
) -> StepResponse:
    """runs a pre-configured experiment"""
    
    # Run the library studio commands to c
    protocol = next(file for file in action.files if file.filename == "protocol")
    print(protocol)
    protocol = protocol.file.read().decode("utf-8")
    protocol_path = "protocol.py"
   
    with open(protocol_path, "w", encoding="utf-8") as pc_file:
            pc_file.write(protocol)

    import protocol

    importlib.reload(protocol)

    ld, containers = protocol.main(**protocol_args)

    if ld.as_prep():
        return StepResponse.step_failed("couldn't set up connection")

    ld.as_run()

    # housekeeping added 3-12-2025
    # call housekeeping(category, rename_container)

    log_file = os.path.join(ld.dir, ld.as10.log)
    excerpt_file_name = "%s.csv" % ld.as10.asl.excerpt_name
    excerpt_file = os.path.join(ld.dir, excerpt_file_name)
    digest_vols_name = "%s.csv" % ld.as10.asl.digest_vol_name
    digest_vols =  os.path.join(ld.dir, digest_vols_name)

    shutil.copy(log_file, os.getcwd())
    shutil.copy(excerpt_file, os.getcwd())
    shutil.copy(digest_vols, os.getcwd())

    response = StepFileResponse(status=StepStatus.SUCCEEDED, 
                                
                                data={"ID": ld.ID, 
                                        "prompts":   ld._prompts, 
                                        "chem":      ld._chem, 
                                        "last_code": ld.last_code, 
                                        "containers": containers}, 

                                files={"raw_log":     ld.as10.log, 
                                        "excerpt_log": excerpt_file_name, 
                                        "digest_vols": digest_vols_name})

    os.remove(ld.as10.log)
    os.remove(excerpt_file_name)
    os.remove(digest_vols_name)
    

    return response
if __name__ == "__main__":
    bk_rest_node.start()
