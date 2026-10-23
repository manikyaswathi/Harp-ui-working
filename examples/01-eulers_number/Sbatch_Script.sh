#!/bin/bash
#SBATCH --job-name=ProfileEluerNumberGenerator
#SBATCH --time=1:00:00
#SBATCH --nodes=1 --ntasks-per-node=28
#   SBATCH --gpus-per-node=1
#SBATCH --output=myjob.out.%j
#SBATCH --account=<OSC_Project>



module use $HOME/osc_apps/lmodfiles
module load harp 
export CONDA_HOME=<path_to_conda_home>/miniconda3
source $CONDA_HOME/bin/activate
source activate harp_env

cd <path_to_harp_download>/harp/examples/01-eulers_number
chmod 755 *
harp pipeline_config.json


