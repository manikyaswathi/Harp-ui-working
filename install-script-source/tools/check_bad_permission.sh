#!/bin/bash

export TOP_PID=$$

exit_with_failure() {
  if [[ "$#" != "2" ]]; then
    export FAILURE_STEP="${FUNCNAME[1]}"
  else
    export FAILURE_STEP="$2"
  fi
  kill -s TERM $TOP_PID
}

# By default, the script uses config.cfg next to this file.
if [ -z "$config_file" ]; then
  config_file=$(dirname "${BASH_SOURCE[0]}")/../config.cfg
fi
match_file=$(dirname "${BASH_SOURCE[0]}")/../configs/match.dat

# Parses the config file.
# Only accepts options listed in match.dat file.
while read -r line
do
  line=$(echo $line | cut -d# -f1)
  line=${line%%#*}
  IFS="=" read -r -a array <<< "$line"
  export ${array[0]}="`eval echo ${array[1]}`"
done < <(grep -f $match_file $config_file)

srcdir=`pwd`

pkgname=${1,,}
pkgversion=$2
argind=3

deps=${!argind,,}
argind=$((argind+1))
topinstalldir=$topdir/$pkgname
dep_str=""
if [ "$deps" == "compiler" ]; then
  compiler=${!argind,,}
  argind=$((argind+1))
  compver=${!argind}
  argind=$((argind+1))
  if [ "$compiler" == "intel" ] || [ "$compiler" == "gnu" ]; then
      compverpath=$(echo $compver | cut -d. -f-2)
  else
      compverpath=$compver
  fi
  dep_str="$deps $compiler/$compver"
  moddir=$modtop/Compiler/$compiler/$compverpath/$pkgname
  installdir=$topinstalldir/$compiler/$compverpath/$pkgversion
elif [ "$deps" == "mpi" ]; then
  mpi=${!argind,,}
  argind=$((argind+1))
  mpiver=${!argind}
  argind=$((argind+1))
  compiler=${!argind,,}
  argind=$((argind+1))
  compver=${!argind}
  argind=$((argind+1))
  if [ "$compiler" == "intel" ] || [ "$compiler" == "gnu" ]; then
    compverpath=$(echo $compver | cut -d. -f-2)
  else
    compverpath=$compver
  fi
  dep_str="$deps $mpi/$mpiver $compiler/$compver"

  if [ "$mpi" == "openmpi" ]; then
    IFS='-' read -r -a verarray <<< "$mpiver"
    mpiverpath=$(echo ${verarray[0]} | cut -d. -f-2)
    if [ ! -z "${verarray[1]+x}" ]; then
      mpiverpath+="-${verarray[1]}"
    fi
  else
    mpiverpath=$mpiver
  fi
  moddir=$modtop/MPI/$compiler/$compverpath/$mpi/$mpiverpath/$pkgname
  installdir=$topinstalldir/$compiler/$compverpath/$mpi/$mpiverpath/$pkgversion
elif [ "$deps" == "core" ]; then
  moddir=$modtop/Core/$pkgname
  installdir=$topinstalldir/$pkgversion
  dep_str="$deps"
else
  echo "$deps is not a valid dependency"
  exit_with_failure
fi

finalize() {
  # If the system has facls, then check if there are any permission issues.
  # If there are any permission issues, try to fix them using the nfs_setfacl
  # command and verify that permissions are now correct.
  if [ "$has_facls" -eq "1" ]; then
    echo "Permission test start"
    # Check if there are any files/directories with bad permissions
    if grep 'skip_files' <<< "$mode" &> /dev/null ; then
      echo "find $topinstalldir $srcdir $moddir -type d -perm -u+r"
      bad_dirs=$(time find $topinstalldir $srcdir $moddir -type d ! -perm -u+r || true)
    else
      echo "find $topinstalldir $srcdir $moddir ! -perm -u+r"
      bad_dirs=$(time find $topinstalldir $srcdir $moddir ! -perm -u+r || true)
    fi
    # Print all files/directories with bad permissions
    if [ ! -z "${bad_dirs}" ]; then
      ls -ld $bad_dirs || true
      echo "[`date`] $pkgname $pkgversion ($moddir):"
      ls -ld $bad_dirs | tee -a bad_dirs || true
      if [ -z "${GRPLIC+x}" ]; then
        GRPLIC=hpcsoft
      fi
      # Fix bad permissions for restricted software
      if [ ! -z "${GRPOWN+x}" ] && [ "$GRPOWN" != "hpcsoft" ]; then
        # Only fix directories with bad permissions
        if grep 'skip_files' <<< "$mode" &> /dev/null ; then
          echo "Skip_files mode: do not check files for bad permissions."
          #nfs4_setfacl -a A:fdg:$GRPLIC@osc.edu:RWXo,A:fdg:$GRPOWN@osc.edu:RX,A::OWNER@:RWX,A:g:GROUP@:RWX,A::EVERYONE@:RX $bad_dirs
          echo "nfs4_setfacl -a A:fdg:$GRPLIC@osc.edu:RWXo,A:fdg:$GRPOWN@osc.edu:RX,A::OWNER@:RWX,A:g:GROUP@:RWX,A::EVERYONE@:RX $bad_dirs"
        # Fix files and directories with bad permissions
        else
          for fil in $bad_dirs; do
            if [ -d $fil ]; then
              #nfs4_setfacl -a A:fdg:$GRPLIC@osc.edu:RWXo,A:fdg:$GRPOWN@osc.edu:RX,A::OWNER@:RWX,A:g:GROUP@:RWX,A::EVERYONE@:RX $fil
              echo "nfs4_setfacl -a A:fdg:$GRPLIC@osc.edu:RWXo,A:fdg:$GRPOWN@osc.edu:RX,A::OWNER@:RWX,A:g:GROUP@:RWX,A::EVERYONE@:RX $fil"
            elif [ -f $fil ]; then
              #nfs4_setfacl -a A:fdg:$GRPLIC@osc.edu:RWo,A:fdg:$GRPOWN@osc.edu:R,A::OWNER@:RW,A:g:GROUP@:RW,A::EVERYONE@:R $fil
              echo "nfs4_setfacl -a A:fdg:$GRPLIC@osc.edu:RWo,A:fdg:$GRPOWN@osc.edu:R,A::OWNER@:RW,A:g:GROUP@:RW,A::EVERYONE@:R $fil"
            fi
          done
        fi
      # Fix bad permissions for non-restricted software
      else
        # Fix directories with bad permissions
        if grep 'skip_files' <<< "$mode" &> /dev/null ; then
          echo "Skip_files mode: do not check files for bad permissions."
          #nfs4_setfacl -a A:fdg:hpcsoft@osc.edu:RWX,A::OWNER@:RWX,A:g:GROUP@:RWX,A::EVERYONE@:RX $bad_dirs
          echo "nfs4_setfacl -a A:fdg:hpcsoft@osc.edu:RWX,A::OWNER@:RWX,A:g:GROUP@:RWX,A::EVERYONE@:RX $bad_dirs"
        # Fix files and directories with bad permissions
        else
          for fil in $bad_dirs; do
            if [ -d $fil ]; then
              #nfs4_setfacl -a A:fdg:hpcsoft@osc.edu:RWX,A::OWNER@:RWX,A:g:GROUP@:RWX,A::EVERYONE@:RX $fil
              echo "nfs4_setfacl -a A:fdg:hpcsoft@osc.edu:RWX,A::OWNER@:RWX,A:g:GROUP@:RWX,A::EVERYONE@:RX $fil"
            elif [ -f $fil ]; then
              #nfs4_setfacl -a A:fdg:hpcsoft@osc.edu:RW,A::OWNER@:RW,A:g:GROUP@:RW,A::EVERYONE@:R $fil
              echo "nfs4_setfacl -a A:fdg:hpcsoft@osc.edu:RW,A::OWNER@:RW,A:g:GROUP@:RW,A::EVERYONE@:R $fil"
            fi
          done
        fi
      fi
      # Re-run check for bad permissions. If there are still any bad permission, print to log file/stdout
      echo "Permission re-test start"
      if grep 'skip_files' <<< "$mode" &> /dev/null ; then
        echo "Skip_files mode: do not check files for bad permissions."
        echo "find $topinstalldir $srcdir $moddir -type d ! -perm -u+r -ls"
        time find $topinstalldir $srcdir $moddir -type d ! -perm -u+r -ls || true
      else
        echo "find $topinstalldir $srcdir $moddir ! -perm -u+r -ls"
        time find $topinstalldir $srcdir $moddir ! -perm -u+r -ls || true
      fi
    fi
    echo "Permission test done"
  fi
}

finalize
