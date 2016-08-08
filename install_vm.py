#!/usr/bin/env python3

from configparser import *
import getopt 
import os
import re
import sys
import traceback
from datetime import datetime
from urllib.request import Request, urlopen

LIB_PATH = os.path.dirname(os.path.realpath(__file__)) + '/lib'
sys.path.insert(0, LIB_PATH)

# Global variables
BRANCHES = [ 'FC_INTEG', 'EC_INTEG' ]

# Variables will be inserted dynamically
DYNAMIC_VARIABLES = [ 'USERNAME', 'VM_ID', 'VM_TYPE', 'VM_PREFIX', 'VM_SUFFIX', 'VERSION', 'VERSION_SHORT', 'BUILD' ]

# Regx to parse web index pages
# look for a link  + a timestamp  + a size ('-' for dir)
DIR_INDEX_REGX = re.compile('href="([^"]*)".*(..-...-.... ..:..).*?(\d+[^\s<]*|-)')

VIRTUAL_DC_NAME_PART=[ 'Cisco_Firepower_Management_Center_Virtual_VMware-VI' ]
VIRTUAL_3D_NAME_PART=[ 'Cisco_Firepower_NGIPSv_VMware-VI' ]
VIRTUAL_TD_NAME_PART=[ 'Cisco_Firepower_Threat_Defense_Virtual-VI' ]
VIRTUAL_TD_IMG_TYPE = [ 'ova', 'ovf' ]

def usage() :
    description='VM install to vCenter'
    conf_help='Configuration file for Vm install, see the sample vm-install.conf'
    print(description)
    print("""Usage:
        vm_install -f <conf_files> [-n <build-number>] [-b <branch>] [-r <version>] [ -i [all | <vm_instance>] | -l] [-d] [-t] [-v <verbose level>]
            -f specify configuration files for Vm install, see the sample vm-install.conf
            -i specify instance id of vm in the config file 
               If you have a section [vm.fp1], then to install that vm you need pass vm_instance as - fp1
               You can pass multiple instance id as comma separated list after '-i' option
            -p profile name, instead of instance name. If instances pass then instances defined in profile are ignored.
            -b specify the branch name or override what's been specified in conf file               
            -n specify the build-number or override what's been specified in conf file                 
            -r specify the version override what's been specified in conf file
            -d dry run, VMs won't get installed but commands will get verified. Ovf source and target location will get verified. 
            -t keep the temporary files, as of now only downloaded ova is temporary file
            -v specify verbosity level

        Examples-
            To install all the VMs defined in mypod.conf, with latest gold build
                ./install_vm.py -f mypod.conf
            To install  vm named fp1 defined in the mypod.conf, ith latest gold build
                ./install_vm.py -f mypod.conf -i fp1
            To install vm named dc and fp1, from DRAMBUIE_INTEG branch build# 10861 overridng the values specified in mypod.conf
                ./install_vm.py -f mypod.conf -i fp1,dc -b DRAMBUIE_INTEG -n 10861
            To install vm named dc, from EC_VPN branch and version 6.1.0 overriding the values specified in mypod.conf
                ./install_vm.py -f mypod.conf -i dc -b EC_VPN -r 6.1.0

           """)

"""
"""
def run_cmd(cmd, hide_stdout=False):
    if isinstance(cmd, list) and sys.version_info > (2,6):
        import subprocess
        print('Running cmd ' + cmd)
        proc = subprocess.Popen(cmd.split(' '), stdout=subprocess.PIPE, stderr=subprocess.PIPE)
        proc.wait()
        returncode = proc.returncode
    else:
        if hide_stdout:
            cmd += ' > /dev/null 2>&1'
        returncode = os.system(cmd)
    return returncode


""" list_url_index

    Returns: dir_tree -
        [ (name=filename,type='f',date,size),
          ( name=dirname,type='d',date,[<dir_tree> ]),.... 
        ]
    params:
           level - None if you need not limit to any level
    
"""
def list_url_index(url, level=1, filter=None):
    dir_tree = []
    try:
        filter_re = None
        if filter:
            filter_re = re.compile(filter)
        if level:
            level -= 1
       
        if not url.endswith('/'):
            url += '/'
        msg = ""
        with urlopen(url) as response:
               html = response.read().decode('utf-8')
        files = DIR_INDEX_REGX.findall(html)
        dirs = []
        for name, date, size in files:
            type = 'f'
            data = size # size for file and dir_tree for directory
            if name.endswith('/'):
                type = 'd'
                name = name[:-1]
            if filter_re and not filter_re.match(name):
                continue 
            if type == 'd':
                dirs += [name]
                data = []
                if level == None or level > 0:
                    data = list_url_index(url + dir, level, filter)

            dir_tree.append((name, type, date, data))
    except IOError as e:
        print('error fetching %s: %s' % (url, e))
    return dir_tree

