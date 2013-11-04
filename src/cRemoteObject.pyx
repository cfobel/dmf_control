#cython: embedsignature=True
cdef class cRemoteObject:
    def protocol_name(self):
        return self.baseptr.protocol_name()

    def protocol_version(self):
        return self.baseptr.protocol_version()

    def name(self):
        return self.baseptr.name()

    def manufacturer(self):
        return self.baseptr.manufacturer()

    def software_version(self):
        return self.baseptr.software_version()

    def hardware_version(self):
        return self.baseptr.hardware_version()

    def url(self):
        return self.baseptr.url()

    def debug_buffer(self):
        return self.baseptr.debug_buffer()

    def set_pin_mode(self, uchar pin, bint mode):
        self.baseptr.set_pin_mode(pin, mode)

    def digital_read(self, uchar pin):
        return self.baseptr.digital_read(pin)

    def digital_write(self, uchar pin, bint value):
        self.baseptr.digital_write(pin, value)

    def analog_read(self, uchar pin):
        return self.baseptr.analog_read(pin)

    def analog_reads(self, uchar pin, uint16_t n_samples):
        return self.baseptr.analog_reads(pin, n_samples)

    def analog_write(self, uchar pin, uint16_t value):
        self.baseptr.analog_write(pin, value)

    def eeprom_read(self, uint16_t address):
        return self.baseptr.eeprom_read(address)

    def eeprom_write(self, uint16_t address, uchar value):
        self.baseptr.eeprom_write(address, value)

    def onewire_address(self, uchar pin, uchar index):
        return self.baseptr.onewire_address(pin, index)

    def onewire_read(self, uchar pin, vector[uchar] address,
                     uchar command, uchar n_bytes):
        return self.baseptr.onewire_read(pin, address, command, n_bytes)

    def onewire_write(self, uchar pin, vector[uchar] address, uchar value,
                      uchar power):
        self.baseptr.onewire_write(pin, address, value, power)

    def i2c_write(self, uchar address, vector[uchar] data):
        print '[i2c_write]', data
        self.baseptr.i2c_write(address, data)

    def i2c_read(self, uchar address, int bytes_to_read):
        return self.baseptr.i2c_read(address, bytes_to_read)

    def i2c_send_command(self, uchar address, uchar cmd, vector[uchar] data,
                         uchar delay_ms):
        return self.baseptr.i2c_send_command(address, cmd, data, delay_ms)

    def spi_set_bit_order(self, bint order):
        self.baseptr.spi_set_bit_order(order)

    def spi_set_clock_divider(self, uchar divider):
        self.baseptr.spi_set_clock_divider(divider)

    def spi_set_data_mode(self, uchar mode):
        self.baseptr.spi_set_data_mode(mode)

    def spi_transfer(self, uchar value):
        return self.baseptr.spi_transfer(value)

    def set_debug(self, bint debug):
        self.baseptr.set_debug(debug)

    def connected(self):
        return self.baseptr.connected()

    def Connect(self, char* port):
        return self.baseptr.Connect(port)

    def Disconnect(self):
        return self.baseptr.Disconnect()

    def flush(self):
        self.baseptr.flush()
