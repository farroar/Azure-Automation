#! /usr/bin/env python
'''
##############################################################################
This script takes a CSV file and builds an Azure environment across multiple 
subscriptions. It uses a Jinja2 template file to create ARM parameter files for
each line of the CSV. It then uses these parameter files against a common
ARM template to build out the environment.

And as an added bonus, it peers the vnets all back to the 'hub'

using the -b flag sets the script to build only. It will only create the .json
files and will NOT send to the Azure subscription

Nathan Farrar - 17-Aug-2019
##############################################################################
'''

import sys
import optparse
import os
import getpass
import csv
from jinja2 import Template
import time
import re


class vnet_object(object):

    def __init__(self,name, subscriptionId, location, resourceGroup, prefix, orgName):
        self.name = name
        self.subscriptionId = subscriptionId
        self.location = location
        self.resourceGroup = resourceGroup
        self.prefix = prefix
        self.orgName = orgName
        self.subnets = []
        self.peers = []

    def add_peer(self, peerId, peerName, peerPrefix, peerRG, orgName):
        self.peers.append({
            'peerId': peerId,
            'peerName': peerName,
            'peerPrefix': peerPrefix,
            'peerRG': peerRG,
            'orgName': orgName
        })
        return self.peers

    def delete_peer(self, peer):
        self.peers = [i for i in self.peers if not (i['peerName'] == peer)]
        return self.peers

    def add_subnet(self, prefix, name):
        self.subnets.append({
            'name':name,
            'prefix':prefix
        })
        return self.subnets

    def delete_subnet(self, name):
        self.subnets = [i for i in self.subnets if not (i['name'] == name)]
        return self.subnets


class logfile(object):

    def __init__(self, logfile_name, location):
        self.logfile_name = logfile_name
        self.logfile_location = location
        self.log_list = []

    def append_log(self, line):
        self.log_list.append(line)

    def write_log(self):
        f = open((self.logfile_location + self.logfile_name), 'w')
        for line in self.log_list:
            f.write(line + '\n')
        f.close()

def vnet_build(build_file):
    with open(build_file, mode='r', encoding='utf-8-sig') as f:
        build_env = csv.DictReader(f)
    return build_env

def test_vm_build(vnets, vnet_name, parameters_file, template_file):
    with open(parameters_file) as f:
        parameters_template = Template(f.read())

    build_file = parameters_template.render(
        location = vnets[vnet_name].location,
        networkInterfaceName = vnets[vnet_name].name + '-testVM-NIC',
        subnetName = vnets[vnet_name].name + '-presentation-subnet',
        VMName = vnets[vnet_name].name + '-testVM',
        resourceGroup = vnets[vnet_name].resourceGroup,
        subscriptionId = vnets[vnet_name].subscriptionId,
        vnetName = vnets[vnet_name].orgName + '-' + vnets[vnet_name].name + '-vnet'
    )
    build_file_name = vnets[vnet_name].orgName + '/' + vnets[vnet_name].orgName + '-' + vnets[vnet_name].name + '-testVM.json'
    with open(build_file_name, 'w') as f:
        f.write(build_file)