def url_exists(url):
    try:
        response = urlopen(url)
        if response.code == 200:
            return 1
        else:
            return 0
    except Exception as e:
        print(e)
        return 0



class InstallImage:

    def __init__(self, base_url, version, branch, build_number, build_type='Development'):
        self.base_url = base_url
        self.version = version
        self.branch_name = branch
        self.build_number = build_number
        self.build_type = build_type

        self.branch = branch
        if branch in [ 'GOLD' ] or build_type in ['Release' ]:
            self.branch = ''
        if build_type == 'Development':
            if self.branch == '':
                index_url = self.base_url + '/Development'
            else:
                index_url = self.base_url + '/Feature/'  + self.branch
        elif build_type == 'Release':
            index_url = self.base_url + '/Release'
        else:
            raise Exception('Error: Incorrect build type.')

        self.index_url = index_url
        # show the information
        self.info()
        #Search the latest build number if we need that 
        if self.build_number == 'latest':
            self.build_number = self.find_latest_build()

    """
    """
    def find_latest_build(self):

        filter_pattern = '^' + self.version + '-(\d+)' 
        if not self.branch == '':
            filter_pattern += '.' + self.branch 
        filter_pattern += '$' 
        
        filter_re = re.compile(filter_pattern)
        sys.stdout.write('Searching for latest build at ' + self.index_url + ' ... ')
        sys.stdout.flush()
        builds = list_url_index(self.index_url, filter=filter_pattern)
        build_numbers = []
        for build in builds:
            build_numbers.append(int(filter_re.match(build[0]).group(1)))
        if len(build_numbers) <= 0:
            print(' failed.')
            print('Error: One of the following is incorrect - ')
            self.info()
            raise Exception('Incorrect configuration or inputs.')
        # debug - print 'Found builds ' + str(build_numbers)
        build_numbers.sort()
        # debug - print 'Found builds sorted' + str(build_numbers)
        latest_bno = str(build_numbers[-1])
        print('found - ' + latest_bno)
        return latest_bno
    
    def _find_vm_image_url(self, vm_type, name_index):
        url_part='virtual-appliance/VMWARE'
        ovf_ext='ovf'
        if vm_type == VmInstall.VM_TYPE_DC:
            name_part = VIRTUAL_DC_NAME_PART[name_index]
        elif vm_type == VmInstall.VM_TYPE_3D:
            name_part = VIRTUAL_3D_NAME_PART[name_index]
        elif vm_type == VmInstall.VM_TYPE_TD:
            name_part = VIRTUAL_TD_NAME_PART[name_index]
            url_part='virtual-ngfw'
            ovf_ext= VIRTUAL_TD_IMG_TYPE[name_index]
        
        version = self.version
        build_number = self.build_number
        branch = self.branch
        image_url = self.index_url
        if branch == '':
            image_url += '/{version}-{build_number}/{url_part}/{name_part}-{version}-{build_number}.{ovf_ext}'
        else:
            image_url += '/{version}-{build_number}.{branch}/{url_part}/{name_part}-{version}-{build_number}.{branch}.{ovf_ext}'
        
        return image_url.format(**locals())

    def find_vm_image_url(self, vm_type):
        for i in range(len(VIRTUAL_DC_NAME_PART) - 1, -1, -1):
            image_url = self._find_vm_image_url(vm_type, i)
            print('Trying if URL exists - ' + image_url)
            if url_exists(image_url):
                return image_url
            print('Error: OVF file not found.')
        raise Exception('Try a build earlier or check if the image naming convention has changed.')

    def info(self):
        print('\tVersion:\t ' + self.version)
        print('\tBranch name:\t ' + self.branch_name)
        print('\tBuild number:\t ' + self.build_number)
        print('\tImage base URL:\t ' + self.index_url)

