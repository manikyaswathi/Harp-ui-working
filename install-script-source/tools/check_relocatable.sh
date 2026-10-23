#!/bin/bash

# Reference
# https://stackoverflow.com/questions/13769141/can-i-change-rpath-in-an-already-compiled-binary
# https://codeyarns.com/2017/11/02/how-to-change-rpath-or-runpath-of-executable/

script_home="`dirname $(readlink -f $0)`"
source ${script_home}/../configs/config_${LMOD_SYSTEM_NAME}.cfg

mpi=$1
mpiver1=$2
mpiver2=$3

help() {
  echo -e "\nUsage: $0 mpi mpiver_orig mpiver_new"
  echo -e "\nE.g. $0 mvapich2 2.3 2.3.2"
  echo -e "\n Variables: VERBOSE=1\n"
  exit 0
}

check_ldd_rpath() {
  instdir=$1 
  find ${instdir}/ -type f -maxdepth 2 -exec file {} \; |grep ELF |cut -d':' -f1 |while read x
  do 
    # check RPATH
    module reset >& /dev/null
    module load ${mpi}/${mpiver1} >& /dev/null
    if readelf -d $x |grep RPATH |grep "/opt/${mpi}/.*/.*/${mpiver1}/\|${srctop}/${mpi}/.*/.*/${mpiver1}/" >& /dev/null ; then
       echo -e "[ \e[1;31mFAILED\e[0m ] ELF file $x is not relocatable: rpath found"
       return 1
    fi
    # check dynamic libraries
    module reset >& /dev/null
    module load ${mpi}/${mpiver1} >& /dev/null
    count1=`ldd $x |grep "/opt/${mpi}/.*/.*/${mpiver1}/\|${scrtop}/${mpi}/.*/.*/${mpiver1}/" -c`
    module load ${mpi}/${mpiver2} >& /dev/null
    count2=`ldd $x |grep "/opt/${mpi}/.*/.*/${mpiver2}/\|${scrtop}/${mpi}/.*/.*/${mpiver2}/" -c`
    if [ $count1 -ne $count2 ]; then
       echo -e "[ \e[1;31mFAILED\e[0m ] ELF file $x is not relocatable: failed in ldd check"
       return 1
    fi
  done
  return 0
}

[ $# -lt 3 ] && help

echo "Checking ELF files up to the second descending levels for applications in ${topdir}/*/*/*/${mpi}/${mpiver1}/"
ls -d ${topdir}/*/*/*/${mpi}/${mpiver1}/*  |while read d
do
  [ "$VERBOSE" = "1" ] && echo $d
  check_ldd_rpath $d
  test $? -ne 0 && continue
done
