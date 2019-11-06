
### TRex on docker
Run container
```bash
$ docker run -itd --privileged --cap-add=ALL -p 8090:8090 -p 4500:4500 -p 4501:4501 -p 4507:4507 --name trex trexcisco/trex:latest
```
Run TRex server on container
```bash
$ docker exec -d trex sh -c "cd /var/trex/v2.41 ; sudo ./t-rex-64 -i" 
```
### TRex client
Install oracle JDK version 8.
Download and install [trex stateless GUI](https://github.com/cisco-system-traffic-generator/trex-stateless-gui/releases)
```bash
$ java -jar trex-stateless-gui.jar
```

### TRex Resources
- RPC commands
  - https://trex-tgn.cisco.com/trex/doc/trex_rpc_server_spec.html#_rpc_commands_common
  - https://trex-tgn.cisco.com/trex/doc/trex_rpc_server_spec.html#_rpc_commands_stl

### trex_stl_lib pros and cons
- Pros
  - OO
  - Working and fully functional
  - Implements all asynch coomands 
- Cons
  - Java style
  - Using rc instead of try/exception
  - Proprietery logger
  - Not python 2, tested on Python 3.6 and later
  - Way too many decorators up to the point where debug is not fluent.
  - If we can get rid of asynch, will be better

### Requirements
- start trex on remote machine if not running (p3)

