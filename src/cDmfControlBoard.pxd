from libcpp.vector cimport vector
from libcpp.string cimport string
from libc.stdint cimport uint16_t, uint32_t
from cRemoteObject cimport uchar, RemoteObject


cdef extern from "dmf_control_board.h":
    cdef cppclass DmfControlBoard:
        DmfControlBoard()

        uint32_t BAUD_RATE
        uchar SINE
        uchar SQUARE
        uint16_t EEPROM_CONFIG_SETTINGS