def main():

    '''
    #get user input and login to Azure
    user = input("Enter your Azure account: ")
    password = getpass.getpass()
    print(f'******** Logging into azure with {user} ********')
    '''

    
    fgt_deploy = False
 
    parser = optparse.OptionParser()

    parser.add_option('-w', '--build-worksheet', action="store", dest="build_file", help="Build csv", default='azureBuild-worksheet.csv')
    parser.add_option('-p', '--peering-worksheet', action="store", dest="peering_file", help="Peering csv", default='azureBuild-peering-worksheet.csv')
    parser.add_option('-f', '--firewall-worksheet', action="store", dest="firewall_file", help="Firewwall csv", default='azureBuild-fortigate-worksheet.csv')
    parser.add_option('-b', '--build-only', action='store_true', dest='build_only', help='Build environment but do not deploy', default=False)
    parser.add_option('-t', '--test-vm', action='store_true', dest='test_vm', help='Deploy test VM in each vnet', default=False)

    options, args = parser.parse_args()

    #build_worksheet_file = options.build_file
    #peering_worksheet_file = options.peering_file
    #fortigate_worksheet_file = options.firewall_file

    #define source data
    build_worksheet_file = 'azureBuild-worksheet.csv'
    peering_worksheet_file = 'azureBuild-peering-worksheet.csv'
    fortigate_worksheet_file = 'azureBuild-fortigate-worksheet.csv'
    
    #define arm templates
    build_template_file = 'azureBuild-template.json'
    peering_template_file = 'azureBuild-peeringTemplate.json'
    test_vm_template_file = 'azureBuild-testVMTemplate.json'
    fortigate_template_file = 'azureBuild-singleFGT-template.json'

    #define Jinja2 templates
    build_parameters_template_file = "azureBuild-parametersTemplate.j2"
    peering_parameters_template_file = 'azureBuild-peeringParametersTemplate.j2'
    test_vm_parameters_template_file = 'azureBuild-testVMparametersTemplate.j2'
    fortigate_parameters_template_file = 'azureBuild-SingleFGTParametersTemplate.j2'

    #parse csv file and build vnet objects
    vnets = {}
    with open(build_worksheet_file, mode='r', encoding='utf-8-sig') as f:
        build_env = csv.DictReader(f)
        for row in build_env: 
            rg = row['vnetName'] + '-network-rg'

            #build the vnet object with the inital values requried of all vnets
            vnets[row['vnetName']] = vnet_object(row['vnetName'], row['subscriptionId'], row['location'], rg, row['vnetPrefix'], row['orgName'])      
            vnets[row['vnetName']].add_subnet(row['subnetOnePrefix'], row['subnetOneName'])
            vnets[row['vnetName']].add_subnet(row['subnetTwoPrefix'], row['subnetTwoName'])
            vnets[row['vnetName']].add_subnet(row['subnetThreePrefix'], row['subnetThreeName'])
    
    
    #read in Jinja2 template file for vnet environment parameters
    with open(build_parameters_template_file) as f:
        build_parameters_template = Template(f.read())

    #parse csv file for vnet build parameters. These are used to create a file based off of Jinja2 template.
    #with open(build_worksheet_file, mode='r', encoding='utf-8-sig') as f:
    #    build_env = csv.DictReader(f) 
    
    for vnet in vnets: 
        build_file = build_parameters_template.render(
            orgName = vnets[vnet].orgName,
            vnetName = vnets[vnet].name,
            vnetPrefix = vnets[vnet].prefix,
            subnetOneName = vnets[vnet].subnets[0]['name'],
            subnetOnePrefix = vnets[vnet].subnets[0]['prefix'],
            subnetTwoName = vnets[vnet].subnets[1]['name'],
            subnetTwoPrefix = vnets[vnet].subnets[1]['prefix'],
            subnetThreeName = vnets[vnet].subnets[2]['name'],
            subnetThreePrefix = vnets[vnet].subnets[2]['prefix'],
        )
        build_file_name = vnets[vnet].orgName + '/' + vnets[vnet].orgName + '-' + vnets[vnet].name + '.json'
        with open(build_file_name, 'w') as f:
            f.write(build_file)
    
    #read in Jinja2 template file for peering environment parameters
    with open(peering_parameters_template_file) as f:
        peering_parameters_template = Template(f.read())    

    with open(peering_worksheet_file, mode='r', encoding='utf-8-sig') as f:
        peering_env = csv.DictReader(f)
        for row in peering_env:
            peering_parameters = peering_parameters_template.render(
                localVnetName = row['localVnetName'],
                localVnetPrefix = row['localVnetPrefix'],
                remoteVnetName = row['remoteVnetName'],
                remoteVnetPrefix = row['remoteVnetPrefix'],
                remoteVnetSubscription = row['remoteVnetSubscription'],
                vnetPeeringName = row['vnetPeeringName'],
                remoteVnetResourceGroup = row['remoteVnetResourceGroup'],
                orgName = row['orgName'],
            )  
            peering_parameters_file = vnets[vnet].orgName + '/' + row['orgName'] + '-' + row['localVnetName'] + '-' + row['remoteVnetName'] + '-peering.json'
            with open(peering_parameters_file, 'w') as f:
                f.write(peering_parameters)   
        
    
    #iterate through vnet objects and deploy if build_only is not set to True
    if not options.build_only:
        for vnet in vnets:
            vnet_name = vnets[vnet].name
            org_name = vnets[vnet].orgName
            subscription = vnets[vnet].subscriptionId
            resource_group = f'{vnet_name}-network-rg'
            resource_location = vnets[vnet].location
            parameters_file = f'{org_name}/{org_name}-{vnet_name}.json'

            #point to current subscription
            print(f'******** Setting subscription to {vnet_name} ********')
            set_subscription = f'az account set --subscription {subscription}'
            os.system(set_subscription)

            #create resource group
            print(f'******** Creating resource group in {vnet_name} ********')
            create_resource_group = f'az group create --name {resource_group} --location {resource_location}'
            os.system(create_resource_group)
        
            #deploy environment
            print(f'******** Deploying {vnet_name} environment ********')
            deploy_command = f'az group deployment create --verbose --name autoDeploy --resource-group {resource_group} --template-file {build_template_file} --parameters {parameters_file}'
            os.system(deploy_command)
    
    if not options.build_only:
    #iterate through peering worksheet csv file and setup up vnet peering if build_only is not set to True
        with open(peering_worksheet_file, mode='r', encoding='utf-8-sig') as f:
            peering_env = csv.DictReader(f)
            for row in peering_env:
                local_vnet_name = row['localVnetName']
                org_name = row['orgName']
                local_vnet_subscription = row['localVnetSubscription']
                local_resource_group = row['localVnetResourceGroup']
                remote_vnet_name = row['remoteVnetName']

                peering_parameters_file = f'{org_name}/{org_name}-{local_vnet_name}-{remote_vnet_name}-peering.json'

                #point to current subscription
                print(f'******** Setting subscription to {local_vnet_name} ********')
                set_subscription = f'az account set --subscription {local_vnet_subscription}'
                os.system(set_subscription)

                #peer Vnets based on peering worksheet
                print(f'******** Peering {local_vnet_name} to {remote_vnet_name} ********')
                deploy_command = f'az group deployment create --verbose --name autoDeploy --resource-group {local_resource_group} --template-file {peering_template_file} --parameters {peering_parameters_file}'
                os.system(deploy_command)
    
    #if test_vm flag is set, create test VM deploy files
    if options.test_vm:
        for vnet in vnets:
            resource_group = vnets[vnet].resourceGroup
            test_vm_build(vnets, vnets[vnet].name, test_vm_parameters_template_file, test_vm_template_file)
            if not options.build_only:
                #if build only flag is not set, deploy the VMs
                vnet_name = vnets[vnet].name
                org_name = vnets[vnet].orgName
                subscription_id = vnets[vnet].subscriptionId
                testVM_parameters_file = f'{org_name}/{org_name}-{vnet_name}-testVM.json'
             
                print(resource_group)

                #point to current subscription
                print(f'******** Setting subscription to {vnet_name} ********')
                set_subscription = f'az account set --subscription {subscription_id}'
                os.system(set_subscription)

                #deploy test VM in vnet
                print(f'******** deployting test VM in {vnet_name} ********')
                deploy_command = f'az group deployment create --verbose --name autoDeploy --resource-group {resource_group} --template-file {test_vm_template_file} --parameters {testVM_parameters_file}'
                os.system(deploy_command)

    #test for single FortiGate VM deployment if fgt_deploy is set to true
    if fgt_deploy:
        with open(fortigate_worksheet_file, mode='r', encoding='utf-8-sig') as f:
            fortigate_env = csv.DictReader(f)
            for row in fortigate_env:
                local_vnet_name = row['vnetName']
                local_vnet_subscription = row['vnetSubscription']
                local_resource_group = row['vnetResourceGroup']

                #point to current subscription
                print(f'******** Setting subscription to {local_vnet_name} ********')
                set_subscription = f'az account set --subscription {local_vnet_subscription}'
                #os.system(set_subscription)

                #peer Vnets based on peering worksheet
                print(f'******** Building FortiGate VM in {local_vnet_name} ********')
                deploy_command = f'az group deployment create --verbose --name autoDeploy --resource-group {local_resource_group} --template-file {fortigate_template_file} --parameters {fortigate_parameters_template_file}'
                #os.system(deploy_command)
    
if __name__ == '__main__':
    main()