exception() {
  status=$?
  err=$1
  if [ $status -ne 0 ]; then
    echo -n -e "\e[1;31mFAILED\e[0m $err"
    return 1
  else
    echo -n -e "\e[1;32mPASSED\e[0m "
  fi
}

check_install() {
  if [ ! -d ${topinstalldir} ]; then
    echo -e "\e[1;31mNOT INSTALLED\e[0m"
    return 1
  else
    echo -e "\e[1;32mINSTALLED\e[0m"
  fi
}

check_inst_group() {
  if [ "$grplic" = "hpcsoft" ]; then 
    bad_ones=$(find $topinstalldir ! -group hpcsoft -ls -quit)
    [ -z "$bad_ones" ]; exception "($inst_user) chgrp -R hpcsoft $topinstalldir ; $bad_ones" || return 1
  else
    grp=$(stat -c %G $topinstalldir)
    [ "$grp" = "$group" ]; exception "($inst_user) ($grp) chgrp $group $topinstalldir" || return 1
  fi
}

check_src_group() {
  if [ "$grplic" = "hpcsoft" ]; then 
    bad_ones=$(find $topsrcdir ! -group hpcsoft -ls -quit) 
    [ -z "$bad_ones" ]; exception "($src_user) chgrp -R hpcsoft $topsrcdir ; $bad_ones" || return 1
  else
    grp=$(stat -c %G $topsrcdir)
    [ "$grp" = "hpcsoft" ]; exception "($src_user) ($grp) chgrp hpcsoft $topsrcdir" || return 1
  fi
}

check_inst_perm() {
  if [ "$grplic" = "hpcsoft" ]; then 
    bad_ones=$(find $topinstalldir ! -perm -o+r -ls -quit) 
    [ -z "$bad_ones" ]; exception "($inst_user) chmod -R u+rwX,g+rwX,o+rX $topinstalldir ; $bad_ones" || return 1
  else
    inst_perm="750"
    dir_perm=$(stat -c %a $topinstalldir)
    [ "$dir_perm" = "$inst_perm" ]; exception "($inst_user) ($dir_perm) chmod $inst_perm $topinstalldir" || return 1
  fi
}

check_src_perm() {
  if [ "$grplic" = "hpcsoft" ]; then
    bad_ones=$(find $topsrcdir ! -perm -o+r -ls -quit) 
    [ -z "$bad_ones" ]; exception "($inst_user) chmod -R u+rwX,g+rwX,o+rX $topsrcdir ; $bad_ones" || return 1
  else
    src_perm="770"
    [ "$LMOD_SYSTEM_NAME" = "pitzer" ] && src_perm="2770"
    dir_perm=$(stat -c %a $topsrcdir)
    [ "$dir_perm" = "$src_perm" ]; exception "($src_user) ($dir_perm) chmod $src_perm $topsrcdir"  || return 1
  fi
}

check_inst_facl() {
  lic_acl="A:fdg:${grplic}@osc.edu:rwaDxtTnNcCoy"
  grp_acl="A:fdg:${group}@osc.edu:rxtncy"
  adm_acl="A:fd:adm@osc.edu:rxtncy"
  if [ "$grplic" = "hpcsoft" ]; then
    dir_acl=$(nfs4_getfacl $topinstalldir |grep "${grplic}@")
    msg_rm_acl="then remove $dir_acl recursively"
    [ -z "$dir_acl" ] && msg_rm_acl=""
    [ "$dir_acl" = "$lic_acl" ]; exception "($inst_user) nfs4_setfacl -R -a $lic_acl $topinstalldir $msg_rm_acl"  || return 1
    dir_acl=$(nfs4_getfacl $topinstalldir |grep "lic_main@")
    [ -z "$dir_acl" ]; exception "($inst_user) nfs4_setfacl -R -x $dir_acl $topinstalldir"  || return 1
  else
    dir_acl=$(nfs4_getfacl $topinstalldir |grep "${grplic}@")
    msg_rm_acl="then remove $dir_acl recursively"
    [ -z "$dir_acl" ] && msg_rm_acl=""
    [ "$dir_acl" = "$lic_acl" ]; exception "($inst_user) nfs4_setfacl -R -a $lic_acl $topinstalldir $msg_rm_acl"  || return 1
    dir_acl=$(nfs4_getfacl $topinstalldir |grep ${group}@)
    msg_rm_acl="then remove $dir_acl recursively"
    [ -z "$dir_acl" ] && msg_rm_acl=""
    [ "$dir_acl" = "$grp_acl" ]; exception "($inst_user) nfs4_setfacl -R -a $grp_acl $topinstalldir $msg_rm_acl"  || return 1
    # topinstalldir can be accessed by adm
    dir_acl=$(nfs4_getfacl $topinstalldir |grep adm@osc.edu)
    msg_rm_acl="then remove $dir_acl recursively"
    [ -z "$dir_acl" ] && msg_rm_acl=""
    [ "$dir_acl" = "$adm_acl" ]; exception "($inst_user) nfs4_setfacl -a $adm_acl $topinstalldir $msg_rm_acl" || return 1
  fi
}

check_src_facl() {
  lic_acl="A:fdg:${grplic}@osc.edu:rwaDxtTnNcCoy"
  if [ "$grplic" = "hpcsoft" ]; then
    dir_acl=$(nfs4_getfacl $topsrcdir |grep "${grplic}@")
    msg_rm_acl="then remove $dir_acl recursively"
    [ -z "$dir_acl" ] && msg_rm_acl=""
    [ "$dir_acl" = "$lic_acl" ]; exception "($src_user) nfs4_setfacl -R -a $lic_acl $topsrcdir $msg_rm_acl"  || return 1
    dir_acl=$(nfs4_getfacl $topsrcdir |grep "lic_main@")
    [ -z "$dir_acl" ]; exception "($src_user) nfs4_setfacl -R -x $dir_acl $topsrcdir "  || return 1
  else
    dir_acl=$(nfs4_getfacl $topsrcdir |grep "${grplic}@")
    msg_rm_acl="then remove $dir_acl recursively"
    [ -z "$dir_acl" ] && msg_rm_acl=""
    [ "$dir_acl" = "$lic_acl" ]; exception "($src_user) nfs4_setfacl -R -a $lic_acl $topsrcdir $msg_rm_acl"  || return 1
    dir_acl=$(nfs4_getfacl $topsrcdir |grep ${group}@)
    [ -z "$dir_acl" ]; exception "($src_user) nfs4_getfacl -x $dir_acl" || return 1
  fi
}

check_inst_adm() {
  adm_acl="A:fd:adm@osc.edu:rxtncy"
  find $topinstalldir -mindepth 1 -maxdepth $depth -type d |while read subdir
  do
    if [ $depth -gt 1 ]; then 
      ssubdir=${subdir/$topinstalldir\//}
      IFS='/' read -r -a array <<< "$ssubdir"
      dep=${array[0]}
      if [ "$dep" != "intel" ] && [ "$dep" != "gnu" ] && [ "$dep" != "pgi" ]; then
        test ! -z ${array[1]} && continue
      fi
    fi
    dir_acl=$(nfs4_getfacl $subdir |grep adm@osc.edu)
    #echo  $subdir $dir_acl
    [ "$dir_acl" = "$adm_acl" ]; exception "($inst_user) nfs4_setfacl -a $adm_acl $subdir" || return 1
  done
}

