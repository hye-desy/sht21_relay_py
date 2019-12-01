#!/usr/bin/python
import fcntl
import unittest
import time
from datetime import datetime

from relay_lib_seeed import *


DewPoint_alarm = -30

alarm_time = -1
sleeptime = 5

class SHT21:

    # control constants
    _SOFTRESET = 0xFE
    _I2C_ADDRESS = 0x40
    _TRIGGER_TEMPERATURE_NO_HOLD = 0xF3
    _TRIGGER_HUMIDITY_NO_HOLD = 0xF5
    _STATUS_BITS_MASK = 0xFFFC

    # From: /linux/i2c-dev.h
    I2C_SLAVE = 0x0703
    I2C_SLAVE_FORCE = 0x0706

    _TEMPERATURE_WAIT_TIME = 0.086  # (datasheet: typ=66, max=85)
    _HUMIDITY_WAIT_TIME = 0.030     # (datasheet: typ=22, max=29)

    def __init__(self, device_number=1):
        self.i2c = open('/dev/i2c-%s' % device_number, 'r+', 0)
        fcntl.ioctl(self.i2c, self.I2C_SLAVE, 0x40)
        self.i2c.write(chr(self._SOFTRESET))
        time.sleep(0.050)

    def read_temperature(self):    
        self.i2c.write(chr(self._TRIGGER_TEMPERATURE_NO_HOLD))
        time.sleep(self._TEMPERATURE_WAIT_TIME)
        data = self.i2c.read(3)
        if self._calculate_checksum(data, 2) == ord(data[2]):
            return self._get_temperature_from_buffer(data)

    def read_humidity(self):    
        """Reads the humidity from the sensor.  Not that this call blocks 
        for ~30ms to allow the sensor to return the data"""
        self.i2c.write(chr(self._TRIGGER_HUMIDITY_NO_HOLD))
        time.sleep(self._HUMIDITY_WAIT_TIME)
        data = self.i2c.read(3)
        if self._calculate_checksum(data, 2) == ord(data[2]):
            return self._get_humidity_from_buffer(data)

    def close(self):
        """Closes the i2c connection"""
        self.i2c.close()

    def __enter__(self):
        """used to enable python's with statement support"""
        return self

    def __exit__(self, type, value, traceback):
        """with support"""
        self.close()

    @staticmethod
    def _calculate_checksum(data, number_of_bytes):
        """5.7 CRC Checksum using the polynomial given in the datasheet"""
        # CRC
        POLYNOMIAL = 0x131  # //P(x)=x^8+x^5+x^4+1 = 100110001
        crc = 0
        # calculates 8-Bit checksum with given polynomial
        for byteCtr in range(number_of_bytes):
            crc ^= (ord(data[byteCtr]))
            for bit in range(8, 0, -1):
                if crc & 0x80:
                    crc = (crc << 1) ^ POLYNOMIAL
                else:
                    crc = (crc << 1)
        return crc

    @staticmethod
    def _get_temperature_from_buffer(data):
        """This function reads the first two bytes of data and
        returns the temperature in C by using the following function:
        T = =46.82 + (172.72 * (ST/2^16))
        where ST is the value from the sensor
        """
        unadjusted = (ord(data[0]) << 8) + ord(data[1])
        unadjusted &= SHT21._STATUS_BITS_MASK  # zero the status bits
        unadjusted *= 175.72
        unadjusted /= 1 << 16  # divide by 2^16
        unadjusted -= 46.85
        return unadjusted

    @staticmethod
    def _get_humidity_from_buffer(data):
        """This function reads the first two bytes of data and returns
        the relative humidity in percent by using the following function:
        RH = -6 + (125 * (SRH / 2 ^16))
        where SRH is the value read from the sensor
        """
        unadjusted = (ord(data[0]) << 8) + ord(data[1])
        unadjusted &= SHT21._STATUS_BITS_MASK  # zero the status bits
        unadjusted *= 125.0
        unadjusted /= 1 << 16  # divide by 2^16
        unadjusted -= 6
        return unadjusted


class SHT21Test(unittest.TestCase):
    """simple sanity test.  Run from the command line with 
    python -m unittest sht21 to check they are still good"""

    def test_temperature(self):
        """Unit test to check the checksum method"""
        calc_temp = SHT21._get_temperature_from_buffer([chr(99), chr(172)])
        self.failUnless(abs(calc_temp - 21.5653979492) < 0.1)

    def test_humidity(self):
        """Unit test to check the humidity computation using example
        from the v4 datasheet"""
        calc_temp = SHT21._get_humidity_from_buffer([chr(99), chr(82)])
        self.failUnless(abs(calc_temp - 42.4924) < 0.001)

    def test_checksum(self):
        """Unit test to check the checksum method.  Uses values read"""
        self.failUnless(SHT21._calculate_checksum([chr(99), chr(172)], 2) == 249)
        self.failUnless(SHT21._calculate_checksum([chr(99), chr(160)], 2) == 132)

def calDewPoint(t, hr):
    if hr<1e-5:
        hr=1
    tdew=pow(hr/100.,1.0/8.0)*(112+0.9*t) +0.1*t-112

    return tdew


if __name__ == "__main__":

    file_dat=open("output.dat","w")
    temp=0
    hr=0
    dewpoint=0
    
    alarm_lasting_time=0

    try:
        while True:
            with SHT21(1) as sht21:
	        temp=sht21.read_temperature()
                hr=sht21.read_humidity()
                dewpoint=calDewPoint(temp,hr)
                timestamp=datetime.fromtimestamp(time.time()).strftime('%Y %m %d %H:%M:%S ')

                print "%s T: %s, HR: %s, DewPoint: %s" % (timestamp, temp,hr,dewpoint)
		file_dat.write(timestamp+str(temp)+" "+str(hr)+" "+str(dewpoint)+"\n")

        
		'''
                if dewpoint>DewPoint_alarm:
	            alarm_lasting_time=alarm_lasting_time+1
                else:
	            alarm_lasting_time=0

	        if alarm_lasting_time>alarm_time/sleeptime:
#relay_all_off()
		    relay_off(2)
                elif relay_get_port_status(2) is False:
#elif (relay_get_port_status(1) and relay_get_port_status(2)) is False:
#relay_all_on()
		    relay_on(2)
'''

                if dewpoint>DewPoint_alarm and relay_get_port_status(2) is True:
		    relay_off(2)
                elif dewpoint<DewPoint_alarm and relay_get_port_status(2) is False:
		    relay_on(2)
             
                time.sleep(sleeptime)


    except IOError, e:
        relay_all_off()
        print e
    except KeyboardInterrupt:
        relay_all_off()
        print "keyboard interrupt"
