from enum import Enum

class ResponseSignal(Enum):

    FILE_NOT_SUPPORTED="Not supported types!"
    FILE_SIZE_EXCEEDED= "Above the allowed size!"
    FILE_SUCCESSFULLY_VALIDATED="Successfully Validated!"
    FILE_UPLOAD_SUCCEED="file_upload_succeed"
    FILE_UPLOAD_FAILED="file_upload_failed"
    PROCESSING_SUCCEED="Processing Succeed!"
    PROCESSING_FAILED= "Processing Failed!" 