def urlencode(str):
    """ custom method as we do not want to encode '/' """
    pattern = re.compile('[-_.~/a-zA-Z0-9]')
    encoded = ''
    for c in str:
        o = c
        if not pattern.match(c):
            o = "%{0:02x}".format(ord(c))
        encoded += o
    return encoded

def get_basedir():
    return os.path.dirname(os.path.realpath(__file__))

def get_datadir():
    return get_basedir() + '/data'

def open_file(filename):
    return open(get_basedir() + '/' + filename)

def _get_vm_section(vm_instance):
    return 'vm.' + str(vm_instance)


class VmInstallConfigParser(RawConfigParser):
    
    def __init__(self):
        RawConfigParser.__init__(self)
        #Make the options case sensitive
        self.optionxform = str

    """
        Returns:
            value for the specified sectio and option in the config file

    """
    def get_value(self, section, option, ignore_error=0):
        try:
            return self.get(section, option)
        except NoOptionError as e:
            if ignore_error:
                print('Warning:', e)
                #print(traceback.format_exc())
                return None
            else:
                #print(traceback.format_exc())
                raise Exception('Error: Please define option - ' + option + ' in the section - ' + section)

    def _populate_dynamic_vars(self, dynamic_vars, vm_section):
        for variable in DYNAMIC_VARIABLES:
            if self.has_option(vm_section, variable):
                dynamic_vars[variable] = self.get(vm_section, variable)


    def _expand_vm_value(self, vm_instance, value):
        dynamic_vars = {}
        self._populate_dynamic_vars(dynamic_vars, _get_vm_section(vm_instance))
        if value and len(dynamic_vars) > 0:
            value = value.format(**dynamic_vars)
        return value

    def _get_vm_section_layers(self, vm_instance, vm_type):
        section_layers = [ _get_vm_section(vm_instance), 'default.vm.' + vm_type , 'default.vm' ]
        return section_layers
        
    """
        Returns:    
            value form section vm.<vm_instance> and if not found it will  check default value
    """
    def get_vm_value(self, vm_instance, option, ignore_error=0):
        vm_section = _get_vm_section(vm_instance)
        vm_type = self.get_value(vm_section, 'vm.type', 1)
        if vm_type == None:
            raise Exception('Error: Must define VM type in vm defintion')
        # validate
        if vm_type not in VmInstall.VM_TYPES:
            raise Exception('Error: incorrect vm type - ' + vm_type + '\n' + 'Value should be one of ' + VmInstall.VM_TYPES)
        
        section_layers = self._get_vm_section_layers(vm_instance, vm_type)
        value = self._get_section_overridden_value(option, section_layers, ignore_error)
        value = self._expand_vm_value(vm_instance, value)
        return value


    
    """
        Returns:    
            value form section vm.<vm_instance> and if not found it will  check default value
    """
    def _get_section_overridden_value(self, option, section_layers, ignore_error=0):
        value = None
        error = None
        for section in section_layers:
            try:
                #print "Get [" + section + "]."  + option + " ..."
                value = self.get(section, option)
                return value
            except NoOptionError as e:
                error = e
                #print(traceback.format_exc())

        if error:
            if ignore_error:
                print('Warning:', error)
                #print(traceback.format_exc())
                return None
            else:
                raise Exception('Error:' + error)
                #print(traceback.format_exc())

        return value


    def vm_options(self, vm_instance, filter=None):
        section = _get_vm_section(vm_instance)
        vm_type = self.get_value(section, 'vm.type', 1)
        options = self._get_aggregated_options(section, self._get_vm_section_layers(vm_instance, vm_type))
        
        if filter:
            filtered_options = []
            for option in options:
                if re.match(filter, option):
                    filtered_options.append(option)
            options = filtered_options

        return list(set(options))

    def _get_aggregated_options(self, section, section_layers):
        options = []
        for section in section_layers:
            options.extend(self.options(section))
        return options



