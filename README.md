# ardopctl
Hooks ardop into rigctld, so that PTT key up and key down commands  are managaged by hamlib, and allows each TNC specified in (g)ARIM ini file to select a frequency for the radio.

usage: ardopctl.py [-h] [-r RIGCTLD] [-t PTT_TIMEOUT] [-a ARDOPBIN]

Hooks ardop into rigctld, so that PTT key up and key down commands are managaged by hamlib. Enables support for embedded auto-QSY feature configured into garim.ini TNC blocks using RADIOHEX commands. 

The garim.ini file may have multiple TNC blocks defined each specifying different operational frequencies.
RADIOHEX PREFIX 2301 is interpreted as a frequency command, frequency must be 9 decimal digits in Hz, MMMKKKHHH, and padded with trailing 'f' chars to length 14. Thus a single frequency may be specified in each TNC block using
statements like these: 

  "tnc-init-cmd = RADIOHEX = 2301003606000f" 
  
  
or


  "tnc-init-cmd = RADIOHEX = 2301007056000f"

optional arguments:

  -h, --help            show this help message and exit
  
  -r RIGCTLD, --rigctld RIGCTLD
  
                        "host:port" for rigctld (default: 127.0.0.1:4532)
                        
  -t PTT_TIMEOUT, --ptt_timeout PTT_TIMEOUT
  
                        ptt hang timeout in seconds, triggers SIGINT, commands
                        
                        PTT Off and abort (default: 60.0)
                        
  -a ARDOPBIN, --ardopbin ARDOPBIN
  
                        path to ardop executable. if not provided, ardop must
                        be spawned/killed manually using (as a minimum)
                        options as printed by ardopctl. May be useful when
                        running ardop in gdb. (default: nothing)

