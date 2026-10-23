This is a sample DEMO of the insights from the profiler. The central server is inaccessible from outside our network. I included the screenshots of the sample demo for reference. Since profiling the application against our hardware generates property traces, we cannot share the original datasets. 

List of Contents
=====
1. HARP GitHub 
2. How much and How Long?
3. HARP - HPC Application Runtime Predictor
4. HARP Portal - In progress for Live - snapshots 
5. Publications and Presetations
6. Future Work

# GitHub
The code for HARP and the contaner Images could be found here: https://anonymous.4open.science/r/EstimateAppRes/Dockerfiles

# How much and How Long?
![Why HARP?](https://anonymous.4open.science/r/EstimateAppRes/DEMO/images/HowWellYouKnowYourJob.png)

Scientific workflows rely on High-Performance Computing (HPC), where varying hardware and software requirements are critical. Choosing the correct execution environment is vital for optimal resource utilization. Yet, users frequently encounter difficulties with manual approaches, resulting in suboptimal allocation and underutilization. Maximizing HPC efficiency in research requires users to comprehend their workflows and execution environments. To accurately estimate resource needs, machine learning models with workflow-specific data are essential. This work highlights the challenges of manual workflow optimization and promotes the use of AI-driven frameworks for precise application resource estimation and optimal allocation recommendations.


# HARP - HPC Application Runtime Predictor

HARP stands for "HPC Application Resource (runtime) Predictor." It is a solution introduced in the context of high-performance computing (HPC) to help optimize resource allocation for scientific tasks. HARP utilizes prediction-based recommendations and aims to improve the efficient use of resources in HPC environments by considering specific resource requirements and batch queueing policies. HARP emulates scientific workflows, estimates resource requirements, and incorporates policy-driven resource management to optimize HPC utilization and improve efficiency.

![Why HARP?](https://anonymous.4open.science/r/EstimateAppRes/DEMO/images/WhyHARP.png)

## Components of HARP
The HARP (HPC Application Resource Predictor) framework consists of several key components:

1. Workflow Emulation Module: This module is responsible for emulating scientific workflows, capturing how different tasks within a workflow interact with HPC resources. It profiles the usage requirements of workflows.

2. Resource Requirement Estimation Module: Using data gathered from the workflow emulation, this module estimates the resource requirements for future job executions. It utilizes regression models to predict memory and execution times accurately.

3. Policy-Driven Component: This component allows users to define and enforce policies for resource allocation. Users can customize rules for job prioritization, resource reservation, and other resource management aspects.

## Executing HARP from TAPIS
We've developed HARP containers for seamless integration with TAPIS. The HARP modules can run as TAPIS applications. The following Colab notebooks demonstrate the execution of HARP for profiling an example application (Euler Number) on both OSC and TACC systems:

* OSC Example: https://colab.research.google.com/drive/19GNHVNE6_b52JepLud1cpeVhg9ApgSlq
* TACC Example: https://colab.research.google.com/drive/1317dQqaKlGqcNULlOPP7i9i_vEvgYbWe

# HARP Portal - In progress for Live - snapshots 

Below are a couple pf screenshots from portal.

![Why HARP?](https://anonymous.4open.science/r/EstimateAppRes/DEMO/images/Harp_portal1.png)

The above image shows the features corelation and the influence of features on Walltime

![Why HARP?](https://anonymous.4open.science/r/EstimateAppRes/DEMO/images/Harp_portal2.png)

This is a sample cost-time output from the regression models results parsed to CI policied and billings. 


# Future Work
![Can it schedule automnatically?](https://anonymous.4open.science/r/EstimateAppRes/DEMO/images/SmartScheduler.png)

