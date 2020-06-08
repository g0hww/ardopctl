#!/usr/bin/env python3
# Copyright Darren Long, G0HWW, 2020
# GPLv3 applies.

import socket
import os
import pty
import binascii
import subprocess
import argparse
import sys
import signal
import threading
import time
from datetime import datetime

def ptt_hang_handler():
    print(datetime.now().astimezone().isoformat()+' '+'CAUTION - PTT Failsafe triggered!')
    os.kill(os.getpid(), signal.SIGINT)

if __name__ == '__main__':
    parser = argparse.ArgumentParser(formatter_class=argparse.ArgumentDefaultsHelpFormatter,
                                     description='''
    Hooks ardop into rigctld, so that PTT key up and key down commands
    are managaged by hamlib.
    Enables support for embedded auto-QSY feature configured into garim.ini
    TNC blocks using RADIOHEX commands. The garim.ini file may have multiple TNC
    blocks defined each specifying different operational frequencies.
    RADIOHEX PREFIX 2301 is interpreted as a frequency command,
    frequency must be 9 decimal digits in Hz, MMMKKKHHH,
    and padded with trailing 'f' chars to length 14.
    Thus a single frequency may be specified in each TNC block using statements
    like these: "tnc-init-cmd = RADIOHEX = 2301003606000f" or
    "tnc-init-cmd = RADIOHEX = 2301007056000f"''')

    parser.add_argument('-r','--rigctld', dest='rigctld', type=str,
                        help='"host:port" for rigctld', action="store",
                        default='127.0.0.1:4532')
    parser.add_argument('-t','--ptt_timeout', dest='ptt_timeout', type=float,
                        help='ptt hang timeout in seconds, triggers SIGINT, commands PTT Off and abort', action="store",
                        default='60.0')
    parser.add_argument('-a','--ardopbin',type=str,
                        help='path to ardop executable. if not provided, ardop must be spawned/killed manually \
                        using (as a minimum) options as printed by ardopctl.\n May be useful when running ardop in gdb.',
                        action="store", default='')
    args = parser.parse_args()

    # Connect a TCP socket to rigctld
    sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    rigctld = args.rigctld.split(':')
    rigctld_host = rigctld[0]
    rigctld_port = int(rigctld[1])
    server_address = (rigctld_host, rigctld_port)
    print(datetime.now().astimezone().isoformat()+' '+'Connecting to rigctld at {} port {}'.format(rigctld_host, str(rigctld_port)))
    try:
        sock.connect(server_address)
    except ConnectionRefusedError as e:
        print(datetime.now().astimezone().isoformat()+' ERROR - failed to connect to rigctld. Is it running?')
        sys.exit(-1)
    print(datetime.now().astimezone().isoformat()+' '+'Connected.')
    # set up a pty for ardop to connect to
    master,slave = pty.openpty() # open the pseudoterminal
    s_name = os.ttyname(slave) # translate the slave fd to a filename
    print(datetime.now().astimezone().isoformat()+' '+'Reading from PTY device: '+s_name)
    # rigctld should respond with this when command succeeds
    expected_res = b'RPRT 0\n'
    # base prefix for custom commands that will be sent to ardop from gARIM
    cmd_prefix_len = len(b'f02300')
    cmd_entire_len = len(b'f023000000000000')
    qsy_prefix = b'f02301'
    # PTT On hex
    ptt_on     = b'f023020000000000'
    # PTT Off hex
    ptt_off    = b'f023030000000000'
    # spawn ardop bin and kill it on exit, if option provided,
    # otherwise print options that must be passed to ardop when run manually
    if args.ardopbin != '':
        # spawn the ardop process, telling it to communicate via the PTY device
        # and tell it which hex commands to use for PTT on/off
        print(datetime.now().astimezone().isoformat()+' '+'Spawning '+args.ardopbin)
        proc = subprocess.Popen([args.ardopbin,
                                 '-c', s_name,
                                 '-k', ptt_on.decode('utf-8'),
                                 '-u', ptt_off.decode('utf-8')],
                                stdout=open(os.devnull, 'w'),
                                stderr=open(os.devnull, 'w'))
    else:
        proc = None
        print(datetime.now().astimezone().isoformat()+' User must spawn ardop process manually, using following options (as a minumum) ...')
        print('\t-c '+s_name+':19200 -k '+ptt_on.decode('utf-8')+' -u '+ptt_off.decode('utf-8'))

    print(datetime.now().astimezone().isoformat()+' '+'Ready')
    ptt_failsafe = None
    try:
        # ensure PTT is off when we start
        sock.sendall(b"T 0\n")
        res = sock.recv(len(expected_res))
        if res != expected_res:
            raise ValueError('rigctld command failed with result:'+res.decode('utf-8'))
        while(True):
            check_res = True
            input = binascii.hexlify(os.read(master,cmd_entire_len))
            print(datetime.now().astimezone().isoformat()+' ', end='')
            if input == ptt_on:
                sock.sendall(b"T 3\n")
                print('PTT On')
                if ptt_failsafe == None:
                    ptt_failsafe = threading.Timer(args.ptt_timeout, ptt_hang_handler)
                    ptt_failsafe.start()
            elif input == ptt_off:
                sock.sendall(b"T 0\n")
                print('PTT Off')
                if ptt_failsafe != None:
                    ptt_failsafe.cancel()
            elif input[:cmd_prefix_len] == qsy_prefix: # qsy cmd
                freq = input[cmd_prefix_len:].rstrip(b'f')
                qsy = b"F "+freq
                print('QSY:'+str(float(int(freq))/1000000.0)+'MHz')
                sock.sendall(qsy+b'\n')
            else:
                print('UNKNOWN COMMAND')
                check_res = False
            if check_res:
                res = sock.recv(len(expected_res))
                if res != expected_res:
                    raise ValueError('rigctld command failed with result:'+res.decode('utf-8'))
    except KeyboardInterrupt as e:
        print('')
    except ValueError as e:
        pass
    finally:
        if ptt_failsafe != None:
            ptt_failsafe.cancel()
        sock.close()
        if proc != None:
            print(datetime.now().astimezone().isoformat()+' '+'Killing '+args.ardopbin)
            proc.terminate()
        else:
            print(datetime.now().astimezone().isoformat()+' CAUTION - User must terminate ardop process manually.')
        print(datetime.now().astimezone().isoformat()+' '+'Setting PTT Off and exiting')
        try:
            ptt_kill = subprocess.run('rigctl -r {}:{} -m 2 T 0'.format(rigctld_host,str(rigctld_port)),shell=True)
            if ptt_kill.returncode == 0:
                print(datetime.now().astimezone().isoformat()+' '+'PTT set off')
            else:
                print(datetime.now().astimezone().isoformat()+' '+'CAUTION - Manually check PTT state!')
        except:
            print(datetime.now().astimezone().isoformat()+' '+'CAUTION - Manually check PTT state!')
        print(datetime.now().astimezone().isoformat()+' '+'Done.')
