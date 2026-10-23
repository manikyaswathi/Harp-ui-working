#!/bin/bash

#trap  "echo Sanity function faile" ERR
#set -eE
#set -o pipefail

# Software permission
# https://wiki.osc.edu/index.php/Sciapps/software_permission_ownership#Current_Policy

script_home="`dirname $(readlink -f $0)`"
source ${script_home}/../configs/config_${LMOD_SYSTEM_NAME}.cfg
source ${script_home}/aux_validate.sh

echo
echo Permission Check Tools 

grep -v '^#'  ${script_home}/restricted_software.txt |while read x
do
  IFS=', ' read -r -a params <<< "$(echo $x)"
  pkgname=${params[0]}
  group=${params[1]}
  grplic=${params[2]}
  depth=${params[3]}
  topinstalldir=$topdir/$pkgname
  topsrcdir=$srctop/$pkgname
  inst_user=$(stat -c %U $topinstalldir 2>/dev/null)
  src_user=$(stat -c %U $topsrcdir 2>/dev/null)
  printf "\n  Software: %s (%s/%s)\n" $pkgname $group $grplic
  printf "    Checking installation  : "
  check_install || continue
  printf "    Checking install group : "
  check_inst_group
  echo
  printf "    Checking  source group : "
  check_src_group
  echo
  printf "    Checking install perm  : "
  check_inst_perm
  echo 
  printf "    Checking  source perm  : "
  check_src_perm
  echo 
  printf "    Checking install facl  : "
  check_inst_facl
  echo
  printf "    Checking  source facl  : "
  check_src_facl
  echo
  if [ "${grplic}" != "hpcsoft" ]; then
    printf "    Checking install adm   : "
    check_inst_adm
    echo
  fi
done

echo
