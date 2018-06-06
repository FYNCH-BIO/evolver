import RPi.GPIO as GPIO
import time

status = 0

def blink(speed):
    while status:
        GPIO.output(7,True) # Switch on pin 7
        time.sleep(speed)
        GPIO.output(7,False) # Switch off pin 7
        time.sleep(speed)
    print('Done')
    GPIO.cleanup()

def run():
    global status
    print('Start running Evolver')
    GPIO.setmode(GPIO.BOARD) # Use board pin numbering
    GPIO.setup(7, GPIO.OUT) # Setup GPIO Pin 7 to OUT
    status = 1
    blink(1)
	
def stop():
    global status
    print('Stop running Evolver')
    status = 0
