#!/bin/bash 

pwdir=`pwd`

source install-script-source/install-template.sh
# source /users/PZS0645/support/share/install-script/install-template.sh

VERIFY_FILES="
cheetah/bin/cheetah
"

MULTISTEPS="" 
initialize harp 1.0.0

#dependencies modname1/modversion1 modname2/modversion2

find_conda_exists(){
    which conda | grep -o /conda > /dev/null &&  echo 0 || echo 1
}

find_in_conda_env(){
    conda env list | grep -o RUNTIME_ENV> /dev/null && echo 0 || echo 1
}

# [REQUIRED] if MODULE_SETTING is not only
obtain_src() {
  # Download your source code in this step
  # You can use the variable `dldir` as the location
  #   to which the files should be downloaded
  # A typical command would look like the following:
  echo ""
}

# [REQUIRED] if MODULE_SETTING is not only
setup_step() {
  # Any steps to process the files obtained in `obtain_src`
  #   before they are ready to be configured
  # The variable `srcdir` contains the location where
  #   the ready-to-configure files should be placed
  # For example, if you downloaded a tarball in the `obtain_src` step,
  #   you should probably extract it here
  echo ""
}

# [REQUIRED] if MODULE_SETTING is not only
configure_step() {
  # Any steps required to configure the source code before it can be compiled
  # The `builddir` variable contains the location of a subdirectory of `srcdir`
  #   in which you can build out-of-tree
  # The `installdir` variable contains the location of the final install directory
  # A typical configure command(s) will be similar to the following:
  
  echo "inside configure step 1"
  echo  $installdir
  if [ ! -d "$HOME/miniconda3" ] 
  then 
    echo "conda doesnot exists"
    # wget https://repo.anaconda.com/miniconda/Miniconda3-latest-Linux-x86_64.sh -P $installdir
    wget https://repo.anaconda.com/miniconda/Miniconda3-latest-Linux-x86_64.sh -P $installdir
    bash $installdir/Miniconda3-latest-Linux-x86_64.sh
    echo "conda is installed"
    rm -rf $installdir/Miniconda3-latest-Linux-x86_64.sh
  fi
  source $HOME/miniconda3/bin/activate
  # source $installdir/miniconda3/bin/activate

  echo "installed conda"
  echo $(find_in_conda_env)
  echo "result is above"
  if [ $(find_in_conda_env) == 1 ] 
  then
      echo "conda env doesnot exists"
      conda create --name harp_env python=3.9
  fi
  conda activate harp_env
  echo "conda env activated"
  echo "inside configure step 2"
  # cd $installdir

  cp -r $srcdir/cheetah $installdir
  # cd $srcdir/cheetah 
  cd $installdir/cheetah
  pip install --editable .
  echo "cheetah is configured"

  echo "Installing tensorflow and other dependecies for the pipeline"
  conda install -c anaconda tensorflow-gpu
  conda install -c conda-forge psutil
  conda install pandas
  conda install scikit-learn
  echo "DONE installing tensorflow and other dependecies for the pipeline"

  #Copy Pipeline to install directory
  cp -r $srcdir/pipeline $installdir/
  mkdir $installdir/bin
  cp $srcdir/pipeline/bin/OSC/harp $installdir/bin


}

# [REQUIRED] if MODULE_SETTING is not only
make_step() {
  # Any steps required to build/compile the software
  # A typical build command(s) will be similar to the following:
  echo "make_step"
  #make
}

# [REQUIRED] if MODULE_SETTING is not only
make_install_step() {
  # Any steps required to install the compiled software
  # A typical install command(s) will be similar to the following:
  echo "make_install_step"
  #make install
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
