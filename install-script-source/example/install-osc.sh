#!/bin/bash 
# This is a simple install script derived from
#   /users/PZS0645/support/share/install-script/install-osc_sample.sh

# Command-line options:
#-c | --config <config_file>:  Specify location of non-default config file to be used during installation.

source /users/PZS0645/support/share/install-script/install-template.sh

VERIFY_FILES="
bin/hello
"

initialize hello 1.0

obtain_src() {
  # A typical script would download the source code in this step
  # e.g. wget -P $dldir <url for tar.gz file>
  # In this case, we have already included the tar file with the example
  #   and just need to move it to the download directory
  mkdir -p $dldir
  cp $pkgname-v$pkgversion.tar.gz $dldir/
}

setup_step() {
  # In most cases, you downloaded a tar file in `obtain_src`
  #   and need to extract it here
  # The extracted source files should be put in `srcdir`
  tar xf $dldir/$pkgname-v$pkgversion.tar.gz -C $srcdir --strip=1
}

configure_step() {
  # In many cases, the only necessary flag for the configure command
  #   will be to set the prefix to `installdir`
  cd $builddir
  $srcdir/configure --prefix=$installdir
}

make_step() {
  cd $builddir
  make
}

make_install_step() {
  cd $builddir
  make install
}

generate_module_file() {
  # Our simple example package builds an shared library
  #   and an executable that links against the shared library
  # So our module file needs to put them on `PATH` and `LD_LIBRARY_PATH`, respectively
cat <<EOF >>$modfile
prepend_path("PATH", root .. "/bin")
prepend_path("LD_LIBRARY_PATH", root .. "/lib")
EOF
}

# Perform the installation
do_install

# Perform post-processing
finalize
