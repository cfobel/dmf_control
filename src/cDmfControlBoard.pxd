from libcpp.vector cimport vector
from libcpp.string cimport string
from libc.stdint cimport uint16_t, uint32_t


ctypedef unsigned char uchar


cdef extern from "RemoteObject.h":
    cdef cppclass RemoteObject:
        RemoteObject(uint32_t baud_rate, bint crc_enabled, char* class_name)

    cdef extern from "dmf_control_board.h":
        cdef cppclass DmfControlBoard:
            DmfControlBoard()

            uint32_t BAUD_RATE
            uchar SINE
            uchar SQUARE
            uint16_t EEPROM_CONFIG_SETTINGS

            string protocol_name()
            string protocol_version()
            string name()
            string manufacturer()
            string software_version()
            string hardware_version()
            string url()

            vector[uchar] debug_buffer()
            void set_pin_mode(uchar pin, bint mode)

            uchar digital_read(uchar pin)
            void digital_write(uchar pin, bint value)

            uint16_t analog_read(uchar pin)
            vector[uint16_t] analog_reads(uchar pin, uint16_t n_samples)
            void analog_write(uchar pin, uint16_t value)

            uchar eeprom_read(uint16_t address)
            void eeprom_write(uint16_t address, uchar value)

            vector[uchar] onewire_address(uchar pin, uchar index)
            vector[uchar] onewire_read(uchar pin, vector[uchar] address,
                                         uchar command, uchar n_bytes)
            void onewire_write(uchar pin, vector[uchar] address,
                               uchar value, uchar power)

            void i2c_write(uchar address, vector[uchar] data)
            vector[uchar] i2c_read(uchar address, uchar n_bytes_to_read)
            vector[uchar] i2c_send_command(uchar address, uchar cmd,
                                             vector[uchar] data,
                                             uchar delay_ms)
            void spi_set_bit_order(bint order)
            void spi_set_clock_divider(uchar divider)
            void spi_set_data_mode(uchar mode)

            uchar spi_transfer(uchar value)

            void set_debug(bint debug)
            bint connected()
            uchar Connect(char* port) except +
            uchar Disconnect()
            void flush()
