#!/bin/bash

# This script contains a number of default functions to be sourced at the
# beginning of all install scripts.

export TOP_PID=$$

exit_with_failure() {
  if [[ "$#" != "2" ]]; then
    export FAILURE_STEP="${FUNCNAME[1]}"
  else
    export FAILURE_STEP="$2"
  fi
  kill -s TERM $TOP_PID
}

# Check if template has been modified since last checkout from git repo.
# This file is directly sourced by the install script so we did to make sure no
# dangerous code was inserted into it.
if [ -z "$CLEANED" ]; then
  pushd $(dirname "${BASH_SOURCE[0]}") > /dev/null
  module load git || true
  git diff --quiet $(basename "${BASH_SOURCE[0]}")\
    && echo "Template script validated."\
    || { printf "WARNING!!!\nTemplate script has been modified. Make sure that any modifications have been checked in.\n"; exit_with_failure; }
  popd > /dev/null
fi

if [[ "$CLEANED" != "1" ]]; then mode=""; fi
while [[ $# -gt 0 ]]
do
  key="$1"
  case $key in
    --update-module-default)
      update_default=1
      shift
      ;;
    -h|--help)
      help=1
      shift
      ;;
    -m|--message)
      commit_message=$2
      shift
      shift
      ;;
    --mod-only)
      module_setting="only"
      shift
      ;;
    --mod-test)
      test_module="1"
      shift
      ;;
    --mod-removal)
      remove_module="1"
      shift
      ;;
    --test-only)
      test_only="1"
      shift
      ;;
    *)    # unknown option
      POSITIONAL+=("$1") # save it in an array for later
      shift # past argument
      ;;
  esac
done

if [[ $help == "1" ]]; then
  echo """Usage: $0 [options]

  Available options:
  --update-module-default:
      Force update of default module to current version.
  --mod-test:
      Create a hidden test module. No changes committed to repo.
  --mod-removal:
      Remove non-default module.
  -h|--help:
      This help message.
  """
  exit 1
fi

# By default, the script uses config.cfg next to this file.
if [ -z "$config_file" ] || [ ! -f "$config_file" ]; then
  config_file=$(dirname "${BASH_SOURCE[0]}")/config.cfg
  if [ ! -f "$config_file" ]; then
    echo "ERROR: cannot read config.cfg: $config_file"
    exit 1
  fi
fi

match_file=$(dirname "${BASH_SOURCE[0]}")/configs/match.dat

