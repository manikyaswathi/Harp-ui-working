# README

This repo contains files to help users write short "local install scripts" to
build, install, and manage software in their home directories. Typically, a
user will want to copy `install-osc_sample.sh` and follow the notes within to
get it to download, build, and install the desired software. Some additional
description of the install script and template are provided below, as well as
simple example at the bottom.

If you have questions or need help writing an install script, feel free to
contact [OSC Help](mailto:oschelp@osc.edu).

## Description

`install-template.sh` is a template script with default/"boilerplate" functions
to be sourced at the beginning of all user install scripts.

`install-osc_sample.sh` is an example of an install script that a user would
copy and modify to locally install some software that OSC does not provide.

The expectation is that users will copy `install-osc_sample.sh` and modify it
to suit their needs. Note that by default:
- The download and build directories, as well as the log file, will be placed in the directory from which the install script is run
- The software will be installed into `$HOME/osc_apps/<pkgname>/<pkgversion>` (configurable by making a modified config file)
- The module file will be placed in `$HOME/osc_apps/lmodfiles/<pkgname>/<pkgversion>.lua` (configurable by making a modified config file)

Assuming the default for the module file directory, the user will need to run
`module use $HOME/osc_apps/lmodfiles` in any session in which they want to load
their locally-installed software.

## Command-line options
`-c | --config <config_file>`:  Specify location of non-default config file to be used during installation

## Environment Variables

### Defined by the install script
These environment variables may be optionally defined by the user in the install script and modify the behavior of the template file:
- `MODULE_SETTING`:  if `only`, skip installation and just update the module file; if `none`, then do not generate a module file
- `VERIFY_FILES`:  list of files that must be in the install directory for a valid installation, exit with error if any are missing.
- `KEEP_INSTALLDIR`: if `1`, do not delete install directory at beginning of installation; otherwise, delete install directory 

### Defined by the template
These variables are defined by the template file and can be used by the user in the install script:
- `installdir`: directory where application should be installed
- `srcdir`: directory containing install script, build directory, and log files for application
- `moddir`: directory module file for application should be located
- `modfile`: module file to be created/updated
- `builddir`: directory where application should be built
- `dldir`: directory where files necessary for installation should be downloaded
- `pkgmaj`: major version of application
- `pkgmin`: minor version of application
- `pkgpatch`: patch version of application
- `pkgmajmin`: major and minor version of application
- `pkgbugfix`: bug fix version of application
- `CC`: C compiler
- `CXX`: C++ compiler
- `FC`: Fortran compiler
- `F77`: Fortran77 compiler
- `F90`: Fortran90 compiler
- `COMPILER_FAMILY`: compiler family (i.e., GNU, Intel, or PGI)
- `MPI_CC`: MPI C compiler
- `MPI_CXX`: MPI Fortran compiler
- `MPI_FC`: MPI Fortran compiler

### Defined by config file
These variables are defined by the config file. Several (marked below as UNUSED) are not used for these local installs and are only kept in the config file for the purpose of consistency with our central install scripts.
- `system_name`: UNUSED
- `topdir`: top-level directory for installations (default `~/osc_apps`)
- `modtop`: top-level directory for module files (default `~/osc_apps/lmodfiles`)
- `srctop`: UNUSED (software is downloaded and built in the directory from which the install script is run)
- `update_cache_command`: UNUSED
- `installdirlen`: UNUSED
- `has_facls`: UNUSED
- `add_facls`: UNUSED
A user can copy the provided config file and make changes as needed. In this case, the install script must be run with the `-c|--config` flag:
```
./install-osc.sh -c <path to modified config>
```

## Example

For a simple example of a local installation using an install script, see the `example` subdirectory and the `README.md` within.
