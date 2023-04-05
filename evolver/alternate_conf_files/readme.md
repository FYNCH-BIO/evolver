Server Configuration Files (conf.yml)
===

## Summary

Configuration files (conf.yml) contain the parameters for the server to run.

More complex conf.yml files including 'pre' and 'post' commands are complicated to repeatedly alter, so storing them allows easy switching to files for different purposes.

## Definitions
subcommand = a command added to the command queue when another command is run

An example subcommand:
```
- param: 'od_led'
  value: ['0', '0', '0', '0', '0', '0', '0', '0', '0', '0', '0', '0', '0', '0', '0', '0']
```

'pre' or 'post' command = a list of subcommands to be added to the command queue before or after the main parameter command

'values' = a keyword referencing the current value of a parameter in the conf file (for example, the subcommand) 
```
- param: 'temp'
  value: 'values'
```

'wait' = a special type of subcommand that makes the server pause for that many seconds (for example so that a command can execute)
```
- param: 'wait'
  value: 15
```


## Examples of potential alternate conf files
Calibration conf - broadcast_timing parameter should be low to speed up calibration

Experiment conf - the OD LED might need to be normally off unless OD is read to prevent the light affecting sensors
