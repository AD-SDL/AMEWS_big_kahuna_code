

from madsci.common.types.base_types import BaseModel
from typing import Literal
from pydantic import Field
from pydantic.types import Discriminator, Tag
from typing import Annotated, Union, Optional


class BigKahunaTags(str, Enum):
   SkipMap =  "SkipMap"  # short codes for common LS design tags
   SyringePump = "SyringePump"
   ExtSingleTip = "ExtSingleTip"
   SingleTip = "SingleTip"
   Chaser = "Chaser"
   FourTip = "4Tip"
   Backsolvent = "Backsolvent"
   LookAhead = "LookAhead"
   SkipWash = "SkipWash"
   Image = "Image"
   Processing = "Processing"


class BigKahunaParameter(BaseModel):
    name: str = Field(
        title="Parameter Name",
        description = "Name of the parameter"
    )
    type: str = Field(
        title="Parameter Type",
        description = "Type of the parameter"

    )
    unit: str = Field(
        title = "Parameter Unit",
        description= "Unit of the parameter"
    )
    
class BigKahunaPlate(BaseModel):
    name: str = Field(
        title="Plate Name",
        description = "Name of the Plate"
    )
    type: str = Field(
        title="Plate Type",
        description = "type of the Plate"
    )
    deck_position: str = Field(
        title="Plate Name",
        description = "Name of the Plate"
    )
    rows: int = Field(
            title="Plate Rows",
            description="The number of rows in the plate"
        )
    columns: int = Field(
            title="Plate Columns",
            description="The number of columns in the plate"
        )
    color: int = Field(
        title="Plate Color",
        description = "Color of the plate to display in library studio",
        default = 0x000000
    )

class BigKahunaChemical(BaseModel):
    name: str = Field(
        title="Chemical Name",
        description = "Name of the Chemical"
    )
    color: int = Field(
        title="Chemical Color",
        description = "Color of the chemical to display in library studio",
        default = 0x000000
    )
    source_plate: Optional[str] = Field(
        title="Source Plate",
        description = "Name of the plate the chemical is stored in",
        default=None
    )
    deck_position: str = Field(
            title="Deck Position",
            description="The position of the chemical on the deck"
        )
    row: int = Field(
         title="Chemical Row",
        description="The row of the chemical in the deck position",
        default=0
        )
    column: int = Field(
        title="Chemical Column",
        description="The column of the chemical in the deck position",
        default=0
        )
    volume: float = Field(
        title="Chemical Volume",
        description="The volume of the chemical",
        default=-1
        )

class BigKahunaAction(BaseModel):
    """a general big kahuna action"""
    action_type: str = Field(
        title="Action Type",
        description="The type of the action",
        default="action"
        )

class BigKahunaTransfer(BigKahunaAction):
    action_type: Literal["transfer"]  = Field(
        title="Action Type",
        description="The type of the action",
        default="transfer"
        )
    source_plate: str  = Field(
        title="Source Plate",
        description="The source plate for the transfer"
        )
    target_plate: str  = Field(
        title="Target Plate",
        description="The target plate for the transfer"
        )
    source_well: str = Field(
        title="Source Well",
        description="The source well for the transfer"
        )
    target_well: str = Field(
        title="Target Well",
        description="The target well for the transfer"
        )
    volume: float = Field(
        title="Transfer Volume",
        description="The volume for the transfer"
        )
    tags: list[BigKahunaTags] = Field(
        title="Tag Code",
        description="The Big Kahuna Specific Tags for the transfer",
        default=[]
        )


class BigKahunaDispense(BigKahunaAction):
    action_type: Literal["dispense"] = Field(
        title="Action Type",
        description="The type of the action",
        default="dispense"
        )
    source_chemical: str = Field(
        title="Source Chemical",
        description="The source chemical to dispense"
        )
    target_plate: str = Field(
        title="Target Plate",
        description="The target plate for the transfer"
        )
    target_well: str = Field(
        title="Target Plate",
        description="The target well for the transfer"
        )
    volume: float = Field(
        title="Target Volume",
        description="The volume to dispense"
        )
    tags: list[BigKahunaTags] = Field(
        title="Tag Code",
        description="The Big Kahuna Specific Tags for the transfer",
        default=[]
        )

class BigKahunaPause(BigKahunaAction):
     action_type: Literal["pause"] = Field(
        title="Action Type",
        description="The type of the action",
        default="pause"
        )
     target_plate: str = Field(
        title="Target Plate",
        description="The target plate for the pause"
        )
     code: str = Field(
        title="Code",
        description="The code for the pause to display"
        )

class BigKahunaDelay(BigKahunaAction):
    action_type: Literal["delay"] = Field(
        title="Action Type",
        description="The type of the action",
        default="delay"
        )
    target_plate: str = Field(
        title="Target Plate",
        description="The target plate for the delay"
        )
    delay: float  = Field(
        title="Code",
        description="The length for the delay"
        )

class BigKahunaStir(BigKahunaAction):
    action_type: Literal["stir"] = Field(
        title="Action Type",
        description="The type of the action",
        default="stir"
        )
    target_plate: str = Field(
        title="Target Plate",
        description="The target plate for the stir"
        )
    rate: float  = Field(
        title="Code",
        description="The rate for the stir"
        )
BigKahunaActions = Annotated[
    Union[
        Annotated[BigKahunaAction, Tag("action")],
        Annotated[BigKahunaTransfer, Tag("transfer")],
        Annotated[BigKahunaDelay, Tag("delay")],
        Annotated[BigKahunaDispense, Tag("dispense")],
        Annotated[BigKahunaPause, Tag("pause")],
        Annotated[BigKahunaStir, Tag("stir")],
    ],
    Discriminator("action_type"),
]


class BigKahunaProtocol(BaseModel):
    name: str = Field(
        title="Protocol Name",
        description="The Name of the Protocol"  
        )
    units: str = Field(
        title="Protocol Units",
        description="The units for the protocol",
        default="ul"
    )
    parameters: list[BigKahunaParameter] =  Field(
        title="Parameters",
        description="The list of parameters for the protocol",
        default_factory=list
    )
    plates: dict[str, BigKahunaPlate] =  Field(
        title="Plates",
        description="The dictionary of plates/libraries for the protocol",
        default_factory=dict
    )
    chemicals: list[BigKahunaChemical] = Field(
        title="Chemicals",
        description="The list of chemicals for the protocol",
        default_factory=list
    )
    actions: list[BigKahunaActions] = Field(
        title="Actions",
        description="The list of actions for the protocol",
        default_factory=list
    )

    


