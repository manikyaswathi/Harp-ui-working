#!/bin/bash 
# This is a sample install script which uses the template.
# It is structured assuming the software is built with the typical
#   configure-make-make install pattern, but can be adapted to fit
#   many installation approaches

# Command-line options:
#-c | --config <config_file>:  Specify location of non-default config file to be used during installation.

source /users/PZS0645/support/share/install-script/install-template.sh

# List of files that should be in the install directory
VERIFY_FILES="
bin/some_executable
lib/some_library
"
MODULE_SETTING={none, only, ""} # [OPTIONAL, default is ""]
KEEP_INSTALLDIR={0,1} # [OPTIONAL, default is 0]
MULTISTEPS="step1 step2 step3" # [OPTIONAL, default is ""] use only if installation requires
                               # multiple configure-make-make install steps.

# Replace pkgname with name of the software package
# Replace pkgversion with the version of the sofware package
initialize pkgname pkgversion

# [OPTIONAL] List any additional module dependencies
dependencies modname1/modversion1 modname2/modversion2

# [REQUIRED] if MODULE_SETTING is not only
obtain_src() {
  # Download your source code in this step
  # You can use the variable `dldir` as the location
  #   to which the files should be downloaded
  # A typical command would look like the following:
  wget -P $dldir <url for tar.gz file>
}

# [REQUIRED] if MODULE_SETTING is not only
setup_step() {
  # Any steps to process the files obtained in `obtain_src`
  #   before they are ready to be configured
  # The variable `srcdir` contains the location where
  #   the ready-to-configure files should be placed
  # For example, if you downloaded a tarball in the `obtain_src` step,
  #   you should probably extract it here
  tar xf $dldir/<tar file> -C $srcdir --strip=1
}

# [REQUIRED] if MODULE_SETTING is not only
configure_step() {
  # Any steps required to configure the source code before it can be compiled
  # The `builddir` variable contains the location of a subdirectory of `srcdir`
  #   in which you can build out-of-tree
  # The `installdir` variable contains the location of the final install directory
  # A typical configure command(s) will be similar to the following:
  cd $builddir
  CC=$CC CXX=$CXX FC=$FC F77=$F77 F90=$F90 MPI_CC=$MPI_CC MPI_CXX=$MPI_CXX MPI_FC=$MPI_FC $srcdir/configure --prefix=$installdir
}

# [REQUIRED] if MODULE_SETTING is not only
make_step() {
  # Any steps required to build/compile the software
  # A typical build command(s) will be similar to the following:
  cd $builddir
  make
}

# [REQUIRED] if MODULE_SETTING is not only
make_install_step() {
  # Any steps required to install the compiled software
  # A typical install command(s) will be similar to the following:
  cd $builddir
  make install
}

generate_module_file() {
  # Append application specific commands to generic module
  # The `root` variable will point to the root of your software's
  #   installation directory
  # For many software, you just need to ensure that your software's
  #   `bin` and `lib` directories are on `PATH` and `LD_LIBRARY_PATH`
  #   (the first two commands shown here)
cat <<EOF >>$modfile
prepend_path("PATH", root .. "/bin")
prepend_path("LD_LIBRARY_PATH", root .. "/lib")
prepend_path("LIBRARY_PATH", root .. "/lib")
prepend_path("INCLUDE", root .. "/include")
prepend_path("CPATH", root .. "/include")
prepend_path("FPATH", root .. "/include")
prepend_path("PKG_CONFIG_PATH", root .. "/lib/pkgconfig")
prepend_path("MANPATH", root .. "/share/man")
EOF
}

whatis_message() {
  # Echo text that should be put into whatis message.
  # If not specified, a default whatis message will be used.
  echo -e "\t$pkgname - loads the $pkgname package\n"
  echo -e "\tAdditional information about this package\n"
  echo -e "\tcan be added with additional calls to `echo -e`"
}

help_message() {
  # Echo text that should be put in help message.
  # If not specified, a default help message will be used.
  echo -e "\tHelp message for $pkgname version $pkgversion\n"
  echo -e "\tAdditional information in the help message\n"
  echo -e "\tcan be added with more `echo -e` calls"
}

## [OPTIONAL] These functions are only necessary if MULTISTEPS is defined.
## MULTISTEPS Functions:
configure_step_step1() {
  # Configure step for step1 of MULTISTEPS
  :
}

configure_step_step2() {
  # Configure step for step2 of MULTISTEPS
  :
}

make_step_step1() {
  # Make step for step1 of MULTISTEPS
  :
}

make_step_step2() {
  # Make step for step2 of MULTISTEPS
  :
}

make_install_step_step1() {
  # Make install step for step1 of MULTISTEPS
  :
}

make_install_step_step2() {
  # Make install step for step2
  :
}

configure_step_generic() {
  # Generic configure step, only used if specific function is not defined for a
  # step, i.e step3 in this sample
  :
}

make_step_generic() {
  # Generic make step, only used if specific function is not defined for a
  # step, i.e step3 in this sample
  :
}

make_install_step_generic() {
  # Generic make install step, only used if specific function is not defined for a
  # step, i.e step3 in this sample
  :
}
## End of MULTISTEPS functions

# Perform the installation
do_install

# Perform post-processing
finalize
