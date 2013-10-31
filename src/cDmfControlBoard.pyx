cdef class cDmfControlBoard:
    cdef DmfControlBoard *thisptr

    def __cinit__(self):
        self.thisptr = new DmfControlBoard()

    def __dealloc__(self):
        del self.thisptr

    property BAUD_RATE:
        def __get__(self):
            return self.thisptr.BAUD_RATE

    property SINE:
        def __get__(self):
            return self.thisptr.SINE

    property SQUARE:
        def __get__(self):
            return self.thisptr.SQUARE

    property EEPROM_CONFIG_SETTINGS:
        def __get__(self):
            return self.thisptr.EEPROM_CONFIG_SETTINGS

    def protocol_name(self):
        return self.thisptr.protocol_name()

    def protocol_version(self):
        return self.thisptr.protocol_version()

    def name(self):
        return self.thisptr.name()

    def manufacturer(self):
        return self.thisptr.manufacturer()

    def software_version(self):
        return self.thisptr.software_version()

    def hardware_version(self):
        return self.thisptr.hardware_version()

    def url(self):
        return self.thisptr.url()

    def debug_buffer(self):
        return self.thisptr.debug_buffer()

    def set_pin_mode(self, uchar pin, bint mode):
        self.thisptr.set_pin_mode(pin, mode)

    def digital_read(self, uchar pin):
        return self.thisptr.digital_read(pin)

    def digital_write(self, uchar pin, bint value):
        self.thisptr.digital_write(pin, value)

    def analog_read(self, uchar pin):
        return self.thisptr.analog_read(pin)

    def analog_reads(self, uchar pin, uint16_t n_samples):
        return self.thisptr.analog_reads(pin, n_samples)

    def analog_write(self, uchar pin, uint16_t value):
        self.thisptr.analog_write(pin, value)

    def eeprom_read(self, uint16_t address):
        return self.thisptr.eeprom_read(address)

    def eeprom_write(self, uint16_t address, uchar value):
        self.thisptr.eeprom_write(address, value)

    def onewire_address(self, uchar pin, uchar index):
        return self.thisptr.onewire_address(pin, index)

    def onewire_read(self, uchar pin, vector[uchar] address,
                     uchar command, uchar n_bytes):
        return self.thisptr.onewire_read(pin, address, command, n_bytes)

    def onewire_write(self, uchar pin, vector[uchar] address, uchar value,
                      uchar power):
        self.thisptr.onewire_write(pin, address, value, power)

    def i2c_write(self, uchar address, vector[uchar] data):
        self.thisptr.i2c_write(address, data)

    def i2c_read(self, uchar address, uchar n_bytes_to_read):
        return self.thisptr.i2c_read(address, n_bytes_to_read)

    def i2c_send_command(self, uchar address, uchar cmd, vector[uchar] data,
                         uchar delay_ms):
        return self.thisptr.i2c_send_command(address, cmd, data, delay_ms)

    def spi_set_bit_order(self, bint order):
        self.thisptr.spi_set_bit_order(order)

    def spi_set_clock_divider(self, uchar divider):
        self.thisptr.spi_set_clock_divider(divider)

    def spi_set_data_mode(self, uchar mode):
        self.thisptr.spi_set_data_mode(mode)

    def spi_transfer(self, uchar value):
        return self.thisptr.spi_transfer(value)

    def set_debug(self, bint debug):
        self.thisptr.set_debug(debug)

    def connected(self):
        return self.thisptr.connected()

    def Connect(self, char* port):
        return self.thisptr.Connect(port)

    def Disconnect(self):
        return self.thisptr.Disconnect()

    def flush(self):
        self.thisptr.flush()
