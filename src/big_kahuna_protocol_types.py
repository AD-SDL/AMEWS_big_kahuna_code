



class BigKahunaPlate:
    name: str
    type: str
    rows: int
    columns: int
    position: str

class BigKahunaChemical:
    name: str
    color: int = 0x000000
    deck_position: str
    row: int
    column: int
    volume: float

class BigKahunaAction:
    """a general big kahuna action"""
    action_type: str

class BigKahunaTransfer(BigKahunaAction):
    action_type = Literal["transfer"]
    source_plate: str
    target_plate: str
    source_well: str
    target_well: str
    volume: float
    tag_code: str ="1tip",
    index: int = -1,


class BigKahunaDispense(BigKahunaAction):
    action_type = Literal["dispense"]
    source_chemical: str
    target_plate: str
    target_well_range: str
    volume: float
    tag_code: str ="1tip",
    index: int = -1,

class BigKahunaPause(BigKahunaAction):
     action_type = Literal["pause"]
     target_plate: str
     code: str

class BigKahunaDelay(BigKahunaAction):
    action_type = Literal["delay"]
    target_plate: str
    delay: float

class BigKahunaStir(BigKahunaAction):
    action_type = Literal["stir"]
    target_plate: str
    rate: float


class BigKahunaProtocol:
    units: str = "ul"
    plates: list[BigKahunaPlate]
    chemicals: list[BigKahunaChemical]
    actions: list[BigKahunaAction]


