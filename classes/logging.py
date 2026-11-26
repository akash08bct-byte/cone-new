import logging
from paths import ERROR_LOG

def error_log(msg,error):
    logging.basicConfig(
        filename=ERROR_LOG,
        level=logging.ERROR,
        format="%(asctime)s - %(levelname)s - %(message)s"
    )
    var = f"{msg} :{error}"
    logging.exception(var)

