# Local Install Script Example

This directory contains the files to install a very simple "Hello World"
program into your home directory using a user/local install script.

## Example Software

The tar file in this directory contains the source code and build files for a very simple software package. The package builds a single shared library, which defines a "Hello World" function, and a single executable, which links against the library and calls the function.

## Install Script

In this directory you will find the file `install-osc.sh`. It was derived from
```
/users/PZS0645/support/share/install-script/install-osc_sample.sh
```
When you go about trying to "locally" install software, you can start by
copying that sample file and modifying it to suit your purposes. In this case,
we modified:
- The `initialize` command: to have the software name (hello) and version (1.0)
- `VERIFY_FILES`: to check that the `hello` executable is correctly installed
- `obtains_src`, `setup_step`, `configure_step`, `make_step`, and `make_install_step`: to obtain and build our software (in general, you should read the documentation/README included with your software to determine what commands to execute in these steps; it is often some variation on `wget`, `tar`, `./configure --prefix=...`, `make`, `make install`)
- `generate_module_file`: to make the module file set the necessary paths for our executable to function correctly
For most software installs, you will need to make similar modifications to the sample file.

## Installation

To install the `hello` package, copy the entire `example` directory and execute the install script. For example:
```
$ cp ~support/share/install-script/example ~/example -r
$ cd ~/example
$ ./install-osc.sh
[omitted output]
```
This will install the software and module file under `~/osc_apps` (creating the
directory structure if it doesn't exist). You can now use the software by
loading the module:
```
$ module use ~/osc_apps/lmodfiles # execute each session to use all your module files
$ module load hello
$ hello
Hello World!
```