class VmInstall:

    VM_TYPE_DC = "dc"
    VM_TYPE_3D = "3d"
    VM_TYPE_TD = "td"
    
    VM_TYPES = [VM_TYPE_DC, VM_TYPE_3D, VM_TYPE_TD]


    def __init__(self, argv):
        os.environ['VM_LOAD_HOME'] = get_basedir()
        self.conf_files = './install_vm.conf'
        self.build_number = None
        self.branch = None 
        self.version = None
        self.vm_list = None
        self.vm_instances = []
        self.keep_temp = False
        self.is_dry_run = 0
        self.debug = 0
        self.esx_ip = None
        self.profile = None
        self.parse_args(argv)

    def parse_args(self, argv):
        try:
            opts, args = getopt.getopt(argv,'dhtf:n:r:b:i:v:p:', ['esx-ip='])
        except getopt.GetoptError:
            usage()
            sys.exit(2)

        for opt, arg in opts:
            if opt == '-h':
                usage()
                sys.exit()
            elif opt == '-d':
                self.is_dry_run = 1
                print('-' * 35 + ' DRY RUN ' +  '-' * 35)
            elif opt in ('-f'):
                self.conf_files = arg
            elif opt in ('-n', ):
                self.build_number = arg
            elif opt in ('-r', ):
                self.version = arg
            elif opt in ('-b', ):
                self.branch = arg
            elif opt in ('-i', ):
                self.vm_list = arg
            elif opt in ('-p', ):
                self.profile = arg
            elif opt in ('-t', ):
                self.keep_temp = True
            elif opt in ('-v', ):
                self.debug = arg
            elif opt in ('--esx-ip'):
                self.esx_ip = arg

    """
        Requires to be called immediately after VmInstall object is created
        It does following - 
            - Locate config files either what user passed or locate vm_install.conf from current working dir or where this script exits.
            - Parse the configuration, identified VMs to be installed.
    """
    def setup(self):
        if self.conf_files:
            self.conf_files = self.conf_files.split(',')
            for conf_file in self.conf_files:
                if not os.path.isfile(conf_file):
                    conf_file = os.path.dirname(__file__) + '/install_vm.conf';
                    if not os.path.isfile(conf_file):
                        raise Exception('Error: File ' + conf_file + ' does not exists. Please specify a valid config file.')
                    else:
                        self.conf_files = [conf_file]
                    
        else:
            print('Error: You must specify a configuration file')
            usage()
            sys.exit(2)

        print("Using configuration(s) " + str(self.conf_files))
        self.config = VmInstallConfigParser()

        self.config.readfp(open_file('install_vm_default.conf' ))

        secret_conf = os.path.expanduser('~/.install_vm_secret.conf')
        conf_files = [secret_conf]
        conf_files.extend(self.conf_files)
        self.config.read(conf_files)

        # Set after parsing
        self.branch = self.get_branch()
        self.version = self.get_version()
        self.build_number = self.get_build_number()

        # Install images
        base_url = None
        if self.config.has_option('install_images', 'url'):
            base_url = self._get_value('install_images', 'url')
        if not base_url:
            host = self._get_value('install_images', 'host')
            basedir = self._get_value('install_images', 'basedir')
            args = {'host': host, 'basedir': basedir}
            base_url = 'http://{host}'
            if basedir:
                base_url += '/{basedir}'
            base_url = base_url.format(**args)
        self.base_url = base_url

        build_type = self._get_value('build', 'build_type',1)
        if not build_type:
            build_type = 'Development'
        self.build_type = build_type

        self.install_image = InstallImage(self.base_url, self.version, self.branch, self.build_number, self.build_type)
        # Get the final build number
        self.build_number = self.install_image.build_number

        # initialize vm_instance configurations
        self.vm_instances = self._get_vm_instances()
 

        if len(self.vm_instances)  == 0:
            raise Exception('No VM instances to install.')
        else:
            print('VMs to be installed - ' + str(self.vm_instances))

        # insert dynamic vm variables as option
        for vm_instance in self.vm_instances:
            vm_section = _get_vm_section(vm_instance)
            for variable in DYNAMIC_VARIABLES:
                value = None
                if 'VM_ID' == variable:
                    if vm_instance.startswith('bulk-vm.'):
                        value = vm_instance[len('bulk-vm.'):]
                    else:
                        value = vm_instance
                elif 'VM_TYPE' == variable:
                    value = self._get_vm_value(vm_instance, 'vm.type')
                elif 'VM_SUFFIX' == variable:
                    value = self._get_vm_value(vm_instance, 'vm.suffix')
                elif 'VM_PREFIX' == variable:
                    value = self._get_vm_value(vm_instance, 'vm.prefix')
                elif 'USERNAME' == variable:
                    value = self.get_username()
                elif 'VERSION' == variable:
                    value = self.get_version()
                elif 'VERSION_SHORT' == variable:
                    value = self.get_version().replace('.','')
                elif 'BUILD' == variable:
                    value = self.build_number
                if not value == None:
                    self.config.set(vm_section, variable, value)
            #special handling for VM_FQDN
            self.config.set(vm_section, 'VM_FQDN', self.get_vm_hostname(vm_instance))

    def _get_vm_instances(self):
        vm_instances = []
        
        if self.profile:
            if not self.config.has_section('profile.' + str(self.profile)):
                raise Exception('Error: Cannot find the profile ' + str(self.profile))
        else:
            self.profile = 'default'
        
        if not self.vm_list:
            if self.config.has_section('profile.' + str(self.profile)):
                print('Using profile ' + str(self.profile))
                self.vm_list = self.config.get_value('profile.' + str(self.profile),'vm.instances')
                # if no instances set then consider all VM instances
                if self.vm_list == '':
                    self.vm_list = 'all'
            # if no profile defined consider all VM instances
            else:         
                self.vm_list = 'all'

        if self.vm_list == 'all':
            for section in self.config.sections():
                if section.startswith('vm.'):
                    self._chk_and_add_vm_instance(section[3:], vm_instances)
        else:
            vm_list = self.vm_list.split(',')
            for item in vm_list:
                if item.startswith('vm.'):
                    # add directly to vm instance after removing 'vm.'
                    self._chk_and_add_vm_instance(item[3:], vm_instances)
                elif item.startswith('bulk-vm.'):
                    vm_type = self.config.get_value(item, 'vm.type')
                    # create vm instances
                    if self.config.has_section(item):
                        vm_count = int(self.config.get_value(item, 'vm.count'))
                        for i in range(0, vm_count):
                            vm_instance = item + '.' + str(i + 1)
                            vm_instances.append(vm_instance)
                            self.config.add_section('vm.' + vm_instance)
                            self.config.set('vm.' + vm_instance , 'vm.type', vm_type)
                    else:
                        print('Warning: bulk-vm config - ' + item[8:] + ' not found.')
                else:
                    self._chk_and_add_vm_instance(item, vm_instances)
        return vm_instances

    def _chk_and_add_vm_instance(self, instance, vm_instances):
        if self.config.has_section('vm.' + instance):
            vm_instances.append(instance)
        else:
            print('Warning: VM instance ' + instance + ' not found. Ignoring and moving ahead.')


    """
        _get_vm_value
        Returns:    
            value form section vm.<vm_instance> and if not found it will  check default value
    """
    def _get_vm_value(self, vm_instance, option, ignore_error=0):
        if vm_instance.startswith('bulk-vm.'):
            return self._get_bulk_vm_value(vm_instance, option, ignore_error)
        else:
            return self.config.get_vm_value(vm_instance, option, ignore_error)


    def _get_bulk_vm_value(self, vm_instance, option, ignore_error=0):
        bulk_vm_section = vm_instance[0: vm_instance.rindex('.')]
        bulk_vm_index = int(vm_instance[vm_instance.rindex('.') + 1:])
        pool_values = self._get_bulk_vm_pool_value(bulk_vm_section, option, ignore_error)
        if pool_values and len(pool_values) > 0:
            return pool_values[bulk_vm_index]
        elif option in ['vm.type', 'vm.name', 'prop.fqdn']:
            return  self.config.get_vm_value(vm_instance, option) 
        else:
            # rest get from base.vm
            base_vm_instance = self.config.get_value(bulk_vm_section, 'bulk-override.base.instance')
            return self._get_vm_value(base_vm_instance, option, ignore_error)

    def _get_bulk_vm_pool_value(self, bulk_vm_section, option, ignore_error=0):
        pool_values = []
        if self.config.has_option(bulk_vm_section, 'bulk-override.pool.' + option):
            pool = self.config.get_value(bulk_vm_section, 'bulk-override.pool.' + option)
            pool_items = pool.split(',')
            for item in pool_items:
                if item.find('-') != -1: # Range provided
                    self._chk_dependency_bulk_vm_pool_range_subnet(option)
                    range_start = item[0:item.rindex('-')]
                    range_end = item[item.rindex('-') + 1:]
                    print('range_start ' + range_start + ' range_end ' + range_end)
                    if option.find('ipv4.addr') != -1:
                        import ipaddress
                        ipv4_range_start  = ipaddress.IPv4Address(range_start)
                        ipv4_range_end =  ipaddress.IPv4Address(range_end)
                        temp_ipv4 = ipv4_range_start
                        while temp_ipv4 <= ipv4_range_end:
                            pool_values.append(str(temp_ipv4))
                            temp_ipv4 += 1
                elif item.find('/') != -1: # Subnet provided
                    print('Warning: subnet are not supported in pools yet')
                    pass # Not supported yet
                else: # indvidual list
                    pool_values.append(item)
        else: # this option doesn't have pool 
            return None
        print('pool_values ' + str(pool_values))
        # check pool size is sufficient
        vm_count = int(self.config.get_value(bulk_vm_section, 'vm.count'))
        if  len(pool_values) < vm_count:
            print('Error: Pool size is not sufficient for option ' + option + ' in bulk-vm config - ' + bulk_vm_section)
            print('VM count in the bulk-vm config is ' + str(vm_count) + ', while pool has only ' + \
                    str(len(pool_values)) + ' items.')
            sys.exit(2)
        return pool_values;
        
                
    def _chk_dependency_bulk_vm_pool_range_subnet(self, option):
        try:
            import ipaddress
        except Exception as e:
            print('Warning: Bulk VM pool doesn\'t support IPv4 address range. You can do one of following - ')
            print(' - Ensure the \'ipaddress\' python module is install, if not install that; or')
            print(' - Use comma separate list in the option ' + option)
            return 0
        return 1


    """
        Returns:
            value for the specified section and option in the config file

    """
    def _get_value(self, section, option, ignore_error=0):
        return self.config.get_value(section, option, ignore_error)

    """
        Get the value if set by cmdline args as member variable named same as option, 
        otherwise get from conf file
    """
    def get_value(self, section, option, ignore_error=0):
        if hasattr(self, option):
            value = getattr(self, option)
            if value:
                return value
        return self._get_value(section, option, ignore_error)

    def _get_build_number(self):
        return self.build_number if self.build_number else "latest"

    def get_branch(self):
        return self.get_value('build', 'branch')

    def get_version(self):
        return self.get_value('build', 'version')

    def get_build_number(self):
        return self.get_value('build', 'build_number')

    def get_esx_ip(self):
        return self.get_value('vCenter','esx_ip')

    def get_seed_build_number(self):
        build_number = 0
        lines = tuple(open_file("seedBuild-" + self.get_branch() + ".txt"))
        return lines[0][:-1]

    def get_ovf_url(self, vm_instance):
        section = _get_vm_section(vm_instance)
        vm_type = self._get_value(section, 'vm.type', 1)
        return self.install_image.find_vm_image_url(vm_type)
        
    def get_source_loc(self, vm_instance):
        ovf_url = self.get_ovf_url(vm_instance)
        tmp_dir = get_basedir() + '/tmp'
        ova_file = os.path.abspath(tmp_dir + '/' + ovf_url[ovf_url.rfind('/'):])
        ovf_file = ova_file[0:-1] + 'f'

        force_esxi4_compatibility = self._get_value('vCenter', 'ovf.esxi4.compatiblity.force')
        if ovf_url and ovf_url[-3:] == 'ova' and self._get_value('install_images', 'extract_ova') in ['true', 'yes', 1 ]:
            args = { 'tmp_dir' : tmp_dir, 'ovf_url' : ovf_url, 'ova_file' : ova_file, 'ovf_file': ovf_file }

            if not os.path.isfile(ova_file):
                run_cmd('mkdir -p {tmp_dir} && cd {tmp_dir} && wget {ovf_url}'.format(**args))

            if not os.path.isfile(ovf_file):
                print('Extracting ova ...')
                run_cmd('cd {tmp_dir} && tar xf {ova_file}'.format(**args), hide_stdout=True)

            ovf_url = 'file://' + ovf_file
        
        if force_esxi4_compatibility and force_esxi4_compatibility in ['true', 'yes', 1]:
            returnval = run_cmd('grep -n "<vssd:VirtualSystemType>.*vmx-07.*</vssd:VirtualSystemType>" ' + ovf_file, hide_stdout=True)
            if returnval != 0:
                sys.stdout.write('OVF file ' + ovf_file + ' is not ESXi 4.x compatible, changing it ...')
                returnval = run_cmd('sed -i s/\<vssd:VirtualSystemType\>/\<vssd:VirtualSystemType\>vmx-07,/g ' + ovf_file, hide_stdout=True)
                if returnval == 0:
                    run_cmd('openssl sha1 ' + ovf_file + ' > ' + ovf_file[0:-3] + '.mf')
                    print(' done.')
        return ovf_url

        
    def get_username(self):
        user =  self._get_value('vCenter', 'user')
        if '\\' in user:
            user = user.split('\\')[1]
        return user

    def get_vm_name(self, vm_instance):
        name = self._get_vm_value(vm_instance, 'vm.name')
        if not name:
            name = self.config._expand_vm_value(vm_instance, '{USERNAME}-{VM_ID}-{VERSION}-{BUILD}{VM_SUFFIX}')
        return name

    def get_vm_hostname(self, vm_instance):
        return self.config._expand_vm_value(vm_instance, '{VM_ID}-v{VERSION_SHORT}b{BUILD}')



    def get_vi_path(self):
        host_cluster = self.get_value('vCenter', 'esx_ip')
        if host_cluster == None or host_cluster == '':
            host_cluster = self._get_value('vCenter', 'cluster_path')
        args = {'vcenter_dc': self._get_value('vCenter', 'datacenter'), 
                'vcenter_cluster_path': host_cluster,
                'vcenter_respool' : self._get_value('vCenter', 'resource_pool')}
        vi_path = "{vcenter_dc}/host/{vcenter_cluster_path}/Resources/{vcenter_respool}".format(**args)
        return urlencode(vi_path)


    def get_vi_url(self):
        args = {'vcenter_user': urlencode(self._get_value('vCenter', 'user')),
                'vcenter_pwd': urlencode(self._get_value('vCenter', 'password')),
                'vcenter_host': self._get_value('vCenter', 'host') }
        vi_url = "vi://{vcenter_user}:{vcenter_pwd}@{vcenter_host}/".format(**args)  + self.get_vi_path()
        return vi_url


    
    """ 
    Returns 
    params: 
        vm_instance:  
    """
    def get_ovftool_args(self, vm_instance):
        args = { 'vm_name': self.get_vm_name(vm_instance),
                 'vm_poweron' : ('', '--powerOn')[self._get_vm_value(vm_instance, 'poweron') in ['true', 'yes', 1]],
                 'vm_overwrite': ('', '--overwrite') [self._get_vm_value(vm_instance, 'overwrite') in ['true', 'yes', 1]],
                 'base_args': self._get_value('ovftool', 'base_args'),
                 'verify_only': ('', '--verifyOnly')[self.is_dry_run],
                 'folder': self._get_value('vCenter', 'folder'),
                 'datastore': self._get_value('vCenter', 'datastore'),
                 'net_options': self.get_ovf_net_options(vm_instance),
                 'ovf_props': self.get_ovf_props(vm_instance),
                 'source_loc': self.get_source_loc(vm_instance),
                 'target_loc': self.get_vi_url()
                 }
                 
        ovf_options = '{base_args} {vm_overwrite} {vm_poweron} {verify_only}'  \
                      ' -dm=thin --name="{vm_name}" --vmFolder="{folder}" --datastore="{datastore}"'  \
                      ' {net_options} {ovf_props} {source_loc} {target_loc}'.format(**args)
        return ovf_options


    def _build_options(self, vm_instance, option_type, exclude_options=[]):
        vm_type = self._get_vm_value(vm_instance,'vm.type')
        vm_options = self.config.vm_options(vm_instance, '^' + option_type + '\.')
        vm_options = list(set(vm_options) - set(exclude_options))
        args = {}
        ovf_options = ''
        for vm_option in vm_options:
            option_name = vm_option[len(option_type) + 1:]
            option_value = self._get_vm_value(vm_instance, vm_option)
            ovf_options += ' --' + option_type + ':"' +  option_name + '"="' + option_value + '"'
        return ovf_options


    """ 
    Returns 
    params: 
        vm_instance:  name of the vm instance from config file 
    """
    def get_ovf_props(self, vm_instance):
        ipv4_how = self._get_vm_value(vm_instance,'prop.ipv4.how',ignore_error=1)
        

        exclude_options = []
        if ipv4_how and ipv4_how.lower() == 'manual':
            exclude_options = ['ipv4.addr', 'ipv4.mask', 'ipv4.gw', 'dns1' , 'dns2', 'dns3']

        return self._build_options(vm_instance, 'prop', exclude_options)

    """ 
    Returns ovf net options string
    params: 
        vm_instance:  
    """
    def get_ovf_net_options(self, vm_instance):
        return self._build_options(vm_instance, 'net')

    def hide_sensitive_data(self, cmd):
        password = urlencode(self._get_value('vCenter', 'password'))
        return cmd.replace(password,'XXXX')


    """ Install the vm for the given vm_instance id """
    def _install_vm(self, vm_instance, show_cmd=0):
        print('Deploying VM ' + vm_instance + ' ...')
        start_time = datetime.now().replace(microsecond=0)
        args = { 'ovf_args' : self.get_ovftool_args(vm_instance),
                 'ovftool_cmd': self._get_value('ovftool', 'path')}
        cmd = '{ovftool_cmd} {ovf_args}'
        cmd = cmd.format(**args)
        if show_cmd:
            print(self.hide_sensitive_data(cmd))
        run_cmd(cmd) 
        end_time = datetime.now().replace(microsecond=0)
        deploy_time = end_time - start_time
        print('VM ' + vm_instance + ' deployed in ' + str(deploy_time))

    def install_vm(self, show_cmd=0):
        for vm_instance in self.vm_instances:
            # using verify only option 
            try:
                self._install_vm(vm_instance, show_cmd)
            except:
                print('Error while deploying VM ' + vm_instance)

    
    def create_snapshot(self):
        # Take snapshot of the VM deployed
        vm_pattern = self.get_username() + '-*' + self.build_number
        os.system("./vm_deploy.py -action snapshot -vm " + vm_pattern)

    def cleanup(self):
        # cleanup the extracts of ova
        args = { 'tmp_dir' : get_basedir() + '/tmp' }
        run_cmd('rm -f {tmp_dir}/*.ova && rm -f {tmp_dir}/*.ovf && rm -f ./tmp/*.vmdk'.format(**args), hide_stdout=True)

    def check_dependency(self):
        check_pass = True
        ovftool = self._get_value('ovftool', 'path')
        cmd = 'which ' + ovftool
        returncode = 0
        if ovftool.find('/') < 0:
            returncode = run_cmd(cmd, hide_stdout=True)
        else:
            #TODO: in case of relative or absolute path is used
            # if exists with exec permission
            pass

        if returncode != 0:
            print('Error: ovftool not found in system path, please install ovftool')
            print('       Or correct the ovftool path in ovftool section')
            print('You can download ovftool from vmware.com or http://kumarg-vdi.cisco.com/files/ovftool-bin/')
            check_pass = False

        #Require openssl to generate sha1 if when we change ovf
        force_esxi4_compatibility = self._get_value('vCenter', 'ovf.esxi4.compatiblity.force')
        if force_esxi4_compatibility:
            cmd = 'which openssl'
            returncode = run_cmd(cmd, hide_stdout=True)
            if returncode != 0:
                print('Error: openssl not found in system path, please install openssl')
                print('You have set [vCenter].ovf.esxi4.compatiblity.force to 1, ')
                print('if you are not deploying to esxi 4.x, then you can set that to 0.')
                check_pass = False

        # Exit on any failure
        if not check_pass:
            sys.exit(1)

    def get_vcenter_password(self):
        pw = self._get_value('vCenter', 'password', 1)

        if not pw:
            try:
               import password
               self.config.set('vCenter', 'password', password.PASSWORD)
            except:
                None

            if not self._get_value('vCenter', 'password', 1):
                print('You will be prompted for password.')
                print('To avoid prompting you can configure it as plain in the file ~/.install_vm_secret.conf')
                import getpass
                pw = getpass.getpass()
                self.config.set('vCenter', 'password', pw)
        


if __name__ == "__main__":
    if sys.version_info < (3,5):
        raise Exception('Need python 3.5 or higher to run this script')
    vmInstall = None
    try:
        vmInstall = VmInstall(sys.argv[1:])
        
        if vmInstall.debug > 1:
            print('Verbose level set to ', vmInstall.debug)

        vmInstall.setup()
        vmInstall.check_dependency()
        vmInstall.get_vcenter_password()
        vmInstall.install_vm(show_cmd=1)
        vmInstall.create_snapshot()

        if not vmInstall.keep_temp:
            vmInstall.cleanup()

    except Exception as e:
        print(e)
        if vmInstall and vmInstall.debug > 2:
            print(traceback.format_exc())