# Parses the config file.
# Only accepts options listed in match.dat file.
while read -r line
do
  line=$(echo $line | cut -d# -f1)
  line=${line%%#*}
  IFS="=" read -r -a array <<< "$line"
  export ${array[0]}="`eval echo ${array[1]}`"
done < <(grep -f $match_file $config_file)

# The initialize function.
# Sets up a clean environment with properly loaded modules and defined variables.
initialize() {
  # Quit installation if any function returns a non-zero status.
  set -eE
  set -o pipefail
  # Create a clean environment, sets a umask of 002 (-rwXrwXr-X), and purges
  # loaded modules.
  [ -z "$CLEANED" ] && exec /bin/env -i CLEANED=1 \
    commit_message="$commit_message" module_setting="$module_setting" \
    test_module="$test_module" test_only="$test_only" remove_module="$remove_module" \
    config_file=$config_file HOME=$HOME mode=$mode update_default=$update_default project=$project \
    /bin/bash "$0" "$@"
  source /etc/profile || true
  umask 002
  module purge

  # Parses the filename of the installation script.
  # We assume that all installation scripts are of the form install-osc_${suff}.sh.
  scriptname=`basename "$0"`
  sname=${scriptname%.*}
  if [[ "$sname" != "install-osc"* ]]; then
    echo "Error: Installation script name must start with install-osc"
    exit 1
  fi
  srcdir=`pwd`
  suff=${sname#*_}
  # Generate the name of the logfile based on the name of the install script
  # and current date/time.
  logfile=$srcdir/${sname}_$(date +"%Y%m%d_%H%M%S").log
  # Print starttime to logfile
  starttime=`date +%s`
  echo "Begin at `date`" | tee -a $logfile
  # Determine the name and version of the package along with its dependencies
  # by parsing the inputs to the initialize function.
  # This initialize function should be called as `initialize pkgname pkgversion`
  if [ ! -z "${project+x}" ]; then
    module load $project
  fi
  if [ "$#" -ne 2 ]; then
    echo "initialize takes exactly 2 arguments"
    echo "usage: initialize [pkgname] [pkgversion]"
    exit_with_failure
  fi
  pkgname=${1,,}
  pkgversion=$2
  topinstalldir=$topdir/$pkgname
  moddir=$modtop/$pkgname
  installdir=$topinstalldir/$pkgversion
  export CC=gcc
  export CXX=g++
  export FC=gfortran
  export COMPILER_FAMILY=gnu

  # Parse package version
  pkgmaj=$(echo $pkgversion | cut -d. -f1)
  pkgmin=$(echo $pkgversion | cut -d. -f2)
  pkgpatch=$(echo $pkgversion | cut -d. -f3)
  pkgmajmin=$(echo $pkgversion | cut -d. -f-2)
  pkgbugfix=$(echo $pkgversion | cut -d- -f2)
  # Create a build directory based on the suffix for the install script.
  if [ "$suff" == "$sname" ]; then
    builddir=$srcdir/BUILD
  else
    builddir=$srcdir/BUILD_$suff
  fi
  test_module=${test_module:-0}
  remove_module=${remove_module:-0}
  if [[ "$MODULE_SETTING" != "only" ]] && [[ "$module_setting" != "only" ]]; then
    if [ $remove_module == "1" ] || [ $test_module == "1" ]; then
      echo "ERROR: The --mod-test or --mod-removal option is only valid for module updates." | tee $logfile
      exit_with_failure
    fi
  fi
  # Create a download directory that will contain any archive files for this application.
  dldir=$srcdir/download
  # Determine the path for this application's module file.
  if [ $test_module == "1" ]; then
    modfile=$moddir/.${pkgversion}.lua
  else
    modfile=$moddir/${pkgversion}.lua
  fi
  # If an installation fails, we generate a file called INSTALL_FAILED_${suff}.
  # We check whether a previous installation of this software has failed.
  # If so, we stop this installation here so that the user can delete the file
  # and make appropriate changes to the install script.
  if ls $srcdir/INSTALL_FAILED* 1> /dev/null 2>&1; then
    echo "ERROR: Previous installation failed."
    exit_with_failure
  fi
  # Check that paths and variables are valid.
  if [ ${#topinstalldir} -lt $installdirlen ] || [ ${#pkgname} -lt 1 ] || [ ${#pkgversion} -lt 1 ]; then
    (
    echo "  pkgname = $pkgname"
    echo "  pkgversion = $pkgversion"
    echo "  topinstalldir = $topinstalldir (less than $installdirlen)"
    echo "Check paths - Something doesn't look right."
    ) | tee $logfile
    exit_with_failure
  fi

  # Assume that the path of the install script contains the name and version of
  # the application.
  pkgversion_wo_suff=${pkgversion%-*}

  echo "Installation log file for $pkgname version $pkgversion" >> $logfile
  echo "Installing to $installdir" >> $logfile
  uname -a >> $logfile
  lscpu >> $logfile

  # If we are installing a new application, make the top-level install directory
  if [ ! -d $topinstalldir ]; then
    mkdir -p $topinstalldir
  fi
  extract_and_emit_compiler_versions
}

# This function loads additional module dependencies.
# If any of the dependencies have not been installed, print an error message
# and quit.
dependencies() {
  for dep in $@; do
      module load $dep &> /dev/null || { echo "$dep cannot be loaded (verify that it has been installed)."; exit_with_failure; }
  done
}

# This function performs post-processing for the installation.
finalize() {
  # Delete the build directory.
  rm -rf $builddir
  # If a modulefile was generated, update the cache and make sure that basic
  # tests pass.
  # If tests pass, commit and push changes to the modulefile to the repo.
  if [[ "$update_default" == "1" ]]; then
    pushd $moddir > /dev/null
    rm default
    ln -s ${pkgversion}.lua default
    popd
  fi
  pushd $srcdir >> /dev/null
  # Print time that installation finished and total execution time.
  endtime=`date +%s`
  echo "Finished at `date`" | tee -a $logfile
  runtime=$((endtime-starttime))
  echo "Execution time: $runtime seconds" | tee -a $logfile
  popd > /dev/null
}

# Extracts the C and Fortran compiler versions.
# Assumes these global variables are already defined: COMPILER_FAMILY, CC, CXX,
# FC.
# These variables are defined: cc_version, cc_version_major, cc_version_minor,
# cc_version_patch, fc_version, fc_version_major, fc_version_minor,
# fc_version_patch.
extract_and_emit_compiler_versions() {
  veropt="-v"
  if [[ "$COMPILER_FAMILY" == "pgi" ]]; then
    veropt="--version"
  fi
  # C
  if [ -z "`which $CC 2> /dev/null`" ]; then
    echo "Error: $CC could not be found!"
    exit_with_failure
  fi
  # select the line containing the version and extract the version numbers;
  # explicitly remove words that may contain digits.
  cc_version=`$CC $veropt 2>&1 | grep -E "$CC |[vV]ersion " \
    | sed -e 's/Open64//' -e 's/^[a-zA-Z :]* //' -e 's/ .*//'`
  if [ -z "$cc_version" ] ; then
    # DRR - Last ditch; compiler name may not be in version string so just
    #       try to get a number that looks like X.X
    cc_version=`$CC $veropt | grep -o -E "[0-9]*\.[0-9]"`
  fi
  if [ -z "$cc_version" ] ; then
    echo "Error: $CC is not well formed or produces unusual version details!"
    echo "       Check for a CC environment variable."
    exit_with_failure
  fi
  # use '.' as only field delimiter.
  cc_version=`echo $cc_version | sed -e 's/-/./'`
  cc_version_major=`echo $cc_version | cut -d'.' -f1`
  cc_version_minor=`echo $cc_version | cut -d'.' -f2`
  cc_version_patch=`echo $cc_version | cut -d'.' -f3`

  # Fortran
  if [ -z "`which $FC 2> /dev/null`" ]; then
    echo "Error: $FC could not be found!"
    exit_with_failure
  fi

  # select the line containing the version and extract the version numbers;
  # explicitly remove words that may contain digits.
  fc_version=`$FC $veropt 2>&1 | grep -E "$FC |$CC |[vV]ersion " | sed -e "s@$FC @@" \
    -e 's/Open64//' -e 's/^[a-zA-Z :]* //' -e 's/ .*//'`
  if [ -z "$fc_version" ] ; then
    # DRR - Last ditch; compiler name may not be in version string so just
    #       try to get a number that looks like X.X
    fc_version=`$FC $veropt | grep -o -E "[0-9]*\.[0-9]"`
  fi
  if [ -z "$fc_version" ] ; then
    echo "Error: $FC is not well formed or produces unusual version details!"
    echo "       Check for an FC environment variable."
    echo "       Do not use @ characters in an FC environment variable."
    exit_with_failure
  fi
  # use '.' as only field delimiter.
  fc_version=`echo $FC | sed -e 's/-/./'`
  fc_version_major=`echo $FC | cut -d'.' -f1`
  fc_version_minor=`echo $FC | cut -d'.' -f2`
  fc_version_patch=`echo $FC | cut -d'.' -f3`
}

# Make sure that the source is not re-downloaded if it has been previously
# downloaded.
wget() {
  command wget -nc "$@"
}

exit_with_code() {
  echo "Installation script is complete!!"
  exit $1
}

# Function that is performed when the script exits, regardless of success or
# failure.
on_exit() {
  status=$?
  exit_with_code $status
}

# Function that is performed if the installation fails.
on_failure() {
  # If the installation fails at any point, generate a file called
  # INSTALL_FAILED_${suff}.
  # This file contains the path to the install directory so that the user can
  # determine precisely which installation failed.
  # Then, exit the script.
  if [ ! -z $2 ]; then
    FAILURE_STEP=$2
  fi
  suff=${sname#*_}
  touch $srcdir/INSTALL_FAILED_${suff}_${FAILURE_STEP}
  echo "$installdir" >> $srcdir/INSTALL_FAILED_${suff}_${FAILURE_STEP}
  echo "touch $srcdir/INSTALL_FAILED_${suff}_${FAILURE_STEP}" | tee -a $logfile
  false
  on_exit
}

on_ctrl_c() {
  :
}

# Function that verifies the installation.
# Checks if files specified in VERIFY_FILES are in the install directory.
verify_step() {
  if [ -z "${VERIFY_FILES+x}" ]; then
    echo "VERIFY_FILES not set"
    exit_with_failure
  fi
  for fil in $VERIFY_FILES; do
    if [ ! -f $installdir/$fil ]; then
      echo "$fil not found" | tee -a $logfile
      exit_with_failure
    fi
  done
  echo "Installation verified." | tee -a $logfile
}

# Update or copy network license files over 
# This is a dummy function that can be defined in the install script when needed
update_license() {
  echo "If you need to update or copy a license file, please use update_license()"
}

# Generates a modulefile for this application in the proper location with
# necessary variables to make it generic.
module_file_header() {
  # Check the state of the module directory.
  if [ -d "$moddir" ]; then
    if [ ! -h "$moddir/default" ]; then
      echo "ERROR: No default module file in $moddir!"
      exit_with_failure
    fi
  elif [ -e "$moddir" ]; then
    echo "ERROR: $moddir exists but is not a directory!"
    exit_with_failure
  else
    # If a directory does not exist for this application, create the directory
    # and create a default symlink to this version.
    mkdir -p $moddir
    tmpdir=$moddir
    pushd $moddir > /dev/null
    ln -s ${pkgversion}.lua $moddir/default
    popd > /dev/null
  fi
  # Create the header information for the modulefile.
  cat <<EOF >$modfile
whatis("$(get_whatis_message)")
help([[$(get_help_message)]])

local name = myModuleName()
local fullName = myFileName()

local pkgName = myModuleFullName()
EOF
  if [ $test_module == "1" ]; then
    cat <<EOF >>$modfile
local version = "$pkgversion"
EOF
  else
    cat <<EOF >>$modfile
local version = myModuleVersion()
EOF
  fi
  cat <<EOF >>$modfile

local pkgroot = pathJoin("$topdir", name)
local root = pathJoin("$topdir", name, version)

EOF
}

# Checks if the function is defined for this command and step.
# If it does not exist, look for a generic function for this command.
# If neither exists, exit with an error.
run_or_generic() {
  cmd_name=$1
  step_name=$2
  if [ -n "$(type -t ${cmd_name}_${step_name})" ]; then
    ${cmd_name}_${step_name} 2>&1
  elif [ -n "$(type -t ${cmd_name}_generic)" ]; then
    ${cmd_name}_generic 2>&1
  else
    exit_with_failure ${step_name}
  fi
}

# Get the whatis message for this module.
# If the user does not define a custom message,
# use a default whatis message.
get_whatis_message() {
  if [ -n "$(type -t whatis_message)" ]; then
    echo "$(whatis_message)"
  else
    echo "loads $pkgname"
  fi
}

# Get the help message for this module.
# If the user does not define a custom message,
# use a default help message.
get_help_message() {
  if [ -n "$(type -t help_message)" ]; then
    echo "$(help_message)"
  else
    echo "This module loads $pkgname"
    echo "Configured and installed with modules:"
    echo `module -t list 2>&1`
  fi
}

# Performs the installation.
# Requires that obtain_src, setup_step, configure_step, make_step, and
# make_install_step functions are defined in the install script (if
# MODULE_SETTING is not set to only).
# If MODULE_SETTING is not set to none, then requires that generate_module_file
# function be set.
# Note: If a function must be defined but does not require any action for the
# application, just add one line with the ":" character.
do_install() {
  module list 2>&1 | tee -a $logfile
  if [[ "$@" == "module_only" ]]; then
    echo "WARNING: The module_only argument for do_install will eventually be removed. Please replace with setting MODULE_SETTING=only."
  fi
  if [[ "$@" == "keep_installdir" ]]; then
    echo "WARNING: The keep_installdir argument for do_install will eventually be removed. Please replace with setting KEEP_INSTALLDIR=1."
  fi
  # If MODULE_SETTING=only, then skip installation and just verify installation
  # and generate module.
  if [[ "$@" == "module_only" ]] || [[ "$MODULE_SETTING" == "only" ]] || [[ "$module_setting" == "only" ]]; then
    echo "Skipping installation. Only generating module." | tee -a $logfile
  elif [[ "$test_only" == "1" ]]; then
    echo "Skipping installation and module generation. Only running tests." | tee -a $logfile
  # Otherwise, go through installation steps
  else
    set -x
    # obtain_src should be defined in the install script and downloads
    # any necessary source archives.
    printf "\n(OSC Install Script) Obtaining Source Step\n" | tee -a $logfile
    obtain_src 2>&1 | tee -a $logfile
    printf "\n(OSC Install Script) Obtaining Source Step Finished\n" | tee -a $logfile
    # Creates fresh build directory and cleans the install directory if
    # KEEP_INSTALLDIR is not set to 1.
    rm -rf $builddir
    mkdir -p $builddir
    if [[ "$@" == "keep_installdir" ]] || [[ "$KEEP_INSTALLDIR" == "1" ]]; then
      :
    else
      rm -rf $installdir
    fi
    mkdir -p $installdir
    # setup_step should be defined in the install script and performs any
    # necessary setup steps.
    printf "\n(OSC Install Script) Setup Step\n" | tee -a $logfile
    setup_step 2>&1 | tee -a $logfile
    printf "\n(OSC Install Script) Setup Step Finished\n" | tee -a $logfile
    # configure_step should be defined in the install script and runs
    # the configure command.
    printf "\n(OSC Install Script) Configure Step\n" | tee -a $logfile
    configure_step 2>&1 | tee -a $logfile
    printf "\n(OSC Install Script) Configure Step Finished\n" | tee -a $logfile
    # make_step should be defined in the install script and runs the build
    # step.
    printf "\n(OSC Install Script) Compile Step\n"| tee -a $logfile
    make_step 2>&1 | tee -a $logfile
    printf "\n(OSC Install Script) Compile Step Finished\n"| tee -a $logfile
    # make_install_step should be defined in the install script and runs the
    # install step.
    printf "\n(OSC Install Script) Install Step\n" | tee -a $logfile
    make_install_step 2>&1 | tee -a $logfile
    printf "\n(OSC Install Script) Install Step Finished\n" | tee -a $logfile
    set +x
  fi
  # Verifies that the installation steps produced the expected files in the
  # install directory.
  printf "\n(OSC Install Script) Verify Step\n" | tee -a $logfile
  verify_step
  printf "\n(OSC Install Script) Verify Step Finished\n" | tee -a $logfile
  # Update or copy over network license files 
  printf "\n(OSC Install Script) Updating License File Step\n" | tee -a $logfile
  update_license
  printf "\n(OSC Install Script) Updating License File Step Finished\n" | tee -a $logfile
  # Generate the modulefile if necessary.
  if [[ "$MODULE_SETTING" != "none" ]] && [[ "$test_only" != "1" ]] && [[ "$remove_module" != "1" ]]; then
    printf "\n(OSC Install Script) Generating Module File Step: $modfile\n" | tee -a $logfile
    module_file_header
    generate_module_file
    printf "\n(OSC Install Script) Generating Module File Step Finished\n" | tee -a $logfile
  fi
  if [[ "$@" != "module_only" ]] && [[ "$MODULE_SETTING" != "only" ]] && [[ "$module_setting" != "only" ]]; then
    if [ -n "$(type -t post_step)" ]; then
      printf "\n(OSC Install Script) Post-processing Step\n" | tee -a $logfile
      post_step 2>&1 | tee -a $logfile
      printf "\n(OSC Install Script) Post-processing Step Finished\n" | tee -a $logfile
    fi
  fi
}

# First obtain the source and perform any required setup.
# Then, for each step of the installation, run the full installation procedure as in
# do_install (configure, make, make install).
# After all steps are complete, verify the installation and generate the
# module.
do_install_multistep() {
  module list 2>&1 | tee -a $logfile
  # If MODULE_SETTING=only, then skip installation and just verify installation
  # and generate module.
  if [[ "$@" == "module_only" ]] || [[ "$MODULE_SETTING" == "only" ]] || [[ "$module_setting" == "only" ]]; then
    echo "Skipping installation. Only generating module." | tee -a $logfile
  elif [[ "$test_only" == "1" ]]; then
    echo "Skipping installation and module generation. Only running tests." | tee -a $logfile
  # Otherwise, go through installation steps
  else
    set -x
    # obtain_src should be defined in the install script and downloads
    # any necessary source archives.
    echo "Obtaining source..." >> $logfile
    obtain_src 2>&1 | tee -a $logfile
    # Creates fresh build directory and cleans the install directory if
    # KEEP_INSTALLDIR is not set to 1.
    echo "Setting up..." | tee -a $logfile
    rm -rf $builddir
    mkdir -p $builddir
    if [[ "$@" == "keep_installdir" ]] || [[ "$KEEP_INSTALLDIR" == "1" ]]; then
      :
    else
      rm -rf $installdir
    fi
    mkdir -p $installdir
    # setup_step should be defined in the install script and performs any
    # necessary setup steps.
    setup_step 2>&1 | tee -a $logfile
    for stepname in $MULTI_STEPS; do
      mkdir -p $builddir/$stepname
      # configure_step should be defined in the install script and runs
      # the configure command.
      echo "Configuring $stepname..." | tee -a $logfile
      run_or_generic configure_step $stepname 2>&1 | tee -a $logfile
      # make_step should be defined in the install script and runs the build
      # step.
      echo "Compiling $stepname..."| tee -a $logfile
      run_or_generic make_step $stepname 2>&1 | tee -a $logfile
      # make_install_step should be defined in the install script and runs the
      # install step.
      echo "Installing $stepname..." | tee -a $logfile
      run_or_generic make_install_step $stepname 2>&1 | tee -a $logfile
    done
    set +x
  fi
  # Verifies that the installation steps produced the expected files in the
  # install directory.
  echo "Verifying installation..." | tee -a $logfile
  verify_step
  # Generate the modulefile if necessary.
  if [[ "$MODULE_SETTING" != "none" ]]; then
    echo "Generating module file: $modfile" | tee -a $logfile
    module_file_header
    generate_module_file
  fi
  if [[ "$@" != "module_only" ]] && [[ "$MODULE_SETTING" != "only" ]] && [[ "$module_setting" != "only" ]]; then
    if [ -n "$(type -t post_step)" ]; then
      post_step 2>&1 | tee -a $logfile
    fi
  fi
}

# Set trap functions
trap 'on_failure 0' TERM
trap 'on_failure 1 ${FUNCNAME[0]}' ERR
trap on_ctrl_c INT
trap on_exit EXIT
