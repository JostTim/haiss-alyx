from textwrap import dedent

# ALYX-SPECIFIC
ALLOWED_HOSTS = ["localhost", "127.0.0.1"]
LANGUAGE_CODE = "en-us"
TIME_ZONE = "GB"
GLOBUS_CLIENT_ID = "525cc543-8ccb-4d11-8036-af332da5eafd"
SUBJECT_REQUEST_EMAIL_FROM = "timothe.jost-mousseau@pasteur.fr"
DEFAULT_SOURCE = "IBL"
DEFAULT_PROTOCOL = "1"
SUPERUSERS = ("root",)
STOCK_MANAGERS = ("root",)
WEIGHT_THRESHOLD = 0.75
DEFAULT_LAB_NAME = "defaultlab"
WATER_RESTRICTIONS_EDITABLE = False  # if set to True, all users can edit water restrictions
# DEFAULT_LAB_PK = '6daeb82a-50ca-4ee9-ae97-50abfd3f50b6'
SESSION_REPO_URL = "http://ibl.flatironinstitute.org/{lab}/Subjects/{subject}/{date}/{number:03d}/"
NARRATIVE_TEMPLATES = {
    "Headplate implant": dedent(
        """
    == General ==

    Start time (hh:mm):   ___:___
    End time (hh:mm):    ___:___

    Bregma-Lambda :   _______  (mm)

    == Drugs == (copy paste as many times as needed; select IV, SC or IP)
    __________________( IV / SC / IP ) Admin. time (hh:mm)  ___:___

    == Coordinates ==  (copy paste as many times as needed; select B or L)
    (B / L) - Region: AP:  _______  ML:  ______  (mm)
    Region: _____________________________

    == Notes ==
    <write your notes here>
        """
    ),
}
