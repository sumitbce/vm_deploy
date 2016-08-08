===========================================================
CLI-based DC, FTD & Sensor VM Installer Script
===========================================================
This script helps with installing the DC, FTD & Sensor VMs to vSphere environments. Currently works only from Linux or MAC system.
 
Basic usage is explained below: 

Usage: ./install_vm.py [-n <build-number>] [-b branch] [-i <instance(s)>] -f <conf_file>
	- Use the -n parameter to override the build number specified in conf file. Otherwise the latest build from the
	  branch will be picked up
	- Use the -b parameter to override the branch name specified in conf file. For GOLD branch, just specify GOLD. The
	  HEAD builds will use DRAMBUIE_INTEG tags.
    - Use the -r parameter to override the version specified in conf file
	- Use the -i parameter to install a particular vm specified in config file as section vm.<instance_name>.  
      You can skip this option to install all vm instances in the config file or specify a comma separated list
	- Use the -f to specify configuration file(s) to use, if not specified vm_install.conf is looked in current 
      directory or where the vm_install.py is located

e.g. 
To install all the VMs defined in mypod.conf, with latest build for the branch and release configure in the configuration file
    ./install_vm.py -f mypod.conf 
To install vm named fp21 defined in the bgl020-pod.conf, with latest build
    ./install_vm.py -f sample-conf/bgl020-pod.conf -i fp21
To install vm named dc and fp1, from DRAMBUIE_INTEG branch build# 10861 overridng the values specified in mypod.conf
    ./install_vm.py -f mypod.conf -i fp1,dc -b DRAMBUIE_INTEG -n 10861
To install vm named dc, from EC_VPN branch and version 6.1.0 overriding the values specified in mypod.conf
     ./install_vm.py -f mypod.conf -i dc -b EC_VPN -r 6.1.0
To install vm in profile UM11 defined in the bgl020-pod.conf
    ./install_vm.py -f sample-conf/bgl020-pod.conf -p UM11
To install vm name dc, with multiple conf file, where my_gcp_pod.conf has just vcenter details, my_vm_topo.conf has 
details of vm and my_drambuie.conf has image server, branch etc. details 
    ./install_vm.py -f my_gcp_pod.conf,my_vm_topo.conf,my_drambuie.conf -i dc
    
For detailed usages run ./install_vm.py -h

The script has been tested against a couple of vSphere servers including VMFarm3, smx-vcenter, GCP PODs.
Sample configuration files for each env are in 'sample-conf' folder.

===========================================================
How to Install this script
===========================================================
- Install ovftool on your system. It can be downloaded from VMWare site or
  following local servers - http://kumarg-vdi.cisco.com/files/ovftool-bin/ and
  \\10.106.134.200\downloads\Softwares\VMWare\Tools
- Create a directory e.g. install-vm
- Copy install_vm.py and install_vm_default.conf
- From sample-conf copy the required sample config and change to suite your
  requirement
- That's all now you can run the script

===========================================================
Defining VM instances
===========================================================
- In the configuration file you can add section name starting with 'vm.', the
  suffix following that will be the ID for VM. You can install specific vm
  instance by specifying the VM ID following the '-i' option as comma separted
  list
- For your VM instance defintion, you must define the vm.type which can be
  dc, fp or td.
- Your VM instance section inherits options/properties from [default.vm.<vm.type>] which
  inherits from [default.vm]. Some basic default of these sections are
  configured in install_vm_default.conf. Which can be overridden in your user
  defined conf file
Example - 
-----------------------------------
[vm.dc11]
vm.type=dc
prop.ipv4.addr=192.168.0.11

[vm.td26]
vm.type=td
vm.suffix=-(transparent)
net.GigabitEthernet0-0=BGL0020-B-1574
net.GigabitEthernet0-1=BGL0020-D-1576
prop.firewallmode=transparent
prop.ipv4.addr=192.168.0.26

[vm.td27]
vm.type=td
prop.ipv4.addr=192.168.0.27

-----------------------------------



===========================================================
Defining Profiles
===========================================================
You can have set of VMs create as a profile and specify just profile name to
the script, e.g. 
./install_vm.py -f sample-conf/bgl020-pod.conf -p UM11

To create profile add a section with profile as prefix. Say you want to create
profile HASetup, with one FMC, two FTD - 
-----------------------------------

[profile.HASetup]
vm.instances=dc11,ftd27,td28

-----------------------------------

Note that VM instances should be defiend already.
In future profile may refer other configuration like vCetner, install server
locations etc.


===========================================================
Configuration File Organization
===========================================================
All configuraiton option resolution happens by looking the following files in
the same order -
1) ~/.install_vm_secret.conf [optional]
2) install_vm_default.conf   [must]
3) user defined conf file passed with '-f' argument

Some of the options in conf file can be overridden from cli, e.g. branch,
version, build_number etc. For more see the help for the command.

===========================================================
Sections and Options in Vm Install Configuration file
===========================================================
[install_images] - Defines the details from where the ovf images will be
                   picked
    
[ovftool]       - ovftool related options 

[vCenter]       - vCenter related options


===========================================================
How TOs
===========================================================
How to store the vCenter password
-----------------------------------------------------
This tool support storing vCenter access password in plain text, so that
you don't have to enter it every time you run the command, or if you want
auto execute the script.

You can create a file ~/.install_vm_secret.conf, and add following - 
-----------------------------------

[vCenter]
password=<PASSWORD>

-----------------------------------





===========================================================
Support
===========================================================
If you have any trouble with the script, please feel free to email the following folks:
- Kshitij Gupta (kshgupta)
- Kumar Gopalakrishnan (kumarg)
- Vikas Sharma (vsharma2)


