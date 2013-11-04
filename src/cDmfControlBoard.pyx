#cython: embedsignature=True
from cRemoteObject cimport RemoteObject, cRemoteObject


cdef class cDmfControlBoard(cRemoteObject):
    cdef DmfControlBoard *thisptr

    def __cinit__(self):
        self.thisptr = new DmfControlBoard()
        self.baseptr = <RemoteObject *>self.thisptr

    property EEPROM_CONFIG_SETTINGS:
        def __get__(self):
            return self.thisptr.EEPROM_CONFIG_SETTINGS

    property BAUD_RATE:
        def __get__(self):
            return self.thisptr.BAUD_RATE

    property SINE:
        def __get__(self):
            return self.thisptr.SINE

    property SQUARE:
        def __get__(self):
            return self.thisptr.SQUARE

    def __dealloc__(self):
        del self.thisptr
